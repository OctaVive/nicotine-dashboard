"""Nicotine+ plugin: log completed uploads into PostgreSQL."""

from __future__ import annotations

import os
import queue
import threading
import time
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from pynicotine.pluginsystem import BasePlugin
except Exception:  # pragma: no cover
    BasePlugin = object

try:
    import psycopg  # type: ignore
except Exception:  # pragma: no cover
    psycopg = None

try:
    import psycopg2  # type: ignore
except Exception:  # pragma: no cover
    psycopg2 = None


class UploadEvent:
    def __init__(
        self,
        occurred_at: datetime,
        peer_username: str,
        peer_ip: Optional[str],
        country_code: Optional[str],
        country_name: Optional[str],
        file_path: Optional[str],
        bytes_transferred: Optional[int],
        transfer_direction: str = "upload_from_me",
    ) -> None:
        self.occurred_at = occurred_at
        self.peer_username = peer_username
        self.peer_ip = peer_ip
        self.country_code = country_code
        self.country_name = country_name
        self.file_path = file_path
        self.bytes_transferred = bytes_transferred
        self.transfer_direction = transfer_direction


class Plugin(BasePlugin):
    settings = {
        "db_host": "127.0.0.1",
        "db_port": 5432,
        "db_name": "nicotine",
        "db_user": "nicotine",
        "db_password": "nicotine",
        "db_sslmode": "prefer",
        "geoip_online_url_template": "https://ipwho.is/{ip}",
        "geoip_online_url_template_backup": (
            "http://ip-api.com/json/{ip}?fields=status,message,country,countryCode"
        ),
        "geoip_online_timeout_seconds": 4,
        "geoip_resolve_wait_seconds": 0.8,
        "geoip_online_retry_count": 2,
        "geoip_online_retry_delay_seconds": 0.5,
        "unknown_country_name": "Unknown",
    }

    metasettings = {
        "db_host": {"description": "PostgreSQL IP or hostname", "type": "str"},
        "db_port": {"description": "PostgreSQL port", "type": "int"},
        "db_name": {"description": "PostgreSQL database name", "type": "str"},
        "db_user": {"description": "PostgreSQL username", "type": "str"},
        "db_password": {"description": "PostgreSQL password", "type": "str"},
        "db_sslmode": {
            "description": "PostgreSQL sslmode (disable/allow/prefer/require)",
            "type": "str",
        },
        "geoip_online_url_template": {
            "description": "Primary online IP lookup URL template (use {ip})",
            "type": "str",
        },
        "geoip_online_url_template_backup": {
            "description": "Backup online lookup if primary fails or returns no country (use {ip}; empty to disable)",
            "type": "str",
        },
        "geoip_online_timeout_seconds": {
            "description": "Online IP lookup timeout in seconds",
            "type": "int",
        },
        "geoip_resolve_wait_seconds": {
            "description": "Seconds to wait before a second IP/country pass (async user resolve race)",
            "type": "float",
            "minimum": 0,
            "maximum": 10,
            "stepsize": 0.1,
        },
        "geoip_online_retry_count": {
            "description": "Extra online geo lookup attempts after failures (0 = single attempt)",
            "type": "int",
            "minimum": 0,
            "maximum": 5,
        },
        "geoip_online_retry_delay_seconds": {
            "description": "Delay between online geo retry attempts",
            "type": "float",
            "minimum": 0,
            "maximum": 5,
            "stepsize": 0.1,
        },
        "unknown_country_name": {"description": "Country name when unknown", "type": "str"},
    }

    def init(self) -> None:
        self._queue: "queue.Queue[UploadEvent]" = queue.Queue(maxsize=1000)
        self._stop_event = threading.Event()
        self._db_conn = None
        self._resolved_users: dict[str, dict[str, Any]] = {}
        self._worker_thread = threading.Thread(
            target=self._worker_loop, name="nicotine-upload-geo-worker", daemon=True
        )
        self._worker_thread.start()
        self.log("Upload Geo plugin initialized")

    def disable(self) -> None:
        self._stop_event.set()
        if hasattr(self, "_worker_thread") and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
        self._close_db_connection()
        self.log("Upload Geo plugin stopped")

    def upload_finished_notification(self, *args: Any, **kwargs: Any) -> None:
        event = self._build_event_from_callback(*args, **kwargs)
        if event is None:
            return
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self.log("Upload queue full; dropping event")

    def user_resolve_notification(
        self, user: str, ip_address: str, port: int, country: str
    ) -> None:
        del port  # Unused for now, but part of callback signature.
        normalized_country = self._normalize_country_code(country)
        self._resolved_users[str(user)] = {
            "ip_address": ip_address,
            "country_code": normalized_country,
        }

    def _build_event_from_callback(self, *args: Any, **kwargs: Any) -> Optional[UploadEvent]:
        # Nicotine+ 3.x: upload_finished_notification(user, virtual_path, real_path) — three strings.
        # Do not treat the username string as a Transfer object.
        transfer = kwargs.get("transfer")
        if transfer is None and args and not isinstance(args[0], str):
            transfer = args[0]

        positional_username = args[0] if args and isinstance(args[0], str) else None
        positional_path = args[1] if len(args) > 1 and isinstance(args[1], str) else None

        peer_username = (
            self._coalesce_attr(transfer, ("username", "user"))
            or kwargs.get("username")
            or positional_username
            or ""
        )
        if not peer_username:
            self.log(
                "Upload callback ignored: missing username "
                f"(args_count={len(args)}, kwargs={list(kwargs.keys())})"
            )
            return None
        self._request_user_resolve(peer_username)

        file_path = (
            self._coalesce_attr(transfer, ("virtual_path", "filename", "path"))
            or kwargs.get("virtual_path")
            or kwargs.get("filename")
            or positional_path
        )
        real_path = kwargs.get("real_path")
        if real_path is None and len(args) > 2 and isinstance(args[2], str):
            real_path = args[2]

        size_candidate = self._coalesce_attr(
            transfer, ("size", "bytes", "transferred", "transferred_bytes_total")
        )
        if size_candidate is None:
            size_candidate = kwargs.get("size")
        bytes_transferred = self._safe_int(size_candidate)
        if bytes_transferred is None and len(args) > 2 and isinstance(args[2], (int, float)):
            bytes_transferred = self._safe_int(args[2])
        if bytes_transferred is None:
            bytes_transferred = self._upload_transfer_size(peer_username, file_path)
        if bytes_transferred is None:
            bytes_transferred = self._safe_file_size(real_path)
        peer_ip = self._extract_ip(peer_username, transfer=transfer, kwargs=kwargs)
        country_code, country_name = self._resolve_country(
            peer_username=peer_username, peer_ip=peer_ip, transfer=transfer, kwargs=kwargs
        )

        return UploadEvent(
            occurred_at=datetime.now(timezone.utc),
            peer_username=str(peer_username),
            peer_ip=peer_ip,
            country_code=country_code,
            country_name=country_name,
            file_path=file_path,
            bytes_transferred=bytes_transferred,
        )

    def _upload_transfer_size(self, username: str, virtual_path: Optional[str]) -> Optional[int]:
        if not virtual_path:
            return None
        uploads = self._coalesce_attr(self.core, ("uploads",))
        if uploads is None:
            return None
        transfers = getattr(uploads, "transfers", None)
        if not isinstance(transfers, dict):
            return None
        t = transfers.get(username + virtual_path)
        if t is None:
            return None
        return self._safe_int(getattr(t, "size", None))

    @staticmethod
    def _safe_file_size(path: Any) -> Optional[int]:
        if path is None:
            return None
        p = str(path).strip()
        if not p:
            return None
        try:
            if os.path.isfile(p):
                return int(os.path.getsize(p))
        except OSError:
            return None
        return None

    def _extract_ip(
        self, peer_username: str, transfer: Any = None, kwargs: Optional[dict[str, Any]] = None
    ) -> Optional[str]:
        kwargs = kwargs or {}
        cached = self._resolved_users.get(peer_username, {})
        candidate = (
            self._coalesce_attr(transfer, ("ip_address", "ip", "addr"))
            or kwargs.get("ip")
            or kwargs.get("ip_address")
            or cached.get("ip_address")
            or self._lookup_user_attr(peer_username, "ip_address", "ip")
        )
        if not candidate:
            return None
        ip = str(candidate).strip()
        if ":" in ip and ip.count(".") == 3:
            ip = ip.rsplit(":", 1)[0]
        return ip or None

    def _resolve_country(
        self,
        peer_username: str,
        peer_ip: Optional[str],
        transfer: Any = None,
        kwargs: Optional[dict[str, Any]] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        kwargs = kwargs or {}
        cached = self._resolved_users.get(peer_username, {})
        from_nicotine = (
            self._coalesce_attr(transfer, ("country", "country_code"))
            or kwargs.get("country")
            or kwargs.get("country_code")
            or cached.get("country_code")
            or self._lookup_user_attr(peer_username, "country", "country_code")
        )
        nicotine_code = self._normalize_country_code(from_nicotine)

        if peer_ip:
            code, name = self._country_from_online_ip(peer_ip)
            if code:
                return code, name
            if nicotine_code:
                return nicotine_code, nicotine_code
            return None, self.settings.get("unknown_country_name", "Unknown")

        if nicotine_code:
            return nicotine_code, nicotine_code
        return None, self.settings.get("unknown_country_name", "Unknown")

    def _request_user_resolve(self, peer_username: str) -> None:
        users = self._coalesce_attr(self.core, ("users",))
        if not users:
            return

        for method_name in (
            "request_ip_address",
            "request_ip",
            "request_user_ip_address",
            "request_user_resolve",
        ):
            method = getattr(users, method_name, None)
            if callable(method):
                try:
                    method(peer_username)
                    return
                except Exception:
                    continue

    @staticmethod
    def _normalize_country_code(value: Any) -> Optional[str]:
        if value is None:
            return None

        text = str(value).strip().lower()
        if not text:
            return None

        # Common Nicotine+/UI forms: "flag_us", "country_us", "us"
        for prefix in ("flag_", "country_"):
            if text.startswith(prefix):
                text = text[len(prefix) :]
                break

        # Keep only last token after separators, e.g. "flag-us"
        for sep in ("-", "_", " "):
            if sep in text:
                text = text.split(sep)[-1]

        if len(text) == 2 and text.isalpha():
            return text.upper()
        return None

    def _country_from_online_ip(self, peer_ip: str) -> tuple[Optional[str], Optional[str]]:
        timeout = self._safe_int(self.settings.get("geoip_online_timeout_seconds")) or 4
        primary = str(self.settings.get("geoip_online_url_template", "")).strip()
        backup = str(self.settings.get("geoip_online_url_template_backup", "")).strip()

        for template in (primary, backup):
            if not template or "{ip}" not in template:
                continue
            result = self._country_from_online_template(peer_ip, template, timeout)
            if result[0]:
                return result
        return None, None

    def _country_from_online_ip_with_retries(self, peer_ip: str) -> tuple[Optional[str], Optional[str]]:
        extra = self._safe_int(self.settings.get("geoip_online_retry_count"))
        if extra is None:
            extra = 2
        extra = max(0, min(extra, 5))
        attempts = 1 + extra
        delay = self._safe_float(self.settings.get("geoip_online_retry_delay_seconds"))
        if delay is None:
            delay = 0.5
        delay = max(0.0, min(delay, 5.0))

        last: tuple[Optional[str], Optional[str]] = (None, None)
        for i in range(attempts):
            if i > 0 and delay > 0:
                time.sleep(delay)
            last = self._country_from_online_ip(peer_ip)
            if last[0]:
                return last
        return last

    def _country_from_online_template(
        self, peer_ip: str, template: str, timeout: int
    ) -> tuple[Optional[str], Optional[str]]:
        url = template.replace("{ip}", urllib.parse.quote(peer_ip, safe=""))
        try:
            with urllib.request.urlopen(url, timeout=max(timeout, 1)) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return None, None

        return self._parse_online_geo_payload(payload)

    def _parse_online_geo_payload(self, payload: Any) -> tuple[Optional[str], Optional[str]]:
        if not isinstance(payload, dict):
            return None, None

        # ipwho.is style
        if payload.get("success") is False:
            return None, None

        # ip-api.com style
        if payload.get("status") == "fail":
            return None, None

        code = (
            payload.get("country_code")
            or payload.get("countryCode")
            or payload.get("country_iso_code")
            or payload.get("country")
        )
        name = (
            payload.get("country_name")
            or payload.get("countryName")
            or payload.get("country")
        )

        normalized = self._normalize_country_code(code)
        if normalized:
            return normalized, str(name) if name else None

        # Some APIs return only a full country name; try normalizing that (usually fails for long names).
        normalized = self._normalize_country_code(name)
        if normalized:
            return normalized, str(name) if name else None

        return None, None

    def _refresh_peer_ip(self, peer_username: str) -> Optional[str]:
        return self._extract_ip(peer_username, transfer=None, kwargs=None)

    def _nicotine_country_fallback(self, peer_username: str) -> Optional[str]:
        cached = self._resolved_users.get(peer_username, {})
        from_nicotine = cached.get("country_code") or self._lookup_user_attr(
            peer_username, "country", "country_code"
        )
        code = self._normalize_country_code(from_nicotine)
        if code:
            return code
        return None

    def _enrich_event_before_insert(self, event: UploadEvent) -> None:
        """Re-resolve IP/country in worker: fixes race where user_resolve arrives after upload_finished."""
        unknown = self.settings.get("unknown_country_name", "Unknown")
        wait_sec = self._safe_float(self.settings.get("geoip_resolve_wait_seconds"))
        if wait_sec is None:
            wait_sec = 0.8
        wait_sec = max(0.0, min(wait_sec, 10.0))

        def try_fill() -> None:
            ip = self._refresh_peer_ip(event.peer_username)
            if ip:
                event.peer_ip = ip
            if event.country_code is None and event.peer_ip:
                code, name = self._country_from_online_ip_with_retries(event.peer_ip)
                if code:
                    event.country_code = code
                    event.country_name = name if name else event.country_name
            if event.country_code is None:
                nc = self._nicotine_country_fallback(event.peer_username)
                if nc:
                    event.country_code = nc
                    event.country_name = nc
            if event.country_code is None:
                event.country_name = unknown

        try_fill()
        if (event.peer_ip is None or event.country_code is None) and wait_sec > 0:
            time.sleep(wait_sec)
            try_fill()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            self._enrich_event_before_insert(event)
            self._persist_with_retry(event)
            self._queue.task_done()

    def _persist_with_retry(self, event: UploadEvent) -> None:
        for attempt in range(1, 6):
            try:
                self._ensure_db_connection()
                self._insert_event(event)
                return
            except Exception as exc:
                self.log(f"DB write failed (attempt {attempt}/5): {exc}")
                self._close_db_connection()
                time.sleep(min(2**attempt, 20))
        self.log("Dropping event after retries exhausted")

    def _db_kwargs(self) -> dict[str, Any]:
        return {
            "host": self.settings.get("db_host"),
            "port": int(self.settings.get("db_port", 5432)),
            "dbname": self.settings.get("db_name"),
            "user": self.settings.get("db_user"),
            "password": self.settings.get("db_password"),
            "sslmode": self.settings.get("db_sslmode", "prefer"),
        }

    def _ensure_db_connection(self) -> None:
        if self._db_conn is not None:
            try:
                cursor = self._db_conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return
            except Exception:
                self._close_db_connection()

        if psycopg is not None:
            self._db_conn = psycopg.connect(**self._db_kwargs())
            return
        if psycopg2 is not None:
            self._db_conn = psycopg2.connect(**self._db_kwargs())
            return
        raise RuntimeError("Install psycopg or psycopg2 to enable PostgreSQL writes")

    def _insert_event(self, event: UploadEvent) -> None:
        sql = """
            INSERT INTO download_events (
                occurred_at,
                peer_username,
                peer_ip,
                country_code,
                country_name,
                file_path,
                bytes_transferred,
                transfer_direction
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor = self._db_conn.cursor()
        try:
            cursor.execute(
                sql,
                (
                    event.occurred_at,
                    event.peer_username,
                    event.peer_ip,
                    event.country_code,
                    event.country_name,
                    event.file_path,
                    event.bytes_transferred,
                    event.transfer_direction,
                ),
            )
            self._db_conn.commit()
        finally:
            cursor.close()

    def _close_db_connection(self) -> None:
        conn = self._db_conn
        if conn is None:
            return
        try:
            conn.close()
        except Exception:
            pass
        self._db_conn = None

    def _lookup_user_attr(self, username: str, *attr_names: str) -> Optional[Any]:
        users = self._coalesce_attr(self.core, ("users",))
        if not users:
            return None

        user_obj = users.get(username) if isinstance(users, dict) else getattr(users, username, None)
        for attr_name in attr_names:
            value = self._coalesce_attr(user_obj, (attr_name,))
            if value is not None:
                return value
        return None

    @staticmethod
    def _coalesce_attr(obj: Any, attr_names: tuple[str, ...]) -> Optional[Any]:
        if obj is None:
            return None
        for name in attr_names:
            value = obj.get(name) if isinstance(obj, dict) and name in obj else getattr(obj, name, None)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def log(self, message: str) -> None:
        if hasattr(super(), "log"):
            try:
                return super().log(message)
            except Exception:
                pass
        print(f"[nicotine-upload-geo] {message}")


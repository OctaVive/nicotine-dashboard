-- 1) Country totals for world map panels
SELECT
    COALESCE(country_code, 'UNK') AS country_code,
    COALESCE(country_name, 'Unknown') AS country_name,
    COUNT(*) AS downloads
FROM download_events
WHERE occurred_at BETWEEN $__timeFrom() AND $__timeTo()
GROUP BY 1, 2
ORDER BY downloads DESC;

-- 2) Time series grouped by country
SELECT
    $__timeGroupAlias(occurred_at, '1h') AS time,
    COALESCE(country_code, 'UNK') AS metric,
    COUNT(*) AS value
FROM download_events
WHERE $__timeFilter(occurred_at)
GROUP BY 1, 2
ORDER BY 1;

-- 3) Top countries table
SELECT
    COALESCE(country_code, 'UNK') AS country_code,
    COALESCE(country_name, 'Unknown') AS country_name,
    COUNT(*) AS downloads
FROM download_events
WHERE $__timeFilter(occurred_at)
GROUP BY 1, 2
ORDER BY downloads DESC
LIMIT 25;

-- 4) Raw events drill-down
SELECT
    occurred_at,
    peer_username,
    host(peer_ip) AS peer_ip,
    COALESCE(country_code, 'UNK') AS country_code,
    COALESCE(country_name, 'Unknown') AS country_name,
    file_path,
    bytes_transferred
FROM download_events
WHERE $__timeFilter(occurred_at)
ORDER BY occurred_at DESC
LIMIT 500;

-- 🐀 Gold Events by Device
-- Platform analysis aggregated by device type
--
-- @name: gold_events_by_device
-- @materialized: table
-- @owner: analytics-team

SELECT
    device,
    COUNT(*) AS total_events,
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(CASE WHEN event_type = 'PURCHASE' THEN 1 END) AS purchases,
    ROUND(
        COUNT(CASE WHEN event_type = 'PURCHASE' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0),
        2
    ) AS conversion_rate,
    ROUND(AVG(session_duration_sec), 1) AS avg_session_duration,
    COUNT(DISTINCT country) AS countries_reached
FROM {{ ref('silver.events') }}
GROUP BY device
ORDER BY total_events DESC

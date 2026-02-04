-- 🐀 Gold: Page Metrics
-- Traffic analysis aggregated by page URL
--
-- @name: gold_page_metrics
-- @materialized: table
-- @owner: analytics-team

SELECT
    page_url,
    COUNT(*) AS total_events,
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(DISTINCT session_id) AS unique_sessions,
    COUNT(CASE WHEN event_type = 'PAGEVIEW' THEN 1 END) AS pageviews,
    COUNT(CASE WHEN event_type = 'CLICK' THEN 1 END) AS clicks,
    COUNT(CASE WHEN event_type = 'PURCHASE' THEN 1 END) AS purchases,
    ROUND(AVG(session_duration_sec), 1) AS avg_session_duration,
    ROUND(
        COUNT(CASE WHEN event_type = 'PURCHASE' THEN 1 END) * 100.0
        / NULLIF(COUNT(CASE WHEN event_type = 'PAGEVIEW' THEN 1 END), 0),
        2
    ) AS conversion_rate,
    MIN(_date) AS first_event_date,
    MAX(_date) AS last_event_date
FROM {{ ref('silver.events') }}
GROUP BY page_url
ORDER BY total_events DESC

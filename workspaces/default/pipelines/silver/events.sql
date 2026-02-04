-- 🐀 Silver Events Pipeline
-- Cleans and validates raw events from bronze layer
--
-- @name: silver_events
-- @materialized: incremental
-- @unique_key: event_id
-- @partition_by: event_date
-- @owner: data-team

SELECT
    event_id,
    user_id,
    UPPER(event_type) AS event_type,
    page_url,
    timestamp AS event_timestamp,
    CAST(timestamp AS DATE) AS event_date,
    device,
    country,
    session_duration_sec,
    _ingested_at,
    NOW() AS _processed_at
FROM {{ ref('bronze.raw_events') }}
WHERE event_id IS NOT NULL
  AND user_id IS NOT NULL
  AND timestamp <= NOW()  -- No future events
{% if is_incremental() %}
  AND _ingested_at > '{{ watermark("_ingested_at") }}'
{% endif %}

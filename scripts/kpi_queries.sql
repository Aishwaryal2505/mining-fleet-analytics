-- Mining Logistics & Fleet Analytics Pipeline
-- KPI queries for the "Data Analyst - Warehousing & Logistics" dashboard.
-- Run against the fleet_analytics database (data already loaded via load_to_rds.py).
--
-- Tested and verified against the actual generated dataset:
--   - Fleet utilization: ~32% for pit-haul trucks, ~13% for line-haul trucks
--   - On-time delivery: ~85.1% overall
--   - Downtime cost: ~$486K total over 3 months, mechanical failure is the top cost driver

-- ============================================================
-- KPI 1a: Daily fleet utilization % per truck
-- Utilization = hours spent on trips / (24 - downtime hours)
-- ============================================================
WITH trip_hours AS (
    SELECT
        truck_id,
        trip_date,
        SUM(EXTRACT(EPOCH FROM (actual_end_ts - actual_start_ts)) / 3600.0) AS hours_on_trips
    FROM trips
    WHERE status IN ('completed', 'delayed')
      AND actual_start_ts IS NOT NULL
      AND actual_end_ts IS NOT NULL
    GROUP BY truck_id, trip_date
),
daily_downtime AS (
    SELECT truck_id, event_date AS trip_date, SUM(downtime_hours) AS downtime_hours
    FROM downtime_events
    GROUP BY truck_id, event_date
)
SELECT
    t.truck_code,
    th.trip_date,
    ROUND(th.hours_on_trips::numeric, 2) AS hours_on_trips,
    COALESCE(ROUND(dd.downtime_hours::numeric, 2), 0) AS downtime_hours,
    ROUND(
        100.0 * th.hours_on_trips / NULLIF(24 - COALESCE(dd.downtime_hours, 0), 0),
        1
    ) AS utilization_pct
FROM trip_hours th
JOIN trucks t ON t.truck_id = th.truck_id
LEFT JOIN daily_downtime dd ON dd.truck_id = th.truck_id AND dd.trip_date = th.trip_date
ORDER BY th.trip_date, t.truck_code;

-- ============================================================
-- KPI 1b: Overall (3-month) fleet utilization % per truck
-- This is the headline number for the dashboard's fleet summary card.
-- ============================================================
WITH trip_hours AS (
    SELECT truck_id, trip_date,
        SUM(EXTRACT(EPOCH FROM (actual_end_ts - actual_start_ts)) / 3600.0) AS hours_on_trips
    FROM trips
    WHERE status IN ('completed', 'delayed') AND actual_start_ts IS NOT NULL AND actual_end_ts IS NOT NULL
    GROUP BY truck_id, trip_date
),
daily_downtime AS (
    SELECT truck_id, event_date AS trip_date, SUM(downtime_hours) AS downtime_hours
    FROM downtime_events GROUP BY truck_id, event_date
),
active_days AS (
    SELECT DISTINCT truck_id, trip_date FROM trips
),
daily AS (
    SELECT
        ad.truck_id, ad.trip_date,
        COALESCE(th.hours_on_trips, 0) AS hours_on_trips,
        COALESCE(dd.downtime_hours, 0) AS downtime_hours
    FROM active_days ad
    LEFT JOIN trip_hours th ON th.truck_id = ad.truck_id AND th.trip_date = ad.trip_date
    LEFT JOIN daily_downtime dd ON dd.truck_id = ad.truck_id AND dd.trip_date = ad.trip_date
)
SELECT
    t.truck_code,
    t.model,
    COUNT(*) AS active_days,
    ROUND(SUM(d.hours_on_trips)::numeric, 1) AS total_trip_hours,
    ROUND(SUM(d.downtime_hours)::numeric, 1) AS total_downtime_hours,
    ROUND(100.0 * SUM(d.hours_on_trips) / NULLIF(SUM(24 - d.downtime_hours), 0), 1) AS avg_utilization_pct
FROM daily d
JOIN trucks t ON t.truck_id = d.truck_id
GROUP BY t.truck_code, t.model
ORDER BY avg_utilization_pct DESC;

-- ============================================================
-- KPI 2a: On-time delivery rate by route
-- ============================================================
SELECT
    r.route_name,
    COUNT(*) AS total_deliveries,
    SUM(CASE WHEN d.on_time THEN 1 ELSE 0 END) AS on_time_deliveries,
    ROUND(100.0 * SUM(CASE WHEN d.on_time THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_pct,
    ROUND(AVG(EXTRACT(EPOCH FROM (d.actual_delivery_ts - d.scheduled_delivery_ts)) / 60.0)::numeric, 1) AS avg_delay_minutes
FROM deliveries d
JOIN trips t ON t.trip_id = d.trip_id
JOIN routes r ON r.route_id = t.route_id
GROUP BY r.route_name
ORDER BY on_time_pct DESC;

-- ============================================================
-- KPI 2b: Overall on-time delivery rate (headline dashboard number)
-- ============================================================
SELECT
    COUNT(*) AS total_deliveries,
    ROUND(100.0 * SUM(CASE WHEN on_time THEN 1 ELSE 0 END) / COUNT(*), 1) AS overall_on_time_pct
FROM deliveries;

-- ============================================================
-- KPI 2c: On-time delivery rate by driver (top/bottom performers)
-- ============================================================
SELECT
    dr.driver_name,
    dr.shift,
    COUNT(*) AS total_deliveries,
    ROUND(100.0 * SUM(CASE WHEN d.on_time THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_pct
FROM deliveries d
JOIN trips t ON t.trip_id = d.trip_id
JOIN drivers dr ON dr.driver_id = t.driver_id
GROUP BY dr.driver_name, dr.shift
ORDER BY on_time_pct DESC;

-- ============================================================
-- KPI 3a: Downtime cost by reason
-- ============================================================
SELECT
    reason,
    COUNT(*) AS event_count,
    ROUND(SUM(downtime_hours)::numeric, 1) AS total_downtime_hours,
    ROUND(SUM(estimated_cost_aud)::numeric, 2) AS total_cost_aud,
    ROUND(AVG(estimated_cost_aud)::numeric, 2) AS avg_cost_per_event_aud
FROM downtime_events
GROUP BY reason
ORDER BY total_cost_aud DESC;

-- ============================================================
-- KPI 3b: Downtime cost by truck (identifies costliest assets)
-- ============================================================
SELECT
    t.truck_code,
    t.model,
    COUNT(*) AS event_count,
    ROUND(SUM(de.downtime_hours)::numeric, 1) AS total_downtime_hours,
    ROUND(SUM(de.estimated_cost_aud)::numeric, 2) AS total_cost_aud
FROM downtime_events de
JOIN trucks t ON t.truck_id = de.truck_id
GROUP BY t.truck_code, t.model
ORDER BY total_cost_aud DESC;

-- ============================================================
-- KPI 3c: Monthly downtime cost trend
-- ============================================================
SELECT
    DATE_TRUNC('month', event_date)::date AS month,
    ROUND(SUM(estimated_cost_aud)::numeric, 2) AS total_cost_aud
FROM downtime_events
GROUP BY 1
ORDER BY 1;

-- ============================================================
-- BONUS: Fuel cost & efficiency per truck (litres/km, cost/km)
-- Useful supporting metric for a logistics-focused dashboard.
-- ============================================================
SELECT
    t.truck_code,
    t.model,
    ROUND(SUM(f.litres_consumed)::numeric, 1) AS total_litres,
    ROUND(SUM(f.km_travelled)::numeric, 1) AS total_km,
    ROUND(SUM(f.cost_aud)::numeric, 2) AS total_fuel_cost_aud,
    ROUND((SUM(f.litres_consumed) / NULLIF(SUM(f.km_travelled), 0))::numeric, 2) AS litres_per_km,
    ROUND((SUM(f.cost_aud) / NULLIF(SUM(f.km_travelled), 0))::numeric, 2) AS cost_per_km_aud
FROM fuel_logs f
JOIN trucks t ON t.truck_id = f.truck_id
GROUP BY t.truck_code, t.model
ORDER BY cost_per_km_aud DESC;

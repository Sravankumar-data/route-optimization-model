-- ============================================================================
-- STEP 6: SQL CORRIDOR & CONGESTION BOTTLENECK ANALYSIS
-- ============================================================================

-- Create a master joined view for fast downstream analytics & ML
CREATE OR REPLACE VIEW vw_master_shipments AS
SELECT
    t.trip_id,
    t.start_lat,
    t.start_lon,
    t.end_lat,
    t.end_lon,
    t.distance_km,
    t.trip_timestamp,
    t.trip_hour,
    t.trip_dow,
    t.travel_time_min,
    t.actual_speed_kmph,
    r.road_id,
    r.road_type,
    r.num_lanes,
    r.num_signals,
    r.zone_type,
    COALESCE(tr.traffic_level, 'unknown') AS traffic_level,
    tr.avg_speed_kmph AS corridor_traffic_speed,
    COALESCE(w.weather_type, 'clear') AS weather_type,
    COALESCE(w.temperature_c, 25.0) AS temperature_c,
    COALESCE(w.visibility_km, 10.0) AS visibility_km
FROM clean_trips t
INNER JOIN clean_roads r ON t.road_id = r.road_id
LEFT JOIN clean_traffic tr ON t.traffic_id = tr.traffic_id
LEFT JOIN clean_weather w ON t.weather_id = w.weather_id;

-- QUERY 1: Top 10 Most Inefficient & High-Congestion Road Corridors
WITH road_benchmarks AS (
    SELECT
        road_type,
        PERCENTILE_CONT(0.85) WITHIN GROUP (ORDER BY actual_speed_kmph) AS benchmark_speed_kmph
    FROM vw_master_shipments
    GROUP BY road_type
),
road_performance AS (
    SELECT
        m.road_id,
        m.road_type,
        m.zone_type,
        m.num_lanes,
        m.num_signals,
        COUNT(*) AS total_trips,
        ROUND(AVG(m.distance_km), 2) AS avg_dist_km,
        ROUND(AVG(m.travel_time_min), 2) AS avg_time_min,
        ROUND(AVG(m.actual_speed_kmph), 2) AS avg_speed_kmph,
        ROUND(MAX(b.benchmark_speed_kmph), 2) AS benchmark_speed_kmph
    FROM vw_master_shipments m
    JOIN road_benchmarks b ON m.road_type = b.road_type
    GROUP BY 1, 2, 3, 4, 5
    HAVING COUNT(*) >= 100
)
SELECT
    road_id,
    road_type,
    zone_type,
    num_lanes,
    num_signals,
    total_trips,
    avg_dist_km,
    avg_time_min,
    avg_speed_kmph,
    benchmark_speed_kmph,
    ROUND(((benchmark_speed_kmph - avg_speed_kmph) / benchmark_speed_kmph) * 100, 1) AS speed_loss_pct
FROM road_performance
ORDER BY speed_loss_pct DESC
LIMIT 10;

-- QUERY 2: Hourly Congestion & Travel Efficiency Breakdown
SELECT
    trip_hour,
    COUNT(*) AS shipment_volume,
    ROUND(AVG(distance_km), 2) AS avg_distance_km,
    ROUND(AVG(travel_time_min), 2) AS avg_travel_min,
    ROUND(AVG(actual_speed_kmph), 2) AS avg_speed_kmph,
    ROUND(AVG(travel_time_min / distance_km), 2) AS min_per_km_cost
FROM vw_master_shipments
GROUP BY trip_hour
ORDER BY min_per_km_cost DESC
LIMIT 10;

-- QUERY 3: Weather & Traffic Level Impact on Delivery Speed
SELECT
    weather_type,
    traffic_level,
    COUNT(*) AS trip_count,
    ROUND(AVG(actual_speed_kmph), 2) AS avg_speed_kmph,
    ROUND(AVG(travel_time_min / distance_km), 2) AS min_per_km
FROM vw_master_shipments
WHERE traffic_level <> 'unknown'
GROUP BY 1, 2
ORDER BY min_per_km DESC
LIMIT 10;

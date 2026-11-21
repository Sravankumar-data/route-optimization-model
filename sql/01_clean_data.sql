-- 1. CLEAN ROADS TABLE (With spelling normalization)
CREATE OR REPLACE TABLE clean_roads AS
WITH ranked_roads AS (
    SELECT
        TRIM(road_id) AS road_id,
        CASE LOWER(TRIM(COALESCE(road_type, 'unknown')))
            WHEN 'hghway' THEN 'highway'
            WHEN 'urbn' THEN 'urban'
            WHEN 'resdential' THEN 'residential'
            ELSE LOWER(TRIM(COALESCE(road_type, 'unknown')))
        END AS road_type,
        COALESCE(CAST(num_lanes AS INTEGER), 2) AS num_lanes,
        COALESCE(CAST(num_signals AS INTEGER), 0) AS num_signals,
        CASE LOWER(TRIM(COALESCE(zone_type, 'unknown')))
            WHEN 'commerical' THEN 'commercial'
            WHEN 'industral' THEN 'industrial'
            WHEN 'resdential' THEN 'residential'
            ELSE LOWER(TRIM(COALESCE(zone_type, 'unknown')))
        END AS zone_type,
        ROW_NUMBER() OVER (PARTITION BY TRIM(road_id) ORDER BY road_id) AS rn
    FROM 'data/roads.csv'
    WHERE road_id IS NOT NULL AND TRIM(road_id) <> ''
)
SELECT road_id, road_type, num_lanes, num_signals, zone_type
FROM ranked_roads
WHERE rn = 1;

-- 2. CLEAN TRAFFIC TABLE (With spelling normalization)
CREATE OR REPLACE TABLE clean_traffic AS
WITH ranked_traffic AS (
    SELECT
        CAST(traffic_id AS INTEGER) AS traffic_id,
        CAST(hour AS INTEGER) AS hour,
        CASE LOWER(TRIM(CAST(day_of_week AS VARCHAR)))
            WHEN '0' THEN 'Mon' WHEN 'mon' THEN 'Mon' WHEN 'monday' THEN 'Mon'
            WHEN '1' THEN 'Tue' WHEN 'tue' THEN 'Tue' WHEN 'tuesday' THEN 'Tue'
            WHEN '2' THEN 'Wed' WHEN 'wed' THEN 'Wed' WHEN 'wednesday' THEN 'Wed'
            WHEN '3' THEN 'Thu' WHEN 'thu' THEN 'Thu' WHEN 'thursday' THEN 'Thu'
            WHEN '4' THEN 'Fri' WHEN 'fri' THEN 'Fri' WHEN 'friday' THEN 'Fri'
            WHEN '5' THEN 'Sat' WHEN 'sat' THEN 'Sat' WHEN 'saturday' THEN 'Sat'
            WHEN '6' THEN 'Sun' WHEN 'sun' THEN 'Sun' WHEN 'sunday' THEN 'Sun'
            ELSE 'Unknown'
        END AS day_of_week,
        CASE LOWER(TRIM(COALESCE(zone_type, 'unknown')))
            WHEN 'commerical' THEN 'commercial'
            WHEN 'industral' THEN 'industrial'
            ELSE LOWER(TRIM(COALESCE(zone_type, 'unknown')))
        END AS zone_type,
        CASE LOWER(TRIM(COALESCE(traffic_level, 'unknown')))
            WHEN 'meduim' THEN 'medium'
            WHEN 'med' THEN 'medium'
            WHEN 'hi' THEN 'high'
            WHEN 'lo' THEN 'low'
            ELSE LOWER(TRIM(COALESCE(traffic_level, 'unknown')))
        END AS traffic_level,
        CAST(avg_speed_kmph AS DOUBLE) AS avg_speed_kmph,
        ROW_NUMBER() OVER (PARTITION BY traffic_id ORDER BY traffic_id) AS rn
    FROM 'data/traffic.csv'
    WHERE traffic_id IS NOT NULL
      AND avg_speed_kmph > 0
      AND hour BETWEEN 0 AND 23
)
SELECT traffic_id, hour, day_of_week, zone_type, traffic_level, avg_speed_kmph
FROM ranked_traffic
WHERE rn = 1;

-- 3. CLEAN WEATHER TABLE (With spelling normalization)
CREATE OR REPLACE TABLE clean_weather AS
WITH ranked_weather AS (
    SELECT
        TRIM(weather_id) AS weather_id,
        CASE LOWER(TRIM(COALESCE(weather_type, 'clear')))
            WHEN 'foggy' THEN 'fog'
            WHEN 'rainy' THEN 'rain'
            WHEN 'raining' THEN 'rain'
            WHEN 'cldy' THEN 'cloudy'
            WHEN 'clr' THEN 'clear'
            ELSE LOWER(TRIM(COALESCE(weather_type, 'clear')))
        END AS weather_type,
        COALESCE(CAST(temperature_c AS DOUBLE), 25.0) AS temperature_c,
        COALESCE(CAST(visibility_km AS DOUBLE), 10.0) AS visibility_km,
        ROW_NUMBER() OVER (PARTITION BY TRIM(weather_id) ORDER BY weather_id) AS rn
    FROM 'data/weather.csv'
    WHERE weather_id IS NOT NULL AND TRIM(weather_id) <> ''
)
SELECT weather_id, weather_type, temperature_c, visibility_km
FROM ranked_weather
WHERE rn = 1;

-- 4. CLEAN TRIPS TABLE
CREATE OR REPLACE TABLE clean_trips AS
WITH parsed_trips AS (
    SELECT
        TRIM(trip_id) AS trip_id,
        CAST(start_lat AS DOUBLE) AS start_lat,
        CAST(start_lon AS DOUBLE) AS start_lon,
        CAST(end_lat AS DOUBLE) AS end_lat,
        CAST(end_lon AS DOUBLE) AS end_lon,
        CAST(distance_km AS DOUBLE) AS distance_km,
        COALESCE(
            TRY_STRPTIME(TRIM(timestamp), '%m-%d-%Y %H:%M'),
            TRY_STRPTIME(TRIM(timestamp), '%d-%b-%Y %H:%M'),
            TRY_STRPTIME(TRIM(timestamp), '%Y-%m-%d %H:%M:%S'),
            TRY_STRPTIME(TRIM(timestamp), '%Y/%m/%d %H:%M:%S'),
            TRY_STRPTIME(TRIM(timestamp), '%Y/%m/%d')
        ) AS trip_timestamp,
        TRIM(road_id) AS road_id,
        TRY_CAST(traffic_id AS INTEGER) AS traffic_id,
        TRIM(weather_id) AS weather_id,
        CAST(travel_time_min AS DOUBLE) AS travel_time_min,
        ROW_NUMBER() OVER (PARTITION BY TRIM(trip_id) ORDER BY trip_id) AS rn
    FROM 'data/trips.csv'
    WHERE trip_id IS NOT NULL
      AND distance_km > 0.1
      AND travel_time_min > 0.5
      AND (distance_km / (travel_time_min / 60.0)) BETWEEN 3.0 AND 140.0
)
SELECT
    trip_id, start_lat, start_lon, end_lat, end_lon,
    ROUND(distance_km, 3) AS distance_km,
    trip_timestamp,
    EXTRACT(HOUR FROM trip_timestamp) AS trip_hour,
    EXTRACT(DOW FROM trip_timestamp) AS trip_dow,
    road_id, traffic_id, weather_id,
    ROUND(travel_time_min, 2) AS travel_time_min,
    ROUND(distance_km / (travel_time_min / 60.0), 2) AS actual_speed_kmph
FROM parsed_trips
WHERE rn = 1 AND trip_timestamp IS NOT NULL;

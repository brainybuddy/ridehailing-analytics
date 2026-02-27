-- =============================================================================
-- Ride-Hailing Analytics — Database Schema
-- =============================================================================
-- Covers: schema design, indexes, and the base join view used by
-- the feature engineering pipeline.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Core tables
-- -----------------------------------------------------------------------------

CREATE TABLE users (
    user_id      VARCHAR(10)  PRIMARY KEY,
    age          SMALLINT     CHECK (age BETWEEN 18 AND 100),
    gender       VARCHAR(5),
    signup_date  DATE         NOT NULL,
    home_zone    VARCHAR(40),
    home_lat     DECIMAL(9,6),
    home_lon     DECIMAL(9,6)
);

CREATE TABLE trips (
    trip_id           VARCHAR(10)   PRIMARY KEY,
    user_id           VARCHAR(10)   NOT NULL  REFERENCES users(user_id),
    pickup_zone       VARCHAR(40),
    dropoff_zone      VARCHAR(40),
    pickup_lat        DECIMAL(9,6),
    pickup_lon        DECIMAL(9,6),
    dropoff_lat       DECIMAL(9,6),
    dropoff_lon       DECIMAL(9,6),
    pickup_datetime   TIMESTAMP     NOT NULL,
    dropoff_datetime  TIMESTAMP     NOT NULL,
    duration_mins     DECIMAL(6,1)  CHECK (duration_mins > 0),
    distance_km       DECIMAL(6,2)  CHECK (distance_km >= 0),
    fare_usd          DECIMAL(7,2)  CHECK (fare_usd >= 0),
    is_weekend        BOOLEAN       NOT NULL
);

-- -----------------------------------------------------------------------------
-- Indexes for join and analytics access patterns
-- -----------------------------------------------------------------------------

CREATE INDEX idx_trips_user_id    ON trips(user_id);
CREATE INDEX idx_trips_pickup_dt  ON trips(pickup_datetime);
CREATE INDEX idx_trips_zones      ON trips(pickup_zone, dropoff_zone);
CREATE INDEX idx_trips_is_weekend ON trips(is_weekend);

-- -----------------------------------------------------------------------------
-- trip_detail view — base join used by feature engineering
-- -----------------------------------------------------------------------------
-- Mirrors the pandas join in feature_engineering.py:
--   trips.merge(users[...], on='user_id', how='left')
-- -----------------------------------------------------------------------------

CREATE VIEW trip_detail AS
SELECT
    u.user_id,
    u.age,
    u.gender,
    u.home_zone,

    t.trip_id,
    t.pickup_zone,
    t.dropoff_zone,
    t.pickup_lat,
    t.pickup_lon,
    t.dropoff_lat,
    t.dropoff_lon,
    t.pickup_datetime,
    t.dropoff_datetime,
    t.duration_mins,
    t.distance_km,
    t.fare_usd,
    t.is_weekend,

    -- Derived temporal columns (pre-computed for fast aggregation)
    EXTRACT(HOUR  FROM t.pickup_datetime) AS pickup_hour,
    EXTRACT(DOW   FROM t.pickup_datetime) AS day_of_week,   -- 0=Sun … 6=Sat
    EXTRACT(MONTH FROM t.pickup_datetime) AS month,

    CASE
        WHEN EXTRACT(HOUR FROM t.pickup_datetime) BETWEEN 7  AND 9  THEN 'am_rush'
        WHEN EXTRACT(HOUR FROM t.pickup_datetime) BETWEEN 16 AND 19 THEN 'pm_rush'
        WHEN EXTRACT(HOUR FROM t.pickup_datetime) >= 23
          OR EXTRACT(HOUR FROM t.pickup_datetime) <= 3                THEN 'late_night'
        WHEN EXTRACT(HOUR FROM t.pickup_datetime) BETWEEN 10 AND 15 THEN 'midday'
        WHEN EXTRACT(HOUR FROM t.pickup_datetime) BETWEEN 20 AND 22 THEN 'evening'
        ELSE 'early_morning'
    END AS time_bucket,

    (t.pickup_zone IN ('jfk_airport','laguardia')
     OR t.dropoff_zone IN ('jfk_airport','laguardia')) AS involves_airport

FROM users u
JOIN trips t ON u.user_id = t.user_id;

-- -----------------------------------------------------------------------------
-- Example: per-user feature aggregation in SQL
-- (feature_engineering.py replicates this logic in pandas)
-- -----------------------------------------------------------------------------

/*
SELECT
    user_id,
    COUNT(*)                                            AS total_trips,
    AVG(distance_km)                                    AS avg_distance_km,
    AVG(duration_mins)                                  AS avg_duration_mins,
    AVG(fare_usd)                                       AS avg_fare_usd,
    AVG(pickup_hour)                                    AS avg_hour,
    STDDEV(pickup_hour)                                 AS std_hour,
    AVG(CASE WHEN time_bucket = 'am_rush'    THEN 1.0 ELSE 0.0 END) AS pct_am_rush,
    AVG(CASE WHEN time_bucket = 'pm_rush'    THEN 1.0 ELSE 0.0 END) AS pct_pm_rush,
    AVG(CASE WHEN time_bucket = 'late_night' THEN 1.0 ELSE 0.0 END) AS pct_late_night,
    AVG(CASE WHEN is_weekend                 THEN 1.0 ELSE 0.0 END) AS pct_weekend,
    AVG(CASE WHEN involves_airport           THEN 1.0 ELSE 0.0 END) AS pct_airport
FROM trip_detail
GROUP BY user_id;
*/

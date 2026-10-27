-- Mining Logistics & Fleet Analytics Pipeline
-- Schema for PostgreSQL (AWS RDS)
-- Run this once against the `fleet_analytics` database before loading data.

DROP TABLE IF EXISTS deliveries CASCADE;
DROP TABLE IF EXISTS downtime_events CASCADE;
DROP TABLE IF EXISTS fuel_logs CASCADE;
DROP TABLE IF EXISTS trips CASCADE;
DROP TABLE IF EXISTS drivers CASCADE;
DROP TABLE IF EXISTS trucks CASCADE;
DROP TABLE IF EXISTS routes CASCADE;
DROP TABLE IF EXISTS sites CASCADE;

-- ---------------------------------------------------------------------
-- Reference tables
-- ---------------------------------------------------------------------

CREATE TABLE sites (
    site_id     INTEGER PRIMARY KEY,
    site_code   VARCHAR(10) NOT NULL UNIQUE,
    site_name   VARCHAR(100) NOT NULL,
    site_type   VARCHAR(30) NOT NULL,
    latitude    DOUBLE PRECISION,
    longitude   DOUBLE PRECISION
);

CREATE TABLE routes (
    route_id                INTEGER PRIMARY KEY,
    route_name               VARCHAR(100) NOT NULL,
    origin_site_id            INTEGER NOT NULL REFERENCES sites(site_id),
    destination_site_id       INTEGER NOT NULL REFERENCES sites(site_id),
    distance_km                NUMERIC(8,2) NOT NULL,
    typical_duration_min       INTEGER NOT NULL
);

CREATE TABLE trucks (
    truck_id            INTEGER PRIMARY KEY,
    truck_code           VARCHAR(10) NOT NULL UNIQUE,
    model                 VARCHAR(50) NOT NULL,
    capacity_tonnes        INTEGER NOT NULL,
    year_commissioned      INTEGER NOT NULL,
    status                 VARCHAR(20) NOT NULL
);

CREATE TABLE drivers (
    driver_id    INTEGER PRIMARY KEY,
    driver_code   VARCHAR(10) NOT NULL UNIQUE,
    driver_name    VARCHAR(100) NOT NULL,
    shift           VARCHAR(10) NOT NULL
);

-- ---------------------------------------------------------------------
-- Fact tables
-- ---------------------------------------------------------------------

CREATE TABLE trips (
    trip_id              INTEGER PRIMARY KEY,
    truck_id              INTEGER NOT NULL REFERENCES trucks(truck_id),
    route_id               INTEGER NOT NULL REFERENCES routes(route_id),
    driver_id               INTEGER NOT NULL REFERENCES drivers(driver_id),
    trip_date                 DATE NOT NULL,
    scheduled_start_ts         TIMESTAMP NOT NULL,
    actual_start_ts             TIMESTAMP,
    scheduled_end_ts             TIMESTAMP NOT NULL,
    actual_end_ts                 TIMESTAMP,
    load_tonnes                     NUMERIC(8,2) NOT NULL,
    status                            VARCHAR(20) NOT NULL
);

CREATE TABLE deliveries (
    delivery_id            INTEGER PRIMARY KEY,
    trip_id                  INTEGER NOT NULL REFERENCES trips(trip_id),
    scheduled_delivery_ts      TIMESTAMP NOT NULL,
    actual_delivery_ts           TIMESTAMP NOT NULL,
    tonnes_delivered                NUMERIC(8,2) NOT NULL,
    on_time                           BOOLEAN NOT NULL
);

CREATE TABLE downtime_events (
    event_id               INTEGER PRIMARY KEY,
    truck_id                 INTEGER NOT NULL REFERENCES trucks(truck_id),
    event_date                 DATE NOT NULL,
    start_ts                     TIMESTAMP NOT NULL,
    end_ts                         TIMESTAMP NOT NULL,
    downtime_hours                   NUMERIC(6,2) NOT NULL,
    reason                             VARCHAR(40) NOT NULL,
    estimated_cost_aud                  NUMERIC(10,2) NOT NULL
);

CREATE TABLE fuel_logs (
    log_id             INTEGER PRIMARY KEY,
    truck_id             INTEGER NOT NULL REFERENCES trucks(truck_id),
    log_date               DATE NOT NULL,
    litres_consumed          NUMERIC(10,2) NOT NULL,
    km_travelled                NUMERIC(8,2) NOT NULL,
    cost_aud                      NUMERIC(10,2) NOT NULL
);

-- ---------------------------------------------------------------------
-- Helpful indexes for the KPI queries we'll write next
-- ---------------------------------------------------------------------

CREATE INDEX idx_trips_truck_date ON trips(truck_id, trip_date);
CREATE INDEX idx_trips_status ON trips(status);
CREATE INDEX idx_deliveries_on_time ON deliveries(on_time);
CREATE INDEX idx_downtime_truck_date ON downtime_events(truck_id, event_date);
CREATE INDEX idx_fuel_truck_date ON fuel_logs(truck_id, log_date);

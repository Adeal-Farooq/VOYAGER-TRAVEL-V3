-- PostgreSQL + PostGIS schema for VOYAGER
-- Run: psql -U postgres -d voyager -f schema.sql

CREATE DATABASE voyager;
\c voyager;

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Bus stops (5077 BMTC stops)
CREATE TABLE bus_stops (
    stop_id    SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    geom       GEOGRAPHY(Point, 4326) NOT NULL,
    routes     TEXT[],  -- route numbers serving this stop
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_bus_stops_geom ON bus_stops USING GIST (geom);
CREATE INDEX idx_bus_stops_name ON bus_stops (name);

-- Metro stations (Namma Metro)
CREATE TABLE metro_stations (
    station_code     TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    line             TEXT NOT NULL,
    sequence         INT NOT NULL,
    next_station_code TEXT,
    distance_to_next_km FLOAT DEFAULT 0,
    is_interchange   INT DEFAULT 0,
    geom             GEOGRAPHY(Point, 4326) NOT NULL
);
CREATE INDEX idx_metro_stations_geom ON metro_stations USING GIST (geom);
CREATE INDEX idx_metro_stations_name ON metro_stations (name);
CREATE INDEX idx_metro_stations_line ON metro_stations (line);

-- Railway stations (Karnataka)
CREATE TABLE railway_stations (
    station_code TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    geom         GEOGRAPHY(Point, 4326) NOT NULL,
    zone         TEXT
);
CREATE INDEX idx_railway_stations_geom ON railway_stations USING GIST (geom);
CREATE INDEX idx_railway_stations_name ON railway_stations (name);

-- KIA bus routes
CREATE TABLE kia_routes (
    route_id    TEXT PRIMARY KEY,
    route_info  JSONB,
    stops       JSONB
);

-- Transit fare slabs (BMTC, Metro)
CREATE TABLE transit_fares (
    mode       TEXT NOT NULL,  -- 'bmtc_ordinary', 'bmtc_ac', 'metro'
    max_km     FLOAT NOT NULL,
    adult_fare FLOAT NOT NULL,
    child_fare FLOAT,
    senior_fare FLOAT
);
CREATE INDEX idx_transit_fares_mode ON transit_fares (mode);

-- Query examples (PostGIS spatial index makes these O(log n)):
--
-- Nearby bus stops (radius in meters):
--   SELECT name, ST_Distance(geom, ST_MakePoint(77.6, 12.97)::geography) AS dist
--   FROM bus_stops
--   WHERE ST_DWithin(geom, ST_MakePoint(77.6, 12.97)::geography, 2000)
--   ORDER BY dist LIMIT 20;
--
-- Nearest metro station:
--   SELECT name, line, ST_Distance(geom, ST_MakePoint(77.6, 12.97)::geography) AS dist
--   FROM metro_stations
--   ORDER BY geom <-> ST_MakePoint(77.6, 12.97)::geography
--   LIMIT 5;

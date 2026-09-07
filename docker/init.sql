CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS accident_zones (
    zone_id          TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    lat              DOUBLE PRECISION NOT NULL,
    lon              DOUBLE PRECISION NOT NULL,
    radius_m         DOUBLE PRECISION NOT NULL,
    historical_risk  DOUBLE PRECISION NOT NULL,
    geog             geography(Point, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS accident_zones_geog ON accident_zones USING GIST (geog);

CREATE TABLE IF NOT EXISTS telemetry (
    time            TIMESTAMPTZ NOT NULL,
    vehicle_id      TEXT NOT NULL,
    speed_kmh       DOUBLE PRECISION NOT NULL,
    accel_ms2       DOUBLE PRECISION NOT NULL,
    brake           DOUBLE PRECISION NOT NULL,
    steering_var    DOUBLE PRECISION NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    heading_deg     DOUBLE PRECISION NOT NULL,
    behavior        TEXT NOT NULL,
    alert           TEXT NOT NULL DEFAULT 'none',
    source          TEXT NOT NULL DEFAULT 'cas',
    alert_score     DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS telemetry_vehicle_time ON telemetry (vehicle_id, time DESC);

CREATE TABLE IF NOT EXISTS incidents (
    id                  BIGSERIAL PRIMARY KEY,
    incident_id         UUID NOT NULL UNIQUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    vehicle_id          TEXT NOT NULL,
    severity            TEXT NOT NULL,
    fused_score         DOUBLE PRECISION NOT NULL,
    behavior            TEXT NOT NULL,
    summary             TEXT NOT NULL,
    contributing        JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommended_action  TEXT NOT NULL,
    citations           JSONB NOT NULL DEFAULT '[]'::jsonb,
    lat                 DOUBLE PRECISION NOT NULL,
    lon                 DOUBLE PRECISION NOT NULL,
    alert               TEXT NOT NULL DEFAULT 'none',
    source              TEXT NOT NULL DEFAULT 'cas',
    alert_score         DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS guideline_chunks (
    section_id  TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    embedding   JSONB NOT NULL DEFAULT '[]'::jsonb
);

"""Optional Postgres helpers. Tests and the static site run without a live DB."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from driveguard.models import Zone
from driveguard.settings import get_settings

ZONE_DWITHIN_SQL = """
SELECT zone_id, historical_risk
FROM accident_zones
WHERE ST_DWithin(
    geog,
    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
    radius_m
)
ORDER BY historical_risk DESC
LIMIT 1
"""


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    settings = get_settings()
    with psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=2) as conn:
        yield conn


def db_available() -> bool:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def postgis_ready() -> bool:
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis')"
            ).fetchone()
        return bool(row and row.get("exists"))
    except Exception:
        return False


def seed_zones(zones: list[Zone]) -> int:
    if not zones:
        return 0
    with connect() as conn:
        for zone in zones:
            conn.execute(
                """
                INSERT INTO accident_zones (
                    zone_id, name, lat, lon, radius_m, historical_risk, geog
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                )
                ON CONFLICT (zone_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    lat = EXCLUDED.lat,
                    lon = EXCLUDED.lon,
                    radius_m = EXCLUDED.radius_m,
                    historical_risk = EXCLUDED.historical_risk,
                    geog = EXCLUDED.geog
                """,
                (
                    zone.zone_id,
                    zone.name,
                    zone.lat,
                    zone.lon,
                    zone.radius_m,
                    zone.historical_risk,
                    zone.lon,
                    zone.lat,
                ),
            )
        conn.commit()
    return len(zones)


def zone_hit_sql(lat: float, lon: float) -> tuple[float, str | None]:
    with connect() as conn:
        row = conn.execute(ZONE_DWITHIN_SQL, (lon, lat)).fetchone()
    if not row:
        return 0.0, None
    return float(row["historical_risk"]), str(row["zone_id"])


def ensure_telemetry_alert_columns(conn: psycopg.Connection) -> None:
    conn.execute(
        "ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS alert TEXT NOT NULL DEFAULT 'none'"
    )
    conn.execute(
        "ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'cas'"
    )
    conn.execute(
        """
        ALTER TABLE telemetry
        ADD COLUMN IF NOT EXISTS alert_score DOUBLE PRECISION NOT NULL DEFAULT 0
        """
    )


def insert_telemetry(conn: psycopg.Connection, sample: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO telemetry (
            time, vehicle_id, speed_kmh, accel_ms2, brake, steering_var,
            lat, lon, heading_deg, behavior, alert, source, alert_score
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            sample["time"],
            sample["vehicle_id"],
            sample["speed_kmh"],
            sample["accel_ms2"],
            sample["brake"],
            sample["steering_var"],
            sample["lat"],
            sample["lon"],
            sample["heading_deg"],
            sample["behavior"],
            sample.get("alert") or "none",
            sample.get("source") or "cas",
            float(sample.get("alert_score") or 0.0),
        ),
    )


def insert_incident(conn: psycopg.Connection, incident: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO incidents (
            incident_id, vehicle_id, severity, fused_score, behavior, summary,
            contributing, recommended_action, citations, lat, lon
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s)
        ON CONFLICT (incident_id) DO NOTHING
        """,
        (
            str(incident["incident_id"]),
            incident["vehicle_id"],
            incident["severity"],
            incident["fused_score"],
            incident["behavior"],
            incident["summary"],
            json.dumps(incident.get("contributing") or []),
            incident["recommended_action"],
            json.dumps(incident.get("citations") or []),
            incident["lat"],
            incident["lon"],
        ),
    )


def persist_ingest(sample: dict[str, Any], incident: dict[str, Any] | None) -> None:
    with connect() as conn:
        ensure_telemetry_alert_columns(conn)
        insert_telemetry(conn, sample)
        if incident is not None:
            insert_incident(conn, incident)
        conn.commit()


def fetch_recent_telemetry(per_vehicle: int = 32) -> list[dict[str, Any]]:
    with connect() as conn:
        ensure_telemetry_alert_columns(conn)
        conn.commit()
        rows = conn.execute(
            """
            SELECT time, vehicle_id, speed_kmh, accel_ms2, brake, steering_var,
                   lat, lon, heading_deg, behavior, alert, source, alert_score
            FROM (
                SELECT time, vehicle_id, speed_kmh, accel_ms2, brake, steering_var,
                       lat, lon, heading_deg, behavior, alert, source, alert_score,
                       ROW_NUMBER() OVER (
                           PARTITION BY vehicle_id ORDER BY time DESC
                       ) AS rn
                FROM telemetry
            ) ranked
            WHERE rn <= %s
            ORDER BY vehicle_id, time ASC
            """,
            (per_vehicle,),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_recent_incidents(limit: int = 80) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT incident_id, vehicle_id, severity, fused_score, behavior, summary,
                   contributing, recommended_action, citations, lat, lon, created_at
            FROM incidents
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]

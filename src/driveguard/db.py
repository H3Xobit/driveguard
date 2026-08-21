"""Optional Postgres helpers. Tests and showcase mode run without a live DB."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from driveguard.settings import get_settings


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    settings = get_settings()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn


def db_available() -> bool:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def insert_telemetry(conn: psycopg.Connection, sample: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO telemetry (
            time, vehicle_id, speed_kmh, accel_ms2, brake, steering_var,
            lat, lon, heading_deg, behavior
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        ),
    )


def insert_incident(conn: psycopg.Connection, incident: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO incidents (
            incident_id, vehicle_id, severity, fused_score, behavior, summary,
            contributing, recommended_action, citations, lat, lon
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s)
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

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from driveguard.models import BehaviorTag, Severity
from driveguard.store import (
    has_desk_state,
    hydrate_from_db,
    list_incidents,
    persist_enabled,
    reset_store,
    restored_from_db,
    seed_demo,
    set_persist,
    vehicles_snapshot,
)


@pytest.fixture(autouse=True)
def _clean_store() -> Iterator[None]:
    reset_store()
    set_persist(False)
    yield
    reset_store()
    set_persist(False)


def test_hydrate_skips_when_persist_is_off() -> None:
    set_persist(False)
    assert hydrate_from_db() is False
    assert restored_from_db() is False
    assert has_desk_state() is False


def test_hydrate_loads_vehicles_and_skips_seed(monkeypatch) -> None:
    set_persist(True)
    now = datetime.now(UTC)
    monkeypatch.setattr(
        "driveguard.db.fetch_recent_desk_rows",
        lambda per_vehicle=32, limit=80: (
            [
                {
                    "time": now,
                    "vehicle_id": "V-9001",
                    "speed_kmh": 62.0,
                    "accel_ms2": 0.4,
                    "brake": 0.1,
                    "steering_var": 1.2,
                    "lat": 35.6812,
                    "lon": 139.7671,
                    "heading_deg": 90.0,
                    "behavior": BehaviorTag.calm.value,
                    "alert": "cas_hmw",
                    "source": "cas",
                    "alert_score": 2.4,
                }
            ],
            [
                {
                    "incident_id": uuid4(),
                    "vehicle_id": "V-9001",
                    "severity": Severity.warn.value,
                    "fused_score": 0.71,
                    "behavior": BehaviorTag.harsh_braking.value,
                    "summary": "Headway warning on the C1 corridor.",
                    "contributing": ["cas_hmw"],
                    "recommended_action": "Ease speed through the hotspot.",
                    "citations": [{"section_id": "cas-hmw"}],
                    "lat": 35.6812,
                    "lon": 139.7671,
                    "created_at": now,
                    "alert": "cas_hmw",
                    "source": "cas",
                    "alert_score": 2.4,
                }
            ],
        ),
    )
    assert hydrate_from_db() is True
    assert restored_from_db() is True
    restored = next(row for row in vehicles_snapshot() if row["vehicle_id"] == "V-9001")
    assert restored["alert"] == "cas_hmw"
    assert restored["source"] == "cas"
    assert restored["alert_score"] == 2.4
    incident = list_incidents()[0]
    assert incident.vehicle_id == "V-9001"
    assert incident.alert.value == "cas_hmw"
    assert incident.source.value == "cas"
    assert incident.alert_score == 2.4
    seed_demo()
    ids = {row["vehicle_id"] for row in vehicles_snapshot()}
    assert "V-9001" in ids
    assert "V-1042" not in ids


def test_hydrate_empty_tables_keep_seed_path(monkeypatch) -> None:
    set_persist(True)
    monkeypatch.setattr(
        "driveguard.db.fetch_recent_desk_rows",
        lambda per_vehicle=32, limit=80: ([], []),
    )
    assert hydrate_from_db() is False
    assert restored_from_db() is False
    assert has_desk_state() is False
    seed_demo()
    ids = {row["vehicle_id"] for row in vehicles_snapshot()}
    assert "V-1042" in ids


def test_hydrate_probe_enables_persist_without_prior_flag(monkeypatch) -> None:
    set_persist(False)
    now = datetime.now(UTC)
    monkeypatch.setattr(
        "driveguard.db.fetch_recent_desk_rows",
        lambda per_vehicle=32, limit=80: (
            [
                {
                    "time": now,
                    "vehicle_id": "V-9001",
                    "speed_kmh": 62.0,
                    "accel_ms2": 0.4,
                    "brake": 0.1,
                    "steering_var": 1.2,
                    "lat": 35.6812,
                    "lon": 139.7671,
                    "heading_deg": 90.0,
                    "behavior": BehaviorTag.calm.value,
                    "alert": "cas_hmw",
                    "source": "cas",
                    "alert_score": 2.4,
                }
            ],
            [],
        ),
    )
    assert hydrate_from_db(probe=True) is True
    assert persist_enabled() is True
    assert restored_from_db() is True


def test_hydrate_rows_use_startup_hits(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("hydrate opened a zone lookup")

    monkeypatch.setattr("driveguard.store.zone_risk", boom)
    now = datetime.now(UTC)
    row = {
        "time": now,
        "vehicle_id": "V-9001",
        "speed_kmh": 62.0,
        "accel_ms2": 0.4,
        "brake": 0.1,
        "steering_var": 1.2,
        "lat": 35.6812,
        "lon": 139.7671,
        "heading_deg": 90.0,
        "behavior": BehaviorTag.calm.value,
        "alert": "cas_hmw",
        "source": "cas",
        "alert_score": 2.4,
    }
    from driveguard.store import hydrate_rows

    assert hydrate_rows(
        [row, dict(row)],
        [],
        probe=True,
        zone_hits={(35.6812, 139.7671): (0.8, "TKY-C1-01")},
    )
    restored = next(item for item in vehicles_snapshot() if item["vehicle_id"] == "V-9001")
    assert restored["nearest_zone"] == "TKY-C1-01"
    assert restored["zone"] == 0.8


def test_hydrate_resolves_zones_outside_the_desk_lock(monkeypatch) -> None:
    from driveguard import geo
    from driveguard.simulator.session import iter_session
    from driveguard.store import _LOCK, hydrate_rows

    held: list[bool] = []

    def fake_hit(_lat: float, _lon: float) -> tuple[float, str | None]:
        held.append(_LOCK.locked())
        return 0.4, "TKY-C1-01"

    monkeypatch.setattr("driveguard.db.zone_hit_sql", fake_hit)
    sample = next(iter(iter_session(duration=1, inject=None)))
    from driveguard.risk.temporal import score_window

    score_window([sample], [0.0])
    geo.set_geo_backend(True)
    geo.clear_zone_hits()
    reset_store()
    moved_lat = sample.lat + 20 / geo._M_PER_DEG
    row = {
        "time": sample.time,
        "vehicle_id": sample.vehicle_id,
        "speed_kmh": sample.speed_kmh,
        "accel_ms2": sample.accel_ms2,
        "brake": sample.brake,
        "steering_var": sample.steering_var,
        "lat": sample.lat,
        "lon": sample.lon,
        "heading_deg": sample.heading_deg,
        "behavior": sample.behavior.value,
        "alert": sample.alert.value,
        "source": sample.source.value,
        "alert_score": sample.alert_score,
    }
    moved = dict(row)
    moved["lat"] = moved_lat
    try:
        assert geo.corridor_cell(sample.lat, sample.lon) != geo.corridor_cell(moved_lat, sample.lon)
        assert hydrate_rows([row, moved], [], probe=True) is True
        assert held == [False, False]
        restored = next(
            item for item in vehicles_snapshot() if item["vehicle_id"] == sample.vehicle_id
        )
        assert restored["zone"] == 0.4
        assert restored["nearest_zone"] == "TKY-C1-01"
        assert restored["lat"] == moved_lat
    finally:
        geo.clear_zone_hits()
        geo.set_geo_backend(False)
        reset_store()


def test_hydrate_db_error_disables_persist(monkeypatch) -> None:
    set_persist(True)

    def boom(per_vehicle: int = 32, limit: int = 80):
        raise RuntimeError("db down")

    monkeypatch.setattr("driveguard.db.fetch_recent_desk_rows", boom)
    assert hydrate_from_db() is False
    assert persist_enabled() is False
    assert restored_from_db() is False

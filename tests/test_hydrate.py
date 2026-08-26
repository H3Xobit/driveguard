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
        "driveguard.db.fetch_recent_telemetry",
        lambda per_vehicle=32: [
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
            }
        ],
    )
    monkeypatch.setattr(
        "driveguard.db.fetch_recent_incidents",
        lambda limit=80: [
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
            }
        ],
    )
    assert hydrate_from_db() is True
    assert restored_from_db() is True
    assert any(row["vehicle_id"] == "V-9001" for row in vehicles_snapshot())
    assert list_incidents()[0].vehicle_id == "V-9001"
    seed_demo()
    ids = {row["vehicle_id"] for row in vehicles_snapshot()}
    assert "V-9001" in ids
    assert "V-1042" not in ids


def test_hydrate_empty_tables_keep_seed_path(monkeypatch) -> None:
    set_persist(True)
    monkeypatch.setattr("driveguard.db.fetch_recent_telemetry", lambda per_vehicle=32: [])
    monkeypatch.setattr("driveguard.db.fetch_recent_incidents", lambda limit=80: [])
    assert hydrate_from_db() is False
    assert restored_from_db() is False
    assert has_desk_state() is False
    seed_demo()
    ids = {row["vehicle_id"] for row in vehicles_snapshot()}
    assert "V-1042" in ids


def test_hydrate_db_error_disables_persist(monkeypatch) -> None:
    set_persist(True)

    def boom(per_vehicle: int = 32):
        raise RuntimeError("db down")

    monkeypatch.setattr("driveguard.db.fetch_recent_telemetry", boom)
    assert hydrate_from_db() is False
    assert persist_enabled() is False
    assert restored_from_db() is False

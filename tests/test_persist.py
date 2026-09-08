from driveguard.simulator.session import iter_session
from driveguard.store import _maybe_persist, persist_enabled, set_persist


def test_persist_failure_turns_the_flag_off() -> None:
    sample = next(iter(iter_session(duration=1, inject=None)))
    set_persist(True)
    _maybe_persist(sample, None)
    assert persist_enabled() is False


def test_insert_telemetry_includes_alert_columns() -> None:
    from driveguard.db import insert_telemetry

    captured: dict = {}

    class FakeConn:
        def execute(self, sql, params=None):
            captured["sql"] = sql
            captured["params"] = params

    insert_telemetry(
        FakeConn(),  # type: ignore[arg-type]
        {
            "time": "2026-08-28T00:00:00Z",
            "vehicle_id": "V-1042",
            "speed_kmh": 64.0,
            "accel_ms2": 0.2,
            "brake": 0.4,
            "steering_var": 1.1,
            "lat": 35.68,
            "lon": 139.76,
            "heading_deg": 90.0,
            "behavior": "harsh_braking",
            "alert": "cas_hmw",
            "source": "cas",
            "alert_score": 2.4,
        },
    )
    assert "alert, source, alert_score" in captured["sql"]
    assert captured["params"][-3:] == ("cas_hmw", "cas", 2.4)


def test_insert_incident_includes_alert_columns() -> None:
    from driveguard.db import insert_incident

    captured: dict = {}

    class FakeConn:
        def execute(self, sql, params=None):
            captured["sql"] = sql
            captured["params"] = params

    insert_incident(
        FakeConn(),  # type: ignore[arg-type]
        {
            "incident_id": "11111111-1111-1111-1111-111111111111",
            "vehicle_id": "V-1042",
            "severity": "warn",
            "fused_score": 0.71,
            "behavior": "harsh_braking",
            "summary": "Headway warning on the C1 corridor.",
            "contributing": ["cas_hmw"],
            "recommended_action": "Ease speed through the hotspot.",
            "citations": [{"section_id": "cas-hmw"}],
            "lat": 35.68,
            "lon": 139.76,
            "alert": "cas_hmw",
            "source": "cas",
            "alert_score": 2.4,
        },
    )
    assert "alert, source, alert_score" in captured["sql"]
    assert captured["params"][-3:] == ("cas_hmw", "cas", 2.4)


def test_ensure_incident_created_at_index_sql() -> None:
    from driveguard.db import INCIDENT_CREATED_AT_INDEX_SQL, ensure_incident_created_at_index

    captured: dict = {}

    class FakeConn:
        def execute(self, sql, params=None):
            captured["sql"] = sql

    ensure_incident_created_at_index(FakeConn())  # type: ignore[arg-type]
    assert captured["sql"] == INCIDENT_CREATED_AT_INDEX_SQL
    assert "incidents_created_at" in captured["sql"]
    assert "created_at DESC" in captured["sql"]

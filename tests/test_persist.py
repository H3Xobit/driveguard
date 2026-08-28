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

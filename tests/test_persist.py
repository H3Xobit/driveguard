from contextlib import contextmanager

import pytest

from driveguard.db import reset_runtime_schema
from driveguard.simulator.session import iter_session
from driveguard.store import _maybe_persist, persist_enabled, set_persist


@pytest.fixture(autouse=True)
def _reset_runtime_schema() -> None:
    reset_runtime_schema()
    yield
    reset_runtime_schema()


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


def test_second_persist_ingest_skips_schema_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    from driveguard.db import persist_ingest

    sqls: list[str] = []

    class FakeConn:
        def execute(self, statement, params=None):
            sqls.append(str(statement))

        def commit(self) -> None:
            return None

    @contextmanager
    def fake_connect():
        yield FakeConn()

    monkeypatch.setattr("driveguard.db.connect", fake_connect)
    sample = {
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
    }
    persist_ingest(sample, None)
    first = list(sqls)
    sqls.clear()
    persist_ingest(sample, None)
    assert any("CREATE INDEX" in item for item in first)
    assert any("ALTER TABLE" in item for item in first)
    assert not any("CREATE INDEX" in item for item in sqls)
    assert not any("ALTER TABLE" in item for item in sqls)
    assert any("INSERT INTO telemetry" in item for item in sqls)


def test_fetch_recent_desk_rows_uses_one_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    from driveguard.db import fetch_recent_desk_rows

    connects = {"n": 0}

    class Result:
        def fetchall(self) -> list:
            return []

    sqls: list[str] = []

    class FakeConn:
        def execute(self, statement, params=None):
            sqls.append(str(statement))
            return Result()

        def commit(self) -> None:
            return None

    @contextmanager
    def fake_connect():
        connects["n"] += 1
        yield FakeConn()

    monkeypatch.setattr("driveguard.db.connect", fake_connect)
    telemetry, incidents = fetch_recent_desk_rows()
    assert connects["n"] == 1
    assert sqls and "SELECT 1" in str(sqls[0])
    assert telemetry == []
    assert incidents == []


def test_load_startup_uses_one_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    from driveguard.db import load_startup
    from driveguard.models import Zone

    connects = {"n": 0}
    sqls: list[str] = []

    class Result:
        def fetchone(self):
            return {"exists": True}

        def fetchall(self) -> list:
            return []

    class FakeConn:
        def execute(self, statement, params=None):
            sqls.append(str(statement))
            return Result()

        def commit(self) -> None:
            return None

    @contextmanager
    def fake_connect():
        connects["n"] += 1
        yield FakeConn()

    monkeypatch.setattr("driveguard.db.connect", fake_connect)
    zone = Zone(
        zone_id="TKY-C1-01",
        name="C1",
        lat=35.68,
        lon=139.76,
        radius_m=400,
        historical_risk=0.4,
    )
    ready, telemetry, incidents, hits = load_startup([zone])
    joined = "\n".join(sqls)
    assert connects["n"] == 1
    assert ready is True
    assert "pg_extension" in joined
    assert "INSERT INTO accident_zones" in joined
    assert "SELECT 1" in joined
    assert "FROM telemetry" in joined
    assert "FROM incidents" in joined
    assert "unnest" not in joined.lower()
    assert telemetry == []
    assert incidents == []
    assert hits == {}


def test_zone_hits_on_one_query() -> None:
    from driveguard.db import zone_hits_on

    captured: dict = {}

    class Result:
        def fetchall(self) -> list:
            return [{"idx": 1, "zone_id": "TKY-C1-01", "historical_risk": 0.8}]

    class FakeConn:
        def execute(self, statement, params=None):
            captured["sql"] = str(statement)
            captured["params"] = params
            return Result()

    hits = zone_hits_on(FakeConn(), [(35.68, 139.76), (35.68, 139.76)])  # type: ignore[arg-type]
    sql = captured["sql"]
    assert "unnest" in sql.lower()
    assert "DISTINCT ON" in sql
    assert "ST_DWithin" in sql
    assert "historical_risk DESC" in sql
    assert captured["params"] == ([35.68], [139.76])
    assert hits[(35.68, 139.76)] == (0.8, "TKY-C1-01")


def test_ingest_resolves_zones_outside_the_desk_lock(monkeypatch) -> None:
    from driveguard import geo
    from driveguard.store import _LOCK, ingest_sample, reset_store

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
    moved = sample.model_copy(update={"lat": sample.lat + 20 / geo._M_PER_DEG})
    try:
        assert geo.corridor_cell(sample.lat, sample.lon) != geo.corridor_cell(moved.lat, moved.lon)
        first = ingest_sample(sample)
        second = ingest_sample(moved)
        assert held == [False, False]
        assert first["score"]["nearest_zone"] == "TKY-C1-01"
        assert first["score"]["zone"] == 0.4
        assert second["score"]["zone"] == 0.4
    finally:
        geo.clear_zone_hits()
        geo.set_geo_backend(False)
        reset_store()


def test_bad_mqtt_payload_is_skipped() -> None:
    from driveguard.ingestion.consumer import handle_payload
    from driveguard.store import reset_store

    sample = next(iter(iter_session(duration=1, inject=None)))
    reset_store()
    try:
        assert handle_payload("{") is None
        assert handle_payload(b"\xff") is None
        result = handle_payload(sample.model_dump_json())
        assert result is not None
        assert result["score"]["vehicle_id"] == sample.vehicle_id
    finally:
        reset_store()

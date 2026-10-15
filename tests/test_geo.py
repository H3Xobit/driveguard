from driveguard import geo
from driveguard.db import ZONE_DWITHIN_SQL
from driveguard.geo import zone_risk
from driveguard.ingestion.consumer import start_background


def test_postgis_zone_risk_hits_sql_once(monkeypatch) -> None:
    from driveguard import geo

    calls = {"n": 0}

    def fake_hit(_lat: float, _lon: float) -> tuple[float, str | None]:
        calls["n"] += 1
        return 0.4, "TKY-C1-01"

    monkeypatch.setattr("driveguard.db.zone_hit_sql", fake_hit)
    geo.set_geo_backend(True)
    geo.clear_zone_hits()
    try:
        first = geo.zone_risk(35.68, 139.76)
        second = geo.zone_risk(35.68, 139.76)
        assert first == second == (0.4, "TKY-C1-01")
        assert calls["n"] == 1
        geo.remember_zone_hits({(35.70, 139.77): (0.8, "TKY-C1-02")})
        assert geo.zone_risk(35.70, 139.77) == (0.8, "TKY-C1-02")
        assert calls["n"] == 1
    finally:
        geo.clear_zone_hits()
        geo.set_geo_backend(False)


def test_tokyo_c1_without_database() -> None:
    geo._BACKEND = "haversine"
    risk, name = zone_risk(35.683, 139.776)
    assert risk > 0
    assert name == "TKY-C1-01"


def test_st_dwithin_sql_uses_meters() -> None:
    sql = " ".join(ZONE_DWITHIN_SQL.split())
    assert "ST_DWithin" in sql
    assert "geography" in sql
    assert "radius_m" in sql


def test_mqtt_background_stays_off_in_tests() -> None:
    assert start_background() is None

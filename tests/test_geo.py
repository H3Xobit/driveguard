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


def test_nearby_samples_share_one_corridor_cell(monkeypatch) -> None:
    from driveguard import geo

    calls: list[float] = []

    def fake_hit(lat: float, _lon: float) -> tuple[float, str | None]:
        calls.append(lat)
        return (0.4 if len(calls) == 1 else 0.9), "TKY-C1-01"

    monkeypatch.setattr("driveguard.db.zone_hit_sql", fake_hit)
    geo.set_geo_backend(True)
    geo.clear_zone_hits()
    lat0 = 35.6812
    lat1 = lat0 + 2 / geo._M_PER_DEG
    far = lat0 + 20 / geo._M_PER_DEG
    try:
        assert geo.corridor_cell(lat0, 139.76) == geo.corridor_cell(lat1, 139.76)
        assert geo.corridor_cell(lat0, 139.76) != geo.corridor_cell(far, 139.76)
        assert geo.zone_risk(lat0, 139.76) == (0.4, "TKY-C1-01")
        assert geo.zone_risk(lat1, 139.76) == (0.4, "TKY-C1-01")
        assert calls == [lat0]
        assert geo.zone_risk(far, 139.76) == (0.9, "TKY-C1-01")
        assert calls == [lat0, far]
    finally:
        geo.clear_zone_hits()
        geo.set_geo_backend(False)


def test_corridor_cache_drops_oldest_cell(monkeypatch) -> None:
    from driveguard import geo

    calls: list[float] = []

    def fake_hit(lat: float, _lon: float) -> tuple[float, str | None]:
        calls.append(lat)
        return float(len(calls)), "TKY-C1-01"

    monkeypatch.setattr("driveguard.db.zone_hit_sql", fake_hit)
    geo.set_geo_backend(True)
    geo.clear_zone_hits()
    cap = geo._CACHE_CAP
    geo._CACHE_CAP = 2
    lats = [35.6812 + i * 20 / geo._M_PER_DEG for i in range(3)]
    lon = 139.76
    try:
        cells = [geo.corridor_cell(lat, lon) for lat in lats]
        assert len(set(cells)) == 3
        assert geo.zone_risk(lats[0], lon) == (1.0, "TKY-C1-01")
        assert geo.zone_risk(lats[1], lon) == (2.0, "TKY-C1-01")
        assert geo.zone_risk(lats[2], lon) == (3.0, "TKY-C1-01")
        assert len(geo._ZONE_HITS) == 2
        assert cells[0] not in geo._ZONE_HITS
        before = len(calls)
        assert geo.zone_risk(lats[1], lon) == (2.0, "TKY-C1-01")
        assert len(calls) == before
        assert geo.zone_risk(lats[0], lon) == (4.0, "TKY-C1-01")
        assert len(calls) == before + 1
    finally:
        geo._CACHE_CAP = cap
        geo.clear_zone_hits()
        geo.set_geo_backend(False)


def test_concurrent_miss_shares_one_corridor_lookup(monkeypatch) -> None:
    import threading
    import time

    from driveguard import geo

    calls: list[float] = []
    entered = threading.Event()
    release = threading.Event()

    def fake_hit(lat: float, _lon: float) -> tuple[float, str | None]:
        calls.append(lat)
        entered.set()
        assert release.wait(2)
        return 0.4, "TKY-C1-01"

    monkeypatch.setattr("driveguard.db.zone_hit_sql", fake_hit)
    geo.set_geo_backend(True)
    geo.clear_zone_hits()
    lat = 35.6812
    lon = 139.76
    key = geo.corridor_cell(lat, lon)
    results: list[tuple[float, str | None]] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            results.append(geo.zone_risk(lat, lon))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    try:
        threads[0].start()
        assert entered.wait(2)
        threads[1].start()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with geo._ZONE_LOCK:
                lookup = geo._LOOKUPS.get(key)
                waiting = lookup.waiting if lookup is not None else 0
            if waiting >= 1:
                break
            time.sleep(0.01)
        else:
            raise AssertionError("second sample did not wait")
        assert calls == [lat]
        release.set()
        for thread in threads:
            thread.join(timeout=2)
        assert errors == []
        assert not any(thread.is_alive() for thread in threads)
        assert results == [(0.4, "TKY-C1-01"), (0.4, "TKY-C1-01")]
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=2)
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

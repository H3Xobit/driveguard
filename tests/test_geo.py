from driveguard import geo
from driveguard.db import ZONE_DWITHIN_SQL
from driveguard.geo import zone_risk
from driveguard.ingestion.consumer import start_background


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

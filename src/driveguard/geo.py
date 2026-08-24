"""Tokyo corridor lookup. PostGIS ST_DWithin when the database is up, haversine otherwise."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from driveguard.models import Zone

ASSETS = Path(__file__).resolve().parent / "assets"

_BACKEND = "haversine"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


@lru_cache
def load_zones() -> list[Zone]:
    path = ASSETS / "zones.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Zone.model_validate(z) for z in raw]


def geo_backend() -> str:
    return _BACKEND


def enable_postgis() -> bool:
    """Seed zones and switch zone_risk to ST_DWithin. Returns False when DB is offline."""
    global _BACKEND
    from driveguard.db import postgis_ready, seed_zones

    if not postgis_ready():
        _BACKEND = "haversine"
        return False
    seed_zones(load_zones())
    _BACKEND = "postgis"
    return True


def zone_risk(lat: float, lon: float) -> tuple[float, str | None]:
    """Return max historical risk of any zone whose radius covers the point."""
    if _BACKEND == "postgis":
        try:
            from driveguard.db import zone_hit_sql

            return zone_hit_sql(lat, lon)
        except Exception:
            pass
    return _zone_risk_haversine(lat, lon)


def _zone_risk_haversine(lat: float, lon: float) -> tuple[float, str | None]:
    best = 0.0
    name: str | None = None
    for zone in load_zones():
        dist = haversine_m(lat, lon, zone.lat, zone.lon)
        if dist <= zone.radius_m and zone.historical_risk > best:
            best = zone.historical_risk
            name = zone.zone_id
    return best, name

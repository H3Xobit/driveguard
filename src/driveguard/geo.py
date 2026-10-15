"""Tokyo corridor lookup. PostGIS ST_DWithin when the database is up, haversine otherwise."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from threading import Lock

from driveguard.models import Zone

ASSETS = Path(__file__).resolve().parent / "assets"

_BACKEND = "haversine"
_ZONE_HITS: dict[tuple[float, float], tuple[float, str | None]] = {}
_ZONE_LOCK = Lock()


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


def set_geo_backend(postgis: bool) -> None:
    """Choose ST_DWithin or haversine. Seeding happens on the startup connection."""
    global _BACKEND
    _BACKEND = "postgis" if postgis else "haversine"


def clear_zone_hits() -> None:
    """Drop the process-local corridor cache. Tests and a failed startup use this."""
    with _ZONE_LOCK:
        _ZONE_HITS.clear()


def remember_zone_hits(
    hits: dict[tuple[float, float], tuple[float, str | None]],
) -> None:
    """Replace the corridor cache with hits already resolved on the startup connection."""
    with _ZONE_LOCK:
        _ZONE_HITS.clear()
        for (lat, lon), hit in hits.items():
            _ZONE_HITS[(float(lat), float(lon))] = hit


def enable_postgis() -> bool:
    """Seed zones and switch zone_risk to ST_DWithin. Returns False when DB is offline."""
    from driveguard.db import postgis_ready, seed_zones

    if not postgis_ready():
        set_geo_backend(False)
        return False
    seed_zones(load_zones())
    set_geo_backend(True)
    return True


def zone_risk(lat: float, lon: float) -> tuple[float, str | None]:
    """Return max historical risk of any zone whose radius covers the point."""
    if _BACKEND == "postgis":
        key = (float(lat), float(lon))
        with _ZONE_LOCK:
            cached = _ZONE_HITS.get(key)
        if cached is not None:
            return cached
        try:
            from driveguard.db import zone_hit_sql

            hit = zone_hit_sql(lat, lon)
        except Exception:
            pass
        else:
            with _ZONE_LOCK:
                existing = _ZONE_HITS.get(key)
                if existing is not None:
                    return existing
                _ZONE_HITS[key] = hit
            return hit
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

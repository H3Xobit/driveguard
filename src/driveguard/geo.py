"""Haversine zone lookup. PostGIS can replace this when the database is in the path."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from driveguard.models import Zone

ASSETS = Path(__file__).resolve().parent / "assets"


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


def zone_risk(lat: float, lon: float) -> tuple[float, str | None]:
    """Return max historical risk of any zone whose radius covers the point."""
    best = 0.0
    name: str | None = None
    for zone in load_zones():
        dist = haversine_m(lat, lon, zone.lat, zone.lon)
        if dist <= zone.radius_m and zone.historical_risk > best:
            best = zone.historical_risk
            name = zone.zone_id
    return best, name

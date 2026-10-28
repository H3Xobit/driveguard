"""Tokyo corridor lookup. PostGIS ST_DWithin when the database is up, haversine otherwise."""

from __future__ import annotations

import json
import math
import time
from functools import lru_cache
from pathlib import Path
from threading import Event, Lock

from driveguard.models import Zone

ASSETS = Path(__file__).resolve().parent / "assets"

_BACKEND = "haversine"
# 111_320 m per degree is the usual WGS84 latitude scale. Longitude uses
# cos of the Tokyo corridor so a cell stays about GRID_M meters on both axes.
_M_PER_DEG = 111_320.0
_REF_LAT = 35.68
_M_PER_DEG_LON = _M_PER_DEG * math.cos(math.radians(_REF_LAT))
GRID_M = 10
# 2048 cells is about 20 km of distinct 10 m cells, enough for one corridor run.
_CACHE_CAP = 2048
# A failed lookup keeps its haversine result only this long, then the next
# sample calls PostGIS again. time.monotonic ignores wall-clock steps.
_FALLBACK_AGE_S = 30.0
_ZONE_HITS: dict[tuple[int, int], tuple[float, str | None]] = {}
_ZONE_FALLBACKS: dict[tuple[int, int], tuple[tuple[float, str | None], float]] = {}
# Set when a lookup fails. Every cell skips PostGIS until this age passes.
_POSTGIS_FAILED_AT: float | None = None
# One sample probes after the pause. Other cells stay on haversine until it finishes
# or until the probe itself is older than the fallback age.
_POSTGIS_PROBING = False
_POSTGIS_PROBE_AT: float | None = None
# After a probe succeeds, one uncached lookup runs at a time until this instant.
_POSTGIS_QUIET_UNTIL: float | None = None
_POSTGIS_QUIET_SQL: int | None = None
_QUIET_GEN = 0
_ZONE_LOCK = Lock()


def _now() -> float:
    return time.monotonic()


class _CellLookup:
    """One in-flight ST_DWithin for a cell. Waiters share its result."""

    def __init__(self) -> None:
        self.done = Event()
        self.hit: tuple[float, str | None] | None = None
        self.waiting = 0


_LOOKUPS: dict[tuple[int, int], _CellLookup] = {}


def _store_cell(key: tuple[int, int], hit: tuple[float, str | None]) -> None:
    """Store one PostGIS cell. Caller holds _ZONE_LOCK. Drops the oldest cells past the cap."""
    _ZONE_HITS[key] = hit
    _ZONE_FALLBACKS.pop(key, None)
    while len(_ZONE_HITS) > _CACHE_CAP:
        del _ZONE_HITS[next(iter(_ZONE_HITS))]


def _probe_blocking() -> bool:
    """True while a young probe should keep other cells off PostGIS. Caller holds _ZONE_LOCK."""
    if not _POSTGIS_PROBING or _POSTGIS_PROBE_AT is None:
        return False
    return _now() - _POSTGIS_PROBE_AT < _FALLBACK_AGE_S


def _clear_probe() -> None:
    """Drop the in-flight probe. Caller holds _ZONE_LOCK."""
    global _POSTGIS_PROBING, _POSTGIS_PROBE_AT
    _POSTGIS_PROBING = False
    _POSTGIS_PROBE_AT = None


def _quiet_active() -> bool:
    """True during the short window after a successful probe. Caller holds _ZONE_LOCK."""
    if _POSTGIS_QUIET_UNTIL is None:
        return False
    return _now() < _POSTGIS_QUIET_UNTIL


def _clear_quiet() -> None:
    """Drop the post-probe quiet window. Caller holds _ZONE_LOCK."""
    global _POSTGIS_QUIET_UNTIL, _POSTGIS_QUIET_SQL
    _POSTGIS_QUIET_UNTIL = None
    _POSTGIS_QUIET_SQL = None


def _postgis_paused() -> bool:
    """True while a failed lookup is still inside its age. Caller holds _ZONE_LOCK."""
    if _POSTGIS_FAILED_AT is None:
        return False
    return _now() - _POSTGIS_FAILED_AT < _FALLBACK_AGE_S


def _fresh_fallback(key: tuple[int, int]) -> tuple[float, str | None] | None:
    """Return a haversine fallback still inside its age. Caller holds _ZONE_LOCK."""
    found = _ZONE_FALLBACKS.get(key)
    if found is None:
        return None
    hit, stored = found
    if _now() - stored >= _FALLBACK_AGE_S:
        del _ZONE_FALLBACKS[key]
        return None
    return hit


def _store_fallback(
    key: tuple[int, int],
    hit: tuple[float, str | None],
    *,
    until: float | None = None,
) -> None:
    """Remember a haversine fallback. Caller holds _ZONE_LOCK.

    until makes the result expire at that instant instead of a full age from now.
    """
    now = _now()
    stored = now if until is None else until - _FALLBACK_AGE_S
    stale = [
        cell
        for cell, (_, seen) in _ZONE_FALLBACKS.items()
        if now - seen >= _FALLBACK_AGE_S
    ]
    for cell in stale:
        del _ZONE_FALLBACKS[cell]
    _ZONE_FALLBACKS[key] = (hit, stored)


def corridor_cell(lat: float, lon: float) -> tuple[int, int]:
    """10 m grid cell for a WGS84 point on the Tokyo corridor."""
    return (
        math.floor(float(lat) * _M_PER_DEG / GRID_M),
        math.floor(float(lon) * _M_PER_DEG_LON / GRID_M),
    )


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
    global _POSTGIS_FAILED_AT
    with _ZONE_LOCK:
        _ZONE_HITS.clear()
        _ZONE_FALLBACKS.clear()
        _POSTGIS_FAILED_AT = None
        _clear_probe()
        _clear_quiet()


def remember_zone_hits(
    hits: dict[tuple[float, float], tuple[float, str | None]],
) -> None:
    """Replace the corridor cache with hits already resolved on the startup connection."""
    global _POSTGIS_FAILED_AT
    with _ZONE_LOCK:
        _ZONE_HITS.clear()
        _ZONE_FALLBACKS.clear()
        _POSTGIS_FAILED_AT = None
        _clear_probe()
        _clear_quiet()
        for (lat, lon), hit in hits.items():
            key = corridor_cell(lat, lon)
            if key not in _ZONE_HITS:
                _store_cell(key, hit)


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
    global _POSTGIS_FAILED_AT, _POSTGIS_PROBING, _POSTGIS_PROBE_AT
    global _POSTGIS_QUIET_UNTIL, _POSTGIS_QUIET_SQL, _QUIET_GEN
    if _BACKEND != "postgis":
        return _zone_risk_haversine(lat, lon)
    key = corridor_cell(lat, lon)
    probe_at: float | None = None
    quiet_token: int | None = None
    with _ZONE_LOCK:
        cached = _ZONE_HITS.get(key)
        if cached is not None:
            return cached
        fallback = _fresh_fallback(key)
        if fallback is not None:
            return fallback
        quiet_skip = False
        if _postgis_paused():
            skip = True
        else:
            skip = False
            lookup = _LOOKUPS.get(key)
            if lookup is not None:
                lookup.waiting += 1
                leader = False
            elif _POSTGIS_FAILED_AT is not None and _probe_blocking():
                skip = True
            elif _quiet_active() and _POSTGIS_QUIET_SQL is not None:
                skip = True
                quiet_skip = True
            else:
                if _POSTGIS_FAILED_AT is not None:
                    probe_at = _now()
                    _POSTGIS_PROBING = True
                    _POSTGIS_PROBE_AT = probe_at
                if _quiet_active():
                    _QUIET_GEN += 1
                    quiet_token = _QUIET_GEN
                    _POSTGIS_QUIET_SQL = quiet_token
                lookup = _CellLookup()
                _LOOKUPS[key] = lookup
                leader = True
    if skip:
        hit = _zone_risk_haversine(lat, lon)
        if quiet_skip:
            with _ZONE_LOCK:
                until = _POSTGIS_QUIET_UNTIL
                if (
                    until is not None
                    and _now() < until
                    and key not in _ZONE_HITS
                    and _fresh_fallback(key) is None
                ):
                    _store_fallback(key, hit, until=until)
        return hit
    if not leader:
        lookup.done.wait()
        if lookup.hit is not None:
            return lookup.hit
        return _zone_risk_haversine(lat, lon)
    hit: tuple[float, str | None] | None = None
    try:
        failed = False
        try:
            from driveguard.db import zone_hit_sql

            hit = zone_hit_sql(lat, lon)
        except Exception:
            failed = True
            hit = _zone_risk_haversine(lat, lon)
        with _ZONE_LOCK:
            existing = _ZONE_HITS.get(key)
            if existing is not None:
                hit = existing
            elif failed:
                if probe_at is None or _POSTGIS_PROBE_AT == probe_at:
                    _POSTGIS_FAILED_AT = _now()
                _store_fallback(key, hit)
            else:
                if probe_at is None or _POSTGIS_PROBE_AT == probe_at:
                    _POSTGIS_FAILED_AT = None
                    if probe_at is not None:
                        _POSTGIS_QUIET_UNTIL = _now() + _FALLBACK_AGE_S
                _store_cell(key, hit)
    finally:
        lookup.hit = hit
        with _ZONE_LOCK:
            if _LOOKUPS.get(key) is lookup:
                del _LOOKUPS[key]
            if probe_at is not None and _POSTGIS_PROBE_AT == probe_at:
                _clear_probe()
            if quiet_token is not None and _POSTGIS_QUIET_SQL == quiet_token:
                _POSTGIS_QUIET_SQL = None
        lookup.done.set()
    if hit is None:
        return _zone_risk_haversine(lat, lon)
    return hit


def _zone_risk_haversine(lat: float, lon: float) -> tuple[float, str | None]:
    best = 0.0
    name: str | None = None
    for zone in load_zones():
        dist = haversine_m(lat, lon, zone.lat, zone.lon)
        if dist <= zone.radius_m and zone.historical_risk > best:
            best = zone.historical_risk
            name = zone.zone_id
    return best, name

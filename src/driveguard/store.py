"""In-process ring buffers so the API works without Postgres in tests and Pages demo."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from threading import Lock
from typing import Any
from uuid import UUID

from driveguard.geo import zone_risk
from driveguard.llm.narrative import narrate_incident
from driveguard.models import BehaviorTag, Incident, Severity, TelemetrySample
from driveguard.risk.priority import prioritize
from driveguard.risk.temporal import score_window
from driveguard.settings import get_settings

_LOCK = Lock()
_TELEM: dict[str, deque[TelemetrySample]] = defaultdict(lambda: deque(maxlen=256))
_SCORES: deque[dict[str, Any]] = deque(maxlen=200)
_INCIDENTS: deque[Incident] = deque(maxlen=80)
_LATEST: dict[str, dict[str, Any]] = {}


def ingest_sample(sample: TelemetrySample) -> dict[str, Any]:
    settings = get_settings()
    zone, zone_id = zone_risk(sample.lat, sample.lon)
    with _LOCK:
        buf = _TELEM[sample.vehicle_id]
        buf.append(sample)
        samples = list(buf)
        zones = [zone_risk(s.lat, s.lon)[0] for s in samples]
        scored = score_window(samples, zones)
        scored["vehicle_id"] = sample.vehicle_id
        scored["behavior"] = sample.behavior.value
        scored["lat"] = sample.lat
        scored["lon"] = sample.lon
        scored["speed_kmh"] = sample.speed_kmh
        scored["nearest_zone"] = zone_id
        scored["zone"] = zone
        scored["alert"] = sample.alert.value
        scored["alert_score"] = sample.alert_score
        scored["source"] = sample.source.value
        fused = scored["fused"]
        if isinstance(fused, float) and zone >= 0.55 and float(scored["temporal"]) >= 0.55:
            scored["compounding"] = True
        _SCORES.appendleft(scored)
        _LATEST[sample.vehicle_id] = scored
        incident = None
        if float(scored["fused"]) >= settings.risk_warn:
            incident = narrate_incident(
                vehicle_id=sample.vehicle_id,
                behavior=sample.behavior,
                fused=float(scored["fused"]),
                severity=Severity(scored["severity"]),
                lat=sample.lat,
                lon=sample.lon,
                zone_name=zone_id,
                compounding=bool(scored["compounding"]),
                alert=sample.alert,
                alert_score_value=sample.alert_score,
                source=sample.source,
            )
            _INCIDENTS.appendleft(incident)
        return {"score": scored, "incident": incident.model_dump(mode="json") if incident else None}


def inject_behavior(
    behavior: str, vehicle_id: str = "V-1042", duration: int = 36
) -> dict[str, Any]:
    from driveguard.simulator.session import iter_session

    reverse = {
        "cas_ldw": "weaving",
        "cas_hmw": "harsh_braking",
        "cas_fcw": "speeding",
        "dms_distract": "fatigue_drift",
    }
    behavior = reverse.get(behavior, behavior)
    tag = BehaviorTag(behavior)
    last: dict[str, Any] | None = None
    for sample in iter_session(vehicle_id=vehicle_id, duration=duration, inject=tag):
        last = ingest_sample(sample)
    assert last is not None
    return last


def list_scores(limit: int = 40) -> list[dict[str, Any]]:
    with _LOCK:
        return list(_SCORES)[:limit]


def list_incidents(limit: int = 20) -> list[Incident]:
    with _LOCK:
        ranked = prioritize(list(_INCIDENTS))
        return ranked[:limit]


def get_incident(incident_id: UUID) -> Incident | None:
    with _LOCK:
        for inc in _INCIDENTS:
            if inc.incident_id == incident_id:
                return inc
    return None


def alert_mix() -> dict[str, dict[str, int]]:
    with _LOCK:
        counts: Counter[str] = Counter()
        weekday: Counter[str] = Counter()
        for buf in _TELEM.values():
            for sample in buf:
                if sample.alert.value != "none":
                    counts[sample.alert.value] += 1
                weekday[sample.time.strftime("%A")] += 1
        return {"alerts": dict(counts), "weekday": dict(weekday)}


def vehicles_snapshot() -> list[dict[str, Any]]:
    with _LOCK:
        return list(_LATEST.values())


def seed_demo() -> None:
    if _LATEST:
        return
    inject_behavior("calm", vehicle_id="V-2218", duration=20)
    inject_behavior("harsh_braking", vehicle_id="V-1042", duration=28)

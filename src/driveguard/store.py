"""In-process ring buffers so the API works without Postgres in tests and Pages demo."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from threading import Lock
from typing import Any
from uuid import UUID

from driveguard.geo import zone_risk
from driveguard.llm.narrative import narrate_incident
from driveguard.models import AlertCode, BehaviorTag, Incident, Severity, StreamSource, TelemetrySample
from driveguard.risk.priority import prioritize
from driveguard.risk.temporal import score_window
from driveguard.settings import get_settings

_LOCK = Lock()
_TELEM: dict[str, deque[TelemetrySample]] = defaultdict(lambda: deque(maxlen=256))
_SCORES: deque[dict[str, Any]] = deque(maxlen=200)
_INCIDENTS: deque[Incident] = deque(maxlen=80)
_LATEST: dict[str, dict[str, Any]] = {}
_PERSIST = False
_RESTORED = False


def set_persist(enabled: bool) -> None:
    global _PERSIST
    _PERSIST = enabled


def persist_enabled() -> bool:
    return _PERSIST


def restored_from_db() -> bool:
    return _RESTORED


def reset_store() -> None:
    global _RESTORED
    with _LOCK:
        _TELEM.clear()
        _SCORES.clear()
        _INCIDENTS.clear()
        _LATEST.clear()
    _RESTORED = False


def has_desk_state() -> bool:
    with _LOCK:
        return bool(_LATEST or _INCIDENTS)


def _maybe_persist(sample: TelemetrySample, incident: Incident | None) -> None:
    if not _PERSIST:
        return
    try:
        from driveguard.db import persist_ingest

        row = sample.model_dump(mode="python")
        row["behavior"] = sample.behavior.value
        row["alert"] = sample.alert.value
        row["source"] = sample.source.value
        persist_ingest(row, incident.model_dump(mode="json") if incident else None)
    except Exception:
        set_persist(False)


def _score_into_buffers(
    sample: TelemetrySample, *, emit_incident: bool
) -> tuple[dict[str, Any], Incident | None]:
    settings = get_settings()
    zone, zone_id = zone_risk(sample.lat, sample.lon)
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
    if emit_incident and float(scored["fused"]) >= settings.risk_warn:
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
    return scored, incident


def ingest_sample(sample: TelemetrySample) -> dict[str, Any]:
    with _LOCK:
        scored, incident = _score_into_buffers(sample, emit_incident=True)
        result = {
            "score": scored,
            "incident": incident.model_dump(mode="json") if incident else None,
        }
    _maybe_persist(sample, incident)
    return result


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
    if has_desk_state():
        return
    inject_behavior("calm", vehicle_id="V-2218", duration=20)
    inject_behavior("harsh_braking", vehicle_id="V-1042", duration=28)


def _sample_from_row(row: dict[str, Any]) -> TelemetrySample | None:
    try:
        return TelemetrySample(
            time=row["time"],
            vehicle_id=row["vehicle_id"],
            speed_kmh=float(row["speed_kmh"]),
            accel_ms2=float(row["accel_ms2"]),
            brake=float(row["brake"]),
            steering_var=float(row["steering_var"]),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            heading_deg=float(row["heading_deg"]),
            behavior=row["behavior"],
            alert=row.get("alert") or AlertCode.none,
            source=row.get("source") or StreamSource.cas,
            alert_score=float(row.get("alert_score") or 0.0),
        )
    except Exception:
        return None


def _incident_from_row(row: dict[str, Any]) -> Incident | None:
    try:
        return Incident(
            incident_id=row["incident_id"],
            vehicle_id=row["vehicle_id"],
            severity=row["severity"],
            fused_score=float(row["fused_score"]),
            behavior=row["behavior"],
            summary=row["summary"],
            contributing=list(row.get("contributing") or []),
            recommended_action=row["recommended_action"],
            citations=list(row.get("citations") or []),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            created_at=row.get("created_at"),
            alert=row.get("alert") or AlertCode.none,
            source=row.get("source") or StreamSource.cas,
            alert_score=float(row.get("alert_score") or 0.0),
        )
    except Exception:
        return None


def hydrate_from_db() -> bool:
    """Fill in-process buffers from Postgres. No-op when persist is off or tables are empty."""
    global _RESTORED
    if not _PERSIST:
        _RESTORED = False
        return False
    try:
        from driveguard.db import fetch_recent_desk_rows

        rows, incident_rows = fetch_recent_desk_rows()
    except Exception:
        set_persist(False)
        _RESTORED = False
        return False
    samples: list[TelemetrySample] = []
    for row in rows:
        sample = _sample_from_row(row)
        if sample is not None:
            samples.append(sample)
    incidents: list[Incident] = []
    for row in incident_rows:
        incident = _incident_from_row(row)
        if incident is not None:
            incidents.append(incident)
    if not samples and not incidents:
        _RESTORED = False
        return False
    with _LOCK:
        _TELEM.clear()
        _SCORES.clear()
        _INCIDENTS.clear()
        _LATEST.clear()
        for sample in samples:
            _score_into_buffers(sample, emit_incident=False)
        for incident in reversed(incidents):
            _INCIDENTS.appendleft(incident)
    _RESTORED = True
    return True

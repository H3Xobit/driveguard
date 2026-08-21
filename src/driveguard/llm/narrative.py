"""Incident notes grounded in retrieved safety guidelines and CAS/DMS codes."""

from __future__ import annotations

from driveguard.models import AlertCode, BehaviorTag, Incident, Severity, StreamSource
from driveguard.rag.retrieve import retrieve
from driveguard.risk.scoring import behavior_to_alert

CAUSE_BY_ALERT = {
    AlertCode.cas_hmw: "headway warning (cas_hmw) with short following distance",
    AlertCode.cas_fcw: "forward collision warning (cas_fcw) at elevated speed",
    AlertCode.cas_ldw: "lane departure warning (cas_ldw) with high steering variance",
    AlertCode.dms_distract: "DMS inattention cue with heading and speed wander",
    AlertCode.none: "no CAS/DMS alert on this sample",
}

ACTION_BY_ALERT = {
    AlertCode.cas_hmw: "Increase following distance; review the last HMW cluster on this vehicle.",
    AlertCode.cas_fcw: "Hold posted speed; treat FCW at band 3+ as a coaching event.",
    AlertCode.cas_ldw: "Lane-discipline review before the next trip.",
    AlertCode.dms_distract: "Rest break and hours-of-service check (DMS stream).",
    AlertCode.none: "No intervention. Keep sampling.",
}


def _offline_narrative(
    *,
    vehicle_id: str,
    alert: AlertCode,
    fused: float,
    alert_score_value: float,
    zone_name: str | None,
    compounding: bool,
    hits: list[dict],
) -> tuple[str, str, list[str], list[dict]]:
    cause = CAUSE_BY_ALERT[alert]
    action = ACTION_BY_ALERT[alert]
    zone_bit = f" in mapped corridor {zone_name}" if zone_name else ""
    extra = ""
    if compounding:
        extra = " Live kinematics and a historical hotspot fired together."
    cites = [
        {
            "section_id": h["section_id"],
            "title": h["title"],
            "quote": h["text"][:180],
        }
        for h in hits[:3]
    ]
    cite_ids = ", ".join(c["section_id"] for c in cites) or "none"
    summary = (
        f"{vehicle_id} {alert.value} (speed-band score {alert_score_value:.1f}, "
        f"session risk {fused:.2f}){zone_bit}. {cause}.{extra} "
        f"Citations: {cite_ids}."
    )
    contributing = [cause]
    if compounding and zone_name:
        contributing.append(f"hotspot {zone_name}")
    return summary.strip(), action, contributing, cites


def narrate_incident(
    *,
    vehicle_id: str,
    behavior: BehaviorTag,
    fused: float,
    severity: Severity,
    lat: float,
    lon: float,
    zone_name: str | None,
    compounding: bool,
    alert: AlertCode | None = None,
    alert_score_value: float = 0.0,
    source: StreamSource = StreamSource.cas,
) -> Incident:
    alert = alert or behavior_to_alert(behavior.value)
    if alert is AlertCode.none:
        query = "incident narrative rules no invented weather"
    else:
        query = f"{alert.value} {behavior.value} headway lane departure speed hotspot"
    hits = retrieve(query, top_k=4)
    summary, action, contributing, cites = _offline_narrative(
        vehicle_id=vehicle_id,
        alert=alert,
        fused=fused,
        alert_score_value=alert_score_value,
        zone_name=zone_name,
        compounding=compounding,
        hits=hits,
    )
    allowed = {h["section_id"] for h in hits}
    cites = [c for c in cites if c["section_id"] in allowed]
    return Incident(
        vehicle_id=vehicle_id,
        severity=severity,
        fused_score=fused,
        behavior=behavior,
        alert=alert,
        alert_score=alert_score_value,
        source=source,
        summary=summary,
        contributing=contributing,
        recommended_action=action,
        citations=cites,
        lat=lat,
        lon=lon,
    )

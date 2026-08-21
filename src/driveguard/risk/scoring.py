"""Speed-banded alert scores for CAS/DMS events.

Each ADAS event is scored from vehicle speed, with a higher band above 60 km/h.
The table is explicit so operators can audit it, then used next to the
rolling-window risk score.

Bands are km/h. Weights follow typical CAS severity (FCW > HMW > LDW).
"""

from __future__ import annotations

from driveguard.models import AlertCode

# Speeds above 60 km/h step into a higher band.
SPEED_BANDS: tuple[tuple[float, int], ...] = (
    (40.0, 1),
    (60.0, 2),
    (80.0, 3),
    (float("inf"), 4),
)

ALERT_WEIGHT: dict[AlertCode, float] = {
    AlertCode.none: 0.0,
    AlertCode.cas_ldw: 1.00,
    AlertCode.cas_hmw: 1.20,
    AlertCode.cas_fcw: 1.40,
    AlertCode.dms_distract: 1.15,
}


def speed_band(speed_kmh: float) -> int:
    for upper, band in SPEED_BANDS:
        if speed_kmh < upper:
            return band
    return 4


def alert_score(alert: AlertCode, speed_kmh: float) -> float:
    """Integer-ish score on 0..5.6 (band 4 * FCW 1.4)."""
    if alert is AlertCode.none:
        return 0.0
    return round(speed_band(speed_kmh) * ALERT_WEIGHT[alert], 3)


def behavior_to_alert(behavior: str) -> AlertCode:
    """Map injected kinematics onto iRASTE-style CAS/DMS codes."""
    return {
        "calm": AlertCode.none,
        "weaving": AlertCode.cas_ldw,
        "harsh_braking": AlertCode.cas_hmw,
        "speeding": AlertCode.cas_fcw,
        "fatigue_drift": AlertCode.dms_distract,
    }.get(behavior, AlertCode.none)

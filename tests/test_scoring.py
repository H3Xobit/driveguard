from driveguard.models import AlertCode
from driveguard.risk.scoring import alert_score, behavior_to_alert, speed_band


def test_speed_band_steps_at_60() -> None:
    assert speed_band(30) == 1
    assert speed_band(59.9) == 2
    assert speed_band(60) == 3
    assert speed_band(90) == 4


def test_fcw_outranks_ldw_at_same_speed() -> None:
    assert alert_score(AlertCode.cas_fcw, 70) > alert_score(AlertCode.cas_ldw, 70)


def test_behavior_maps_to_cas_codes() -> None:
    assert behavior_to_alert("weaving") is AlertCode.cas_ldw
    assert behavior_to_alert("harsh_braking") is AlertCode.cas_hmw
    assert behavior_to_alert("speeding") is AlertCode.cas_fcw
    assert behavior_to_alert("fatigue_drift") is AlertCode.dms_distract
    assert alert_score(AlertCode.none, 90) == 0.0

from driveguard.models import BehaviorTag, Incident, Severity
from driveguard.risk.priority import prioritize


def test_fault_hides_info_rows() -> None:
    fault = Incident(
        vehicle_id="V-1",
        severity=Severity.fault,
        fused_score=0.9,
        behavior=BehaviorTag.speeding,
        summary="fcw event",
        recommended_action="slow down",
        lat=35.68,
        lon=139.77,
        alert_score=4.2,
    )
    info = Incident(
        vehicle_id="V-2",
        severity=Severity.info,
        fused_score=0.2,
        behavior=BehaviorTag.calm,
        summary="quiet",
        recommended_action="none",
        lat=35.68,
        lon=139.77,
        alert_score=0.0,
    )
    ranked = prioritize([info, fault])
    assert [i.vehicle_id for i in ranked] == ["V-1"]

"""Rank incidents the way a safety desk would, not FIFO.

Literature on adaptive information filtering (Park and Kim, among others)
argues that low-priority ADAS chatter should drop when a high-severity event
is on the board. DriveGuard applies a small version of that: fault rows lead,
then warn, then info, and info rows are omitted while any fault is present.
"""

from __future__ import annotations

from driveguard.models import Incident, Severity


def prioritize(incidents: list[Incident]) -> list[Incident]:
    has_fault = any(i.severity is Severity.fault for i in incidents)
    pool = [i for i in incidents if not (has_fault and i.severity is Severity.info)]
    rank = {Severity.fault: 0, Severity.warn: 1, Severity.info: 2}
    return sorted(
        pool,
        key=lambda i: (rank[i.severity], -i.alert_score, -i.fused_score),
    )

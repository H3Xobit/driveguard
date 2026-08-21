from driveguard.llm.narrative import narrate_incident
from driveguard.models import BehaviorTag, Severity
from driveguard.rag.retrieve import retrieve


def test_retrieve_brake_guidelines() -> None:
    hits = retrieve("hard braking following distance", top_k=3)
    assert hits
    assert hits[0]["section_id"].startswith("GL-")


def test_narrative_no_hallucinated_weather() -> None:
    inc = narrate_incident(
        vehicle_id="V-1042",
        behavior=BehaviorTag.harsh_braking,
        fused=0.81,
        severity=Severity.fault,
        lat=35.68,
        lon=139.77,
        zone_name="TKY-C1-01",
        compounding=True,
    )
    blob = (inc.summary + inc.recommended_action).lower()
    assert "intoxication" not in blob
    assert "ice" not in blob
    assert "cas_hmw" in blob
    assert inc.citations
    assert all(c["section_id"].startswith("GL-") for c in inc.citations)

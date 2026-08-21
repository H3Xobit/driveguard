from fastapi.testclient import TestClient

from driveguard.api.main import app

client = TestClient(app)


def test_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "driveguard-api"


def test_meta_behaviors() -> None:
    res = client.get("/meta")
    body = res.json()
    assert body["service"] == "driveguard-api"
    assert "harsh_braking" in body["behaviors"]
    assert "cas_ldw" in body["alert_codes"]
    assert body["zones"] >= 1


def test_inject_cas_code() -> None:
    res = client.post("/simulate/inject", params={"type": "cas_hmw"})
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is True
    assert body["score"]["alert"] == "cas_hmw"
    listed = client.get("/incidents")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1
    stats = client.get("/stats")
    assert "cas_hmw" in stats.json()["alerts"]

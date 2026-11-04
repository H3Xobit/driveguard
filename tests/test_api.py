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
    assert body["geo_backend"] in {"haversine", "postgis"}
    assert "persist" in body
    assert "restored" in body
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


def test_negative_desk_limit_is_rejected() -> None:
    seeded = client.post("/simulate/inject", params={"type": "cas_hmw"})
    assert seeded.status_code == 200
    assert client.get("/scores", params={"limit": -1}).status_code == 422
    assert client.get("/incidents", params={"limit": -1}).status_code == 422
    scores = client.get("/scores", params={"limit": 1})
    incidents = client.get("/incidents", params={"limit": 1})
    assert scores.status_code == 200
    assert incidents.status_code == 200
    assert len(scores.json()) == 1
    assert len(incidents.json()) == 1
    assert scores.json()[0]["vehicle_id"] == seeded.json()["score"]["vehicle_id"]

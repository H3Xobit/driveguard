"""DriveGuard FastAPI service."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from driveguard import __version__
from driveguard.geo import enable_postgis, geo_backend, load_zones
from driveguard.ingestion.consumer import start_background
from driveguard.models import AlertCode, BehaviorTag, HealthResponse
from driveguard.risk.scoring import ALERT_WEIGHT, SPEED_BANDS
from driveguard.settings import get_settings
from driveguard.store import (
    alert_mix,
    get_incident,
    hydrate_from_db,
    inject_behavior,
    list_incidents,
    list_scores,
    persist_enabled,
    restored_from_db,
    seed_demo,
    vehicles_snapshot,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        enable_postgis()
    except Exception:
        pass
    if not hydrate_from_db(probe=True):
        seed_demo()
    mqtt = start_background()
    yield
    if mqtt is not None:
        mqtt.loop_stop()
        mqtt.disconnect()


app = FastAPI(title="DriveGuard", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@app.get("/meta")
def meta() -> dict:
    settings = get_settings()
    return {
        "service": "driveguard-api",
        "version": __version__,
        "behaviors": [b.value for b in BehaviorTag],
        "alert_codes": [a.value for a in AlertCode if a is not AlertCode.none],
        "speed_bands_kmh": [upper if upper != float("inf") else 80 for upper, _ in SPEED_BANDS],
        "alert_weights": {k.value: v for k, v in ALERT_WEIGHT.items() if k is not AlertCode.none},
        "window_size": settings.window_size,
        "risk_warn": settings.risk_warn,
        "risk_fault": settings.risk_fault,
        "offline_llm": bool(settings.dg_offline_llm),
        "geo_backend": geo_backend(),
        "mqtt_consumer": bool(settings.dg_mqtt_consumer),
        "persist": persist_enabled(),
        "restored": restored_from_db(),
        "zones": len(load_zones()),
    }


@app.get("/zones")
def zones() -> list[dict]:
    return [z.model_dump() for z in load_zones()]


@app.get("/vehicles")
def vehicles() -> list[dict]:
    return vehicles_snapshot()


@app.get("/scores")
def scores(limit: int = 40) -> list[dict]:
    return list_scores(limit=limit)


@app.get("/incidents")
def incidents(limit: int = 20) -> list[dict]:
    return [i.model_dump(mode="json") for i in list_incidents(limit=limit)]


@app.get("/incidents/{incident_id}")
def incident_detail(incident_id: UUID) -> dict:
    found = get_incident(incident_id)
    if not found:
        raise HTTPException(404, "incident not found")
    return found.model_dump(mode="json")


@app.get("/stats")
def stats() -> dict:
    return alert_mix()


@app.post("/simulate/inject")
def simulate_inject(type: str = "cas_hmw", vehicle_id: str = "V-1042") -> dict:
    allowed = {b.value for b in BehaviorTag} | {
        a.value for a in AlertCode if a is not AlertCode.none
    }
    if type not in allowed:
        raise HTTPException(400, f"unknown inject type {type}")
    result = inject_behavior(type, vehicle_id=vehicle_id)
    return {"accepted": True, "inject": type, **result}


@app.get("/risk/stream")
async def risk_stream() -> EventSourceResponse:
    async def gen():
        while True:
            payload = {
                "vehicles": vehicles_snapshot(),
                "incidents": [i.model_dump(mode="json") for i in list_incidents(limit=8)],
            }
            yield {"event": "risk", "data": json.dumps(payload, default=str)}
            await asyncio.sleep(1.5)

    return EventSourceResponse(gen())

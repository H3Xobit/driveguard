"""Pydantic models at every I/O boundary."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class Severity(StrEnum):
    info = "info"
    warn = "warn"
    fault = "fault"


class BehaviorTag(StrEnum):
    calm = "calm"
    harsh_braking = "harsh_braking"
    speeding = "speeding"
    weaving = "weaving"
    fatigue_drift = "fatigue_drift"


class AlertCode(StrEnum):
    """iRASTE Nxt CAS / DMS alert codes."""

    none = "none"
    cas_ldw = "cas_ldw"
    cas_hmw = "cas_hmw"
    cas_fcw = "cas_fcw"
    dms_distract = "dms_distract"


class StreamSource(StrEnum):
    cas = "cas"
    casdms = "casdms"


class TelemetrySample(BaseModel):
    time: datetime
    vehicle_id: str
    speed_kmh: float
    accel_ms2: float
    brake: float = Field(ge=0.0, le=1.0)
    steering_var: float = Field(ge=0.0)
    lat: float
    lon: float
    heading_deg: float
    behavior: BehaviorTag = BehaviorTag.calm
    alert: AlertCode = AlertCode.none
    source: StreamSource = StreamSource.cas
    alert_score: float = 0.0


class RiskScore(BaseModel):
    vehicle_id: str
    temporal: float = Field(ge=0.0, le=1.0)
    zone: float = Field(ge=0.0, le=1.0)
    fused: float = Field(ge=0.0, le=1.0)
    baseline_rf: float = Field(ge=0.0, le=1.0)
    compounding: bool = False
    nearest_zone: str | None = None
    severity: Severity
    behavior: BehaviorTag
    alert: AlertCode = AlertCode.none
    alert_score: float = 0.0
    source: StreamSource = StreamSource.cas
    created_at: datetime | None = None


class Incident(BaseModel):
    incident_id: UUID = Field(default_factory=uuid4)
    vehicle_id: str
    severity: Severity
    fused_score: float
    behavior: BehaviorTag
    alert: AlertCode = AlertCode.none
    alert_score: float = 0.0
    source: StreamSource = StreamSource.cas
    summary: str
    contributing: list[str] = Field(default_factory=list)
    recommended_action: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    lat: float
    lon: float
    created_at: datetime | None = None

    @field_validator("summary")
    @classmethod
    def summary_nonempty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("summary must be non-empty")
        return cleaned


class Zone(BaseModel):
    zone_id: str
    name: str
    lat: float
    lon: float
    radius_m: float
    historical_risk: float = Field(ge=0.0, le=1.0)


class HealthResponse(BaseModel):
    status: str
    service: str = "driveguard-api"
    version: str

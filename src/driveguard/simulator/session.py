"""Synthetic driving sessions published over MQTT (and usable in-process)."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections.abc import Iterator
from datetime import UTC, datetime

import numpy as np

from driveguard.geo import zone_risk
from driveguard.models import BehaviorTag, StreamSource, TelemetrySample
from driveguard.risk.scoring import alert_score, behavior_to_alert
from driveguard.settings import get_settings

VEHICLES = ("V-1042", "V-2218", "V-7730")
# Approximate Hyderabad / South India corridor used as a demo map frame.
ORIGIN = (17.385, 78.486)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def step_vehicle(
    rng: np.random.Generator,
    *,
    vehicle_id: str,
    t: int,  # noqa: ARG001
    behavior: BehaviorTag,
    lat: float,
    lon: float,
    heading: float,
    speed: float,
) -> TelemetrySample:
    if behavior is BehaviorTag.speeding:
        speed = 92 + float(rng.normal(6, 3))
        brake = abs(float(rng.normal(0.05, 0.03)))
        accel = float(rng.normal(1.4, 0.4))
        steer = abs(float(rng.normal(2.0, 0.6)))
    elif behavior is BehaviorTag.harsh_braking:
        speed = max(18.0, speed - 18)
        brake = float(rng.uniform(0.72, 0.98))
        accel = float(rng.uniform(-7.5, -4.0))
        steer = abs(float(rng.normal(3.5, 1.0)))
    elif behavior is BehaviorTag.weaving:
        speed = 58 + float(rng.normal(0, 4))
        brake = abs(float(rng.normal(0.2, 0.08)))
        accel = float(rng.normal(0.2, 1.2))
        steer = abs(float(rng.normal(9.5, 1.8)))
        heading += float(rng.normal(0, 14))
    elif behavior is BehaviorTag.fatigue_drift:
        speed = 48 + float(rng.normal(0, 8))
        brake = abs(float(rng.normal(0.12, 0.1)))
        accel = float(rng.normal(-0.4, 1.6))
        steer = abs(float(rng.normal(6.5, 1.4)))
        heading += float(rng.normal(0, 8))
    else:
        speed = 52 + float(rng.normal(0, 3))
        brake = abs(float(rng.normal(0.04, 0.02)))
        accel = float(rng.normal(0.1, 0.4))
        steer = abs(float(rng.normal(1.2, 0.4)))

    heading = heading % 360
    rad = math.radians(heading)
    mps = max(speed, 0.0) / 3.6
    lat += (mps * math.cos(rad)) / 111_000
    lon += (mps * math.sin(rad)) / (111_000 * math.cos(math.radians(lat)))
    alert = behavior_to_alert(behavior.value)
    source = StreamSource.casdms if alert.value.startswith("dms_") else StreamSource.cas
    return TelemetrySample(
        time=_now(),
        vehicle_id=vehicle_id,
        speed_kmh=float(max(0.0, speed)),
        accel_ms2=float(accel),
        brake=float(min(1.0, max(0.0, brake))),
        steering_var=float(max(0.0, steer)),
        lat=float(lat),
        lon=float(lon),
        heading_deg=float(heading),
        behavior=behavior,
        alert=alert,
        source=source,
        alert_score=alert_score(alert, float(max(0.0, speed))),
    )


def iter_session(
    *,
    vehicle_id: str = "V-1042",
    duration: int = 40,
    inject: BehaviorTag | None = None,
    seed: int = 42,
) -> Iterator[TelemetrySample]:
    rng = np.random.default_rng(seed)
    lat, lon = ORIGIN[0] + rng.normal(0, 0.01), ORIGIN[1] + rng.normal(0, 0.01)
    heading = float(rng.uniform(0, 360))
    speed = 50.0
    inject_at = max(8, duration // 3) if inject and inject is not BehaviorTag.calm else -1
    for t in range(duration):
        behavior = inject if (inject and t >= inject_at) else BehaviorTag.calm
        sample = step_vehicle(
            rng,
            vehicle_id=vehicle_id,
            t=t,
            behavior=behavior,
            lat=lat,
            lon=lon,
            heading=heading,
            speed=speed,
        )
        lat, lon, heading, speed = sample.lat, sample.lon, sample.heading_deg, sample.speed_kmh
        yield sample


def synth_windows(n: int = 240, seed: int = 42) -> tuple[list[np.ndarray], list[int]]:
    from driveguard.risk.temporal import window_matrix

    windows: list[np.ndarray] = []
    labels: list[int] = []
    tags = list(BehaviorTag)
    for i in range(n):
        tag = tags[i % len(tags)]
        samples = list(iter_session(duration=36, inject=tag, seed=seed + i))
        zones = [zone_risk(s.lat, s.lon)[0] for s in samples]
        windows.append(window_matrix(samples, zones))
        labels.append(0 if tag is BehaviorTag.calm else 1)
    return windows, labels


def publish_mqtt(samples: list[TelemetrySample]) -> int:
    import paho.mqtt.client as mqtt

    settings = get_settings()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(settings.mqtt_broker, settings.mqtt_port, 60)
    n = 0
    for sample in samples:
        topic = f"driveguard/telemetry/{sample.vehicle_id}"
        payload = sample.model_dump(mode="json")
        client.publish(topic, json.dumps(payload), qos=0)
        n += 1
        time.sleep(0.02)
    client.disconnect()
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="DriveGuard telemetry simulator")
    parser.add_argument("--duration", type=int, default=40)
    parser.add_argument("--inject", default="", help="harsh_braking|speeding|weaving|fatigue_drift")
    parser.add_argument("--vehicle", default="V-1042")
    parser.add_argument("--mqtt", action="store_true")
    args = parser.parse_args()
    inject = BehaviorTag(args.inject) if args.inject else None
    samples = list(iter_session(vehicle_id=args.vehicle, duration=args.duration, inject=inject))
    if args.mqtt:
        print(f"published {publish_mqtt(samples)} samples")
        return
    print(json.dumps([s.model_dump(mode="json") for s in samples[-3:]], indent=2))


if __name__ == "__main__":
    main()

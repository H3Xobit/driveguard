"""MQTT consumer that writes telemetry into the in-process store."""

from __future__ import annotations

from driveguard.models import TelemetrySample
from driveguard.settings import get_settings
from driveguard.store import ingest_sample


def handle_payload(raw: str | bytes) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode()
    sample = TelemetrySample.model_validate_json(raw)
    return ingest_sample(sample)


def start_background():
    """Subscribe in a background thread. Returns None if the broker is down or disabled."""
    settings = get_settings()
    if not settings.dg_mqtt_consumer:
        return None
    try:
        import socket

        import paho.mqtt.client as mqtt

        with socket.create_connection((settings.mqtt_broker, settings.mqtt_port), timeout=0.4):
            pass

        def on_message(_client, _userdata, msg) -> None:
            handle_payload(msg.payload)

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_message = on_message
        client.connect(settings.mqtt_broker, settings.mqtt_port, 60)
        client.subscribe(settings.mqtt_topic)
        client.loop_start()
        return client
    except Exception:
        return None


def main() -> None:
    import paho.mqtt.client as mqtt

    settings = get_settings()

    def on_message(_client, _userdata, msg) -> None:
        handle_payload(msg.payload)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.connect(settings.mqtt_broker, settings.mqtt_port, 60)
    client.subscribe(settings.mqtt_topic)
    client.loop_forever()


if __name__ == "__main__":
    main()

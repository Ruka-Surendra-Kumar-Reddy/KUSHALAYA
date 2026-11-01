"""Print every MQTT message on the lab broker (watch MG7 traffic live)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
import paho.mqtt.client as mqtt

CREDS = Path.home() / "AppData" / "Local" / "LiveWellMqtt" / ".credentials.app"


def main() -> None:
    vals = dotenv_values(CREDS)
    user = vals.get("MQTT_SNIFFER_USER") or "lab_sniffer"
    password = vals.get("MQTT_SNIFFER_PASSWORD") or ""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="livewell-lab-sniffer")
    client.username_pw_set(user, password)

    def on_connect(c, u, f, rc, p=None):
        print(f"connected rc={rc}; subscribed to #")
        c.subscribe("#")

    def on_message(c, u, msg):
        body = msg.payload.decode("utf-8", "replace")
        print(f"{msg.topic}  {body}")

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("127.0.0.1", 1884, 60)
    print("Watching all MQTT topics. Press Ctrl+C to stop.")
    client.loop_forever()


if __name__ == "__main__":
    main()

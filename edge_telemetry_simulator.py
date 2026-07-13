"""
Edge Telemetry Simulator
-------------------------
Simulates a resource-constrained IoT device (e.g. ESP32) publishing
sensor telemetry to AWS IoT Core over MQTT/TLS (mTLS, port 8883).

Install dependency:
    pip install paho-mqtt

Usage:
    python3 edge_telemetry_simulator.py

Before running, fill in the CONFIG section below with:
  - Your AWS IoT Core custom endpoint (Settings -> Device data endpoint)
  - Paths to your device certificate, private key, and Amazon Root CA 1
"""

import json
import time
import random
import ssl
import sys

import paho.mqtt.client as mqtt

# ----------------------------- CONFIG ---------------------------------

AWS_IOT_ENDPOINT = "a26xcsbu1t616r-ats.iot.us-east-1.amazonaws.com"  # no https://, no port
MQTT_PORT = 8883
CLIENT_ID = "UTD_CE_NODE_01"
TOPIC = "device/telemetry"

# Paths to the three files AWS IoT Core gave you when you created the Thing
DEVICE_CERT_PATH = "./certs/device-certificate.pem.crt"
PRIVATE_KEY_PATH = "./certs/private.pem.key"
ROOT_CA_PATH = "./certs/AmazonRootCA1.pem"

PUBLISH_INTERVAL_SECONDS = 5

# ----------------------------- SENSOR MODEL ----------------------------

class TelemetrySensor:
    """
    Generates semi-realistic drifting sensor values instead of pure
    random noise, so the data looks like a real environment rather
    than static jitter.
    """

    def __init__(self):
        self.temperature_c = 24.0
        self.humidity_pct = 50.0
        self.voltage_mv = 3300

    def read(self):
        # Small random walk so values drift naturally over time
        self.temperature_c += random.uniform(-0.3, 0.3)
        self.humidity_pct += random.uniform(-0.5, 0.5)
        self.voltage_mv += random.uniform(-5, 5)

        # Clamp to plausible physical ranges
        self.temperature_c = max(15.0, min(35.0, self.temperature_c))
        self.humidity_pct = max(20.0, min(90.0, self.humidity_pct))
        self.voltage_mv = max(3000, min(3400, self.voltage_mv))

        return {
            "temperature_c": round(self.temperature_c, 2),
            "humidity_pct": round(self.humidity_pct, 2),
            "voltage_mv": round(self.voltage_mv, 1),
        }


def build_payload(sensor: TelemetrySensor) -> dict:
    return {
        "device_id": CLIENT_ID,
        "timestamp": int(time.time()),
        "metrics": sensor.read(),
        "network_firmware": "v1.1.0",
    }


# ----------------------------- MQTT CALLBACKS ---------------------------

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"[MQTT] Connected to {AWS_IOT_ENDPOINT} as {CLIENT_ID}")
    else:
        print(f"[MQTT] Connection failed with reason code: {reason_code}")
        sys.exit(1)


def on_publish(client, userdata, mid, reason_code=None, properties=None):
    print(f"[MQTT] Message {mid} published")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    print(f"[MQTT] Disconnected (reason code: {reason_code})")


# ----------------------------- MAIN ------------------------------------

def main():
    # paho-mqtt 2.x requires an explicit callback API version.
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )

    # mTLS setup: device presents its own cert + key, and validates
    # AWS's server cert against the Amazon Root CA.
    client.tls_set(
        ca_certs=ROOT_CA_PATH,
        certfile=DEVICE_CERT_PATH,
        keyfile=PRIVATE_KEY_PATH,
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLSv1_2,
    )

    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect

    print(f"[MQTT] Connecting to {AWS_IOT_ENDPOINT}:{MQTT_PORT} ...")
    client.connect(AWS_IOT_ENDPOINT, MQTT_PORT, keepalive=60)
    client.loop_start()

    sensor = TelemetrySensor()

    try:
        while True:
            payload = build_payload(sensor)
            message = json.dumps(payload)
            result = client.publish(TOPIC, message, qos=1)
            result.wait_for_publish()
            print(f"[DATA] Sent -> {message}")
            time.sleep(PUBLISH_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\n[MQTT] Shutting down simulator...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
HMAC configuration debug script for NEMO MQTT Plugin.

Prints current HMAC and broker settings (no secrets). Use to verify
configuration is loaded correctly.

Usage (from project root or NEMO project root, with a valid NEMO settings module):
    export DJANGO_SETTINGS_MODULE=settings_dev  # or your NEMO settings module
    python scripts/debug_hmac.py
"""

import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings_dev")

import django
django.setup()

from nemo_mqtt.models import MQTTConfiguration
from nemo_mqtt.utils import sign_payload_hmac, verify_payload_hmac


def main():
    print("NEMO MQTT HMAC Debug")
    print("=" * 50)
    config = MQTTConfiguration.objects.filter(enabled=True).first()
    if not config:
        print("No enabled MQTT configuration found.")
        return
    print(f"Configuration: {config.name}")
    print(f"Broker: {config.broker_host}:{config.broker_port}")
    print(f"HMAC enabled: {getattr(config, 'use_hmac', False)}")
    print("HMAC algorithm: SHA-256 (fixed)")
    print(f"HMAC secret set: {bool(getattr(config, 'hmac_secret_key', None))}")
    if getattr(config, "use_hmac", False) and getattr(config, "hmac_secret_key", None):
        test = '{"hello": "world"}'
        envelope = sign_payload_hmac(test, config.hmac_secret_key)
        valid, payload = verify_payload_hmac(envelope, config.hmac_secret_key)
        print(f"Sign/verify test: {'OK' if valid and payload == test else 'FAIL'}")
    print("Done.")


if __name__ == "__main__":
    main()

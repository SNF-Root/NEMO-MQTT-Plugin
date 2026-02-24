#!/usr/bin/env python3
"""
TLS Debug Script for NEMO MQTT Plugin

This script helps debug TLS connection issues by testing the configuration
and providing detailed debugging information.

Usage (from project root or NEMO project root):
    python scripts/debug_tls.py
"""

import os
import sys
import django

# Add the project root to the Python path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_dev')
django.setup()

from nemo_mqtt.models import MQTTConfiguration
from nemo_mqtt.utils import validate_tls_certificate, test_tls_connection


def main():
    print("🔐 NEMO MQTT TLS Debug Script")
    print("=" * 50)

    # Get MQTT configuration
    config = MQTTConfiguration.objects.filter(enabled=True).first()
    if not config:
        print("❌ No enabled MQTT configuration found")
        return

    print(f"📋 Configuration: {config.name}")
    print(f"📍 Broker: {config.broker_host}:{config.broker_port}")
    print(f"🔐 TLS Enabled: {config.use_tls}")
    print()

    if not config.use_tls:
        print("ℹ️  TLS is not enabled in configuration")
        return

    print("🔍 TLS Configuration Analysis:")
    print(f"   🔐 TLS Version: {config.tls_version}")
    print(f"   🔐 Insecure Mode: {getattr(config, 'insecure', False)}")
    print(f"   🔐 CA Cert Content: {'Provided' if config.ca_cert_content else 'Not provided'}")
    print(f"   🔐 CA Cert Path: {'Provided' if config.ca_cert_path else 'Not provided'}")
    print(f"   🔐 Client Cert Content: {'Provided' if config.client_cert_content else 'Not provided'}")
    print(f"   🔐 Client Key Content: {'Provided' if config.client_key_content else 'Not provided'}")
    print()

    # Validate certificates
    if config.ca_cert_content:
        print("🔐 Validating CA Certificate:")
        ca_validation = validate_tls_certificate(config.ca_cert_content, "CA")
        print(f"   Valid: {ca_validation['valid']}")
        if ca_validation['valid']:
            cert_info = ca_validation['cert_info']
            print(f"   Subject: {cert_info.get('subject', 'N/A')}")
            print(f"   Issuer: {cert_info.get('issuer', 'N/A')}")
            print(f"   Valid Until: {cert_info.get('not_after', 'N/A')}")
        else:
            print(f"   Error: {ca_validation['error']}")
        print()

    if config.client_cert_content:
        print("🔐 Validating Client Certificate:")
        client_validation = validate_tls_certificate(config.client_cert_content, "CLIENT")
        print(f"   Valid: {client_validation['valid']}")
        if client_validation['valid']:
            cert_info = client_validation['cert_info']
            print(f"   Subject: {cert_info.get('subject', 'N/A')}")
            print(f"   Issuer: {cert_info.get('issuer', 'N/A')}")
            print(f"   Valid Until: {cert_info.get('not_after', 'N/A')}")
        else:
            print(f"   Error: {client_validation['error']}")
        print()

    if config.client_key_content:
        print("🔐 Validating Client Key:")
        key_validation = validate_tls_certificate(config.client_key_content, "KEY")
        print(f"   Valid: {key_validation['valid']}")
        if not key_validation['valid']:
            print(f"   Error: {key_validation['error']}")
        print()

    # Test TLS connection
    print("🔐 Testing TLS Connection:")
    tls_test = test_tls_connection(config)
    print(f"   Success: {tls_test['success']}")

    if tls_test['success']:
        print("   ✅ TLS connection test passed!")
        if 'server_cert' in tls_test.get('debug_info', {}):
            server_cert = tls_test['debug_info']['server_cert']
            print("   Server Certificate Info:")
            print(f"     Subject: {server_cert.get('subject', 'N/A')}")
            print(f"     Issuer: {server_cert.get('issuer', 'N/A')}")
            print(f"     Valid Until: {server_cert.get('not_after', 'N/A')}")
    else:
        print(f"   ❌ TLS connection test failed: {tls_test['error']}")
        print("   Steps:")
        for step in tls_test.get('steps', []):
            print(f"     {step}")

    print()
    print("🔍 Common TLS Issues and Solutions:")
    print("   1. Wrong Port: TLS MQTT typically uses port 8883, not 1883")
    print("   2. Certificate Format: Ensure certificates are in PEM format")
    print("   3. Certificate Chain: CA cert must be trusted by the broker")
    print("   4. Hostname Mismatch: Broker hostname must match certificate")
    print("   5. TLS Version: Ensure broker supports the selected TLS version")
    print("   6. Firewall: Check if port 8883 is open")
    print("   7. Broker Config: Ensure broker is configured for TLS")


if __name__ == "__main__":
    main()

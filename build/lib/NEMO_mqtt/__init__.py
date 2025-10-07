"""
NEMO MQTT Plugin

A Django plugin that provides MQTT integration for NEMO tool usage events.
This plugin enables real-time publishing of tool usage data to MQTT brokers.
"""

__version__ = "1.0.0"
__author__ = "SNF-Root"
__email__ = "alexdenton998@gmail.com"

default_app_config = "NEMO_mqtt.apps.MqttPluginConfig"

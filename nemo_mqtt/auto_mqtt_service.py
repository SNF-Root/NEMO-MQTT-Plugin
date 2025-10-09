#!/usr/bin/env python3
"""
Auto MQTT Service for NEMO Plugin
Automatically starts Redis, MQTT broker, and MQTT service when Django starts
"""

import os
import sys
import time
import json
import logging
import threading
import subprocess
import redis
import paho.mqtt.client as mqtt
from datetime import datetime

logger = logging.getLogger(__name__)

class AutoMQTTService:
    """Automatically manages Redis, MQTT broker, and MQTT service for NEMO"""
    
    def __init__(self):
        self.redis_client = None
        self.mqtt_client = None
        self.running = False
        self.redis_process = None
        self.mosquitto_process = None
        
        # Configuration
        self.config = {
            'broker_host': 'localhost',
            'broker_port': 1883,
            'redis_host': 'localhost',
            'redis_port': 6379,
            'redis_db': 1  # Use database 1 for plugin isolation
        }
    
    def start(self):
        """Start all required services"""
        try:
            logger.info("🚀 Starting Auto MQTT Service...")
            
            # Clean up any existing instances first
            self._cleanup_existing_services()
            
            # Start Redis (fresh instance)
            self._start_redis()
            
            # Start MQTT broker (fresh instance)
            self._start_mosquitto()
            
            # Start MQTT service
            self._start_mqtt_service()
            
            logger.info("✅ Auto MQTT Service started successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start Auto MQTT Service: {e}")
            return False
    
    def _cleanup_existing_services(self):
        """Clean up any existing Redis, MQTT broker, and MQTT service instances"""
        try:
            logger.info("🧹 Cleaning up existing services...")
            
            # Only kill Redis if we started it (not system Redis)
            if self.redis_process:
                logger.info("   Stopping Redis instance started by plugin...")
                try:
                    self.redis_process.terminate()
                    self.redis_process.wait(timeout=5)
                except:
                    self.redis_process.kill()
                self.redis_process = None
            else:
                logger.info("   No Redis instance started by plugin to stop")
            
            # Kill all Mosquitto processes
            logger.info("   Stopping existing MQTT broker instances...")
            subprocess.run(['pkill', '-f', 'mosquitto'], capture_output=True)
            subprocess.run(['pkill', '-9', 'mosquitto'], capture_output=True)  # Force kill
            
            # Kill all MQTT service processes
            logger.info("   Stopping existing MQTT service instances...")
            subprocess.run(['pkill', '-f', 'standalone_mqtt_service'], capture_output=True)
            subprocess.run(['pkill', '-f', 'simple_standalone_mqtt'], capture_output=True)
            subprocess.run(['pkill', '-f', 'auto_mqtt_service'], capture_output=True)
            
            # Wait a moment for processes to die
            time.sleep(2)
            
            logger.info("✅ Cleanup completed")
            
        except Exception as e:
            logger.warning(f"⚠️  Cleanup warning: {e}")
    
    def _start_redis(self):
        """Start Redis server or connect to existing one"""
        try:
            # First, check if Redis is already running
            logger.info("🔍 Checking for existing Redis server...")
            try:
                test_client = redis.Redis(host=self.config['redis_host'], port=self.config['redis_port'], db=self.config['redis_db'])
                test_client.ping()
                logger.info("✅ Redis server already running, connecting to existing instance")
                self.redis_client = test_client
                return
            except redis.ConnectionError:
                logger.info("🔍 No existing Redis server found, starting new one...")
            
            # Start Redis server only if none exists
            self.redis_process = subprocess.Popen(
                ['redis-server', '--daemonize', 'yes'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for Redis to start
            for i in range(10):
                try:
                    test_client = redis.Redis(host=self.config['redis_host'], port=self.config['redis_port'], db=self.config['redis_db'])
                    test_client.ping()
                    logger.info("✅ Redis server started successfully")
                    self.redis_client = test_client
                    return
                except redis.ConnectionError:
                    time.sleep(1)
            
            raise Exception("Redis failed to start within 10 seconds")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Redis: {e}")
            raise
    
    def _start_mosquitto(self):
        """Start Mosquitto MQTT broker (fresh instance)"""
        try:
            logger.info("🔍 Starting MQTT broker...")
            
            # Start Mosquitto broker
            self.mosquitto_process = subprocess.Popen(
                ['mosquitto', '-d'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for Mosquitto to start
            for i in range(10):
                try:
                    test_client = mqtt.Client()
                    test_client.connect(self.config['broker_host'], self.config['broker_port'], 60)
                    test_client.disconnect()
                    logger.info("✅ MQTT broker started successfully")
                    return
                except Exception:
                    time.sleep(1)
            
            raise Exception("Mosquitto failed to start within 10 seconds")
            
        except Exception as e:
            logger.error(f"❌ Failed to start MQTT broker: {e}")
            raise
    
    def _start_mqtt_service(self):
        """Start the MQTT service that consumes from Redis and publishes to MQTT"""
        try:
            logger.info("🔍 Starting MQTT service...")
            
            # Start the service in a separate thread
            def run_mqtt_service():
                try:
                    # Import the simple MQTT service
                    from .simple_standalone_mqtt import SimpleStandaloneMQTTService
                    
                    service = SimpleStandaloneMQTTService()
                    service.start()
                    
                    # Keep the service running
                    while service.running:
                        time.sleep(1)
                        
                except Exception as e:
                    logger.error(f"MQTT service error: {e}")
            
            # Start the service in a daemon thread
            mqtt_thread = threading.Thread(target=run_mqtt_service, daemon=True)
            mqtt_thread.start()
            
            logger.info("✅ MQTT service started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start MQTT service: {e}")
            raise
    
    def stop(self):
        """Stop all services"""
        logger.info("🛑 Stopping Auto MQTT Service...")
        
        # Clean up all services
        self._cleanup_existing_services()
        
        logger.info("✅ Auto MQTT Service stopped")

# Global instance
auto_mqtt_service = AutoMQTTService()

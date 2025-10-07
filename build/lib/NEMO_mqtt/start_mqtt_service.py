#!/usr/bin/env python3
"""
Startup script for the external MQTT service
This script starts the standalone MQTT service that maintains a persistent connection.
"""

import os
import sys
import subprocess
import time
import signal
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_redis():
    """Check if Redis is running"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        logger.info("Redis is running")
        return True
    except Exception as e:
        logger.error(f"Redis is not available: {e}")
        return False

def check_mqtt_broker():
    """Check if MQTT broker is running"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 1883))
        sock.close()
        if result == 0:
            logger.info("MQTT broker is running")
            return True
        else:
            logger.error("MQTT broker is not available on port 1883")
            return False
    except Exception as e:
        logger.error(f"Failed to check MQTT broker: {e}")
        return False

def start_mqtt_service():
    """Start the external MQTT service"""
    try:
        # Check dependencies
        if not check_redis():
            logger.error("Redis is required but not running. Please start Redis first.")
            return False
        
        if not check_mqtt_broker():
            logger.error("MQTT broker is required but not running. Please start MQTT broker first.")
            return False
        
        # Start the MQTT service
        logger.info("Starting external MQTT service...")
        
        # Get the path to the MQTT service script
        script_path = os.path.join(os.path.dirname(__file__), 'NEMO', 'plugins', 'mqtt', 'external_mqtt_service.py')
        
        if not os.path.exists(script_path):
            logger.error(f"MQTT service script not found at: {script_path}")
            return False
        
        # Start the service
        process = subprocess.Popen([
            sys.executable, script_path
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        logger.info(f"External MQTT service started with PID: {process.pid}")
        
        # Handle shutdown signals
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, stopping MQTT service...")
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Monitor the process
        try:
            while True:
                return_code = process.poll()
                if return_code is not None:
                    logger.error(f"MQTT service exited with code: {return_code}")
                    return False
                
                # Print output
                output = process.stdout.readline()
                if output:
                    print(output.strip())
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            return True
            
    except Exception as e:
        logger.error(f"Failed to start MQTT service: {e}")
        return False

def main():
    """Main entry point"""
    logger.info("NEMO External MQTT Service Startup Script")
    logger.info("=" * 50)
    
    if start_mqtt_service():
        logger.info("MQTT service stopped gracefully")
    else:
        logger.error("Failed to start or run MQTT service")
        sys.exit(1)

if __name__ == "__main__":
    main()

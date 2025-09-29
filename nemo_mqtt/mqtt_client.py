"""
MQTT Client for publishing NEMO events to MQTT broker.
Handles connection, publishing, and error management.
"""
import json
import logging
import ssl
import threading
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Global lock to prevent multiple MQTT client initializations
_mqtt_lock = threading.Lock()


class MQTTClient:
    """MQTT client for publishing NEMO events"""
    _instance = None
    _initialized = False
    
    def __new__(cls, config=None):
        with _mqtt_lock:
            if cls._instance is None:
                cls._instance = super(MQTTClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config=None):
        # Only initialize once to prevent reconnection loops
        if not self._initialized:
            self.client = None
            self.connected = False
            self.config = config
            self._initialized = True
            self._last_connect_attempt = 0
            self._initialize_client()
    
    def _should_reconnect(self):
        """Check if we should attempt to reconnect (with delay)"""
        import time
        current_time = time.time()
        # Wait at least 5 seconds between connection attempts
        if current_time - self._last_connect_attempt < 5:
            return False
        self._last_connect_attempt = current_time
        return True
    
    def _initialize_client(self):
        """Initialize the MQTT client with configuration"""
        with _mqtt_lock:
            try:
                import paho.mqtt.client as mqtt
                
                # Get configuration from database or settings
                if self.config:
                    # Use database configuration
                    broker_host = self.config.broker_host
                    broker_port = self.config.broker_port
                    username = self.config.username
                    password = self.config.password
                    client_id = self.config.client_id
                    use_tls = self.config.use_tls
                    ca_cert = self.config.ca_cert_path
                    client_cert = self.config.client_cert_path
                    client_key = self.config.client_key_path
                    keepalive = self.config.keepalive
                    clean_session = self.config.clean_session
                else:
                    # Fall back to settings
                    import os
                    import socket
                    broker_host = getattr(settings, 'MQTT_BROKER_HOST', 'localhost')
                    broker_port = getattr(settings, 'MQTT_BROKER_PORT', 1883)
                    username = getattr(settings, 'MQTT_USERNAME', None)
                    password = getattr(settings, 'MQTT_PASSWORD', None)
                    # Create unique client ID using hostname and process ID
                    default_client_id = f"nemo_{socket.gethostname()}_{os.getpid()}"
                    client_id = getattr(settings, 'MQTT_CLIENT_ID', default_client_id)
                    use_tls = getattr(settings, 'MQTT_USE_TLS', False)
                    ca_cert = getattr(settings, 'MQTT_CA_CERT', None)
                    client_cert = getattr(settings, 'MQTT_CLIENT_CERT', None)
                    client_key = getattr(settings, 'MQTT_CLIENT_KEY', None)
                    keepalive = getattr(settings, 'MQTT_KEEPALIVE', 60)
                    clean_session = getattr(settings, 'MQTT_CLEAN_SESSION', True)
                
                # Create MQTT client
                self.client = mqtt.Client(client_id=client_id, clean_session=clean_session)
                
                # Set up authentication
                if username and password:
                    self.client.username_pw_set(username, password)
                
                # Set up TLS if enabled
                if use_tls:
                    context = ssl.create_default_context()
                    if self.config and hasattr(self.config, 'tls_version'):
                        # Set TLS version based on configuration
                        tls_version_map = {
                            'tlsv1': ssl.PROTOCOL_TLSv1,
                            'tlsv1.1': ssl.PROTOCOL_TLSv1_1,
                            'tlsv1.2': ssl.PROTOCOL_TLSv1_2,
                            'tlsv1.3': ssl.PROTOCOL_TLSv1_2  # Python doesn't have TLSv1.3 constant
                        }
                        if self.config.tls_version in tls_version_map:
                            context.protocol = tls_version_map[self.config.tls_version]
                    
                    if ca_cert:
                        context.load_verify_locations(ca_cert)
                    if client_cert and client_key:
                        context.load_cert_chain(client_cert, client_key)
                    
                    # Handle insecure connections
                    if self.config and getattr(self.config, 'insecure', False):
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                    
                    self.client.tls_set_context(context)
                
                # Set up callbacks
                self.client.on_connect = self._on_connect
                self.client.on_disconnect = self._on_disconnect
                self.client.on_publish = self._on_publish
                self.client.on_connect_fail = self._on_connect_fail
                
                # Don't auto-connect to prevent reconnection loops
                # Connection will be handled manually when needed
                logger.info(f"MQTT client initialized (not connected) - Broker: {broker_host}:{broker_port}")
                
            except ImportError:
                logger.error("paho-mqtt library not installed. Install with: pip install paho-mqtt")
            except Exception as e:
                logger.error(f"Failed to initialize MQTT client: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker. Return code: {rc}")
            # Don't auto-reconnect immediately to prevent loops
            # The singleton pattern will handle reconnection when needed
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_connect_fail(self, client, userdata):
        """Callback for when connection fails"""
        logger.error("Failed to connect to MQTT broker")
        self.connected = False
    
    def _on_publish(self, client, userdata, mid):
        """Callback for when a message is published"""
        logger.debug(f"Message published with mid: {mid}")
    
    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> bool:
        """
        Publish a message to the MQTT broker
        
        Args:
            topic: MQTT topic to publish to
            payload: Message payload (string)
            qos: Quality of Service level (0, 1, or 2)
            retain: Whether to retain the message
            
        Returns:
            bool: True if message was queued for publishing, False otherwise
        """
        if not self.client:
            logger.warning("MQTT client not initialized. Message not published.")
            return False
            
        # If not connected, try to connect manually
        if not self.connected:
            if not self.connect_manually():
                logger.warning("MQTT client not connected and connection failed. Message not published.")
                return False
        
        try:
            import paho.mqtt.client as mqtt
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Message queued for publishing to topic: {topic}")
                return True
            else:
                logger.error(f"Failed to queue message for publishing. Error: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing message to topic {topic}: {e}")
            return False
    
    def publish_json(self, topic: str, data: Dict[str, Any], qos: int = 0, retain: bool = False) -> bool:
        """
        Publish a JSON message to the MQTT broker
        
        Args:
            topic: MQTT topic to publish to
            data: Dictionary to serialize as JSON
            qos: Quality of Service level (0, 1, or 2)
            retain: Whether to retain the message
            
        Returns:
            bool: True if message was queued for publishing, False otherwise
        """
        try:
            payload = json.dumps(data, default=str)
            return self.publish(topic, payload, qos, retain)
        except Exception as e:
            logger.error(f"Error serializing JSON for topic {topic}: {e}")
            return False
    
    def connect_manually(self):
        """Manually connect to the MQTT broker"""
        if not self.client or self.connected:
            return True
            
        try:
            if self.config:
                broker_host = self.config.broker_host
                broker_port = self.config.broker_port
                keepalive = self.config.keepalive
            else:
                broker_host = getattr(settings, 'MQTT_BROKER_HOST', 'localhost')
                broker_port = getattr(settings, 'MQTT_BROKER_PORT', 1883)
                keepalive = getattr(settings, 'MQTT_KEEPALIVE', 60)
            
            if self._should_reconnect():
                self.client.connect(broker_host, broker_port, keepalive)
                self.client.loop_start()
                logger.info(f"MQTT client connected to {broker_host}:{broker_port}")
                return True
            else:
                logger.info("Skipping MQTT connection due to recent attempt")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client disconnected")
    
    @classmethod
    def reset_singleton(cls):
        """Reset the singleton instance (useful for testing or reconfiguration)"""
        if cls._instance:
            cls._instance.disconnect()
        cls._instance = None
        cls._initialized = False

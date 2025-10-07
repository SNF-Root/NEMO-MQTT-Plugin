from django.apps import AppConfig
from django.conf import settings
import logging
import threading
import time

logger = logging.getLogger(__name__)


class MqttPluginConfig(AppConfig):
    name = "NEMO_mqtt"
    verbose_name = "MQTT Plugin"
    default_auto_field = "django.db.models.AutoField"
    _initialized = False

    def ready(self):
        """
        Initialize the MQTT plugin when Django starts.
        This sets up signal handlers and MQTT client with a delay.
        """
        # Prevent multiple initializations during development auto-reload
        if self._initialized:
            return
            
        if "migrate" in self.get_migration_args():
            return
            
        # Import signal handlers to register them immediately
        from . import signals
        
        # Import customization to register it immediately
        from . import customization
        
        # Mark as initialized to prevent multiple calls
        self._initialized = True
        
        # Initialize Redis publisher for MQTT events
        try:
            from .utils import get_mqtt_config
            from .signals import signal_handler
            
            config = get_mqtt_config()
            if config and config.enabled:
                logger.info(f"MQTT plugin initialized successfully with config: {config.name}")
                logger.info("MQTT events will be published via Redis to external MQTT service")
            else:
                logger.info("MQTT plugin loaded but no enabled configuration found")
                
        except Exception as e:
            logger.error(f"Failed to initialize MQTT plugin: {e}")
        
        logger.info("MQTT plugin: Signal handlers and customization registered. Events will be published via Redis.")
    
    def get_migration_args(self):
        """Get migration-related command line arguments"""
        import sys
        return [arg for arg in sys.argv if 'migrate' in arg or 'makemigrations' in arg]
    
    def disconnect_mqtt(self):
        """Disconnect MQTT client when app is shutting down"""
        if hasattr(self, 'mqtt_client') and self.mqtt_client:
            self.mqtt_client.disconnect()
            logger.info("MQTT client disconnected during app shutdown")

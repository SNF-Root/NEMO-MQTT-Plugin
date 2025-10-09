"""
Simple pytest configuration for NEMO MQTT Plugin tests
This avoids importing signals that depend on NEMO
"""
import os
import sys
import pytest
import django
from django.conf import settings

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure Django settings for testing
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.test_settings')

# Setup Django
django.setup()

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Setup test database"""
    with django_db_blocker.unblock():
        from django.core.management import call_command
        call_command('migrate', verbosity=0, interactive=False)

@pytest.fixture
def mqtt_config():
    """Create a test MQTT configuration"""
    from NEMO_mqtt.models import MQTTConfiguration
    return MQTTConfiguration.objects.create(
        name='Test Config',
        enabled=True,
        broker_host='localhost',
        broker_port=1883,
        qos_level=1,
        retain_messages=False
    )

@pytest.fixture
def redis_mock():
    """Mock Redis connection for testing"""
    import redis
    from unittest.mock import Mock
    
    mock_redis = Mock(spec=redis.Redis)
    mock_redis.ping.return_value = True
    mock_redis.lpush.return_value = 1
    mock_redis.brpop.return_value = None
    
    return mock_redis

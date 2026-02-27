"""
Tests for NEMO MQTT Plugin views
"""
import pytest
import json
from unittest.mock import Mock, patch
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from nemo_mqtt.models import MQTTConfiguration


class MQTTMonitorViewTest(TestCase):
    """Test MQTT monitor view"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
        
        self.mqtt_config = MQTTConfiguration.objects.create(
            name='Test Config',
            enabled=True,
            broker_host='localhost',
            broker_port=1883
        )
    
    def test_mqtt_monitor_requires_login(self):
        """Test that MQTT monitor requires login"""
        response = self.client.get('/mqtt/monitor/')
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_mqtt_monitor_authenticated(self):
        """Test MQTT monitor with authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/mqtt/monitor/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MQTT Messages')
    
    @patch('nemo_mqtt.views.monitor')
    def test_mqtt_monitor_api(self, mock_monitor):
        """Test MQTT monitor API endpoint"""
        # Mock monitor messages
        mock_monitor.messages = [
            {
                'id': 1,
                'timestamp': '2024-01-15T10:30:00Z',
                'source': 'MQTT',
                'topic': 'nemo/tools/1/start',
                'payload': '{"event": "tool_usage_start"}',
                'qos': 1,
                'retain': False
            }
        ]
        mock_monitor.running = True
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/mqtt/monitor/api/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['messages']), 1)
        self.assertEqual(data['count'], 1)
        self.assertTrue(data['monitoring'])
    
    def test_mqtt_monitor_control_start(self):
        """Test MQTT monitor control start"""
        self.client.login(username='testuser', password='testpass123')
        
        with patch('nemo_mqtt.views.monitor') as mock_monitor:
            mock_monitor.running = False
            response = self.client.post('/mqtt/monitor/control/', {
                'action': 'start'
            })
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertEqual(data['status'], 'started')
            mock_monitor.start_monitoring.assert_called_once()
    
    def test_mqtt_monitor_control_stop(self):
        """Test MQTT monitor control stop"""
        self.client.login(username='testuser', password='testpass123')
        
        with patch('nemo_mqtt.views.monitor') as mock_monitor:
            mock_monitor.running = True
            response = self.client.post('/mqtt/monitor/control/', {
                'action': 'stop'
            })
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertEqual(data['status'], 'stopped')
            mock_monitor.stop_monitoring.assert_called_once()
    
    def test_mqtt_monitor_control_invalid_action(self):
        """Test MQTT monitor control with invalid action"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post('/mqtt/monitor/control/', {
            'action': 'invalid'
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Invalid action')


class MQTTWebMonitorTest(TestCase):
    """Test MQTTWebMonitor class"""
    
    def setUp(self):
        """Set up test data"""
        from nemo_mqtt.views import MQTTWebMonitor
        self.monitor = MQTTWebMonitor()
    
    def test_monitor_initialization(self):
        """Test monitor initialization"""
        self.assertIsNone(self.monitor.redis_client)
        self.assertIsNone(self.monitor.mqtt_client)
        self.assertEqual(len(self.monitor.messages), 0)
        self.assertEqual(self.monitor.max_messages, 100)
        self.assertFalse(self.monitor.running)
        self.assertIsNone(self.monitor.monitor_thread)
    
    @patch('redis.Redis')
    def test_connect_redis_success(self, mock_redis_class):
        """Test successful Redis connection"""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis
        
        result = self.monitor.connect_redis()
        
        self.assertTrue(result)
        self.assertEqual(self.monitor.redis_client, mock_redis)
        mock_redis.ping.assert_called_once()
    
    @patch('redis.Redis')
    def test_connect_redis_failure(self, mock_redis_class):
        """Test failed Redis connection"""
        mock_redis_class.side_effect = Exception("Connection failed")
        
        result = self.monitor.connect_redis()
        
        self.assertFalse(result)
        self.assertIsNone(self.monitor.redis_client)
    
    def test_add_message(self):
        """Test adding message to monitor"""
        message_data = {
            'id': 1,
            'timestamp': '2024-01-15T10:30:00Z',
            'source': 'MQTT',
            'topic': 'nemo/tools/1/start',
            'payload': '{"event": "tool_usage_start"}'
        }
        
        self.monitor.add_message(message_data)
        
        self.assertEqual(len(self.monitor.messages), 1)
        self.assertEqual(self.monitor.messages[0], message_data)
    
    def test_add_message_max_limit(self):
        """Test message limit enforcement"""
        # Add more than max_messages
        for i in range(105):
            message_data = {
                'id': i,
                'timestamp': '2024-01-15T10:30:00Z',
                'source': 'MQTT',
                'topic': f'nemo/tools/{i}/start',
                'payload': f'{{"event": "tool_usage_start", "id": {i}}}'
            }
            self.monitor.add_message(message_data)
        
        # Should only keep the last 100 messages
        self.assertEqual(len(self.monitor.messages), 100)
        self.assertEqual(self.monitor.messages[0]['id'], 5)  # First message should be id 5
        self.assertEqual(self.monitor.messages[-1]['id'], 104)  # Last message should be id 104

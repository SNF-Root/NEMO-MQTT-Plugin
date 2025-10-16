"""
Views for MQTT plugin.
"""
import json
import redis
import paho.mqtt.client as mqtt
import threading
import time
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache

try:
    from NEMO_mqtt.health_monitor import HealthMonitor
except ImportError:
    HealthMonitor = None


class MQTTWebMonitor:
    """Web-based MQTT monitoring for Django views"""
    
    def __init__(self):
        self.redis_client = None
        self.mqtt_client = None
        self.messages = []
        self.max_messages = 100  # Keep last 100 messages
        self.running = False
        self.monitor_thread = None
        
    def connect_redis(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                decode_responses=True
            )
            self.redis_client.ping()
            return True
        except Exception as e:
            print(f"Redis connection failed: {e}")
            return False
    
    def connect_mqtt(self):
        """Connect to MQTT broker using same config as bridge service"""
        try:
            # Import the MQTT configuration utility
            from .utils import get_mqtt_config
            
            # Get the same MQTT configuration as the bridge service
            config = get_mqtt_config()
            if not config or not config.enabled:
                print(f"❌ No enabled MQTT configuration found")
                return False
            
            print(f"🔍 Using MQTT config: {config.name}")
            print(f"   Broker: {config.broker_host}:{config.broker_port}")
            print(f"   TLS: {config.use_tls}")
            print(f"   Config ID: {config.id}")
            print(f"   Updated: {config.updated_at}")
            
            # Create MQTT client with compatibility check
            try:
                # Try newer API first
                self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            except AttributeError:
                # Fall back to older API
                self.mqtt_client = mqtt.Client()
            
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            
            # Configure TLS if enabled
            if config.use_tls:
                import ssl
                context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                
                if config.ca_cert_content:
                    # Write CA cert to temp file
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                        f.write(config.ca_cert_content)
                        ca_cert_path = f.name
                    
                    try:
                        context.load_verify_locations(ca_cert_path)
                        print(f"✅ CA Certificate loaded for TLS verification")
                    finally:
                        # Clean up temp file
                        import os
                        os.unlink(ca_cert_path)
                
                # Set TLS version
                if config.tls_version == 'tlsv1.2':
                    context.minimum_version = ssl.TLSVersion.TLSv1_2
                elif config.tls_version == 'tlsv1.3':
                    context.minimum_version = ssl.TLSVersion.TLSv1_3
                
                # Disable insecure protocols
                context.options |= ssl.OP_NO_SSLv2
                context.options |= ssl.OP_NO_SSLv3
                
                self.mqtt_client.tls_set_context(context)
                print(f"🔐 TLS configured: {config.tls_version}")
            
            # Connect to broker
            self.mqtt_client.connect(config.broker_host, config.broker_port, 60)
            self.mqtt_client.loop_start()
            return True
            
        except Exception as e:
            print(f"❌ MQTT connection failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            print(f"✅ MQTT Monitor connected to broker")
            client.subscribe("nemo/#")
            print(f"📡 MQTT Monitor subscribed to nemo/#")
        else:
            print(f"❌ MQTT Monitor connection failed: {rc}")
    
    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            payload = msg.payload.decode('utf-8')
            message_data = {
                'id': len(self.messages) + 1,
                'timestamp': datetime.now().isoformat(),
                'source': 'MQTT',
                'topic': msg.topic,
                'payload': payload,
                'qos': msg.qos,
                'retain': msg.retain
            }
            
            self.add_message(message_data)
            print(f"📨 MQTT Message: {msg.topic} - {payload[:50]}...")
            
        except Exception as e:
            print(f"❌ Error processing MQTT message: {e}")
    
    def add_message(self, message_data):
        """Add message to the list"""
        self.messages.append(message_data)
        
        # Keep only the last max_messages
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
    
    def start_monitoring(self):
        """Start monitoring in background thread"""
        if self.running:
            print(f"📡 MQTT Monitor already running")
            return
        
        print(f"🚀 Starting MQTT Monitor...")
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print(f"✅ MQTT Monitor thread started")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        if self.mqtt_client:
            self.mqtt_client.disconnect()
    
    def force_reconnect(self):
        """Force reconnection with fresh configuration"""
        print(f"🔄 Forcing MQTT monitor reconnection...")
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        self.mqtt_client = None
        # The monitor loop will automatically reconnect
    
    def clear_config_cache(self):
        """Clear MQTT configuration cache to force fresh load"""
        from django.core.cache import cache
        cache.delete('mqtt_active_config')
        print(f"🧹 MQTT configuration cache cleared")
    
    def _monitor_loop(self):
        """Main monitoring loop with configuration refresh"""
        print(f"🔍 MQTT Monitor loop starting...")
        
        last_config_hash = None
        reconnect_interval = 30  # Check for config changes every 30 seconds
        last_check = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check for configuration changes periodically
                if current_time - last_check > reconnect_interval:
                    try:
                        # Clear cache to ensure we get the latest configuration
                        from django.core.cache import cache
                        cache.delete('mqtt_active_config')
                        
                        from .utils import get_mqtt_config
                        current_config = get_mqtt_config()
                        
                        if current_config:
                            # Create a simple hash of the configuration
                            config_hash = hash(f"{current_config.broker_host}:{current_config.broker_port}:{current_config.use_tls}:{current_config.name}")
                            
                            # If configuration changed, reconnect
                            if last_config_hash is not None and config_hash != last_config_hash:
                                print(f"🔄 Configuration changed, reconnecting MQTT monitor...")
                                print(f"   New config: {current_config.broker_host}:{current_config.broker_port}")
                                if self.mqtt_client:
                                    self.mqtt_client.disconnect()
                                self.mqtt_client = None
                                
                                # Wait a moment before reconnecting
                                time.sleep(2)
                            
                            last_config_hash = config_hash
                            
                    except Exception as e:
                        print(f"⚠️ Error checking configuration: {e}")
                    
                    last_check = current_time
                
                # Connect to MQTT if not connected
                if not self.mqtt_client or not self.mqtt_client.is_connected():
                    if not self.connect_mqtt():
                        print(f"❌ MQTT Monitor failed to connect to broker, retrying in 10s...")
                        time.sleep(10)
                        continue
                    else:
                        print(f"✅ MQTT Monitor connected successfully")
                
                # Small delay to prevent excessive CPU usage
                time.sleep(1)
                
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(5)


# Global monitor instance
monitor = MQTTWebMonitor()


@login_required
def mqtt_monitor(request):
    """Web-based MQTT monitoring dashboard - shows last 10 MQTT messages"""
    import uuid
    view_id = str(uuid.uuid4())[:8]
    
    print(f"\n" + "="*80)
    print(f"🌐 [VIEW-{view_id}] MQTT MONITOR PAGE REQUESTED")
    print(f"="*80)
    print(f"   User: {request.user}")
    print(f"   Monitor running: {monitor.running}")
    print(f"   Monitor messages: {len(monitor.messages)}")
    
    # Always start monitoring when page loads
    if not monitor.running:
        print(f"🚀 [VIEW-{view_id}] Starting MQTT monitor from web interface...")
        monitor.start_monitoring()
        print(f"✅ [VIEW-{view_id}] Monitor started")
    else:
        print(f"✅ [VIEW-{view_id}] Monitor already running")
    
    # Get messages from cache and filter for MQTT only
    print(f"🔍 [VIEW-{view_id}] Retrieving messages from cache...")
    messages = cache.get('mqtt_monitor_messages', [])
    print(f"📊 [VIEW-{view_id}] Cache retrieval:")
    print(f"   Total cached messages: {len(messages)}")
    print(f"   Cache key: mqtt_monitor_messages")
    
    # Fallback to in-memory messages if cache is empty
    if not messages and monitor.messages:
        print(f"🔄 [VIEW-{view_id}] Cache empty, using in-memory messages as fallback")
        messages = monitor.messages
        # Re-store in cache
        cache.set('mqtt_monitor_messages', messages, timeout=3600)
        print(f"✅ [VIEW-{view_id}] Re-stored {len(messages)} messages in cache")
    
    mqtt_messages = [msg for msg in messages if msg.get('source') == 'MQTT']
    print(f"📨 [VIEW-{view_id}] MQTT message filtering:")
    print(f"   Total messages: {len(messages)}")
    print(f"   MQTT messages: {len(mqtt_messages)}")
    
    # Show details of MQTT messages
    for i, msg in enumerate(mqtt_messages[-5:]):  # Show last 5
        print(f"   {i+1}. Topic: {msg.get('topic', 'unknown')} - {msg.get('payload', 'unknown')[:50]}...")
    
    # Prepare response
    response_messages = mqtt_messages[-10:]  # Show last 10 MQTT messages
    print(f"📤 [VIEW-{view_id}] Sending {len(response_messages)} messages to template")
    
    print(f"="*80)
    
    print(f"🔍 [VIEW-{view_id}] Rendering template with context:")
    print(f"   Title: MQTT Messages")
    print(f"   Template: NEMO_mqtt/monitor.html")
    print(f"   User agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
    print(f"   Request method: {request.method}")
    print(f"   Request path: {request.path}")
    
    # Test template rendering
    try:
        from django.template.loader import get_template
        template = get_template('NEMO_mqtt/monitor.html')
        print(f"✅ [VIEW-{view_id}] Template loaded successfully")
        
        # Check if template has JavaScript block (fix source access)
        try:
            template_content = template.template.source
            if 'extra_js' in template_content:
                print(f"✅ [VIEW-{view_id}] Template contains extra_js block")
            else:
                print(f"❌ [VIEW-{view_id}] Template missing extra_js block")
                
            if 'JavaScript' in template_content:
                print(f"✅ [VIEW-{view_id}] Template contains JavaScript")
            else:
                print(f"❌ [VIEW-{view_id}] Template missing JavaScript")
        except Exception as e:
            print(f"⚠️ [VIEW-{view_id}] Could not access template source: {e}")
            print(f"✅ [VIEW-{view_id}] Template object exists and loaded successfully")
            
    except Exception as e:
        print(f"❌ [VIEW-{view_id}] Template loading error: {e}")
    
    print(f"🚀 [VIEW-{view_id}] About to render template...")
    
    # Get MQTT configuration for display
    mqtt_config = None
    try:
        from .utils import get_mqtt_config
        mqtt_config = get_mqtt_config()
    except Exception as e:
        print(f"⚠️ Could not get MQTT config: {e}")
    
    response = render(request, 'NEMO_mqtt/monitor.html', {
        'title': 'MQTT Messages',
        'mqtt_config': mqtt_config,
    })
    
    # Add cache-busting headers to prevent browser caching
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    print(f"✅ [VIEW-{view_id}] Template rendered successfully")
    print(f"   Response status: {response.status_code}")
    print(f"   Response content length: {len(response.content)}")
    print(f"   Cache headers added: no-cache")
    
    # Check if response contains our debug content
    content_str = response.content.decode('utf-8')
    if 'Django Template Debug' in content_str:
        print(f"✅ [VIEW-{view_id}] Response contains Django debug content")
    else:
        print(f"❌ [VIEW-{view_id}] Response missing Django debug content")
        
    if 'Static HTML Test' in content_str:
        print(f"✅ [VIEW-{view_id}] Response contains static HTML test")
    else:
        print(f"❌ [VIEW-{view_id}] Response missing static HTML test")
    
    return response


@login_required
@require_http_methods(["GET"])
def mqtt_monitor_api(request):
    """API endpoint for fetching MQTT messages only"""
    try:
        # Get messages from the monitor
        messages = monitor.messages
        
        # Filter for MQTT messages only
        mqtt_messages = [msg for msg in messages if msg.get('source') == 'MQTT']
        
        response_data = {
            'messages': mqtt_messages,
            'count': len(mqtt_messages),
            'monitoring': monitor.running
        }
        
        print(f"📊 API: {len(mqtt_messages)} MQTT messages")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"❌ API Error: {e}")
        return JsonResponse({'error': str(e), 'messages': [], 'count': 0, 'monitoring': False}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def mqtt_monitor_control(request):
    """Control monitoring (start/stop/reconnect)"""
    action = request.POST.get('action')
    print(f"Monitor control action: {action}, current status: {monitor.running}")
    
    if action == 'start':
        if not monitor.running:
            print("Starting monitor...")
            monitor.start_monitoring()
        return JsonResponse({'status': 'started'})
    elif action == 'stop':
        print("Stopping monitor...")
        monitor.stop_monitoring()
        return JsonResponse({'status': 'stopped'})
    elif action == 'reconnect':
        print("Reconnecting monitor...")
        if monitor.running:
            monitor.force_reconnect()
        else:
            monitor.start_monitoring()
        return JsonResponse({'status': 'reconnected'})
    elif action == 'clear_cache':
        print("Clearing configuration cache...")
        monitor.clear_config_cache()
        if monitor.running:
            monitor.force_reconnect()
        return JsonResponse({'status': 'cache_cleared'})
    else:
        return JsonResponse({'error': 'Invalid action'}, status=400)


@require_http_methods(["GET"])
def health_check(request):
    """
    Health check endpoint for monitoring systems.
    
    Returns comprehensive health status of all MQTT plugin components:
    - Redis connectivity and performance
    - MQTT broker connectivity
    - External MQTT service status
    - Message queue status
    
    Returns HTTP 200 if healthy, 503 if unhealthy.
    """
    if HealthMonitor is None:
        return JsonResponse({
            'status': 'error',
            'error': 'Health monitoring not available',
            'timestamp': time.time()
        }, status=503)
    
    try:
        # Get MQTT configuration for connection details
        from NEMO_mqtt.utils import get_mqtt_config
        config = get_mqtt_config()
        
        if config:
            mqtt_host = config.broker_host
            mqtt_port = config.broker_port
        else:
            mqtt_host = getattr(settings, 'MQTT_BROKER_HOST', 'localhost')
            mqtt_port = getattr(settings, 'MQTT_BROKER_PORT', 1883)
        
        # Initialize health monitor
        monitor = HealthMonitor(
            redis_host=getattr(settings, 'REDIS_HOST', 'localhost'),
            redis_port=getattr(settings, 'REDIS_PORT', 6379),
            redis_db=1,  # Plugin uses DB 1
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port
        )
        
        # Run health checks
        results = monitor.run_health_checks()
        
        # Determine HTTP status code
        status_code = 200 if results['overall'] == 'healthy' else 503
        
        return JsonResponse(results, status=status_code)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'timestamp': time.time()
        }, status=503)

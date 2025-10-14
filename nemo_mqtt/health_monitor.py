"""
Health Monitoring System for NEMO MQTT Plugin

Provides comprehensive health checks for all components:
- Redis connectivity and performance
- MQTT broker connectivity
- Redis-MQTT Bridge service status
- End-to-end message flow
"""
import time
import logging
from typing import Dict, List, Callable, Optional
import redis
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Monitors health of all MQTT plugin components.
    
    Usage:
        monitor = HealthMonitor()
        
        # Add alert callback
        monitor.add_alert_callback(send_email_alert)
        
        # Run health checks
        results = monitor.run_health_checks()
        
        # Check overall health
        if results['overall'] == 'unhealthy':
            print("System is unhealthy!")
    """
    
    def __init__(
        self,
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        redis_db: int = 1,
        mqtt_host: str = 'localhost',
        mqtt_port: int = 1883
    ):
        """
        Initialize health monitor.
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
            mqtt_host: MQTT broker host
            mqtt_port: MQTT broker port
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        
        self.health_status = {}
        self.alert_callbacks: List[Callable] = []
        
        # Health check functions
        self.checks = {
            'redis': self._check_redis,
            'mqtt_broker': self._check_mqtt_broker,
            'mqtt_service': self._check_mqtt_service,
            'message_queue': self._check_message_queue
        }
    
    def _check_redis(self) -> Dict:
        """
        Check Redis connectivity and performance.
        
        Returns:
            dict: Health status with latency and connection info
        """
        try:
            start = time.time()
            redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            redis_client.ping()
            latency = (time.time() - start) * 1000  # Convert to ms
            
            # Get Redis info
            info = redis_client.info()
            
            # Check memory usage
            used_memory = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            memory_warning = False
            
            if max_memory > 0:
                memory_percent = (used_memory / max_memory) * 100
                memory_warning = memory_percent > 80
            
            result = {
                'status': 'healthy',
                'latency_ms': round(latency, 2),
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_mb': round(used_memory / (1024 * 1024), 2),
                'uptime_seconds': info.get('uptime_in_seconds', 0),
                'warning': memory_warning
            }
            
            if latency > 100:
                result['warning'] = True
                result['warning_message'] = f"High latency: {latency:.1f}ms"
            
            return result
            
        except redis.ConnectionError as e:
            return {
                'status': 'unhealthy',
                'error': f"Connection failed: {e}"
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_mqtt_broker(self) -> Dict:
        """
        Check MQTT broker connectivity.
        
        Returns:
            dict: Health status with latency and connection info
        """
        try:
            start = time.time()
            test_client = mqtt.Client(client_id="health_check")
            
            # Set connection timeout
            connected = False
            
            def on_connect(client, userdata, flags, rc):
                nonlocal connected
                connected = (rc == 0)
            
            test_client.on_connect = on_connect
            test_client.connect(self.mqtt_host, self.mqtt_port, 5)
            test_client.loop_start()
            
            # Wait for connection
            timeout = 5
            elapsed = 0
            while not connected and elapsed < timeout:
                time.sleep(0.1)
                elapsed += 0.1
            
            test_client.loop_stop()
            test_client.disconnect()
            
            latency = (time.time() - start) * 1000  # Convert to ms
            
            if not connected:
                return {
                    'status': 'unhealthy',
                    'error': 'Failed to connect within timeout'
                }
            
            result = {
                'status': 'healthy',
                'latency_ms': round(latency, 2)
            }
            
            if latency > 1000:
                result['warning'] = True
                result['warning_message'] = f"High latency: {latency:.1f}ms"
            
            return result
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_mqtt_service(self) -> Dict:
        """
        Check if Redis-MQTT Bridge service is running.
        
        Returns:
            dict: Health status with process info
        """
        try:
            import psutil
            
            # Look for Redis-MQTT Bridge service processes
            service_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'redis_mqtt_bridge' in cmdline:
                        service_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'uptime_seconds': int(time.time() - proc.info['create_time'])
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not service_processes:
                return {
                    'status': 'unhealthy',
                    'error': 'Redis-MQTT Bridge process not found'
                }
            
            return {
                'status': 'healthy',
                'processes': service_processes,
                'process_count': len(service_processes)
            }
            
        except ImportError:
            return {
                'status': 'unknown',
                'error': 'psutil not installed - cannot check process status'
            }
        except Exception as e:
            return {
                'status': 'unknown',
                'error': str(e)
            }
    
    def _check_message_queue(self) -> Dict:
        """
        Check Redis message queue status.
        
        Returns:
            dict: Health status with queue length and stats
        """
        try:
            redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Check queue length
            queue_length = redis_client.llen('NEMO_mqtt_events')
            
            # Warning if queue is too long
            warning = queue_length > 1000
            
            result = {
                'status': 'healthy',
                'queue_length': queue_length,
                'warning': warning
            }
            
            if warning:
                result['warning_message'] = (
                    f"Message queue is large ({queue_length} messages). "
                    "MQTT service may not be consuming fast enough."
                )
            
            return result
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def run_health_checks(self) -> Dict:
        """
        Run all health checks and return comprehensive status.
        
        Returns:
            dict: Complete health status for all components
        """
        results = {}
        
        # Run all health checks
        for name, check_func in self.checks.items():
            try:
                results[name] = check_func()
            except Exception as e:
                logger.error(f"Health check '{name}' failed: {e}")
                results[name] = {
                    'status': 'error',
                    'error': f"Check failed: {e}"
                }
        
        # Calculate overall health
        overall = self._calculate_overall_health(results)
        
        results['overall'] = overall
        results['timestamp'] = time.time()
        
        # Store results
        self.health_status = results
        
        # Trigger alerts if unhealthy
        if overall == 'unhealthy':
            self._trigger_alerts(results)
        
        return results
    
    def _calculate_overall_health(self, results: Dict) -> str:
        """
        Calculate overall system health from component results.
        
        Args:
            results: Dict of component health results
        
        Returns:
            str: 'healthy', 'warning', or 'unhealthy'
        """
        # Check for any unhealthy components
        if any(r.get('status') == 'unhealthy' for r in results.values()):
            return 'unhealthy'
        
        # Check for warnings
        if any(r.get('warning') for r in results.values()):
            return 'warning'
        
        # Check for unknown status
        if any(r.get('status') == 'unknown' for r in results.values()):
            return 'warning'
        
        return 'healthy'
    
    def _trigger_alerts(self, results: Dict):
        """
        Trigger all registered alert callbacks.
        
        Args:
            results: Health check results to include in alert
        """
        for callback in self.alert_callbacks:
            try:
                callback(results)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def add_alert_callback(self, callback: Callable):
        """
        Add callback to be triggered on unhealthy status.
        
        Args:
            callback: Function that takes health results dict as parameter
        """
        self.alert_callbacks.append(callback)
    
    def get_status(self) -> Dict:
        """
        Get last health status without running new checks.
        
        Returns:
            dict: Last health check results
        """
        return self.health_status
    
    def is_healthy(self) -> bool:
        """
        Quick check if system is healthy.
        
        Returns:
            bool: True if overall status is healthy
        """
        return self.health_status.get('overall') == 'healthy'


def example_alert_callback(results: Dict):
    """
    Example alert callback function.
    
    This would typically send an email, Slack message, PagerDuty alert, etc.
    
    Args:
        results: Health check results
    """
    logger.error(f"ALERT: System is unhealthy!")
    logger.error(f"Health status: {results}")
    
    # Example: Send email
    # send_email(
    #     to="admin@example.com",
    #     subject="NEMO MQTT Plugin Health Alert",
    #     body=f"System is unhealthy:\n{json.dumps(results, indent=2)}"
    # )


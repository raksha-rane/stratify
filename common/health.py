"""
Health check utilities for monitoring service status and dependencies.

This module provides comprehensive health checking functionality including:
- Database connectivity tests
- Redis connectivity tests
- External API availability checks
- Disk space monitoring
- System metrics collection (CPU, memory, uptime)
"""

import os
import psutil
import time
from datetime import datetime
from typing import Dict, Any, Optional
import requests
from sqlalchemy import create_engine, text
from .logger import get_logger

logger = get_logger(__name__)


class HealthCheck:
    """
    Comprehensive health check system for microservices.
    
    Performs various health checks including database connectivity,
    cache availability, external service checks, and system metrics.
    """
    
    def __init__(self, 
                 db_url: Optional[str] = None,
                 redis_url: Optional[str] = None,
                 service_name: str = "unknown"):
        """
        Initialize health checker.
        
        Args:
            db_url: Database connection URL (SQLAlchemy format)
            redis_url: Redis connection URL
            service_name: Name of the service being monitored
        """
        self.db_url = db_url or os.getenv('DATABASE_URL')
        self.redis_url = redis_url
        self.service_name = service_name
        self.start_time = time.time()
        
        logger.debug("HealthCheck initialized", extra={
            'service': service_name,
            'has_db': bool(self.db_url),
            'has_redis': bool(self.redis_url)
        })
    
    def check_database(self) -> Dict[str, Any]:
        """
        Test PostgreSQL database connection.
        
        Attempts to connect and execute a simple query to verify
        database is accessible and responsive.
        
        Returns:
            Dictionary with status, response_time, and optional error
        """
        if not self.db_url:
            return {
                'status': 'skipped',
                'message': 'Database URL not configured',
                'healthy': True  # Not required
            }
        
        start_time = time.time()
        
        try:
            # Create engine with short timeout
            engine = create_engine(
                self.db_url,
                pool_pre_ping=True,
                connect_args={'connect_timeout': 5}
            )
            
            # Test connection with simple query
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            logger.debug("Database health check passed", extra={
                'response_time_ms': response_time
            })
            
            engine.dispose()
            
            return {
                'status': 'healthy',
                'healthy': True,
                'response_time_ms': round(response_time, 2),
                'message': 'Database connection successful'
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            logger.error("Database health check failed", extra={
                'error': str(e),
                'response_time_ms': response_time
            })
            
            return {
                'status': 'unhealthy',
                'healthy': False,
                'response_time_ms': round(response_time, 2),
                'error': str(e),
                'message': 'Database connection failed'
            }
    
    def check_redis(self) -> Dict[str, Any]:
        """
        Test Redis connection.
        
        Attempts to connect to Redis and execute a PING command.
        
        Returns:
            Dictionary with status, response_time, and optional error
        """
        if not self.redis_url:
            return {
                'status': 'skipped',
                'message': 'Redis URL not configured',
                'healthy': True  # Not required for current implementation
            }
        
        start_time = time.time()
        
        try:
            import redis
            
            # Parse Redis URL
            r = redis.from_url(self.redis_url, socket_connect_timeout=5)
            
            # Test connection
            r.ping()
            
            response_time = (time.time() - start_time) * 1000
            
            logger.debug("Redis health check passed", extra={
                'response_time_ms': response_time
            })
            
            return {
                'status': 'healthy',
                'healthy': True,
                'response_time_ms': round(response_time, 2),
                'message': 'Redis connection successful'
            }
            
        except ImportError:
            return {
                'status': 'skipped',
                'message': 'Redis library not installed',
                'healthy': True
            }
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            logger.error("Redis health check failed", extra={
                'error': str(e),
                'response_time_ms': response_time
            })
            
            return {
                'status': 'unhealthy',
                'healthy': False,
                'response_time_ms': round(response_time, 2),
                'error': str(e),
                'message': 'Redis connection failed'
            }
    
    def check_external_api(self, test_symbol: str = "AAPL") -> Dict[str, Any]:
        """
        Test yfinance API availability.
        
        Attempts to fetch a small amount of data from Yahoo Finance
        to verify the external API is accessible.
        
        Args:
            test_symbol: Stock symbol to test with
            
        Returns:
            Dictionary with status, response_time, and optional error
        """
        start_time = time.time()
        
        try:
            import yfinance as yf
            
            # Quick test fetch with minimal data
            ticker = yf.Ticker(test_symbol)
            info = ticker.info
            
            # Verify we got some data back
            if not info or 'symbol' not in info:
                raise ValueError("No data returned from yfinance")
            
            response_time = (time.time() - start_time) * 1000
            
            logger.debug("External API health check passed", extra={
                'response_time_ms': response_time,
                'test_symbol': test_symbol
            })
            
            return {
                'status': 'healthy',
                'healthy': True,
                'response_time_ms': round(response_time, 2),
                'message': f'Successfully fetched data for {test_symbol}',
                'api': 'yfinance'
            }
            
        except ImportError:
            return {
                'status': 'skipped',
                'message': 'yfinance library not installed',
                'healthy': True
            }
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            logger.error("External API health check failed", extra={
                'error': str(e),
                'response_time_ms': response_time,
                'test_symbol': test_symbol
            })
            
            return {
                'status': 'unhealthy',
                'healthy': False,
                'response_time_ms': round(response_time, 2),
                'error': str(e),
                'message': 'External API connection failed',
                'api': 'yfinance'
            }
    
    def check_disk_space(self, min_free_gb: float = 1.0) -> Dict[str, Any]:
        """
        Check available disk space.
        
        Verifies that sufficient disk space is available for operation.
        
        Args:
            min_free_gb: Minimum free space in GB required
            
        Returns:
            Dictionary with status, disk usage stats, and health status
        """
        try:
            # Get disk usage for root partition
            disk = psutil.disk_usage('/')
            
            free_gb = disk.free / (1024 ** 3)  # Convert bytes to GB
            total_gb = disk.total / (1024 ** 3)
            used_gb = disk.used / (1024 ** 3)
            percent_used = disk.percent
            
            is_healthy = free_gb >= min_free_gb
            
            status_msg = 'healthy' if is_healthy else 'unhealthy'
            
            logger.debug("Disk space check completed", extra={
                'free_gb': free_gb,
                'total_gb': total_gb,
                'percent_used': percent_used,
                'healthy': is_healthy
            })
            
            return {
                'status': status_msg,
                'healthy': is_healthy,
                'free_gb': round(free_gb, 2),
                'used_gb': round(used_gb, 2),
                'total_gb': round(total_gb, 2),
                'percent_used': round(percent_used, 1),
                'threshold_gb': min_free_gb,
                'message': f'{free_gb:.2f}GB free of {total_gb:.2f}GB'
            }
            
        except Exception as e:
            logger.error("Disk space check failed", extra={
                'error': str(e)
            })
            
            return {
                'status': 'error',
                'healthy': False,
                'error': str(e),
                'message': 'Failed to check disk space'
            }
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Collect system performance metrics.
        
        Gathers information about CPU usage, memory usage, and service uptime.
        
        Returns:
            Dictionary with CPU, memory, and uptime metrics
        """
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_total_mb = memory.total / (1024 ** 2)
            memory_used_mb = memory.used / (1024 ** 2)
            memory_percent = memory.percent
            
            # Process-specific metrics
            process = psutil.Process(os.getpid())
            process_memory_mb = process.memory_info().rss / (1024 ** 2)
            process_cpu_percent = process.cpu_percent(interval=0.1)
            
            # Uptime
            uptime_seconds = time.time() - self.start_time
            
            metrics = {
                'cpu': {
                    'percent': round(cpu_percent, 1),
                    'count': cpu_count,
                    'process_percent': round(process_cpu_percent, 1)
                },
                'memory': {
                    'total_mb': round(memory_total_mb, 0),
                    'used_mb': round(memory_used_mb, 0),
                    'percent': round(memory_percent, 1),
                    'process_mb': round(process_memory_mb, 1)
                },
                'uptime': {
                    'seconds': round(uptime_seconds, 0),
                    'formatted': self._format_uptime(uptime_seconds)
                },
                'timestamp': datetime.now().isoformat()
            }
            
            logger.debug("System metrics collected", extra=metrics)
            
            return metrics
            
        except Exception as e:
            logger.error("Failed to collect system metrics", extra={
                'error': str(e)
            })
            
            return {
                'error': str(e),
                'message': 'Failed to collect system metrics'
            }
    
    def _format_uptime(self, seconds: float) -> str:
        """
        Format uptime in human-readable format.
        
        Args:
            seconds: Uptime in seconds
            
        Returns:
            Formatted string like "2h 15m 30s"
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    def run_all_checks(self, 
                       check_db: bool = True,
                       check_redis: bool = False,
                       check_api: bool = False,
                       check_disk: bool = True) -> Dict[str, Any]:
        """
        Run all configured health checks.
        
        Args:
            check_db: Whether to check database
            check_redis: Whether to check Redis
            check_api: Whether to check external API
            check_disk: Whether to check disk space
            
        Returns:
            Dictionary with all check results and overall health status
        """
        logger.info("Running health checks", extra={
            'service': self.service_name,
            'check_db': check_db,
            'check_redis': check_redis,
            'check_api': check_api,
            'check_disk': check_disk
        })
        
        checks = {}
        
        if check_db:
            checks['database'] = self.check_database()
        
        if check_redis:
            checks['redis'] = self.check_redis()
        
        if check_api:
            checks['external_api'] = self.check_external_api()
        
        if check_disk:
            checks['disk_space'] = self.check_disk_space()
        
        # Determine overall health
        all_healthy = all(
            check.get('healthy', True) 
            for check in checks.values()
        )
        
        overall_status = 'healthy' if all_healthy else 'unhealthy'
        
        result = {
            'status': overall_status,
            'service': self.service_name,
            'timestamp': datetime.now().isoformat(),
            'checks': checks,
            'metrics': self.get_system_metrics()
        }
        
        logger.info("Health checks completed", extra={
            'service': self.service_name,
            'status': overall_status,
            'checks_run': len(checks)
        })
        
        return result

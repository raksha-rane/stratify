"""
Prometheus metrics for monitoring service performance and health.

Provides standardized metrics collection across all services:
- Request counters with labels (service, endpoint, status)
- Duration histograms for performance monitoring
- Active connection gauges
- Strategy-specific metrics
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from functools import wraps
import time
from typing import Callable, Optional
from .logger import get_logger

logger = get_logger(__name__)

# ============================================================================
# REQUEST METRICS
# ============================================================================

api_requests_total = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['service', 'endpoint', 'method', 'status']
)

request_duration_seconds = Histogram(
    'request_duration_seconds',
    'HTTP request duration in seconds',
    ['service', 'endpoint', 'method'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

request_size_bytes = Histogram(
    'request_size_bytes',
    'HTTP request size in bytes',
    ['service', 'endpoint'],
    buckets=(100, 1000, 10000, 100000, 1000000)
)

response_size_bytes = Histogram(
    'response_size_bytes',
    'HTTP response size in bytes',
    ['service', 'endpoint'],
    buckets=(100, 1000, 10000, 100000, 1000000, 10000000)
)

# ============================================================================
# STRATEGY ENGINE METRICS
# ============================================================================

strategy_execution_duration = Histogram(
    'strategy_execution_duration_seconds',
    'Strategy execution time in seconds',
    ['strategy', 'ticker'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

backtest_trades_total = Counter(
    'backtest_trades_total',
    'Total number of trades in backtest',
    ['strategy', 'ticker']
)

backtest_return_percent = Histogram(
    'backtest_return_percent',
    'Backtest return percentage',
    ['strategy', 'ticker'],
    buckets=[-50, -20, -10, -5, 0, 5, 10, 20, 50, 100, 200]
)

backtest_sharpe_ratio = Gauge(
    'backtest_sharpe_ratio',
    'Backtest Sharpe ratio',
    ['strategy', 'ticker']
)

# ============================================================================
# DATA SERVICE METRICS
# ============================================================================

data_fetch_total = Counter(
    'data_fetch_total',
    'Total data fetch operations',
    ['service', 'ticker', 'status']
)

data_validation_failures = Counter(
    'data_validation_failures',
    'Total data validation failures',
    ['ticker', 'failure_type']
)

data_quality_score = Gauge(
    'data_quality_score',
    'Data quality score (0-100)',
    ['ticker']
)

# ============================================================================
# DATABASE METRICS
# ============================================================================

db_operations_total = Counter(
    'db_operations_total',
    'Total database operations',
    ['service', 'operation', 'status']
)

db_operation_duration_seconds = Histogram(
    'db_operation_duration_seconds',
    'Database operation duration in seconds',
    ['service', 'operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

db_connection_pool_size = Gauge(
    'db_connection_pool_size',
    'Database connection pool size',
    ['service']
)

# ============================================================================
# RATE LIMITING METRICS
# ============================================================================

rate_limit_hits_total = Counter(
    'rate_limit_hits_total',
    'Total rate limit hits (requests blocked)',
    ['service', 'resource', 'identifier']
)

rate_limit_tokens_remaining = Gauge(
    'rate_limit_tokens_remaining',
    'Remaining rate limit tokens',
    ['service', 'resource', 'identifier']
)

# ============================================================================
# QUEUE METRICS
# ============================================================================

queue_size = Gauge(
    'queue_size',
    'Number of items in queue',
    ['service', 'queue_name', 'status']
)

queue_processing_duration_seconds = Histogram(
    'queue_processing_duration_seconds',
    'Queue item processing duration',
    ['service', 'queue_name'],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0)
)

# ============================================================================
# SYSTEM METRICS
# ============================================================================

active_connections = Gauge(
    'active_connections',
    'Number of active connections',
    ['service']
)

service_info = Info(
    'service_info',
    'Service information'
)

service_up = Gauge(
    'service_up',
    'Service availability (1 = up, 0 = down)',
    ['service']
)

# ============================================================================
# ERROR METRICS
# ============================================================================

errors_total = Counter(
    'errors_total',
    'Total number of errors',
    ['service', 'error_type', 'endpoint']
)

exceptions_total = Counter(
    'exceptions_total',
    'Total number of exceptions',
    ['service', 'exception_type']
)

# ============================================================================
# HEALTH CHECK METRICS
# ============================================================================

health_check_duration_seconds = Histogram(
    'health_check_duration_seconds',
    'Health check duration in seconds',
    ['service', 'check_type'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0)
)

health_check_status = Gauge(
    'health_check_status',
    'Health check status (1 = healthy, 0 = unhealthy)',
    ['service', 'check_type']
)

# ============================================================================
# DECORATOR FUNCTIONS
# ============================================================================

def track_request_metrics(service_name: str, endpoint: str):
    """
    Decorator to automatically track request metrics.
    
    Usage:
        @app.route('/data/fetch')
        @track_request_metrics('data-service', '/data/fetch')
        def fetch_data():
            return {...}
    
    Args:
        service_name: Name of the service
        endpoint: Endpoint path
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args, **kwargs):
            start_time = time.time()
            status = '200'
            method = 'POST'  # Default, can be enhanced
            
            try:
                # Execute the function
                result = f(*args, **kwargs)
                
                # Extract status from response if possible
                if hasattr(result, 'status_code'):
                    status = str(result.status_code)
                elif isinstance(result, tuple) and len(result) > 1:
                    status = str(result[1])
                
                return result
                
            except Exception as e:
                status = '500'
                errors_total.labels(
                    service=service_name,
                    error_type=type(e).__name__,
                    endpoint=endpoint
                ).inc()
                raise
                
            finally:
                # Record metrics
                duration = time.time() - start_time
                
                api_requests_total.labels(
                    service=service_name,
                    endpoint=endpoint,
                    method=method,
                    status=status
                ).inc()
                
                request_duration_seconds.labels(
                    service=service_name,
                    endpoint=endpoint,
                    method=method
                ).observe(duration)
                
                logger.debug("Request metrics recorded", extra={
                    'service': service_name,
                    'endpoint': endpoint,
                    'duration': duration,
                    'status': status
                })
        
        return wrapped
    return decorator


def track_strategy_execution(strategy_name: str, ticker: str):
    """
    Decorator to track strategy execution metrics.
    
    Usage:
        @track_strategy_execution('sma', 'AAPL')
        def run_strategy():
            return {...}
    
    Args:
        strategy_name: Name of the strategy
        ticker: Ticker symbol
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = f(*args, **kwargs)
                
                # Record trade counts and performance if available
                if isinstance(result, dict):
                    if 'total_trades' in result:
                        backtest_trades_total.labels(
                            strategy=strategy_name,
                            ticker=ticker,
                            signal='all'
                        ).inc(result['total_trades'])
                    
                    if 'total_return' in result:
                        backtest_return_percent.labels(
                            strategy=strategy_name,
                            ticker=ticker
                        ).set(result['total_return'])
                    
                    if 'sharpe_ratio' in result:
                        backtest_sharpe_ratio.labels(
                            strategy=strategy_name,
                            ticker=ticker
                        ).set(result['sharpe_ratio'])
                
                return result
                
            finally:
                duration = time.time() - start_time
                strategy_execution_duration.labels(
                    strategy=strategy_name,
                    ticker=ticker
                ).observe(duration)
        
        return wrapped
    return decorator


def track_db_operation(service_name: str, operation: str):
    """
    Decorator to track database operation metrics.
    
    Usage:
        @track_db_operation('data-service', 'insert')
        def save_to_db():
            return {...}
    
    Args:
        service_name: Name of the service
        operation: Type of database operation (insert, update, select, delete)
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            
            try:
                result = f(*args, **kwargs)
                return result
                
            except Exception as e:
                status = 'failure'
                raise
                
            finally:
                duration = time.time() - start_time
                
                db_operations_total.labels(
                    service=service_name,
                    operation=operation,
                    status=status
                ).inc()
                
                db_operation_duration_seconds.labels(
                    service=service_name,
                    operation=operation
                ).observe(duration)
        
        return wrapped
    return decorator


def initialize_service_metrics(service_name: str, version: str = "1.0.0"):
    """
    Initialize service-level metrics.
    
    Args:
        service_name: Name of the service
        version: Service version
    """
    service_info.info({
        'service': service_name,
        'version': version
    })
    
    service_up.labels(service=service_name).set(1)
    active_connections.labels(service=service_name).set(0)
    
    logger.info("Service metrics initialized", extra={
        'service': service_name,
        'version': version
    })


def record_health_check(service_name: str, check_type: str, 
                       duration: float, is_healthy: bool):
    """
    Record health check metrics.
    
    Args:
        service_name: Name of the service
        check_type: Type of health check (database, redis, etc.)
        duration: Check duration in seconds
        is_healthy: Whether the check passed
    """
    health_check_duration_seconds.labels(
        service=service_name,
        check_type=check_type
    ).observe(duration)
    
    health_check_status.labels(
        service=service_name,
        check_type=check_type
    ).set(1 if is_healthy else 0)

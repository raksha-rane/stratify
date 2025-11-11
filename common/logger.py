"""
Structured Logging Module for AQUA
Provides JSON and pretty-formatted logging with rotation
"""
import logging
import logging.handlers
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from functools import wraps
import threading

# Thread-local storage for correlation IDs
_thread_local = threading.local()


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging
    Outputs logs in JSON format for production environments
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'service': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(_thread_local, 'correlation_id', None),
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add additional record attributes
        log_data.update({
            'file': record.filename,
            'function': record.funcName,
            'line': record.lineno,
        })
        
        # Remove None values
        log_data = {k: v for k, v in log_data.items() if v is not None}
        
        return json.dumps(log_data)


class PrettyFormatter(logging.Formatter):
    """
    Pretty formatter for development environments
    Color-coded, human-readable format
    """
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and pretty layout"""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Build the log message
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        level = f"{color}{record.levelname:8}{reset}"
        service = f"{record.name:30}"
        message = record.getMessage()
        
        # Add correlation ID if present
        correlation_id = getattr(_thread_local, 'correlation_id', None)
        correlation_str = f" [{correlation_id[:8]}]" if correlation_id else ""
        
        log_line = f"{timestamp} | {level} | {service}{correlation_str} | {message}"
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields') and record.extra_fields:
            extras = ', '.join(f"{k}={v}" for k, v in record.extra_fields.items())
            log_line += f" | {extras}"
        
        # Add exception info if present
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"
        
        return log_line


class StructuredLogger(logging.Logger):
    """
    Enhanced logger that supports structured logging with extra fields
    """
    
    def _log_with_extras(self, level, msg, *args, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Internal method to log with extra fields"""
        if extra:
            # Create a custom LogRecord with extra fields
            if 'extra' not in kwargs:
                kwargs['extra'] = {}
            kwargs['extra']['extra_fields'] = extra
        
        super()._log(level, msg, args, **kwargs)
    
    def debug(self, msg, *args, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Log debug message with optional extra fields"""
        self._log_with_extras(logging.DEBUG, msg, *args, extra=extra, **kwargs)
    
    def info(self, msg, *args, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Log info message with optional extra fields"""
        self._log_with_extras(logging.INFO, msg, *args, extra=extra, **kwargs)
    
    def warning(self, msg, *args, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Log warning message with optional extra fields"""
        self._log_with_extras(logging.WARNING, msg, *args, extra=extra, **kwargs)
    
    def error(self, msg, *args, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Log error message with optional extra fields"""
        self._log_with_extras(logging.ERROR, msg, *args, extra=extra, **kwargs)
    
    def critical(self, msg, *args, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Log critical message with optional extra fields"""
        self._log_with_extras(logging.CRITICAL, msg, *args, extra=extra, **kwargs)


def get_logger(name: str, service_name: Optional[str] = None) -> StructuredLogger:
    """
    Get or create a structured logger instance
    
    Args:
        name: Logger name (typically __name__)
        service_name: Service name override (defaults to LOG_SERVICE_NAME env var)
    
    Returns:
        StructuredLogger instance configured based on environment
    
    Example:
        logger = get_logger(__name__)
        logger.info("Processing request", extra={"user_id": 123, "action": "login"})
    """
    # Set the custom logger class
    logging.setLoggerClass(StructuredLogger)
    
    # Get or create logger
    logger = logging.getLogger(service_name or os.getenv('LOG_SERVICE_NAME', name))
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Get configuration from environment
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_format = os.getenv('LOG_FORMAT', 'pretty').lower()  # 'json' or 'pretty'
    log_file = os.getenv('LOG_FILE', None)
    
    # Set log level
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Choose formatter based on format preference
    if log_format == 'json':
        formatter = JSONFormatter()
    else:
        formatter = PrettyFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logger.level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation if log file is specified
    if log_file:
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Rotating file handler (10MB max, keep 5 files)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logger.level)
        
        # Always use JSON format for file logs
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
    
    return logger


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set correlation ID for the current thread/request
    
    Args:
        correlation_id: Custom correlation ID (generates UUID if None)
    
    Returns:
        The correlation ID that was set
    
    Example:
        correlation_id = set_correlation_id()
        logger.info("Request started")
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    
    _thread_local.correlation_id = correlation_id
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID for this thread/request
    
    Returns:
        Current correlation ID or None
    """
    return getattr(_thread_local, 'correlation_id', None)


def clear_correlation_id():
    """Clear the correlation ID for the current thread/request"""
    if hasattr(_thread_local, 'correlation_id'):
        delattr(_thread_local, 'correlation_id')


def log_execution_time(logger: Optional[StructuredLogger] = None):
    """
    Decorator to log function execution time
    
    Args:
        logger: Logger instance (creates one if None)
    
    Example:
        @log_execution_time()
        def expensive_function():
            # Do work
            pass
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.info(
                    f"Function {func.__name__} completed",
                    extra={
                        'function': func.__name__,
                        'duration_ms': round(duration_ms, 2),
                        'status': 'success'
                    }
                )
                
                return result
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.error(
                    f"Function {func.__name__} failed",
                    extra={
                        'function': func.__name__,
                        'duration_ms': round(duration_ms, 2),
                        'status': 'failed',
                        'error': str(e)
                    },
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator


def mask_sensitive_data(data: Dict[str, Any], sensitive_keys: list = None) -> Dict[str, Any]:
    """
    Mask sensitive data in dictionaries before logging
    
    Args:
        data: Dictionary containing data to log
        sensitive_keys: List of keys to mask (defaults to common sensitive fields)
    
    Returns:
        Dictionary with sensitive values masked
    
    Example:
        safe_data = mask_sensitive_data({"password": "secret123", "user": "john"})
        logger.info("User data", extra=safe_data)
    """
    if sensitive_keys is None:
        sensitive_keys = ['password', 'token', 'secret', 'api_key', 'authorization']
    
    masked_data = data.copy()
    
    for key in masked_data:
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            masked_data[key] = '***MASKED***'
    
    return masked_data


# Example usage for testing
if __name__ == '__main__':
    # Test pretty format
    os.environ['LOG_FORMAT'] = 'pretty'
    logger = get_logger('test-service')
    
    set_correlation_id()
    logger.info("Application started")
    logger.debug("Debug information", extra={'config': 'loaded', 'modules': 5})
    logger.warning("This is a warning")
    logger.error("An error occurred", extra={'error_code': 500})
    
    # Test JSON format
    os.environ['LOG_FORMAT'] = 'json'
    logger2 = get_logger('test-service-json')
    
    logger2.info("JSON formatted log", extra={'user_id': 123, 'action': 'login'})
    
    # Test execution time decorator
    @log_execution_time(logger)
    def slow_function():
        import time
        time.sleep(0.1)
        return "Done"
    
    slow_function()

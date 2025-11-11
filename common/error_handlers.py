"""
Error Handling Middleware for AQUA

This module provides:
- Custom exception classes for different error types
- Decorators for automatic error handling in Flask routes
- Retry logic with exponential backoff
- Consistent error response formatting
- Integration with structured logging

Usage:
    from common.error_handlers import handle_errors, retry_on_failure, ValidationError
    
    @app.route('/api/endpoint')
    @handle_errors
    @retry_on_failure(max_retries=3)
    def my_endpoint():
        if invalid:
            raise ValidationError("Invalid input")
        return {"result": "success"}
"""

import time
import functools
from typing import Optional, Dict, Any, Callable
from flask import jsonify, request
from werkzeug.exceptions import HTTPException


# ============================================================================
# CUSTOM EXCEPTION CLASSES
# ============================================================================

class APIError(Exception):
    """Base exception class for all API errors"""
    status_code = 500
    error_type = "API_ERROR"
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response"""
        error_dict = {
            'error': self.error_type,
            'message': self.message,
            'status_code': self.status_code
        }
        if self.details:
            error_dict['details'] = self.details
        return error_dict


class ValidationError(APIError):
    """Raised when input validation fails"""
    status_code = 400
    error_type = "VALIDATION_ERROR"
    
    def __init__(self, message: str, field: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=details)
        if field:
            self.details['field'] = field


class DataFetchError(APIError):
    """Raised when external data fetching fails"""
    status_code = 503
    error_type = "DATA_FETCH_ERROR"
    
    def __init__(self, message: str, source: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=details)
        if source:
            self.details['source'] = source


class DatabaseError(APIError):
    """Raised when database operations fail"""
    status_code = 500
    error_type = "DATABASE_ERROR"
    
    def __init__(self, message: str, operation: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=details)
        if operation:
            self.details['operation'] = operation


class RateLimitError(APIError):
    """Raised when rate limits are exceeded"""
    status_code = 429
    error_type = "RATE_LIMIT_ERROR"
    
    def __init__(self, message: str = "Rate limit exceeded", 
                 retry_after: Optional[int] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=details)
        if retry_after:
            self.details['retry_after_seconds'] = retry_after


class ResourceNotFoundError(APIError):
    """Raised when requested resource is not found"""
    status_code = 404
    error_type = "RESOURCE_NOT_FOUND"


class StrategyError(APIError):
    """Raised when strategy execution fails"""
    status_code = 500
    error_type = "STRATEGY_ERROR"
    
    def __init__(self, message: str, strategy_name: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=details)
        if strategy_name:
            self.details['strategy'] = strategy_name


class ServiceUnavailableError(APIError):
    """Raised when a dependent service is unavailable"""
    status_code = 503
    error_type = "SERVICE_UNAVAILABLE"
    
    def __init__(self, message: str, service_name: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=details)
        if service_name:
            self.details['service'] = service_name


# ============================================================================
# ERROR HANDLER DECORATOR
# ============================================================================

def handle_errors(f: Callable) -> Callable:
    """
    Decorator that handles exceptions and returns proper JSON error responses.
    
    Integrates with structured logging to track errors with correlation IDs.
    
    Usage:
        @app.route('/api/endpoint')
        @handle_errors
        def my_endpoint():
            # Your code here
            pass
    
    Returns:
        JSON response with error details and appropriate HTTP status code
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Get logger if available
            logger = None
            try:
                from common.logger import get_logger, get_correlation_id
                logger = get_logger(__name__)
                correlation_id = get_correlation_id()
            except ImportError:
                correlation_id = None
            
            # Execute the wrapped function
            return f(*args, **kwargs)
            
        except ValidationError as e:
            # Log validation errors at warning level
            if logger:
                logger.warning(
                    f"Validation error: {e.message}",
                    extra={
                        'error_type': e.error_type,
                        'status_code': e.status_code,
                        'details': e.details,
                        'endpoint': request.endpoint,
                        'method': request.method,
                        'correlation_id': correlation_id
                    }
                )
            
            response = e.to_dict()
            if correlation_id:
                response['correlation_id'] = correlation_id
            return jsonify(response), e.status_code
            
        except ResourceNotFoundError as e:
            # Log not found errors at info level
            if logger:
                logger.info(
                    f"Resource not found: {e.message}",
                    extra={
                        'error_type': e.error_type,
                        'status_code': e.status_code,
                        'endpoint': request.endpoint,
                        'correlation_id': correlation_id
                    }
                )
            
            response = e.to_dict()
            if correlation_id:
                response['correlation_id'] = correlation_id
            return jsonify(response), e.status_code
            
        except (DataFetchError, ServiceUnavailableError, RateLimitError) as e:
            # Log external service errors at error level
            if logger:
                logger.error(
                    f"{e.error_type}: {e.message}",
                    extra={
                        'error_type': e.error_type,
                        'status_code': e.status_code,
                        'details': e.details,
                        'endpoint': request.endpoint,
                        'correlation_id': correlation_id
                    },
                    exc_info=True
                )
            
            response = e.to_dict()
            if correlation_id:
                response['correlation_id'] = correlation_id
            return jsonify(response), e.status_code
            
        except APIError as e:
            # Log all other API errors at error level
            if logger:
                logger.error(
                    f"{e.error_type}: {e.message}",
                    extra={
                        'error_type': e.error_type,
                        'status_code': e.status_code,
                        'details': e.details,
                        'endpoint': request.endpoint,
                        'correlation_id': correlation_id
                    },
                    exc_info=True
                )
            
            response = e.to_dict()
            if correlation_id:
                response['correlation_id'] = correlation_id
            return jsonify(response), e.status_code
            
        except HTTPException as e:
            # Handle Flask/Werkzeug HTTP exceptions
            if logger:
                logger.warning(
                    f"HTTP error: {e.description}",
                    extra={
                        'status_code': e.code,
                        'endpoint': request.endpoint,
                        'correlation_id': correlation_id
                    }
                )
            
            response = {
                'error': 'HTTP_ERROR',
                'message': e.description,
                'status_code': e.code
            }
            if correlation_id:
                response['correlation_id'] = correlation_id
            return jsonify(response), e.code
            
        except Exception as e:
            # Catch-all for unexpected errors
            if logger:
                logger.critical(
                    f"Unexpected error: {str(e)}",
                    extra={
                        'error_type': type(e).__name__,
                        'endpoint': request.endpoint,
                        'method': request.method,
                        'correlation_id': correlation_id
                    },
                    exc_info=True
                )
            
            # Don't expose internal error details in production
            response = {
                'error': 'INTERNAL_SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'status_code': 500
            }
            if correlation_id:
                response['correlation_id'] = correlation_id
            
            return jsonify(response), 500
    
    return decorated_function


# ============================================================================
# RETRY DECORATOR
# ============================================================================

def retry_on_failure(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    exceptions: tuple = (DataFetchError, ServiceUnavailableError, ConnectionError),
    on_retry: Optional[Callable] = None
) -> Callable:
    """
    Decorator that retries a function on failure with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_factor: Multiplier for exponential backoff (default: 2.0)
        exceptions: Tuple of exceptions to catch and retry (default: DataFetchError, ServiceUnavailableError)
        on_retry: Optional callback function called before each retry
    
    Usage:
        @retry_on_failure(max_retries=3, backoff_factor=2)
        def fetch_data():
            # Code that might fail
            pass
    
    Backoff pattern: wait = backoff_factor ^ attempt
    - Attempt 1: wait 2^0 = 1 second
    - Attempt 2: wait 2^1 = 2 seconds
    - Attempt 3: wait 2^2 = 4 seconds
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            logger = None
            try:
                from common.logger import get_logger
                logger = get_logger(__name__)
            except ImportError:
                pass
            
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    # First attempt (attempt=0) happens immediately
                    if attempt > 0:
                        # Calculate wait time with exponential backoff
                        wait_time = backoff_factor ** (attempt - 1)
                        
                        if logger:
                            logger.warning(
                                f"Retrying {f.__name__} after failure",
                                extra={
                                    'attempt': attempt,
                                    'max_retries': max_retries,
                                    'wait_seconds': wait_time,
                                    'function': f.__name__
                                }
                            )
                        
                        # Call retry callback if provided
                        if on_retry:
                            on_retry(attempt, wait_time, last_exception)
                        
                        # Wait before retry
                        time.sleep(wait_time)
                    
                    # Execute the function
                    result = f(*args, **kwargs)
                    
                    # Log successful retry
                    if attempt > 0 and logger:
                        logger.info(
                            f"Function {f.__name__} succeeded after retry",
                            extra={
                                'attempt': attempt,
                                'function': f.__name__
                            }
                        )
                    
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        # Max retries reached, log and re-raise
                        if logger:
                            logger.error(
                                f"Function {f.__name__} failed after {max_retries} retries",
                                extra={
                                    'function': f.__name__,
                                    'max_retries': max_retries,
                                    'error': str(e)
                                },
                                exc_info=True
                            )
                        raise
                    
                    # Will retry on next iteration
                    continue
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def register_error_handlers(app):
    """
    Register global error handlers for Flask application.
    
    Usage:
        from common.error_handlers import register_error_handlers
        
        app = Flask(__name__)
        register_error_handlers(app)
    """
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        """Handle all custom API errors"""
        response = error.to_dict()
        try:
            from common.logger import get_correlation_id
            correlation_id = get_correlation_id()
            if correlation_id:
                response['correlation_id'] = correlation_id
        except ImportError:
            pass
        return jsonify(response), error.status_code
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 errors"""
        response = {
            'error': 'NOT_FOUND',
            'message': 'The requested resource was not found',
            'status_code': 404
        }
        try:
            from common.logger import get_correlation_id
            correlation_id = get_correlation_id()
            if correlation_id:
                response['correlation_id'] = correlation_id
        except ImportError:
            pass
        return jsonify(response), 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        """Handle 405 errors"""
        response = {
            'error': 'METHOD_NOT_ALLOWED',
            'message': 'The method is not allowed for the requested URL',
            'status_code': 405
        }
        try:
            from common.logger import get_correlation_id
            correlation_id = get_correlation_id()
            if correlation_id:
                response['correlation_id'] = correlation_id
        except ImportError:
            pass
        return jsonify(response), 405
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle 500 errors"""
        try:
            from common.logger import get_logger, get_correlation_id
            logger = get_logger(__name__)
            logger.critical(
                "Internal server error",
                extra={'error': str(error)},
                exc_info=True
            )
        except ImportError:
            pass
        
        response = {
            'error': 'INTERNAL_SERVER_ERROR',
            'message': 'An unexpected error occurred',
            'status_code': 500
        }
        try:
            from common.logger import get_correlation_id
            correlation_id = get_correlation_id()
            if correlation_id:
                response['correlation_id'] = correlation_id
        except ImportError:
            pass
        return jsonify(response), 500


def validate_request_data(data: Dict[str, Any], required_fields: list, 
                         optional_fields: Optional[list] = None) -> None:
    """
    Validate request data has required fields.
    
    Args:
        data: Request data dictionary
        required_fields: List of required field names
        optional_fields: List of optional field names (for documentation)
    
    Raises:
        ValidationError: If validation fails
    
    Usage:
        validate_request_data(
            request.json,
            required_fields=['ticker', 'start_date', 'end_date'],
            optional_fields=['interval']
        )
    """
    if not data:
        raise ValidationError("Request body is required")
    
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            details={'missing_fields': missing_fields}
        )
    
    # Check for empty values
    empty_fields = [
        field for field in required_fields 
        if field in data and (data[field] is None or data[field] == '')
    ]
    
    if empty_fields:
        raise ValidationError(
            f"Fields cannot be empty: {', '.join(empty_fields)}",
            details={'empty_fields': empty_fields}
        )

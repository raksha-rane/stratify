"""
Rate limiting utilities using Redis for distributed rate limiting.

Implements token bucket algorithm for API rate limiting with:
- Configurable requests per period
- Burst capacity handling
- Automatic token refill
- Distributed coordination via Redis
- Decorator pattern for easy application
"""

import time
import redis
from functools import wraps
from typing import Optional, Tuple
from flask import request, jsonify
from .logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter using Redis for distributed rate limiting.
    
    The token bucket algorithm allows for burst traffic while maintaining
    average rate limits over time.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Initialize rate limiter with Redis connection.
        
        Args:
            redis_url: Redis connection URL
        """
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            self.enabled = True
            logger.info("Rate limiter initialized with Redis", extra={
                'redis_url': redis_url.split('@')[-1]  # Hide password
            })
        except Exception as e:
            logger.warning("Redis not available, rate limiting disabled", extra={
                'error': str(e)
            })
            self.redis_client = None
            self.enabled = False
    
    def _get_bucket_key(self, resource: str, identifier: str) -> str:
        """
        Generate Redis key for rate limit bucket.
        
        Args:
            resource: Resource being rate limited (e.g., 'yfinance')
            identifier: Unique identifier (e.g., IP address, user ID)
            
        Returns:
            Redis key string
        """
        return f"rate_limit:{resource}:{identifier}"
    
    def _get_tokens_key(self, resource: str, identifier: str) -> str:
        """Get Redis key for token count."""
        return f"{self._get_bucket_key(resource, identifier)}:tokens"
    
    def _get_timestamp_key(self, resource: str, identifier: str) -> str:
        """Get Redis key for last update timestamp."""
        return f"{self._get_bucket_key(resource, identifier)}:timestamp"
    
    def check_rate_limit(self, 
                        resource: str,
                        identifier: str,
                        calls: int = 48,
                        period: int = 60,
                        burst: int = 10) -> Tuple[bool, dict]:
        """
        Check if request is within rate limit using token bucket algorithm.
        
        Args:
            resource: Resource being accessed (e.g., 'yfinance')
            identifier: Unique identifier for the requester
            calls: Number of allowed calls per period
            period: Time period in seconds
            burst: Maximum burst capacity (tokens in bucket)
            
        Returns:
            Tuple of (allowed: bool, info: dict)
            info contains: tokens_remaining, reset_time, retry_after
        """
        if not self.enabled:
            # Rate limiting disabled, allow all requests
            return True, {
                'tokens_remaining': burst,
                'reset_time': 0,
                'retry_after': 0,
                'rate_limiting': 'disabled'
            }
        
        try:
            tokens_key = self._get_tokens_key(resource, identifier)
            timestamp_key = self._get_timestamp_key(resource, identifier)
            
            current_time = time.time()
            
            # Get current state from Redis
            pipe = self.redis_client.pipeline()
            pipe.get(tokens_key)
            pipe.get(timestamp_key)
            results = pipe.execute()
            
            current_tokens = float(results[0]) if results[0] else burst
            last_update = float(results[1]) if results[1] else current_time
            
            # Calculate token refill rate (tokens per second)
            refill_rate = calls / period
            
            # Calculate time elapsed and tokens to add
            time_elapsed = current_time - last_update
            tokens_to_add = time_elapsed * refill_rate
            
            # Refill tokens (capped at burst capacity)
            current_tokens = min(burst, current_tokens + tokens_to_add)
            
            # Check if we have at least 1 token available
            if current_tokens >= 1.0:
                # Consume 1 token
                current_tokens -= 1.0
                allowed = True
                
                # Update Redis with new state
                pipe = self.redis_client.pipeline()
                pipe.set(tokens_key, current_tokens, ex=period * 2)
                pipe.set(timestamp_key, current_time, ex=period * 2)
                pipe.execute()
                
                logger.debug("Rate limit check passed", extra={
                    'resource': resource,
                    'identifier': identifier,
                    'tokens_remaining': current_tokens
                })
                
                return True, {
                    'tokens_remaining': int(current_tokens),
                    'reset_time': int(current_time + (burst - current_tokens) / refill_rate),
                    'retry_after': 0
                }
            else:
                # Not enough tokens, rate limit exceeded
                tokens_needed = 1.0 - current_tokens
                retry_after = tokens_needed / refill_rate
                
                logger.warning("Rate limit exceeded", extra={
                    'resource': resource,
                    'identifier': identifier,
                    'tokens_remaining': 0,
                    'retry_after': retry_after
                })
                
                return False, {
                    'tokens_remaining': 0,
                    'reset_time': int(current_time + retry_after),
                    'retry_after': int(retry_after) + 1
                }
                
        except Exception as e:
            logger.error("Rate limit check failed", extra={
                'error': str(e),
                'resource': resource
            }, exc_info=True)
            # On error, allow request (fail open)
            return True, {
                'tokens_remaining': burst,
                'reset_time': 0,
                'retry_after': 0,
                'error': 'rate_limit_check_failed'
            }
    
    def time_until_reset(self, resource: str, identifier: str, 
                        calls: int = 48, period: int = 60, 
                        burst: int = 10) -> int:
        """
        Get seconds until rate limit resets to full capacity.
        
        Args:
            resource: Resource being rate limited
            identifier: Unique identifier
            calls: Allowed calls per period
            period: Time period in seconds
            burst: Burst capacity
            
        Returns:
            Seconds until reset (0 if already at capacity)
        """
        if not self.enabled:
            return 0
        
        try:
            tokens_key = self._get_tokens_key(resource, identifier)
            timestamp_key = self._get_timestamp_key(resource, identifier)
            
            current_time = time.time()
            
            pipe = self.redis_client.pipeline()
            pipe.get(tokens_key)
            pipe.get(timestamp_key)
            results = pipe.execute()
            
            current_tokens = float(results[0]) if results[0] else burst
            last_update = float(results[1]) if results[1] else current_time
            
            if current_tokens >= burst:
                return 0
            
            refill_rate = calls / period
            time_elapsed = current_time - last_update
            tokens_to_add = time_elapsed * refill_rate
            current_tokens = min(burst, current_tokens + tokens_to_add)
            
            if current_tokens >= burst:
                return 0
            
            tokens_needed = burst - current_tokens
            time_needed = tokens_needed / refill_rate
            
            return int(time_needed) + 1
            
        except Exception as e:
            logger.error("Failed to calculate reset time", extra={
                'error': str(e)
            })
            return 0
    
    def reset_limit(self, resource: str, identifier: str) -> bool:
        """
        Reset rate limit for a specific resource and identifier.
        
        Args:
            resource: Resource to reset
            identifier: Identifier to reset
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            tokens_key = self._get_tokens_key(resource, identifier)
            timestamp_key = self._get_timestamp_key(resource, identifier)
            
            pipe = self.redis_client.pipeline()
            pipe.delete(tokens_key)
            pipe.delete(timestamp_key)
            pipe.execute()
            
            logger.info("Rate limit reset", extra={
                'resource': resource,
                'identifier': identifier
            })
            
            return True
            
        except Exception as e:
            logger.error("Failed to reset rate limit", extra={
                'error': str(e),
                'resource': resource
            })
            return False
    
    def get_stats(self, resource: str, identifier: str, 
                  calls: int = 48, period: int = 60, 
                  burst: int = 10) -> dict:
        """
        Get current rate limit statistics.
        
        Args:
            resource: Resource being monitored
            identifier: Identifier to check
            calls: Calls per period
            period: Period in seconds
            burst: Burst capacity
            
        Returns:
            Dictionary with rate limit stats
        """
        if not self.enabled:
            return {
                'enabled': False,
                'tokens_remaining': burst,
                'capacity': burst,
                'reset_time': 0
            }
        
        try:
            tokens_key = self._get_tokens_key(resource, identifier)
            timestamp_key = self._get_timestamp_key(resource, identifier)
            
            current_time = time.time()
            
            pipe = self.redis_client.pipeline()
            pipe.get(tokens_key)
            pipe.get(timestamp_key)
            results = pipe.execute()
            
            current_tokens = float(results[0]) if results[0] else burst
            last_update = float(results[1]) if results[1] else current_time
            
            refill_rate = calls / period
            time_elapsed = current_time - last_update
            tokens_to_add = time_elapsed * refill_rate
            current_tokens = min(burst, current_tokens + tokens_to_add)
            
            return {
                'enabled': True,
                'tokens_remaining': int(current_tokens),
                'capacity': burst,
                'calls_per_period': calls,
                'period_seconds': period,
                'reset_time': self.time_until_reset(resource, identifier, calls, period, burst),
                'refill_rate': round(refill_rate, 3)
            }
            
        except Exception as e:
            logger.error("Failed to get rate limit stats", extra={
                'error': str(e)
            })
            return {
                'enabled': False,
                'error': str(e)
            }


def rate_limit(calls: int = 48, 
               period: int = 60, 
               resource: str = "api",
               burst: Optional[int] = None,
               identifier_fn=None):
    """
    Decorator for rate limiting Flask routes.
    
    Usage:
        @app.route('/data/fetch')
        @rate_limit(calls=48, period=60, resource='yfinance')
        def fetch_data():
            return {...}
    
    Args:
        calls: Number of allowed calls per period
        period: Time period in seconds
        resource: Resource being rate limited
        burst: Burst capacity (defaults to calls/5)
        identifier_fn: Function to get identifier (defaults to IP address)
    
    Returns:
        Decorated function with rate limiting
    """
    if burst is None:
        burst = max(10, calls // 5)  # Default burst is 20% of calls or 10, whichever is larger
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get rate limiter from app config or create new one
            from flask import current_app
            
            if not hasattr(current_app, 'rate_limiter'):
                redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
                current_app.rate_limiter = RateLimiter(redis_url)
            
            limiter = current_app.rate_limiter
            
            # Get identifier (IP address by default)
            if identifier_fn:
                identifier = identifier_fn()
            else:
                identifier = request.remote_addr or 'unknown'
            
            # Check rate limit
            allowed, info = limiter.check_rate_limit(
                resource=resource,
                identifier=identifier,
                calls=calls,
                period=period,
                burst=burst
            )
            
            if not allowed:
                logger.warning("Rate limit exceeded for request", extra={
                    'resource': resource,
                    'identifier': identifier,
                    'retry_after': info['retry_after']
                })
                
                response = jsonify({
                    'error': 'RATE_LIMIT_EXCEEDED',
                    'message': f'Rate limit exceeded for {resource}',
                    'retry_after': info['retry_after'],
                    'limit': {
                        'calls': calls,
                        'period': period,
                        'burst': burst
                    }
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(info['retry_after'])
                response.headers['X-RateLimit-Limit'] = str(calls)
                response.headers['X-RateLimit-Remaining'] = str(info['tokens_remaining'])
                response.headers['X-RateLimit-Reset'] = str(info['reset_time'])
                return response
            
            # Add rate limit headers to response
            response = f(*args, **kwargs)
            
            # Add headers if response is a Flask response object
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(calls)
                response.headers['X-RateLimit-Remaining'] = str(info['tokens_remaining'])
                response.headers['X-RateLimit-Reset'] = str(info['reset_time'])
            
            return response
        
        return decorated_function
    return decorator

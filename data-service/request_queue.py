"""
Redis-backed request queue for data service.

Implements priority queue for processing data requests with:
- Priority levels (live > historical requests)
- Automatic retry on failure (configurable attempts)
- Sequential processing with rate limiting
- Job status tracking and monitoring
"""

import json
import time
import redis
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import IntEnum
from dataclasses import dataclass, asdict
import threading
from common.logger import get_logger

logger = get_logger(__name__)


class RequestPriority(IntEnum):
    """Priority levels for requests (higher number = higher priority)."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    LIVE = 4  # Real-time/live data requests


class RequestStatus(IntEnum):
    """Status of queued requests."""
    PENDING = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4
    RETRYING = 5


@dataclass
class QueuedRequest:
    """Represents a queued data request."""
    id: str
    ticker: str
    start_date: str
    end_date: str
    priority: int
    status: int
    attempts: int
    max_attempts: int
    created_at: float
    updated_at: float
    error: Optional[str] = None
    result: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'QueuedRequest':
        """Create from dictionary."""
        return cls(**data)


class RequestQueue:
    """
    Redis-backed priority queue for data requests.
    
    Features:
    - Priority-based processing
    - Automatic retry with exponential backoff
    - Job status tracking
    - Failed job management
    """
    
    def __init__(self, 
                 redis_url: str = "redis://localhost:6379/0",
                 max_retries: int = 3,
                 retry_delay: int = 5):
        """
        Initialize request queue.
        
        Args:
            redis_url: Redis connection URL
            max_retries: Maximum retry attempts for failed requests
            retry_delay: Base delay in seconds between retries
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
            logger.info("Request queue initialized with Redis", extra={
                'redis_url': redis_url.split('@')[-1],
                'max_retries': max_retries
            })
        except Exception as e:
            logger.error("Failed to initialize request queue", extra={
                'error': str(e)
            })
            self.redis_client = None
            self.enabled = False
            raise
        
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.processing_lock = threading.Lock()
        
        # Redis key patterns
        self.queue_key = "request_queue:pending"
        self.processing_key = "request_queue:processing"
        self.completed_key = "request_queue:completed"
        self.failed_key = "request_queue:failed"
        self.request_prefix = "request:"
    
    def enqueue(self,
                ticker: str,
                start_date: str,
                end_date: str,
                priority: RequestPriority = RequestPriority.NORMAL,
                request_id: Optional[str] = None) -> str:
        """
        Add a request to the queue.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date for data
            end_date: End date for data
            priority: Request priority level
            request_id: Optional custom request ID
            
        Returns:
            Request ID
        """
        if not self.enabled:
            raise RuntimeError("Request queue not available")
        
        if request_id is None:
            request_id = f"{ticker}_{int(time.time() * 1000)}"
        
        request = QueuedRequest(
            id=request_id,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            priority=priority,
            status=RequestStatus.PENDING,
            attempts=0,
            max_attempts=self.max_retries,
            created_at=time.time(),
            updated_at=time.time()
        )
        
        try:
            # Store request data
            request_key = f"{self.request_prefix}{request_id}"
            self.redis_client.set(
                request_key,
                json.dumps(request.to_dict()),
                ex=86400  # Expire after 24 hours
            )
            
            # Add to priority queue (sorted set with priority as score)
            self.redis_client.zadd(
                self.queue_key,
                {request_id: priority}
            )
            
            logger.info("Request enqueued", extra={
                'request_id': request_id,
                'ticker': ticker,
                'priority': priority
            })
            
            return request_id
            
        except Exception as e:
            logger.error("Failed to enqueue request", extra={
                'error': str(e),
                'request_id': request_id
            })
            raise
    
    def dequeue(self) -> Optional[QueuedRequest]:
        """
        Get the highest priority pending request.
        
        Returns:
            QueuedRequest or None if queue is empty
        """
        if not self.enabled:
            return None
        
        try:
            with self.processing_lock:
                # Get highest priority item (ZPOPMAX gets item with highest score)
                result = self.redis_client.bzpopmax(self.queue_key, timeout=1)
                
                if not result:
                    return None
                
                _, request_id, priority = result
                
                # Get request data
                request_key = f"{self.request_prefix}{request_id}"
                request_data = self.redis_client.get(request_key)
                
                if not request_data:
                    logger.warning("Request data not found", extra={
                        'request_id': request_id
                    })
                    return None
                
                request = QueuedRequest.from_dict(json.loads(request_data))
                
                # Move to processing
                request.status = RequestStatus.PROCESSING
                request.updated_at = time.time()
                
                self.redis_client.set(
                    request_key,
                    json.dumps(request.to_dict()),
                    ex=86400
                )
                
                # Add to processing set
                self.redis_client.sadd(self.processing_key, request_id)
                
                logger.debug("Request dequeued", extra={
                    'request_id': request_id,
                    'priority': priority
                })
                
                return request
                
        except Exception as e:
            logger.error("Failed to dequeue request", extra={
                'error': str(e)
            })
            return None
    
    def mark_completed(self, request_id: str, result: Optional[dict] = None):
        """
        Mark a request as completed.
        
        Args:
            request_id: Request ID
            result: Optional result data
        """
        if not self.enabled:
            return
        
        try:
            request_key = f"{self.request_prefix}{request_id}"
            request_data = self.redis_client.get(request_key)
            
            if request_data:
                request = QueuedRequest.from_dict(json.loads(request_data))
                request.status = RequestStatus.COMPLETED
                request.updated_at = time.time()
                request.result = result
                
                self.redis_client.set(
                    request_key,
                    json.dumps(request.to_dict()),
                    ex=3600  # Keep completed requests for 1 hour
                )
            
            # Remove from processing
            self.redis_client.srem(self.processing_key, request_id)
            
            # Add to completed
            self.redis_client.zadd(
                self.completed_key,
                {request_id: time.time()}
            )
            
            logger.info("Request completed", extra={
                'request_id': request_id
            })
            
        except Exception as e:
            logger.error("Failed to mark request as completed", extra={
                'error': str(e),
                'request_id': request_id
            })
    
    def mark_failed(self, request_id: str, error: str, retry: bool = True):
        """
        Mark a request as failed and optionally retry.
        
        Args:
            request_id: Request ID
            error: Error message
            retry: Whether to retry the request
        """
        if not self.enabled:
            return
        
        try:
            request_key = f"{self.request_prefix}{request_id}"
            request_data = self.redis_client.get(request_key)
            
            if not request_data:
                logger.warning("Request data not found for failed request", extra={
                    'request_id': request_id
                })
                return
            
            request = QueuedRequest.from_dict(json.loads(request_data))
            request.attempts += 1
            request.error = error
            request.updated_at = time.time()
            
            # Remove from processing
            self.redis_client.srem(self.processing_key, request_id)
            
            # Check if should retry
            if retry and request.attempts < request.max_attempts:
                request.status = RequestStatus.RETRYING
                
                # Calculate exponential backoff delay
                delay = self.retry_delay * (2 ** (request.attempts - 1))
                retry_time = time.time() + delay
                
                # Re-queue with lower priority and delay
                self.redis_client.set(
                    request_key,
                    json.dumps(request.to_dict()),
                    ex=86400
                )
                
                # Add back to queue with retry timestamp as score (process after delay)
                self.redis_client.zadd(
                    self.queue_key,
                    {request_id: retry_time}
                )
                
                logger.warning("Request failed, will retry", extra={
                    'request_id': request_id,
                    'attempt': request.attempts,
                    'retry_in': delay,
                    'error': error
                })
            else:
                # Max retries reached or retry disabled
                request.status = RequestStatus.FAILED
                
                self.redis_client.set(
                    request_key,
                    json.dumps(request.to_dict()),
                    ex=86400
                )
                
                # Add to failed set
                self.redis_client.zadd(
                    self.failed_key,
                    {request_id: time.time()}
                )
                
                logger.error("Request permanently failed", extra={
                    'request_id': request_id,
                    'attempts': request.attempts,
                    'error': error
                })
                
        except Exception as e:
            logger.error("Failed to mark request as failed", extra={
                'error': str(e),
                'request_id': request_id
            })
    
    def get_request(self, request_id: str) -> Optional[QueuedRequest]:
        """
        Get request details by ID.
        
        Args:
            request_id: Request ID
            
        Returns:
            QueuedRequest or None if not found
        """
        if not self.enabled:
            return None
        
        try:
            request_key = f"{self.request_prefix}{request_id}"
            request_data = self.redis_client.get(request_key)
            
            if request_data:
                return QueuedRequest.from_dict(json.loads(request_data))
            
            return None
            
        except Exception as e:
            logger.error("Failed to get request", extra={
                'error': str(e),
                'request_id': request_id
            })
            return None
    
    def size(self) -> int:
        """Get number of pending requests in queue."""
        if not self.enabled:
            return 0
        
        try:
            return self.redis_client.zcard(self.queue_key)
        except Exception as e:
            logger.error("Failed to get queue size", extra={'error': str(e)})
            return 0
    
    def processing_count(self) -> int:
        """Get number of requests currently being processed."""
        if not self.enabled:
            return 0
        
        try:
            return self.redis_client.scard(self.processing_key)
        except Exception as e:
            logger.error("Failed to get processing count", extra={'error': str(e)})
            return 0
    
    def failed_count(self) -> int:
        """Get number of failed requests."""
        if not self.enabled:
            return 0
        
        try:
            return self.redis_client.zcard(self.failed_key)
        except Exception as e:
            logger.error("Failed to get failed count", extra={'error': str(e)})
            return 0
    
    def completed_count(self) -> int:
        """Get number of completed requests."""
        if not self.enabled:
            return 0
        
        try:
            return self.redis_client.zcard(self.completed_key)
        except Exception as e:
            logger.error("Failed to get completed count", extra={'error': str(e)})
            return 0
    
    def current_job(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently processing job.
        
        Returns:
            Dictionary with job info or None
        """
        if not self.enabled:
            return None
        
        try:
            processing_ids = self.redis_client.smembers(self.processing_key)
            
            if not processing_ids:
                return None
            
            # Get first processing request
            request_id = list(processing_ids)[0]
            request = self.get_request(request_id)
            
            if request:
                return {
                    'request_id': request.id,
                    'ticker': request.ticker,
                    'status': RequestStatus(request.status).name,
                    'attempts': request.attempts,
                    'processing_time': time.time() - request.updated_at
                }
            
            return None
            
        except Exception as e:
            logger.error("Failed to get current job", extra={'error': str(e)})
            return None
    
    def get_failed_requests(self, limit: int = 10) -> List[QueuedRequest]:
        """
        Get list of failed requests.
        
        Args:
            limit: Maximum number of requests to return
            
        Returns:
            List of failed requests
        """
        if not self.enabled:
            return []
        
        try:
            # Get most recent failed requests
            failed_ids = self.redis_client.zrevrange(self.failed_key, 0, limit - 1)
            
            requests = []
            for request_id in failed_ids:
                request = self.get_request(request_id)
                if request:
                    requests.append(request)
            
            return requests
            
        except Exception as e:
            logger.error("Failed to get failed requests", extra={'error': str(e)})
            return []
    
    def clear_completed(self, older_than: int = 3600):
        """
        Clear completed requests older than specified time.
        
        Args:
            older_than: Clear requests completed more than this many seconds ago
        """
        if not self.enabled:
            return
        
        try:
            cutoff_time = time.time() - older_than
            
            # Remove old completed requests
            removed = self.redis_client.zremrangebyscore(
                self.completed_key,
                '-inf',
                cutoff_time
            )
            
            if removed > 0:
                logger.info("Cleared old completed requests", extra={
                    'count': removed,
                    'older_than': older_than
                })
                
        except Exception as e:
            logger.error("Failed to clear completed requests", extra={
                'error': str(e)
            })
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with queue stats
        """
        if not self.enabled:
            return {
                'enabled': False,
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0
            }
        
        return {
            'enabled': True,
            'pending': self.size(),
            'processing': self.processing_count(),
            'completed': self.completed_count(),
            'failed': self.failed_count(),
            'current_job': self.current_job()
        }

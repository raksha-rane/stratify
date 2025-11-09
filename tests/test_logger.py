"""
Unit tests for the structured logging module
"""
import unittest
import os
import json
import sys
import tempfile
from io import StringIO

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.logger import (
    get_logger,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
    mask_sensitive_data,
    log_execution_time
)


class TestStructuredLogger(unittest.TestCase):
    """Test cases for structured logging"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear any existing correlation IDs
        clear_correlation_id()
        
        # Set environment for testing
        os.environ['LOG_LEVEL'] = 'DEBUG'
        os.environ['LOG_FORMAT'] = 'json'
    
    def tearDown(self):
        """Clean up after tests"""
        clear_correlation_id()
    
    def test_get_logger(self):
        """Test logger creation"""
        logger = get_logger('test-service')
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, 'test-service')
    
    def test_logger_with_service_name(self):
        """Test logger with custom service name"""
        logger = get_logger(__name__, service_name='custom-service')
        self.assertEqual(logger.name, 'custom-service')
    
    def test_logger_log_level(self):
        """Test logger respects LOG_LEVEL environment variable"""
        os.environ['LOG_LEVEL'] = 'WARNING'
        logger = get_logger('test-warning')
        
        # Should be WARNING level
        import logging
        self.assertEqual(logger.level, logging.WARNING)
    
    def test_correlation_id(self):
        """Test correlation ID management"""
        # Set correlation ID
        corr_id = set_correlation_id()
        self.assertIsNotNone(corr_id)
        
        # Get correlation ID
        retrieved_id = get_correlation_id()
        self.assertEqual(corr_id, retrieved_id)
        
        # Clear correlation ID
        clear_correlation_id()
        self.assertIsNone(get_correlation_id())
    
    def test_custom_correlation_id(self):
        """Test setting custom correlation ID"""
        custom_id = 'test-123-456'
        set_correlation_id(custom_id)
        self.assertEqual(get_correlation_id(), custom_id)
    
    def test_mask_sensitive_data(self):
        """Test sensitive data masking"""
        data = {
            'username': 'john',
            'password': 'secret123',
            'api_key': 'key-12345',
            'age': 30
        }
        
        masked = mask_sensitive_data(data)
        
        self.assertEqual(masked['username'], 'john')
        self.assertEqual(masked['password'], '***MASKED***')
        self.assertEqual(masked['api_key'], '***MASKED***')
        self.assertEqual(masked['age'], 30)
    
    def test_mask_custom_keys(self):
        """Test masking with custom sensitive keys"""
        data = {
            'email': 'john@example.com',
            'phone': '123-456-7890'
        }
        
        masked = mask_sensitive_data(data, sensitive_keys=['phone'])
        
        self.assertEqual(masked['email'], 'john@example.com')
        self.assertEqual(masked['phone'], '***MASKED***')
    
    def test_log_with_extra_fields(self):
        """Test logging with extra fields"""
        # Capture log output
        log_capture = StringIO()
        logger = get_logger('test-extra')
        
        # Add handler to capture output
        import logging
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        
        # Log with extra fields
        logger.info("Test message", extra={'user_id': 123, 'action': 'login'})
        
        # Check output contains the message
        output = log_capture.getvalue()
        self.assertIn("Test message", output)
    
    def test_log_execution_time_decorator(self):
        """Test execution time logging decorator"""
        logger = get_logger('test-decorator')
        
        @log_execution_time(logger)
        def test_function():
            import time
            time.sleep(0.01)  # Sleep for 10ms
            return "done"
        
        result = test_function()
        self.assertEqual(result, "done")
    
    def test_log_execution_time_with_exception(self):
        """Test execution time decorator handles exceptions"""
        logger = get_logger('test-exception')
        
        @log_execution_time(logger)
        def failing_function():
            raise ValueError("Test error")
        
        with self.assertRaises(ValueError):
            failing_function()
    
    def test_json_format(self):
        """Test JSON log format"""
        os.environ['LOG_FORMAT'] = 'json'
        
        # Create logger with file output
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as f:
            temp_log_file = f.name
        
        try:
            os.environ['LOG_FILE'] = temp_log_file
            logger = get_logger('test-json')
            logger.info("Test JSON log", extra={'key': 'value'})
            
            # Read the log file
            with open(temp_log_file, 'r') as f:
                log_line = f.readline()
            
            # Parse JSON
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data['message'], "Test JSON log")
            self.assertEqual(log_data['level'], 'INFO')
            self.assertEqual(log_data['service'], 'test-json')
            self.assertIn('timestamp', log_data)
        
        finally:
            # Clean up
            if os.path.exists(temp_log_file):
                os.remove(temp_log_file)
            if 'LOG_FILE' in os.environ:
                del os.environ['LOG_FILE']
    
    def test_pretty_format(self):
        """Test pretty log format"""
        os.environ['LOG_FORMAT'] = 'pretty'
        logger = get_logger('test-pretty')
        
        # Capture output
        log_capture = StringIO()
        import logging
        handler = logging.StreamHandler(log_capture)
        logger.addHandler(handler)
        
        logger.info("Pretty formatted message")
        
        output = log_capture.getvalue()
        self.assertIn("Pretty formatted message", output)
        self.assertIn("INFO", output)


class TestLoggerIntegration(unittest.TestCase):
    """Integration tests for logger in realistic scenarios"""
    
    def test_request_logging_pattern(self):
        """Test logging pattern for API requests"""
        logger = get_logger('api-service')
        
        # Simulate API request
        correlation_id = set_correlation_id()
        
        logger.info("API request received", extra={
            'method': 'POST',
            'endpoint': '/data/fetch',
            'correlation_id': correlation_id
        })
        
        # Simulate processing
        logger.debug("Processing request", extra={
            'ticker': 'AAPL',
            'start_date': '2023-01-01'
        })
        
        # Simulate response
        logger.info("API request completed", extra={
            'status_code': 200,
            'duration_ms': 1250
        })
        
        self.assertEqual(get_correlation_id(), correlation_id)
    
    def test_error_logging_with_traceback(self):
        """Test error logging with exception info"""
        logger = get_logger('error-service')
        
        try:
            # Simulate an error
            raise ValueError("Test error for logging")
        except ValueError as e:
            logger.error("An error occurred", extra={
                'error_type': type(e).__name__,
                'error_message': str(e)
            }, exc_info=True)
    
    def test_performance_logging(self):
        """Test performance metric logging"""
        logger = get_logger('perf-service')
        
        import time
        start_time = time.time()
        
        # Simulate work
        time.sleep(0.05)
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info("Operation completed", extra={
            'operation': 'data_fetch',
            'duration_ms': round(duration_ms, 2),
            'records_processed': 100
        })


if __name__ == '__main__':
    unittest.main()

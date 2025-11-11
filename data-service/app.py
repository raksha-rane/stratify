"""
Data Service Module
Fetches and preprocesses stock market data from Yahoo Finance
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import sys
import time
import json

# Add parent directory to path for common module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.logger import get_logger, set_correlation_id, log_execution_time
from common.error_handlers import (
    handle_errors, retry_on_failure, register_error_handlers,
    ValidationError, DataFetchError, DatabaseError, ResourceNotFoundError,
    validate_request_data
)
from common.health import HealthCheck
from validators import validate_ohlcv_data, validate_ticker_format, validate_date_range

app = Flask(__name__)
CORS(app)

# Register global error handlers
register_error_handlers(app)

# Initialize logger
logger = get_logger(__name__, service_name='data-service')


# Database configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'aqts_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Configure connection pooling for production use
engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # Number of connections to maintain
    max_overflow=20,        # Additional connections when pool is full
    pool_pre_ping=True,     # Test connections before using
    pool_recycle=3600       # Recycle connections after 1 hour
)
Base = declarative_base()
Session = sessionmaker(bind=engine)


class MarketData(Base):
    """Market data model"""
    __tablename__ = 'market_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False)
    date = Column(DateTime, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    adj_close = Column(Float)


class DataQualityLog(Base):
    """Data quality validation log model"""
    __tablename__ = 'data_quality_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False)
    validation_date = Column(DateTime, nullable=False, default=datetime.now)
    is_valid = Column(Boolean, nullable=False)
    critical_issues = Column(JSON)
    warnings = Column(JSON)
    stats = Column(JSON)
    record_count = Column(Integer)
    quality_score = Column(Integer)


def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Error creating database tables", extra={'error': str(e)}, exc_info=True)

# Initialize health checker
health_checker = HealthCheck(
    db_url=DATABASE_URL,
    service_name='data-service'
)

# Initialize Prometheus metrics
from common.metrics import (
    initialize_service_metrics, 
    service_up, 
    active_connections,
    track_request_metrics,
    data_fetch_total,
    data_quality_score,
    rate_limit_hits_total
)
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

initialize_service_metrics('data-service', version='1.0.0')

# Initialize rate limiter and request queue
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

try:
    from common.rate_limiter import RateLimiter, rate_limit
    from request_queue import RequestQueue, RequestPriority
    
    app.rate_limiter = RateLimiter(REDIS_URL)
    request_queue = RequestQueue(REDIS_URL, max_retries=3, retry_delay=5)
    
    logger.info("Rate limiter and request queue initialized", extra={
        'redis_url': REDIS_URL.split('@')[-1]
    })
except Exception as e:
    logger.warning("Failed to initialize rate limiter/queue", extra={
        'error': str(e)
    })
    app.rate_limiter = None
    request_queue = None

@app.route('/', methods=['GET'])
def index():
    """
    Root endpoint - Service information and available endpoints
    """
    return jsonify({
        'service': 'AQTS Data Service',
        'version': '1.0.0',
        'description': 'Fetches and stores stock market data from Yahoo Finance',
        'status': 'running',
        'endpoints': {
            '/': 'GET - Service information (this endpoint)',
            '/health': 'GET - Health check endpoint',
            '/metrics': 'GET - Prometheus metrics',
            '/data/fetch': 'POST - Fetch stock data from Yahoo Finance',
            '/data/get': 'GET - Retrieve stored stock data',
            '/queue/status': 'GET - Check request queue status'
        },
        'examples': {
            'fetch_data': {
                'method': 'POST',
                'url': '/data/fetch',
                'body': {
                    'ticker': 'AAPL',
                    'start_date': '2023-01-01',
                    'end_date': '2024-01-01'
                }
            },
            'get_data': {
                'method': 'GET',
                'url': '/data/get?ticker=AAPL&start_date=2023-01-01&end_date=2024-01-01'
            }
        }
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns health status of all dependencies including:
    - Database connectivity
    - External API (yfinance) availability
    - Disk space
    - System metrics (CPU, memory, uptime)
    """
    logger.debug("Health check requested")
    
    # Run all health checks
    result = health_checker.run_all_checks(
        check_db=True,
        check_redis=False,  # Not using Redis in data-service
        check_api=True,     # Check yfinance API
        check_disk=True
    )
    
    status_code = 200 if result['status'] == 'healthy' else 503
    
    return jsonify(result), status_code


@app.route('/metrics', methods=['GET'])
def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus format for scraping.
    """
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


def _fetch_yahoo_finance_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Internal function to fetch data from Yahoo Finance with retry logic.
    Separated to use with retry decorator.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        stock_data = ticker_obj.history(start=start_date, end=end_date, auto_adjust=False, timeout=30)
        
        if stock_data.empty:
            # Try alternate method
            stock_data = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=False, timeout=30)
        
        if stock_data.empty:
            raise DataFetchError(
                f"No data available for ticker '{ticker}' in the specified date range",
                source="Yahoo Finance",
                details={'ticker': ticker, 'start_date': start_date, 'end_date': end_date}
            )
        
        logger.info("Data fetched successfully from Yahoo Finance", extra={
            'ticker': ticker,
            'records': len(stock_data)
        })
        
        return stock_data
        
    except DataFetchError:
        raise
    except Exception as e:
        raise DataFetchError(
            f"Failed to fetch data for {ticker}: {str(e)}",
            source="Yahoo Finance",
            details={'ticker': ticker, 'error': str(e)}
        )


@app.route('/data/fetch', methods=['POST'])
@rate_limit(calls=48, period=60, resource='yfinance')  # Yahoo Finance rate limit
@handle_errors
@log_execution_time(logger)
@track_request_metrics('data-service', '/data/fetch')
def fetch_data():
    """
    Fetch stock data from Yahoo Finance with rate limiting.
    
    Rate limit: 48 requests per minute for yfinance API
    Burst capacity: 10 requests
    
    Expected JSON: {
        "ticker": "AAPL",
        "start_date": "2023-01-01",
        "end_date": "2024-01-01"
    }
    """
    # Apply rate limiting manually (since decorator needs Flask app context)
    if app.rate_limiter and app.rate_limiter.enabled:
        identifier = request.remote_addr or 'unknown'
        allowed, info = app.rate_limiter.check_rate_limit(
            resource='yfinance',
            identifier=identifier,
            calls=48,      # 48 requests per minute
            period=60,     # 60 seconds
            burst=10       # Burst capacity of 10
        )
        
        if not allowed:
            logger.warning("Rate limit exceeded", extra={
                'identifier': identifier,
                'retry_after': info['retry_after']
            })
            
            # Track rate limit hit in metrics
            rate_limit_hits_total.labels(
                service='data-service',
                resource='yfinance'
            ).inc()
            
            response = jsonify({
                'error': 'RATE_LIMIT_EXCEEDED',
                'message': 'Rate limit exceeded for yfinance API',
                'retry_after': info['retry_after'],
                'limit': {
                    'calls': 48,
                    'period': 60,
                    'burst': 10
                }
            })
            response.status_code = 429
            response.headers['Retry-After'] = str(info['retry_after'])
            response.headers['X-RateLimit-Limit'] = '48'
            response.headers['X-RateLimit-Remaining'] = str(info['tokens_remaining'])
            response.headers['X-RateLimit-Reset'] = str(info['reset_time'])
            return response
    
    # Set correlation ID for request tracing
    correlation_id = request.headers.get('X-Correlation-ID', set_correlation_id())
    
    # Validate request data
    data = request.get_json()
    validate_request_data(
        data,
        required_fields=['ticker', 'start_date', 'end_date']
    )
    
    ticker = data['ticker'].upper()
    start_date = data['start_date']
    end_date = data['end_date']
    
    # Validate ticker format
    if not validate_ticker_format(ticker):
        raise ValidationError(
            "Invalid ticker symbol format",
            field="ticker",
            details={'ticker': ticker}
        )
    
    # Validate date range
    date_validation = validate_date_range(start_date, end_date)
    if not date_validation['valid']:
        raise ValidationError(
            date_validation['error'],
            field="date_range",
            details={'start_date': start_date, 'end_date': end_date}
        )
    
    logger.info("Starting data fetch", extra={
        'ticker': ticker,
        'start_date': start_date,
        'end_date': end_date,
        'correlation_id': correlation_id
    })
    
    # Fetch data with retry logic using decorator
    @retry_on_failure(max_retries=3, backoff_factor=2, exceptions=(DataFetchError, ConnectionError))
    def fetch_with_retry():
        return _fetch_yahoo_finance_data(ticker, start_date, end_date)
    
    stock_data = fetch_with_retry()
    
    # ========================================================================
    # DATA QUALITY VALIDATION
    # ========================================================================
    logger.info("Validating data quality", extra={'ticker': ticker, 'records': len(stock_data)})
    
    quality_report = validate_ohlcv_data(
        stock_data,
        ticker=ticker,
        max_price_change_pct=50.0,
        max_date_gap_days=5,
        enable_outlier_detection=True
    )
    
    # Save quality report to database
    session_quality = Session()
    try:
        quality_log = DataQualityLog(
            ticker=ticker,
            validation_date=quality_report.validation_date,
            is_valid=quality_report.is_valid,
            critical_issues=json.dumps(quality_report.critical_issues),
            warnings=json.dumps(quality_report.warnings),
            stats=json.dumps(quality_report.stats),
            record_count=quality_report.record_count,
            quality_score=quality_report.stats.get('quality_score', 0)
        )
        session_quality.add(quality_log)
        session_quality.commit()
        
        # Track data quality score in metrics
        quality_score = quality_report.stats.get('quality_score', 0)
        data_quality_score.labels(ticker=ticker).set(quality_score)
        
        # Track successful data fetch
        data_fetch_total.labels(
            service='data-service',
            ticker=ticker,
            status='success'
        ).inc()
        
        logger.info("Quality report saved", extra={
            'ticker': ticker,
            'is_valid': quality_report.is_valid,
            'quality_score': quality_report.stats.get('quality_score', 0)
        })
    except Exception as e:
        session_quality.rollback()
        logger.error("Failed to save quality report", extra={'error': str(e)}, exc_info=True)
    finally:
        session_quality.close()
    
    # Check validation results
    if not quality_report.is_valid:
        logger.error("Data quality validation failed", extra={
            'ticker': ticker,
            'critical_issues': quality_report.critical_issues
        })
        raise ValidationError(
            f"Data quality validation failed: {'; '.join(quality_report.critical_issues[:3])}",
            details={
                'critical_issues': quality_report.critical_issues,
                'quality_score': quality_report.stats.get('quality_score', 0)
            }
        )
    
    # Log warnings if any
    if quality_report.warnings:
        logger.warning("Data quality warnings detected", extra={
            'ticker': ticker,
            'warnings': quality_report.warnings,
            'quality_score': quality_report.stats.get('quality_score', 0)
        })
    
    # Clean and preprocess data
    stock_data.reset_index(inplace=True)
    stock_data.columns = [col.lower() for col in stock_data.columns]
    
    logger.info("Storing data in database", extra={
        'ticker': ticker,
        'records': len(stock_data)
    })
    
    # Store in database
    session = Session()
    try:
        # Delete existing data for this ticker and date range
        deleted_count = session.query(MarketData).filter(
            MarketData.ticker == ticker,
            MarketData.date >= start_date,
            MarketData.date <= end_date
        ).delete()
        
        logger.debug("Deleted existing data", extra={
            'ticker': ticker,
            'deleted_records': deleted_count
        })
        
        # Insert new data
        for _, row in stock_data.iterrows():
            market_entry = MarketData(
                ticker=ticker,
                date=row['date'],
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume']),
                adj_close=float(row['adj close']) if 'adj close' in row else float(row['close'])
            )
            session.add(market_entry)
        
        session.commit()
        
        logger.info("Data stored successfully", extra={
            'ticker': ticker,
            'records': len(stock_data),
            'start_date': start_date,
            'end_date': end_date
        })
        
        return jsonify({
            'message': 'Data fetched and stored successfully',
            'ticker': ticker,
            'records': len(stock_data),
            'start_date': start_date,
            'end_date': end_date,
            'sample_data': stock_data.head(5).to_dict('records'),
            'data_quality': {
                'is_valid': quality_report.is_valid,
                'quality_score': quality_report.stats.get('quality_score', 0),
                'warnings_count': len(quality_report.warnings),
                'warnings': quality_report.warnings[:3] if quality_report.warnings else []  # First 3 warnings
            }
        }), 200
        
    except Exception as e:
        session.rollback()
        raise DatabaseError(
            f"Failed to store data in database: {str(e)}",
            operation="insert",
            details={'ticker': ticker, 'records': len(stock_data)}
        )
    finally:
        session.close()


@app.route('/data/get', methods=['GET'])
@handle_errors
@log_execution_time(logger)
def get_data():
    """
    Get stored stock data from database with Redis caching
    Query params: ticker, start_date, end_date
    """
    correlation_id = request.headers.get('X-Correlation-ID', set_correlation_id())
    
    ticker = request.args.get('ticker')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Validate required parameters
    if not ticker:
        raise ValidationError("ticker parameter is required", field="ticker")
    if not start_date:
        raise ValidationError("start_date parameter is required", field="start_date")
    if not end_date:
        raise ValidationError("end_date parameter is required", field="end_date")
    
    ticker = ticker.upper()
    
    # Try to get from Redis cache first
    cache_key = f"market_data:{ticker}:{start_date}:{end_date}"
    cached_data = None
    
    if app.rate_limiter and app.rate_limiter.enabled:
        try:
            cached_json = app.rate_limiter.redis_client.get(cache_key)
            if cached_json:
                cached_data = json.loads(cached_json)
                logger.info("Data retrieved from cache", extra={
                    'ticker': ticker,
                    'cache_key': cache_key,
                    'correlation_id': correlation_id
                })
                return jsonify(cached_data), 200
        except Exception as e:
            logger.warning("Cache retrieval failed", extra={'error': str(e)})
    
    logger.info("Retrieving data from database", extra={
        'ticker': ticker,
        'start_date': start_date,
        'end_date': end_date,
        'correlation_id': correlation_id
    })
    
    session = Session()
    try:
        results = session.query(MarketData).filter(
            MarketData.ticker == ticker,
            MarketData.date >= start_date,
            MarketData.date <= end_date
        ).order_by(MarketData.date).all()
        
        if not results:
            raise ResourceNotFoundError(
                f"No data found for ticker '{ticker}' between {start_date} and {end_date}",
                details={
                    'ticker': ticker,
                    'start_date': start_date,
                    'end_date': end_date
                }
            )
        
        data = [{
            'date': r.date.strftime('%Y-%m-%d'),
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume,
            'adj_close': r.adj_close
        } for r in results]
        
        logger.info("Data retrieved successfully", extra={
            'ticker': ticker,
            'records': len(data)
        })
        
        response_data = {
            'ticker': ticker,
            'records': len(data),
            'data': data
        }
        
        # Cache the result in Redis (expire after 1 hour)
        if app.rate_limiter and app.rate_limiter.enabled:
            try:
                app.rate_limiter.redis_client.setex(
                    cache_key,
                    3600,  # 1 hour TTL
                    json.dumps(response_data)
                )
                logger.debug("Data cached in Redis", extra={'cache_key': cache_key})
            except Exception as e:
                logger.warning("Failed to cache data", extra={'error': str(e)})
        
        return jsonify(response_data), 200
        
    except (ValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        raise DatabaseError(
            f"Failed to retrieve data from database: {str(e)}",
            operation="query",
            details={'ticker': ticker}
        )
    finally:
        session.close()


@app.route('/queue/status', methods=['GET'])
def queue_status():
    """
    Get current status of the request queue and rate limiter.
    
    Returns:
        JSON with queue statistics and rate limit information
    """
    if not request_queue or not request_queue.enabled:
        return jsonify({
            'queue': {
                'enabled': False,
                'message': 'Request queue not available'
            }
        }), 200
    
    try:
        # Get queue stats
        stats = request_queue.get_stats()
        
        # Get rate limiter info
        rate_limit_info = {}
        if app.rate_limiter and app.rate_limiter.enabled:
            identifier = request.remote_addr or 'unknown'
            rate_limit_info = app.rate_limiter.get_stats(
                resource='yfinance',
                identifier=identifier,
                calls=48,
                period=60,
                burst=10
            )
            rate_limit_info['time_until_reset'] = app.rate_limiter.time_until_reset(
                resource='yfinance',
                identifier=identifier,
                calls=48,
                period=60,
                burst=10
            )
        
        # Get failed requests
        failed_requests = []
        if stats.get('failed', 0) > 0:
            failed = request_queue.get_failed_requests(limit=5)
            failed_requests = [
                {
                    'request_id': req.id,
                    'ticker': req.ticker,
                    'attempts': req.attempts,
                    'error': req.error,
                    'created_at': datetime.fromtimestamp(req.created_at).isoformat()
                }
                for req in failed
            ]
        
        return jsonify({
            'queue': stats,
            'rate_limit': rate_limit_info,
            'failed_requests': failed_requests,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error("Failed to get queue status", extra={'error': str(e)})
        return jsonify({
            'error': 'Failed to get queue status',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    logger.info("Starting Data Service", extra={
        'port': 5001,
        'debug': True,
        'db_host': DB_HOST
    })
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)

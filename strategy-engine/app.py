"""
Strategy Engine Module
Implements trading strategies and generates buy/sell signals
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import sys
import requests

# Add parent directory to path for common module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.logger import get_logger, set_correlation_id, log_execution_time
from common.health import HealthCheck
from common.rate_limiter import RateLimiter, rate_limit
from common.metrics import (
    initialize_service_metrics,
    service_up,
    active_connections,
    track_request_metrics,
    track_strategy_execution,
    backtest_trades_total,
    backtest_return_percent,
    backtest_sharpe_ratio
)
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from risk_manager import RiskManager, Portfolio, TransactionCosts

app = Flask(__name__)
CORS(app)

# Initialize logger
logger = get_logger(__name__, service_name='strategy-engine')

# Initialize Prometheus metrics
initialize_service_metrics('strategy-engine', version='1.0.0')

# Constants
MIN_TRADES_FOR_KELLY = 10  # Minimum trades before applying Kelly Criterion
DEFAULT_STOP_LOSS_PCT = 0.05  # 5% stop loss
MIN_WINDOW_SIZE = 1
MAX_WINDOW_SIZE = 200
MIN_STD_DEV = 0.1
MAX_STD_DEV = 5.0
MIN_MOMENTUM_THRESHOLD = 0.001
MAX_MOMENTUM_THRESHOLD = 1.0
MIN_STOP_LOSS_PCT = 0.01  # 1%
MAX_STOP_LOSS_PCT = 0.5   # 50%
BACKTEST_PAGE_SIZE = 100  # Number of backtest results per page

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'aqua_db')
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

DATA_SERVICE_URL = os.getenv('DATA_SERVICE_URL', 'http://localhost:5001')


class Trade(Base):
    """Trade signals model"""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False)
    strategy = Column(String(50), nullable=False)
    date = Column(DateTime, nullable=False)
    signal = Column(String(10), nullable=False)  # BUY, SELL, HOLD
    price = Column(Float)
    quantity = Column(Float)
    portfolio_value = Column(Float)


class BacktestResult(Base):
    """Backtest results model"""
    __tablename__ = 'backtest_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False)
    strategy = Column(String(50), nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    initial_capital = Column(Float)
    final_capital = Column(Float)
    total_return = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    total_trades = Column(Integer)
    parameters = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Error creating database tables", extra={'error': str(e)}, exc_info=True)


class TradingStrategy:
    """Base class for trading strategies"""
    
    def __init__(self, data):
        self.data = data.copy()
        
    def calculate_signals(self):
        """Override this method in subclasses"""
        raise NotImplementedError


class SMAStrategy(TradingStrategy):
    """Simple Moving Average Crossover Strategy"""
    
    def __init__(self, data, short_window=20, long_window=50):
        super().__init__(data)
        self.short_window = short_window
        self.long_window = long_window
        
    def calculate_signals(self):
        """Generate signals based on SMA crossover"""
        self.data['sma_short'] = self.data['close'].rolling(window=self.short_window).mean()
        self.data['sma_long'] = self.data['close'].rolling(window=self.long_window).mean()
        
        self.data['signal'] = 'HOLD'
        self.data.loc[self.data['sma_short'] > self.data['sma_long'], 'signal'] = 'BUY'
        self.data.loc[self.data['sma_short'] < self.data['sma_long'], 'signal'] = 'SELL'
        
        # Generate trading signals (only when crossing)
        self.data['position'] = 0
        self.data.loc[self.data['signal'] == 'BUY', 'position'] = 1
        self.data.loc[self.data['signal'] == 'SELL', 'position'] = -1
        
        return self.data


class MeanReversionStrategy(TradingStrategy):
    """Mean Reversion Strategy"""
    
    def __init__(self, data, window=20, num_std=2):
        super().__init__(data)
        self.window = window
        self.num_std = num_std
        
    def calculate_signals(self):
        """Generate signals based on mean reversion"""
        self.data['moving_avg'] = self.data['close'].rolling(window=self.window).mean()
        self.data['std'] = self.data['close'].rolling(window=self.window).std()
        
        self.data['upper_band'] = self.data['moving_avg'] + (self.num_std * self.data['std'])
        self.data['lower_band'] = self.data['moving_avg'] - (self.num_std * self.data['std'])
        
        self.data['signal'] = 'HOLD'
        self.data.loc[self.data['close'] < self.data['lower_band'], 'signal'] = 'BUY'
        self.data.loc[self.data['close'] > self.data['upper_band'], 'signal'] = 'SELL'
        
        self.data['position'] = 0
        self.data.loc[self.data['signal'] == 'BUY', 'position'] = 1
        self.data.loc[self.data['signal'] == 'SELL', 'position'] = -1
        
        return self.data


class MomentumStrategy(TradingStrategy):
    """Momentum Strategy"""
    
    def __init__(self, data, lookback=10):
        super().__init__(data)
        self.lookback = lookback
        
    def calculate_signals(self):
        """Generate signals based on momentum"""
        self.data['returns'] = self.data['close'].pct_change()
        self.data['momentum'] = self.data['returns'].rolling(window=self.lookback).sum()
        
        self.data['signal'] = 'HOLD'
        self.data.loc[self.data['momentum'] > 0, 'signal'] = 'BUY'
        self.data.loc[self.data['momentum'] < 0, 'signal'] = 'SELL'
        
        self.data['position'] = 0
        self.data.loc[self.data['signal'] == 'BUY', 'position'] = 1
        self.data.loc[self.data['signal'] == 'SELL', 'position'] = -1
        
        return self.data


def run_backtest(data, initial_capital=10000, enable_risk_management=True, use_kelly=False, enable_stop_loss=True, stop_loss_pct=0.05, commission=0.001, slippage=0.0005, max_position_pct=0.95):
    """
    Run backtest on strategy signals with risk management
    
    Args:
        data: DataFrame with columns ['date', 'close', 'signal']
        initial_capital: Starting capital
        enable_risk_management: Whether to apply risk management rules
        use_kelly: Whether to use Kelly Criterion for position sizing (after 10+ trades)
        enable_stop_loss: Whether to enable automatic stop-loss
        stop_loss_pct: Stop loss percentage (e.g., 0.05 for 5%)
        commission: Commission per trade as decimal (e.g., 0.001 for 0.1%)
        slippage: Slippage per trade as decimal (e.g., 0.0005 for 0.05%)
        max_position_pct: Maximum portfolio percentage in single position (e.g., 0.95 for 95%)
    
    Returns:
        Dictionary with backtest results and metrics
    """
    # Initialize risk manager with custom parameters
    risk_mgr = RiskManager(
        commission=commission,
        slippage=slippage,
        max_position_pct=max_position_pct,
        max_risk_per_trade=0.02,    # Max 2% risk per trade
        min_position_value=100.0    # Minimum $100 position
    )
    
    # Initialize portfolio
    portfolio = Portfolio(cash=initial_capital)
    
    # Track metrics
    equity_curve = []
    trades = []
    rejected_trades = []
    total_commission = 0.0
    total_slippage = 0.0
    stop_losses_triggered = 0
    
    # Track for Kelly Criterion
    trade_history = []  # Store completed trades for Kelly calculation
    entry_prices = {}   # Track entry prices for stop-loss
    stop_loss_prices = {}  # Track stop-loss levels
    
    logger.info("Starting backtest", extra={
        'initial_capital': initial_capital,
        'enable_risk_management': enable_risk_management,
        'use_kelly': use_kelly,
        'enable_stop_loss': enable_stop_loss,
        'commission': commission,
        'slippage': slippage,
        'max_position_pct': max_position_pct,
        'data_records': len(data)
    })
    
    for idx, row in data.iterrows():
        current_price = row['close']
        signal = row['signal']
        ticker = 'STOCK'  # Generic ticker for backtest
        
        # Update position values
        for t in portfolio.positions:
            portfolio.position_values[t] = portfolio.positions[t] * current_price
        
        # Check stop-loss for existing positions
        if enable_stop_loss and ticker in portfolio.positions and ticker in stop_loss_prices:
            if current_price <= stop_loss_prices[ticker]:
                # Stop-loss triggered!
                shares = portfolio.positions[ticker]
                
                logger.info("Stop-loss triggered", extra={
                    'date': str(row['date']),
                    'entry_price': entry_prices[ticker],
                    'stop_price': stop_loss_prices[ticker],
                    'current_price': current_price,
                    'shares': shares
                })
                
                # Apply transaction costs
                costs = risk_mgr.apply_transaction_costs(
                    price=current_price,
                    quantity=int(shares),
                    side='SELL'
                )
                
                # Execute stop-loss exit
                proceeds = shares * costs.effective_price - costs.total_cost
                entry_cost = entry_prices[ticker] * shares
                pnl = proceeds - entry_cost
                
                portfolio.cash += proceeds
                del portfolio.positions[ticker]
                del portfolio.position_values[ticker]
                del entry_prices[ticker]
                del stop_loss_prices[ticker]
                
                total_commission += costs.commission
                total_slippage += costs.slippage
                stop_losses_triggered += 1
                
                trades.append({
                    'date': row['date'],
                    'signal': 'STOP_LOSS',
                    'price': current_price,
                    'effective_price': costs.effective_price,
                    'shares': shares,
                    'proceeds': proceeds,
                    'commission': costs.commission,
                    'slippage': costs.slippage,
                    'portfolio_value': portfolio.total_value,
                    'pnl': pnl
                })
                
                # Record in trade history for Kelly
                trade_history.append({
                    'entry_price': entry_cost / shares,
                    'exit_price': current_price,
                    'shares': shares,
                    'pnl': pnl,
                    'profit': pnl > 0
                })
                
                equity_curve.append(portfolio.total_value)
                continue
        
        # Execute trades based on signals
        if signal == 'BUY' and ticker not in portfolio.positions:
            # Calculate position size
            if enable_risk_management:
                # Use stop loss percentage from parameters
                
                # Use Kelly Criterion if we have enough trade history
                if use_kelly and len(trade_history) >= MIN_TRADES_FOR_KELLY:
                    wins = [t for t in trade_history if t['profit']]
                    losses = [t for t in trade_history if not t['profit']]
                    
                    win_rate = len(wins) / len(trade_history)
                    avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
                    avg_loss = abs(np.mean([t['pnl'] for t in losses])) if losses else 1
                    
                    shares = risk_mgr.calculate_position_size(
                        capital=portfolio.cash,
                        price=current_price,
                        stop_loss_pct=stop_loss_pct,
                        win_rate=win_rate,
                        avg_win=avg_win,
                        avg_loss=avg_loss,
                        use_kelly=True
                    )
                    
                    logger.debug("Kelly Criterion position sizing", extra={
                        'win_rate': win_rate,
                        'avg_win': avg_win,
                        'avg_loss': avg_loss,
                        'shares': shares
                    })
                else:
                    # Use risk-based position sizing
                    shares = risk_mgr.calculate_position_size(
                        capital=portfolio.cash,
                        price=current_price,
                        stop_loss_pct=stop_loss_pct
                    )
            else:
                # Use all available capital
                shares = risk_mgr.get_max_shares_affordable(portfolio.cash, current_price)
            
            if shares > 0:
                # Validate trade
                if enable_risk_management:
                    is_valid, reason = risk_mgr.validate_trade(
                        portfolio=portfolio,
                        ticker=ticker,
                        quantity=int(shares),
                        price=current_price,
                        side='BUY'
                    )
                    
                    if not is_valid:
                        logger.warning("Trade rejected", extra={
                            'reason': reason,
                            'date': str(row['date']),
                            'price': current_price,
                            'shares': shares
                        })
                        rejected_trades.append({
                            'date': row['date'],
                            'signal': 'BUY',
                            'reason': reason
                        })
                        equity_curve.append(portfolio.total_value)
                        continue
                
                # Apply transaction costs
                costs = risk_mgr.apply_transaction_costs(
                    price=current_price,
                    quantity=int(shares),
                    side='BUY'
                )
                
                # Execute trade
                total_cost = shares * costs.effective_price + costs.total_cost
                
                if total_cost <= portfolio.cash:
                    portfolio.cash -= total_cost
                    portfolio.positions[ticker] = shares
                    portfolio.position_values[ticker] = shares * current_price
                    
                    # Set stop-loss price
                    if enable_stop_loss:
                        stop_loss_prices[ticker] = risk_mgr.calculate_stop_loss(
                            entry_price=current_price,
                            side='BUY',
                            fixed_pct=0.05  # 5% stop loss
                        )
                        entry_prices[ticker] = current_price
                    
                    # Calculate risk-reward ratio (assuming 10% target)
                    target_price = current_price * 1.10
                    stop_loss = stop_loss_prices.get(ticker, current_price * 0.95)
                    risk_reward = risk_mgr.calculate_risk_reward(
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        target_price=target_price,
                        side='BUY'
                    )
                    
                    total_commission += costs.commission
                    total_slippage += costs.slippage
                    
                    trades.append({
                        'date': row['date'],
                        'signal': 'BUY',
                        'price': current_price,
                        'effective_price': costs.effective_price,
                        'shares': shares,
                        'cost': total_cost,
                        'commission': costs.commission,
                        'slippage': costs.slippage,
                        'portfolio_value': portfolio.total_value,
                        'stop_loss': stop_loss_prices.get(ticker, 0),
                        'target_price': target_price,
                        'risk_reward_ratio': risk_reward
                    })
                    
                    logger.debug("BUY executed", extra={
                        'date': str(row['date']),
                        'shares': shares,
                        'price': current_price,
                        'effective_price': costs.effective_price,
                        'total_cost': total_cost,
                        'stop_loss': stop_loss_prices.get(ticker, 0),
                        'risk_reward_ratio': risk_reward
                    })
        
        elif signal == 'SELL' and ticker in portfolio.positions:
            shares = portfolio.positions[ticker]
            
            if shares > 0:
                # Validate trade
                if enable_risk_management:
                    is_valid, reason = risk_mgr.validate_trade(
                        portfolio=portfolio,
                        ticker=ticker,
                        quantity=int(shares),
                        price=current_price,
                        side='SELL'
                    )
                    
                    if not is_valid:
                        logger.warning("Trade rejected", extra={
                            'reason': reason,
                            'date': str(row['date']),
                            'price': current_price,
                            'shares': shares
                        })
                        rejected_trades.append({
                            'date': row['date'],
                            'signal': 'SELL',
                            'reason': reason
                        })
                        equity_curve.append(portfolio.total_value)
                        continue
                
                # Apply transaction costs
                costs = risk_mgr.apply_transaction_costs(
                    price=current_price,
                    quantity=int(shares),
                    side='SELL'
                )
                
                # Execute trade
                proceeds = shares * costs.effective_price - costs.total_cost
                
                # Calculate P&L
                entry_cost = entry_prices.get(ticker, current_price) * shares
                pnl = proceeds - entry_cost
                
                portfolio.cash += proceeds
                del portfolio.positions[ticker]
                del portfolio.position_values[ticker]
                
                # Clean up stop-loss tracking
                if ticker in entry_prices:
                    del entry_prices[ticker]
                if ticker in stop_loss_prices:
                    del stop_loss_prices[ticker]
                
                total_commission += costs.commission
                total_slippage += costs.slippage
                
                trades.append({
                    'date': row['date'],
                    'signal': 'SELL',
                    'price': current_price,
                    'effective_price': costs.effective_price,
                    'shares': shares,
                    'proceeds': proceeds,
                    'commission': costs.commission,
                    'slippage': costs.slippage,
                    'portfolio_value': portfolio.total_value,
                    'pnl': pnl
                })
                
                # Record in trade history for Kelly
                trade_history.append({
                    'entry_price': entry_cost / shares if shares > 0 else 0,
                    'exit_price': current_price,
                    'shares': shares,
                    'pnl': pnl,
                    'profit': pnl > 0
                })
                
                logger.debug("SELL executed", extra={
                    'date': str(row['date']),
                    'shares': shares,
                    'price': current_price,
                    'effective_price': costs.effective_price,
                    'proceeds': proceeds,
                    'pnl': pnl
                })
        
        # Record equity curve
        equity_curve.append(portfolio.total_value)
    
    # Calculate performance metrics
    equity_curve = np.array(equity_curve)
    
    if len(equity_curve) == 0:
        equity_curve = np.array([initial_capital])
    
    returns = np.diff(equity_curve) / equity_curve[:-1] if len(equity_curve) > 1 else np.array([0])
    
    # Final capital
    final_capital = equity_curve[-1]
    total_return = ((final_capital - initial_capital) / initial_capital) * 100
    
    # Sharpe ratio (annualized, assuming 252 trading days)
    if len(returns) > 0 and np.std(returns) != 0:
        sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
    else:
        sharpe_ratio = 0
    
    # Maximum drawdown
    cumulative = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - cumulative) / cumulative
    max_drawdown = np.min(drawdown) * 100 if len(drawdown) > 0 else 0
    
    # Win rate (profitable trades / total trades)
    if len(trades) >= 2:
        buy_trades = [t for t in trades if t['signal'] == 'BUY']
        sell_trades = [t for t in trades if t['signal'] == 'SELL']
        
        profitable_trades = 0
        for i in range(min(len(buy_trades), len(sell_trades))):
            if sell_trades[i]['proceeds'] > buy_trades[i]['cost']:
                profitable_trades += 1
        
        win_rate = (profitable_trades / len(sell_trades) * 100) if len(sell_trades) > 0 else 0
    else:
        win_rate = 0
    
    # Total costs
    total_costs = total_commission + total_slippage
    costs_pct = (total_costs / initial_capital) * 100 if initial_capital > 0 else 0
    
    # Calculate Kelly Criterion statistics
    # Always return stats when use_kelly is True, even if not enough trades yet
    wins = [t for t in trade_history if t['profit']] if trade_history else []
    losses = [t for t in trade_history if not t['profit']] if trade_history else []
    
    kelly_stats = {
        'total_completed_trades': len(trade_history),
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'win_rate': len(wins) / len(trade_history) if trade_history else 0,
        'avg_win': float(np.mean([t['pnl'] for t in wins])) if wins else 0,
        'avg_loss': float(abs(np.mean([t['pnl'] for t in losses]))) if losses else 0,
        'kelly_used': use_kelly and len(trade_history) >= 10  # Only true if actually used
    }
    
    logger.info("Backtest completed", extra={
        'final_capital': final_capital,
        'total_return': total_return,
        'total_trades': len(trades),
        'rejected_trades': len(rejected_trades),
        'stop_losses_triggered': stop_losses_triggered,
        'total_costs': total_costs,
        'costs_pct': costs_pct,
        'kelly_stats': kelly_stats
    })
    
    return {
        'initial_capital': initial_capital,
        'final_capital': final_capital,
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'total_trades': len(trades),
        'rejected_trades': len(rejected_trades),
        'stop_losses_triggered': stop_losses_triggered,
        'equity_curve': equity_curve.tolist(),
        'trades': trades,
        'costs': {
            'total_commission': total_commission,
            'total_slippage': total_slippage,
            'total_costs': total_costs,
            'costs_pct': costs_pct
        },
        'risk_management': risk_mgr.to_dict(),
        'kelly_criterion': kelly_stats
    }

# Initialize health checker
health_checker = HealthCheck(
    db_url=DATABASE_URL,
    service_name='strategy-engine'
)

# Initialize rate limiter
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
try:
    rate_limiter = RateLimiter(redis_url=REDIS_URL)
    app.rate_limiter = rate_limiter
    logger.info("Rate limiter initialized")
except Exception as e:
    logger.warning("Failed to initialize rate limiter, rate limiting disabled", extra={'error': str(e)})
    app.rate_limiter = None

@app.route('/', methods=['GET'])
def index():
    """
    Root endpoint - Service information and available endpoints
    """
    return jsonify({
        'service': 'AQUA Strategy Engine',
        'version': '1.0.0',
        'description': 'Implements trading strategies and backtesting engine',
        'status': 'running',
        'endpoints': {
            '/': 'GET - Service information (this endpoint)',
            '/health': 'GET - Health check endpoint',
            '/metrics': 'GET - Prometheus metrics',
            '/strategy/run': 'POST - Execute backtest for a trading strategy',
            '/results': 'GET - List all backtest results (paginated)',
            '/results/<id>': 'GET - Get specific backtest result by ID'
        },
        'available_strategies': [
            'sma_crossover',
            'mean_reversion',
            'momentum'
        ],
        'docs': {
            'strategy_run': {
                'method': 'POST',
                'endpoint': '/strategy/run',
                'parameters': {
                    'ticker': 'Stock ticker symbol (e.g., AAPL)',
                    'strategy': 'Strategy name (sma_crossover, mean_reversion, momentum)',
                    'start_date': 'Start date (YYYY-MM-DD)',
                    'end_date': 'End date (YYYY-MM-DD)',
                    'initial_capital': 'Initial capital (default: 10000)',
                    'parameters': 'Strategy-specific parameters (optional)'
                }
            }
        }
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns health status of all dependencies including:
    - Database connectivity
    - Data service availability
    - Disk space
    - System metrics (CPU, memory, uptime)
    """
    logger.debug("Health check requested")
    
    # Run basic health checks
    result = health_checker.run_all_checks(
        check_db=True,
        check_redis=False,
        check_api=False,  # Don't check yfinance directly
        check_disk=True
    )
    
    # Add data service health check
    try:
        response = requests.get(f'{DATA_SERVICE_URL}/health', timeout=5)
        result['checks']['data_service'] = {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'healthy': response.status_code == 200,
            'response_time_ms': response.elapsed.total_seconds() * 1000,
            'message': 'Data service is reachable'
        }
    except Exception as e:
        result['checks']['data_service'] = {
            'status': 'unhealthy',
            'healthy': False,
            'error': str(e),
            'message': 'Data service is unreachable'
        }
        result['status'] = 'unhealthy'  # Overall status becomes unhealthy
    
    status_code = 200 if result['status'] == 'healthy' else 503
    
    return jsonify(result), status_code


@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.route('/strategy/run', methods=['POST'])
@rate_limit(calls=10, period=60, resource='strategy_execution')  # Max 10 strategy runs per minute
@log_execution_time(logger)
def run_strategy():
    """
    Run a trading strategy
    Expected JSON: {
        "ticker": "AAPL",
        "strategy": "sma|mean_reversion|momentum",
        "start_date": "2023-01-01",
        "end_date": "2024-01-01",
        "parameters": {...},
        "initial_capital": 10000
    }
    """
    # Set correlation ID for request tracing
    correlation_id = request.headers.get('X-Correlation-ID', set_correlation_id())
    
    try:
        data = request.get_json()
        ticker = data.get('ticker', 'AAPL')
        strategy_name = data.get('strategy', 'sma')
        start_date = data.get('start_date', '2023-01-01')
        end_date = data.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        parameters = data.get('parameters', {})
        initial_capital = data.get('initial_capital', 10000)
        
        # Validate inputs
        if initial_capital <= 0:
            return jsonify({'error': 'initial_capital must be positive'}), 400
        
        if strategy_name not in ['sma', 'mean_reversion', 'momentum']:
            return jsonify({'error': f'Invalid strategy: {strategy_name}'}), 400
        
        # Validate strategy-specific parameters
        if strategy_name == 'sma':
            short_window = parameters.get('short_window', 20)
            long_window = parameters.get('long_window', 50)
            if not (MIN_WINDOW_SIZE <= short_window <= MAX_WINDOW_SIZE and MIN_WINDOW_SIZE <= long_window <= MAX_WINDOW_SIZE):
                return jsonify({'error': f'Window sizes must be between {MIN_WINDOW_SIZE} and {MAX_WINDOW_SIZE}'}), 400
            if short_window >= long_window:
                return jsonify({'error': 'short_window must be less than long_window'}), 400
        elif strategy_name == 'mean_reversion':
            window = parameters.get('window', 20)
            std_dev = parameters.get('std_dev', 2.0)
            if not (MIN_WINDOW_SIZE <= window <= MAX_WINDOW_SIZE):
                return jsonify({'error': f'Window size must be between {MIN_WINDOW_SIZE} and {MAX_WINDOW_SIZE}'}), 400
            if not (MIN_STD_DEV <= std_dev <= MAX_STD_DEV):
                return jsonify({'error': f'std_dev must be between {MIN_STD_DEV} and {MAX_STD_DEV}'}), 400
        elif strategy_name == 'momentum':
            window = parameters.get('window', 14)
            threshold = parameters.get('threshold', 0.02)
            if not (MIN_WINDOW_SIZE <= window <= MAX_WINDOW_SIZE):
                return jsonify({'error': f'Window size must be between {MIN_WINDOW_SIZE} and {MAX_WINDOW_SIZE}'}), 400
            if not (MIN_MOMENTUM_THRESHOLD <= threshold <= MAX_MOMENTUM_THRESHOLD):
                return jsonify({'error': f'threshold must be between {MIN_MOMENTUM_THRESHOLD} and {MAX_MOMENTUM_THRESHOLD}'}), 400
        
        logger.info("Starting strategy execution", extra={
            'ticker': ticker,
            'strategy': strategy_name,
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': initial_capital,
            'correlation_id': correlation_id
        })
        
        # Fetch data from data service
        logger.debug("Fetching data from data service", extra={
            'data_service_url': DATA_SERVICE_URL,
            'ticker': ticker
        })
        
        response = requests.get(
            f'{DATA_SERVICE_URL}/data/get',
            params={'ticker': ticker, 'start_date': start_date, 'end_date': end_date},
            headers={'X-Correlation-ID': correlation_id}
        )
        
        if response.status_code != 200:
            logger.error("Failed to fetch data from data service", extra={
                'status_code': response.status_code,
                'ticker': ticker
            })
            return jsonify({'error': 'Failed to fetch data from data service'}), 500
        
        market_data = response.json()['data']
        df = pd.DataFrame(market_data)
        df['date'] = pd.to_datetime(df['date'])
        
        logger.info("Data fetched successfully", extra={
            'ticker': ticker,
            'records': len(df)
        })
        
        # Select and run strategy
        if strategy_name == 'sma':
            short_window = parameters.get('short_window', 20)
            long_window = parameters.get('long_window', 50)
            logger.debug("Running SMA strategy", extra={
                'short_window': short_window,
                'long_window': long_window
            })
            strategy = SMAStrategy(df, short_window, long_window)
        elif strategy_name == 'mean_reversion':
            window = parameters.get('window', 20)
            num_std = parameters.get('num_std', 2)
            logger.debug("Running Mean Reversion strategy", extra={
                'window': window,
                'num_std': num_std
            })
            strategy = MeanReversionStrategy(df, window, num_std)
        elif strategy_name == 'momentum':
            lookback = parameters.get('lookback', 10)
            logger.debug("Running Momentum strategy", extra={
                'lookback': lookback
            })
            strategy = MomentumStrategy(df, lookback)
        else:
            logger.warning("Invalid strategy name requested", extra={
                'strategy': strategy_name
            })
            return jsonify({'error': 'Invalid strategy name'}), 400
        
        # Calculate signals
        logger.debug("Calculating trading signals")
        result_df = strategy.calculate_signals()
        
        # Get advanced parameters
        enable_risk_management = data.get('enable_risk_management', True)
        use_kelly = data.get('use_kelly', False)
        enable_stop_loss = data.get('enable_stop_loss', True)
        stop_loss_pct = data.get('stop_loss_pct', DEFAULT_STOP_LOSS_PCT)
        
        # Get custom risk parameters
        commission = data.get('commission', 0.001)
        slippage = data.get('slippage', 0.0005)
        max_position_pct = data.get('max_position_pct', 0.95)
        
        # Validate stop loss percentage
        if not (MIN_STOP_LOSS_PCT <= stop_loss_pct <= MAX_STOP_LOSS_PCT):
            return jsonify({'error': f'stop_loss_pct must be between {MIN_STOP_LOSS_PCT} ({MIN_STOP_LOSS_PCT*100}%) and {MAX_STOP_LOSS_PCT} ({MAX_STOP_LOSS_PCT*100}%)'}), 400
        
        # Run backtest
        logger.debug("Running backtest simulation", extra={
            'enable_risk_management': enable_risk_management,
            'use_kelly': use_kelly,
            'enable_stop_loss': enable_stop_loss,
            'commission': commission,
            'slippage': slippage,
            'max_position_pct': max_position_pct
        })
        backtest_results = run_backtest(
            result_df, 
            initial_capital,
            enable_risk_management=enable_risk_management,
            use_kelly=use_kelly,
            enable_stop_loss=enable_stop_loss,
            stop_loss_pct=stop_loss_pct,
            commission=commission,
            slippage=slippage,
            max_position_pct=max_position_pct
        )
        
        logger.info("Backtest completed", extra={
            'ticker': ticker,
            'strategy': strategy_name,
            'total_return': backtest_results['total_return'],
            'sharpe_ratio': backtest_results['sharpe_ratio'],
            'total_trades': backtest_results['total_trades']
        })
        
        # Track backtest metrics in Prometheus
        backtest_trades_total.labels(
            strategy=strategy_name,
            ticker=ticker
        ).inc(int(backtest_results['total_trades']))
        
        backtest_return_percent.labels(
            strategy=strategy_name,
            ticker=ticker
        ).observe(float(backtest_results['total_return']))
        
        backtest_sharpe_ratio.labels(
            strategy=strategy_name,
            ticker=ticker
        ).set(float(backtest_results['sharpe_ratio']))
        
        # Store results in database (convert numpy types to Python native types)
        session = Session()
        try:
            backtest_record = BacktestResult(
                ticker=ticker,
                strategy=strategy_name,
                start_date=datetime.strptime(start_date, '%Y-%m-%d'),
                end_date=datetime.strptime(end_date, '%Y-%m-%d'),
                initial_capital=float(backtest_results['initial_capital']),
                final_capital=float(backtest_results['final_capital']),
                total_return=float(backtest_results['total_return']),
                sharpe_ratio=float(backtest_results['sharpe_ratio']),
                max_drawdown=float(backtest_results['max_drawdown']),
                win_rate=float(backtest_results['win_rate']),
                total_trades=int(backtest_results['total_trades']),
                parameters=str(parameters)
            )
            session.add(backtest_record)
            session.commit()
            backtest_id = backtest_record.id
            
            logger.info("Backtest results stored in database", extra={
                'backtest_id': backtest_id,
                'ticker': ticker
            })
        except Exception as e:
            session.rollback()
            logger.error("Database error while storing backtest results", extra={
                'error': str(e),
                'ticker': ticker
            }, exc_info=True)
            raise
        finally:
            session.close()
        
        return jsonify({
            'message': 'Strategy executed successfully',
            'backtest_id': int(backtest_id),
            'ticker': ticker,
            'strategy': strategy_name,
            'metrics': {
                'initial_capital': float(backtest_results['initial_capital']),
                'final_capital': float(backtest_results['final_capital']),
                'total_return': float(backtest_results['total_return']),
                'sharpe_ratio': float(backtest_results['sharpe_ratio']),
                'max_drawdown': float(backtest_results['max_drawdown']),
                'win_rate': float(backtest_results['win_rate']),
                'total_trades': int(backtest_results['total_trades']),
                'rejected_trades': int(backtest_results.get('rejected_trades', 0)),
                'stop_losses_triggered': int(backtest_results.get('stop_losses_triggered', 0))
            },
            'costs': {
                'total_commission': float(backtest_results.get('costs', {}).get('total_commission', 0)),
                'total_slippage': float(backtest_results.get('costs', {}).get('total_slippage', 0)),
                'total_costs': float(backtest_results.get('costs', {}).get('total_costs', 0)),
                'costs_pct': float(backtest_results.get('costs', {}).get('costs_pct', 0))
            },
            'risk_management': backtest_results.get('risk_management', {}),
            'kelly_criterion': backtest_results.get('kelly_criterion', {}),
            'equity_curve': [float(x) for x in backtest_results['equity_curve']],
            'trades': backtest_results['trades'],
            'signals': result_df[['date', 'close', 'signal', 'position']].to_dict('records')
        }), 200
        
    except Exception as e:
        logger.error("Error running strategy", extra={
            'error': str(e),
            'ticker': ticker,
            'strategy': strategy_name
        }, exc_info=True)
        return jsonify({'error': f'Error running strategy: {str(e)}'}), 500


@app.route('/results/<int:backtest_id>', methods=['GET'])
@log_execution_time(logger)
def get_results(backtest_id):
    """Get backtest results by ID"""
    correlation_id = request.headers.get('X-Correlation-ID', set_correlation_id())
    
    try:
        logger.info("Retrieving backtest results", extra={
            'backtest_id': backtest_id,
            'correlation_id': correlation_id
        })
        
        session = Session()
        try:
            result = session.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
            
            if not result:
                logger.warning("Backtest not found", extra={'backtest_id': backtest_id})
                return jsonify({'error': 'Backtest not found'}), 404
            
            logger.info("Backtest results retrieved", extra={
                'backtest_id': backtest_id,
                'ticker': result.ticker,
                'strategy': result.strategy
            })
            
            return jsonify({
                'id': result.id,
                'ticker': result.ticker,
                'strategy': result.strategy,
                'start_date': result.start_date.strftime('%Y-%m-%d'),
                'end_date': result.end_date.strftime('%Y-%m-%d'),
                'initial_capital': result.initial_capital,
                'final_capital': result.final_capital,
                'total_return': result.total_return,
                'sharpe_ratio': result.sharpe_ratio,
                'max_drawdown': result.max_drawdown,
                'win_rate': result.win_rate,
                'total_trades': result.total_trades,
                'parameters': result.parameters,
                'created_at': result.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error("Error retrieving results", extra={
            'backtest_id': backtest_id,
            'error': str(e)
        }, exc_info=True)
        return jsonify({'error': f'Error retrieving results: {str(e)}'}), 500


@app.route('/results', methods=['GET'])
@log_execution_time(logger)
def list_results():
    """List backtest results with pagination"""
    correlation_id = request.headers.get('X-Correlation-ID', set_correlation_id())
    
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', BACKTEST_PAGE_SIZE, type=int)
        
        # Validate pagination parameters
        if page < 1:
            return jsonify({'error': 'page must be >= 1'}), 400
        if not (1 <= page_size <= 500):
            return jsonify({'error': 'page_size must be between 1 and 500'}), 400
        
        offset = (page - 1) * page_size
        
        logger.info("Listing backtest results", extra={
            'correlation_id': correlation_id,
            'page': page,
            'page_size': page_size
        })
        
        session = Session()
        try:
            # Get total count for pagination metadata
            total_count = session.query(BacktestResult).count()
            
            # Get paginated results
            results = session.query(BacktestResult)\
                .order_by(BacktestResult.created_at.desc())\
                .limit(page_size)\
                .offset(offset)\
                .all()
            
            logger.info("Backtest results listed", extra={
                'count': len(results),
                'total': total_count,
                'page': page
            })
            
            data = [{
                'id': r.id,
                'ticker': r.ticker,
                'strategy': r.strategy,
                'total_return': r.total_return,
                'sharpe_ratio': r.sharpe_ratio,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S')
            } for r in results]
            
            return jsonify({
                'results': data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size
                }
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error("Error listing results", extra={'error': str(e)}, exc_info=True)
        return jsonify({'error': f'Error listing results: {str(e)}'}), 500


if __name__ == '__main__':
    logger.info("Starting Strategy Engine", extra={
        'port': 5002,
        'debug': True,
        'db_host': DB_HOST,
        'data_service_url': DATA_SERVICE_URL
    })
    init_db()
    app.run(host='0.0.0.0', port=5002, debug=True)

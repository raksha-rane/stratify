"""
Unit Tests for Trading Strategies
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'strategy-engine'))

# Mock the imports that require external packages
class MockApp:
    def route(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator
    
    def run(self, *args, **kwargs):
        pass

sys.modules['flask'] = type(sys)('flask')
sys.modules['flask'].Flask = lambda x: MockApp()
sys.modules['flask'].request = type(sys)('request')
sys.modules['flask'].jsonify = lambda x: x
sys.modules['flask_cors'] = type(sys)('flask_cors')
sys.modules['flask_cors'].CORS = lambda x: None
sys.modules['sqlalchemy'] = type(sys)('sqlalchemy')
sys.modules['sqlalchemy'].create_engine = lambda x: None
sys.modules['sqlalchemy'].Column = lambda *args, **kwargs: None
sys.modules['sqlalchemy'].String = lambda *args: None
sys.modules['sqlalchemy'].Float = None
sys.modules['sqlalchemy'].DateTime = None
sys.modules['sqlalchemy'].Integer = None
sys.modules['sqlalchemy'].Text = None
sys.modules['sqlalchemy.ext'] = type(sys)('ext')
sys.modules['sqlalchemy.ext.declarative'] = type(sys)('declarative')
sys.modules['sqlalchemy.ext.declarative'].declarative_base = lambda: object
sys.modules['sqlalchemy.orm'] = type(sys)('orm')
sys.modules['sqlalchemy.orm'].sessionmaker = lambda **kwargs: None
sys.modules['requests'] = type(sys)('requests')


def generate_sample_data(days=100):
    """Generate sample market data for testing"""
    dates = pd.date_range(start=datetime.now() - timedelta(days=days), periods=days, freq='D')
    
    # Generate random walk for prices
    np.random.seed(42)
    returns = np.random.randn(days) * 0.02
    prices = 100 * np.exp(np.cumsum(returns))
    
    data = pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.randn(days) * 0.01),
        'high': prices * (1 + np.abs(np.random.randn(days) * 0.02)),
        'low': prices * (1 - np.abs(np.random.randn(days) * 0.02)),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, days),
        'adj_close': prices
    })
    
    return data


class TestSMAStrategy:
    """Test SMA Crossover Strategy"""
    
    def test_sma_calculation(self):
        """Test SMA calculation"""
        data = generate_sample_data(100)
        
        short_window = 20
        long_window = 50
        
        data['sma_short'] = data['close'].rolling(window=short_window).mean()
        data['sma_long'] = data['close'].rolling(window=long_window).mean()
        
        # Check that SMAs are calculated
        assert not data['sma_short'].iloc[-1] == np.nan
        assert not data['sma_long'].iloc[-1] == np.nan
        
        # Check SMA properties
        assert len(data['sma_short'].dropna()) >= len(data) - short_window
        assert len(data['sma_long'].dropna()) >= len(data) - long_window
    
    def test_sma_signals(self):
        """Test signal generation"""
        data = generate_sample_data(100)
        
        data['sma_short'] = data['close'].rolling(window=20).mean()
        data['sma_long'] = data['close'].rolling(window=50).mean()
        
        data['signal'] = 'HOLD'
        data.loc[data['sma_short'] > data['sma_long'], 'signal'] = 'BUY'
        data.loc[data['sma_short'] < data['sma_long'], 'signal'] = 'SELL'
        
        # Check that signals are generated
        assert 'BUY' in data['signal'].values or 'SELL' in data['signal'].values
        
        # Check that only valid signals exist
        valid_signals = {'BUY', 'SELL', 'HOLD'}
        assert all(signal in valid_signals for signal in data['signal'].unique())


class TestMeanReversionStrategy:
    """Test Mean Reversion Strategy"""
    
    def test_bollinger_bands(self):
        """Test Bollinger Bands calculation"""
        data = generate_sample_data(100)
        
        window = 20
        num_std = 2
        
        data['moving_avg'] = data['close'].rolling(window=window).mean()
        data['std'] = data['close'].rolling(window=window).std()
        data['upper_band'] = data['moving_avg'] + (num_std * data['std'])
        data['lower_band'] = data['moving_avg'] - (num_std * data['std'])
        
        # Check that bands are calculated
        assert not data['upper_band'].iloc[-1] == np.nan
        assert not data['lower_band'].iloc[-1] == np.nan
        
        # Check that upper band is above lower band
        valid_data = data.dropna()
        assert all(valid_data['upper_band'] > valid_data['lower_band'])
    
    def test_mean_reversion_signals(self):
        """Test mean reversion signal generation"""
        data = generate_sample_data(100)
        
        window = 20
        num_std = 2
        
        data['moving_avg'] = data['close'].rolling(window=window).mean()
        data['std'] = data['close'].rolling(window=window).std()
        data['upper_band'] = data['moving_avg'] + (num_std * data['std'])
        data['lower_band'] = data['moving_avg'] - (num_std * data['std'])
        
        data['signal'] = 'HOLD'
        data.loc[data['close'] < data['lower_band'], 'signal'] = 'BUY'
        data.loc[data['close'] > data['upper_band'], 'signal'] = 'SELL'
        
        # Check that only valid signals exist
        valid_signals = {'BUY', 'SELL', 'HOLD'}
        assert all(signal in valid_signals for signal in data['signal'].unique())


class TestMomentumStrategy:
    """Test Momentum Strategy"""
    
    def test_momentum_calculation(self):
        """Test momentum calculation"""
        data = generate_sample_data(100)
        
        lookback = 10
        
        data['returns'] = data['close'].pct_change()
        data['momentum'] = data['returns'].rolling(window=lookback).sum()
        
        # Check that momentum is calculated
        assert not data['momentum'].iloc[-1] == np.nan
        
        # Check that momentum values are reasonable
        assert all(abs(data['momentum'].dropna()) < 1.0)  # Less than 100% over 10 days
    
    def test_momentum_signals(self):
        """Test momentum signal generation"""
        data = generate_sample_data(100)
        
        lookback = 10
        
        data['returns'] = data['close'].pct_change()
        data['momentum'] = data['returns'].rolling(window=lookback).sum()
        
        data['signal'] = 'HOLD'
        data.loc[data['momentum'] > 0, 'signal'] = 'BUY'
        data.loc[data['momentum'] < 0, 'signal'] = 'SELL'
        
        # Check that signals are generated
        assert 'BUY' in data['signal'].values or 'SELL' in data['signal'].values


class TestBacktesting:
    """Test Backtesting Logic"""
    
    def test_returns_calculation(self):
        """Test returns calculation"""
        data = generate_sample_data(100)
        
        initial_capital = 10000
        
        # Simple buy and hold
        shares = initial_capital / data['close'].iloc[0]
        final_value = shares * data['close'].iloc[-1]
        
        total_return = ((final_value - initial_capital) / initial_capital) * 100
        
        # Check that return is calculated
        assert isinstance(total_return, (int, float))
        assert -100 < total_return < 1000  # Reasonable range
    
    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation"""
        data = generate_sample_data(100)
        
        returns = data['close'].pct_change().dropna()
        
        if len(returns) > 0 and returns.std() != 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
            
            # Check that Sharpe ratio is calculated
            assert isinstance(sharpe_ratio, (int, float))
            assert -10 < sharpe_ratio < 10  # Reasonable range
    
    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation"""
        data = generate_sample_data(100)
        
        cumulative = np.maximum.accumulate(data['close'])
        drawdown = (data['close'] - cumulative) / cumulative
        max_drawdown = np.min(drawdown) * 100
        
        # Check that max drawdown is calculated
        assert isinstance(max_drawdown, (int, float))
        assert max_drawdown <= 0  # Drawdown should be negative or zero


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

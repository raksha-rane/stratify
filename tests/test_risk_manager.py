"""
Unit Tests for Risk Manager Module
Tests position sizing, Kelly Criterion, and transaction cost calculations
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategy_engine.risk_manager import RiskManager, Portfolio, TransactionCosts


class TestTransactionCosts:
    """Test transaction cost calculations"""
    
    def test_calculate_commission(self):
        """Test commission calculation"""
        costs = TransactionCosts(commission_pct=0.001, slippage_pct=0.0005)
        
        # Test buy commission
        commission = costs.calculate_commission(100, 150.0)
        assert commission == 15.0  # 100 * 150 * 0.001
        
        # Test zero shares
        commission = costs.calculate_commission(0, 150.0)
        assert commission == 0
    
    def test_calculate_slippage(self):
        """Test slippage calculation"""
        costs = TransactionCosts(commission_pct=0.001, slippage_pct=0.0005)
        
        # Test slippage
        slippage = costs.calculate_slippage(100, 150.0)
        assert slippage == 7.5  # 100 * 150 * 0.0005
        
        # Test zero shares
        slippage = costs.calculate_slippage(0, 150.0)
        assert slippage == 0
    
    def test_total_costs(self):
        """Test total transaction costs"""
        costs = TransactionCosts(commission_pct=0.001, slippage_pct=0.0005)
        
        commission, slippage, total = costs.calculate_costs(100, 150.0)
        assert commission == 15.0
        assert slippage == 7.5
        assert total == 22.5


class TestPortfolio:
    """Test portfolio management"""
    
    def test_initialization(self):
        """Test portfolio initialization"""
        portfolio = Portfolio(initial_capital=10000)
        
        assert portfolio.cash == 10000
        assert portfolio.initial_capital == 10000
        assert len(portfolio.positions) == 0
        assert portfolio.total_value == 10000
    
    def test_buy_position(self):
        """Test buying a position"""
        portfolio = Portfolio(initial_capital=10000)
        costs = TransactionCosts(commission_pct=0.001, slippage_pct=0.0005)
        
        # Buy 50 shares at $100
        success, message = portfolio.buy('AAPL', 50, 100.0, costs)
        
        assert success is True
        assert 'AAPL' in portfolio.positions
        assert portfolio.positions['AAPL']['shares'] == 50
        assert portfolio.positions['AAPL']['entry_price'] == 100.0
        assert portfolio.cash < 10000  # Cash reduced by purchase + costs
    
    def test_buy_insufficient_funds(self):
        """Test buying with insufficient funds"""
        portfolio = Portfolio(initial_capital=100)
        costs = TransactionCosts(commission_pct=0.001, slippage_pct=0.0005)
        
        # Try to buy 50 shares at $100 (need $5000)
        success, message = portfolio.buy('AAPL', 50, 100.0, costs)
        
        assert success is False
        assert 'Insufficient funds' in message
    
    def test_sell_position(self):
        """Test selling a position"""
        portfolio = Portfolio(initial_capital=10000)
        costs = TransactionCosts(commission_pct=0.001, slippage_pct=0.0005)
        
        # Buy then sell
        portfolio.buy('AAPL', 50, 100.0, costs)
        initial_cash = portfolio.cash
        
        success, message = portfolio.sell('AAPL', 50, 110.0, costs)
        
        assert success is True
        assert 'AAPL' not in portfolio.positions
        assert portfolio.cash > initial_cash  # Made profit
    
    def test_sell_nonexistent_position(self):
        """Test selling a position we don't own"""
        portfolio = Portfolio(initial_capital=10000)
        costs = TransactionCosts(commission_pct=0.001, slippage_pct=0.0005)
        
        success, message = portfolio.sell('AAPL', 50, 100.0, costs)
        
        assert success is False
        assert 'No position' in message
    
    def test_update_value(self):
        """Test portfolio value update"""
        portfolio = Portfolio(initial_capital=10000)
        costs = TransactionCosts(commission_pct=0.001, slippage_pct=0.0005)
        
        # Buy position
        portfolio.buy('AAPL', 50, 100.0, costs)
        
        # Update with new price
        portfolio.update_value({'AAPL': 110.0})
        
        expected_value = portfolio.cash + (50 * 110.0)
        assert abs(portfolio.total_value - expected_value) < 0.01


class TestRiskManager:
    """Test risk management calculations"""
    
    def test_initialization(self):
        """Test risk manager initialization"""
        rm = RiskManager(commission=0.001, slippage=0.0005)
        
        assert rm.transaction_costs.commission_pct == 0.001
        assert rm.transaction_costs.slippage_pct == 0.0005
    
    def test_kelly_criterion_basic(self):
        """Test Kelly Criterion calculation"""
        rm = RiskManager()
        
        # Win rate 60%, avg win $100, avg loss $50
        kelly_fraction = rm.kelly_criterion(
            win_rate=0.6,
            avg_win=100,
            avg_loss=50
        )
        
        # Kelly = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
        # Kelly = 0.6 - (0.4 / 2) = 0.6 - 0.2 = 0.4
        assert abs(kelly_fraction - 0.4) < 0.01
    
    def test_kelly_criterion_no_edge(self):
        """Test Kelly Criterion with no edge"""
        rm = RiskManager()
        
        # Win rate 50%, equal wins and losses
        kelly_fraction = rm.kelly_criterion(
            win_rate=0.5,
            avg_win=100,
            avg_loss=100
        )
        
        # Should be 0 (no edge)
        assert kelly_fraction == 0
    
    def test_kelly_criterion_negative(self):
        """Test Kelly Criterion with negative edge"""
        rm = RiskManager()
        
        # Win rate 30%, avg win $100, avg loss $100
        kelly_fraction = rm.kelly_criterion(
            win_rate=0.3,
            avg_win=100,
            avg_loss=100
        )
        
        # Should be 0 (capped at 0)
        assert kelly_fraction == 0
    
    def test_kelly_criterion_max_cap(self):
        """Test Kelly Criterion maximum cap"""
        rm = RiskManager()
        
        # Very high edge
        kelly_fraction = rm.kelly_criterion(
            win_rate=0.9,
            avg_win=200,
            avg_loss=50
        )
        
        # Should be capped at 0.25
        assert kelly_fraction == 0.25
    
    def test_calculate_position_size_fixed(self):
        """Test fixed position sizing"""
        rm = RiskManager()
        
        shares = rm.calculate_position_size(
            capital=10000,
            price=100,
            stop_loss_pct=0.05
        )
        
        # Max risk per trade is 2% = $200
        # Stop loss 5% means we can buy 200 / (100 * 0.05) = 40 shares
        assert shares == 40
    
    def test_calculate_position_size_kelly(self):
        """Test Kelly-based position sizing"""
        rm = RiskManager()
        
        shares = rm.calculate_position_size(
            capital=10000,
            price=100,
            stop_loss_pct=0.05,
            kelly_fraction=0.2,  # 20% of capital
            use_kelly=True
        )
        
        # Kelly says use 20% of capital = $2000
        # Can buy $2000 / $100 = 20 shares
        assert shares == 20
    
    def test_calculate_position_size_kelly_with_risk(self):
        """Test Kelly position sizing with risk management"""
        rm = RiskManager()
        
        shares = rm.calculate_position_size(
            capital=10000,
            price=100,
            stop_loss_pct=0.05,
            kelly_fraction=0.5,  # 50% Kelly (will be halved)
            use_kelly=True
        )
        
        # Half-Kelly = 25% of capital = $2500
        # Can buy $2500 / $100 = 25 shares
        assert shares == 25
    
    def test_calculate_position_size_zero_capital(self):
        """Test position sizing with zero capital"""
        rm = RiskManager()
        
        shares = rm.calculate_position_size(
            capital=0,
            price=100,
            stop_loss_pct=0.05
        )
        
        assert shares == 0
    
    def test_calculate_position_size_zero_price(self):
        """Test position sizing with zero price"""
        rm = RiskManager()
        
        shares = rm.calculate_position_size(
            capital=10000,
            price=0,
            stop_loss_pct=0.05
        )
        
        assert shares == 0
    
    def test_to_dict(self):
        """Test risk manager serialization"""
        rm = RiskManager(commission=0.001, slippage=0.0005)
        
        data = rm.to_dict()
        
        assert 'max_risk_per_trade_pct' in data
        assert 'max_position_size_pct' in data
        assert 'commission_pct' in data
        assert 'slippage_pct' in data
        assert data['commission_pct'] == 0.1  # 0.001 * 100
        assert data['slippage_pct'] == 0.05   # 0.0005 * 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

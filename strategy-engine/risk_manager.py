"""
Risk Management Module for AQUA Platform

This module provides comprehensive risk management functionality including:
- Position sizing using Kelly Criterion
- Transaction cost modeling (commission + slippage)
- Trade validation and risk limits
- Portfolio risk monitoring

Usage:
    from risk_manager import RiskManager
    
    risk_mgr = RiskManager(
        commission=0.001,
        slippage=0.0005,
        max_position_pct=0.2,
        max_risk_per_trade=0.02
    )
    
    # Calculate position size
    size = risk_mgr.calculate_position_size(
        capital=10000,
        price=100,
        stop_loss_pct=0.05
    )
    
    # Validate trade
    is_valid, reason = risk_mgr.validate_trade(
        portfolio=portfolio,
        ticker='AAPL',
        quantity=50,
        price=100,
        side='BUY'
    )
"""

import sys
import os
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import math

# Add parent directory to path for common module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.logger import get_logger

logger = get_logger(__name__, service_name='strategy-engine')


@dataclass
class TransactionCosts:
    """Transaction costs breakdown"""
    commission: float = 0.0
    slippage: float = 0.0
    total_cost: float = 0.0
    effective_price: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'commission': self.commission,
            'slippage': self.slippage,
            'total_cost': self.total_cost,
            'effective_price': self.effective_price
        }


@dataclass
class Portfolio:
    """Portfolio state for risk management"""
    cash: float
    positions: Dict[str, float] = field(default_factory=dict)  # ticker -> quantity
    position_values: Dict[str, float] = field(default_factory=dict)  # ticker -> value
    
    @property
    def total_value(self) -> float:
        """Total portfolio value (cash + positions)"""
        return self.cash + sum(self.position_values.values())
    
    @property
    def invested_value(self) -> float:
        """Total value invested in positions"""
        return sum(self.position_values.values())
    
    def get_position_pct(self, ticker: str) -> float:
        """Get position as percentage of portfolio"""
        if self.total_value == 0:
            return 0.0
        return self.position_values.get(ticker, 0.0) / self.total_value


class RiskManager:
    """
    Comprehensive risk management system for trading strategies.
    
    Features:
    - Transaction cost modeling (commission + slippage)
    - Position size calculation using Kelly Criterion
    - Portfolio risk limits (max position size, max risk per trade)
    - Trade validation
    """
    
    def __init__(
        self,
        commission: float = 0.001,           # 0.1% per trade (typical for retail)
        slippage: float = 0.0005,            # 0.05% slippage (market impact)
        max_position_pct: float = 0.2,       # Max 20% portfolio in one position
        max_risk_per_trade: float = 0.02,    # Max 2% risk per trade
        min_position_value: float = 100.0,   # Minimum position value ($100)
        max_leverage: float = 1.0            # No leverage by default
    ):
        """
        Initialize risk manager with risk parameters.
        
        Args:
            commission: Commission rate as decimal (0.001 = 0.1%)
            slippage: Slippage rate as decimal (0.0005 = 0.05%)
            max_position_pct: Maximum position size as portfolio percentage
            max_risk_per_trade: Maximum risk per trade as portfolio percentage
            min_position_value: Minimum dollar value for a position
            max_leverage: Maximum leverage allowed (1.0 = no leverage)
        """
        self.commission = commission
        self.slippage = slippage
        self.max_position_pct = max_position_pct
        self.max_risk_per_trade = max_risk_per_trade
        self.min_position_value = min_position_value
        self.max_leverage = max_leverage
        
        logger.info("Risk manager initialized", extra={
            'commission': commission,
            'slippage': slippage,
            'max_position_pct': max_position_pct,
            'max_risk_per_trade': max_risk_per_trade
        })
    
    def calculate_position_size(
        self,
        capital: float,
        price: float,
        stop_loss_pct: float,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        use_kelly: bool = False
    ) -> int:
        """
        Calculate optimal position size based on risk parameters.
        
        Uses Kelly Criterion if historical performance data is provided,
        otherwise uses fixed fractional position sizing.
        
        Args:
            capital: Available capital
            price: Current price per share
            stop_loss_pct: Stop loss percentage (e.g., 0.05 for 5%)
            win_rate: Historical win rate (0.0 to 1.0)
            avg_win: Average win amount
            avg_loss: Average loss amount
            use_kelly: Whether to use Kelly Criterion
        
        Returns:
            Number of shares to buy (integer)
        """
        if capital <= 0 or price <= 0 or stop_loss_pct <= 0:
            logger.warning("Invalid inputs for position sizing", extra={
                'capital': capital,
                'price': price,
                'stop_loss_pct': stop_loss_pct
            })
            return 0
        
        # Kelly Criterion: f = (p * b - q) / b
        # where f = fraction to bet, p = win probability, q = loss probability, b = win/loss ratio
        if use_kelly and win_rate is not None and avg_win is not None and avg_loss is not None:
            if avg_loss == 0:
                kelly_fraction = 0.0
            else:
                b = abs(avg_win / avg_loss)  # Win/loss ratio
                p = win_rate
                q = 1 - win_rate
                kelly_fraction = (p * b - q) / b
                
                # Apply Kelly fraction with safety margin (half Kelly is common)
                kelly_fraction = max(0, min(kelly_fraction * 0.5, self.max_position_pct))
                
                logger.debug("Kelly Criterion calculation", extra={
                    'kelly_fraction': kelly_fraction,
                    'win_rate': win_rate,
                    'win_loss_ratio': b
                })
        else:
            # Fixed fractional based on max risk per trade
            kelly_fraction = min(self.max_risk_per_trade / stop_loss_pct, self.max_position_pct)
        
        # Calculate position value based on risk
        max_position_value = capital * self.max_position_pct
        risk_based_value = (capital * self.max_risk_per_trade) / stop_loss_pct
        
        position_value = min(max_position_value, risk_based_value)
        
        # Check minimum position value
        if position_value < self.min_position_value:
            logger.info("Position value below minimum", extra={
                'position_value': position_value,
                'min_position_value': self.min_position_value
            })
            return 0
        
        # Calculate number of shares
        shares = int(position_value / price)
        
        logger.info("Position size calculated", extra={
            'shares': shares,
            'position_value': shares * price,
            'capital': capital,
            'risk_pct': (shares * price * stop_loss_pct) / capital if capital > 0 else 0
        })
        
        return shares
    
    def apply_transaction_costs(
        self,
        price: float,
        quantity: int,
        side: str
    ) -> TransactionCosts:
        """
        Apply transaction costs (commission and slippage) to a trade.
        
        Args:
            price: Base price per share
            quantity: Number of shares
            side: 'BUY' or 'SELL'
        
        Returns:
            TransactionCosts object with breakdown
        """
        if quantity == 0:
            return TransactionCosts(
                commission=0.0,
                slippage=0.0,
                total_cost=0.0,
                effective_price=price
            )
        
        trade_value = price * quantity
        
        # Commission (fixed percentage)
        commission = trade_value * self.commission
        
        # Slippage (adverse price movement)
        # BUY: pay more, SELL: receive less
        if side.upper() == 'BUY':
            slippage_amount = trade_value * self.slippage
            effective_price = price * (1 + self.slippage)
        else:  # SELL
            slippage_amount = trade_value * self.slippage
            effective_price = price * (1 - self.slippage)
        
        total_cost = commission + slippage_amount
        
        costs = TransactionCosts(
            commission=commission,
            slippage=slippage_amount,
            total_cost=total_cost,
            effective_price=effective_price
        )
        
        logger.debug("Transaction costs applied", extra={
            'side': side,
            'quantity': quantity,
            'base_price': price,
            'effective_price': effective_price,
            'commission': commission,
            'slippage': slippage_amount,
            'total_cost': total_cost
        })
        
        return costs
    
    def validate_trade(
        self,
        portfolio: Portfolio,
        ticker: str,
        quantity: int,
        price: float,
        side: str
    ) -> Tuple[bool, str]:
        """
        Validate if a trade meets risk management criteria.
        
        Args:
            portfolio: Current portfolio state
            ticker: Stock ticker
            quantity: Number of shares
            price: Price per share
            side: 'BUY' or 'SELL'
        
        Returns:
            Tuple of (is_valid, reason)
        """
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if price <= 0:
            return False, "Price must be positive"
        
        side = side.upper()
        if side not in ['BUY', 'SELL']:
            return False, f"Invalid side: {side}"
        
        trade_value = quantity * price
        
        # Check 1: Minimum position value
        if trade_value < self.min_position_value:
            return False, f"Trade value ${trade_value:.2f} below minimum ${self.min_position_value:.2f}"
        
        # Check 2: Sufficient cash for BUY orders (including costs)
        if side == 'BUY':
            costs = self.apply_transaction_costs(price, quantity, side)
            total_required = trade_value + costs.total_cost
            
            if total_required > portfolio.cash:
                return False, f"Insufficient cash: need ${total_required:.2f}, have ${portfolio.cash:.2f}"
        
        # Check 3: Sufficient shares for SELL orders
        if side == 'SELL':
            current_position = portfolio.positions.get(ticker, 0)
            if quantity > current_position:
                return False, f"Insufficient shares: trying to sell {quantity}, have {current_position}"
        
        # Check 4: Maximum position size
        if side == 'BUY':
            # Calculate new position value
            current_value = portfolio.position_values.get(ticker, 0.0)
            new_position_value = current_value + trade_value
            
            total_portfolio_value = portfolio.total_value
            if total_portfolio_value > 0:
                new_position_pct = new_position_value / total_portfolio_value
                
                if new_position_pct > self.max_position_pct:
                    return False, (
                        f"Position would exceed max size: "
                        f"{new_position_pct*100:.1f}% > {self.max_position_pct*100:.1f}%"
                    )
        
        # Check 5: Maximum leverage
        if side == 'BUY':
            new_invested_value = portfolio.invested_value + trade_value
            total_value = portfolio.total_value
            
            if total_value > 0:
                new_leverage = new_invested_value / total_value
                
                if new_leverage > self.max_leverage:
                    return False, (
                        f"Would exceed max leverage: "
                        f"{new_leverage:.2f}x > {self.max_leverage:.2f}x"
                    )
        
        logger.debug("Trade validated successfully", extra={
            'ticker': ticker,
            'side': side,
            'quantity': quantity,
            'price': price,
            'trade_value': trade_value
        })
        
        return True, "Trade validated"
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        side: str,
        atr: Optional[float] = None,
        atr_multiplier: float = 2.0,
        fixed_pct: Optional[float] = None
    ) -> float:
        """
        Calculate stop loss price.
        
        Args:
            entry_price: Entry price
            side: 'BUY' or 'SELL'
            atr: Average True Range (for ATR-based stops)
            atr_multiplier: ATR multiplier for stop distance
            fixed_pct: Fixed percentage for stop (e.g., 0.05 for 5%)
        
        Returns:
            Stop loss price
        """
        if fixed_pct is not None:
            # Fixed percentage stop
            if side.upper() == 'BUY':
                stop_price = entry_price * (1 - fixed_pct)
            else:  # SELL (short)
                stop_price = entry_price * (1 + fixed_pct)
        elif atr is not None:
            # ATR-based stop
            stop_distance = atr * atr_multiplier
            if side.upper() == 'BUY':
                stop_price = entry_price - stop_distance
            else:  # SELL (short)
                stop_price = entry_price + stop_distance
        else:
            # Default: 2% stop
            if side.upper() == 'BUY':
                stop_price = entry_price * 0.98
            else:
                stop_price = entry_price * 1.02
        
        logger.debug("Stop loss calculated", extra={
            'entry_price': entry_price,
            'stop_price': stop_price,
            'side': side,
            'atr': atr,
            'fixed_pct': fixed_pct
        })
        
        return stop_price
    
    def calculate_risk_reward(
        self,
        entry_price: float,
        stop_loss: float,
        target_price: float,
        side: str
    ) -> float:
        """
        Calculate risk-reward ratio.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            target_price: Target/take-profit price
            side: 'BUY' or 'SELL'
        
        Returns:
            Risk-reward ratio (reward/risk)
        """
        if side.upper() == 'BUY':
            risk = entry_price - stop_loss
            reward = target_price - entry_price
        else:  # SELL (short)
            risk = stop_loss - entry_price
            reward = entry_price - target_price
        
        if risk <= 0:
            logger.warning("Invalid risk calculation", extra={
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'risk': risk
            })
            return 0.0
        
        risk_reward_ratio = reward / risk
        
        logger.debug("Risk-reward calculated", extra={
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'target_price': target_price,
            'risk': risk,
            'reward': reward,
            'ratio': risk_reward_ratio
        })
        
        return risk_reward_ratio
    
    def get_max_shares_affordable(
        self,
        cash: float,
        price: float
    ) -> int:
        """
        Calculate maximum number of shares affordable with available cash.
        Accounts for transaction costs.
        
        Args:
            cash: Available cash
            price: Price per share
        
        Returns:
            Maximum number of shares
        """
        if cash <= 0 or price <= 0:
            return 0
        
        # Account for commission and slippage
        effective_price_with_costs = price * (1 + self.slippage + self.commission)
        
        max_shares = int(cash / effective_price_with_costs)
        
        return max(0, max_shares)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export risk manager configuration as dictionary"""
        return {
            'commission': self.commission,
            'slippage': self.slippage,
            'max_position_pct': self.max_position_pct,
            'max_risk_per_trade': self.max_risk_per_trade,
            'min_position_value': self.min_position_value,
            'max_leverage': self.max_leverage
        }

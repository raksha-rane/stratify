"""
Streamlit Dashboard for AQUA
Interactive visualization and control interface
"""
import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json
import os
import sys
from pathlib import Path
from PIL import Image

# Add parent directory to path for common module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.logger import get_logger, set_correlation_id

# Initialize logger
logger = get_logger(__name__, service_name='dashboard')

# Configuration - defaults to localhost for local development
# Override with environment variables when running in Docker
DATA_SERVICE_URL = os.getenv('DATA_SERVICE_URL', 'http://localhost:5001')
STRATEGY_SERVICE_URL = os.getenv('STRATEGY_SERVICE_URL', 'http://localhost:5002')

logger.info("Dashboard starting", extra={
    'data_service_url': DATA_SERVICE_URL,
    'strategy_service_url': STRATEGY_SERVICE_URL
})

# Load custom page icon
icon_path = Path(__file__).parent / "static" / "stock.png"
try:
    page_icon = Image.open(icon_path)
except Exception as e:
    logger.warning(f"Could not load custom icon: {e}")
    page_icon = "📈"  # Fallback to emoji

st.set_page_config(
    page_title="AQUA - Automated Quantitative Unified Analyst",
    page_icon=page_icon,
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3.5rem;
        font-weight: 800;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 0.2rem;
        letter-spacing: 0.1em;
    }
    .sub-header {
        font-size: 1.1rem;
        font-weight: 400;
        color: #555;
        text-align: center;
        margin-bottom: 1.5rem;
        font-style: italic;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<div class="main-header">AQUA</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Automated Quantitative Unified Analyst</div>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar configuration
st.sidebar.title("Configuration")
st.sidebar.markdown("---")

# Popular stock tickers database
STOCK_TICKERS = {
    # Tech Giants
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "GOOGL": "Alphabet Inc. (Google)",
    "AMZN": "Amazon.com Inc.",
    "META": "Meta Platforms Inc. (Facebook)",
    "NVDA": "NVIDIA Corporation",
    "TSLA": "Tesla Inc.",
    "NFLX": "Netflix Inc.",
    "AMD": "Advanced Micro Devices",
    "INTC": "Intel Corporation",
    "ORCL": "Oracle Corporation",
    "ADBE": "Adobe Inc.",
    "CRM": "Salesforce Inc.",
    "CSCO": "Cisco Systems",
    "IBM": "IBM Corporation",
    
    # Finance
    "JPM": "JPMorgan Chase & Co.",
    "BAC": "Bank of America Corp.",
    "WFC": "Wells Fargo & Company",
    "GS": "Goldman Sachs Group",
    "MS": "Morgan Stanley",
    "C": "Citigroup Inc.",
    "V": "Visa Inc.",
    "MA": "Mastercard Inc.",
    "AXP": "American Express",
    
    # Consumer & Retail
    "WMT": "Walmart Inc.",
    "HD": "Home Depot Inc.",
    "MCD": "McDonald's Corporation",
    "NKE": "Nike Inc.",
    "SBUX": "Starbucks Corporation",
    "TGT": "Target Corporation",
    "COST": "Costco Wholesale",
    "KO": "Coca-Cola Company",
    "PEP": "PepsiCo Inc.",
    
    # Healthcare & Pharma
    "JNJ": "Johnson & Johnson",
    "UNH": "UnitedHealth Group",
    "PFE": "Pfizer Inc.",
    "ABBV": "AbbVie Inc.",
    "TMO": "Thermo Fisher Scientific",
    "MRK": "Merck & Co.",
    "LLY": "Eli Lilly and Company",
    
    # Energy
    "XOM": "Exxon Mobil Corporation",
    "CVX": "Chevron Corporation",
    "COP": "ConocoPhillips",
    
    # Telecommunications
    "T": "AT&T Inc.",
    "VZ": "Verizon Communications",
    
    # Aerospace & Defense
    "BA": "Boeing Company",
    "LMT": "Lockheed Martin",
    
    # Automotive
    "F": "Ford Motor Company",
    "GM": "General Motors Company",
    
    # Crypto ETFs
    "BTC-USD": "Bitcoin USD",
    "ETH-USD": "Ethereum USD",
    
    # Index ETFs
    "SPY": "SPDR S&P 500 ETF",
    "QQQ": "Invesco QQQ ETF",
    "DIA": "SPDR Dow Jones ETF",
    "IWM": "iShares Russell 2000 ETF",
}

# Create searchable options
ticker_options = [f"{symbol} - {name}" for symbol, name in sorted(STOCK_TICKERS.items())]
ticker_options.insert(0, "Type to search or select...")

# Ticker selection with searchable dropdown
selected_option = st.sidebar.selectbox(
    "Stock Ticker",
    options=ticker_options,
    index=0,  # Start with the hint/placeholder
    help="Search by typing stock symbol or company name"
)

# Extract ticker symbol from selection
if selected_option and selected_option != "Type to search or select...":
    ticker = selected_option.split(" - ")[0]
    st.session_state["selected_ticker"] = selected_option
else:
    ticker = None  # No default, user must select
    
# Show selected ticker info
if ticker and ticker in STOCK_TICKERS:
    st.sidebar.caption(f"{STOCK_TICKERS[ticker]}")
elif not ticker:
    st.sidebar.info("Please select a stock ticker to begin")


# Date range selection
col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=365))
with col2:
    end_date = st.date_input("End Date", value=datetime.now())

# Strategy selection
strategy = st.sidebar.selectbox(
    "Select Strategy",
    ["sma", "mean_reversion", "momentum"],
    format_func=lambda x: {
        "sma": "SMA Crossover",
        "mean_reversion": "Mean Reversion",
        "momentum": "Momentum"
    }[x]
)

# Strategy parameters
st.sidebar.markdown("### Strategy Parameters")
parameters = {}

if strategy == "sma":
    parameters['short_window'] = st.sidebar.slider(
        "Short Window", 5, 50, 20,
        help="Number of days for short-term moving average (faster signal)"
    )
    parameters['long_window'] = st.sidebar.slider(
        "Long Window", 20, 200, 50,
        help="Number of days for long-term moving average (slower signal)"
    )
elif strategy == "mean_reversion":
    parameters['window'] = st.sidebar.slider(
        "Window", 5, 50, 20,
        help="Lookback period for calculating moving average"
    )
    parameters['num_std'] = st.sidebar.slider(
        "Number of Std Dev", 1.0, 3.0, 2.0, 0.5,
        help="Number of standard deviations for bands (higher = wider bands)"
    )
elif strategy == "momentum":
    parameters['lookback'] = st.sidebar.slider(
        "Lookback Period", 5, 30, 10,
        help="Number of days to calculate momentum"
    )

# Initial capital
initial_capital = st.sidebar.number_input("Initial Capital ($)", min_value=1000, max_value=1000000, value=10000, step=1000)

# Risk Management Parameters
st.sidebar.markdown("---")
st.sidebar.markdown("### Risk Management")

enable_risk_mgmt = st.sidebar.checkbox(
    "Enable Risk Management",
    value=True,
    help="Apply transaction costs and position size limits"
)

with st.sidebar.expander("Risk Parameters"):
    commission = st.slider(
        "Commission (%)", 
        0.0, 1.0, 0.1, 0.05,
        help="Trading commission as percentage (0.1% = $1 per $1000)"
    ) / 100
    
    slippage = st.slider(
        "Slippage (%)", 
        0.0, 0.5, 0.05, 0.01,
        help="Expected slippage due to market impact"
    ) / 100
    
    max_position_pct = st.slider(
        "Max Position Size (%)", 
        5, 100, 95, 5,
        help="Maximum portfolio percentage in single position"
    ) / 100
    
    stop_loss_pct = st.slider(
        "Stop Loss (%)", 
        1, 10, 5, 1,
        help="Stop loss percentage below entry"
    ) / 100

with st.sidebar.expander("Advanced Features"):
    use_kelly = st.checkbox(
        "Use Kelly Criterion",
        value=False,
        help="Use Kelly Criterion for position sizing after 10+ trades (more aggressive)"
    )
    
    enable_stop_loss = st.checkbox(
        "Enable Automatic Stop-Loss",
        value=True,
        help="Automatically exit positions when stop-loss is hit"
    )
    
    show_risk_reward = st.checkbox(
        "Show Risk-Reward Ratios",
        value=True,
        help="Display risk-reward ratio for each trade"
    )

st.sidebar.markdown("---")

# Service Status
with st.sidebar.expander("Service Status"):
    try:
        # Check Data Service
        data_health = requests.get(f'{DATA_SERVICE_URL}/health', timeout=3)
        if data_health.status_code == 200:
            st.success("✅ Data Service: Healthy")
        else:
            st.error("❌ Data Service: Unhealthy")
    except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
        st.error(f"❌ Data Service: Unreachable ({type(e).__name__})")
    
    try:
        # Check Strategy Engine
        strategy_health = requests.get(f'{STRATEGY_SERVICE_URL}/health', timeout=3)
        if strategy_health.status_code == 200:
            st.success("✅ Strategy Engine: Healthy")
        else:
            st.error("❌ Strategy Engine: Unhealthy")
    except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
        st.error(f"❌ Strategy Engine: Unreachable ({type(e).__name__})")

st.sidebar.markdown("---")

# Action buttons
col1, col2 = st.sidebar.columns(2)
with col1:
    fetch_data_btn = st.button("Fetch Data", use_container_width=True, disabled=(ticker is None))
with col2:
    run_strategy_btn = st.button("Run Strategy", use_container_width=True, disabled=(ticker is None))

# Main content area
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Advanced Analytics", "Detailed Results", "History"])

# Fetch Data
if fetch_data_btn:
    if not ticker:
        st.sidebar.error("Please select a stock ticker first!")
    else:
        with st.spinner("Fetching market data..."):
            try:
                correlation_id = set_correlation_id()
                logger.info("Fetching data from data service", extra={
                    'ticker': ticker,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'correlation_id': correlation_id
                })
                
                response = requests.post(
                    f'{DATA_SERVICE_URL}/data/fetch',
                    json={
                        'ticker': ticker,
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d')
                    },
                    headers={'X-Correlation-ID': correlation_id},
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info("Data fetched successfully", extra={
                        'ticker': ticker,
                        'records': result['records'],
                        'correlation_id': correlation_id
                    })
                    st.sidebar.success(f"Fetched {result['records']} records for {ticker}")
                else:
                    error_msg = response.json().get('error', 'Unknown error')
                    logger.error("Failed to fetch data", extra={
                        'ticker': ticker,
                        'status_code': response.status_code,
                        'error': error_msg
                    })
                    st.sidebar.error(f"Error: {error_msg}")
            except Exception as e:
                logger.error("Connection error while fetching data", extra={
                    'ticker': ticker,
                    'error': str(e)
                }, exc_info=True)
                st.sidebar.error(f"Connection error: {str(e)}")

# Run Strategy
if run_strategy_btn:
    if not ticker:
        st.sidebar.error("Please select a stock ticker first!")
    else:
        # Validate date range
        if start_date >= end_date:
            st.sidebar.error("Start date must be before end date!")
        else:
            with st.spinner("Running strategy and backtesting..."):
                try:
                    correlation_id = set_correlation_id()
                    logger.info("Running strategy", extra={
                        'ticker': ticker,
                        'strategy': strategy,
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d'),
                        'initial_capital': initial_capital,
                        'correlation_id': correlation_id
                    })
                    
                    response = requests.post(
                        f'{STRATEGY_SERVICE_URL}/strategy/run',
                        json={
                            'ticker': ticker,
                            'strategy': strategy,
                            'start_date': start_date.strftime('%Y-%m-%d'),
                            'end_date': end_date.strftime('%Y-%m-%d'),
                            'parameters': parameters,
                            'initial_capital': initial_capital,
                            'enable_risk_management': enable_risk_mgmt,
                            'use_kelly': use_kelly,
                            'enable_stop_loss': enable_stop_loss,
                            'stop_loss_pct': stop_loss_pct,
                            'commission': commission,
                            'slippage': slippage,
                            'max_position_pct': max_position_pct
                        },
                        headers={'X-Correlation-ID': correlation_id},
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.session_state['backtest_result'] = result
                        logger.info("Strategy executed successfully", extra={
                            'ticker': ticker,
                            'strategy': strategy,
                            'backtest_id': result.get('backtest_id'),
                            'total_return': result['metrics']['total_return'],
                            'correlation_id': correlation_id
                        })
                        st.sidebar.success("Strategy executed successfully!")
                    else:
                        error_msg = response.json().get('error', 'Unknown error')
                        logger.error("Failed to run strategy", extra={
                            'ticker': ticker,
                            'strategy': strategy,
                            'status_code': response.status_code,
                            'error': error_msg
                        })
                        st.sidebar.error(f"Error: {error_msg}")
                except Exception as e:
                    logger.error("Connection error while running strategy", extra={
                        'ticker': ticker,
                        'strategy': strategy,
                        'error': str(e)
                    }, exc_info=True)
                    st.sidebar.error(f"Connection error: {str(e)}")

# Dashboard Tab
with tab1:
    st.header("Strategy Overview")
    
    # Strategy display names mapping
    strategy_names = {
        "sma": "SMA Crossover",
        "mean_reversion": "Mean Reversion",
        "momentum": "Momentum"
    }
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**Ticker:** {ticker if ticker else 'Not selected'}")
    with col2:
        st.info(f"**Strategy:** {strategy_names.get(strategy, strategy.replace('_', ' ').title())}")
    with col3:
        st.info(f"**Capital:** ${initial_capital:,.2f}")
    
    st.markdown("---")
    
    if not ticker:
        st.warning("Please select a stock ticker from the sidebar to get started!")
        st.markdown("""
        ### How to use this platform:
        1. **Select a stock** from the dropdown in the sidebar
        2. **Choose a date range** for historical data
        3. **Click "Fetch Data"** to download market data
        4. **Select a trading strategy** and adjust parameters
        5. **Click "Run Strategy"** to execute the backtest
        6. **View results** including metrics, charts, and signals
        """)
    elif 'backtest_result' in st.session_state:
        result = st.session_state['backtest_result']
        metrics = result['metrics']
        
        # Performance Metrics
        st.subheader("Performance Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Return",
                f"{metrics['total_return']:.2f}%",
                delta=f"{metrics['total_return']:.2f}%"
            )
        
        with col2:
            st.metric(
                "Sharpe Ratio",
                f"{metrics['sharpe_ratio']:.2f}",
                delta="Higher is better"
            )
        
        with col3:
            st.metric(
                "Max Drawdown",
                f"{metrics['max_drawdown']:.2f}%",
                delta=f"{metrics['max_drawdown']:.2f}%",
                delta_color="inverse"
            )
        
        with col4:
            st.metric(
                "Win Rate",
                f"{metrics['win_rate']:.2f}%"
            )
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Final Capital", f"${metrics['final_capital']:,.2f}")
        
        with col2:
            st.metric("Total Trades", metrics['total_trades'])
        
        # Stop-Loss Statistics (only show if enabled and triggered)
        if enable_stop_loss and metrics.get('stop_losses_triggered', 0) > 0:
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "Stop-Losses Triggered",
                    metrics['stop_losses_triggered'],
                    delta="Automatic exits",
                    delta_color="off"
                )
            with col2:
                stop_loss_rate = (metrics['stop_losses_triggered'] / metrics['total_trades'] * 100) if metrics['total_trades'] > 0 else 0
                st.metric(
                    "Stop-Loss Rate",
                    f"{stop_loss_rate:.1f}%"
                )
        
        st.markdown("---")
        
        # Transaction Costs Section (only show if risk management enabled)
        if enable_risk_mgmt and 'costs' in result:
            st.subheader("Transaction Costs")
            costs = result['costs']
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Total Commission",
                    f"${costs['total_commission']:.2f}"
                )
            with col2:
                st.metric(
                    "Total Slippage",
                    f"${costs['total_slippage']:.2f}"
                )
            with col3:
                total_costs = costs['total_costs']
                st.metric(
                    "Total Costs",
                    f"${total_costs:.2f}",
                    delta=f"-{costs['costs_pct']:.2f}%",
                    delta_color="inverse"
                )
            with col4:
                net_return = metrics['total_return'] - costs['costs_pct']
                st.metric(
                    "Net Return (After Costs)",
                    f"{net_return:.2f}%",
                    delta=f"-{costs['costs_pct']:.2f}% costs"
                )
        
        # Risk Management Section (only show if enabled)
        if enable_risk_mgmt and 'risk_management' in result:
            with st.expander("Risk Management Details"):
                risk_config = result['risk_management']
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Configuration:**")
                    st.write(f"- Commission Rate: {risk_config['commission']*100:.2f}%")
                    st.write(f"- Slippage Rate: {risk_config['slippage']*100:.2f}%")
                    st.write(f"- Max Position Size: {risk_config['max_position_pct']*100:.0f}%")
                    st.write(f"- Max Risk/Trade: {risk_config['max_risk_per_trade']*100:.0f}%")
                    st.write(f"- Min Position Value: ${risk_config['min_position_value']:.0f}")
                    st.write(f"- Max Leverage: {risk_config['max_leverage']:.1f}x")
                
                with col2:
                    st.write("**Trade Validation:**")
                    rejected = metrics.get('rejected_trades', 0)
                    total = metrics['total_trades'] + rejected
                    acceptance_rate = (metrics['total_trades'] / total * 100) if total > 0 else 100
                    
                    st.write(f"- Total Trades Attempted: {total}")
                    st.write(f"- Trades Executed: {metrics['total_trades']}")
                    st.write(f"- Trades Rejected: {rejected}")
                    st.write(f"- Acceptance Rate: {acceptance_rate:.1f}%")
        
        # Kelly Criterion Statistics (show if enabled)
        if use_kelly:
            st.markdown("---")
            st.subheader("Kelly Criterion Position Sizing")
            
            kelly = result.get('kelly_criterion', {})
            
            if kelly and kelly.get('total_completed_trades', 0) >= 10:
                # Kelly was used - show full statistics
                st.success("**Kelly Criterion is ACTIVE** - Position sizes optimized based on historical performance")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Completed Trades", kelly.get('total_completed_trades', 0))
                    st.metric("Winning Trades", kelly.get('winning_trades', 0))
                with col2:
                    st.metric("Win Rate", f"{kelly.get('win_rate', 0)*100:.1f}%")
                    st.metric("Avg Win", f"${kelly.get('avg_win', 0):.2f}")
                with col3:
                    st.metric("Losing Trades", kelly.get('losing_trades', 0))
                    st.metric("Avg Loss", f"${kelly.get('avg_loss', 0):.2f}")
                
                # Calculate and display Kelly percentage
                win_rate = kelly.get('win_rate', 0)
                avg_win = kelly.get('avg_win', 0)
                avg_loss = abs(kelly.get('avg_loss', 0))
                
                if avg_loss > 0:
                    win_loss_ratio = avg_win / avg_loss
                    kelly_pct = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
                    kelly_pct = max(0, min(kelly_pct, 1))  # Clamp between 0 and 1
                    
                    st.info(f"""
                    **Kelly Formula Applied:**
                    - Win/Loss Ratio: {win_loss_ratio:.2f}
                    - Optimal Position Size: {kelly_pct*100:.1f}% of capital per trade
                    - Position sizing is dynamically adjusted based on this calculation
                    """)
            else:
                # Not enough trades yet - using fixed fractional
                completed_trades = kelly.get('total_completed_trades', 0)
                remaining = 10 - completed_trades
                
                st.warning(f"""
                ⏳ **Kelly Criterion is ENABLED but not yet active**
                
                **Status:** Using fixed fractional position sizing (20% of capital)
                
                **Reason:** Need at least 10 completed trade pairs to calculate Kelly statistics
                
                **Current Progress:** {completed_trades}/10 completed trades
                
                **What happens next:** Once you have {remaining} more completed trade(s), 
                the system will automatically switch to Kelly Criterion for optimal position sizing.
                """)
                
                if completed_trades > 0:
                    st.write("**Trades so far:**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Completed Trades", completed_trades)
                        st.metric("Winning Trades", kelly.get('winning_trades', 0))
                    with col2:
                        st.metric("Losing Trades", kelly.get('losing_trades', 0))
                        if completed_trades > 0:
                            current_win_rate = kelly.get('winning_trades', 0) / completed_trades * 100
                            st.metric("Current Win Rate", f"{current_win_rate:.1f}%")
        
        st.markdown("---")
        
        # Equity Curve
        st.subheader("Equity Curve")
        
        equity_df = pd.DataFrame({
            'Day': range(len(result['equity_curve'])),
            'Portfolio Value': result['equity_curve']
        })
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=equity_df['Day'],
            y=equity_df['Portfolio Value'],
            mode='lines',
            name='Portfolio Value',
            line=dict(color='#1f77b4', width=2),
            fill='tonexty',
            fillcolor='rgba(31, 119, 180, 0.1)'
        ))
        
        fig.add_hline(
            y=initial_capital,
            line_dash="dash",
            line_color="red",
            annotation_text="Initial Capital",
            line_width=2
        )
        
        fig.update_layout(
            title="Portfolio Value Over Time",
            xaxis_title="Trading Days",
            yaxis_title="Portfolio Value ($)",
            hovermode='x unified',
            height=400,
            template="plotly_white"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Drawdown Chart
        st.subheader("Drawdown Analysis")
        
        equity_curve_np = np.array(result['equity_curve'])
        cumulative_max = np.maximum.accumulate(equity_curve_np)
        drawdown = ((equity_curve_np - cumulative_max) / cumulative_max) * 100
        
        fig_dd = go.Figure()
        fig_dd.add_trace(go.Scatter(
            x=list(range(len(drawdown))),
            y=drawdown,
            mode='lines',
            name='Drawdown',
            line=dict(color='red', width=2),
            fill='tozeroy',
            fillcolor='rgba(255, 0, 0, 0.2)'
        ))
        
        fig_dd.add_hline(
            y=metrics['max_drawdown'],
            line_dash="dash",
            line_color="darkred",
            annotation_text=f"Max Drawdown: {metrics['max_drawdown']:.2f}%",
            line_width=2
        )
        
        fig_dd.update_layout(
            title="Portfolio Drawdown Over Time",
            xaxis_title="Trading Days",
            yaxis_title="Drawdown (%)",
            hovermode='x unified',
            height=300,
            template="plotly_white"
        )
        
        st.plotly_chart(fig_dd, use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Cumulative Returns Comparison (Strategy vs Buy-and-Hold)
        st.subheader("Strategy vs Buy-and-Hold Comparison")
        
        signals_df = pd.DataFrame(result['signals'])
        if not signals_df.empty and 'close' in signals_df.columns:
            # Calculate buy-and-hold returns
            initial_price = signals_df['close'].iloc[0]
            buy_hold_values = (signals_df['close'] / initial_price) * initial_capital
            
            # Calculate strategy returns
            strategy_returns = [(val / initial_capital - 1) * 100 for val in result['equity_curve']]
            buy_hold_returns = [(val / initial_capital - 1) * 100 for val in buy_hold_values]
            
            fig_comp = go.Figure()
            
            fig_comp.add_trace(go.Scatter(
                x=list(range(len(strategy_returns))),
                y=strategy_returns,
                mode='lines',
                name='Strategy',
                line=dict(color='#1f77b4', width=2)
            ))
            
            fig_comp.add_trace(go.Scatter(
                x=list(range(len(buy_hold_returns))),
                y=buy_hold_returns,
                mode='lines',
                name='Buy & Hold',
                line=dict(color='orange', width=2, dash='dash')
            ))
            
            fig_comp.update_layout(
                title=f"Cumulative Returns: Strategy vs Buy-and-Hold ({ticker})",
                xaxis_title="Trading Days",
                yaxis_title="Cumulative Return (%)",
                hovermode='x unified',
                height=400,
                template="plotly_white",
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
            )
            
            st.plotly_chart(fig_comp, use_container_width=True)
            
            # Show comparison metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                strategy_final = strategy_returns[-1] if strategy_returns else 0
                st.metric("Strategy Return", f"{strategy_final:.2f}%")
            with col2:
                buy_hold_final = buy_hold_returns[-1] if buy_hold_returns else 0
                st.metric("Buy & Hold Return", f"{buy_hold_final:.2f}%")
            with col3:
                outperformance = strategy_final - buy_hold_final
                st.metric("Outperformance", f"{outperformance:.2f}%", 
                         delta=f"{outperformance:.2f}%")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
    else:
        st.info("Configure parameters in the sidebar and click 'Run Strategy' to see results.")

# Advanced Analytics Tab
with tab2:
    st.header("Advanced Analytics")
    
    if 'backtest_result' in st.session_state:
        result = st.session_state['backtest_result']
        metrics = result['metrics']
        signals_df = pd.DataFrame(result['signals'])
        signals_df['date'] = pd.to_datetime(signals_df['date'])
        
        # Strategy Indicator Visualization
        st.subheader("Strategy Indicators")
        
        if strategy == "sma":
            # SMA Crossover Strategy
            short_window = parameters.get('short_window', 20)
            long_window = parameters.get('long_window', 50)
            
            # Calculate SMAs
            signals_df['sma_short'] = signals_df['close'].rolling(window=short_window).mean()
            signals_df['sma_long'] = signals_df['close'].rolling(window=long_window).mean()
            
            fig_ind = go.Figure()
            
            # Price
            fig_ind.add_trace(go.Scatter(
                x=signals_df['date'],
                y=signals_df['close'],
                mode='lines',
                name='Close Price',
                line=dict(color='black', width=2)
            ))
            
            # Short SMA
            fig_ind.add_trace(go.Scatter(
                x=signals_df['date'],
                y=signals_df['sma_short'],
                mode='lines',
                name=f'SMA {short_window}',
                line=dict(color='blue', width=1.5)
            ))
            
            # Long SMA
            fig_ind.add_trace(go.Scatter(
                x=signals_df['date'],
                y=signals_df['sma_long'],
                mode='lines',
                name=f'SMA {long_window}',
                line=dict(color='orange', width=1.5)
            ))
            
            # Buy signals
            buy_signals = signals_df[signals_df['signal'] == 'BUY']
            if not buy_signals.empty:
                fig_ind.add_trace(go.Scatter(
                    x=buy_signals['date'],
                    y=buy_signals['close'],
                    mode='markers',
                    name='Buy Signal',
                    marker=dict(color='green', size=12, symbol='triangle-up')
                ))
            
            # Sell signals
            sell_signals = signals_df[signals_df['signal'] == 'SELL']
            if not sell_signals.empty:
                fig_ind.add_trace(go.Scatter(
                    x=sell_signals['date'],
                    y=sell_signals['close'],
                    mode='markers',
                    name='Sell Signal',
                    marker=dict(color='red', size=12, symbol='triangle-down')
                ))
            
            fig_ind.update_layout(
                title=f"SMA Crossover Strategy ({short_window}/{long_window})",
                xaxis_title="Date",
                yaxis_title="Price ($)",
                hovermode='x unified',
                height=500,
                template="plotly_white"
            )
            
            st.plotly_chart(fig_ind, use_container_width=True)
            
        elif strategy == "mean_reversion":
            # Mean Reversion Strategy
            window = parameters.get('window', 20)
            num_std = parameters.get('num_std', 2.0)
            
            # Calculate bands
            signals_df['ma'] = signals_df['close'].rolling(window=window).mean()
            signals_df['std'] = signals_df['close'].rolling(window=window).std()
            signals_df['upper_band'] = signals_df['ma'] + (signals_df['std'] * num_std)
            signals_df['lower_band'] = signals_df['ma'] - (signals_df['std'] * num_std)
            
            fig_ind = go.Figure()
            
            # Upper band
            fig_ind.add_trace(go.Scatter(
                x=signals_df['date'],
                y=signals_df['upper_band'],
                mode='lines',
                name='Upper Band',
                line=dict(color='red', width=1, dash='dash')
            ))
            
            # Moving average
            fig_ind.add_trace(go.Scatter(
                x=signals_df['date'],
                y=signals_df['ma'],
                mode='lines',
                name=f'MA {window}',
                line=dict(color='blue', width=2)
            ))
            
            # Lower band
            fig_ind.add_trace(go.Scatter(
                x=signals_df['date'],
                y=signals_df['lower_band'],
                mode='lines',
                name='Lower Band',
                line=dict(color='green', width=1, dash='dash')
            ))
            
            # Price
            fig_ind.add_trace(go.Scatter(
                x=signals_df['date'],
                y=signals_df['close'],
                mode='lines',
                name='Close Price',
                line=dict(color='black', width=2)
            ))
            
            # Buy signals
            buy_signals = signals_df[signals_df['signal'] == 'BUY']
            if not buy_signals.empty:
                fig_ind.add_trace(go.Scatter(
                    x=buy_signals['date'],
                    y=buy_signals['close'],
                    mode='markers',
                    name='Buy Signal',
                    marker=dict(color='green', size=12, symbol='triangle-up')
                ))
            
            # Sell signals
            sell_signals = signals_df[signals_df['signal'] == 'SELL']
            if not sell_signals.empty:
                fig_ind.add_trace(go.Scatter(
                    x=sell_signals['date'],
                    y=sell_signals['close'],
                    mode='markers',
                    name='Sell Signal',
                    marker=dict(color='red', size=12, symbol='triangle-down')
                ))
            
            fig_ind.update_layout(
                title=f"Mean Reversion Strategy (±{num_std}σ Bands)",
                xaxis_title="Date",
                yaxis_title="Price ($)",
                hovermode='x unified',
                height=500,
                template="plotly_white"
            )
            
            st.plotly_chart(fig_ind, use_container_width=True)
            
        elif strategy == "momentum":
            # Momentum Strategy
            lookback = parameters.get('lookback', 10)
            
            # Calculate momentum
            signals_df['returns'] = signals_df['close'].pct_change()
            signals_df['momentum'] = signals_df['returns'].rolling(window=lookback).sum()
            
            # Create subplots
            fig_ind = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.1,
                subplot_titles=(f'{ticker} Price', 'Momentum Indicator'),
                row_heights=[0.7, 0.3]
            )
            
            # Price chart
            fig_ind.add_trace(go.Scatter(
                x=signals_df['date'],
                y=signals_df['close'],
                mode='lines',
                name='Close Price',
                line=dict(color='black', width=2)
            ), row=1, col=1)
            
            # Buy signals
            buy_signals = signals_df[signals_df['signal'] == 'BUY']
            if not buy_signals.empty:
                fig_ind.add_trace(go.Scatter(
                    x=buy_signals['date'],
                    y=buy_signals['close'],
                    mode='markers',
                    name='Buy Signal',
                    marker=dict(color='green', size=10, symbol='triangle-up')
                ), row=1, col=1)
            
            # Sell signals
            sell_signals = signals_df[signals_df['signal'] == 'SELL']
            if not sell_signals.empty:
                fig_ind.add_trace(go.Scatter(
                    x=sell_signals['date'],
                    y=sell_signals['close'],
                    mode='markers',
                    name='Sell Signal',
                    marker=dict(color='red', size=10, symbol='triangle-down')
                ), row=1, col=1)
            
            # Momentum indicator
            fig_ind.add_trace(go.Scatter(
                x=signals_df['date'],
                y=signals_df['momentum'],
                mode='lines',
                name='Momentum',
                line=dict(color='purple', width=2),
                fill='tozeroy',
                fillcolor='rgba(128, 0, 128, 0.2)'
            ), row=2, col=1)
            
            # Zero line
            fig_ind.add_hline(
                y=0,
                line_dash="dash",
                line_color="gray",
                row=2, col=1
            )
            
            fig_ind.update_xaxes(title_text="Date", row=2, col=1)
            fig_ind.update_yaxes(title_text="Price ($)", row=1, col=1)
            fig_ind.update_yaxes(title_text="Momentum", row=2, col=1)
            
            fig_ind.update_layout(
                height=600,
                template="plotly_white",
                showlegend=True,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig_ind, use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Returns Distribution
        st.subheader("Returns Distribution")
        
        equity_curve_np = np.array(result['equity_curve'])
        returns = np.diff(equity_curve_np) / equity_curve_np[:-1] * 100  # Daily returns in %
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Histogram
            fig_hist = go.Figure()
            
            fig_hist.add_trace(go.Histogram(
                x=returns,
                nbinsx=30,
                name='Returns',
                marker_color='#1f77b4',
                opacity=0.7
            ))
            
            fig_hist.update_layout(
                title="Daily Returns Distribution",
                xaxis_title="Return (%)",
                yaxis_title="Frequency",
                height=350,
                template="plotly_white",
                showlegend=False
            )
            
            st.plotly_chart(fig_hist, use_container_width=True)
        
        with col2:
            # Statistics
            st.markdown("**Distribution Statistics**")
            st.write(f"- **Mean Return**: {np.mean(returns):.3f}%")
            st.write(f"- **Median Return**: {np.median(returns):.3f}%")
            st.write(f"- **Std Deviation**: {np.std(returns):.3f}%")
            st.write(f"- **Skewness**: {pd.Series(returns).skew():.3f}")
            st.write(f"- **Min Return**: {np.min(returns):.3f}%")
            st.write(f"- **Max Return**: {np.max(returns):.3f}%")
            
            # Win/Loss statistics
            positive_returns = returns[returns > 0]
            negative_returns = returns[returns < 0]
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Win/Loss Analysis**")
            st.write(f"- **Positive Days**: {len(positive_returns)} ({len(positive_returns)/len(returns)*100:.1f}%)")
            st.write(f"- **Negative Days**: {len(negative_returns)} ({len(negative_returns)/len(returns)*100:.1f}%)")
            st.write(f"- **Avg Positive**: {np.mean(positive_returns):.3f}%" if len(positive_returns) > 0 else "- **Avg Positive**: N/A")
            st.write(f"- **Avg Negative**: {np.mean(negative_returns):.3f}%" if len(negative_returns) > 0 else "- **Avg Negative**: N/A")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Monthly Returns Heatmap
        st.subheader("Monthly Returns Heatmap")
        
        if not signals_df.empty and len(result['equity_curve']) == len(signals_df):
            # Add portfolio values to signals_df
            signals_df['portfolio_value'] = result['equity_curve']
            signals_df['returns'] = signals_df['portfolio_value'].pct_change() * 100
            
            # Extract year and month
            signals_df['year'] = signals_df['date'].dt.year
            signals_df['month'] = signals_df['date'].dt.month
            
            # Calculate monthly returns
            monthly_returns = signals_df.groupby(['year', 'month'])['returns'].sum().reset_index()
            
            if not monthly_returns.empty:
                # Pivot for heatmap
                heatmap_data = monthly_returns.pivot(index='year', columns='month', values='returns')
                
                # Month names
                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                
                fig_heatmap = go.Figure(data=go.Heatmap(
                    z=heatmap_data.values,
                    x=[month_names[i-1] for i in heatmap_data.columns],
                    y=heatmap_data.index,
                    colorscale='RdYlGn',
                    zmid=0,
                    text=heatmap_data.values,
                    texttemplate='%{text:.1f}%',
                    textfont={"size": 10},
                    colorbar=dict(title="Return (%)")
                ))
                
                fig_heatmap.update_layout(
                    title="Monthly Returns by Year",
                    xaxis_title="Month",
                    yaxis_title="Year",
                    height=300,
                    template="plotly_white"
                )
                
                st.plotly_chart(fig_heatmap, use_container_width=True)
            else:
                st.info("Insufficient data for monthly returns heatmap")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Trade Analysis
        if result.get('trades'):
            st.subheader("Trade Analysis")
            
            trades_df = pd.DataFrame(result['trades'])
            
            # Filter for completed trades (Buy-Sell pairs)
            buy_trades = trades_df[trades_df['signal'].isin(['BUY'])].copy()
            sell_trades = trades_df[trades_df['signal'].isin(['SELL', 'STOP_LOSS'])].copy()
            
            if not buy_trades.empty and not sell_trades.empty:
                # Calculate trade durations and PnL
                trade_analysis = []
                for i in range(min(len(buy_trades), len(sell_trades))):
                    buy_trade = buy_trades.iloc[i]
                    sell_trade = sell_trades.iloc[i]
                    
                    duration = (pd.to_datetime(sell_trade['date']) - pd.to_datetime(buy_trade['date'])).days
                    pnl = sell_trade.get('pnl', 0)
                    
                    trade_analysis.append({
                        'duration': duration,
                        'pnl': pnl,
                        'is_win': pnl > 0,
                        'entry_date': buy_trade['date'],
                        'exit_date': sell_trade['date']
                    })
                
                if trade_analysis:
                    trade_df = pd.DataFrame(trade_analysis)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Trade Duration Histogram
                        fig_duration = go.Figure()
                        
                        fig_duration.add_trace(go.Histogram(
                            x=trade_df['duration'],
                            nbinsx=20,
                            name='Trade Duration',
                            marker_color='#ff7f0e',
                            opacity=0.7
                        ))
                        
                        fig_duration.update_layout(
                            title="Trade Duration Distribution",
                            xaxis_title="Days Held",
                            yaxis_title="Number of Trades",
                            height=350,
                            template="plotly_white",
                            showlegend=False
                        )
                        
                        st.plotly_chart(fig_duration, use_container_width=True)
                        
                        # Duration stats
                        st.markdown("**Duration Statistics**")
                        st.write(f"- **Avg Duration**: {trade_df['duration'].mean():.1f} days")
                        st.write(f"- **Median**: {trade_df['duration'].median():.0f} days")
                        st.write(f"- **Min**: {trade_df['duration'].min():.0f} days")
                        st.write(f"- **Max**: {trade_df['duration'].max():.0f} days")
                    
                    with col2:
                        # PnL Scatter Plot
                        fig_scatter = go.Figure()
                        
                        wins = trade_df[trade_df['is_win']]
                        losses = trade_df[~trade_df['is_win']]
                        
                        if not wins.empty:
                            fig_scatter.add_trace(go.Scatter(
                                x=wins['duration'],
                                y=wins['pnl'],
                                mode='markers',
                                name='Winning Trades',
                                marker=dict(color='green', size=10, opacity=0.6)
                            ))
                        
                        if not losses.empty:
                            fig_scatter.add_trace(go.Scatter(
                                x=losses['duration'],
                                y=losses['pnl'],
                                mode='markers',
                                name='Losing Trades',
                                marker=dict(color='red', size=10, opacity=0.6)
                            ))
                        
                        fig_scatter.add_hline(y=0, line_dash="dash", line_color="gray")
                        
                        fig_scatter.update_layout(
                            title="Trade PnL vs Duration",
                            xaxis_title="Days Held",
                            yaxis_title="Profit/Loss ($)",
                            height=350,
                            template="plotly_white"
                        )
                        
                        st.plotly_chart(fig_scatter, use_container_width=True)
                        
                        # PnL stats
                        st.markdown("**PnL Statistics**")
                        st.write(f"- **Total Trades**: {len(trade_df)}")
                        st.write(f"- **Winning Trades**: {len(wins)} ({len(wins)/len(trade_df)*100:.1f}%)")
                        st.write(f"- **Avg Win**: ${wins['pnl'].mean():.2f}" if not wins.empty else "- **Avg Win**: N/A")
                        st.write(f"- **Avg Loss**: ${losses['pnl'].mean():.2f}" if not losses.empty else "- **Avg Loss**: N/A")
        
    else:
        st.info("Run a strategy first to see advanced analytics.")

# Detailed Results Tab
with tab3:
    st.header("Detailed Results")
    
    if 'backtest_result' in st.session_state:
        result = st.session_state['backtest_result']
        
        # Export functionality
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("Export Results"):
                # Prepare export data
                export_data = {
                    'ticker': result['ticker'],
                    'strategy': result['strategy'],
                    'metrics': result['metrics'],
                    'costs': result.get('costs', {}),
                    'signals': result.get('signals', [])
                }
                
                # Convert to CSV for trades
                if result.get('trades'):
                    trades_df = pd.DataFrame(result['trades'])
                    csv = trades_df.to_csv(index=False)
                    st.download_button(
                        label="Download Trades CSV",
                        data=csv,
                        file_name=f"{result['ticker']}_{result['strategy']}_trades.csv",
                        mime="text/csv"
                    )
        
        # Trading Signals
        st.subheader("Trading Signals")
        
        signals_df = pd.DataFrame(result['signals'])
        signals_df['date'] = pd.to_datetime(signals_df['date'])
        
        # Filter only actual trade signals (not HOLD)
        trade_signals = signals_df[signals_df['signal'] != 'HOLD'].copy()
        
        if not trade_signals.empty:
            st.dataframe(
                trade_signals[['date', 'close', 'signal']].head(20),
                use_container_width=True
            )
        else:
            st.warning("No trade signals generated for this period.")
        
        st.markdown("---")
        
        # Price Chart with Signals
        st.subheader("Price Chart with Trading Signals")
        
        fig = go.Figure()
        
        # Price line
        fig.add_trace(go.Scatter(
            x=signals_df['date'],
            y=signals_df['close'],
            mode='lines',
            name='Close Price',
            line=dict(color='blue', width=1)
        ))
        
        # Buy signals
        buy_signals = signals_df[signals_df['signal'] == 'BUY']
        if not buy_signals.empty:
            fig.add_trace(go.Scatter(
                x=buy_signals['date'],
                y=buy_signals['close'],
                mode='markers',
                name='Buy Signal',
                marker=dict(color='green', size=10, symbol='triangle-up')
            ))
        
        # Sell signals
        sell_signals = signals_df[signals_df['signal'] == 'SELL']
        if not sell_signals.empty:
            fig.add_trace(go.Scatter(
                x=sell_signals['date'],
                y=sell_signals['close'],
                mode='markers',
                name='Sell Signal',
                marker=dict(color='red', size=10, symbol='triangle-down')
            ))
        
        fig.update_layout(
            title=f"{ticker} Price with Trading Signals",
            xaxis_title="Date",
            yaxis_title="Price ($)",
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Trade Details
        st.subheader("Trade Details")
        
        if result['trades']:
            trades_df = pd.DataFrame(result['trades'])
            trades_df['date'] = pd.to_datetime(trades_df['date'], errors='coerce')
            
            # Add calculated columns if they exist
            if 'commission' in trades_df.columns:
                total_commission = trades_df['commission'].sum()
                total_slippage = trades_df['slippage'].sum()
                total_costs = total_commission + total_slippage
                st.info(f"Total Costs: Commission \${total_commission:.2f} + Slippage \${total_slippage:.2f} = \${total_costs:.2f}")
            
            # Show risk-reward statistics for BUY trades (only if enabled)
            if show_risk_reward:
                buy_trades = trades_df[trades_df['signal'] == 'BUY']
                if not buy_trades.empty and 'risk_reward_ratio' in buy_trades.columns:
                    avg_rr = buy_trades['risk_reward_ratio'].mean()
                    st.info(f"Average Risk-Reward Ratio: {avg_rr:.2f}:1 (Higher is better)")
            
            # Format columns for display
            format_dict = {
                'price': '${:.2f}',
                'effective_price': '${:.2f}',
                'commission': '${:.2f}',
                'slippage': '${:.2f}',
                'portfolio_value': '${:,.2f}'
            }
            
            # Add conditional formatting for specific columns
            if 'cost' in trades_df.columns:
                format_dict['cost'] = '${:.2f}'
            if 'proceeds' in trades_df.columns:
                format_dict['proceeds'] = '${:.2f}'
            if 'pnl' in trades_df.columns:
                format_dict['pnl'] = '${:.2f}'
            
            # Conditionally show/hide risk-reward related columns
            if show_risk_reward:
                # Include R:R columns in display
                if 'stop_loss' in trades_df.columns:
                    format_dict['stop_loss'] = '${:.2f}'
                if 'target_price' in trades_df.columns:
                    format_dict['target_price'] = '${:.2f}'
                if 'risk_reward_ratio' in trades_df.columns:
                    format_dict['risk_reward_ratio'] = '{:.2f}'
            else:
                # Hide R:R columns
                cols_to_drop = ['stop_loss', 'target_price', 'risk_reward_ratio']
                trades_df = trades_df.drop(columns=[col for col in cols_to_drop if col in trades_df.columns])
            
            # Display trades with formatting
            st.dataframe(
                trades_df.style.format(format_dict),
                use_container_width=True
            )
        else:
            st.warning("No trades executed during this period.")
            
    else:
        st.info("Run a strategy first to see detailed results.")

# History Tab
with tab4:
    st.header("Backtest History")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Refresh History", use_container_width=True):
            try:
                response = requests.get(f'{STRATEGY_SERVICE_URL}/results', timeout=10)
                if response.status_code == 200:
                    st.session_state['history'] = response.json()['results']
                    st.success("History refreshed!")
            except Exception as e:
                st.error(f"Error fetching history: {str(e)}")
    
    if 'history' in st.session_state:
        history_df = pd.DataFrame(st.session_state['history'])
        
        if not history_df.empty:
            # Add some metrics at the top
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Backtests", len(history_df))
            with col2:
                avg_return = history_df['total_return'].mean() if 'total_return' in history_df.columns else 0
                st.metric("Avg Return", f"{avg_return:.2f}%")
            with col3:
                avg_sharpe = history_df['sharpe_ratio'].mean() if 'sharpe_ratio' in history_df.columns else 0
                st.metric("Avg Sharpe", f"{avg_sharpe:.2f}")
            with col4:
                best_return = history_df['total_return'].max() if 'total_return' in history_df.columns else 0
                st.metric("Best Return", f"{best_return:.2f}%")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Display history table
            display_columns = ['id', 'ticker', 'strategy', 'total_return', 'sharpe_ratio', 'max_drawdown', 'created_at']
            available_columns = [col for col in display_columns if col in history_df.columns]
            
            st.dataframe(
                history_df[available_columns].sort_values(by='id', ascending=False),
                use_container_width=True,
                height=400
            )
            
            # Performance comparison chart
            if len(history_df) > 1 and 'total_return' in history_df.columns:
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("Performance Comparison")
                
                fig_comp = go.Figure()
                
                fig_comp.add_trace(go.Bar(
                    x=[f"{row['ticker']}-{row['strategy']}" for _, row in history_df.iterrows()],
                    y=history_df['total_return'],
                    marker_color=['green' if x > 0 else 'red' for x in history_df['total_return']],
                    text=history_df['total_return'].round(2),
                    textposition='outside'
                ))
                
                fig_comp.update_layout(
                    title="Returns Across All Backtests",
                    xaxis_title="Backtest",
                    yaxis_title="Total Return (%)",
                    height=400,
                    template="plotly_white",
                    showlegend=False
                )
                
                st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info("No backtest history available yet. Run some strategies to see them here!")
    else:
        st.info("Click 'Refresh History' to load previous backtests.")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "AQUA - Automated Quantitative Unified Analyst | "
    "For simulation and educational purposes only | "
    "© 2025"
    "</div>",
    unsafe_allow_html=True
)

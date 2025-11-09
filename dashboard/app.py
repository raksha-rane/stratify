"""
Streamlit Dashboard for AQTS
Interactive visualization and control interface
"""
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
import sys

# Add parent directory to path for common module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.logger import get_logger, set_correlation_id

# Initialize logger
logger = get_logger(__name__, service_name='dashboard')

# Configuration - use Docker service names when running in container
DATA_SERVICE_URL = os.getenv('DATA_SERVICE_URL', 'http://data-service:5001')
STRATEGY_SERVICE_URL = os.getenv('STRATEGY_SERVICE_URL', 'http://strategy-engine:5002')

logger.info("Dashboard starting", extra={
    'data_service_url': DATA_SERVICE_URL,
    'strategy_service_url': STRATEGY_SERVICE_URL
})

st.set_page_config(
    page_title="AQTS - Automated Quant Trading Strategy",
    page_icon="📈",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
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
st.markdown('<div class="main-header">📈 Automated Quant Trading Strategy Platform</div>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar configuration
st.sidebar.title("🎯 Configuration")
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
    st.sidebar.caption(f"📊 {STOCK_TICKERS[ticker]}")
elif not ticker:
    st.sidebar.info("👆 Please select a stock ticker to begin")


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
    parameters['short_window'] = st.sidebar.slider("Short Window", 5, 50, 20)
    parameters['long_window'] = st.sidebar.slider("Long Window", 20, 200, 50)
elif strategy == "mean_reversion":
    parameters['window'] = st.sidebar.slider("Window", 5, 50, 20)
    parameters['num_std'] = st.sidebar.slider("Number of Std Dev", 1.0, 3.0, 2.0, 0.5)
elif strategy == "momentum":
    parameters['lookback'] = st.sidebar.slider("Lookback Period", 5, 30, 10)

# Initial capital
initial_capital = st.sidebar.number_input("Initial Capital ($)", min_value=1000, max_value=1000000, value=10000, step=1000)

st.sidebar.markdown("---")

# Action buttons
col1, col2 = st.sidebar.columns(2)
with col1:
    fetch_data_btn = st.button("📥 Fetch Data", use_container_width=True, disabled=(ticker is None))
with col2:
    run_strategy_btn = st.button("🚀 Run Strategy", use_container_width=True, disabled=(ticker is None))

# Main content area
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📈 Results", "📚 History"])

# Fetch Data
if fetch_data_btn:
    if not ticker:
        st.sidebar.error("⚠️ Please select a stock ticker first!")
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
                    st.sidebar.success(f"✅ Fetched {result['records']} records for {ticker}")
                else:
                    error_msg = response.json().get('error', 'Unknown error')
                    logger.error("Failed to fetch data", extra={
                        'ticker': ticker,
                        'status_code': response.status_code,
                        'error': error_msg
                    })
                    st.sidebar.error(f"❌ Error: {error_msg}")
            except Exception as e:
                logger.error("Connection error while fetching data", extra={
                    'ticker': ticker,
                    'error': str(e)
                }, exc_info=True)
                st.sidebar.error(f"❌ Connection error: {str(e)}")

# Run Strategy
if run_strategy_btn:
    if not ticker:
        st.sidebar.error("⚠️ Please select a stock ticker first!")
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
                        'initial_capital': initial_capital
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
                    st.sidebar.success("✅ Strategy executed successfully!")
                else:
                    error_msg = response.json().get('error', 'Unknown error')
                    logger.error("Failed to run strategy", extra={
                        'ticker': ticker,
                        'strategy': strategy,
                        'status_code': response.status_code,
                        'error': error_msg
                    })
                    st.sidebar.error(f"❌ Error: {error_msg}")
            except Exception as e:
                logger.error("Connection error while running strategy", extra={
                    'ticker': ticker,
                    'strategy': strategy,
                    'error': str(e)
                }, exc_info=True)
                st.sidebar.error(f"❌ Connection error: {str(e)}")

# Dashboard Tab
with tab1:
    st.header("📊 Strategy Overview")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**Ticker:** {ticker if ticker else 'Not selected'}")
    with col2:
        st.info(f"**Strategy:** {strategy.replace('_', ' ').title()}")
    with col3:
        st.info(f"**Capital:** ${initial_capital:,.2f}")
    
    st.markdown("---")
    
    if not ticker:
        st.warning("👆 Please select a stock ticker from the sidebar to get started!")
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
        st.subheader("📈 Performance Metrics")
        
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
        
        st.markdown("---")
        
        # Equity Curve
        st.subheader("💰 Equity Curve")
        
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
            line=dict(color='#1f77b4', width=2)
        ))
        
        fig.add_hline(
            y=initial_capital,
            line_dash="dash",
            line_color="red",
            annotation_text="Initial Capital"
        )
        
        fig.update_layout(
            title="Portfolio Value Over Time",
            xaxis_title="Trading Days",
            yaxis_title="Portfolio Value ($)",
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("👆 Configure parameters in the sidebar and click 'Run Strategy' to see results.")

# Results Tab
with tab2:
    st.header("📈 Detailed Results")
    
    if 'backtest_result' in st.session_state:
        result = st.session_state['backtest_result']
        
        # Trading Signals
        st.subheader("🎯 Trading Signals")
        
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
        st.subheader("📊 Price Chart with Trading Signals")
        
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
        st.subheader("💼 Trade Details")
        
        if result['trades']:
            trades_df = pd.DataFrame(result['trades'])
            trades_df['date'] = pd.to_datetime(trades_df['date'], format='mixed', errors='coerce')
            st.dataframe(trades_df, use_container_width=True)
        else:
            st.warning("No trades executed during this period.")
            
    else:
        st.info("👆 Run a strategy first to see detailed results.")

# History Tab
with tab3:
    st.header("📚 Backtest History")
    
    if st.button("🔄 Refresh History"):
        try:
            response = requests.get(f'{STRATEGY_SERVICE_URL}/results', timeout=10)
            if response.status_code == 200:
                st.session_state['history'] = response.json()['results']
        except Exception as e:
            st.error(f"Error fetching history: {str(e)}")
    
    if 'history' in st.session_state:
        history_df = pd.DataFrame(st.session_state['history'])
        
        if not history_df.empty:
            st.dataframe(
                history_df[['id', 'ticker', 'strategy', 'total_return', 'sharpe_ratio', 'created_at']],
                use_container_width=True
            )
        else:
            st.info("No backtest history available yet.")
    else:
        st.info("Click 'Refresh History' to load previous backtests.")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "AQTS - Automated Quant Trading Strategy Platform | "
    "For simulation and educational purposes only | "
    "© 2025"
    "</div>",
    unsafe_allow_html=True
)

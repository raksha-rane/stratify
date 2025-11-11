-- Initialize AQUA Database Schema

-- Create market_data table
CREATE TABLE IF NOT EXISTS market_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date TIMESTAMP NOT NULL,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume FLOAT,
    adj_close FLOAT,
    UNIQUE(ticker, date)
);

CREATE INDEX idx_market_data_ticker_date ON market_data(ticker, date);

-- Create trades table
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    date TIMESTAMP NOT NULL,
    signal VARCHAR(10) NOT NULL,
    price FLOAT,
    quantity FLOAT,
    portfolio_value FLOAT
);

CREATE INDEX idx_trades_ticker_strategy ON trades(ticker, strategy);

-- Create backtest_results table
CREATE TABLE IF NOT EXISTS backtest_results (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    initial_capital FLOAT,
    final_capital FLOAT,
    total_return FLOAT,
    sharpe_ratio FLOAT,
    max_drawdown FLOAT,
    win_rate FLOAT,
    total_trades INTEGER,
    parameters TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_backtest_ticker_strategy ON backtest_results(ticker, strategy);
CREATE INDEX idx_backtest_created_at ON backtest_results(created_at DESC);

-- Create data_quality_logs table
CREATE TABLE IF NOT EXISTS data_quality_logs (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    validation_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_valid BOOLEAN NOT NULL,
    critical_issues JSONB,
    warnings JSONB,
    stats JSONB,
    record_count INTEGER,
    quality_score INTEGER DEFAULT 0
);

CREATE INDEX idx_quality_logs_ticker ON data_quality_logs(ticker);
CREATE INDEX idx_quality_logs_date ON data_quality_logs(validation_date DESC);
CREATE INDEX idx_quality_logs_valid ON data_quality_logs(is_valid);

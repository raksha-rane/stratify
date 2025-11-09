# API Documentation

## Overview

The AQTS platform exposes two main APIs:
1. **Data Service API** - Port 5001
2. **Strategy Engine API** - Port 5002

All APIs return JSON responses and accept JSON payloads.

---

## Data Service API

Base URL: `http://localhost:5001`

### Health Check

Check if the service is running.

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "service": "data-service"
}
```

---

### Fetch Market Data

Fetch historical stock data from Yahoo Finance and store in database.

**Endpoint**: `POST /data/fetch`

**Request Body**:
```json
{
  "ticker": "AAPL",
  "start_date": "2023-01-01",
  "end_date": "2024-01-01"
}
```

**Response**:
```json
{
  "message": "Data fetched and stored successfully",
  "ticker": "AAPL",
  "records": 252,
  "start_date": "2023-01-01",
  "end_date": "2024-01-01",
  "sample_data": [...]
}
```

**Status Codes**:
- 200: Success
- 404: No data found for ticker
- 500: Server error

---

### Get Stored Data

Retrieve stored market data from database.

**Endpoint**: `GET /data/get`

**Query Parameters**:
- `ticker` (required): Stock ticker symbol
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)

**Example**:
```
GET /data/get?ticker=AAPL&start_date=2023-01-01&end_date=2024-01-01
```

**Response**:
```json
{
  "ticker": "AAPL",
  "records": 252,
  "data": [
    {
      "date": "2023-01-03",
      "open": 130.28,
      "high": 130.90,
      "low": 124.17,
      "close": 125.07,
      "volume": 112117500,
      "adj_close": 125.07
    },
    ...
  ]
}
```

---

## Strategy Engine API

Base URL: `http://localhost:5002`

### Health Check

Check if the service is running.

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "service": "strategy-engine"
}
```

---

### Run Strategy

Execute a trading strategy and backtest.

**Endpoint**: `POST /strategy/run`

**Request Body**:
```json
{
  "ticker": "AAPL",
  "strategy": "sma",
  "start_date": "2023-01-01",
  "end_date": "2024-01-01",
  "parameters": {
    "short_window": 20,
    "long_window": 50
  },
  "initial_capital": 10000
}
```

**Strategy Options**:
- `sma` - Simple Moving Average Crossover
- `mean_reversion` - Mean Reversion Strategy
- `momentum` - Momentum Strategy

**Strategy Parameters**:

For `sma`:
- `short_window`: Short-term moving average period (default: 20)
- `long_window`: Long-term moving average period (default: 50)

For `mean_reversion`:
- `window`: Moving average period (default: 20)
- `num_std`: Number of standard deviations for bands (default: 2)

For `momentum`:
- `lookback`: Lookback period in days (default: 10)

**Response**:
```json
{
  "message": "Strategy executed successfully",
  "backtest_id": 1,
  "ticker": "AAPL",
  "strategy": "sma",
  "metrics": {
    "initial_capital": 10000,
    "final_capital": 12500,
    "total_return": 25.0,
    "sharpe_ratio": 1.5,
    "max_drawdown": -8.5,
    "win_rate": 55.5,
    "total_trades": 20
  },
  "equity_curve": [10000, 10050, 10100, ...],
  "trades": [...],
  "signals": [...]
}
```

---

### Get Backtest Result

Retrieve a specific backtest result by ID.

**Endpoint**: `GET /results/<backtest_id>`

**Example**:
```
GET /results/1
```

**Response**:
```json
{
  "id": 1,
  "ticker": "AAPL",
  "strategy": "sma",
  "start_date": "2023-01-01",
  "end_date": "2024-01-01",
  "initial_capital": 10000,
  "final_capital": 12500,
  "total_return": 25.0,
  "sharpe_ratio": 1.5,
  "max_drawdown": -8.5,
  "win_rate": 55.5,
  "total_trades": 20,
  "parameters": "{'short_window': 20, 'long_window': 50}",
  "created_at": "2024-01-15 10:30:00"
}
```

---

### List All Results

Get a list of all backtest results.

**Endpoint**: `GET /results`

**Response**:
```json
{
  "results": [
    {
      "id": 1,
      "ticker": "AAPL",
      "strategy": "sma",
      "total_return": 25.0,
      "sharpe_ratio": 1.5,
      "created_at": "2024-01-15 10:30:00"
    },
    ...
  ]
}
```

---

## Error Responses

All APIs return error responses in the following format:

```json
{
  "error": "Error message description"
}
```

Common HTTP status codes:
- 200: Success
- 400: Bad request (invalid parameters)
- 404: Resource not found
- 500: Internal server error

---

## Examples with cURL

### Fetch Data
```bash
curl -X POST http://localhost:5001/data/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "GOOGL",
    "start_date": "2023-01-01",
    "end_date": "2023-12-31"
  }'
```

### Run SMA Strategy
```bash
curl -X POST http://localhost:5002/strategy/run \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "GOOGL",
    "strategy": "sma",
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "parameters": {"short_window": 20, "long_window": 50},
    "initial_capital": 10000
  }'
```

### List Results
```bash
curl http://localhost:5002/results
```

---

## Python Examples

### Using requests library

```python
import requests

# Fetch data
response = requests.post(
    'http://localhost:5001/data/fetch',
    json={
        'ticker': 'MSFT',
        'start_date': '2023-01-01',
        'end_date': '2023-12-31'
    }
)
print(response.json())

# Run strategy
response = requests.post(
    'http://localhost:5002/strategy/run',
    json={
        'ticker': 'MSFT',
        'strategy': 'momentum',
        'start_date': '2023-01-01',
        'end_date': '2023-12-31',
        'parameters': {'lookback': 10},
        'initial_capital': 10000
    }
)
result = response.json()
print(f"Total Return: {result['metrics']['total_return']:.2f}%")
```

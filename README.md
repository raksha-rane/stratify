# Automated Quantitative Unified Analyst (AQUA)

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-brightgreen.svg)](https://www.docker.com/)

A comprehensive DevOps-integrated quantitative trading platform for backtesting algorithmic trading strategies. Built with Python, Flask, Streamlit, PostgreSQL, Docker, and Jenkins.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Services](#services)
- [Trading Strategies](#trading-strategies)
- [CI/CD Pipeline](#cicd-pipeline)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Overview

AQUA is an end-to-end automated trading research platform that demonstrates:

- **Quantitative Finance**: Implementation of established trading strategies
- **Microservices Architecture**: Containerized, scalable services
- **DevOps Practices**: CI/CD with Jenkins, Docker orchestration
- **Data Engineering**: ETL pipeline for market data
- **Full-Stack Development**: Backend APIs and interactive dashboard

**Disclaimer**: This platform is for educational and simulation purposes only. No real trades are executed.

## Features

- **Market Data Ingestion**: Fetch historical data from Yahoo Finance
- **Trading Strategies**: SMA Crossover, Mean Reversion, Momentum
- **Backtesting Engine**: Simulate trades with comprehensive performance metrics
- **Performance Metrics**: ROI, Sharpe Ratio, Max Drawdown, Win Rate
- **Interactive Dashboard**: Real-time visualization with Streamlit
- **Containerized Deployment**: Docker Compose orchestration
- **CI/CD Pipeline**: Automated testing and deployment with Jenkins
- **Database Persistence**: PostgreSQL for data storage
- **Monitoring Stack**: Prometheus and Grafana for system observability

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Dashboard  │────▶│ Strategy     │────▶│  Data Service   │
│ (Streamlit) │     │ Engine       │     │  (Flask API)    │
│   :8501     │     │ (Flask API)  │     │    :5001        │
└─────────────┘     │   :5002      │     └─────────────────┘
                    └──────────────┘               │
                           │                       │
                           └───────────┬───────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │   PostgreSQL    │
                              │   Database      │
                              │     :5432       │
                              └─────────────────┘
```

## Prerequisites

- **Docker**: Version 20.x or higher
- **Docker Compose**: Version 2.x or higher
- **Python**: 3.11+ (for local development)
- **Git**: For version control
- **Jenkins**: (Optional) For CI/CD pipeline

### System Requirements

- **RAM**: 4GB minimum, 8GB recommended
- **Disk Space**: 5GB free space
- **OS**: Linux, macOS, or Windows with WSL2

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/raksha-rane/aqua.git
cd aqua
```

### 2. Start All Services (Automated Setup)

The easiest way to start everything:

```bash
# Build and start all services (main + monitoring)
./setup.sh
```

This automated setup will:

- Check prerequisites (Docker, Docker Compose)
- Clean up any existing containers
- Build all Docker images
- Create the necessary network
- Start main services (PostgreSQL, Redis, Data Service, Strategy Engine, Dashboard)
- Start monitoring services (Prometheus, Grafana)
- Perform health checks on all services

**Manual Setup (Alternative)**:

```bash
# Start main services first (creates the network)
docker-compose up -d

# Then start monitoring services
docker-compose -f monitoring/docker-compose.monitoring.yml up -d

# Check container status
docker-compose ps
```

### 3. Access the Dashboard

Open your browser and navigate to:

- Dashboard: `http://localhost:8501`
- Data Service API: `http://localhost:5001/health`
- Strategy Engine API: `http://localhost:5002/health`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (credentials: admin/admin123)

### 4. Run Your First Backtest

1. Open the dashboard at `http://localhost:8501`
2. Enter a stock ticker (e.g., AAPL)
3. Select date range
4. Choose a strategy (SMA Crossover recommended for first run)
5. Click "Fetch Data" to download market data
6. Click "Run Strategy" to execute backtest
7. View results, charts, and metrics

### 5. Stop Services

```bash
# Stop all services (main + monitoring)
./shutdown.sh

# Stop and remove all data (clean slate)
./shutdown.sh --volumes
```

**Manual Shutdown (Alternative)**:

```bash
# Stop all containers
docker-compose down
docker-compose -f monitoring/docker-compose.monitoring.yml down

# Stop and remove volumes
docker-compose down -v
docker-compose -f monitoring/docker-compose.monitoring.yml down -v
```

## Project Structure

```text
aqua/
├── data-service/           # Market data fetching service
│   ├── app.py             # Flask API for data operations
│   ├── Dockerfile
│   └── requirements.txt
├── strategy-engine/        # Trading strategy execution
│   ├── app.py             # Strategy implementation and backtesting
│   ├── risk_manager.py    # Risk management and position sizing
│   ├── Dockerfile
│   └── requirements.txt
├── dashboard/              # Web interface
│   ├── app.py             # Streamlit dashboard
│   ├── Dockerfile
│   └── requirements.txt
├── database/               # Database configuration
│   └── init.sql           # Schema initialization
├── monitoring/             # Monitoring stack
│   ├── docker-compose.monitoring.yml
│   ├── prometheus.yml
│   └── grafana/
├── tests/                  # Test suites
│   ├── test_strategies.py
│   ├── test_integration.py
│   └── requirements.txt
├── common/                 # Shared utilities
│   ├── logger.py
│   ├── health.py
│   └── metrics.py
├── docker-compose.yml      # Container orchestration
├── setup.sh               # Automated setup script
├── shutdown.sh            # Automated shutdown script
├── Jenkinsfile            # CI/CD pipeline definition
└── README.md              # This file
```

## Services

### Data Service (Port 5001)

Handles market data operations:

- Fetch data from Yahoo Finance
- Store in PostgreSQL
- Serve data to other services

**Endpoints**:

- `GET /health` - Health check
- `POST /data/fetch` - Fetch and store market data
- `GET /data/get` - Retrieve stored data

### Strategy Engine (Port 5002)

Executes trading strategies and backtests:

- Implement trading algorithms
- Calculate signals
- Run backtests
- Compute performance metrics

**Endpoints**:

- `GET /health` - Health check
- `POST /strategy/run` - Execute strategy
- `GET /results` - List all backtest results
- `GET /results/<id>` - Get specific result

### Dashboard (Port 8501)

Interactive web interface:

- Configure parameters
- Trigger data fetch and strategy runs
- Visualize results with charts
- View performance metrics

### PostgreSQL Database (Port 5432)

Stores:

- Market data (OHLCV)
- Trade signals
- Backtest results

## Trading Strategies

### 1. SMA Crossover

**Logic**: Buy when short-term SMA crosses above long-term SMA, sell when it crosses below.

**Parameters**:

- `short_window` (default: 20) - Short-term moving average period
- `long_window` (default: 50) - Long-term moving average period

**Best For**: Trending markets

### 2. Mean Reversion

**Logic**: Buy when price drops below lower Bollinger Band, sell when it rises above upper band.

**Parameters**:

- `window` (default: 20) - Moving average period
- `num_std` (default: 2) - Number of standard deviations for bands

**Best For**: Range-bound markets

### 3. Momentum

**Logic**: Go long if recent returns are positive, short if negative.

**Parameters**:

- `lookback` (default: 10) - Number of days to calculate momentum

**Best For**: Strong trending markets

## CI/CD Pipeline

The Jenkins pipeline automates:

1. **Checkout**: Pull latest code
2. **Build**: Create Docker images
3. **Test**: Run unit and integration tests
4. **Quality Check**: Code linting with flake8
5. **Deploy**: Start services with docker-compose
6. **Health Check**: Verify all services are running

### Setting Up Jenkins

**Install Jenkins**:

```bash
# Using Docker
docker run -d -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts
```

**Configure Pipeline**:

- Create new pipeline job
- Point to your repository
- Use `Jenkinsfile` from root directory

**Run Pipeline**:

- Click "Build Now"
- Monitor progress in Console Output

## API Documentation

### Fetch Market Data

```bash
curl -X POST http://localhost:5001/data/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01"
  }'
```

### Run Strategy

```bash
curl -X POST http://localhost:5002/strategy/run \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "strategy": "sma",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
    "parameters": {
      "short_window": 20,
      "long_window": 50
    },
    "initial_capital": 10000
  }'
```

### Get Results

```bash
curl http://localhost:5002/results
```

## Testing

### Run Unit Tests

```bash
cd tests
pip install -r requirements.txt
pytest test_strategies.py -v
```

### Run Integration Tests

```bash
# Make sure all services are running first
docker-compose up -d

# Run tests
cd tests
pytest test_integration.py -v
```

### Test Coverage

```bash
pytest --cov=. --cov-report=html
```

## Troubleshooting

### Services Won't Start

```bash
# Check Docker daemon
docker ps

# View service logs
docker-compose logs data-service
docker-compose logs strategy-engine

# Restart services
docker-compose restart
```

### Database Connection Issues

```bash
# Check if PostgreSQL is healthy
docker-compose ps postgres

# Access database directly
docker exec -it aqua-postgres psql -U postgres -d aqua_db

# Verify tables
\dt
```

### Port Already in Use

```bash
# Find process using port
lsof -i :5001  # or 5002, 8501, 5432

# Kill process or change port in docker-compose.yml
```

### Data Fetch Failures

- Check internet connection
- Verify ticker symbol is correct
- Ensure Yahoo Finance is accessible
- Try different date ranges

## Additional Resources

- [Software Requirements Specification](SRS.md) - Complete system specification
- [Quick Start Guide](QUICKSTART.md) - Quick reference for common operations
- [Docker Documentation](https://docs.docker.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Jenkins Pipeline](https://www.jenkins.io/doc/book/pipeline/)

## Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Authors

Developed for educational purposes as part of a DevOps and quantitative finance learning project.

## Acknowledgments

- Yahoo Finance for market data API
- Open source community for tools and libraries
- DevOps best practices from industry standards

---

For questions or issues, please open an issue on GitHub.

# 🚀 AQTS - Automated Quant Trading Strategy Platform

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-brightgreen.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A complete DevOps-integrated quantitative trading platform for backtesting algorithmic trading strategies. Built with Python, Flask, Streamlit, PostgreSQL, Docker, and Jenkins.

## 📋 Table of Contents

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

## 🎯 Overview

AQTS is an end-to-end automated trading research platform that demonstrates:

- **Quantitative Finance**: Implementation of popular trading strategies
- **Microservices Architecture**: Containerized, scalable services
- **DevOps Practices**: CI/CD with Jenkins, Docker orchestration
- **Data Engineering**: ETL pipeline for market data
- **Full-Stack Development**: Backend APIs and interactive dashboard

**⚠️ Disclaimer**: This platform is for educational and simulation purposes only. No real trades are executed.

## ✨ Features

- 📊 **Market Data Ingestion**: Fetch historical data from Yahoo Finance
- 🤖 **Trading Strategies**: SMA Crossover, Mean Reversion, Momentum
- 📈 **Backtesting Engine**: Simulate trades with performance metrics
- 💹 **Performance Metrics**: ROI, Sharpe Ratio, Max Drawdown, Win Rate
- 🎨 **Interactive Dashboard**: Real-time visualization with Streamlit
- 🐳 **Containerized Deployment**: Docker Compose orchestration
- 🔄 **CI/CD Pipeline**: Automated testing and deployment with Jenkins
- 🗄️ **Database Persistence**: PostgreSQL for data storage

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Dashboard  │────▶│ Strategy     │────▶│  Data Service   │
│ (Streamlit) │     │ Engine       │     │  (Flask API)    │
│   :8501     │     │ (Flask API)  │     │    :5001        │
└─────────────┘     │   :5002      │     └─────────────────┘
                    └──────────────┘              │
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

## 🔧 Prerequisites

- **Docker**: Version 20.x or higher
- **Docker Compose**: Version 2.x or higher
- **Python**: 3.11+ (for local development)
- **Git**: For version control
- **Jenkins**: (Optional) For CI/CD pipeline

### System Requirements

- **RAM**: 4GB minimum, 8GB recommended
- **Disk Space**: 5GB free space
- **OS**: Linux, macOS, or Windows with WSL2

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd stratify
```

### 2. Start All Services

```bash
# Build and start all containers
docker-compose up -d

# Check container status
docker-compose ps

# View logs
docker-compose logs -f
```

### 3. Access the Dashboard

Open your browser and navigate to:
- **Dashboard**: http://localhost:8501
- **Data Service API**: http://localhost:5001/health
- **Strategy Engine API**: http://localhost:5002/health

### 4. Run Your First Backtest

1. Open the dashboard at http://localhost:8501
2. Enter a stock ticker (e.g., `AAPL`)
3. Select date range
4. Choose a strategy (SMA Crossover recommended for first run)
5. Click **"Fetch Data"** to download market data
6. Click **"Run Strategy"** to execute backtest
7. View results, charts, and metrics!

### 5. Stop Services

```bash
# Stop all containers
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

## 📁 Project Structure

```
stratify/
├── data-service/           # Market data fetching service
│   ├── app.py             # Flask API for data operations
│   ├── Dockerfile
│   └── requirements.txt
├── strategy-engine/        # Trading strategy execution
│   ├── app.py             # Strategy implementation and backtesting
│   ├── Dockerfile
│   └── requirements.txt
├── dashboard/              # Web interface
│   ├── app.py             # Streamlit dashboard
│   ├── Dockerfile
│   └── requirements.txt
├── database/               # Database configuration
│   └── init.sql           # Schema initialization
├── tests/                  # Test suites
│   ├── test_strategies.py
│   ├── test_integration.py
│   └── requirements.txt
├── docs/                   # Documentation
├── docker-compose.yml      # Container orchestration
├── Jenkinsfile            # CI/CD pipeline definition
├── SRS.md                 # Software Requirements Specification
└── README.md              # This file
```

## 🔌 Services

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

## 📊 Trading Strategies

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

## 🔄 CI/CD Pipeline

The Jenkins pipeline automates:

1. **Checkout**: Pull latest code
2. **Build**: Create Docker images
3. **Test**: Run unit and integration tests
4. **Quality Check**: Code linting with flake8
5. **Deploy**: Start services with docker-compose
6. **Health Check**: Verify all services are running

### Setting Up Jenkins

1. **Install Jenkins**:
```bash
# Using Docker
docker run -d -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts
```

2. **Configure Pipeline**:
   - Create new pipeline job
   - Point to your repository
   - Use `Jenkinsfile` from root directory

3. **Run Pipeline**:
   - Click "Build Now"
   - Monitor progress in Console Output

## 📖 API Documentation

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

## 🧪 Testing

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

## 🐛 Troubleshooting

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
docker exec -it aqts-postgres psql -U postgres -d aqts_db

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

## 📚 Additional Resources

- [SRS Document](SRS.md) - Complete system specification
- [Docker Documentation](https://docs.docker.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Jenkins Pipeline](https://www.jenkins.io/doc/book/pipeline/)

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Authors

- **Your Name** - Initial work

## 🙏 Acknowledgments

- Yahoo Finance for market data API
- Open source community for amazing tools
- DevOps best practices from industry leaders

---

**Made with ❤️ for educational purposes**

For questions or issues, please open an issue on GitHub.

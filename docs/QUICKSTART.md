# 🚀 Quick Start Guide

Get AQTS running in 5 minutes!

## Prerequisites Check

Before starting, ensure you have:

- ✅ Docker installed and running
- ✅ Docker Compose installed
- ✅ At least 4GB RAM available
- ✅ Ports 5001, 5002, 5432, 8501 are free

## Step 1: Clone and Navigate

```bash
cd /Users/raksharane/Documents/Uni/devops/stratify
```

## Step 2: Start the Platform

### Option A: Using the setup script (Recommended)

```bash
./setup.sh
```

### Option B: Manual start

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check status
docker-compose ps
```

## Step 3: Access the Dashboard

Open your browser and go to:
**http://localhost:8501**

## Step 4: Run Your First Backtest

1. In the dashboard sidebar:
   - Enter ticker: `AAPL`
   - Select date range: Last year
   - Choose strategy: `SMA Crossover`
   - Keep default parameters

2. Click **"📥 Fetch Data"** button
   - Wait for success message (usually 5-10 seconds)

3. Click **"🚀 Run Strategy"** button
   - Wait for processing (usually 10-15 seconds)

4. View your results! 📊
   - Check performance metrics
   - See equity curve chart
   - Explore trading signals

## What's Next?

### Try Different Strategies

- **SMA Crossover**: Good for trending markets
  - Adjust short/long windows (e.g., 10/30, 50/200)
  
- **Mean Reversion**: Good for range-bound markets
  - Try different window and std dev parameters
  
- **Momentum**: Good for strong trends
  - Adjust lookback period (5-20 days)

### Test Different Stocks

Popular tickers to try:
- Tech: `AAPL`, `GOOGL`, `MSFT`, `TSFT`, `NVDA`
- Finance: `JPM`, `GS`, `BAC`
- Consumer: `WMT`, `AMZN`, `COST`
- Crypto: `BTC-USD`, `ETH-USD`

### Compare Performance

1. Run the same strategy on multiple stocks
2. Run different strategies on the same stock
3. Adjust parameters to optimize returns
4. Check the History tab to compare results

## Useful Commands

```bash
# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart a service
docker-compose restart dashboard

# Clean restart
docker-compose down -v
docker-compose up -d

# Check database
docker exec -it aqts-postgres psql -U postgres -d aqts_db
```

## API Testing

Test the APIs directly:

```bash
# Health checks
curl http://localhost:5001/health
curl http://localhost:5002/health

# Fetch data via API
curl -X POST http://localhost:5001/data/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01"
  }'

# Run strategy via API
curl -X POST http://localhost:5002/strategy/run \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "strategy": "sma",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
    "parameters": {"short_window": 20, "long_window": 50},
    "initial_capital": 10000
  }'
```

## Troubleshooting

### Services won't start?

```bash
# Check Docker is running
docker ps

# View logs for errors
docker-compose logs

# Try clean restart
docker-compose down -v
docker-compose up -d
```

### Dashboard shows connection error?

```bash
# Wait a bit longer (services need time to start)
sleep 15

# Check if all services are healthy
curl http://localhost:5001/health
curl http://localhost:5002/health

# Restart dashboard
docker-compose restart dashboard
```

### Data fetch fails?

- Check internet connection
- Verify ticker symbol is correct
- Try a different date range
- Yahoo Finance might be rate-limiting

### Port already in use?

```bash
# Find what's using the port
lsof -i :8501

# Option 1: Stop the process
kill -9 <PID>

# Option 2: Change port in docker-compose.yml
# Edit ports section, e.g., "8502:8501"
```

## Testing the Platform

Run the test suite:

```bash
./run_tests.sh
```

## Next Steps

1. 📚 Read the full [README.md](../README.md)
2. 🔌 Explore [API Documentation](API.md)
3. 🚀 Check [Deployment Guide](DEPLOYMENT.md)
4. 📋 Review [SRS Document](../SRS.md)

## Support

Having issues?
1. Check logs: `docker-compose logs`
2. Verify all services are running: `docker-compose ps`
3. Try clean restart: `docker-compose down -v && docker-compose up -d`

---

**Happy Trading! 📈**

Remember: This is a simulation platform for educational purposes only. No real money is involved.

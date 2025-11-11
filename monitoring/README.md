# StraAQUAtify Monitoring Stack

This directory contains the monitoring infrastructure for the AQUA using Prometheus and Grafana.

## Architecture

- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards

## Quick Start

### 1. Start Main Services

First, ensure the main application stack is running:

```bash
cd ..
docker-compose up -d
```

### 2. Start Monitoring Stack

```bash
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

### 3. Access Monitoring Tools

- **Prometheus**: http://localhost:9090
  - Query metrics, view targets, check health
  
- **Grafana**: http://localhost:3000
  - Username: `admin`
  - Password: `admin123`
  - Pre-configured Prometheus datasource
  - Auto-loaded dashboards

## Metrics Overview

### Request Metrics
- `api_requests_total` - Total API requests (Counter)
- `request_duration_seconds` - Request latency (Histogram)
- `active_connections` - Current active connections (Gauge)
- `errors_total` - Total errors by type (Counter)

### Data Service Metrics
- `data_fetch_total` - Data fetches by ticker and status
- `data_quality_score` - Quality score per ticker (0-100)
- `rate_limit_hits_total` - Rate limit violations

### Strategy Engine Metrics
- `strategy_execution_duration` - Strategy execution time
- `backtest_trades_total` - Total trades in backtests
- `backtest_return_percent` - Backtest returns
- `backtest_sharpe_ratio` - Sharpe ratio per backtest

### System Metrics
- `service_up` - Service availability (1=up, 0=down)
- `health_check_status` - Health check results
- `queue_size` - Request queue size by status

## Configuration

### Prometheus (`prometheus.yml`)
- Scrape interval: 15 seconds
- Retention: 30 days
- Targets:
  - data-service:5001
  - strategy-engine:5002

### Grafana
- Datasource: Auto-configured Prometheus
- Dashboards: Auto-loaded from `grafana/dashboards/`
- Provisioning: Automatic on startup

## Dashboards

### AQUA - Overview
Pre-configured dashboard with:
- Total request rate
- 95th percentile latency
- Error rate
- Active connections
- Request rate by endpoint
- Request duration (p50, p95)
- Data fetch rate by ticker
- Data quality scores
- Backtest metrics (trades, returns, Sharpe ratio)
- Rate limit hits

## Querying Metrics

### Prometheus Query Examples

**Request rate per service:**
```promql
sum(rate(api_requests_total[5m])) by (service)
```

**95th percentile latency:**
```promql
histogram_quantile(0.95, sum(rate(request_duration_seconds_bucket[5m])) by (le))
```

**Error rate:**
```promql
sum(rate(api_requests_total{status=~"4..|5.."}[5m]))
```

**Data quality by ticker:**
```promql
data_quality_score
```

**Backtest returns:**
```promql
backtest_return_percent{strategy="sma"}
```

## Stopping Services

```bash
# Stop monitoring stack
docker-compose -f docker-compose.monitoring.yml down

# Stop with volume cleanup
docker-compose -f docker-compose.monitoring.yml down -v
```

## Troubleshooting

### Prometheus not scraping targets

1. Check if services are running:
   ```bash
   docker ps
   ```

2. Verify network connectivity:
   ```bash
   docker exec aqua-prometheus wget -O- http://data-service:5001/metrics
   ```

3. Check Prometheus targets: http://localhost:9090/targets

### Grafana dashboard not loading

1. Verify datasource: Grafana → Configuration → Data Sources
2. Check dashboard provisioning logs:
   ```bash
   docker logs aqua-grafana
   ```

3. Manually import dashboard from `grafana/dashboards/aqua-overview.json`

### No metrics appearing

1. Generate some traffic:
   ```bash
   # Fetch data
   curl -X POST http://localhost:5001/data/fetch \
     -H "Content-Type: application/json" \
     -d '{"ticker": "AAPL", "start_date": "2024-01-01", "end_date": "2024-12-31"}'
   
   # Run backtest
   curl -X POST http://localhost:5002/strategy/run \
     -H "Content-Type: application/json" \
     -d '{"ticker": "AAPL", "strategy": "sma", "start_date": "2024-01-01", "end_date": "2024-12-31"}'
   ```

2. Check metrics endpoints:
   ```bash
   curl http://localhost:5001/metrics
   curl http://localhost:5002/metrics
   ```

## Adding Custom Dashboards

1. Create dashboard in Grafana UI
2. Export as JSON
3. Save to `grafana/dashboards/`
4. Restart Grafana or wait for auto-reload (30s)

## Production Considerations

- [ ] Enable Prometheus authentication
- [ ] Configure alerting rules
- [ ] Set up Alertmanager
- [ ] Increase retention period
- [ ] Add remote storage
- [ ] Enable HTTPS
- [ ] Configure backup strategy
- [ ] Set proper resource limits

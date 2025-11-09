# Deployment Guide

This guide covers deployment options for the AQTS platform.

## Table of Contents

1. [Local Deployment](#local-deployment)
2. [Production Deployment](#production-deployment)
3. [Environment Variables](#environment-variables)
4. [Scaling](#scaling)
5. [Monitoring](#monitoring)
6. [Backup and Recovery](#backup-and-recovery)

---

## Local Deployment

### Prerequisites

- Docker 20.x or higher
- Docker Compose 2.x or higher
- 4GB RAM minimum
- 5GB free disk space

### Quick Start

```bash
# Clone repository
git clone <repo-url>
cd stratify

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Accessing Services

- Dashboard: http://localhost:8501
- Data Service: http://localhost:5001
- Strategy Engine: http://localhost:5002
- PostgreSQL: localhost:5432

---

## Production Deployment

### Security Considerations

1. **Change default passwords**:
   - Update PostgreSQL password in docker-compose.yml
   - Use environment variables or secrets management

2. **Enable HTTPS**:
   - Use reverse proxy (nginx/traefik)
   - Add SSL certificates

3. **Restrict network access**:
   - Use firewalls
   - Limit exposed ports

4. **Update regularly**:
   - Keep Docker images updated
   - Monitor security advisories

### Production docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    restart: always
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - internal
    # Don't expose port publicly
    
  data-service:
    build: ./data-service
    restart: always
    environment:
      DB_HOST: postgres
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
    networks:
      - internal
    depends_on:
      - postgres
      
  # ... other services
  
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    networks:
      - internal
    depends_on:
      - dashboard

networks:
  internal:
    driver: bridge
    
volumes:
  postgres_data:
```

### Using .env File

Create a `.env` file:

```bash
# Database
DB_NAME=aqts_db
DB_USER=aqts_user
DB_PASSWORD=strong_password_here

# Services
DATA_SERVICE_URL=http://data-service:5001
STRATEGY_SERVICE_URL=http://strategy-engine:5002
```

---

## Environment Variables

### Data Service

- `DB_HOST`: PostgreSQL host (default: localhost)
- `DB_PORT`: PostgreSQL port (default: 5432)
- `DB_NAME`: Database name (default: aqts_db)
- `DB_USER`: Database user (default: postgres)
- `DB_PASSWORD`: Database password (default: postgres)

### Strategy Engine

- `DB_HOST`: PostgreSQL host
- `DB_PORT`: PostgreSQL port
- `DB_NAME`: Database name
- `DB_USER`: Database user
- `DB_PASSWORD`: Database password
- `DATA_SERVICE_URL`: Data service URL (default: http://localhost:5001)

### Dashboard

- `DATA_SERVICE_URL`: Data service URL
- `STRATEGY_SERVICE_URL`: Strategy engine URL

---

## Scaling

### Horizontal Scaling

Scale individual services:

```bash
# Scale strategy engine to 3 instances
docker-compose up -d --scale strategy-engine=3

# Add load balancer
docker-compose -f docker-compose.yml -f docker-compose.scale.yml up -d
```

### Database Optimization

```sql
-- Add indexes for frequently queried fields
CREATE INDEX idx_market_data_ticker ON market_data(ticker);
CREATE INDEX idx_market_data_date ON market_data(date);

-- Analyze tables
ANALYZE market_data;
ANALYZE trades;
ANALYZE backtest_results;
```

### Caching

Add Redis for caching:

```yaml
redis:
  image: redis:alpine
  ports:
    - "6379:6379"
```

---

## Monitoring

### Health Checks

Monitor service health:

```bash
#!/bin/bash
# health_check.sh

services=("data-service:5001" "strategy-engine:5002")

for service in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if curl -f "http://localhost:$port/health" &> /dev/null; then
        echo "✅ $name is healthy"
    else
        echo "❌ $name is down"
    fi
done
```

### Log Aggregation

View aggregated logs:

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f data-service

# Last 100 lines
docker-compose logs --tail=100
```

### Metrics

Monitor Docker stats:

```bash
docker stats
```

---

## Backup and Recovery

### Database Backup

```bash
# Backup database
docker exec aqts-postgres pg_dump -U postgres aqts_db > backup_$(date +%Y%m%d).sql

# Restore database
docker exec -i aqts-postgres psql -U postgres aqts_db < backup_20240115.sql
```

### Automated Backups

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
docker exec aqts-postgres pg_dump -U postgres aqts_db > "$BACKUP_DIR/aqts_$DATE.sql"

# Keep only last 7 days
find $BACKUP_DIR -name "aqts_*.sql" -mtime +7 -delete

echo "Backup completed: aqts_$DATE.sql"
```

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * /path/to/backup.sh
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs data-service

# Restart service
docker-compose restart data-service

# Rebuild and restart
docker-compose up -d --build data-service
```

### Database Connection Issues

```bash
# Check database
docker-compose ps postgres

# Connect to database
docker exec -it aqts-postgres psql -U postgres -d aqts_db

# Check tables
\dt
```

### Port Conflicts

```bash
# Find process using port
lsof -i :5001

# Change port in docker-compose.yml
ports:
  - "5011:5001"  # Map to different host port
```

---

## CI/CD Integration

### Jenkins Deployment

The platform includes a Jenkinsfile for automated deployment:

```groovy
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                sh 'docker-compose build'
            }
        }
        stage('Test') {
            steps {
                sh 'cd tests && pytest'
            }
        }
        stage('Deploy') {
            steps {
                sh 'docker-compose up -d'
            }
        }
    }
}
```

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy AQTS

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build images
        run: docker-compose build
        
      - name: Run tests
        run: cd tests && pytest
        
      - name: Deploy
        run: docker-compose up -d
```

---

## Support

For issues or questions:
- Check logs: `docker-compose logs`
- View status: `docker-compose ps`
- Restart services: `docker-compose restart`
- Clean slate: `docker-compose down -v && docker-compose up -d`

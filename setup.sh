#!/bin/bash

# AQUA Setup Script
# This script sets up the AQUA platform

set -e

echo "AQUA Platform Setup"
echo "======================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker found: $(docker --version)"
echo "✅ Docker Compose found: $(docker-compose --version)"
echo ""

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker."
    exit 1
fi

echo "✅ Docker daemon is running"
echo ""

# Clean up existing containers and networks if any
echo "🧹 Cleaning up any existing containers..."
docker-compose down -v 2>/dev/null || true
docker-compose -f monitoring/docker-compose.monitoring.yml down -v 2>/dev/null || true

echo ""

# Build images
echo "🔨 Building Docker images..."
docker-compose build --no-cache

echo ""
echo "✅ Images built successfully"
echo ""

# Create network explicitly (if it doesn't exist)
echo "🌐 Creating Docker network..."
docker network create aqua-network 2>/dev/null || echo "   Network already exists, continuing..."

echo ""

# Start main services (this will use the existing network)
echo "🚀 Starting main services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for main services to be healthy..."
sleep 15

# Verify main services are running
echo "   Checking service status..."
docker-compose ps

echo ""

# Start monitoring stack
echo "📊 Starting monitoring services (Prometheus & Grafana)..."
docker-compose -f monitoring/docker-compose.monitoring.yml up -d

echo ""
echo "⏳ Waiting for monitoring services to be ready..."
sleep 10

# Verify monitoring services are running
echo "   Checking monitoring status..."
docker-compose -f monitoring/docker-compose.monitoring.yml ps

# Health checks
echo ""
echo "Performing health checks..."

if curl -f http://localhost:5001/health &> /dev/null; then
    echo "✅ Data Service is healthy"
else
    echo "⚠️  Data Service health check failed"
fi

if curl -f http://localhost:5002/health &> /dev/null; then
    echo "✅ Strategy Engine is healthy"
else
    echo "⚠️  Strategy Engine health check failed"
fi

if curl -f http://localhost:8501 &> /dev/null; then
    echo "✅ Dashboard is accessible"
else
    echo "⚠️  Dashboard health check failed"
fi

if curl -f http://localhost:9090/-/healthy &> /dev/null; then
    echo "✅ Prometheus is healthy"
else
    echo "⚠️  Prometheus health check failed"
fi

if curl -f http://localhost:3000/api/health &> /dev/null; then
    echo "✅ Grafana is healthy"
else
    echo "⚠️  Grafana health check failed"
fi

echo ""
echo "================================================"
echo " AQUA Platform is ready!"
echo "================================================"
echo ""
echo "Access the services:"
echo "   Dashboard:        http://localhost:8501"
echo "   Data Service:     http://localhost:5001"
echo "   Strategy Engine:  http://localhost:5002"
echo ""
echo "Monitoring:"
echo "   Prometheus:       http://localhost:9090"
echo "   Grafana:          http://localhost:3000"
echo "   Credentials:      Set in docker-compose.yml (SECURITY: Change default passwords!)"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo "  docker-compose -f monitoring/docker-compose.monitoring.yml logs -f"
echo ""
echo "To stop all services:"
echo "  docker-compose down && docker-compose -f monitoring/docker-compose.monitoring.yml down"
echo ""
echo "To stop and remove volumes:"
echo "  docker-compose down -v && docker-compose -f monitoring/docker-compose.monitoring.yml down -v"
echo ""
echo "Happy trading! 📈"

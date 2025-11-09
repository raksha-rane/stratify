#!/bin/bash

# AQTS Setup Script
# This script sets up the AQTS platform

set -e

echo "🚀 AQTS Platform Setup"
echo "======================"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

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

# Build images
echo "🔨 Building Docker images..."
docker-compose build --no-cache

echo ""
echo "✅ Images built successfully"
echo ""

# Start services
echo "🚀 Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 15

# Health checks
echo ""
echo "🏥 Performing health checks..."

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

echo ""
echo "================================================"
echo "🎉 AQTS Platform is ready!"
echo "================================================"
echo ""
echo "Access the services:"
echo "  📊 Dashboard:        http://localhost:8501"
echo "  🔌 Data Service:     http://localhost:5001"
echo "  🤖 Strategy Engine:  http://localhost:5002"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop services:"
echo "  docker-compose down"
echo ""
echo "Happy trading! 📈"

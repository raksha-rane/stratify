#!/bin/bash

# AQUA Test Runner Script
# Runs all tests for the platform

set -e

echo "🧪 AQUA Test Suite"
echo "=================="
echo ""

# Navigate to tests directory
cd "$(dirname "$0")/tests"

# Install test requirements
echo "📦 Installing test dependencies..."
pip install -r requirements.txt -q

echo ""
echo "🔬 Running Unit Tests..."
echo "========================"
pytest test_strategies.py -v --tb=short

echo ""
echo "🔗 Running Integration Tests..."
echo "==============================="
echo "⚠️  Make sure services are running (docker-compose up -d)"
sleep 2

pytest test_integration.py -v --tb=short

echo ""
echo "✅ All tests completed!"

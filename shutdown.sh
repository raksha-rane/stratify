#!/bin/bash

# AQUA Shutdown Script
# This script stops all AQUA platform services

set -e

echo "AQUA Platform Shutdown"
echo "======================"
echo ""

# Parse command line arguments
REMOVE_VOLUMES=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-v|--volumes]"
            echo "  -v, --volumes    Remove volumes (will delete all data)"
            exit 1
            ;;
    esac
done

# Stop monitoring services
echo "🛑 Stopping monitoring services..."
if [ "$REMOVE_VOLUMES" = true ]; then
    docker-compose -f monitoring/docker-compose.monitoring.yml down -v
else
    docker-compose -f monitoring/docker-compose.monitoring.yml down
fi

echo "✅ Monitoring services stopped"
echo ""

# Stop main services
echo "🛑 Stopping main services..."
if [ "$REMOVE_VOLUMES" = true ]; then
    docker-compose down -v
    echo "⚠️  Volumes removed - all data has been deleted"
else
    docker-compose down
fi

echo "✅ Main services stopped"
echo ""

# Optional: Remove the network if no containers are using it
if [ "$REMOVE_VOLUMES" = true ]; then
    echo "🧹 Cleaning up network..."
    docker network rm aqua-network 2>/dev/null || echo "   Network already removed or in use"
    echo ""
fi

echo "================================================"
echo " AQUA Platform has been shut down"
echo "================================================"
echo ""
echo "To start again, run: ./setup.sh"
echo ""

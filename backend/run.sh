#!/bin/bash

# AlphaTransformer uv startup script

echo "🚀 Starting AlphaTransformer Market Data Service (uv)"
echo "📍 Current directory: $(pwd)"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv not installed, please install uv first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Show Python version
echo "🐍 Python version: $(uv run python --version)"

# Sync dependencies
echo "📦 Syncing project dependencies..."
uv sync

# Start API service
echo "🌐 Starting Web API service..."
echo "📊 API docs: http://localhost:8000/docs"
echo "💚 Health check: http://localhost:8000/api/v1/health"
echo ""
echo "Press Ctrl+C to stop service"
echo "=========================================="

# Use uv to run API service directly (not through package scripts)
uv run python -m api.main
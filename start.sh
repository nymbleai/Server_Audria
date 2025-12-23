#!/bin/bash
set -e

# Get port from environment variable (Render provides this)
PORT=${PORT:-8000}

echo "🚀 Starting Audria API server..."
echo "📍 Binding to port: $PORT"
echo "🌐 Host: 0.0.0.0"

# Start the server with explicit port binding
exec poetry run uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --log-level info


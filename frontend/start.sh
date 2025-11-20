#!/bin/bash

# Simple HTTP server for frontend
echo "🚀 Starting Admin Dashboard Frontend..."
echo ""
echo "📊 Dashboard will be available at: http://localhost:8080"
echo "🔧 API should be running at: http://localhost:8000"
echo "⚠️  Note: Port 3000 is used by Grafana"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Check if Python 3 is available
if command -v python3 &> /dev/null; then
    python3 -m http.server 8080
elif command -v python &> /dev/null; then
    python -m http.server 8080
else
    echo "❌ Error: Python not found. Please install Python 3."
    exit 1
fi

#!/bin/bash

# NBA Fantasy Draft Dashboard Launcher
# This script automatically starts the web server and opens the dashboard

echo "🏀 NBA Fantasy Draft Dashboard Launcher"
echo "========================================"
echo ""

# Check if JSON files exist
if [ ! -f "teams_data.json" ] || [ ! -f "players_data.json" ]; then
    echo "⚠️  Data files not found. Running preprocessing..."
    echo ""
    python3 preprocess_data.py
    echo ""
    echo "✅ Preprocessing complete!"
    echo ""
fi

# Check if dashboard.html exists
if [ ! -f "dashboard.html" ]; then
    echo "❌ Error: dashboard.html not found!"
    exit 1
fi

# Find available port
PORT=8000
while lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; do
    echo "⚠️  Port $PORT is already in use, trying next port..."
    PORT=$((PORT + 1))
done

echo "🚀 Starting web server on port $PORT..."
echo ""
echo "📱 Dashboard URL: http://localhost:$PORT/dashboard.html"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================"
echo ""

# Start server and open browser
python3 -m http.server $PORT &
SERVER_PID=$!

# Wait a moment for server to start
sleep 2

# Open browser
if command -v open &> /dev/null; then
    # macOS
    open "http://localhost:$PORT/dashboard.html"
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open "http://localhost:$PORT/dashboard.html"
elif command -v start &> /dev/null; then
    # Windows
    start "http://localhost:$PORT/dashboard.html"
else
    echo "Please open your browser and navigate to: http://localhost:$PORT/dashboard.html"
fi

# Wait for server
wait $SERVER_PID

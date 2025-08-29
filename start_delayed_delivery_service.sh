#!/bin/bash

# Start the delayed delivery service as a background daemon
# This ensures startup messages are delivered even if hooks don't trigger immediately

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SERVICE_SCRIPT="$SCRIPT_DIR/claude_hooks/delayed_delivery_service.py"
PID_FILE="/tmp/delayed_delivery_service.pid"
LOG_FILE="$SCRIPT_DIR/logs/delayed_delivery_service.log"

# Create logs directory
mkdir -p "$(dirname "$LOG_FILE")"

# Check if service is already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Delayed delivery service already running (PID: $PID)"
        exit 0
    else
        echo "Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# Start the service
echo "Starting delayed delivery service..."
nohup python3 "$SERVICE_SCRIPT" > "$LOG_FILE" 2>&1 &
SERVICE_PID=$!

# Save PID
echo "$SERVICE_PID" > "$PID_FILE"

echo "Delayed delivery service started (PID: $SERVICE_PID)"
echo "Log file: $LOG_FILE"
echo "PID file: $PID_FILE"

# Wait a moment to check if it started successfully
sleep 2
if ps -p "$SERVICE_PID" > /dev/null 2>&1; then
    echo "Service is running successfully"
else
    echo "ERROR: Service failed to start"
    rm -f "$PID_FILE"
    exit 1
fi
#!/bin/bash
# Auto-start queue daemon if not running

SERVICE_NAME="tmux-orchestrator-queue"

# Check if service is running
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "🚀 Starting queue daemon service..."
    sudo systemctl start "$SERVICE_NAME"
    
    # Wait a moment for startup
    sleep 2
    
    # Check if it started successfully
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "✅ Queue daemon started successfully"
    else
        echo "❌ Failed to start queue daemon"
        echo "📋 Service status:"
        systemctl status "$SERVICE_NAME" --no-pager -l
    fi
else
    echo "✅ Queue daemon already running"
fi

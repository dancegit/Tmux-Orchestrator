#!/bin/bash
#
# Installation script for Tmux Orchestrator Queue Error Monitoring Service
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="tmux-queue-error-monitor"
TIMER_NAME="tmux-queue-error-monitor.timer"

echo "Installing Tmux Orchestrator Queue Error Monitoring Service..."

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo "ERROR: This script should not be run as root"
    echo "It will use sudo when needed"
    exit 1
fi

# Check if files exist
if [[ ! -f "$SCRIPT_DIR/queue_error_monitor.sh" ]]; then
    echo "ERROR: queue_error_monitor.sh not found in $SCRIPT_DIR"
    exit 1
fi

if [[ ! -f "$SCRIPT_DIR/$SERVICE_NAME.service" ]]; then
    echo "ERROR: $SERVICE_NAME.service not found in $SCRIPT_DIR"
    exit 1
fi

if [[ ! -f "$SCRIPT_DIR/$SERVICE_NAME.timer" ]]; then
    echo "ERROR: $SERVICE_NAME.timer not found in $SCRIPT_DIR"
    exit 1
fi

# Make monitoring script executable
echo "Making queue_error_monitor.sh executable..."
chmod +x "$SCRIPT_DIR/queue_error_monitor.sh"

# Create logs directory
echo "Creating logs directory..."
mkdir -p "$SCRIPT_DIR/logs"

# Stop existing services if running
echo "Stopping existing services (if running)..."
sudo systemctl stop "$TIMER_NAME" 2>/dev/null || true
sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true

# Copy systemd files
echo "Installing systemd service and timer files..."
sudo cp "$SCRIPT_DIR/$SERVICE_NAME.service" "/etc/systemd/system/"
sudo cp "$SCRIPT_DIR/$SERVICE_NAME.timer" "/etc/systemd/system/"

# Set correct permissions
sudo chown root:root "/etc/systemd/system/$SERVICE_NAME.service"
sudo chown root:root "/etc/systemd/system/$SERVICE_NAME.timer"
sudo chmod 644 "/etc/systemd/system/$SERVICE_NAME.service"
sudo chmod 644 "/etc/systemd/system/$SERVICE_NAME.timer"

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable and start timer
echo "Enabling and starting timer..."
sudo systemctl enable "$TIMER_NAME"
sudo systemctl start "$TIMER_NAME"

# Create logrotate configuration
echo "Setting up log rotation..."
sudo tee "/etc/logrotate.d/tmux-queue-monitor" > /dev/null << EOF
/home/clauderun/Tmux-Orchestrator/logs/queue_error_monitor.log {
    daily
    rotate 7
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
    create 644 clauderun clauderun
}
EOF

# Test the service
echo "Testing service configuration..."
sudo systemctl --quiet is-enabled "$TIMER_NAME" || {
    echo "ERROR: Timer failed to enable"
    exit 1
}

# Show status
echo ""
echo "=== Installation Complete ==="
echo ""
echo "Service status:"
sudo systemctl status "$TIMER_NAME" --no-pager --lines=5 || true
echo ""
echo "Timer schedule:"
sudo systemctl list-timers "$TIMER_NAME" --no-pager || true
echo ""
echo "Log file: $SCRIPT_DIR/logs/queue_error_monitor.log"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status $TIMER_NAME      # Check timer status"
echo "  sudo systemctl status $SERVICE_NAME    # Check service status"
echo "  sudo journalctl -u $SERVICE_NAME       # View service logs"
echo "  sudo systemctl start $SERVICE_NAME     # Run service immediately"
echo "  tail -f $SCRIPT_DIR/logs/queue_error_monitor.log  # Watch logs"
echo ""

# Offer to run the service immediately
read -p "Run the monitoring service immediately for testing? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running service immediately..."
    sudo systemctl start "$SERVICE_NAME"
    echo "Service started. Check logs for results."
    echo "You can monitor with: tail -f $SCRIPT_DIR/logs/queue_error_monitor.log"
fi

echo "Installation completed successfully!"
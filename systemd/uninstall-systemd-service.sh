#!/bin/bash

# Uninstall systemd service for Tmux Orchestrator Scheduler
# Usage: sudo ./uninstall-systemd-service.sh <username>

if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

if [ $# -lt 1 ]; then
    echo "Usage: sudo $0 <username>"
    echo "Example: sudo $0 clauderun"
    exit 1
fi

USERNAME="$1"
SERVICE_NAME="tmux-orchestrator-scheduler@${USERNAME}.service"

# Stop the service
echo "Stopping service: $SERVICE_NAME"
systemctl stop "$SERVICE_NAME"

# Disable the service
echo "Disabling service: $SERVICE_NAME"
systemctl disable "$SERVICE_NAME"

# Remove service file if no other instances exist
if ! systemctl list-units --all | grep -q "tmux-orchestrator-scheduler@.*\.service"; then
    echo "Removing service file"
    rm -f "/etc/systemd/system/tmux-orchestrator-scheduler@.service"
fi

# Reload systemd
systemctl daemon-reload

echo "Service uninstalled successfully!"
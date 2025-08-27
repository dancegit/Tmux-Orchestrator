#!/bin/bash

# Install systemd service for Tmux Orchestrator Scheduler with race condition fixes
# Usage: sudo ./install-systemd-service-fixed.sh <username>

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
SERVICE_NAME="tmux-orchestrator-scheduler.service"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Verify user exists
if ! id "$USERNAME" &>/dev/null; then
    echo "Error: User $USERNAME does not exist"
    exit 1
fi

# Stop and disable any existing service
echo "Stopping existing services..."
systemctl stop tmux-orchestrator-scheduler.service 2>/dev/null || true
systemctl stop tmux-orchestrator-scheduler@${USERNAME}.service 2>/dev/null || true
systemctl disable tmux-orchestrator-scheduler.service 2>/dev/null || true
systemctl disable tmux-orchestrator-scheduler@${USERNAME}.service 2>/dev/null || true

# Remove old service files
rm -f /etc/systemd/system/tmux-orchestrator-scheduler.service
rm -f /etc/systemd/system/tmux-orchestrator-scheduler@.service

# Copy the FIXED service file to systemd directory
echo "Installing FIXED systemd service for user: $USERNAME"
sed "s/clauderun/$USERNAME/g" "$SCRIPT_DIR/tmux-orchestrator-scheduler-fixed.service" > "/etc/systemd/system/$SERVICE_NAME"

# Create necessary directories
sudo -u "$USERNAME" mkdir -p "/home/$USERNAME/Tmux-Orchestrator/logs"
sudo -u "$USERNAME" mkdir -p "/home/$USERNAME/Tmux-Orchestrator/locks"

# Clean up any existing lock files
sudo -u "$USERNAME" rm -f "/home/$USERNAME/Tmux-Orchestrator/locks/scheduler.lock"
sudo -u "$USERNAME" rm -f "/home/$USERNAME/Tmux-Orchestrator/locks/scheduler_process.info"
sudo -u "$USERNAME" rm -f "/home/$USERNAME/Tmux-Orchestrator/locks/project_queue.lock"

# Reload systemd
systemctl daemon-reload

# Enable the service
systemctl enable "$SERVICE_NAME"
echo "Service enabled: $SERVICE_NAME"

# Start the service
echo "Starting service with race condition fixes..."
systemctl start "$SERVICE_NAME"
echo "Service started: $SERVICE_NAME"

# Wait a moment and show status
sleep 3
systemctl status "$SERVICE_NAME" --no-pager

echo ""
echo "Installation complete with race condition fixes!"
echo ""
echo "Key improvements:"
echo "  ✅ Proper process cleanup sequence with delays"
echo "  ✅ Systemd-aware lock manager"
echo "  ✅ Enhanced restart handling"
echo "  ✅ Lock file cleanup in service startup"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status $SERVICE_NAME       # Check status"
echo "  sudo systemctl start $SERVICE_NAME        # Start service"
echo "  sudo systemctl stop $SERVICE_NAME         # Stop service"
echo "  sudo systemctl restart $SERVICE_NAME      # Restart service"
echo "  sudo journalctl -u $SERVICE_NAME -f       # View logs"
echo "  sudo systemctl disable $SERVICE_NAME      # Disable service"
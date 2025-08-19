#!/bin/bash

# Install systemd service for Tmux Orchestrator Scheduler
# Usage: sudo ./install-systemd-service.sh <username>

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
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Verify user exists
if ! id "$USERNAME" &>/dev/null; then
    echo "Error: User $USERNAME does not exist"
    exit 1
fi

# Copy service file to systemd directory with @ for templating
echo "Installing systemd service for user: $USERNAME"
cp "$SCRIPT_DIR/tmux-orchestrator-scheduler.service" "/etc/systemd/system/tmux-orchestrator-scheduler@.service"

# Create log directory if it doesn't exist
sudo -u "$USERNAME" mkdir -p "/home/$USERNAME/Tmux-Orchestrator/logs"

# Reload systemd
systemctl daemon-reload

# Enable the service
systemctl enable "$SERVICE_NAME"
echo "Service enabled: $SERVICE_NAME"

# Start the service
systemctl start "$SERVICE_NAME"
echo "Service started: $SERVICE_NAME"

# Show status
systemctl status "$SERVICE_NAME" --no-pager

echo ""
echo "Installation complete!"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status $SERVICE_NAME    # Check status"
echo "  sudo systemctl start $SERVICE_NAME     # Start service"
echo "  sudo systemctl stop $SERVICE_NAME      # Stop service"
echo "  sudo systemctl restart $SERVICE_NAME   # Restart service"
echo "  sudo journalctl -u $SERVICE_NAME -f    # View logs"
echo "  sudo systemctl disable $SERVICE_NAME   # Disable service"
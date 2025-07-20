#!/bin/bash
# Install the Claude credit monitor as a systemd user service

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo "Installing Claude Credit Monitor..."

# Create directories
mkdir -p ~/.claude
mkdir -p ~/.config/systemd/user/

# Copy service file
cp "$SCRIPT_DIR/claude-credit-monitor.service" ~/.config/systemd/user/

# Update paths in service file
sed -i "s|/home/per|$HOME|g" ~/.config/systemd/user/claude-credit-monitor.service

# Reload systemd
systemctl --user daemon-reload

# Enable and start service
systemctl --user enable claude-credit-monitor.service
systemctl --user start claude-credit-monitor.service

# Check status
systemctl --user status claude-credit-monitor.service

echo ""
echo "Installation complete!"
echo ""
echo "Useful commands:"
echo "  systemctl --user status claude-credit-monitor    # Check status"
echo "  systemctl --user stop claude-credit-monitor      # Stop monitor"
echo "  systemctl --user start claude-credit-monitor     # Start monitor"
echo "  systemctl --user restart claude-credit-monitor   # Restart monitor"
echo "  journalctl --user -u claude-credit-monitor -f   # View logs"
echo ""
echo "Manual run: python3 $SCRIPT_DIR/credit_monitor.py"
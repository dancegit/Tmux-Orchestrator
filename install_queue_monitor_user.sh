#!/bin/bash
#
# User-space installation script for Queue Error Monitoring Service
# (No sudo required - uses cron instead of systemd)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing Tmux Orchestrator Queue Error Monitoring Service (User Mode)..."

# Make scripts executable
echo "Making scripts executable..."
chmod +x "$SCRIPT_DIR/queue_error_monitor.sh"
chmod +x "$SCRIPT_DIR/monitor_control.sh"

# Create logs directory
echo "Creating logs directory..."
mkdir -p "$SCRIPT_DIR/logs"

# Create wrapper script for cron
echo "Creating cron wrapper script..."
cat > "$SCRIPT_DIR/queue_monitor_cron.sh" << 'EOF'
#!/bin/bash
# Cron wrapper for queue error monitor

# Set environment
export TMUX_ORCHESTRATOR_HOME="${TMUX_ORCHESTRATOR_HOME:-/home/clauderun/Tmux-Orchestrator}"
export HOME="/home/clauderun"
export PATH="/usr/local/bin:/usr/bin:/bin:/home/clauderun/.local/bin"

# Change to working directory
cd "$TMUX_ORCHESTRATOR_HOME"

# Run the monitoring script
./queue_error_monitor.sh
EOF

chmod +x "$SCRIPT_DIR/queue_monitor_cron.sh"

# Add to crontab (every 30 minutes)
echo "Setting up cron job (every 30 minutes)..."
CRON_ENTRY="*/30 * * * * $SCRIPT_DIR/queue_monitor_cron.sh >> $SCRIPT_DIR/logs/cron.log 2>&1"

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -F "queue_monitor_cron.sh" >/dev/null; then
    echo "Cron job already exists, updating..."
    # Remove old entry and add new one
    (crontab -l 2>/dev/null | grep -v "queue_monitor_cron.sh"; echo "$CRON_ENTRY") | crontab -
else
    echo "Adding new cron job..."
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
fi

# Set up logrotate user config
echo "Setting up log rotation..."
mkdir -p ~/.config
cat > ~/.config/logrotate.conf << EOF
$SCRIPT_DIR/logs/queue_error_monitor.log {
    daily
    rotate 7
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
    create 644 $(whoami) $(whoami)
}

$SCRIPT_DIR/logs/cron.log {
    weekly
    rotate 4
    missingok
    notifempty  
    compress
    delaycompress
    copytruncate
    create 644 $(whoami) $(whoami)
}
EOF

# Create user logrotate script
cat > "$SCRIPT_DIR/run_logrotate.sh" << 'EOF'
#!/bin/bash
logrotate -s ~/.config/logrotate.status ~/.config/logrotate.conf
EOF
chmod +x "$SCRIPT_DIR/run_logrotate.sh"

# Add logrotate to daily cron
LOGROTATE_CRON="0 2 * * * $SCRIPT_DIR/run_logrotate.sh"
if ! crontab -l 2>/dev/null | grep -F "run_logrotate.sh" >/dev/null; then
    (crontab -l 2>/dev/null; echo "$LOGROTATE_CRON") | crontab -
fi

# Test the service
echo "Testing monitoring script..."
if ./queue_error_monitor.sh; then
    echo "✅ Test run completed successfully"
else
    echo "⚠️  Test run had issues (check logs)"
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Cron job installed: Every 30 minutes"
crontab -l | grep "queue_monitor_cron.sh"
echo ""
echo "Log files:"
echo "  Monitor: $SCRIPT_DIR/logs/queue_error_monitor.log"
echo "  Cron:    $SCRIPT_DIR/logs/cron.log"
echo ""
echo "Management commands:"
echo "  ./monitor_control.sh status    # Check status"
echo "  ./monitor_control.sh run-now   # Run immediately"  
echo "  ./monitor_control.sh logs      # View logs"
echo "  ./monitor_control.sh attach    # Attach to Claude session"
echo ""
echo "To uninstall:"
echo "  crontab -e  # Remove the queue_monitor_cron.sh lines"
echo ""

# Offer to run immediately
read -p "Run the monitoring service immediately for testing? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running service immediately..."
    ./queue_error_monitor.sh
    echo ""
    echo "Service completed. Check the logs:"
    echo "  tail -f $SCRIPT_DIR/logs/queue_error_monitor.log"
fi

echo "Installation completed successfully!"
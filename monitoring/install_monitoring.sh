#!/bin/bash
# Install and configure the Tmux Orchestrator Compliance Monitoring System

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Tmux Orchestrator Compliance Monitoring Installation ==="
echo

# Check prerequisites
echo "Checking prerequisites..."

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "❌ Error: 'uv' is required but not installed."
    echo "   Install from: https://github.com/astral-sh/uv"
    exit 1
fi

# Check for claude CLI
if ! command -v claude &> /dev/null; then
    echo "⚠️  Warning: 'claude' CLI not found."
    echo "   The rule analyzer will use fallback mode."
    echo "   For best results, install Claude CLI."
fi

# Check for jq
if ! command -v jq &> /dev/null; then
    echo "❌ Error: 'jq' is required but not installed."
    echo "   Install with: sudo apt-get install jq (or brew install jq)"
    exit 1
fi

echo "✅ Prerequisites checked"
echo

# Extract rules from CLAUDE.md
echo "Extracting compliance rules from CLAUDE.md..."
"$SCRIPT_DIR/extract_rules.py"
echo "✅ Rules extracted"
echo

# Create alias for monitored messaging
echo "Setting up command aliases..."

# Create wrapper script in parent directory
cat > "$PARENT_DIR/send-monitored-message.sh" << 'EOF'
#!/bin/bash
# Wrapper to use monitored messaging
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
"$SCRIPT_DIR/monitoring/monitored_send_message.sh" "$@"
EOF

chmod +x "$PARENT_DIR/send-monitored-message.sh"

echo "✅ Command wrapper created"
echo

# Create systemd service file (optional)
echo "Would you like to install the compliance monitor as a systemd service? (y/n)"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    SERVICE_FILE="/tmp/tmux-compliance-monitor.service"
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Tmux Orchestrator Compliance Monitor
After=network.target

[Service]
Type=simple
ExecStart=$SCRIPT_DIR/compliance_monitor.py
Restart=on-failure
RestartSec=10
User=$USER
WorkingDirectory=$PARENT_DIR

[Install]
WantedBy=multi-user.target
EOF

    echo "Service file created at: $SERVICE_FILE"
    echo "To install:"
    echo "  sudo cp $SERVICE_FILE /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable tmux-compliance-monitor"
    echo "  sudo systemctl start tmux-compliance-monitor"
else
    echo "Skipping systemd service installation"
fi

echo

# Create cron job for daily reports (optional)
echo "Would you like to set up automatic daily compliance reports? (y/n)"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    CRON_CMD="0 2 * * * $SCRIPT_DIR/report_generator.py && $SCRIPT_DIR/notification_handler.py --daily-summary"
    
    # Check if cron job already exists
    if ! crontab -l 2>/dev/null | grep -q "report_generator.py"; then
        (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
        echo "✅ Daily report cron job added (runs at 2 AM)"
    else
        echo "⚠️  Daily report cron job already exists"
    fi
else
    echo "Skipping daily report setup"
fi

echo

# Instructions
echo "=== Installation Complete ==="
echo
echo "📋 Quick Start Guide:"
echo
echo "1. Start monitoring service:"
echo "   $SCRIPT_DIR/compliance_monitor.py"
echo "   (or use systemd service if installed)"
echo
echo "2. Use monitored messaging:"
echo "   ./send-monitored-message.sh <target> \"message\""
echo "   (instead of ./send-claude-message.sh)"
echo
echo "3. Generate compliance report:"
echo "   $SCRIPT_DIR/report_generator.py [--show]"
echo
echo "4. Check violations:"
echo "   ls $PARENT_DIR/registry/logs/communications/*/violations.jsonl"
echo
echo "5. View orchestrator notifications:"
echo "   cat $PARENT_DIR/registry/logs/compliance/notifications.jsonl"
echo
echo "📊 Monitoring Features:"
echo "- Automatic rule violation detection"
echo "- Real-time orchestrator notifications"
echo "- Daily compliance reports"
echo "- Communication pattern analysis"
echo "- Git workflow compliance checking"
echo
echo "⚠️  Important Notes:"
echo "- The monitor needs to be running to analyze messages"
echo "- Use send-monitored-message.sh for tracked communications"
echo "- Reports are saved in registry/logs/compliance/daily_reports/"
echo "- Violations trigger immediate orchestrator notifications"
echo
echo "For more information, see monitoring/README.md"
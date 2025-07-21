#!/bin/bash
# Start the compliance monitoring system with CLAUDE.md watcher

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo "Starting Tmux Orchestrator Compliance Monitoring System..."
echo "=========================================="

# Check if monitoring is already running
if pgrep -f "compliance_monitor.py" > /dev/null; then
    echo "⚠️  Compliance monitor is already running"
else
    echo "Starting compliance monitor..."
    "$SCRIPT_DIR/compliance_monitor.py" &
    MONITOR_PID=$!
    echo "✓ Compliance monitor started (PID: $MONITOR_PID)"
fi

# Check if CLAUDE.md watcher is already running
if pgrep -f "claude_md_watcher.py" > /dev/null; then
    echo "⚠️  CLAUDE.md watcher is already running"
else
    echo "Starting CLAUDE.md watcher..."
    "$SCRIPT_DIR/claude_md_watcher.py" &
    WATCHER_PID=$!
    echo "✓ CLAUDE.md watcher started (PID: $WATCHER_PID)"
fi

echo ""
echo "Monitoring system is active:"
echo "- Communication logs: $SCRIPT_DIR/../registry/logs/communications/"
echo "- Violation logs: $SCRIPT_DIR/../registry/logs/communications/*/violations.jsonl"
echo "- CLAUDE.md changes will automatically update rules"
echo ""
echo "To stop monitoring, run: $SCRIPT_DIR/stop_monitoring.sh"
echo ""

# Keep script running to show both outputs
wait
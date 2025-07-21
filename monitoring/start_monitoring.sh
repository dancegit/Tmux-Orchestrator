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

# Start git activity monitor
if pgrep -f "git_activity_monitor.py.*--continuous" > /dev/null; then
    echo "⚠️  Git activity monitor is already running"
else
    echo "Starting git activity monitor..."
    "$SCRIPT_DIR/git_activity_monitor.py" --continuous --interval 120 > /dev/null 2>&1 &
    GIT_MON_PID=$!
    echo "✓ Git activity monitor started (PID: $GIT_MON_PID)"
fi

# Start workflow bottleneck detector
if pgrep -f "workflow_bottleneck_detector.py.*--continuous" > /dev/null; then
    echo "⚠️  Bottleneck detector is already running"
else
    echo "Starting workflow bottleneck detector..."
    "$SCRIPT_DIR/workflow_bottleneck_detector.py" --continuous --notify --interval 300 > /dev/null 2>&1 &
    BOTTLENECK_PID=$!
    echo "✓ Bottleneck detector started (PID: $BOTTLENECK_PID)"
fi

echo ""
echo "Monitoring system is active:"
echo "- Communication logs: $SCRIPT_DIR/../registry/logs/communications/"
echo "- Git activity logs: $SCRIPT_DIR/../registry/logs/git-activity/"
echo "- Violation reports: $SCRIPT_DIR/../registry/logs/*/violations.jsonl"
echo "- Workflow analysis: $SCRIPT_DIR/../registry/logs/workflow-analysis/"
echo "- CLAUDE.md changes automatically update rules"
echo ""
echo "Quick commands:"
echo "- View dashboard: $SCRIPT_DIR/workflow_dashboard.sh"
echo "- Check violations: cat $SCRIPT_DIR/../registry/logs/communications/\$(date +%Y-%m-%d)/violations.jsonl | jq ."
echo "- Stop monitoring: $SCRIPT_DIR/stop_monitoring.sh"
echo ""

# Keep script running to show outputs
echo "Press Ctrl+C to stop all monitors..."
wait
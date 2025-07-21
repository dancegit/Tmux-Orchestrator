#!/bin/bash
# Stop the compliance monitoring system

echo "Stopping Tmux Orchestrator Compliance Monitoring System..."

# Stop compliance monitor
if pgrep -f "compliance_monitor.py" > /dev/null; then
    echo "Stopping compliance monitor..."
    pkill -f "compliance_monitor.py"
    echo "✓ Compliance monitor stopped"
else
    echo "⚠️  Compliance monitor was not running"
fi

# Stop CLAUDE.md watcher
if pgrep -f "claude_md_watcher.py" > /dev/null; then
    echo "Stopping CLAUDE.md watcher..."
    pkill -f "claude_md_watcher.py"
    echo "✓ CLAUDE.md watcher stopped"
else
    echo "⚠️  CLAUDE.md watcher was not running"
fi

echo ""
echo "Monitoring system stopped."
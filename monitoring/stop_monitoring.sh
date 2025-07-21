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

# Stop git activity monitor
if pgrep -f "git_activity_monitor.py.*--continuous" > /dev/null; then
    echo "Stopping git activity monitor..."
    pkill -f "git_activity_monitor.py.*--continuous"
    echo "✓ Git activity monitor stopped"
else
    echo "⚠️  Git activity monitor was not running"
fi

# Stop workflow bottleneck detector
if pgrep -f "workflow_bottleneck_detector.py.*--continuous" > /dev/null; then
    echo "Stopping workflow bottleneck detector..."
    pkill -f "workflow_bottleneck_detector.py.*--continuous"
    echo "✓ Bottleneck detector stopped"
else
    echo "⚠️  Bottleneck detector was not running"
fi

echo ""
echo "Monitoring system stopped."
#!/bin/bash
#
# Project Health Monitor Cron Script
# Runs every 30 minutes to check for failed projects and fix them using Claude AI
#

# Set environment
export PATH=/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/home/clauderun/Tmux-Orchestrator:$PYTHONPATH

# Change to correct directory
cd /home/clauderun/Tmux-Orchestrator || {
    echo "ERROR: Could not cd to /home/clauderun/Tmux-Orchestrator" >&2
    exit 1
}

# Ensure we're in the right place
if [ ! -f "project_health_monitor_claude.py" ]; then
    echo "ERROR: project_health_monitor_claude.py not found in $(pwd)" >&2
    exit 1
fi

# Log start
echo "$(date): Starting project health check from $(pwd)" >> project_health_cron.log

# Run the health monitor once
python3 project_health_monitor_claude.py --once >> project_health_cron.log 2>&1

# Log completion
echo "$(date): Health check completed" >> project_health_cron.log
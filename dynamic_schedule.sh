#!/bin/bash
# Dynamic scheduling for orchestrator check-ins
# Usage: ./dynamic_schedule.sh [minutes]
# Default: 3 minutes if not specified

MINUTES=${1:-3}
SECONDS=$((MINUTES * 60))

echo "Scheduling next orchestrator check in $MINUTES minutes..."

# Run in background
(
    sleep $SECONDS
    
    # Send the check-in message
    tmux send-keys -t tmux-orc:0 "Time for orchestrator check-in! (Scheduled after $MINUTES minutes) Please: 1) Check all sessions with claude_control.py status, 2) Monitor agent progress, 3) Assess task complexity and schedule next check dynamically (2-5 min)"
    
    # CRITICAL: Send the actual Enter key
    tmux send-keys -t tmux-orc:0 C-m
) &

echo "Check-in scheduled for $MINUTES minutes from now"
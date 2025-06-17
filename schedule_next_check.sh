#!/bin/bash
# Schedule the next orchestrator check
# This ensures Claude continues in the SAME conversation

echo "Scheduling next orchestrator check in 10 minutes..."
sleep 600

# Send a message to the current Claude window to trigger continuation
tmux send-keys -t tmux-orc:0 "Time for orchestrator check! Please run: python3 claude_control.py status detailed"
# CRITICAL: Send the actual Enter key
tmux send-keys -t tmux-orc:0 C-m
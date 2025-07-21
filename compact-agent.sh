#!/bin/bash

# Send /compact command to a Claude agent
# Usage: compact-agent.sh <session:window>

if [ $# -lt 1 ]; then
    echo "Usage: $0 <session:window>"
    echo "Example: $0 signalmatrix-hybrid--impl:2"
    exit 1
fi

WINDOW="$1"

echo "Sending /compact to $WINDOW..."

# Send /compact command
tmux send-keys -t "$WINDOW" "/compact"
sleep 0.5
tmux send-keys -t "$WINDOW" Enter

echo "✅ Compact command sent to $WINDOW"
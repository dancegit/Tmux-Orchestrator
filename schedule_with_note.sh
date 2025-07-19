#!/bin/bash
# Dynamic scheduler with note for next check
# Usage: ./schedule_with_note.sh <minutes> "<note>" [target_window]

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Source configuration if available
if [ -f "$SCRIPT_DIR/config.local.sh" ]; then
    source "$SCRIPT_DIR/config.local.sh"
elif [ -f "$SCRIPT_DIR/config.sh" ]; then
    source "$SCRIPT_DIR/config.sh"
fi

MINUTES=${1:-3}
NOTE=${2:-"Standard check-in"}
TARGET=${3:-"${TMO_DEFAULT_SESSION:-tmux-orc}:${TMO_DEFAULT_WINDOW:-0}"}
NOTE_FILE="$SCRIPT_DIR/next_check_note.txt"

# Create a note file for the next check
echo "=== Next Check Note ($(date)) ===" > "$NOTE_FILE"
echo "Scheduled for: $MINUTES minutes" >> "$NOTE_FILE"
echo "" >> "$NOTE_FILE"
echo "$NOTE" >> "$NOTE_FILE"

echo "Scheduling check in $MINUTES minutes with note: $NOTE"

# Calculate the exact time when the check will run
CURRENT_TIME=$(date +"%H:%M:%S")
# Try Linux date format first, then macOS format
if date --version >/dev/null 2>&1; then
    # Linux date command
    RUN_TIME=$(date -d "+${MINUTES} minutes" +"%H:%M:%S")
else
    # macOS date command
    RUN_TIME=$(date -v +${MINUTES}M +"%H:%M:%S")
fi

# Use nohup to completely detach the sleep process
# Use bc for floating point calculation if available, otherwise use bash arithmetic
if command -v bc >/dev/null 2>&1; then
    SECONDS=$(echo "$MINUTES * 60" | bc)
else
    SECONDS=$((MINUTES * 60))
fi

# Check if claude_control.py exists, otherwise just show the note
if [ -f "$SCRIPT_DIR/claude_control.py" ]; then
    CMD="cat '$NOTE_FILE' && '$SCRIPT_DIR/claude_control.py' status detailed"
else
    CMD="cat '$NOTE_FILE'"
fi

nohup bash -c "sleep $SECONDS && tmux send-keys -t $TARGET 'Time for orchestrator check! $CMD' && sleep 1 && tmux send-keys -t $TARGET Enter" > /dev/null 2>&1 &

# Get the PID of the background process
SCHEDULE_PID=$!

echo "Scheduled successfully - process detached (PID: $SCHEDULE_PID)"
echo "SCHEDULED TO RUN AT: $RUN_TIME (in $MINUTES minutes from $CURRENT_TIME)"
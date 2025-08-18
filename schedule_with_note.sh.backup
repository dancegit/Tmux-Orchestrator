#!/bin/bash
# Dynamic scheduler with note for next check
# Usage: ./schedule_with_note.sh <minutes> "<note>" [target_window]
#
# This script now uses the Python-based scheduler for reliability

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

# Check if Python scheduler is available
if [ -f "$SCRIPT_DIR/scheduler.py" ]; then
    # Use the new Python-based scheduler
    # Parse the target to get session and window
    SESSION=$(echo "$TARGET" | cut -d: -f1)
    WINDOW=$(echo "$TARGET" | cut -d: -f2)
    
    # Try to infer the agent role from the window name or use default
    ROLE="orchestrator"
    if [ "$WINDOW" -eq "1" ]; then
        ROLE="project-manager"
    elif [ "$WINDOW" -eq "2" ]; then
        ROLE="developer"
    elif [ "$WINDOW" -eq "3" ]; then
        ROLE="tester"
    elif [ "$WINDOW" -eq "4" ]; then
        ROLE="testrunner"
    fi
    
    # Add task to scheduler
    python3 "$SCRIPT_DIR/scheduler.py" --add "$SESSION" "$ROLE" "$WINDOW" "$MINUTES" "$NOTE"
    
    if [ $? -eq 0 ]; then
        echo "Task scheduled successfully using Python scheduler"
        echo "SCHEDULED TO RUN AT: $RUN_TIME (in $MINUTES minutes from $CURRENT_TIME)"
        
        # Check if scheduler daemon is running
        if ! pgrep -f "scheduler.py --daemon" > /dev/null; then
            echo "WARNING: Scheduler daemon not running. Starting it now..."
            nohup python3 "$SCRIPT_DIR/scheduler.py" --daemon > "$SCRIPT_DIR/scheduler_daemon.log" 2>&1 &
            echo "Scheduler daemon started (PID: $!)"
        fi
    else
        echo "Failed to schedule with Python scheduler, falling back to legacy method"
        # Fallback to old method
        LEGACY_MODE=1
    fi
else
    # No Python scheduler available, use legacy method
    LEGACY_MODE=1
fi

# Legacy scheduling method (fallback)
if [ "$LEGACY_MODE" = "1" ]; then
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
    
    echo "Scheduled successfully using legacy method - process detached (PID: $SCHEDULE_PID)"
    echo "SCHEDULED TO RUN AT: $RUN_TIME (in $MINUTES minutes from $CURRENT_TIME)"
fi
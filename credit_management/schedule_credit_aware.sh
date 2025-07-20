#!/bin/bash
# Credit-aware scheduling wrapper
# Checks agent credit status before scheduling
# Usage: ./schedule_credit_aware.sh <minutes> "<note>" [target_window]

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ORCHESTRATOR_DIR="$(dirname "$SCRIPT_DIR")"

# Get parameters
MINUTES=${1:-3}
NOTE=${2:-"Standard check-in"}
TARGET=${3:-"tmux-orc:0"}

# Check if agent is exhausted
is_exhausted() {
    local target=$1
    local pane_text=$(tmux capture-pane -t "$target" -p -S -50 2>/dev/null)
    
    if echo "$pane_text" | grep -qi "/upgrade"; then
        return 0  # Exhausted
    fi
    
    return 1  # Not exhausted
}

# Check agent status
if is_exhausted "$TARGET"; then
    echo "Agent $TARGET is exhausted - skipping schedule"
    
    # Log this skip
    echo "[$(date)] Skipped scheduling for exhausted agent $TARGET" >> "$ORCHESTRATOR_DIR/logs/credit_skips.log"
    
    # Try to parse reset time and schedule wake-up
    pane_text=$(tmux capture-pane -t "$TARGET" -p -S -100 2>/dev/null)
    reset_info=$(echo "$pane_text" | grep -i "credits will reset at" | tail -1)
    
    if [ -n "$reset_info" ]; then
        echo "Found reset info: $reset_info"
        
        # Use Python to parse and schedule
        python3 - <<EOF
import re
import subprocess
from datetime import datetime, timedelta

reset_info = """$reset_info"""
target = "$TARGET"

# Parse time
patterns = [
    r'credits will reset at (\d{1,2}):(\d{2})\s*(am|pm)?',
    r'credits will reset at (\d{1,2})(am|pm)',
]

for pattern in patterns:
    match = re.search(pattern, reset_info, re.IGNORECASE)
    if match:
        groups = match.groups()
        hour = int(groups[0])
        
        if len(groups) >= 2 and groups[1] and groups[1].isdigit():
            minute = int(groups[1])
        else:
            minute = 0
            
        # Handle AM/PM
        if groups[-1]:
            am_pm = groups[-1].lower()
            if am_pm == 'pm' and hour < 12:
                hour += 12
            elif am_pm == 'am' and hour == 12:
                hour = 0
        
        # Calculate wake time (add 2 minute buffer)
        now = datetime.now()
        wake_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if wake_time <= now:
            wake_time += timedelta(days=1)
        wake_time += timedelta(minutes=2)
        
        # Schedule wake-up
        minutes_until = int((wake_time - now).total_seconds() / 60)
        print(f"Scheduling wake-up in {minutes_until} minutes ({wake_time.strftime('%H:%M')})")
        
        # Use the regular schedule script for wake-up
        subprocess.run([
            '$ORCHESTRATOR_DIR/schedule_with_note.sh',
            str(minutes_until),
            'Credit reset - checking if ready to resume',
            target
        ])
        
        break
EOF
    else
        # Fallback: schedule check in 5 hours
        echo "No reset time found - scheduling fallback check in 5 hours"
        "$ORCHESTRATOR_DIR/schedule_with_note.sh" 300 "Fallback credit check" "$TARGET"
    fi
    
    exit 0
fi

# Agent is not exhausted, proceed with normal scheduling
echo "Agent $TARGET has credits - scheduling normally"
"$ORCHESTRATOR_DIR/schedule_with_note.sh" "$MINUTES" "$NOTE" "$TARGET"
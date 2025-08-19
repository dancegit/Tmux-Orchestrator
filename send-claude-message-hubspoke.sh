#!/bin/bash

# Enhanced send-claude-message.sh with hub-and-spoke enforcement
# Ensures all critical messages are routed through or CC'd to Orchestrator
# Usage: send-claude-message-hubspoke.sh <session:window_or_role> "<message>" [--no-enforce]

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window_or_role> \"<message>\" [--no-enforce]"
    echo "Example: $0 tmux-orc:devops \"Deployment complete\""
    echo "Options:"
    echo "  --no-enforce    Skip hub-and-spoke enforcement (for Orchestrator itself)"
    exit 1
fi

TARGET="$1"
MESSAGE="$2"
NO_ENFORCE="${3:-}"

# Extract session and target part
SESSION=$(echo "$TARGET" | cut -d: -f1)
TARGET_PART=$(echo "$TARGET" | cut -d: -f2)

# Resolve window/role using Python (similar to schedule_with_note.sh)
RESOLUTION=$(python3 << EOF
import sys
sys.path.append('$SCRIPT_DIR')
from session_state import SessionStateManager
from pathlib import Path

# Extract project name from session
session = "$SESSION"
target = "$TARGET_PART"

# Try to resolve
mgr = SessionStateManager(Path('$SCRIPT_DIR'))
project_name = session.split('-impl')[0].replace('-', ' ').title()
state = mgr.load_session_state(project_name)

window = None
role = None

if state:
    # Check if target is a number (window index)
    if target.isdigit():
        window = int(target)
        # Find role for this window
        for r, agent in state.agents.items():
            if agent.window_index == window:
                role = r
                break
    else:
        # Target is a role, find window
        role = target.lower()
        if role in state.agents:
            window = state.agents[role].window_index

if window is not None:
    print(f"{window}|{role or 'unknown'}")
else:
    print(f"{target}|unknown")
EOF
)

WINDOW=$(echo "$RESOLUTION" | cut -d'|' -f1)
ROLE=$(echo "$RESOLUTION" | cut -d'|' -f2)

# Hub-and-spoke enforcement logic
ENFORCED_MESSAGE="$MESSAGE"
SEND_TO_ORCHESTRATOR=false

# Check if we should enforce hub-and-spoke
if [ "$NO_ENFORCE" != "--no-enforce" ] && [ "$WINDOW" != "0" ] && [ "$ROLE" != "orchestrator" ]; then
    # Not sending to orchestrator, so enforce hub-and-spoke
    
    # Check message type to determine enforcement level
    if echo "$MESSAGE" | grep -qiE "(complete|finish|done|deploy|fail|error|block|issue)"; then
        # Critical status update - must report to Orchestrator
        ENFORCED_MESSAGE="$MESSAGE

IMPORTANT: Report this status to Orchestrator (window 0) immediately for coordination."
        SEND_TO_ORCHESTRATOR=true
        
    elif echo "$MESSAGE" | grep -qiE "(status|update|progress|working on)"; then
        # Regular status - suggest reporting
        ENFORCED_MESSAGE="$MESSAGE

Note: Consider updating Orchestrator if this represents significant progress."
    fi
fi

# Function to send message
send_message() {
    local target_window="$1"
    local msg="$2"
    
    # Check for /compact handling
    if echo "$msg" | grep -q "/compact"; then
        # Extract message without /compact
        MSG_WITHOUT_COMPACT=$(echo "$msg" | sed 's|/compact||g' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//')
        
        if [ -n "$MSG_WITHOUT_COMPACT" ] && [ "$MSG_WITHOUT_COMPACT" != " " ]; then
            tmux send-keys -t "$SESSION:$target_window" "$MSG_WITHOUT_COMPACT"
            sleep 0.5
            tmux send-keys -t "$SESSION:$target_window" Enter
            echo "Message sent to $SESSION:$target_window: $MSG_WITHOUT_COMPACT"
            sleep 2
        fi
        
        # Send /compact separately
        tmux send-keys -t "$SESSION:$target_window" "/compact"
        sleep 0.5
        tmux send-keys -t "$SESSION:$target_window" Enter
        echo "Compact command sent to $SESSION:$target_window"
    else
        # Normal message
        tmux send-keys -t "$SESSION:$target_window" "$msg"
        sleep 0.5
        tmux send-keys -t "$SESSION:$target_window" Enter
        echo "Message sent to $SESSION:$target_window ($ROLE): $msg"
    fi
}

# Send to target
send_message "$WINDOW" "$ENFORCED_MESSAGE"

# If critical message and not already to orchestrator, also notify orchestrator
if [ "$SEND_TO_ORCHESTRATOR" = true ] && [ "$WINDOW" != "0" ]; then
    sleep 2
    ORCHESTRATOR_MSG="Hub-Spoke Notice: $ROLE (window $WINDOW) reports: $MESSAGE"
    send_message "0" "$ORCHESTRATOR_MSG"
    echo "Also notified Orchestrator for hub-and-spoke compliance"
fi

# Log for compliance monitoring
if [ -f "$SCRIPT_DIR/registry/logs/communications/messages.log" ]; then
    echo "[$(date -Iseconds)] $SESSION:$WINDOW ($ROLE) <- $MESSAGE" >> "$SCRIPT_DIR/registry/logs/communications/messages.log"
fi
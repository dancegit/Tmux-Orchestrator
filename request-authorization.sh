#!/bin/bash

# Request authorization from another role with proper tracking
# Usage: request-authorization.sh <role> "<request_message>" "<target_role>"
# Example: request-authorization.sh developer "Deploy event_router.py to Modal" "pm"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

if [ $# -lt 3 ]; then
    echo "Usage: $0 <role> \"<request_message>\" \"<target_role>\""
    echo "Example: $0 developer \"Deploy event_router.py to Modal\" \"pm\""
    exit 1
fi

ROLE="$1"
REQUEST_MESSAGE="$2"
TARGET_ROLE="$3"

# Get current session and window from tmux
SESSION=$(tmux display-message -p '#{session_name}' 2>/dev/null)
if [ -z "$SESSION" ]; then
    echo "Error: Not running in a tmux session"
    exit 1
fi

WINDOW=$(tmux display-message -p '#{window_index}' 2>/dev/null)
TIMESTAMP=$(date -Iseconds)
REQUEST_ID=$(uuidgen || echo "REQ-$(date +%s)")  # Fallback if uuidgen not available

# Create authorization request report
REPORT="AUTHORIZATION REQUEST [$REQUEST_ID]
From: $ROLE (window $WINDOW)
To: $TARGET_ROLE
Time: $TIMESTAMP
Request: $REQUEST_MESSAGE

This request has been routed to $TARGET_ROLE and CC'd to Orchestrator for tracking.
Please respond with 'Approved [$REQUEST_ID]' or 'Denied [$REQUEST_ID] [reason]' within 30 minutes."

# Update session state with waiting_for information
python3 << EOF
import sys
sys.path.append('$SCRIPT_DIR')
from session_state import SessionStateManager
from datetime import datetime
from pathlib import Path

try:
    mgr = SessionStateManager(Path('$SCRIPT_DIR'))
    project_name = "$SESSION".split('-impl')[0].replace('-', ' ').title()
    
    # Update agent state with waiting_for
    mgr.update_agent_state(project_name, "$ROLE", {
        'waiting_for': {
            'role': '$TARGET_ROLE',
            'reason': 'authorization',
            'request': '$REQUEST_MESSAGE',
            'since': datetime.now().isoformat(),
            'request_id': '$REQUEST_ID',
            'timeout_minutes': 30
        }
    })
    print("Session state updated with authorization request")
except Exception as e:
    print(f"Warning: Could not update session state: {e}")
EOF

# Send to target role using hub-spoke enforced messaging
echo "Sending authorization request to $TARGET_ROLE..."
if [ -f "$SCRIPT_DIR/send-claude-message-hubspoke.sh" ]; then
    "$SCRIPT_DIR/send-claude-message-hubspoke.sh" "$SESSION:$TARGET_ROLE" "$REPORT"
else
    # Fallback to regular send
    "$SCRIPT_DIR/send-claude-message.sh" "$SESSION:$TARGET_ROLE" "$REPORT"
fi

# Explicitly CC to Orchestrator (window 0) for visibility
echo "CC'ing Orchestrator for tracking..."
if [ -f "$SCRIPT_DIR/send-claude-message-hubspoke.sh" ]; then
    "$SCRIPT_DIR/send-claude-message-hubspoke.sh" "$SESSION:0" "CC: $REPORT" --no-enforce
else
    "$SCRIPT_DIR/send-claude-message.sh" "$SESSION:0" "CC: $REPORT"
fi

# Log for audit
LOG_DIR="$SCRIPT_DIR/registry/logs/authorizations"
mkdir -p "$LOG_DIR"
echo "[$TIMESTAMP] $REQUEST_ID: $ROLE -> $TARGET_ROLE: $REQUEST_MESSAGE" >> "$LOG_DIR/requests.log"

echo "Authorization request sent successfully!"
echo "Request ID: $REQUEST_ID"
echo "Target will be notified to respond within 30 minutes."
#!/bin/bash
# Monitored message sender - wraps send-claude-message.sh with logging and compliance checking
# Usage: monitored_send_message.sh <session:window> <message>

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PARENT_DIR/registry/logs/communications/$(date +%Y-%m-%d)"
MESSAGE_LOG="$LOG_DIR/messages.jsonl"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window> <message>"
    echo "Example: $0 pm:1 'Status update please'"
    exit 1
fi

TARGET="$1"
shift
MESSAGE="$*"

# Extract sender information from current tmux pane
SENDER_PANE=$(tmux display-message -p "#{session_name}:#{window_index}")
SENDER_SESSION=$(echo "$SENDER_PANE" | cut -d: -f1)
SENDER_WINDOW=$(echo "$SENDER_PANE" | cut -d: -f2)

# Extract target information
TARGET_SESSION=$(echo "$TARGET" | cut -d: -f1)
TARGET_WINDOW=$(echo "$TARGET" | cut -d: -f2)

# Create JSON log entry
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_ENTRY=$(cat <<EOF
{
  "timestamp": "$TIMESTAMP",
  "sender": {
    "session": "$SENDER_SESSION",
    "window": "$SENDER_WINDOW",
    "pane": "$SENDER_PANE"
  },
  "recipient": {
    "session": "$TARGET_SESSION",
    "window": "$TARGET_WINDOW",
    "pane": "$TARGET"
  },
  "message": $(echo "$MESSAGE" | jq -Rs .),
  "compliance_checked": false
}
EOF
)

# Log the message
echo "$LOG_ENTRY" >> "$MESSAGE_LOG"

# Send the actual message using the original script
"$PARENT_DIR/send-claude-message.sh" "$TARGET" "$MESSAGE"

# Trigger async compliance check if monitor is running
if pgrep -f "compliance_monitor.py" > /dev/null; then
    # Touch a trigger file to notify the monitor
    touch "$LOG_DIR/.new_messages"
fi

echo "Message logged and sent to $TARGET"
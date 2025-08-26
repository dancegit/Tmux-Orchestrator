#!/bin/bash
# Direct message sender - bypasses monitoring for critical messages
# Usage: send-direct-message.sh <session:window> <message>

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window> <message>"
    echo "Example: $0 developer:3 'Critical fix message'"
    exit 1
fi

TARGET="$1"
shift
MESSAGE="$*"

# Reset pane state first
tmux send-keys -t "$TARGET" C-c Escape C-u 2>/dev/null
sleep 0.2

# Send message directly without any wrapper
tmux send-keys -l -t "$TARGET" "$MESSAGE" 2>/dev/null
sleep 0.1

# Send Enter to execute
tmux send-keys -t "$TARGET" Enter 2>/dev/null

echo "✅ Direct message sent to $TARGET"
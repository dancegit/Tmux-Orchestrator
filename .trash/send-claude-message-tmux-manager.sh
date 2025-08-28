#!/bin/bash

# Send message to Claude agent using TmuxManager
# This is a drop-in replacement for send-claude-message.sh that uses the new TmuxManager
# Usage: send-claude-message-tmux-manager.sh <session:window> <message>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window> <message>"
    echo "Example: $0 agentic-seek:3 'Hello Claude!'"
    exit 1
fi

WINDOW="$1"
shift  # Remove first argument, rest is the message
MESSAGE="$*"

# Use the TmuxManager to send the message
python3 -c "
import sys
sys.path.insert(0, '.')
from tmux_utils import tmux_send_message

target = '$WINDOW'
message = '''$MESSAGE'''

success = tmux_send_message(target, message, validate=True)
if success:
    print(f'Message sent to {target} via TmuxManager')
    sys.exit(0)
else:
    print(f'Failed to send message to {target}')
    sys.exit(1)
"
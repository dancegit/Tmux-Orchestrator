#!/bin/bash

# Send message to Claude agent in tmux window
# Now with smart /compact handling!
# Usage: send-claude-message.sh <session:window> <message>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window> <message>"
    echo "Example: $0 agentic-seek:3 'Hello Claude!'"
    exit 1
fi

WINDOW="$1"
shift  # Remove first argument, rest is the message
MESSAGE="$*"

# Self-referential detection - prevent agents from messaging themselves
CURRENT_WINDOW=$(tmux display-message -p "#{session_name}:#{window_index}" 2>/dev/null || echo "")
if [ "$CURRENT_WINDOW" = "$WINDOW" ]; then
    echo "WARNING: Attempting to send message to self ($WINDOW). Skipping to prevent feedback loop."
    exit 0
fi

# Check if message contains /compact
if echo "$MESSAGE" | grep -q "/compact"; then
    # Extract message without /compact
    MESSAGE_WITHOUT_COMPACT=$(echo "$MESSAGE" | sed 's|/compact||g' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//')
    
    # Send the main message if it's not empty
    if [ -n "$MESSAGE_WITHOUT_COMPACT" ] && [ "$MESSAGE_WITHOUT_COMPACT" != " " ]; then
        tmux send-keys -t "$WINDOW" "$MESSAGE_WITHOUT_COMPACT"
        sleep 0.5
        tmux send-keys -t "$WINDOW" Enter
        echo "Message sent to $WINDOW: $MESSAGE_WITHOUT_COMPACT"
        
        # Wait for the message to be processed
        sleep 2
    fi
    
    # Now send /compact as a separate command
    tmux send-keys -t "$WINDOW" "/compact"
    sleep 0.5
    tmux send-keys -t "$WINDOW" Enter
    echo "Compact command sent separately to $WINDOW"
else
    # Normal message sending
    tmux send-keys -t "$WINDOW" "$MESSAGE"
    sleep 0.5
    tmux send-keys -t "$WINDOW" Enter
    echo "Message sent to $WINDOW: $MESSAGE"
fi
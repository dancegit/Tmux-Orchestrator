#!/bin/bash
# Clean message sender that ensures proper delivery without protocol markers
# This is a safer alternative to send-claude-message.sh for critical messages

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window> <message>"
    echo "Example: $0 dev:3 'Deploy the application'"
    exit 1
fi

WINDOW="$1"
shift
MESSAGE="$*"

# Function to clean any MCP markers from message
clean_message() {
    local msg="$1"
    # Remove any TMUX_MCP_START/DONE patterns
    msg=$(echo "$msg" | sed 's/echo "TMUX_MCP_START";//g')
    msg=$(echo "$msg" | sed 's/echo "TMUX_MCP_DONE_\$?";//g')
    msg=$(echo "$msg" | sed 's/TMUX_MCP_START//g')
    msg=$(echo "$msg" | sed 's/TMUX_MCP_DONE_\$?//g')
    # Remove multiple semicolons
    msg=$(echo "$msg" | sed 's/;;*/;/g')
    # Trim leading/trailing semicolons and spaces
    msg=$(echo "$msg" | sed 's/^[; ]*//;s/[; ]*$//')
    echo "$msg"
}

# Clean the message
CLEAN_MESSAGE=$(clean_message "$MESSAGE")

# Function to send message safely
send_message_safely() {
    local window="$1"
    local msg="$2"
    
    # Reset pane state first
    tmux send-keys -t "$window" C-c 2>/dev/null
    sleep 0.1
    tmux send-keys -t "$window" Escape 2>/dev/null
    sleep 0.1
    tmux send-keys -t "$window" C-u 2>/dev/null
    sleep 0.2
    
    # Send the message
    tmux send-keys -l -t "$window" "$msg" 2>/dev/null
    sleep 0.1
    
    # CRITICAL: Send Enter to execute
    tmux send-keys -t "$window" Enter 2>/dev/null
    
    echo "✅ Message sent cleanly to $window"
}

# Check if window exists
if ! tmux has-session -t "$WINDOW" 2>/dev/null; then
    echo "❌ Error: Window $WINDOW does not exist"
    exit 1
fi

# Send the cleaned message
send_message_safely "$WINDOW" "$CLEAN_MESSAGE"

# Log for debugging (optional)
if [ -n "$DEBUG_MESSAGING" ]; then
    echo "[$(date)] Sent to $WINDOW: $CLEAN_MESSAGE" >> "$SCRIPT_DIR/registry/logs/clean_messages.log"
fi
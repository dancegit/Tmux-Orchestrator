#!/bin/bash
# Smart message sender with window name resolution
# Usage: smart_send_message.sh <session:window_name_or_number> <message>
# Examples:
#   smart_send_message.sh orchestrator-session:TestRunner "Hello!"
#   smart_send_message.sh orchestrator-session:4 "Hello!"  (fallback)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window_name_or_number> <message>"
    echo "Examples:"
    echo "  $0 orchestrator-session:TestRunner 'Hello TestRunner!'"
    echo "  $0 orchestrator-session:Developer 'Status update please'"
    echo "  $0 orchestrator-session:Project-Manager 'Review needed'"
    exit 1
fi

TARGET="$1"
shift
MESSAGE="$*"

# Extract session and window parts
SESSION=$(echo "$TARGET" | cut -d: -f1)
WINDOW_PART=$(echo "$TARGET" | cut -d: -f2)

# Function to resolve window name to index
resolve_window_name() {
    local session="$1"
    local window_name="$2"
    
    # Check if it's already a number
    if [[ "$window_name" =~ ^[0-9]+$ ]]; then
        echo "$window_name"
        return 0
    fi
    
    # Try to resolve window name to index
    local window_index
    window_index=$(tmux list-windows -t "$session" -F '#{window_index} #{window_name}' 2>/dev/null | \
                   awk -v name="$window_name" '$2 == name { print $1; exit }')
    
    if [ -n "$window_index" ]; then
        echo "$window_index"
        return 0
    else
        echo "ERROR: Window '$window_name' not found in session '$session'" >&2
        echo "Available windows:" >&2
        tmux list-windows -t "$session" -F '  #{window_index}: #{window_name}' 2>/dev/null >&2
        return 1
    fi
}

# Resolve window name to index
WINDOW_INDEX=$(resolve_window_name "$SESSION" "$WINDOW_PART")
if [ $? -ne 0 ]; then
    exit 1
fi

# Construct the target with resolved index
RESOLVED_TARGET="${SESSION}:${WINDOW_INDEX}"

echo "🎯 Resolved target: $TARGET → $RESOLVED_TARGET"

# Call the existing monitored send message script
exec "$SCRIPT_DIR/monitored_send_message.sh" "$RESOLVED_TARGET" "$MESSAGE"
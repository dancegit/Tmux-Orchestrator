#!/bin/bash

# Monitor agent context levels and help with compacting
# Usage: monitor_agent_context.sh [session-name]

SESSION="${1:-signalmatrix-hybrid--impl}"

echo "=== Monitoring Agent Context Levels ==="
echo "Session: $SESSION"
echo ""

# Function to check context level in a window
check_context() {
    local window=$1
    local name=$2
    
    # Capture pane content
    local content=$(tmux capture-pane -t "$SESSION:$window" -p -S -100 2>/dev/null)
    
    if [ -z "$content" ]; then
        echo "  $name (Window $window): Cannot capture"
        return
    fi
    
    # Look for context percentage
    local context_match=$(echo "$content" | grep -o "Context[^:]*: [0-9]\+%" | tail -1)
    if [ -n "$context_match" ]; then
        echo "  $name (Window $window): $context_match"
        
        # Extract percentage
        local percentage=$(echo "$context_match" | grep -o "[0-9]\+" | tail -1)
        
        # Check if critically low
        if [ -n "$percentage" ] && [ "$percentage" -le 5 ]; then
            echo "    ⚠️  CRITICAL: Agent needs to compact!"
            
            # Check if agent already tried to compact
            if echo "$content" | tail -20 | grep -q "/compact"; then
                echo "    📝 Agent tried to compact but it wasn't executed properly"
                echo "    🔧 Sending proper compact command..."
                
                # Send compact command properly
                tmux send-keys -t "$SESSION:$window" C-c  # Cancel any current input
                sleep 0.5
                tmux send-keys -t "$SESSION:$window" "/compact"
                sleep 0.5
                tmux send-keys -t "$SESSION:$window" Enter
                
                echo "    ✅ Compact command sent!"
            fi
        fi
    else
        # Try alternative patterns
        local alt_match=$(echo "$content" | grep -o "[0-9]\+% of context" | tail -1)
        if [ -n "$alt_match" ]; then
            echo "  $name (Window $window): $alt_match"
        else
            echo "  $name (Window $window): Context level unknown"
        fi
    fi
}

# Get all windows
windows=$(tmux list-windows -t "$SESSION" -F "#{window_index}:#{window_name}" 2>/dev/null)

if [ -z "$windows" ]; then
    echo "Error: Session '$SESSION' not found"
    exit 1
fi

# Check each window
while IFS= read -r window_info; do
    index=$(echo "$window_info" | cut -d: -f1)
    name=$(echo "$window_info" | cut -d: -f2-)
    check_context "$index" "$name"
done <<< "$windows"

echo ""
echo "=== Summary ==="
echo "If agents show '/compact' in their messages but context isn't clearing:"
echo "1. The command needs to be on its own line"
echo "2. This script will help send it properly"
echo "3. Consider using send-claude-message-smart.sh for future messages"
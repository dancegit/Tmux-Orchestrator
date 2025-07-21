#!/bin/bash

# Find and compact all agents with critically low context
# Usage: compact-all-critical.sh [session-name] [threshold]

SESSION="${1:-signalmatrix-hybrid--impl}"
THRESHOLD="${2:-10}"  # Default to 10% as critical

echo "=== Checking for agents with context < ${THRESHOLD}% ==="
echo "Session: $SESSION"
echo ""

# Track compacted agents
COMPACTED=0

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
    
    # Capture pane content
    content=$(tmux capture-pane -t "$SESSION:$index" -p -S -100 2>/dev/null)
    
    if [ -n "$content" ]; then
        # Look for context percentage in various formats
        percentage=""
        
        # Try different patterns
        match1=$(echo "$content" | grep -o "Context[^:]*: [0-9]\+%" | tail -1 | grep -o "[0-9]\+")
        match2=$(echo "$content" | grep -o "context.*[0-9]\+%" | tail -1 | grep -o "[0-9]\+")
        match3=$(echo "$content" | grep -o "[0-9]\+% of context" | tail -1 | grep -o "[0-9]\+")
        
        # Use first non-empty match
        for match in "$match1" "$match2" "$match3"; do
            if [ -n "$match" ]; then
                percentage="$match"
                break
            fi
        done
        
        # Check if critically low
        if [ -n "$percentage" ] && [ "$percentage" -le "$THRESHOLD" ]; then
            echo "⚠️  $name (Window $index): ${percentage}% - CRITICAL!"
            echo "   Sending /compact command..."
            
            tmux send-keys -t "$SESSION:$index" "/compact"
            sleep 0.5
            tmux send-keys -t "$SESSION:$index" Enter
            
            echo "   ✅ Compacted!"
            ((COMPACTED++))
            
            # Wait between compacts to avoid overwhelming
            sleep 1
        elif [ -n "$percentage" ]; then
            echo "✓ $name (Window $index): ${percentage}% - OK"
        fi
    fi
done <<< "$windows"

echo ""
echo "=== Summary ==="
echo "Compacted $COMPACTED agents with context < ${THRESHOLD}%"
echo ""
echo "Note: Agents should now have fresh context to continue working."
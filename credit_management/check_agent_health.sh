#!/bin/bash
# Quick health check for all Claude agents
# Shows credit status and estimated reset times

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ORCHESTRATOR_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "=== Claude Agent Credit Health Check ==="
echo "Time: $(date)"
echo ""

# Function to check a single agent
check_agent() {
    local target=$1
    local name=$2
    
    # Capture last 100 lines
    local pane_text=$(tmux capture-pane -t "$target" -p -S -100 2>/dev/null)
    
    if [ -z "$pane_text" ]; then
        echo -e "${RED}✗ $name ($target) - Cannot capture pane${NC}"
        return
    fi
    
    # Check for exhaustion indicators
    if echo "$pane_text" | grep -qi "/upgrade"; then
        echo -e "${RED}✗ $name ($target) - EXHAUSTED (upgrade required)${NC}"
        
        # Try to find reset time
        reset_time=$(echo "$pane_text" | grep -i "credits will reset at" | tail -1)
        if [ -n "$reset_time" ]; then
            echo "  └─ $reset_time"
        fi
        
    elif echo "$pane_text" | grep -qi "approaching.*usage limit"; then
        echo -e "${YELLOW}⚠ $name ($target) - WARNING (approaching limit)${NC}"
        
        # Try to find reset time
        reset_time=$(echo "$pane_text" | grep -i "credits will reset at" | tail -1)
        if [ -n "$reset_time" ]; then
            echo "  └─ $reset_time"
        fi
        
    else
        # Check if Claude is actually running
        if echo "$pane_text" | tail -20 | grep -q "Human:"; then
            echo -e "${GREEN}✓ $name ($target) - Active${NC}"
        else
            echo -e "${YELLOW}? $name ($target) - Unknown status${NC}"
        fi
    fi
}

# Get all sessions
sessions=$(tmux list-sessions -F '#{session_name}' 2>/dev/null)

if [ -z "$sessions" ]; then
    echo "No tmux sessions found"
    exit 1
fi

# Check each session's windows
for session in $sessions; do
    windows=$(tmux list-windows -t "$session" -F '#{window_index}:#{window_name}' 2>/dev/null)
    
    for window in $windows; do
        idx=$(echo "$window" | cut -d: -f1)
        name=$(echo "$window" | cut -d: -f2-)
        
        # Skip non-Claude windows
        case "$name" in
            *Claude*|*orchestrator*|*manager*|*developer*|*tester*|*researcher*)
                check_agent "$session:$idx" "$name"
                ;;
        esac
    done
done

echo ""
echo "=== Summary ==="

# Show next expected reset if we have schedule info
if [ -f "$HOME/.claude/credit_schedule.json" ]; then
    next_reset=$(python3 -c "
import json
from datetime import datetime
try:
    with open('$HOME/.claude/credit_schedule.json', 'r') as f:
        data = json.load(f)
    if data.get('next_reset_time'):
        reset_time = datetime.fromisoformat(data['next_reset_time'])
        now = datetime.now()
        if reset_time > now:
            delta = reset_time - now
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            print(f'Next reset in approximately {hours}h {minutes}m ({reset_time.strftime(\"%H:%M\")})')
        else:
            print('Reset time has passed, credits should be available')
    else:
        print('No reset time data available')
except:
    print('Could not read schedule data')
" 2>/dev/null)
    
    if [ -n "$next_reset" ]; then
        echo "$next_reset"
    fi
fi

# Provide action hints
echo ""
echo "Actions:"
echo "- To pause an exhausted agent: kill its tmux window"
echo "- To manually resume: ./send-claude-message.sh session:window 'Please continue'"
echo "- To start monitoring: python3 credit_management/credit_monitor.py"
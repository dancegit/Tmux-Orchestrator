#!/bin/bash

# Diagnostic script to identify MCP wrapper contamination sources

echo "=== MCP Wrapper Diagnostic Tool ==="
echo "Checking for MCP wrapper contamination in tmux sessions..."
echo

# Enable debug mode for send-claude-message.sh
export DEBUG_MCP_WRAPPER=1

# Clear previous debug log
> /tmp/mcp_wrapper_debug.log

# Function to check a tmux pane for MCP wrappers
check_pane_for_mcp() {
    local pane="$1"
    local content=$(tmux capture-pane -p -t "$pane" -S -100 2>/dev/null)
    
    if echo "$content" | grep -q "echo.*TMUX_MCP_START"; then
        echo "❌ MCP wrapper found in pane: $pane"
        echo "   Sample:"
        echo "$content" | grep -B2 -A2 "echo.*TMUX_MCP_START" | head -10 | sed 's/^/   /'
        echo
        return 1
    fi
    return 0
}

# Check all tmux panes
echo "Checking all tmux panes for MCP wrappers..."
tmux list-panes -a -F "#{session_name}:#{window_index}.#{pane_index}" | while read pane; do
    check_pane_for_mcp "$pane"
done

# Check running MCP processes
echo
echo "MCP-related processes:"
ps aux | grep -E "mcp|tmux-mcp" | grep -v grep | head -10

# Check for MCP hooks in tmux
echo
echo "Checking tmux hooks:"
tmux show-hooks -g 2>/dev/null | grep -i mcp || echo "No MCP-related hooks found"

# Check recent scheduler logs
echo
echo "Recent scheduler messages with potential MCP wrappers:"
if [ -f logs/scheduler-checkin.log ]; then
    grep -B2 -A2 "TMUX_MCP" logs/scheduler-checkin.log | tail -20
else
    echo "No scheduler log found"
fi

# Test message sending
echo
echo "Testing message send to detect wrapper injection..."
TEST_SESSION=$(tmux list-sessions -F "#{session_name}" | grep -E "^project-" | head -1)

if [ -n "$TEST_SESSION" ]; then
    echo "Sending test message to $TEST_SESSION:0"
    echo "TEST_MESSAGE_NO_MCP_$(date +%s)" > /tmp/test_msg.txt
    ./send-claude-message.sh "$TEST_SESSION:0" "TEST_MESSAGE_NO_MCP_$(date +%s)"
    
    sleep 2
    
    # Check if message arrived with wrapper
    if tmux capture-pane -p -t "$TEST_SESSION:0" -S -10 | grep -q "TMUX_MCP.*TEST_MESSAGE_NO_MCP"; then
        echo "❌ Test message was wrapped with MCP!"
    else
        echo "✅ Test message sent cleanly"
    fi
fi

# Check debug log
echo
if [ -f /tmp/mcp_wrapper_debug.log ] && [ -s /tmp/mcp_wrapper_debug.log ]; then
    echo "MCP wrapper debug log:"
    cat /tmp/mcp_wrapper_debug.log
else
    echo "No MCP wrapper detected in debug log"
fi

echo
echo "Diagnostic complete."
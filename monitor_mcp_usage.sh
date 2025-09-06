#!/bin/bash
#
# MCP Usage Monitor
# Monitors tmux panes for MCP pattern usage and alerts/fixes automatically
#

# Configuration
MONITOR_INTERVAL=30  # Check every 30 seconds
LOG_DIR="registry/logs/mcp_violations"
ALERT_ORCHESTRATOR=true

# Create log directory
mkdir -p "$LOG_DIR"

# Function to check a single pane for MCP patterns
check_pane_for_mcp() {
    local session="$1"
    local window="$2"
    local pane_id="${session}:${window}"
    
    # Capture pane content
    local content=$(tmux capture-pane -t "$pane_id" -p -S -100 2>/dev/null | tail -50)
    
    # Check for MCP patterns
    if echo "$content" | grep -E "TMUX_MCP_(START|DONE)|MCP_EXECUTE" >/dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] MCP detected in $pane_id"
        
        # Check if it's an unexecuted command (no Enter sent)
        if echo "$content" | grep -E "echo.*TMUX_MCP_DONE.*\$\?\"?$" >/dev/null 2>&1; then
            echo "  → Unexecuted MCP command detected. Sending Enter key."
            tmux send-keys -t "$pane_id" C-m
            
            # Log the violation
            echo "{\"timestamp\":\"$(date -Iseconds)\",\"pane\":\"$pane_id\",\"type\":\"unexecuted_mcp\"}" >> "$LOG_DIR/$(date +%Y-%m-%d).jsonl"
            
            # Alert the agent
            if [ "$ALERT_ORCHESTRATOR" = true ]; then
                ./send-claude-message.sh "$pane_id" "⚠️ MCP usage detected. Please use 'scm' or 'send-monitored-message.sh' for all messaging instead of MCP tmux commands."
            fi
        fi
        
        return 1  # MCP detected
    fi
    
    return 0  # No MCP detected
}

# Function to scan all active sessions
scan_all_sessions() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Scanning for MCP usage..."
    
    local violations=0
    
    # Get all tmux sessions
    while IFS= read -r session; do
        # Skip if session doesn't exist
        [ -z "$session" ] && continue
        
        # Get all windows in the session
        while IFS= read -r window_info; do
            local window_idx=$(echo "$window_info" | cut -d: -f1)
            
            # Check the pane
            if ! check_pane_for_mcp "$session" "$window_idx"; then
                ((violations++))
            fi
        done < <(tmux list-windows -t "$session" -F "#{window_index}:#{window_name}" 2>/dev/null)
    done < <(tmux list-sessions -F "#{session_name}" 2>/dev/null)
    
    if [ $violations -gt 0 ]; then
        echo "  Found $violations MCP violations"
    else
        echo "  No MCP violations detected"
    fi
}

# Main monitoring loop
main() {
    echo "=== MCP Usage Monitor Started ==="
    echo "Monitoring interval: ${MONITOR_INTERVAL}s"
    echo "Log directory: $LOG_DIR"
    echo ""
    
    # Run initial scan
    scan_all_sessions
    
    # Continuous monitoring
    while true; do
        sleep "$MONITOR_INTERVAL"
        scan_all_sessions
    done
}

# Handle script termination
trap 'echo "Monitor stopped."; exit 0' SIGINT SIGTERM

# Start monitoring
main
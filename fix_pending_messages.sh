#!/bin/bash

# Fix Pending Messages - Standalone script to fix stuck messages in tmux windows
# Usage: ./fix_pending_messages.sh [session_name]
# If no session specified, checks all sessions

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LOG_FILE="$SCRIPT_DIR/logs/message_fixes.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    local level="INFO"
    local message="$1"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

fix_session_messages() {
    local session="$1"
    local stuck_messages_found=0
    local messages_fixed=0
    
    log "Checking session: $session"
    
    # Get all windows in session
    local windows
    windows=$(tmux list-windows -t "$session" -F '#{window_index}:#{window_name}' 2>/dev/null) || {
        log "ERROR: Could not access session $session"
        return 1
    }
    
    for window_info in $windows; do
        [ -z "$window_info" ] && continue
        
        local window_idx=$(echo "$window_info" | cut -d: -f1)
        local window_name=$(echo "$window_info" | cut -d: -f2)
        local target="$session:$window_idx"
        
        # Capture recent pane content
        local content
        content=$(tmux capture-pane -p -t "$target" -S -30 2>/dev/null) || continue
        
        # Check for MCP wrapper patterns that indicate stuck messages
        if echo "$content" | grep -q "TMUX_MCP_START\|TMUX_MCP_DONE"; then
            stuck_messages_found=$((stuck_messages_found + 1))
            log "🔧 Found stuck MCP message in $target ($window_name)"
            
            # Show the stuck message context
            local stuck_lines
            stuck_lines=$(echo "$content" | grep -A2 -B2 "TMUX_MCP" | tail -5)
            log "   Context: $(echo "$stuck_lines" | tr '\n' ' ' | sed 's/  */ /g')"
            
            # Send Enter to execute the stuck message
            if tmux send-keys -t "$target" Enter 2>/dev/null; then
                sleep 1.5  # Give more time for processing
                
                # Verify the fix by checking if MCP patterns are gone
                local new_content
                new_content=$(tmux capture-pane -p -t "$target" -S -10 2>/dev/null)
                
                if ! echo "$new_content" | grep -q "TMUX_MCP_START\|TMUX_MCP_DONE"; then
                    messages_fixed=$((messages_fixed + 1))
                    log "✅ Successfully cleared stuck message in $target ($window_name)"
                else
                    log "⚠️  First attempt failed for $target, trying escalated fix"
                    
                    # Escalation: Progressive intervention
                    # 1. Try Ctrl-C to interrupt
                    tmux send-keys -t "$target" C-c 2>/dev/null
                    sleep 0.5
                    
                    # 2. Try Enter again
                    tmux send-keys -t "$target" Enter 2>/dev/null
                    sleep 1
                    
                    # 3. Final verification
                    local final_content
                    final_content=$(tmux capture-pane -p -t "$target" -S -5 2>/dev/null)
                    if ! echo "$final_content" | grep -q "TMUX_MCP_START\|TMUX_MCP_DONE"; then
                        messages_fixed=$((messages_fixed + 1))
                        log "✅ Successfully cleared stuck message in $target ($window_name) after escalation"
                    else
                        log "❌ Failed to clear stuck message in $target ($window_name) after all attempts"
                        log "   Manual intervention may be required for this window"
                    fi
                fi
            else
                log "❌ Failed to send Enter to $target (tmux communication error)"
            fi
        fi
        
        # Also check for incomplete command lines (another pattern of stuck messages)
        local last_line
        last_line=$(echo "$content" | tail -1)
        if echo "$last_line" | grep -q "echo.*;" && ! echo "$last_line" | grep -q "DONE"; then
            log "🔄 Found incomplete command line in $target ($window_name), sending Enter"
            tmux send-keys -t "$target" Enter 2>/dev/null
            sleep 0.5
        fi
    done
    
    # Session summary
    if [ $stuck_messages_found -gt 0 ]; then
        log "Session $session: Found $stuck_messages_found stuck messages, fixed $messages_fixed"
    else
        log "Session $session: ✅ No stuck messages found"
    fi
    
    return $stuck_messages_found
}

main() {
    local target_session="$1"
    local total_stuck=0
    local total_fixed=0
    
    log "=== Fix Pending Messages - Started ==="
    
    if [ -n "$target_session" ]; then
        # Check specific session
        log "Targeting specific session: $target_session"
        if tmux has-session -t "$target_session" 2>/dev/null; then
            fix_session_messages "$target_session"
            total_stuck=$?
        else
            log "ERROR: Session '$target_session' not found"
            tmux list-sessions -F "Available sessions: #{session_name}" 2>/dev/null || log "No tmux sessions running"
            exit 1
        fi
    else
        # Check all sessions
        log "Checking all tmux sessions for stuck messages"
        
        local sessions
        sessions=$(tmux list-sessions -F '#{session_name}' 2>/dev/null)
        
        if [ -z "$sessions" ]; then
            log "No tmux sessions found"
            exit 0
        fi
        
        log "Found sessions: $(echo "$sessions" | tr '\n' ', ' | sed 's/, $//')"
        
        for session in $sessions; do
            [ -z "$session" ] && continue
            fix_session_messages "$session"
            local session_stuck=$?
            total_stuck=$((total_stuck + session_stuck))
        done
    fi
    
    # Final summary
    if [ $total_stuck -gt 0 ]; then
        log "=== SUMMARY: Found stuck messages, check log for details ==="
        log "Recommendation: If problems persist, consider reviewing send-claude-message.sh"
    else
        log "=== SUMMARY: All sessions healthy, no stuck messages found ==="
    fi
    
    log "=== Fix Pending Messages - Completed ==="
    
    # Return non-zero if we found stuck messages (useful for monitoring)
    return $total_stuck
}

# Show usage if requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Fix Pending Messages - Clear stuck tmux messages"
    echo ""
    echo "Usage:"
    echo "  $0                    # Check all tmux sessions"
    echo "  $0 session_name       # Check specific session"
    echo "  $0 --help            # Show this help"
    echo ""
    echo "This script fixes messages that were sent to tmux windows but"
    echo "had their Enter key press fail, leaving them as unexecuted commands."
    echo ""
    echo "Log file: $LOG_FILE"
    exit 0
fi

# Execute main function
main "$@"
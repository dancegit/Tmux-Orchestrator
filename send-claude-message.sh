#!/bin/bash

# Enhanced Send message to Claude agent in tmux window with retry and validation
# Prevents stuck messages requiring manual intervention
# Usage: send-claude-message-enhanced.sh <session:window> <message> [project_id]

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window> <message> [project_id]"
    echo "Example: $0 agentic-seek:3 'Hello Claude!' default"
    exit 1
fi

WINDOW="$1"
shift
MESSAGE="$1"
shift
PROJECT_ID="${1:-default}"

# Configuration
MAX_ATTEMPTS=3
INITIAL_DELAY=1.0
BACKOFF_MULTIPLIER=1.5
VERIFY_TIMEOUT=5
RESET_PANE_BEFORE_SEND=1

# Load project root if available
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Function to reset pane state (clear any stuck input or modes)
reset_pane_state() {
    local window="$1"
    echo "🔄 Resetting pane state for $window"
    
    # Only send Ctrl-C if explicitly enabled (to avoid interrupting bash prompts)
    if [ "${RESET_WITH_CTRL_C:-0}" -eq 1 ]; then
        # Send Ctrl-C only if explicitly enabled (for debugging stuck states)
        tmux send-keys -t "$window" C-c 2>/dev/null
        sleep 0.2
    else
        echo "   Skipping Ctrl-C reset to avoid interrupts"
    fi
    
    # Send Escape to exit any special modes (vi mode, copy mode, etc)
    tmux send-keys -t "$window" Escape 2>/dev/null
    sleep 0.2
    
    # Clear the current line
    tmux send-keys -t "$window" C-u 2>/dev/null
    sleep 0.1
}

# Function to verify message was processed
verify_message_delivered() {
    local window="$1"
    local message="$2"
    local timeout="$3"
    
    local start_time=$(date +%s)
    
    while true; do
        # Capture recent pane content
        local captured=$(tmux capture-pane -p -t "$window" -S -50 2>/dev/null | tail -30)
        
        # Check if our message appears in the captured content
        if echo "$captured" | grep -F "$message" >/dev/null 2>&1; then
            # Check for Claude response indicators
            if echo "$captured" | grep -E "(Assistant:|Claude:|●|>)" >/dev/null 2>&1; then
                echo "✅ Message verified as processed in $window"
                return 0
            fi
        fi
        
        # Check timeout
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [ $elapsed -ge $timeout ]; then
            echo "⏱️  Verification timeout after ${elapsed}s"
            return 1
        fi
        
        sleep 0.5
    done
}

# Function to send message with retry logic
send_with_retry() {
    local window="$1"
    local message="$2"
    local attempts=0
    local delay=$INITIAL_DELAY
    
    while [ $attempts -lt $MAX_ATTEMPTS ]; do
        attempts=$((attempts + 1))
        echo "📤 Attempt $attempts/$MAX_ATTEMPTS: Sending to $window"
        
        # Reset pane state before each attempt if enabled
        if [ $RESET_PANE_BEFORE_SEND -eq 1 ]; then
            reset_pane_state "$window"
        fi
        
        # Handle /compact specially
        if echo "$message" | grep -q "/compact"; then
            # Extract message without /compact
            local message_without_compact=$(echo "$message" | sed 's|/compact||g' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//')
            
            # Send main message if not empty
            if [ -n "$message_without_compact" ] && [ "$message_without_compact" != " " ]; then
                tmux send-keys -l -t "$window" "$message_without_compact" 2>/dev/null
                sleep $delay
                tmux send-keys -t "$window" Enter 2>/dev/null
                sleep $delay
            fi
            
            # Send /compact separately
            tmux send-keys -t "$window" "/compact" 2>/dev/null
            sleep 0.5
            tmux send-keys -t "$window" Enter 2>/dev/null
            
            # For /compact, just verify it was sent (don't wait for full processing)
            sleep 1
            echo "✅ Compact command sent to $window"
            return 0
        else
            # Normal message sending with literal flag to handle special characters
            tmux send-keys -l -t "$window" "$message" 2>/dev/null
            sleep $delay
            tmux send-keys -t "$window" Enter 2>/dev/null
        fi
        
        # Verify delivery
        if verify_message_delivered "$window" "$message" "$VERIFY_TIMEOUT"; then
            return 0
        fi
        
        echo "⚠️  Message not verified, will retry..."
        
        # Exponential backoff - use integer arithmetic
        # Convert float to integer for bash arithmetic
        delay_int=${delay%.*}  # Remove decimal part
        multiplier_int=${BACKOFF_MULTIPLIER%.*}  # Remove decimal part
        delay=$((delay_int * multiplier_int))
        
        # If not last attempt, wait before retry
        if [ $attempts -lt $MAX_ATTEMPTS ]; then
            echo "⏳ Waiting ${delay}s before retry..."
            sleep $delay
        fi
    done
    
    echo "❌ Failed to deliver message after $MAX_ATTEMPTS attempts"
    return 1
}

# Self-referential detection (enhanced)
if [ -n "$TMUX" ]; then  # Only check if actually inside tmux
    CURRENT_WINDOW=$(tmux display-message -p "#{session_name}:#{window_index}" 2>/dev/null | tr -d '[:space:]')  # Trim whitespace
    if [ -z "$CURRENT_WINDOW" ]; then
        # Failed to get current window - assuming not self
        :  # No-op
    elif [ "$CURRENT_WINDOW" = "$WINDOW" ]; then
        echo "WARNING: Attempting to send message to self ($WINDOW). Skipping."
        exit 0
    fi
else
    # Not inside tmux - proceeding with send
    :  # No-op
fi

# Validate target exists
if ! tmux has-session -t "$WINDOW" 2>/dev/null; then
    echo "ERROR: Target session/window $WINDOW does not exist."
    exit 1
fi

# Check if target process is alive
TARGET_PID=$(tmux display-message -p -t "$WINDOW" '#{pid}' 2>/dev/null)
if [ -z "$TARGET_PID" ] || ! ps -p "$TARGET_PID" > /dev/null 2>&1; then
    echo "ERROR: Target process is dead. Preventing message to phantom session."
    exit 1
fi

# Check if target is in copy mode (which would block input)
COPY_MODE=$(tmux display-message -p -t "$WINDOW" '#{pane_in_mode}' 2>/dev/null)
if [ "$COPY_MODE" = "1" ]; then
    echo "⚠️  Target is in copy mode, attempting to exit it..."
    tmux send-keys -t "$WINDOW" q 2>/dev/null
    sleep 0.5
fi

# Main sending logic with retry
if send_with_retry "$WINDOW" "$MESSAGE"; then
    echo "✅ Message successfully delivered to $WINDOW"
    exit 0
else
    echo "❌ Failed to deliver message to $WINDOW"
    
    # Log failure for monitoring
    if [ -d "$SCRIPT_DIR/registry/logs" ]; then
        echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") DELIVERY_FAILURE $WINDOW $MESSAGE" >> "$SCRIPT_DIR/registry/logs/message_failures.log"
    fi
    
    # Attempt recovery by notifying scheduler
    if [ -f "$SCRIPT_DIR/scheduler.py" ]; then
        echo "🔧 Attempting session recovery via scheduler..."
        python3 "$SCRIPT_DIR/scheduler.py" --reset-session "$WINDOW" 2>/dev/null || true
    fi
    
    exit 1
fi
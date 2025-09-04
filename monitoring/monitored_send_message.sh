#!/bin/bash
# Fixed monitored message sender - ensures proper message delivery
# Usage: monitored_send_message_fixed.sh <session:window> <message>

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PARENT_DIR/registry/logs/communications/$(date +%Y-%m-%d)"
MESSAGE_LOG="$LOG_DIR/messages.jsonl"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window> <message>"
    echo "Example: $0 pm:1 'Status update please'"
    exit 1
fi

TARGET="$1"
shift
MESSAGE="$*"

# Extract sender information from current tmux pane
SENDER_PANE=$(tmux display-message -p "#{session_name}:#{window_index}" 2>/dev/null || echo "unknown:0")
SENDER_SESSION=$(echo "$SENDER_PANE" | cut -d: -f1)
SENDER_WINDOW=$(echo "$SENDER_PANE" | cut -d: -f2)

# Extract target information
TARGET_SESSION=$(echo "$TARGET" | cut -d: -f1)
TARGET_WINDOW=$(echo "$TARGET" | cut -d: -f2)

# Create JSON log entry (JSONL format - single line)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Build JSON as a single line using jq with compact output
LOG_ENTRY=$(jq -c -n \
  --arg ts "$TIMESTAMP" \
  --arg ss "$SENDER_SESSION" \
  --arg sw "$SENDER_WINDOW" \
  --arg sp "$SENDER_PANE" \
  --arg rs "$TARGET_SESSION" \
  --arg rw "$TARGET_WINDOW" \
  --arg rp "$TARGET" \
  --arg msg "$MESSAGE" \
  '{timestamp: $ts, sender: {session: $ss, window: $sw, pane: $sp}, recipient: {session: $rs, window: $rw, pane: $rp}, message: $msg, compliance_checked: false}')

# Log the message (single line for JSONL)
echo "$LOG_ENTRY" >> "$MESSAGE_LOG"

# IMPORTANT FIX: Send the message directly without MCP wrapper commands
# The original script was creating echo commands that weren't executed properly
if [ "$USE_TMUX_MANAGER" = "1" ]; then
    echo "🔧 Monitored messaging: Using TmuxManager for centralized operations"
    USE_TMUX_MANAGER=1 "$PARENT_DIR/send-claude-message.sh" "$TARGET" "$MESSAGE"
else
    # Direct send without problematic echo wrappers
    "$PARENT_DIR/send-claude-message.sh" "$TARGET" "$MESSAGE"
fi

# Enhanced verification: Check if message was properly delivered
sleep 2  # Give message time to be processed
VERIFICATION_RESULT=$(tmux capture-pane -p -t "$TARGET" -S -10 2>/dev/null)

# Check for stuck MCP patterns that indicate Enter wasn't pressed
if echo "$VERIFICATION_RESULT" | grep -q "TMUX_MCP_START\|TMUX_MCP_DONE"; then
    echo "⚠️  Message may be stuck in $TARGET, attempting to fix"
    
    # Send Enter to complete the stuck message
    if tmux send-keys -t "$TARGET" Enter 2>/dev/null; then
        sleep 1
        
        # Verify the fix
        FIXED_RESULT=$(tmux capture-pane -p -t "$TARGET" -S -5 2>/dev/null)
        if ! echo "$FIXED_RESULT" | grep -q "TMUX_MCP_START\|TMUX_MCP_DONE"; then
            echo "✅ Successfully cleared stuck message in $TARGET"
            
            # Log the fix attempt
            FIX_LOG_ENTRY=$(jq -c -n \
              --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
              --arg target "$TARGET" \
              --arg action "fixed_stuck_message" \
              --arg success "true" \
              '{timestamp: $ts, target: $target, action: $action, success: $success}')
            echo "$FIX_LOG_ENTRY" >> "$LOG_DIR/message_fixes.jsonl"
        else
            echo "❌ Failed to clear stuck message in $TARGET"
            
            # Log the failed fix attempt  
            FIX_LOG_ENTRY=$(jq -c -n \
              --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
              --arg target "$TARGET" \
              --arg action "failed_to_fix_stuck_message" \
              --arg success "false" \
              '{timestamp: $ts, target: $target, action: $action, success: $success}')
            echo "$FIX_LOG_ENTRY" >> "$LOG_DIR/message_fixes.jsonl"
        fi
    fi
fi

# Trigger async compliance check if monitor is running
if pgrep -f "compliance_monitor.py" > /dev/null; then
    # Touch a trigger file to notify the monitor
    touch "$LOG_DIR/.new_messages"
fi

echo "Message logged and sent to $TARGET"
#!/bin/bash

# scm (Standardized Claude Messaging) - Enhanced wrapper for send-claude-message.sh
# Provides MCP wrapper prevention, monitoring, and standardized messaging
# Usage: scm <target> "message"

if [ $# -lt 2 ]; then
    echo "Usage: scm <target> \"message\""
    echo "Example: scm agentic-seek:3 'Hello Claude!'"
    echo "         scm tmux-orc:0.1 'Message to pane 1'"
    exit 1
fi

TARGET="$1"
MESSAGE="$2"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Enhanced MCP wrapper prevention at entry point
clean_message_mcp() {
    local msg="$1"
    
    # Remove comprehensive MCP wrapper patterns
    msg=$(echo "$msg" | sed -E 's/^echo[[:space:]]+[\"'\''"]?TMUX_MCP_START[\"'\''"]?;[[:space:]]*//g')
    msg=$(echo "$msg" | sed -E 's/;[[:space:]]*echo[[:space:]]+[\"'\''"]?TMUX_MCP_DONE_\$\?[\"'\''"]?[[:space:]]*$//g')
    msg=$(echo "$msg" | sed -E 's/echo[[:space:]]+[\"'\''"]?TMUX_MCP_START[\"'\''"]?;[[:space:]]*//g')
    msg=$(echo "$msg" | sed -E 's/;[[:space:]]*echo[[:space:]]+[\"'\''"]?TMUX_MCP_DONE_\$\?[\"'\''"]?//g')
    msg=$(echo "$msg" | sed -E 's/TMUX_MCP_START[[:space:]]*;?[[:space:]]*//g')
    msg=$(echo "$msg" | sed -E 's/;[[:space:]]*TMUX_MCP_DONE_\$\?[[:space:]]*//g')
    
    # Clean up shell wrapper patterns
    msg=$(echo "$msg" | sed -E 's/bash[[:space:]]+-c[[:space:]]+[\"'\''"]echo[[:space:]]+[\"'\''"]?TMUX_MCP_START[\"'\''"]?;//g')
    msg=$(echo "$msg" | sed -E 's/echo[[:space:]]+[\"'\''"]?MCP_EXECUTE_START[\"'\''"]?;//g')
    msg=$(echo "$msg" | sed -E 's/;[[:space:]]*echo[[:space:]]+[\"'\''"]?MCP_EXECUTE_END_\$\?[\"'\''"]?//g')
    
    # Clean up artifacts
    msg=$(echo "$msg" | sed -E 's/;[[:space:]]*;/;/g')         # Double semicolons
    msg=$(echo "$msg" | sed -E 's/^[[:space:]]*;[[:space:]]*//g')  # Leading semicolon
    msg=$(echo "$msg" | sed -E 's/[[:space:]]*;[[:space:]]*$//g') # Trailing semicolon
    msg=$(echo "$msg" | sed -E 's/[[:space:]]+/ /g')           # Multiple spaces
    msg=$(echo "$msg" | sed -E 's/^[[:space:]]*//g; s/[[:space:]]*$//g') # Trim
    
    echo "$msg"
}

# Clean the message before processing
CLEAN_MESSAGE=$(clean_message_mcp "$MESSAGE")

# Log cleaned message for debugging if significant cleaning occurred
if [ ${#MESSAGE} -gt $((${#CLEAN_MESSAGE} + 20)) ]; then
    echo "🧹 Cleaned MCP wrappers: ${#MESSAGE} → ${#CLEAN_MESSAGE} chars"
fi

# Use the enhanced send-claude-message.sh script with cleaned message
exec "$SCRIPT_DIR/send-claude-message.sh" "$TARGET" "$CLEAN_MESSAGE"
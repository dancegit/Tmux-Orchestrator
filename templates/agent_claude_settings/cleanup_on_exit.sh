#!/bin/bash
# Cleanup script to be called when an agent session ends
# This replaces the SessionEnd hook functionality

AGENT_ID="${1:-${TMUX_SESSION_NAME}:${TMUX_WINDOW_INDEX}}"
CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Run the cleanup agent script
if [ -f "$CLAUDE_PROJECT_DIR/.claude/hooks/cleanup_agent.py" ]; then
    python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/cleanup_agent.py" --agent "$AGENT_ID"
fi

# Remove the initialized flag
rm -f "$CLAUDE_PROJECT_DIR/.claude/.initialized"

echo "Cleanup completed for agent: $AGENT_ID"
#!/bin/bash
# Manually trigger project completion by creating a marker file
# Usage: ./trigger_completion.sh [optional_message]
# Must be run from Orchestrator's worktree directory

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get current directory
CURRENT_DIR=$(pwd)

# Check if we're in an orchestrator worktree
if [[ ! "$CURRENT_DIR" =~ worktrees/orchestrator$ ]] && [[ ! "$CURRENT_DIR" =~ worktrees/orchestrator/.*$ ]]; then
    echo -e "${RED}Error: This script must be run from the Orchestrator's worktree directory.${NC}"
    echo -e "${YELLOW}Current directory: $CURRENT_DIR${NC}"
    echo -e "${YELLOW}Expected pattern: .../worktrees/orchestrator${NC}"
    exit 1
fi

# Find the orchestrator worktree root (in case we're in a subdirectory)
WORKTREE_ROOT="$CURRENT_DIR"
while [[ ! -d "$WORKTREE_ROOT/.git" ]] && [[ "$WORKTREE_ROOT" != "/" ]]; do
    WORKTREE_ROOT=$(dirname "$WORKTREE_ROOT")
done

if [[ ! -d "$WORKTREE_ROOT/.git" ]]; then
    echo -e "${RED}Error: Could not find git worktree root.${NC}"
    exit 1
fi

# Create marker file
MARKER_FILE="$WORKTREE_ROOT/COMPLETED"
MESSAGE=${1:-"Project completed successfully by Orchestrator decision."}

# Get additional context
SESSION_NAME=$(tmux display-message -p '#S' 2>/dev/null || echo "unknown")
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')
GIT_BRANCH=$(cd "$WORKTREE_ROOT" && git branch --show-current 2>/dev/null || echo "unknown")
GIT_COMMIT=$(cd "$WORKTREE_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Create marker with detailed information
cat > "$MARKER_FILE" << EOF
Project Completion Marker
========================
Timestamp: $TIMESTAMP
Session: $SESSION_NAME
Branch: $GIT_BRANCH
Commit: $GIT_COMMIT
Triggered By: Orchestrator Manual Decision

Message: $MESSAGE

Notes:
- Email notification will be sent on next monitor check (within 5 minutes)
- This marker indicates all project success criteria have been met
- The completion has been verified by the Orchestrator agent
EOF

echo -e "${GREEN}✓ Completion triggered successfully!${NC}"
echo -e "  Marker file: $MARKER_FILE"
echo -e "  Session: $SESSION_NAME"
echo -e "  Message: $MESSAGE"
echo -e ""
echo -e "${YELLOW}The completion notification will be sent within the next 5 minutes.${NC}"

# Optionally, log the completion
LOG_DIR="$WORKTREE_ROOT/../../registry/logs"
if [[ -d "$LOG_DIR" ]]; then
    echo "[$TIMESTAMP] Completion triggered for $SESSION_NAME: $MESSAGE" >> "$LOG_DIR/completions.log"
fi
#!/bin/bash

# Post-commit hook for fast lane triggers
# Copy this to .git/hooks/post-commit in each agent's worktree

# Detect role from worktree path
WORKTREE_PATH=$(pwd)
if [[ "$WORKTREE_PATH" == *"/developer/"* ]]; then
    ROLE="developer"
    TARGETS=("tester:0" "testrunner:0")
elif [[ "$WORKTREE_PATH" == *"/tester/"* ]]; then
    ROLE="tester"  
    TARGETS=("testrunner:0" "pm:0")
elif [[ "$WORKTREE_PATH" == *"/testrunner/"* ]]; then
    ROLE="testrunner"
    TARGETS=("pm:0" "orchestrator:0")
else
    # Not a fast lane role
    exit 0
fi

# Get the latest commit info
LATEST_COMMIT=$(git log --oneline -1)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Send fast lane trigger notifications
for target in "${TARGETS[@]}"; do
    if command -v scm >/dev/null 2>&1; then
        scm "$target" "FAST_LANE_TRIGGER: $ROLE pushed to $BRANCH: $LATEST_COMMIT"
    fi
done

# Log the trigger
LOG_DIR="../../../registry/logs/fast-lane"
mkdir -p "$LOG_DIR"
echo "$(date '+%Y-%m-%d %H:%M:%S') [$ROLE] Triggered fast lane notifications for: $LATEST_COMMIT" >> "$LOG_DIR/$(date +%Y-%m-%d).log"
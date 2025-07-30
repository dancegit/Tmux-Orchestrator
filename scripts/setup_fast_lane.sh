#!/bin/bash

# Setup Fast Lane Git Hooks for All Agent Worktrees
# Usage: ./setup_fast_lane.sh [project_name]

PROJECT_NAME=${1:-""}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "$PROJECT_NAME" ]]; then
    echo "Usage: $0 <project_name>"
    echo "Example: $0 cryptocurrency-transaction-analyzer"
    exit 1
fi

WORKTREES_DIR="$SCRIPT_DIR/../registry/projects/$PROJECT_NAME/worktrees"

if [[ ! -d "$WORKTREES_DIR" ]]; then
    echo "Error: Project worktrees not found at $WORKTREES_DIR"
    exit 1
fi

echo "Setting up fast lane hooks for project: $PROJECT_NAME"

# Install post-commit hooks in relevant worktrees
for worktree in developer tester testrunner; do
    WORKTREE_PATH="$WORKTREES_DIR/$worktree"
    if [[ -d "$WORKTREE_PATH" ]]; then
        # Handle worktree git directory structure
        if [[ -f "$WORKTREE_PATH/.git" ]]; then
            # Worktree with git file pointing to actual git dir
            GIT_DIR=$(cat "$WORKTREE_PATH/.git" | sed 's/gitdir: //')
            HOOKS_DIR="$GIT_DIR/hooks"
        else
            # Regular git repository
            HOOKS_DIR="$WORKTREE_PATH/.git/hooks"
        fi
        
        mkdir -p "$HOOKS_DIR"
        
        # Copy post-commit hook
        cp "$SCRIPT_DIR/post-commit-fast-lane.sh" "$HOOKS_DIR/post-commit"
        chmod +x "$HOOKS_DIR/post-commit"
        
        echo "✅ Installed fast lane hook in $worktree worktree (git dir: $HOOKS_DIR)"
    else
        echo "⚠️  Worktree not found: $worktree"
    fi
done

# Create fast lane log directory
LOG_DIR="$SCRIPT_DIR/../registry/logs/fast-lane"
mkdir -p "$LOG_DIR"

echo ""
echo "🚀 Fast Lane Setup Complete!"
echo ""
echo "Features enabled:"
echo "- Post-commit triggers for Developer → Tester → TestRunner"
echo "- Automatic merge notifications via scm"
echo "- Conflict escalation to PM"
echo "- Activity logging to registry/logs/fast-lane/"
echo ""
echo "Agents can now use: ./scripts/fast_lane_sync.sh"
echo "PM can disable with: export DISABLE_FAST_LANE=true"
#!/bin/bash
SESSION="MOBILE-APP-SPEC-V2-416343a3"
WORKTREE_BASE="/home/clauderun/mobile_app_spec_v2-tmux-worktrees"
PROJECT_DIR="/home/clauderun/mobile_app_spec_v2"

echo "Fixing agents in session: $SESSION"
echo "Moving agents to correct worktrees..."

# Kill any running claude processes and restart in correct directories
declare -A agents=(
    [0]="orchestrator"
    [1]="project_manager"  
    [2]="developer"
    [3]="tester"
    [4]="testrunner"
)

for window in "${!agents[@]}"; do
    role="${agents[$window]}"
    worktree="$WORKTREE_BASE/$role"
    
    echo "Fixing window $window ($role)..."
    
    # Kill current process
    tmux send-keys -t "$SESSION:$window" C-c
    sleep 1
    
    # Navigate to correct worktree
    tmux send-keys -t "$SESSION:$window" "cd $worktree" Enter
    sleep 1
    
    # Restart claude in the correct directory
    tmux send-keys -t "$SESSION:$window" "claude --dangerously-skip-permissions" Enter
    sleep 3
done

echo "All agents moved to correct directories!"

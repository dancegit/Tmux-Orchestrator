#!/bin/bash
# Git wrapper scripts for autonomous conflict resolution
# These commands integrate with GitCoordinator and GitConflictResolver

TMUX_ORCHESTRATOR_PATH="${TMUX_ORCHESTRATOR_PATH:-$(dirname "$0")}"

# Function to get current agent role from worktree path
get_agent_role() {
    local worktree_path="$1"
    basename "$worktree_path"
}

# git-sync-and-resolve: Sync from source with autonomous conflict resolution
# Usage: git-sync-and-resolve --source <branch/role> [--targets <roles>]
git-sync-and-resolve() {
    local source=""
    local targets="all"
    local worktree_path=$(pwd)
    local agent_role=$(get_agent_role "$worktree_path")
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --source)
                source="$2"
                shift 2
                ;;
            --targets)
                targets="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                return 1
                ;;
        esac
    done
    
    if [ -z "$source" ]; then
        echo "Error: --source is required"
        return 1
    fi
    
    echo "Syncing from $source with autonomous conflict resolution..."
    
    # First, try preview
    python3 "$TMUX_ORCHESTRATOR_PATH/git_conflict_resolver.py" \
        "$worktree_path" "$source" "$agent_role" --preview
    
    if [ $? -eq 0 ]; then
        # No conflicts, proceed with normal merge
        git merge "$source" --no-ff -m "Synced from $source"
    else
        # Conflicts detected, attempt autonomous resolution
        python3 "$TMUX_ORCHESTRATOR_PATH/git_conflict_resolver.py" \
            "$worktree_path" "$source" "$agent_role"
        
        if [ $? -ne 0 ]; then
            echo "Autonomous resolution failed. Please resolve manually or escalate to PM."
            return 1
        fi
    fi
    
    echo "Sync complete!"
    return 0
}

# git-detect-divergence: Check if current branch has diverged
# Usage: git-detect-divergence
git-detect-divergence() {
    local project_name=$(basename $(dirname $(dirname $(pwd))))
    
    python3 -c "
from pathlib import Path
from git_coordinator import GitCoordinator
from session_state import SessionStateManager

base_path = Path('$TMUX_ORCHESTRATOR_PATH/registry/projects/$project_name')
state_manager = SessionStateManager(base_path)
state = state_manager.load_session_state('$project_name')

if state:
    coordinator = GitCoordinator(Path('.').parent.parent)
    diverged = coordinator.detect_divergence(state)
    print(f'Divergence detected: {diverged}')
    exit(0 if not diverged else 1)
else:
    print('Could not load session state')
    exit(2)
"
}

# git-resolve-conflict: Resolve conflicts with AI assistance
# Usage: git-resolve-conflict --ai --files <file1,file2>
git-resolve-conflict() {
    local use_ai=false
    local files=""
    local worktree_path=$(pwd)
    local agent_role=$(get_agent_role "$worktree_path")
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --ai)
                use_ai=true
                shift
                ;;
            --files)
                files="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                return 1
                ;;
        esac
    done
    
    if [ "$use_ai" = true ]; then
        echo "Attempting AI-assisted conflict resolution..."
        python3 "$TMUX_ORCHESTRATOR_PATH/git_conflict_resolver.py" \
            "$worktree_path" "HEAD" "$agent_role" --resolve-only
    else
        echo "Please specify --ai for autonomous resolution"
        return 1
    fi
}

# pm-fetch-all: PM-specific command to fetch from all agents
# Usage: pm-fetch-all
pm-fetch-all() {
    if [ ! -f "tools/pm_fetch_all.py" ]; then
        echo "Error: pm_fetch_all.py not found. Are you in the PM worktree?"
        return 1
    fi
    
    python3 tools/pm_fetch_all.py
}

# git-sync-all: Sync all agents from current branch (PM use)
# Usage: git-sync-all --source <role>
git-sync-all() {
    local source="pm"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --source)
                source="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                return 1
                ;;
        esac
    done
    
    echo "Syncing all agents from $source..."
    
    # Get list of remotes (other agents)
    for remote in $(git remote | grep -v origin); do
        echo "Syncing $remote..."
        git push "$remote" integration:integration --force-with-lease
    done
}

# Export functions for use in subshells
export -f git-sync-and-resolve
export -f git-detect-divergence
export -f git-resolve-conflict
export -f pm-fetch-all
export -f git-sync-all

# Make available as commands if sourced
if [ "$0" = "${BASH_SOURCE[0]}" ]; then
    # Script is being executed directly
    command="$1"
    shift
    case "$command" in
        sync-and-resolve)
            git-sync-and-resolve "$@"
            ;;
        detect-divergence)
            git-detect-divergence "$@"
            ;;
        resolve-conflict)
            git-resolve-conflict "$@"
            ;;
        fetch-all)
            pm-fetch-all "$@"
            ;;
        sync-all)
            git-sync-all "$@"
            ;;
        *)
            echo "Usage: $0 {sync-and-resolve|detect-divergence|resolve-conflict|fetch-all|sync-all} [options]"
            exit 1
            ;;
    esac
fi
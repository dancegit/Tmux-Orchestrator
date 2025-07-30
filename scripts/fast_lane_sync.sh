#!/bin/bash

# Fast Lane Auto-Sync Script
# Usage: ./fast_lane_sync.sh [role] [source_branch]
# Called automatically by agents during check-ins

set -e

ROLE=${1:-$(whoami)}
SOURCE_BRANCH=${2:-""}
PROJECT_ROOT=$(pwd)
DISABLE_FAST_LANE=${DISABLE_FAST_LANE:-false}

# Logging
LOG_DIR="registry/logs/fast-lane"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$ROLE] $1" | tee -a "$LOG_FILE"
}

# Check if fast lane is disabled
if [[ "$DISABLE_FAST_LANE" == "true" ]]; then
    log "Fast lane disabled via DISABLE_FAST_LANE flag"
    exit 0
fi

# Determine source branch based on role
case "$ROLE" in
    "tester")
        if [[ -z "$SOURCE_BRANCH" ]]; then
            # Auto-detect developer branch
            SOURCE_BRANCH=$(git branch -r | grep "origin/feature/" | head -1 | sed 's/.*origin\///')
        fi
        NOTIFICATION_TARGET="pm:0"
        ;;
    "testrunner") 
        if [[ -z "$SOURCE_BRANCH" ]]; then
            # Auto-detect tester branch  
            SOURCE_BRANCH=$(git branch -r | grep "origin/test/" | head -1 | sed 's/.*origin\///')
        fi
        NOTIFICATION_TARGET="pm:0"
        ;;
    *)
        log "Fast lane not configured for role: $ROLE"
        exit 0
        ;;
esac

if [[ -z "$SOURCE_BRANCH" ]]; then
    log "No source branch detected for fast lane sync"
    exit 0
fi

log "Starting fast lane sync from $SOURCE_BRANCH"

# Fetch latest changes
git fetch origin

# Check if there are changes to pull
if git diff HEAD "origin/$SOURCE_BRANCH" --quiet; then
    log "No changes detected in $SOURCE_BRANCH"
    exit 0
fi

# Show what we're about to merge
CHANGES=$(git log HEAD.."origin/$SOURCE_BRANCH" --oneline | head -3)
log "Changes detected: $CHANGES"

# Attempt auto-merge
if git merge "origin/$SOURCE_BRANCH" --no-edit --no-commit; then
    # Check for conflicts
    if git diff --name-only --diff-filter=U | grep -q .; then
        log "CONFLICT DETECTED: Escalating to PM"
        git merge --abort
        
        # Notify PM of conflict
        if command -v scm >/dev/null 2>&1; then
            scm pm:0 "FAST_LANE_CONFLICT: $ROLE cannot auto-merge $SOURCE_BRANCH - manual resolution needed"
        fi
        exit 1
    else
        # Clean merge, commit it
        git commit --no-edit
        MERGE_COMMIT=$(git log --oneline -1)
        log "Successfully merged: $MERGE_COMMIT"
        
        # Notify PM of successful fast lane merge
        if command -v scm >/dev/null 2>&1; then
            scm "$NOTIFICATION_TARGET" "Fast lane: $ROLE auto-merged $SOURCE_BRANCH: $MERGE_COMMIT"
        fi
        
        # Trigger role-specific actions
        case "$ROLE" in
            "tester")
                log "Running test suite after fast lane merge"
                # Could trigger test execution here
                ;;
            "testrunner")
                log "Executing tests after fast lane merge"
                # Could trigger test runner here
                ;;
        esac
        
    fi
else
    log "MERGE FAILED: Escalating to PM"
    git merge --abort 2>/dev/null || true
    
    if command -v scm >/dev/null 2>&1; then
        scm pm:0 "FAST_LANE_FAILURE: $ROLE failed to merge $SOURCE_BRANCH - manual intervention required"
    fi
    exit 1
fi

log "Fast lane sync completed successfully"
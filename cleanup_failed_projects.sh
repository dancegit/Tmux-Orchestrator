#!/bin/bash
# Script to clean up failed projects with no implementation

echo "=== Cleaning up failed projects with no implementation ==="
echo

# Projects to clean up (IDs from database)
PROJECT_IDS="83 84 88 90"

# First, backup the database
echo "1. Backing up database..."
cp task_queue.db task_queue.db.backup.$(date +%Y%m%d_%H%M%S)

# Remove from database
echo "2. Removing projects from database..."
for id in $PROJECT_IDS; do
    echo "   Removing project $id..."
    sqlite3 task_queue.db "DELETE FROM project_queue WHERE id = $id"
done

echo "3. Database cleanup complete"
echo

# Now clean up worktrees and directories
echo "4. Cleaning up project directories and worktrees..."

# Project 83: vertical-slice-orchestration-system slice-001
DIR1="/home/clauderun/vertical-slice-orchestration-system-20250902-232958/vertical-slices/repos/slice-001-core-components-tmux-worktrees"
if [ -d "$DIR1" ]; then
    echo "   Removing: $DIR1"
    rm -rf "$DIR1"
fi

# Project 84: vertical-slice-orchestration-system slice-002  
DIR2="/home/clauderun/vertical-slice-orchestration-system-20250902-232958/vertical-slices/repos/slice-002-data-ingestion-service-tmux-worktrees"
if [ -d "$DIR2" ]; then
    echo "   Removing: $DIR2"
    rm -rf "$DIR2"
fi

# Project 88: test_project
DIR3="/tmp/test_project"
if [ -d "$DIR3" ]; then
    echo "   Removing: $DIR3"
    rm -rf "$DIR3"
fi
# Check for worktrees
DIR3_WT="/tmp/test_project-tmux-worktrees"
if [ -d "$DIR3_WT" ]; then
    echo "   Removing: $DIR3_WT"
    rm -rf "$DIR3_WT"
fi

# Project 90: mcp_server_spec_v2
DIR4="/home/clauderun/mcp_server_spec_v2"
if [ -d "$DIR4" ]; then
    echo "   Removing: $DIR4"
    rm -rf "$DIR4"
fi
# Check for worktrees
DIR4_WT="/home/clauderun/mcp_server_spec_v2-tmux-worktrees"
if [ -d "$DIR4_WT" ]; then
    echo "   Removing: $DIR4_WT"
    rm -rf "$DIR4_WT"
fi

echo
echo "5. Directory cleanup complete"
echo

# Clean up any registry entries
echo "6. Cleaning up registry entries..."
for id in $PROJECT_IDS; do
    # Find registry directories
    REGISTRY_DIRS=$(find registry/projects/ -type d -name "*$(printf "%08d" $id)*" 2>/dev/null)
    for dir in $REGISTRY_DIRS; do
        if [ -d "$dir" ]; then
            echo "   Removing registry: $dir"
            rm -rf "$dir"
        fi
    done
done

echo
echo "=== Cleanup complete ==="
echo
echo "Removed projects: $PROJECT_IDS"
echo "Database backed up to: task_queue.db.backup.$(date +%Y%m%d_%H%M%S)"

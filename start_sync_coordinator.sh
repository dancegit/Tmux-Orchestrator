#!/bin/bash
# Start sync coordinator for a project
# Usage: ./start_sync_coordinator.sh <project-name> [registry-dir]

PROJECT=$1
REGISTRY_DIR=$2

if [ -z "$PROJECT" ]; then
    echo "Usage: $0 <project-name> [registry-dir]"
    echo "Example: $0 my-project"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Check if sync coordinator is already running for this project
if pgrep -f "sync_coordinator.py $PROJECT" > /dev/null; then
    echo "Sync coordinator already running for project: $PROJECT"
    echo "To view dashboard: watch -n 1 cat registry/projects/$PROJECT/sync_dashboard.txt"
    exit 0
fi

echo "Starting sync coordinator for project: $PROJECT"

# Start in background
if [ -z "$REGISTRY_DIR" ]; then
    nohup python3 "$SCRIPT_DIR/sync_coordinator.py" "$PROJECT" > "$SCRIPT_DIR/sync_coordinator_$PROJECT.log" 2>&1 &
else
    nohup python3 "$SCRIPT_DIR/sync_coordinator.py" "$PROJECT" --registry-dir "$REGISTRY_DIR" > "$SCRIPT_DIR/sync_coordinator_$PROJECT.log" 2>&1 &
fi

PID=$!
echo "Sync coordinator started (PID: $PID)"
echo "Dashboard: registry/projects/$PROJECT/sync_dashboard.txt"
echo "Logs: sync_coordinator_$PROJECT.log"
echo ""
echo "To view dashboard in real-time:"
echo "  watch -n 1 cat registry/projects/$PROJECT/sync_dashboard.txt"
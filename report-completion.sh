#!/bin/bash

# Report task completion to Orchestrator with automatic hub-and-spoke enforcement
# Usage: report-completion.sh <role> "<completion_message>"
# Example: report-completion.sh devops "Modal deployment complete - EVENT_ROUTER_ENABLED=true"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <role> \"<completion_message>\""
    echo "Example: $0 devops \"Deployment complete\""
    exit 1
fi

ROLE="$1"
COMPLETION_MESSAGE="$2"

# Get current session from tmux
SESSION=$(tmux display-message -p '#{session_name}' 2>/dev/null)
if [ -z "$SESSION" ]; then
    echo "Error: Not running in a tmux session"
    exit 1
fi

# Get window index from tmux
WINDOW=$(tmux display-message -p '#{window_index}' 2>/dev/null)

# Create completion report
TIMESTAMP=$(date -Iseconds)
REPORT="TASK COMPLETION REPORT
Role: $ROLE (window $WINDOW)
Time: $TIMESTAMP
Status: $COMPLETION_MESSAGE

This completion has been automatically reported to maintain hub-and-spoke compliance."

# Update session state with Python
python3 << EOF
import sys
sys.path.append('$SCRIPT_DIR')
from session_state import SessionStateManager
from datetime import datetime
from pathlib import Path

mgr = SessionStateManager(Path('$SCRIPT_DIR'))
project_name = "$SESSION".split('-impl')[0].replace('-', ' ').title()

# Update agent state
mgr.update_agent_state(project_name, "$ROLE", {
    'last_check_in_time': datetime.now().isoformat(),
    'completion_status': 'completed'
})

# Also trigger scheduler completion if available
try:
    from scheduler import TmuxOrchestratorScheduler
    scheduler = TmuxOrchestratorScheduler(tmux_orchestrator_path=Path('$SCRIPT_DIR'))
    
    # Find any active tasks for this role
    tasks = scheduler.list_tasks()
    for task in tasks:
        if task[2] == "$ROLE":  # agent_role column
            scheduler.complete_task(task[0], "$SESSION", "$ROLE", "$COMPLETION_MESSAGE")
            break
except Exception as e:
    print(f"Could not update scheduler: {e}")
EOF

# Send completion report to Orchestrator using hub-spoke enforced script
if [ -f "$SCRIPT_DIR/send-claude-message-hubspoke.sh" ]; then
    "$SCRIPT_DIR/send-claude-message-hubspoke.sh" "$SESSION:0" "$REPORT"
else
    # Fallback to regular script
    "$SCRIPT_DIR/send-claude-message.sh" "$SESSION:0" "$REPORT"
fi

# Also update local agent
echo "$REPORT" | tee -a "$SCRIPT_DIR/registry/logs/completions.log"

echo "Completion reported successfully!"
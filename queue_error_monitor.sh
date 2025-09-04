#!/bin/bash
#
# Queue Error Monitoring Service
# Monitors ./qs output and addresses errors in non-completed projects
#

set -euo pipefail

# Configuration
TMUX_ORCHESTRATOR_HOME="${TMUX_ORCHESTRATOR_HOME:-/home/clauderun/Tmux-Orchestrator}"
SESSION_NAME="queue-error-monitoring-service"
LOCK_FILE="$TMUX_ORCHESTRATOR_HOME/logs/queue_monitor.lock"
LOG_FILE="$TMUX_ORCHESTRATOR_HOME/logs/queue_error_monitor.log"
MAX_LOG_SIZE="50M"
LOG_RETAIN=7

# Ensure log directory exists
mkdir -p "$TMUX_ORCHESTRATOR_HOME/logs"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$$] $*" | tee -a "$LOG_FILE"
}

# Log rotation function
rotate_log() {
    if [[ -f "$LOG_FILE" ]] && [[ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE") -gt $((50*1024*1024)) ]]; then
        log "Rotating log file (size limit reached)"
        mv "$LOG_FILE" "${LOG_FILE}.$(date +%Y%m%d_%H%M%S)"
        # Keep only last 7 rotated logs
        find "$TMUX_ORCHESTRATOR_HOME/logs" -name "queue_error_monitor.log.*" -type f | sort -r | tail -n +$((LOG_RETAIN+1)) | xargs -r rm -f
    fi
}

# Lock file management
acquire_lock() {
    if [[ -f "$LOCK_FILE" ]]; then
        local pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            log "Another instance is already running (PID: $pid). Exiting."
            exit 1
        else
            log "Stale lock file detected, removing..."
            rm -f "$LOCK_FILE"
        fi
    fi
    echo $$ > "$LOCK_FILE"
    log "Lock acquired (PID: $$)"
}

release_lock() {
    rm -f "$LOCK_FILE"
    log "Lock released"
}

# Trap to ensure cleanup
trap 'release_lock; exit' INT TERM EXIT

# Check if Claude is running in the tmux session
is_claude_running() {
    local pane_content=$(tmux capture-pane -t "$SESSION_NAME:0" -p 2>/dev/null || echo "")
    echo "$pane_content" | grep -q "bypass permissions" || echo "$pane_content" | grep -q "claude>" || echo "$pane_content" | grep -q "Claude"
}

# Start or ensure Claude is running
ensure_claude_running() {
    log "Ensuring Claude is running in session $SESSION_NAME"
    
    # Create session if it doesn't exist
    if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        log "Creating new tmux session: $SESSION_NAME"
        tmux new-session -d -s "$SESSION_NAME" -c "$TMUX_ORCHESTRATOR_HOME"
        sleep 2
    fi
    
    # Check if Claude is already running
    if is_claude_running; then
        log "Claude is already running in session"
        return 0
    fi
    
    # Start Claude
    log "Starting Claude in session"
    tmux send-keys -t "$SESSION_NAME:0" "claude --dangerously-skip-permissions" Enter
    sleep 5
    
    # Wait for Claude to fully load
    local attempts=0
    while [[ $attempts -lt 12 ]]; do
        if is_claude_running; then
            log "Claude started successfully"
            break
        fi
        sleep 5
        ((attempts++))
    done
    
    if [[ $attempts -eq 12 ]]; then
        log "ERROR: Failed to start Claude after 60 seconds"
        return 1
    fi
    
    # Brief Claude about the monitoring task
    brief_claude
}

# Brief Claude about the monitoring task
brief_claude() {
    log "Briefing Claude about monitoring tasks"
    
    local briefing_message="You are the Queue Error Monitoring Service for the Tmux Orchestrator system.

Your responsibilities:
1. Monitor the queue status using ./qs command
2. Identify and address errors in non-completed projects
3. Take corrective actions for failed or stuck projects
4. Report status and actions taken

Key commands:
- ./qs - Check queue status
- ./queue_status.py --reset <id> - Reset a failed project
- ./queue_status.py --remove <id> - Remove a problematic project

Current context: You are running as a systemd monitoring service, checking every 30 minutes.

Please start by reading the README.md and CLAUDE.md files to understand the system, then run ./qs to check the current queue status and identify any issues that need attention."

    # Send briefing message to Claude
    echo "$briefing_message" | while IFS= read -r line; do
        tmux send-keys -t "$SESSION_NAME:0" "$line"
        sleep 0.1
    done
    tmux send-keys -t "$SESSION_NAME:0" Enter
    
    sleep 3
    
    # Send command to read documentation
    tmux send-keys -t "$SESSION_NAME:0" "Please read README.md and CLAUDE.md to understand the system, then run ./qs to check current status and address any errors." Enter
}

# Parse queue status and identify errors
check_queue_errors() {
    log "Checking queue for errors..."
    
    cd "$TMUX_ORCHESTRATOR_HOME"
    
    # Get queue status
    local queue_output
    if ! queue_output=$(timeout 30 ./qs 2>&1); then
        log "ERROR: Failed to get queue status"
        return 1
    fi
    
    # Extract projects with errors (failed or completed with errors)
    local error_projects
    error_projects=$(echo "$queue_output" | awk '
        BEGIN { in_project = 0; project_id = ""; status = ""; error = "" }
        /^[✅❌🔄⏳].*\[.*\]/ {
            if (in_project && error != "" && (status == "FAILED" || status == "COMPLETED")) {
                print project_id ":" status ":" error
            }
            in_project = 1
            match($0, /\[([0-9]+)\]/, arr)
            project_id = arr[1]
            if (/❌/) status = "FAILED"
            else if (/✅/) status = "COMPLETED"
            else if (/🔄/) status = "PROCESSING"
            else if (/⏳/) status = "QUEUED"
            error = ""
        }
        /Error:/ {
            if (in_project) {
                sub(/.*Error: /, "", $0)
                error = $0
            }
        }
        END {
            if (in_project && error != "" && (status == "FAILED" || status == "COMPLETED")) {
                print project_id ":" status ":" error
            }
        }
    ')
    
    if [[ -z "$error_projects" ]]; then
        log "No projects with errors found"
        return 0
    fi
    
    log "Found projects with errors:"
    echo "$error_projects" | while IFS=':' read -r project_id status error_msg; do
        log "  Project $project_id ($status): $error_msg"
    done
    
    # Send error report to Claude
    local claude_message="I found the following projects with errors that need attention:

"
    echo "$error_projects" | while IFS=':' read -r project_id status error_msg; do
        claude_message="$claude_message
Project $project_id (Status: $status)
Error: $error_msg
"
    done
    
    claude_message="$claude_message

Please analyze these errors and take appropriate corrective actions. For failed projects, consider:
1. Checking if they actually completed successfully (phantom failures)
2. Resetting projects that can be retried: ./queue_status.py --reset <id>
3. Removing projects that are permanently broken: ./queue_status.py --remove <id>

Run ./qs first to see the current status, then take action."
    
    # Send to Claude
    tmux send-keys -t "$SESSION_NAME:0" "$claude_message" Enter
    
    log "Error report sent to Claude for analysis and action"
}

# Main monitoring function
main_monitor() {
    log "Starting queue error monitoring cycle"
    
    # Ensure tmux and Claude are running
    if ! ensure_claude_running; then
        log "ERROR: Failed to ensure Claude is running"
        return 1
    fi
    
    # Check for errors and brief Claude
    if ! check_queue_errors; then
        log "ERROR: Failed to check queue errors"
        return 1
    fi
    
    log "Monitoring cycle completed successfully"
}

# Main execution
main() {
    rotate_log
    acquire_lock
    
    log "=== Queue Error Monitor Started ==="
    log "PID: $$"
    log "TMUX_ORCHESTRATOR_HOME: $TMUX_ORCHESTRATOR_HOME"
    log "Session: $SESSION_NAME"
    
    if ! main_monitor; then
        log "ERROR: Monitoring cycle failed"
        exit 1
    fi
    
    log "=== Queue Error Monitor Completed ==="
}

# Execute main function
main "$@"
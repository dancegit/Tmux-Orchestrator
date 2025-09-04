#!/bin/bash
#
# Enhanced Queue Error Monitoring Service with Modularization Support
# Monitors ./qs output and addresses modularization-specific errors
#

set -euo pipefail

# Configuration
TMUX_ORCHESTRATOR_HOME="${TMUX_ORCHESTRATOR_HOME:-/home/clauderun/Tmux-Orchestrator}"
SESSION_NAME="queue-error-monitoring-service"
LOCK_FILE="$TMUX_ORCHESTRATOR_HOME/logs/queue_monitor.lock"
LOG_FILE="$TMUX_ORCHESTRATOR_HOME/logs/queue_error_monitor.log"
MODULAR_LOG="$TMUX_ORCHESTRATOR_HOME/logs/modularization_progress.log"
MAX_LOG_SIZE="50M"
LOG_RETAIN=7

# Ensure log directory exists
mkdir -p "$TMUX_ORCHESTRATOR_HOME/logs"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$$] $*" | tee -a "$LOG_FILE"
}

# Modularization progress logging
log_modular() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [MODULAR] $*" | tee -a "$MODULAR_LOG"
}

# Log rotation function
rotate_log() {
    if [[ -f "$LOG_FILE" ]] && [[ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE") -gt $((50*1024*1024)) ]]; then
        log "Rotating log file (size limit reached)"
        mv "$LOG_FILE" "${LOG_FILE}.$(date +%Y%m%d_%H%M%S)"
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

# Analyze modularization status
check_modularization_status() {
    log_modular "Checking modularization status..."
    
    local status=""
    
    # Check if tmux_orchestrator package exists
    if [[ -d "$TMUX_ORCHESTRATOR_HOME/tmux_orchestrator" ]]; then
        status="$status\n✅ tmux_orchestrator package found"
    else
        status="$status\n❌ tmux_orchestrator package missing"
    fi
    
    # Check if scheduler_modules exists
    if [[ -d "$TMUX_ORCHESTRATOR_HOME/scheduler_modules" ]]; then
        status="$status\n✅ scheduler_modules package found"
    else
        status="$status\n❌ scheduler_modules package missing"
    fi
    
    # Check if tmux_orchestrator_cli.py exists and is executable
    if [[ -x "$TMUX_ORCHESTRATOR_HOME/tmux_orchestrator_cli.py" ]]; then
        status="$status\n✅ tmux_orchestrator_cli.py is executable"
    else
        status="$status\n❌ tmux_orchestrator_cli.py not executable"
    fi
    
    # Check migration progress
    if [[ -f "$TMUX_ORCHESTRATOR_HOME/MIGRATION_TO_MODULAR.md" ]]; then
        status="$status\n📋 Migration documentation found"
    fi
    
    echo -e "$status"
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
    
    # Enhanced briefing for modularization support
    brief_claude_enhanced
}

# Enhanced briefing with modularization focus
brief_claude_enhanced() {
    log "Briefing Claude about enhanced monitoring tasks with modularization focus"
    
    local briefing_message="You are the Enhanced Queue Error Monitoring Service for the Tmux Orchestrator system.

PRIMARY MISSION: Fix and migrate the system to use the modular components:
1. tmux_orchestrator_cli.py (replaces auto_orchestrate.py)
2. scheduler_modules/ (replaces monolithic scheduler.py)

Your responsibilities:
1. Monitor queue using ./qs command
2. Identify errors specifically related to modularization:
   - 'tmux_orchestrator_cli.py run completed but no tmux session was created'
   - 'Subprocess failed: None'
   - Missing module imports
   - Path resolution issues
3. Fix modularization-specific issues:
   - Ensure tmux_orchestrator_cli.py properly delegates to auto_orchestrate.py
   - Fix missing imports in tmux_orchestrator modules
   - Update paths and configurations
4. Gradually migrate successful patterns

Key files to check and fix:
- /home/clauderun/Tmux-Orchestrator/tmux_orchestrator_cli.py
- /home/clauderun/Tmux-Orchestrator/tmux_orchestrator/core/orchestrator.py
- /home/clauderun/Tmux-Orchestrator/scheduler_modules/*.py

Reference documentation:
- docs/specs/auto-orchestrate-modularization.md
- docs/specs/scheduler_modularization_spec.md
- docs/MODULARIZATION_STATUS.md

Please start by:
1. Reading CLAUDE.md and README.md
2. Checking modularization status: ls -la tmux_orchestrator/ scheduler_modules/
3. Running ./qs to identify current errors
4. Investigating why tmux_orchestrator_cli.py fails to create sessions
5. Fixing identified issues

Focus on making the modular system work, not reverting to the old system."

    # Send briefing message to Claude
    echo "$briefing_message" | while IFS= read -r line; do
        tmux send-keys -t "$SESSION_NAME:0" "$line"
        sleep 0.05
    done
    tmux send-keys -t "$SESSION_NAME:0" Enter
    
    sleep 3
    
    # Send specific investigation command
    tmux send-keys -t "$SESSION_NAME:0" "First, check the modularization status by examining the tmux_orchestrator_cli.py file and investigating recent failures. Run: tail -50 logs/auto_orchestrate/project_* | grep -E 'ERROR|Failed|tmux_orchestrator_cli'" Enter
}

# Parse queue status and identify modularization-specific errors
check_modularization_errors() {
    log "Checking queue for modularization-specific errors..."
    
    cd "$TMUX_ORCHESTRATOR_HOME"
    
    # Get queue status
    local queue_output
    if ! queue_output=$(timeout 30 ./qs 2>&1); then
        log "ERROR: Failed to get queue status"
        return 1
    fi
    
    # Look for specific modularization error patterns
    local modular_errors=""
    
    # Pattern 1: tmux_orchestrator_cli.py failures
    if echo "$queue_output" | grep -q "tmux_orchestrator_cli.py run completed but no tmux session"; then
        modular_errors="$modular_errors\n🔧 tmux_orchestrator_cli.py failing to create sessions"
        log_modular "Detected: tmux_orchestrator_cli.py session creation failure"
    fi
    
    # Pattern 2: Subprocess failures (likely module import issues)
    if echo "$queue_output" | grep -q "Subprocess failed: None"; then
        modular_errors="$modular_errors\n🔧 Subprocess failures (possible module import issues)"
        log_modular "Detected: Subprocess failures indicating module issues"
    fi
    
    # Pattern 3: auto_orchestrate.py fallback failures
    if echo "$queue_output" | grep -q "auto_orchestrate.py completed but no tmux session"; then
        modular_errors="$modular_errors\n🔧 Even fallback to auto_orchestrate.py is failing"
        log_modular "Detected: Critical - both new and old systems failing"
    fi
    
    # Extract all failed project IDs
    local failed_projects=$(echo "$queue_output" | grep -E "^❌" | sed -n 's/.*\[\([0-9]*\)\].*/\1/p')
    
    if [[ -n "$modular_errors" ]]; then
        log_modular "Modularization errors detected:"
        echo -e "$modular_errors"
        
        # Send detailed analysis to Claude
        local claude_message="MODULARIZATION ISSUES DETECTED:

$modular_errors

Failed Project IDs: $failed_projects

INVESTIGATION STEPS:
1. Check tmux_orchestrator_cli.py:
   - Verify it properly imports and uses the modular components
   - Check the start_orchestration method in tmux_orchestrator/core/orchestrator.py
   - Ensure it falls back to auto_orchestrate.py correctly

2. Test the modular system:
   python3 -c 'from tmux_orchestrator.core.orchestrator import Orchestrator; print(\"Module loads OK\")'

3. Check recent logs for specific errors:
   tail -100 scheduler.log | grep -E 'tmux_orchestrator_cli|ERROR'
   
4. For each failed project, check if the issue is:
   - Missing imports in modules
   - Incorrect path resolution
   - OAuth port conflicts
   - Missing dependencies

5. Fix identified issues:
   - Update imports in tmux_orchestrator_cli.py
   - Fix path issues in tmux_orchestrator/core/orchestrator.py
   - Ensure proper delegation to auto_orchestrate.py

Please investigate and fix these issues to advance the modularization effort."
        
        tmux send-keys -t "$SESSION_NAME:0" "$claude_message" Enter
        
        log_modular "Sent modularization fix request to Claude"
    else
        log "No specific modularization errors detected"
    fi
    
    # Check and report modularization progress
    local mod_status=$(check_modularization_status)
    log_modular "Current modularization status:$mod_status"
}

# Main monitoring function
main_monitor() {
    log "Starting enhanced queue error monitoring cycle with modularization focus"
    
    # Ensure tmux and Claude are running
    if ! ensure_claude_running; then
        log "ERROR: Failed to ensure Claude is running"
        return 1
    fi
    
    # Check for modularization-specific errors
    if ! check_modularization_errors; then
        log "ERROR: Failed to check modularization errors"
        return 1
    fi
    
    log "Enhanced monitoring cycle completed successfully"
}

# Main execution
main() {
    rotate_log
    acquire_lock
    
    log "=== Enhanced Queue Error Monitor Started ==="
    log "PID: $$"
    log "TMUX_ORCHESTRATOR_HOME: $TMUX_ORCHESTRATOR_HOME"
    log "Session: $SESSION_NAME"
    log "Focus: Modularization migration support"
    
    if ! main_monitor; then
        log "ERROR: Monitoring cycle failed"
        exit 1
    fi
    
    log "=== Enhanced Queue Error Monitor Completed ==="
}

# Execute main function
main "$@"
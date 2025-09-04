#!/bin/bash

# Enhanced Queue Error Monitor with Modular Implementation Focus
# Goal: Continuously iterate over and refine modules until they work independently from legacy code
# Runs every 30 minutes to progressively implement legacy functionality in modules

set -e

# Configuration
TMUX_ORCHESTRATOR_HOME="${TMUX_ORCHESTRATOR_HOME:-/home/clauderun/Tmux-Orchestrator}"
SESSION_NAME="queue-error-monitoring-service"
LOG_FILE="$TMUX_ORCHESTRATOR_HOME/logs/modular_implementation.log"
PID_FILE="/tmp/queue_monitor_modular.pid"
LOCK_FILE="/tmp/queue_monitor_modular.lock"

# Ensure log directory exists
mkdir -p "$TMUX_ORCHESTRATOR_HOME/logs"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$$] $1" | tee -a "$LOG_FILE"
}

# Lock management
acquire_lock() {
    if [ -f "$LOCK_FILE" ]; then
        local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
            log "Another instance is already running (PID: $lock_pid)"
            exit 1
        else
            log "Removing stale lock file"
            rm -f "$LOCK_FILE"
        fi
    fi
    echo "$$" > "$LOCK_FILE"
    log "Lock acquired (PID: $$)"
}

release_lock() {
    if [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
        log "Lock released"
    fi
}

# Cleanup on exit
cleanup() {
    release_lock
}
trap cleanup EXIT

# Function to ensure Claude is running in the session
ensure_claude_running() {
    local session="$1"
    
    if ! tmux has-session -t "$session" 2>/dev/null; then
        log "Creating new tmux session: $session"
        tmux new-session -d -s "$session" -c "$TMUX_ORCHESTRATOR_HOME"
        sleep 2
    fi
    
    # Check if Claude is already running and active
    local pane_content=$(tmux capture-pane -t "$session" -p | tail -10)
    if echo "$pane_content" | grep -q "claude>" || echo "$pane_content" | grep -q "Human:" || echo "$pane_content" | grep -q "⏵⏵ bypass permissions"; then
        log "Claude is already running and ready in session"
        return 0
    fi
    
    # Check if there's a prompt waiting 
    if echo "$pane_content" | grep -q "claude$" || echo "$pane_content" | grep -q "clauderun@"; then
        log "Starting Claude with dangerously-skip-permissions flag"
        tmux send-keys -t "$session" "claude --dangerously-skip-permissions" Enter
        sleep 5
        
        # Verify Claude started
        pane_content=$(tmux capture-pane -t "$session" -p | tail -5)
        if echo "$pane_content" | grep -q "claude>" || echo "$pane_content" | grep -q "Human:" || echo "$pane_content" | grep -q "⏵⏵ bypass permissions"; then
            log "Claude started successfully"
            return 0
        else
            log "ERROR: Failed to start Claude after attempt"
            return 1
        fi
    fi
    
    # If we can't determine the state, assume it's ready
    log "Claude session state unclear but proceeding"
    return 0
}

# Function to brief Claude about modular implementation task
brief_claude_modular_implementation() {
    local session="$1"
    local iteration="$2"
    
    log "Briefing Claude about modular implementation iteration $iteration"
    
    # Send comprehensive briefing about the modular implementation goals
    tmux send-keys -t "$session" "I am Claude Code, and this is iteration $iteration of the modular implementation process. My goal is to implement functionality directly in the tmux_orchestrator and scheduler_modules packages instead of delegating to legacy auto_orchestrate.py.

Current Status Analysis:
- tmux_orchestrator package EXISTS but delegates to legacy via start_orchestration() method
- scheduler_modules package EXISTS and is partially implemented
- Both packages need INDEPENDENT functionality implementation

Key Implementation Areas for This Iteration:
1. TMUX_ORCHESTRATOR CRITICAL GAPS:
   - core/orchestrator.py currently delegates to auto_orchestrate.py (lines 202-284)
   - Need to implement: project setup, agent deployment, worktree creation
   - Missing: claude/initialization.py OAuth timing implementation
   - Missing: agents/agent_factory.py team creation logic
   - Missing: git/worktree_manager.py sibling directory setup

2. SCHEDULER_MODULES CRITICAL GAPS:  
   - Core scheduler delegates properly but modules may be incomplete
   - Need to verify all 13 modules have full functionality
   - Check if CLI parsing matches original scheduler.py capabilities

IMMEDIATE TASKS for this iteration:
1. Read /home/clauderun/Tmux-Orchestrator/docs/specs/auto-orchestrate-modularization.md 
2. Identify ONE critical function currently delegated to legacy
3. Extract that function from auto_orchestrate.py and implement it in appropriate module
4. Update the orchestrator to call the new modular implementation instead of legacy
5. Test the implementation works correctly

Focus on OAuth/MCP initialization as HIGHEST PRIORITY - this is critical for batch processing.

After completing one function implementation, create a progress report in /home/clauderun/Tmux-Orchestrator/logs/modular_progress_iteration_$iteration.md documenting:
- What was implemented
- What was extracted from legacy
- Current delegation status
- Next priority functions

Begin implementation immediately. Do NOT ask for permissions." Enter
    
    sleep 2
}

# Function to analyze current modular implementation status
analyze_modular_status() {
    log "Analyzing current modular implementation status"
    
    cd "$TMUX_ORCHESTRATOR_HOME"
    
    cat > analyze_current_status.py << 'EOF'
import os
import ast
import re
from pathlib import Path

def analyze_delegation_patterns():
    """Find all places where modular code delegates to legacy"""
    tmux_orchestrator_dir = Path("tmux_orchestrator")
    scheduler_modules_dir = Path("scheduler_modules") 
    
    delegation_patterns = []
    
    # Check tmux_orchestrator for delegation
    if tmux_orchestrator_dir.exists():
        for py_file in tmux_orchestrator_dir.rglob("*.py"):
            try:
                content = py_file.read_text()
                if "auto_orchestrate" in content or "subprocess" in content:
                    delegation_patterns.append({
                        "file": str(py_file),
                        "type": "tmux_orchestrator",
                        "delegates_to_legacy": True,
                        "contains_subprocess": "subprocess" in content
                    })
            except Exception as e:
                print(f"Error reading {py_file}: {e}")
    
    # Check scheduler_modules for completeness
    expected_modules = [
        "core_scheduler.py", "queue_manager.py", "session_monitor.py",
        "process_manager_wrapper.py", "state_synchronizer_wrapper.py",
        "event_dispatcher.py", "batch_processor.py", "recovery_manager.py",
        "notification_manager.py", "dependency_checker.py", "cli_handler.py",
        "config.py", "utils.py"
    ]
    
    missing_modules = []
    if scheduler_modules_dir.exists():
        existing_modules = [f.name for f in scheduler_modules_dir.glob("*.py") if f.name != "__init__.py"]
        missing_modules = [m for m in expected_modules if m not in existing_modules]
    
    return {
        "delegation_patterns": delegation_patterns,
        "missing_scheduler_modules": missing_modules,
        "tmux_orchestrator_exists": tmux_orchestrator_dir.exists(),
        "scheduler_modules_exists": scheduler_modules_dir.exists()
    }

def main():
    status = analyze_delegation_patterns()
    import json
    print(json.dumps(status, indent=2))

if __name__ == "__main__":
    main()
EOF

    python3 analyze_current_status.py > "$LOG_FILE.analysis.json" 2>&1
    
    # Log the analysis results
    if [ -f "$LOG_FILE.analysis.json" ]; then
        log "Modular status analysis completed:"
        cat "$LOG_FILE.analysis.json" | tee -a "$LOG_FILE"
    else
        log "ERROR: Failed to generate modular status analysis"
    fi
}

# Function to check for progress reports
check_implementation_progress() {
    local iteration="$1"
    local progress_file="$TMUX_ORCHESTRATOR_HOME/logs/modular_progress_iteration_$iteration.md"
    
    log "Checking for progress report: $progress_file"
    
    if [ -f "$progress_file" ]; then
        log "Progress report found for iteration $iteration:"
        cat "$progress_file" | tee -a "$LOG_FILE"
        return 0
    else
        log "No progress report found for iteration $iteration"
        return 1
    fi
}

# Function to detect modularization-specific issues
detect_modular_implementation_issues() {
    log "Detecting modular implementation issues"
    
    local issues_found=false
    
    # Check if orchestrator still delegates to legacy
    if grep -q "auto_orchestrate.py" "$TMUX_ORCHESTRATOR_HOME/tmux_orchestrator/core/orchestrator.py" 2>/dev/null; then
        log "ISSUE: tmux_orchestrator still delegates to legacy auto_orchestrate.py"
        issues_found=true
    fi
    
    # Check if scheduler has shim patterns still active
    if [ -f "$TMUX_ORCHESTRATOR_HOME/scheduler.py" ]; then
        if grep -q "from scheduler_modules" "$TMUX_ORCHESTRATOR_HOME/scheduler.py" 2>/dev/null; then
            log "INFO: scheduler.py properly imports from modules"
        else
            log "ISSUE: scheduler.py may not be using modular imports"
            issues_found=true
        fi
    fi
    
    # Check queue processing
    cd "$TMUX_ORCHESTRATOR_HOME"
    if [ -f "task_queue.db" ]; then
        local failed_count=$(sqlite3 task_queue.db "SELECT COUNT(*) FROM project_queue WHERE status='FAILED';" 2>/dev/null || echo "0")
        local processing_count=$(sqlite3 task_queue.db "SELECT COUNT(*) FROM project_queue WHERE status='PROCESSING';" 2>/dev/null || echo "0")
        
        if [ "$failed_count" -gt 0 ]; then
            log "ISSUE: Found $failed_count failed projects in queue"
            issues_found=true
        fi
        
        if [ "$processing_count" -gt 5 ]; then
            log "WARNING: Found $processing_count processing projects (may indicate stuck projects)"
        fi
    fi
    
    if [ "$issues_found" = true ]; then
        return 1
    else
        log "No critical modular implementation issues detected"
        return 0
    fi
}

# Main monitoring cycle function
run_modular_implementation_cycle() {
    local iteration_number=$(date +%Y%m%d_%H%M)
    
    log "Starting modular implementation cycle iteration: $iteration_number"
    log "PID: $$"
    log "TMUX_ORCHESTRATOR_HOME: $TMUX_ORCHESTRATOR_HOME"
    log "Session: $SESSION_NAME"
    log "Focus: Progressive modular implementation to replace legacy delegation"
    
    # Ensure Claude is running in monitoring session
    if ! ensure_claude_running "$SESSION_NAME"; then
        log "ERROR: Failed to start Claude, aborting cycle"
        return 1
    fi
    
    # Analyze current modular status
    analyze_modular_status
    
    # Brief Claude about the specific implementation tasks for this iteration
    brief_claude_modular_implementation "$SESSION_NAME" "$iteration_number"
    
    # Wait for Claude to work (give more time for implementation)
    log "Allowing 25 minutes for modular implementation work..."
    sleep 1500  # 25 minutes for implementation work
    
    # Check if progress was made
    if check_implementation_progress "$iteration_number"; then
        log "Progress detected for iteration $iteration_number"
    else
        log "No progress report found - will retry in next iteration"
    fi
    
    # Detect any issues that need attention
    if ! detect_modular_implementation_issues; then
        log "Issues detected that need resolution"
    fi
    
    log "Modular implementation cycle completed for iteration: $iteration_number"
    return 0
}

# Main execution
main() {
    acquire_lock
    
    log "=== Enhanced Queue Error Monitor Started with Modular Implementation Focus ==="
    log "PID: $$"
    log "TMUX_ORCHESTRATOR_HOME: $TMUX_ORCHESTRATOR_HOME"
    log "Session: $SESSION_NAME"
    log "Focus: Progressive modular implementation to eliminate legacy dependencies"
    
    if ! run_modular_implementation_cycle; then
        log "ERROR: Modular implementation cycle failed"
        exit 1
    fi
    
    log "=== Enhanced Queue Error Monitor Completed ==="
}

# Execute main function
main
#!/bin/bash

# Enhanced Self-Healing Modular Implementation Monitor
# Progressive implementation of modular functionality to replace legacy delegation
# Based on comprehensive analysis and expert recommendations

set -e

# Configuration
TMUX_ORCHESTRATOR_HOME="${TMUX_ORCHESTRATOR_HOME:-/home/clauderun/Tmux-Orchestrator}"
SESSION_NAME="modular-self-healing-monitor"
LOG_FILE="$TMUX_ORCHESTRATOR_HOME/logs/self_healing_modular.log"
PID_FILE="/tmp/self_healing_modular.pid"
LOCK_FILE="/tmp/self_healing_modular.lock"

# Claude configuration - ALWAYS use skip permissions
Claude_SKIP_PERMISSIONS="true"

# Configuration files
CONFIG_FILE="$TMUX_ORCHESTRATOR_HOME/.modular_monitor_config"
STATE_FILE="$TMUX_ORCHESTRATOR_HOME/.modular_implementation_state.json"
STATE_DIR="$TMUX_ORCHESTRATOR_HOME/.modular_monitor_state"

# Priority order for implementation (OAuth > Core > Utilities)
PRIORITY_ORDER=("oauth" "core" "git" "tmux" "queue" "monitoring" "utils")

# Circuit breaker settings
IMPLEMENTATION_FAILURE_THRESHOLD=5
implementation_failures=0

# Ensure log and config directories exist
mkdir -p "$TMUX_ORCHESTRATOR_HOME/logs"
mkdir -p "$STATE_DIR"

# Enhanced logging with structured data
log() {
    local level="${2:-INFO}"
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local pid=$$
    
    echo "[$timestamp] [$level] [PID:$pid] $message" | tee -a "$LOG_FILE"
    
    # Also log structured data for analysis
    echo "{\"timestamp\":\"$timestamp\",\"level\":\"$level\",\"pid\":$pid,\"message\":\"$message\"}" >> "${LOG_FILE}.jsonl"
}

# Lock management with better error handling
acquire_lock() {
    local max_wait=300  # 5 minutes
    local wait_time=0
    
    while [ $wait_time -lt $max_wait ]; do
        if [ -f "$LOCK_FILE" ]; then
            local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
            if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
                log "Another instance is running (PID: $lock_pid), waiting..."
                sleep 30
                wait_time=$((wait_time + 30))
                continue
            else
                log "Removing stale lock file"
                rm -f "$LOCK_FILE"
            fi
        fi
        
        echo "$$" > "$LOCK_FILE"
        log "Lock acquired (PID: $$)"
        return 0
    done
    
    log "ERROR: Could not acquire lock after $max_wait seconds"
    exit 1
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
    # Clean up temporary files
    rm -f "$TMUX_ORCHESTRATOR_HOME/analyze_modular_status.py" 2>/dev/null || true
    rm -f "$TMUX_ORCHESTRATOR_HOME"/*.tmp 2>/dev/null || true
}
trap cleanup EXIT

# Configuration management
create_default_config() {
    cat > "$CONFIG_FILE" << EOF
# Modular Implementation Monitor Configuration
MONITOR_INTERVAL_MINUTES=30
MAX_IMPLEMENTATION_TIME_MINUTES=25
PYTHON_ANALYSIS_TIMEOUT_SECONDS=300
CIRCUIT_BREAKER_THRESHOLD=5
LOG_RETENTION_DAYS=7
MAX_LOG_SIZE_MB=100
CLAUDE_CONTEXT_REFRESH_HOURS=6
ENABLE_QUEUE_HEALING=true
ENABLE_AUTO_IMPLEMENTATION=true
NOTIFICATION_EMAIL=""
SLACK_WEBHOOK_URL=""
Claude_SKIP_PERMISSIONS=true
EOF
}

load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    else
        create_default_config
        source "$CONFIG_FILE"
    fi
    
    log "Configuration loaded - Implementation enabled: $ENABLE_AUTO_IMPLEMENTATION"
}

# Initialize implementation state tracking
init_implementation_state() {
    if [ ! -f "$STATE_FILE" ]; then
        cat > "$STATE_FILE" << EOF
{
  "last_iteration": "$(date +%s)",
  "implemented_functions": [],
  "failed_attempts": [],
  "current_priority": "oauth",
  "delegation_points": [],
  "success_rate": 0.0,
  "total_attempts": 0,
  "successful_attempts": 0,
  "circuit_breaker_active": false
}
EOF
        log "Initialized implementation state tracking"
    fi
}

# Update implementation state
update_implementation_state() {
    local key="$1"
    local value="$2"
    
    # Use Python for JSON manipulation
    python3 -c "
import json
import sys
try:
    with open('$STATE_FILE', 'r') as f:
        state = json.load(f)
    
    # Update the specified key
    if '$key' == 'add_implemented_function':
        if '$value' not in state.get('implemented_functions', []):
            state.setdefault('implemented_functions', []).append('$value')
    elif '$key' == 'add_failed_attempt':
        state.setdefault('failed_attempts', []).append({
            'function': '$value',
            'timestamp': '$(date -Iseconds)',
            'iteration': state.get('last_iteration', 0)
        })
    else:
        state['$key'] = $value
    
    # Update metrics
    total = len(state.get('failed_attempts', [])) + len(state.get('implemented_functions', []))
    successful = len(state.get('implemented_functions', []))
    if total > 0:
        state['success_rate'] = successful / total
    
    with open('$STATE_FILE', 'w') as f:
        json.dump(state, f, indent=2)
        
except Exception as e:
    print(f'Error updating state: {e}', file=sys.stderr)
    sys.exit(1)
"
}

# Function to check if Claude needs context refresh (every 6 hours by default)
check_claude_context_refresh() {
    local session="$1"
    local CONTEXT_REFRESH_FILE="$STATE_DIR/claude_last_refresh.txt"
    local REFRESH_INTERVAL_HOURS=${CLAUDE_CONTEXT_REFRESH_HOURS:-3}  # Default to 3 hours for better stability
    local REFRESH_INTERVAL_SECONDS=$((REFRESH_INTERVAL_HOURS * 3600))
    
    # Check if refresh file exists
    if [ -f "$CONTEXT_REFRESH_FILE" ]; then
        local last_refresh=$(cat "$CONTEXT_REFRESH_FILE")
        local current_time=$(date +%s)
        local time_diff=$((current_time - last_refresh))
        
        if [ $time_diff -gt $REFRESH_INTERVAL_SECONDS ]; then
            log "Claude context refresh needed (last refresh: $((time_diff / 3600)) hours ago)"
            return 0  # Needs refresh
        else
            local hours_until_refresh=$(( (REFRESH_INTERVAL_SECONDS - time_diff) / 3600 ))
            local minutes_until_refresh=$(( ((REFRESH_INTERVAL_SECONDS - time_diff) % 3600) / 60 ))
            log "Claude context OK (next refresh in ${hours_until_refresh}h ${minutes_until_refresh}m)"
            return 1  # No refresh needed
        fi
    else
        # First run, create the file
        echo $(date +%s) > "$CONTEXT_REFRESH_FILE"
        log "Claude context refresh tracking initialized"
        return 1  # No refresh needed on first run
    fi
}

# Function to restart Claude with fresh context
restart_claude_with_fresh_context() {
    local session="$1"
    
    log "🔄 Restarting Claude with fresh context by recreating window"
    
    # First create a temporary window to keep session alive
    log "Creating temporary window to maintain session..."
    tmux new-window -t "$session" -n "temp" -c "$TMUX_ORCHESTRATOR_HOME"
    sleep 1
    
    # Now kill the Claude window (window 0)
    log "Killing existing Claude window..."
    tmux kill-window -t "$session:0" 2>/dev/null || true
    sleep 1
    
    # Create a new window at index 0 for Claude
    log "Creating fresh window for Claude..."
    tmux new-window -t "$session:0" -n "Claude-Monitor" -c "$TMUX_ORCHESTRATOR_HOME"
    sleep 1
    
    # Kill the temporary window
    tmux kill-window -t "$session:temp" 2>/dev/null || true
    
    # Start Claude with dangerous skip permissions flag
    log "Starting fresh Claude instance with --dangerously-skip-permissions"
    tmux send-keys -t "$session:0" "claude --dangerously-skip-permissions" Enter
    sleep 8
    
    # Verify Claude started
    local pane_content=$(tmux capture-pane -t "$session:0" -p | tail -10)
    if echo "$pane_content" | grep -q "claude>" || echo "$pane_content" | grep -q "Human:" || echo "$pane_content" | grep -q "⏵⏵ bypass permissions"; then
        log "✅ Claude restarted successfully with fresh context"
        
        # Update refresh timestamp
        echo $(date +%s) > "$STATE_DIR/claude_last_refresh.txt"
        
        # Re-brief Claude with its monitoring responsibilities
        brief_claude_after_refresh "$session"
        return 0
    else
        log "❌ Failed to restart Claude with fresh context"
        return 1
    fi
}

# Function to re-brief Claude after context refresh
brief_claude_after_refresh() {
    local session="$1"
    
    log "📋 Re-briefing Claude after context refresh"
    
    # Get current status for briefing
    local total_delegations=$(python3 -c "
import json
try:
    with open('$LOG_FILE.analysis.json') as f:
        data = json.load(f)
    print(data.get('total_delegations', 0))
except:
    print('0')
" 2>/dev/null || echo "0")
    
    local queue_health=$(python3 -c "
import json
try:
    with open('$LOG_FILE.analysis.json') as f:
        data = json.load(f)
    print(data.get('queue_health', {}).get('health_score', 100))
except:
    print('100')
" 2>/dev/null || echo "100")
    
    local briefing="You are the Self-Healing Modular Implementation Monitor for the Tmux Orchestrator system.

Your PRIMARY responsibilities:
1. Monitor and eliminate all legacy delegation points to auto_orchestrate.py
2. Implement modular replacements for any remaining delegations
3. Monitor active project health and detect completion mismatches
4. Recover failed projects automatically
5. Use /dwg command to consult Grok for complex problems

CONTEXT REFRESH NOTE: Your context was just refreshed to prevent overflow. This happens every ${CLAUDE_CONTEXT_REFRESH_HOURS:-6} hours automatically.

Current System Status:
- Remaining delegations: $total_delegations
- Queue health score: $queue_health/100
- Session: $session
- Monitoring directory: $TMUX_ORCHESTRATOR_HOME
- State file: $STATE_FILE
- Log file: $LOG_FILE

Key Commands:
- Use /dwg to discuss problems with Grok
- Include full file contents and logs when consulting Grok
- Always use send-direct-message.sh for messaging other agents

When you receive implementation tasks:
1. Read and understand the target delegation point
2. Implement the modular replacement
3. Test the implementation
4. Report completion status

Ready to continue monitoring and self-healing the system."

    send_message_to_agent "$session:0" "$briefing" "context_refresh_briefing"
    log "✅ Claude re-briefed after context refresh"
}

# Function to ensure Claude is running with proper permissions
ensure_claude_running() {
    local session="$1"
    
    if ! tmux has-session -t "$session" 2>/dev/null; then
        log "Creating new tmux session: $session"
        tmux new-session -d -s "$session" -c "$TMUX_ORCHESTRATOR_HOME"
        sleep 2
    fi
    
    # Check if Claude needs context refresh (every 6 hours)
    if check_claude_context_refresh "$session"; then
        restart_claude_with_fresh_context "$session"
        return $?
    fi
    
    # Check if Claude is already running and active
    local pane_content=$(tmux capture-pane -t "$session" -p | tail -10)
    if echo "$pane_content" | grep -q "claude>" || echo "$pane_content" | grep -q "Human:" || echo "$pane_content" | grep -q "⏵⏵ bypass permissions"; then
        log "Claude is already running and ready in session"
        return 0
    fi
    
    # Check if there's a prompt waiting 
    if echo "$pane_content" | grep -q "claude$" || echo "$pane_content" | grep -q "clauderun@"; then
        local claude_cmd="claude"
        if [ "$Claude_SKIP_PERMISSIONS" = "true" ]; then
            claude_cmd="claude --dangerously-skip-permissions"
        fi
        
        log "Starting Claude with permissions: $claude_cmd"
        tmux send-keys -t "$session:0" "$claude_cmd" Enter
        sleep 8  # Give more time for Claude to start
        
        # Verify Claude started with multiple attempts
        local attempts=0
        while [ $attempts -lt 5 ]; do
            pane_content=$(tmux capture-pane -t "$session:0" -p | tail -5)
            if echo "$pane_content" | grep -q "claude>" || echo "$pane_content" | grep -q "Human:" || echo "$pane_content" | grep -q "⏵⏵ bypass permissions"; then
                log "Claude started successfully after $attempts attempts"
                return 0
            fi
            
            attempts=$((attempts + 1))
            log "Waiting for Claude to start (attempt $attempts/5)..."
            sleep 3
        done
        
        log "ERROR: Failed to start Claude after 5 attempts"
        return 1
    fi
    
    # If we can't determine the state, try to start Claude anyway
    log "Claude session state unclear, attempting to start Claude"
    local claude_cmd="claude"
    if [ "$Claude_SKIP_PERMISSIONS" = "true" ]; then
        claude_cmd="claude --dangerously-skip-permissions"
    fi
    
    tmux send-keys -t "$session:0" "$claude_cmd" Enter
    sleep 8
    
    # Final verification
    pane_content=$(tmux capture-pane -t "$session:0" -p | tail -5)
    if echo "$pane_content" | grep -q "claude>" || echo "$pane_content" | grep -q "Human:" || echo "$pane_content" | grep -q "⏵⏵ bypass permissions"; then
        log "Claude started successfully"
        return 0
    else
        log "ERROR: Claude failed to start"
        return 1
    fi
}

# Get active and failed projects from queue status
get_active_projects() {
    python3 -c "
import subprocess
import json
import sys
import re

try:
    # Get queue status output
    result = subprocess.run(['python3', 'queue_status.py'], 
                          capture_output=True, text=True, cwd='$TMUX_ORCHESTRATOR_HOME')
    if result.returncode == 0:
        output = result.stdout
        active_projects = []
        
        # Parse the output for PROCESSING and FAILED projects
        lines = output.split('\n')
        current_project = None
        
        for line in lines:
            # Look for project headers like '🔄 [77] Unknown-Spec' or '❌ [71] Project Name'
            project_match = re.search(r'(🔄|❌) \[(\d+)\] (.+)', line)
            if project_match:
                # Save previous project if it exists
                if current_project:
                    active_projects.append(current_project)
                
                status_icon = project_match.group(1)
                current_project = {
                    'id': project_match.group(2),
                    'name': project_match.group(3),
                    'status': 'PROCESSING' if status_icon == '🔄' else 'FAILED',
                    'session': None,
                    'spec': None,
                    'error': None,
                    'started': 'Unknown'
                }
                continue
            
            # Look for session info
            if current_project and 'Session:' in line:
                session_match = re.search(r'Session: ([^\s]+)', line)
                if session_match:
                    current_project['session'] = session_match.group(1)
            
            # Look for error info
            if current_project and 'Error:' in line:
                error_match = re.search(r'Error: (.+)', line)
                if error_match:
                    current_project['error'] = error_match.group(1)
            
            # Look for spec path
            if current_project and 'Spec:' in line:
                spec_match = re.search(r'Spec: (.+)', line)
                if spec_match:
                    current_project['spec'] = spec_match.group(1)
        
        # Don't forget the last project
        if current_project:
            active_projects.append(current_project)
        
        print(json.dumps(active_projects, indent=2))
    else:
        print('[]')
except Exception as e:
    print(f'[]  # Error: {e}', file=sys.stderr)
"
}

# Monitor active project progress and health
monitor_active_projects() {
    log "Checking active project health and progress"
    
    local active_projects=$(get_active_projects)
    local project_count=$(echo "$active_projects" | python3 -c "import json, sys; data=json.load(sys.stdin); print(len(data))")
    
    if [ "$project_count" -eq 0 ]; then
        log "No active projects to monitor"
        return 0
    fi
    
    log "Found $project_count active projects to monitor"
    
    echo "$active_projects" | python3 -c "
import json
import sys
import subprocess
import os
import time

projects = json.load(sys.stdin)
for project in projects:
    session = project.get('session')
    project_id = project['id']
    project_name = project['name']
    status = project.get('status', 'UNKNOWN')
    error = project.get('error', '')
    spec = project.get('spec', '')
    
    print(f'Monitoring project {project_id}: {project_name} (status: {status}, session: {session})')
    
    # Handle FAILED projects
    if status == 'FAILED':
        print(f'FAILED PROJECT DETECTED: {project_id} - {project_name}')
        print(f'  Error: {error}')
        
        # Create failure recovery file
        with open(f'/tmp/failed_project_{project_id}.txt', 'w') as f:
            f.write(f'Project: {project_name}\\n')
            f.write(f'ID: {project_id}\\n')
            f.write(f'Status: FAILED\\n')
            f.write(f'Error: {error}\\n')
            f.write(f'Spec: {spec}\\n')
            
            # Determine recovery strategy based on error
            if 'Subprocess failed: None' in error:
                f.write(f'Recovery: Reset and retry with fresh start\\n')
                f.write(f'Issue: Subprocess launch failed - likely args issue\\n')
            elif 'Graceful cleanup of completed' in error:
                f.write(f'Recovery: Mark as completed - project actually finished\\n')
                f.write(f'Issue: Incorrectly marked as failed when actually completed\\n')
            else:
                f.write(f'Recovery: Investigate error and reset\\n')
                f.write(f'Issue: Unknown failure type\\n')
        continue
    
    # Handle projects without active sessions
    if not session:
        print(f'WARNING: Project {project_id} is PROCESSING but has no active session - likely completed but not marked')
        with open(f'/tmp/completion_issue_{project_id}.txt', 'w') as f:
            f.write(f'Project: {project_name}\\n')
            f.write(f'Issue: PROCESSING status but no active session\\n')
            f.write(f'Recommendation: Verify completion and update status\\n')
        continue
    
    # Check if tmux session exists
    result = subprocess.run(['tmux', 'has-session', '-t', session], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print(f'ERROR: Session {session} not found for project {project_id}')
        with open(f'/tmp/completion_issue_{project_id}.txt', 'w') as f:
            f.write(f'Project: {project_name}\\n')
            f.write(f'Session: {session}\\n') 
            f.write(f'Issue: PROCESSING status but session not found\\n')
            f.write(f'Recommendation: Check if project completed and update status\\n')
        continue
    
    # Get window list for this session
    result = subprocess.run(['tmux', 'list-windows', '-t', session, '-F', '#{window_index}:#{window_name}'], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        windows = result.stdout.strip().split('\n')
        print(f'Session {session} has {len(windows)} windows: {windows}')
        
        # Check each window for agent health
        for window_info in windows:
            if ':' in window_info:
                window_idx, window_name = window_info.split(':', 1)
                target = f'{session}:{window_idx}'
                
                # Capture recent activity with more history
                capture_result = subprocess.run(['tmux', 'capture-pane', '-t', target, '-S', '-200', '-p'], 
                                              capture_output=True, text=True)
                if capture_result.returncode == 0:
                    content = capture_result.stdout
                    
                    # Check for completion markers (expanded patterns)
                    completion_patterns = [
                        'PROJECT COMPLETED',
                        'FINAL_COMPLETION_CONFIRMATION',
                        'integration is complete',
                        'Integration is complete', 
                        'MVP Integration is complete',
                        'work is actually complete',
                        'ready for production',
                        'VERIFICATION COMPLETE',
                        'successfully completed',
                        'All technical deliverables',
                        'completion verification'
                    ]
                    
                    completion_found = False
                    for pattern in completion_patterns:
                        if pattern in content:
                            print(f'FOUND COMPLETION: {window_name} in {session} shows \"{pattern}\"')
                            completion_found = True
                            break
                    
                    if completion_found:
                        
                        # Verify if project is actually marked complete in database
                        queue_check = subprocess.run(['python3', 'queue_status.py', '--project-id', str(project_id)], 
                                                   cwd=os.environ.get('TMUX_ORCHESTRATOR_HOME', '.'),
                                                   capture_output=True, text=True)
                        if queue_check.returncode == 0 and 'COMPLETED' not in queue_check.stdout:
                            print(f'ISSUE: Project {project_id} shows completion but not marked complete in queue')
                            # Report this to monitoring
                            with open(f'/tmp/completion_issue_{project_id}.txt', 'w') as f:
                                f.write(f'Project: {project_name}\\n')
                                f.write(f'Session: {session}\\n') 
                                f.write(f'Window: {window_name}\\n')
                                f.write(f'Issue: Shows completion but not marked complete\\n')
                                f.write(f'Content sample: {content[-500:]}\\n')
                    
                    # Check for error patterns
                    if 'Error:' in content or 'Exception:' in content or 'Traceback:' in content:
                        print(f'FOUND ERRORS: {window_name} in {session} has errors')
                        with open(f'/tmp/agent_errors_{session}_{window_idx}.txt', 'w') as f:
                            f.write(f'Session: {session}\\n')
                            f.write(f'Window: {window_name}\\n')
                            f.write(f'Recent content:\\n{content[-1000:]}\\n')
                    
                    # Check if agent is stuck/inactive
                    if 'claude>' in content[-100:] and content.count('\\n') > 50:
                        # Agent might be waiting - check timestamp
                        print(f'AGENT STATUS: {window_name} appears to be waiting for input')
    else:
        print(f'ERROR: Could not list windows for session {session}')
"
}

# Monitor message delivery and fix stuck messages
monitor_message_delivery() {
    log "Checking for stuck messages requiring Enter key press"
    
    # Find all tmux sessions
    local sessions
    sessions=$(tmux list-sessions -F '#{session_name}' 2>/dev/null) || return 0
    
    local stuck_messages_found=0
    local messages_fixed=0
    
    for session in $sessions; do
        # Skip if session is empty
        [ -z "$session" ] && continue
        
        # Get all windows in session
        local windows
        windows=$(tmux list-windows -t "$session" -F '#{window_index}' 2>/dev/null) || continue
        
        for window in $windows; do
            [ -z "$window" ] && continue
            
            local target="$session:$window"
            
            # Capture recent pane content (last 20 lines to check for stuck patterns)
            local content
            content=$(tmux capture-pane -p -t "$target" -S -20 2>/dev/null) || continue
            
            # Check for MCP wrapper patterns that indicate stuck messages
            if echo "$content" | grep -q "TMUX_MCP_START\|TMUX_MCP_DONE"; then
                stuck_messages_found=$((stuck_messages_found + 1))
                log "🔧 Found stuck MCP message in $target, attempting to fix"
                
                # Get the specific stuck message for logging
                local stuck_pattern
                stuck_pattern=$(echo "$content" | grep -E "TMUX_MCP_START|TMUX_MCP_DONE" | tail -1)
                
                # Send Enter to execute the stuck message
                if tmux send-keys -t "$target" Enter 2>/dev/null; then
                    sleep 1  # Give time for processing
                    
                    # Verify the fix by checking if MCP patterns are gone
                    local new_content
                    new_content=$(tmux capture-pane -p -t "$target" -S -10 2>/dev/null)
                    
                    if ! echo "$new_content" | grep -q "TMUX_MCP_START\|TMUX_MCP_DONE"; then
                        messages_fixed=$((messages_fixed + 1))
                        log "✅ Successfully cleared stuck message in $target"
                        
                        # Log the successful fix for monitoring
                        echo "$(date -Iseconds) FIXED_STUCK_MESSAGE $target: $stuck_pattern" >> "$TMUX_ORCHESTRATOR_HOME/logs/message_fixes.log"
                    else
                        log "⚠️  First attempt failed for $target, trying escalated fix"
                        
                        # Escalation: Try alternative fixes
                        tmux send-keys -t "$target" C-c 2>/dev/null  # Interrupt any stuck process
                        sleep 0.5
                        tmux send-keys -t "$target" Enter 2>/dev/null  # Try Enter again
                        sleep 0.5
                        
                        # Final verification
                        local final_content
                        final_content=$(tmux capture-pane -p -t "$target" -S -5 2>/dev/null)
                        if ! echo "$final_content" | grep -q "TMUX_MCP_START\|TMUX_MCP_DONE"; then
                            messages_fixed=$((messages_fixed + 1))
                            log "✅ Successfully cleared stuck message in $target (escalated fix)"
                        else
                            log "❌ Failed to clear stuck message in $target after escalation"
                            
                            # Log persistent stuck messages for manual review
                            echo "$(date -Iseconds) PERSISTENT_STUCK_MESSAGE $target: $stuck_pattern" >> "$TMUX_ORCHESTRATOR_HOME/logs/persistent_stuck_messages.log"
                        fi
                    fi
                else
                    log "❌ Failed to send Enter to $target (tmux error)"
                fi
            fi
            
            # Also check for other signs of unresponsive agents (no activity in last few lines)
            # This helps catch agents that might be waiting for input without MCP patterns
            local last_lines
            last_lines=$(echo "$content" | tail -5)
            if echo "$last_lines" | grep -q "echo.*TMUX_MCP.*echo" && ! echo "$last_lines" | grep -E "(claude>|Assistant:|Human:|●|\$|#)"; then
                # Found what looks like an unexecuted command line
                log "🔄 Found potential unexecuted command in $target, sending Enter"
                tmux send-keys -t "$target" Enter 2>/dev/null
                sleep 0.5
            fi
        done
    done
    
    # Summary logging
    if [ $stuck_messages_found -gt 0 ]; then
        log "Message delivery check completed: Found $stuck_messages_found stuck messages, fixed $messages_fixed"
        
        # Update implementation state with message health metrics
        update_implementation_state "last_message_check" "$(date +%s)"
        update_implementation_state "stuck_messages_found" "$stuck_messages_found"
        update_implementation_state "messages_fixed" "$messages_fixed"
        
        # If we consistently find stuck messages, that indicates a systemic issue
        if [ $stuck_messages_found -gt 5 ] && [ $messages_fixed -lt $((stuck_messages_found / 2)) ]; then
            log "⚠️  HIGH STUCK MESSAGE RATE: Consider reviewing message sending scripts"
        fi
    else
        log "✅ Message delivery health check passed - no stuck messages found"
    fi
}

# Send message using proper send-direct-message.sh with Enter key
send_message_to_agent() {
    local target="$1"
    local message="$2"
    local issue_type="$3"
    
    log "Sending message to $target: $message"
    
    # Use send-direct-message.sh which properly sends Enter key
    if [ -f "$TMUX_ORCHESTRATOR_HOME/send-direct-message.sh" ]; then
        "$TMUX_ORCHESTRATOR_HOME/send-direct-message.sh" "$target" "$message"
        log "Message sent via send-direct-message.sh to $target"
    else
        # Fallback to tmux with explicit Enter
        tmux send-keys -t "$target" "$message" Enter
        log "Message sent via tmux send-keys to $target"
    fi
}

# Consult Grok about problems before fixing
consult_grok_about_issue() {
    local issue_type="$1"
    local issue_details="$2"
    local relevant_files="$3"
    
    log "Consulting Grok about issue: $issue_type"
    
    # Use the existing monitoring session instead of creating new one
    local monitoring_session="$SESSION_NAME"
    
    # Send Grok discussion request directly to the monitoring session
    local grok_query="/dwg discuss with grok about this issue:

ISSUE TYPE: $issue_type
DETAILS: $issue_details

RELEVANT FILES TO INCLUDE:
$relevant_files

Please analyze this problem and provide recommendations for fixing it. Include all relevant context files and logs in your discussion with Grok.

After getting Grok's recommendation, provide me with a specific action plan to resolve this issue."

    # Use the proper messaging function to send to monitoring session
    send_message_to_agent "$monitoring_session:0" "$grok_query" "grok_consultation"
    
    log "Grok consultation sent to monitoring session: $monitoring_session"
    log "Waiting 60 seconds for Grok response..."
    sleep 60
    
    # Capture Grok's response from the monitoring session
    local grok_response=$(tmux capture-pane -t "$monitoring_session:0" -S -100 -p)
    echo "$grok_response" > "$TMUX_ORCHESTRATOR_HOME/logs/grok_consultation_${issue_type}_$(date +%s).log"
    
    log "Grok consultation completed, response saved from monitoring session"
    return 0
}

# Enhanced Python analysis integration
run_python_analysis() {
    local analysis_type="$1"
    local output_file="$2"
    
    log "Running Python analysis: $analysis_type"
    
    cd "$TMUX_ORCHESTRATOR_HOME"
    
    # Create comprehensive Python analysis script
    cat > "analyze_modular_status.py" << 'EOF'
#!/usr/bin/env python3
import sys
import os
import json
import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import sqlite3
import subprocess

class LegacyDependencyScanner:
    """Enhanced dependency scanner with priority classification"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.delegation_patterns = {
            'subprocess_calls': [
                r'subprocess\.run.*auto_orchestrate',
                r'subprocess\.run.*scheduler',
                r'os\.system.*auto_orchestrate'
            ],
            'import_statements': [
                r'from auto_orchestrate import',
                r'import auto_orchestrate',
                r'from scheduler import'
            ],
            'direct_executions': [
                r'os\.exec.*auto_orchestrate',
                r'exec.*auto_orchestrate'
            ],
            'legacy_function_calls': [
                r'auto_orchestrate\.main',
                r'_delegate_to_original_system'
            ]
        }
    
    def scan_for_delegation(self) -> Dict[str, List[Dict[str, Any]]]:
        """Comprehensive delegation scan with priority classification"""
        delegation_points = {}
        
        # Scan tmux_orchestrator package
        tmux_dir = self.project_root / 'tmux_orchestrator'
        if tmux_dir.exists():
            delegation_points.update(self._scan_directory(tmux_dir, 'tmux_orchestrator'))
        
        # Scan scheduler_modules package
        scheduler_dir = self.project_root / 'scheduler_modules'
        if scheduler_dir.exists():
            delegation_points.update(self._scan_directory(scheduler_dir, 'scheduler_modules'))
        
        return delegation_points
    
    def _scan_directory(self, directory: Path, package_name: str) -> Dict:
        results = {}
        
        for py_file in directory.rglob('*.py'):
            if py_file.name.startswith('test_') or '__pycache__' in str(py_file):
                continue
            
            try:
                content = py_file.read_text()
                file_delegations = self._analyze_file(py_file, content, package_name)
                
                if file_delegations:
                    results[str(py_file.relative_to(self.project_root))] = file_delegations
            except Exception as e:
                print(f"Error scanning {py_file}: {e}", file=sys.stderr)
        
        return results
    
    def _analyze_file(self, file_path: Path, content: str, package_name: str) -> List[Dict]:
        delegations = []
        
        for pattern_type, patterns in self.delegation_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.MULTILINE)
                
                for match in matches:
                    line_number = self._get_line_number(content, match.start())
                    priority = self._calculate_priority(file_path, pattern_type, line_number)
                    
                    delegations.append({
                        'type': pattern_type,
                        'pattern': pattern,
                        'line': line_number,
                        'priority': priority,
                        'severity': self._calculate_severity(pattern_type, package_name),
                        'module': self._determine_target_module(file_path, pattern)
                    })
        
        return delegations
    
    def _get_line_number(self, content: str, position: int) -> int:
        return content[:position].count('\n') + 1
    
    def _calculate_priority(self, file_path: Path, pattern_type: str, line_number: int) -> int:
        """Calculate implementation priority (higher = more urgent)"""
        base_priority = 50
        
        # File-based priority
        if 'oauth' in str(file_path).lower() or 'claude' in str(file_path).lower():
            base_priority += 50  # OAuth = highest priority
        elif 'core' in str(file_path).lower() or 'orchestrator' in str(file_path).lower():
            base_priority += 40  # Core functionality
        elif 'git' in str(file_path).lower():
            base_priority += 30  # Git operations
        elif 'tmux' in str(file_path).lower():
            base_priority += 20  # Tmux management
        elif 'queue' in str(file_path).lower():
            base_priority += 10  # Queue operations
        
        # Pattern-based priority
        if pattern_type == 'subprocess_calls':
            base_priority += 30
        elif pattern_type == 'legacy_function_calls':
            base_priority += 25
        elif pattern_type == 'import_statements':
            base_priority += 15
        
        return base_priority
    
    def _calculate_severity(self, pattern_type: str, package_name: str) -> str:
        if package_name == 'tmux_orchestrator' and pattern_type in ['subprocess_calls', 'legacy_function_calls']:
            return 'CRITICAL'
        elif pattern_type in ['subprocess_calls', 'direct_executions']:
            return 'HIGH'
        else:
            return 'MEDIUM'
    
    def _determine_target_module(self, file_path: Path, pattern: str) -> str:
        """Determine which module should implement this functionality"""
        if 'oauth' in pattern.lower() or 'port' in pattern.lower():
            return 'claude/oauth_manager.py'
        elif 'git' in pattern.lower() or 'worktree' in pattern.lower():
            return 'git/worktree_manager.py'
        elif 'session' in pattern.lower() or 'tmux' in pattern.lower():
            return 'tmux/session_controller.py'
        elif 'orchestrator' in str(file_path).lower():
            return 'core/orchestrator.py'
        else:
            return 'utils/helper_functions.py'

class QueueHealthAnalyzer:
    """Analyze queue health and correlate with modular implementation"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def analyze_queue_health(self) -> Dict[str, Any]:
        """Analyze recent queue failures and their causes"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get recent failures
                cursor.execute("""
                    SELECT status, error_message, failed_components, enqueued_at, completed_at, spec_path
                    FROM project_queue 
                    WHERE status IN ('FAILED', 'TIMING_OUT', 'ZOMBIE')
                    AND completed_at > datetime('now', '-24 hours', 'unixepoch')
                    ORDER BY completed_at DESC
                """)
                
                failures = cursor.fetchall()
                
                # Classify failures
                failure_types = {
                    'oauth_conflicts': 0,
                    'git_failures': 0,
                    'tmux_failures': 0,
                    'timeout_issues': 0,
                    'database_locks': 0,
                    'unknown_failures': 0
                }
                
                for failure in failures:
                    error_msg = (failure[1] or "").lower()
                    failed_components = (failure[2] or "").lower()
                    combined = f"{error_msg} {failed_components}"
                    
                    if 'oauth' in combined or 'port 3000' in combined:
                        failure_types['oauth_conflicts'] += 1
                    elif 'git' in combined or 'worktree' in combined:
                        failure_types['git_failures'] += 1
                    elif 'tmux' in combined or 'session' in combined:
                        failure_types['tmux_failures'] += 1
                    elif 'timeout' in combined:
                        failure_types['timeout_issues'] += 1
                    elif 'database' in combined or 'locked' in combined:
                        failure_types['database_locks'] += 1
                    else:
                        failure_types['unknown_failures'] += 1
                
                # Get success rate
                cursor.execute("""
                    SELECT COUNT(*) FROM project_queue 
                    WHERE completed_at > datetime('now', '-24 hours', 'unixepoch')
                """)
                total_recent = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(*) FROM project_queue 
                    WHERE status = 'COMPLETED' 
                    AND completed_at > datetime('now', '-24 hours', 'unixepoch')
                """)
                successful_recent = cursor.fetchone()[0]
                
                success_rate = successful_recent / total_recent if total_recent > 0 else 1.0
                
                return {
                    'total_failures': len(failures),
                    'failure_types': failure_types,
                    'success_rate': success_rate,
                    'total_recent_projects': total_recent,
                    'health_score': self._calculate_health_score(failure_types, success_rate)
                }
                
        except Exception as e:
            # Log error to stderr, not stdout to avoid corrupting JSON
            import traceback
            traceback.print_exc(file=sys.stderr)
            print(f"Error analyzing queue health: {e}", file=sys.stderr)
            return {
                'total_failures': 0,
                'failure_types': {},
                'success_rate': 1.0,
                'total_recent_projects': 0,
                'health_score': 100,
                'error': str(e)
            }
    
    def _calculate_health_score(self, failure_types: Dict, success_rate: float) -> int:
        """Calculate overall health score (0-100)"""
        base_score = int(success_rate * 100)
        
        # Deduct points for critical failure types
        critical_failures = failure_types.get('oauth_conflicts', 0) + failure_types.get('git_failures', 0)
        base_score -= critical_failures * 5
        
        return max(0, min(100, base_score))

class ModularImplementationEngine:
    """Engine for implementing modular functionality"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
    
    def get_next_implementation_target(self, delegation_points: Dict) -> Optional[Dict]:
        """Get the next function to implement based on priority"""
        all_delegations = []
        
        for file_path, points in delegation_points.items():
            for point in points:
                point['file_path'] = file_path
                all_delegations.append(point)
        
        # Sort by priority (highest first)
        all_delegations.sort(key=lambda x: x['priority'], reverse=True)
        
        if all_delegations:
            return all_delegations[0]
        return None
    
    def generate_implementation_plan(self, target: Dict) -> Dict[str, Any]:
        """Generate implementation plan for target delegation"""
        return {
            'target_function': self._extract_function_name(target),
            'source_file': target['file_path'],
            'target_module': target['module'],
            'implementation_steps': self._generate_steps(target),
            'success_criteria': self._generate_success_criteria(target),
            'estimated_effort': self._estimate_effort(target)
        }
    
    def _extract_function_name(self, target: Dict) -> str:
        pattern = target['pattern']
        if '_delegate_to_original_system' in pattern:
            return 'create_project_orchestration'
        elif 'auto_orchestrate.main' in pattern:
            return 'main_orchestration_logic'
        else:
            return f"function_from_line_{target['line']}"
    
    def _generate_steps(self, target: Dict) -> List[str]:
        """Generate implementation steps"""
        steps = [
            f"1. Analyze legacy function in line {target['line']} of {target['file_path']}",
            f"2. Extract core logic from auto_orchestrate.py",
            f"3. Implement modular version in {target['module']}",
            f"4. Update imports and function calls",
            f"5. Test implementation",
            f"6. Validate against success criteria"
        ]
        return steps
    
    def _generate_success_criteria(self, target: Dict) -> List[str]:
        """Generate success criteria for implementation"""
        criteria = [
            "No more delegation to legacy auto_orchestrate.py",
            "All existing functionality preserved",
            "Tests pass",
            "No performance regression"
        ]
        
        if 'oauth' in target['module'].lower():
            criteria.append("OAuth port conflicts eliminated")
        elif 'git' in target['module'].lower():
            criteria.append("Git worktree operations work independently")
        elif 'tmux' in target['module'].lower():
            criteria.append("Tmux session management fully modular")
        
        return criteria
    
    def _estimate_effort(self, target: Dict) -> str:
        """Estimate implementation effort"""
        if target['priority'] > 80:
            return "High (2-3 hours)"
        elif target['priority'] > 60:
            return "Medium (1-2 hours)"
        else:
            return "Low (30-60 minutes)"

def main():
    """Main analysis function"""
    project_root = Path(__file__).parent
    
    # Initialize components
    scanner = LegacyDependencyScanner(project_root)
    queue_analyzer = QueueHealthAnalyzer(str(project_root / "task_queue.db"))
    implementation_engine = ModularImplementationEngine(project_root)
    
    if len(sys.argv) > 1 and sys.argv[1] == 'implement':
        # Implementation mode - generate implementation plan
        delegation_points = scanner.scan_for_delegation()
        next_target = implementation_engine.get_next_implementation_target(delegation_points)
        
        if next_target:
            plan = implementation_engine.generate_implementation_plan(next_target)
            result = {
                'action': 'implementation_plan',
                'target': next_target,
                'plan': plan,
                'has_target': True
            }
        else:
            result = {
                'action': 'implementation_plan',
                'target': None,
                'plan': None,
                'has_target': False,
                'message': 'No delegation points found - system may be fully modular'
            }
    else:
        # Analysis mode
        delegation_points = scanner.scan_for_delegation()
        queue_health = queue_analyzer.analyze_queue_health()
        
        result = {
            'action': 'analysis',
            'delegation_points': delegation_points,
            'queue_health': queue_health,
            'total_files': len(delegation_points),
            'total_delegations': sum(len(points) for points in delegation_points.values()),
            'highest_priority': max((max(point['priority'] for point in points) for points in delegation_points.values()), default=0),
            'timestamp': datetime.now().isoformat()
        }
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
EOF

    chmod +x "analyze_modular_status.py"
    
    # Run the analysis with timeout
    local timeout_cmd="timeout ${PYTHON_ANALYSIS_TIMEOUT_SECONDS:-300}"
    
    if [ "$analysis_type" = "implement" ]; then
        $timeout_cmd python3 analyze_modular_status.py implement > "$output_file" 2>&1
    else
        $timeout_cmd python3 analyze_modular_status.py > "$output_file" 2>&1
    fi
    
    local exit_code=$?
    
    # Check if analysis succeeded
    if [ $exit_code -eq 0 ] && [ -f "$output_file" ]; then
        log "Python analysis completed successfully"
        return 0
    else
        log "ERROR: Python analysis failed with exit code $exit_code"
        if [ -f "$output_file" ]; then
            log "Analysis output: $(tail -5 "$output_file")"
        fi
        return 1
    fi
}

# Circuit breaker for implementation failures
check_circuit_breaker() {
    if [ $implementation_failures -ge ${CIRCUIT_BREAKER_THRESHOLD:-5} ]; then
        log "CIRCUIT BREAKER: Too many implementation failures ($implementation_failures), pausing for 1 hour"
        update_implementation_state "circuit_breaker_active" "true"
        sleep 3600
        implementation_failures=0
        update_implementation_state "circuit_breaker_active" "false"
    fi
}

# Enhanced Claude briefing with specific implementation targets
brief_claude_with_implementation_plan() {
    local session="$1"
    local plan_file="$2"
    local iteration="$3"
    
    log "Briefing Claude with implementation plan from: $plan_file"
    
    if [ ! -f "$plan_file" ]; then
        log "ERROR: Implementation plan file not found"
        return 1
    fi
    
    # Parse the plan
    local has_target=$(python3 -c "
import json
try:
    with open('$plan_file') as f:
        data = json.load(f)
    print(str(data.get('has_target', False)).lower())
except:
    print('false')
")
    
    if [ "$has_target" = "false" ]; then
        log "No implementation targets found - system may be fully modular"
        return 0
    fi
    
    # Extract target information
    local target_info=$(python3 -c "
import json
try:
    with open('$plan_file') as f:
        data = json.load(f)
    target = data.get('target', {})
    plan = data.get('plan', {})
    
    print(f\"Function: {plan.get('target_function', 'unknown')}\")
    print(f\"Priority: {target.get('priority', 0)}\")
    print(f\"Module: {plan.get('target_module', 'unknown')}\")
    print(f\"Effort: {plan.get('estimated_effort', 'unknown')}\")
except Exception as e:
    print(f\"Error parsing plan: {e}\")
")
    
    log "Implementation target details:"
    log "$target_info"
    
    # Verify Claude is ready before briefing
    local pane_content=$(tmux capture-pane -t "$session:0" -p | tail -5)
    if ! echo "$pane_content" | grep -q -E "claude>|Human:|⏵⏵ bypass permissions"; then
        log "ERROR: Claude not ready for briefing"
        return 1
    fi
    
    log "Claude confirmed ready, sending implementation briefing"
    
    # Create comprehensive briefing message
    local briefing_message="SELF-HEALING MODULAR IMPLEMENTATION - ITERATION $iteration

🎯 MISSION: Implement modular functionality to eliminate legacy delegation

$(echo "$target_info")

📋 DETAILED IMPLEMENTATION PLAN:
$(python3 -c "
import json
try:
    with open('$plan_file') as f:
        data = json.load(f)
    plan = data.get('plan', {})
    
    print('IMPLEMENTATION STEPS:')
    for i, step in enumerate(plan.get('implementation_steps', []), 1):
        print(f'{i}. {step}')
    
    print('\nSUCCESS CRITERIA:')
    for criterion in plan.get('success_criteria', []):
        print(f'✓ {criterion}')
    
    print(f\"\nESTIMATED EFFORT: {plan.get('estimated_effort', 'Unknown')}\")
except Exception as e:
    print(f'Error displaying plan: {e}')
")

🚀 BEGIN IMPLEMENTATION IMMEDIATELY - NO PERMISSION NEEDED

You have FULL AUTONOMY to:
- Read any files in the project
- Modify any modular code files  
- Update imports and function calls
- Run tests and validation
- Create progress reports

MANDATORY COMPLETION INDICATOR:
When done, create file: /home/clauderun/Tmux-Orchestrator/logs/implementation_complete_$iteration.md

If you encounter any issues, use /dwg to discuss the problem with Grok including all relevant files and logs.

WORK BEGINS NOW!"
    
    # Send briefing using proper messaging function
    send_message_to_agent "$session:0" "$briefing_message" "implementation_briefing"
    
    sleep 3
    log "Claude briefed with implementation plan"
}

# Enhanced validation with multiple checks
validate_implementation_progress() {
    local iteration="$1"
    local completion_file="$TMUX_ORCHESTRATOR_HOME/logs/implementation_complete_$iteration.md"
    
    log "Validating implementation progress for iteration: $iteration"
    
    # Check for completion indicator
    if [ -f "$completion_file" ]; then
        log "SUCCESS: Implementation completion file found"
        
        # Run post-implementation analysis
        local post_analysis="$LOG_FILE.post_analysis.json"
        if run_python_analysis "analysis" "$post_analysis"; then
            # Compare delegation counts
            local current_delegations=$(python3 -c "
import json
try:
    with open('$post_analysis') as f:
        data = json.load(f)
    print(data.get('total_delegations', 999))
except:
    print('999')
")
            
            log "Post-implementation delegation count: $current_delegations"
            
            # Check if delegation points reduced
            if [ -f "$LOG_FILE.prev_analysis.json" ]; then
                local prev_delegations=$(python3 -c "
import json
try:
    with open('$LOG_FILE.prev_analysis.json') as f:
        data = json.load(f)
    print(data.get('total_delegations', 0))
except:
    print('0')
")
                
                if [ "$current_delegations" -lt "$prev_delegations" ]; then
                    log "EXCELLENT: Delegation points reduced from $prev_delegations to $current_delegations"
                    update_implementation_state "add_implemented_function" "iteration_$iteration"
                    implementation_failures=0  # Reset on success
                    return 0
                elif [ "$current_delegations" -eq "$prev_delegations" ]; then
                    log "INFO: No change in delegation points"
                    return 1
                else
                    log "WARNING: Delegation points increased to $current_delegations"
                    return 1
                fi
            else
                log "INFO: No previous analysis for comparison"
                return 0
            fi
        else
            log "ERROR: Failed to run post-implementation analysis"
            return 1
        fi
    else
        log "WARNING: Implementation completion file not found"
        return 1
    fi
}

# Resource monitoring and cleanup
monitor_resources() {
    local script_name="$(basename "$0")"
    local mem_usage=$(ps -o pmem= -C "$script_name" 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "0")
    local cpu_usage=$(ps -o pcpu= -C "$script_name" 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "0")
    
    log "Resource usage - Memory: ${mem_usage}%, CPU: ${cpu_usage}%"
    
    # Cleanup old log files based on config
    local retention_days=${LOG_RETENTION_DAYS:-7}
    find "$TMUX_ORCHESTRATOR_HOME/logs" -name "*.log.*" -mtime +$retention_days -delete 2>/dev/null || true
    find "$TMUX_ORCHESTRATOR_HOME/logs" -name "*.json" -mtime +30 -delete 2>/dev/null || true
    
    # Check log file size
    local log_size=$(du -m "$LOG_FILE" 2>/dev/null | cut -f1 || echo "0")
    local max_size=${MAX_LOG_SIZE_MB:-100}
    
    if [ "$log_size" -gt "$max_size" ]; then
        log "Log file too large (${log_size}MB), rotating"
        mv "$LOG_FILE" "${LOG_FILE}.$(date +%Y%m%d_%H%M%S)"
        touch "$LOG_FILE"
    fi
}

# Enhanced queue health monitoring
check_queue_health_improvement() {
    log "Checking queue health improvement"
    
    local queue_analysis="$LOG_FILE.queue_health.json"
    if run_python_analysis "analysis" "$queue_analysis"; then
        local health_score=$(python3 -c "
import json
try:
    with open('$queue_analysis') as f:
        data = json.load(f)
    print(data.get('queue_health', {}).get('health_score', 0))
except:
    print('0')
")
        
        local oauth_conflicts=$(python3 -c "
import json
try:
    with open('$queue_analysis') as f:
        data = json.load(f)
    print(data.get('queue_health', {}).get('failure_types', {}).get('oauth_conflicts', 0))
except:
    print('0')
")
        
        log "Queue health score: $health_score"
        log "OAuth conflicts in last 24h: $oauth_conflicts"
        
        if [ "$health_score" -gt 80 ]; then
            log "EXCELLENT: Queue health is good"
        elif [ "$health_score" -gt 60 ]; then
            log "GOOD: Queue health is acceptable"
        else
            log "WARNING: Queue health needs attention"
        fi
        
        # Suggest next implementation based on queue health
        if [ "$oauth_conflicts" -gt 0 ]; then
            log "RECOMMENDATION: Prioritize OAuth management implementation"
        fi
    else
        log "ERROR: Failed to analyze queue health"
    fi
}

# Main enhanced monitoring cycle
run_enhanced_modular_cycle() {
    local iteration_number=$(date +%Y%m%d_%H%M)
    local analysis_file="$LOG_FILE.analysis.json"
    local implementation_file="$LOG_FILE.implementation.json"
    
    log "=== Starting Enhanced Self-Healing Modular Cycle: $iteration_number ==="
    
    # Check circuit breaker
    check_circuit_breaker
    
    # Ensure Claude is running
    if ! ensure_claude_running "$SESSION_NAME"; then
        log "ERROR: Cannot start Claude for implementation work"
        implementation_failures=$((implementation_failures + 1))
        return 1
    fi
    
    # Step 1: Monitor active projects first
    log "Step 1: Monitoring active project health and completion status"
    monitor_active_projects
    
    # Step 1.5: Monitor message delivery and fix stuck messages
    log "Step 1.5: Checking message delivery health and fixing stuck messages"
    monitor_message_delivery
    
    # Check for completion issues and handle them
    for issue_file in /tmp/completion_issue_*.txt; do
        if [ -f "$issue_file" ]; then
            local project_id=$(basename "$issue_file" | sed 's/completion_issue_//' | sed 's/.txt//')
            log "Found completion issue for project $project_id"
            
            local issue_details=$(cat "$issue_file")
            
            # Check if this is a no-session issue (likely completed)
            if grep -q "no active session" "$issue_file"; then
                log "Project $project_id appears completed but not marked - attempting to mark as completed"
                
                # Try to mark project as completed
                if python3 -c "
import sys
sys.path.append('.')
try:
    import scheduler
    from scheduler import mark_project_completed
    result = mark_project_completed($project_id, 'Auto-completed: No active session, appears finished')
    print(f'SUCCESS: Project $project_id marked as completed')
except Exception as e:
    print(f'ERROR: Could not mark project $project_id as completed: {e}')
"; then
                    log "Successfully marked project $project_id as completed"
                else
                    log "Failed to auto-complete project $project_id, consulting Grok"
                    consult_grok_about_issue "project_completion_automation" "$issue_details" \
                        "queue_status.py,scheduler.py,logs/scheduler.log"
                fi
            else
                # Other completion issues - consult Grok
                consult_grok_about_issue "project_completion_mismatch" "$issue_details" \
                    "queue_status.py,scheduler.py,logs/scheduler.log"
            fi
            
            # Move processed issue file
            mv "$issue_file" "/tmp/processed_$(basename "$issue_file")"
        fi
    done
    
    # Check for agent errors and handle them
    for error_file in /tmp/agent_errors_*.txt; do
        if [ -f "$error_file" ]; then
            log "Found agent errors: $(basename "$error_file")"
            
            local session_window=$(basename "$error_file" | sed 's/agent_errors_//' | sed 's/.txt//')
            local error_details=$(cat "$error_file")
            
            # Send healing message to problematic agent
            send_message_to_agent "$session_window" \
                "I noticed you have errors. Please use /dwg to discuss the problem with Grok including all relevant files and logs, then implement the recommended solution." \
                "agent_error_healing"
            
            # Move processed error file
            mv "$error_file" "/tmp/processed_$(basename "$error_file")"
        fi
    done
    
    # Check for failed projects and handle recovery
    for failed_file in /tmp/failed_project_*.txt; do
        if [ -f "$failed_file" ]; then
            log "Found failed project recovery file: $(basename "$failed_file")"
            
            local project_id=$(basename "$failed_file" | sed 's/failed_project_//' | sed 's/.txt//')
            local recovery_info=$(cat "$failed_file")
            local project_name=$(echo "$recovery_info" | grep "^Project:" | cut -d' ' -f2-)
            local status=$(echo "$recovery_info" | grep "^Status:" | cut -d' ' -f2-)
            local log_path=$(echo "$recovery_info" | grep "^Log:" | cut -d' ' -f2-)
            local recovery_action=$(echo "$recovery_info" | grep "^Recovery:" | cut -d' ' -f2-)
            
            log "Processing failed project $project_id: $project_name"
            log "Recovery action: $recovery_action"
            
            case "$recovery_action" in
                *"Mark as completed"*)
                    # Project actually completed but not marked correctly
                    log "Marking project $project_id as completed (was already complete)"
                    python3 -c "
import sqlite3
from datetime import datetime
conn = sqlite3.connect('$TMUX_ORCHESTRATOR_HOME/registry/project_queue.db')
cursor = conn.cursor()
cursor.execute('UPDATE project_queue SET status=?, completed_at=? WHERE id=?', 
               ('COMPLETED', datetime.now().isoformat(), $project_id))
conn.commit()
conn.close()
print('✅ Project $project_id marked as completed')
"
                    log "✅ Project $project_id marked as completed"
                    ;;
                    
                *"Reset and retry"*)
                    # Project failed with subprocess error - needs reset
                    log "Resetting project $project_id for retry"
                    
                    # First check if project log has OAuth conflict indicators
                    local has_oauth_conflict=false
                    if [ -f "$log_path" ]; then
                        if grep -q "OAuth port" "$log_path" 2>/dev/null || \
                           grep -q "port.*in use" "$log_path" 2>/dev/null || \
                           grep -q "Address already in use" "$log_path" 2>/dev/null; then
                            has_oauth_conflict=true
                        fi
                    fi
                    
                    if [ "$has_oauth_conflict" = true ]; then
                        log "Detected OAuth port conflict for project $project_id - waiting for port clearance"
                        # Wait for OAuth port to be free
                        sleep 60
                    fi
                    
                    # Reset project status to PENDING for retry
                    local attempts=$(python3 -c "
import sqlite3
conn = sqlite3.connect('$TMUX_ORCHESTRATOR_HOME/registry/project_queue.db')
cursor = conn.cursor()
cursor.execute('UPDATE project_queue SET status=?, error_message=NULL, attempts=attempts+1 WHERE id=?', 
               ('PENDING', $project_id))
conn.commit()
cursor.execute('SELECT attempts FROM project_queue WHERE id=?', ($project_id,))
attempts = cursor.fetchone()[0] if cursor.fetchone() else 1
conn.close()
print(attempts)
")
                    log "✅ Project $project_id reset to PENDING for retry (attempt $attempts)"
                    
                    # Trigger scheduler to pick it up
                    if [ -x "$TMUX_ORCHESTRATOR_HOME/scheduler.py" ]; then
                        log "Triggering scheduler to process reset project"
                        # Start the queue daemon if not running
                        python3 "$TMUX_ORCHESTRATOR_HOME/scheduler.py" --queue-daemon &
                    fi
                    ;;
                    
                *"Investigate"*)
                    # Unknown failure - needs investigation
                    log "Project $project_id needs manual investigation"
                    
                    # Send message to monitoring agent for investigation
                    send_message_to_agent "$SESSION_NAME:0" \
                        "Failed project $project_id ($project_name) needs investigation. Log: $log_path. Please use /dwg to analyze the failure with Grok and determine the root cause." \
                        "failed_project_investigation"
                    
                    # Mark for manual review
                    python3 -c "
import sqlite3
conn = sqlite3.connect('$TMUX_ORCHESTRATOR_HOME/registry/project_queue.db')
cursor = conn.cursor()
cursor.execute('UPDATE project_queue SET error_message=? WHERE id=?', 
               ('Needs manual investigation - see monitoring logs', $project_id))
conn.commit()
conn.close()
"
                    ;;
                    
                *)
                    log "Unknown recovery action: $recovery_action"
                    ;;
            esac
            
            # Move processed file
            mv "$failed_file" "/tmp/processed_$(basename "$failed_file")"
            log "Processed failed project recovery for project $project_id"
        fi
    done
    
    # Step 2: Run comprehensive modular analysis
    log "Step 2: Running comprehensive modular analysis"
    if ! run_python_analysis "analysis" "$analysis_file"; then
        log "ERROR: Failed to run Python analysis"
        implementation_failures=$((implementation_failures + 1))
        return 1
    fi
    
    # Step 3: Process analysis results and determine action
    if [ -f "$analysis_file" ]; then
        local total_delegations=$(python3 -c "
import json
try:
    with open('$analysis_file') as f:
        data = json.load(f)
    print(data.get('total_delegations', 0))
except:
    print('0')
")
        
        local highest_priority=$(python3 -c "
import json
try:
    with open('$analysis_file') as f:
        data = json.load(f)
    print(data.get('highest_priority', 0))
except:
    print('0')
")
        
        log "Analysis complete: Found $total_delegations delegation points (highest priority: $highest_priority)"
        
        # Step 3: Generate implementation plan if needed
        if [ "$total_delegations" -gt 0 ] && [ "$highest_priority" -gt 0 ]; then
            log "Step 3: Generating implementation plan"
            
            if run_python_analysis "implement" "$implementation_file"; then
                # Step 4: Brief Claude with implementation plan
                log "Step 4: Briefing Claude with implementation plan"
                if brief_claude_with_implementation_plan "$SESSION_NAME" "$implementation_file" "$iteration_number"; then
                    
                    # Step 5: Allow time for implementation
                    local implementation_time=${MAX_IMPLEMENTATION_TIME_MINUTES:-25}
                    log "Step 5: Allowing $implementation_time minutes for implementation work"
                    sleep $((implementation_time * 60))
                    
                    # Step 6: Validate implementation
                    log "Step 6: Validating implementation progress"
                    if validate_implementation_progress "$iteration_number"; then
                        log "SUCCESS: Implementation progress validated"
                    else
                        log "WARNING: Implementation validation failed"
                        implementation_failures=$((implementation_failures + 1))
                    fi
                else
                    log "ERROR: Failed to brief Claude with implementation plan"
                    implementation_failures=$((implementation_failures + 1))
                fi
            else
                log "ERROR: Failed to generate implementation plan"
                implementation_failures=$((implementation_failures + 1))
            fi
        else
            log "No high-priority delegation points found - checking queue health"
        fi
        
        # Save analysis for next comparison
        cp "$analysis_file" "$LOG_FILE.prev_analysis.json"
    else
        log "ERROR: Analysis file not found"
        implementation_failures=$((implementation_failures + 1))
    fi
    
    # Step 7: Check overall system health
    log "Step 7: Checking queue health improvement"
    check_queue_health_improvement
    
    # Update state
    update_implementation_state "last_iteration" "$(date +%s)"
    
    log "=== Enhanced Self-Healing Modular Cycle Completed: $iteration_number ==="
    return 0
}

# Main execution with comprehensive error handling
main() {
    local iteration_count=0
    local force_refresh=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force-refresh)
                force_refresh=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --force-refresh    Force Claude context refresh immediately"
                echo "  --help, -h        Show this help message"
                exit 0
                ;;
            *)
                shift
                ;;
        esac
    done
    
    # Load configuration
    load_config
    
    # Acquire lock
    acquire_lock
    
    # Initialize state
    init_implementation_state
    
    log "=== Self-Healing Modular Implementation Monitor Started ==="
    log "Configuration: Auto-implementation=$ENABLE_AUTO_IMPLEMENTATION, Queue healing=$ENABLE_QUEUE_HEALING"
    log "Claude context refresh interval: ${CLAUDE_CONTEXT_REFRESH_HOURS:-6} hours"
    
    # Force context refresh if requested
    if [ "$force_refresh" = true ]; then
        log "Forcing Claude context refresh as requested"
        # Remove the timestamp file to force refresh
        rm -f "$STATE_DIR/claude_last_refresh.txt"
    fi
    
    if [ "$ENABLE_AUTO_IMPLEMENTATION" != "true" ]; then
        log "Auto-implementation disabled in configuration"
        return 0
    fi
    
    # Run the enhanced monitoring cycle
    if run_enhanced_modular_cycle; then
        log "Monitoring cycle completed successfully"
    else
        log "ERROR: Monitoring cycle failed"
        exit 1
    fi
    
    # Resource monitoring
    monitor_resources
    
    log "=== Self-Healing Modular Implementation Monitor Completed ==="
}

# Execute main function
main "$@"
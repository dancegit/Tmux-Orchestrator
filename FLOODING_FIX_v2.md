# Tmux Orchestrator Flooding Fix v2 - Comprehensive Solution

## Problem Summary
The orchestrator was getting flooded with messages despite our previous fix for interval_minutes=0. The root causes were:
1. Existing high-retry tasks (up to 136 retries) continuing to execute
2. Missing `bc` command causing exponential backoff to fail
3. Messages being sent to bash shell instead of Claude agents
4. No retry cap allowing infinite retry loops

## Fixes Implemented

### 1. Added Retry Cap in scheduler.py
- Added MAX_TASK_RETRIES environment variable (default: 5)
- Tasks exceeding retry limit are permanently disabled
- Prevents infinite retry loops

### 2. Fixed bc Dependency in send-claude-message.sh
- Replaced `bc` calculation with bash-native arithmetic
- Changed: `delay=$(echo "$delay * $BACKOFF_MULTIPLIER" | bc)`
- To: `delay=$((delay * BACKOFF_MULTIPLIER))`
- No external dependency required

### 3. Added Session Validation
- New `_is_session_ready()` method checks:
  - Session exists
  - Target window is not running bash/sh
- Prevents sending messages to invalid targets

### 4. Database Cleanup
- Created cleanup_high_retry_tasks.py script
- Removed 14 tasks with retry_count >= 10
- Disabled 12 one-time tasks with retries
- Backed up database before changes

## Results
- No pending tasks in queue
- No more flooding messages
- Scheduler running smoothly
- All high-retry tasks purged

## Prevention Measures
1. Retry cap prevents future infinite loops
2. Session validation prevents invalid sends
3. No external dependencies for critical paths
4. One-time tasks properly handled

## Configuration
Set these environment variables as needed:
- MAX_TASK_RETRIES=5 (max retry attempts)
- BACKOFF_MULTIPLIER=2 (retry delay multiplier)

## Monitoring
Check for issues with:
```bash
# Check for high retry tasks
python3 -c "import sqlite3; conn = sqlite3.connect('task_queue.db'); cur = conn.cursor(); cur.execute('SELECT id, retry_count FROM tasks WHERE retry_count > 5'); print(cur.fetchall())"

# Monitor scheduler logs
tail -f logs/scheduler.out | grep -E "(ERROR|exceeded|retry)"
```
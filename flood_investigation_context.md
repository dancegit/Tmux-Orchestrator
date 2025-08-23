# Tmux Orchestrator Flooding Investigation

## Problem Description
The orchestrator is still getting flooded with messages despite our previous fix. The messages are being sent to a bash shell instead of Claude, showing:
```
SCHEDULED CHECK-IN: Agent orchestrator completed: Task 2998 completed successfully
-bash: SCHEDULED: command not found
```

## Key Findings

### 1. Database Analysis
- Tasks with interval_minutes=0 are still being created
- Tasks 3006-3010 have extremely high retry counts (112-126)
- These tasks keep failing and retrying, causing the flood

### 2. Script Issues
- `bc` command is missing, causing send-claude-message.sh to fail at line 134
- Exponential backoff calculation fails: `delay=$(echo "$delay * $BACKOFF_MULTIPLIER" | bc)`
- This causes rapid retries without proper delays

### 3. Message Delivery
- Messages are being sent to bash shell instead of Claude agent
- The orchestrator window might not have Claude running
- Session name mismatch: some tasks use full session name with hash, others without

### 4. Root Causes
1. Our previous fix only prevents rescheduling, but doesn't handle existing high-retry tasks
2. Missing `bc` command breaks exponential backoff
3. Orchestrator window might be in wrong state (bash instead of Claude)
4. Session name inconsistency causing message routing issues

## Current State
- Scheduler is running but failing to deliver messages
- High retry counts causing continuous message attempts
- Orchestrator flooded with bash command errors
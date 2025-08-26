# Tmux Orchestrator Scheduler Investigation Summary
**Date**: 2025-08-26
**Context**: Investigation of Project 67 check-ins stopping

## Completed Fixes

### 1. Scheduler Patches Applied
All three critical patches from Grok have been successfully applied to `scheduler.py`:

1. **lock_fd AttributeError Fix** (Lines 324-340)
   - Fixed `_heartbeat_thread` to access lock_fd through `self.lock_manager`
   - Prevents AttributeError: 'TmuxOrchestratorScheduler' object has no attribute 'lock_fd'

2. **Active Orchestration Detection Fix** (Lines 1840-1902)
   - Added tmux fallback detection when no JSON-based active sessions
   - Checks tmux sessions when `json_based_active == 0`
   - Activity threshold changed from 1 hour to 6 hours (line 1886: `if age_seconds < 21600`)

3. **2026 Date Bug Fix** (Lines 414-417)
   - Fixed one-time tasks being scheduled for year 2026
   - Now properly calls `remove_task()` for one-time tasks

### 2. Service Configuration
- Systemd service (`tmux-orchestrator-queue.service`) updated to remove restrictive security settings
- Service now running successfully at `/etc/systemd/system/tmux-orchestrator-queue.service`
- Removed `PrivateTmp` and `ProtectSystem` to allow tmux access

## Current Status

### Project 67 Elliott Wave Session
- **Original Session**: `elliott-wave-mvp-wave-5-detection-implementation-impl-6604a61f`
  - Was inactive for 10+ hours (last activity: 2025-08-25 23:55:57)
  - Lost during server reboot due to 100% CPU
  
- **New Session**: `elliott-wave-mvp-wave-5-detection-enhancement-impl-d7293152`
  - Created via `./qs --reset 67` at 2025-08-26 11:00:55
  - Currently in 15-minute grace period (scheduler shows "Project 67 is within grace period")

### Scheduler Status
- Running as systemd service
- Detecting tmux sessions correctly (found 1 session after reboot)
- Activity threshold increased to 6 hours (from 1 hour)
- Tasks rescheduled to start at 10:52 on 2025-08-26

### Task Queue Status
Found 7 overdue tasks for the old elliott-wave session:
- All targeting orchestrator role with different windows
- Intervals: 20-45 minutes
- Were scheduled for 2025-08-25 19:26-19:51

## Pending Issues

### 1. Incomplete Fixes
- **State Synchronizer AttributeError** (Todo #5)
  - NoneType error still needs investigation
  
- **Scheduler --list Lock Issue** (Todo #29)
  - Need to make `scheduler.py --list` work when another scheduler is running
  - Currently blocked by file lock

### 2. Monitoring Tasks
- Continue monitoring Project 67 check-ins after grace period expires
- Verify scheduled tasks run properly for new session ID `d7293152`

## Key Learnings

1. **Session Persistence**: Tmux sessions don't survive reboots
2. **Activity Threshold**: 1-hour threshold was too aggressive for long-running projects
3. **Systemd Restrictions**: Security settings can prevent tmux access
4. **Grace Period**: New projects have a 15-minute grace period before monitoring

## Next Steps

1. Wait for Project 67 grace period to expire (~15 minutes from creation)
2. Monitor if scheduled check-ins resume automatically
3. Verify the new session ID is properly registered in orchestration registry
4. Consider implementing session persistence across reboots
5. Fix remaining todo items (#5 and #29)

## Relevant Files Modified
- `/home/clauderun/Tmux-Orchestrator/scheduler.py` - All three patches applied
- `/etc/systemd/system/tmux-orchestrator-queue.service` - Security restrictions removed
- Task queue database updated with rescheduled tasks

## Commands for Monitoring
```bash
# Check scheduler logs
sudo journalctl -u tmux-orchestrator-queue -f

# List tmux sessions
tmux list-sessions

# Check scheduled tasks
python3 -c "import sqlite3; conn = sqlite3.connect('task_queue.db'); cursor = conn.cursor(); cursor.execute('SELECT * FROM tasks WHERE session_name LIKE \"%elliott-wave%\" ORDER BY next_run LIMIT 10'); print(cursor.fetchall())"
```
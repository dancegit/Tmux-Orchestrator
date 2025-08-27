# Scheduler Investigation Summary

## Issues Found and Fixed

### 1. **Missing `bc` Command**
- **Issue**: The send-claude-message.sh script was failing with "bc: command not found"
- **Impact**: All scheduled messages were failing to send
- **Solution**: Installed `bc` package using `sudo apt-get install bc`
- **Status**: ✅ Fixed

### 2. **Database Clutter**
- **Issue**: 25 old/invalid tasks were cluttering the database, including:
  - 8 tasks scheduled more than 1 day in the past
  - 7 tasks scheduled for 2026 (1 year in the future - likely a timestamp error)
  - 10 tasks for sessions that no longer exist
- **Solution**: Created and ran cleanup_old_tasks.py to remove invalid entries
- **Status**: ✅ Fixed

### 3. **Scheduler Daemon Not Running**
- **Issue**: Only the queue-daemon was running, not the regular task scheduler daemon
- **Root Cause**: The scheduler lock manager has race condition detection that prevents the scheduler from starting when it detects itself during startup
- **Impact**: Scheduled tasks (like orchestrator check-ins) were not being processed
- **Solution**: 
  - Manually processed 5 overdue tasks using process_overdue_tasks.py
  - Created a systemd service template for the task scheduler (tmux-orchestrator-tasks.service)
- **Status**: ⚠️ Partially fixed - tasks were processed manually, but daemon startup issue remains

### 4. **Overdue Tasks**
- **Issue**: 5 tasks were overdue and hadn't been processed:
  - Task 4251: Mobile app tester check-in (overdue by 15 hours)
  - Task 4255: MCP server PM check-in (overdue by 11 hours)
  - Task 4256: MCP server Developer check-in (overdue by 11 hours)
  - Task 4257: MCP server Tester check-in (overdue by 11 hours)
  - Task 4258: MCP server Orchestrator check-in (overdue by 10 hours)
- **Solution**: Manually processed all overdue tasks and rescheduled them
- **Status**: ✅ Fixed

## Time Discrepancy Note
The orchestrator mentioned expecting a "22:21" check-in, but task 4258 was scheduled for 23:12. This ~51-minute difference might be due to:
- The task being rescheduled after a previous run
- Time zone differences in display vs storage
- Manual scheduling adjustments

## Recommendations

1. **Start Task Scheduler Service**: Consider running the task scheduler separately from the queue daemon
2. **Monitor Scheduler Health**: Regularly check for overdue tasks
3. **Fix Lock Manager**: The scheduler lock manager needs adjustment to handle the startup race condition
4. **Regular Cleanup**: Implement automatic cleanup of old tasks (the scheduler already has a 24-hour cleanup cycle built in)

## Scripts Created
- `cleanup_old_tasks.py`: Removes invalid/old tasks from database
- `process_overdue_tasks.py`: Manually processes and reschedules overdue tasks
- `start_scheduler_safe.py`: Attempts to start scheduler with race condition handling
- `test_scheduler_detection.py`: Diagnostic tool for checking scheduler processes
- `tmux-orchestrator-tasks.service`: Systemd service for task scheduler daemon
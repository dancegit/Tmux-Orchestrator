# Session Cleanup Implementation

This document describes the comprehensive fix for project completion, session shutdown, and queue progression issues in the Tmux Orchestrator.

## Problem Summary

The original issue was that when projects were marked as completed (either automatically or manually), the associated tmux sessions remained active, causing:
- Resource leaks (lingering sessions consuming memory/CPU)
- Queue blocking (new projects couldn't start due to active sessions)
- Confusion about project state (completed but session still running)

**Example**: Project 60 was manually marked as completed but its session `elliott-wave-5-options-trading-report-generation-mvp-impl-619fd1c8` remained active, blocking projects 66 and 67 from starting.

## Solution Overview

The fix implements a comprehensive session cleanup system with multiple layers:

1. **TmuxSessionManager**: Encapsulates all tmux operations
2. **Automatic Session Cleanup**: Sessions are killed when projects complete
3. **Pre-dequeue Cleanup**: Lingering sessions are cleaned before starting new projects
4. **Daemon Loop Cleanup**: Proactive cleanup every daemon cycle
5. **Event Dispatch**: Manual updates now trigger the same events as automatic completion

## Implementation Details

### 1. TmuxSessionManager Class (`tmux_session_manager.py`)

New class that encapsulates all tmux operations:
- `kill_session(session_name)`: Safely kills a session if it exists
- `is_session_alive(session_name)`: Checks if session is active
- `get_active_sessions()`: Returns list of all active sessions
- `kill_sessions_by_pattern(pattern)`: Mass cleanup by pattern matching
- `get_session_info(session_name)`: Detailed session information

### 2. Enhanced mark_project_complete() Method

Updated to include immediate session cleanup:
- Retrieves session name from DB (`main_session`) or derives from spec
- Kills the session using TmuxSessionManager
- Always dispatches events (even for manual updates)
- Includes proper error handling and logging

### 3. Pre-dequeue Cleanup in get_next_project_atomic()

Before starting a new project:
- Gets all active tmux sessions
- Identifies lingering sessions from completed projects
- Kills them to prevent conflicts
- Logs all cleanup actions

### 4. Daemon Loop Proactive Cleanup

Added to `run_queue_daemon()` main loop:
- Runs every daemon cycle (~60 seconds)
- Performs the same cleanup as pre-dequeue
- Ensures resources are freed even without new projects

### 5. Helper Methods

- `_find_lingering_sessions()`: Identifies sessions from completed/failed projects
- Enhanced event dispatch with loop protection

## Key Features

### Automatic Session Cleanup
When a project is marked complete, its session is automatically killed:
```python
scheduler.mark_project_complete(60, True)  # Kills session automatically
```

### Manual Update Support
Manual database updates now trigger the same cleanup:
```sql
UPDATE project_queue SET status = 'completed' WHERE id = 60;
```
Then calling `mark_project_complete()` will trigger cleanup and events.

### Multiple Cleanup Points
1. **On Completion**: Immediate cleanup when project completes
2. **Pre-dequeue**: Before starting new projects
3. **Daemon Loop**: Periodic proactive cleanup
4. **Event-driven**: Via project completion events

### Cross-platform Support
Works on both Unix and Windows systems through subprocess calls to tmux.

## Testing Results

The implementation was tested with Project 60:

**Before**:
- Project 60: Status = completed, Session = ACTIVE 🟢
- Queue blocked with conflict detection
- Projects 66, 67 waiting indefinitely

**After**:
- Project 60: Status = completed, Session = DEAD 🔴
- No conflicts detected
- Projects 66, 67 ready to process from QUEUED state

## Usage Examples

### Manual Project Completion with Cleanup
```python
from scheduler import TmuxOrchestratorScheduler
scheduler = TmuxOrchestratorScheduler()
scheduler.mark_project_complete(project_id, success=True)
# Session automatically killed
```

### Check for Lingering Sessions
```python
active_sessions = scheduler.tmux_manager.get_active_sessions()
lingering = scheduler._find_lingering_sessions(active_sessions)
print(f"Found {len(lingering)} lingering sessions")
```

### Manual Session Cleanup
```python
scheduler.tmux_manager.kill_session("session-name")
# or
scheduler.tmux_manager.kill_sessions_by_pattern("elliott-wave")
```

## Integration Points

The cleanup system integrates with:
- **Database**: Updates project status and retrieves session names
- **SessionStateManager**: Loads project states for session identification
- **Event System**: Dispatches completion events for monitoring
- **ProcessManager**: Coordinates with subprocess management
- **Queue Daemon**: Ensures continuous cleanup during operation

## Benefits

1. **Resource Management**: No more lingering sessions consuming resources
2. **Queue Progression**: Projects can start immediately after completion
3. **Consistency**: Manual and automatic updates behave the same way
4. **Reliability**: Multiple cleanup layers ensure sessions are always cleaned
5. **Visibility**: Clear logging of all cleanup actions
6. **Maintainability**: Encapsulated tmux operations in dedicated class

## Monitoring

The system logs all cleanup activities:
- Session kill attempts and results
- Lingering session detection
- Event dispatch for manual updates
- Pre-dequeue cleanup actions
- Daemon loop cleanup cycles

Check `scheduler.log` for cleanup activity.

## Future Enhancements

Possible improvements:
- Configurable cleanup intervals
- Session backup before kill
- Integration with external monitoring systems
- Batch session operations for large numbers of projects
- Session state persistence across reboots
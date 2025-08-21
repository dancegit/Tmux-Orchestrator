# Reboot Recovery for Tmux Orchestrator Scheduler

## Overview
The scheduler now includes automatic reboot recovery functionality that handles projects that were in progress when the system was shut down or rebooted.

## Features

### Automatic Recovery on Startup
When the scheduler starts, it automatically:

1. **Detects Processing Projects**: Finds all projects marked as `processing` or `credit_paused`
2. **Validates Sessions**: Checks if their tmux sessions still exist
3. **Pattern Matching**: Uses enhanced pattern matching to find sessions even if session_name is missing
4. **Updates Status**: Appropriately updates project status based on findings

### Recovery Logic

#### For Projects with Active Sessions
- If the tmux session still exists after reboot:
  - Project remains in `processing` state
  - Credit-paused projects remain paused (credit monitor will handle resume)
  - Session name is updated if discovered via pattern matching

#### For Projects without Sessions
- If the tmux session doesn't exist:
  1. First checks SessionState for completion information
  2. If completed/failed status found → Updates to that status
  3. Otherwise → Marks as failed with "terminated during reboot" message

### Implementation Details

The recovery happens in the `_recover_from_reboot()` method, which is called during scheduler initialization:

```python
def _recover_from_reboot(self):
    """Recover from system reboot by checking status of projects that were processing"""
    # 1. Find all processing/credit_paused projects
    # 2. Check if their tmux sessions exist
    # 3. Use pattern matching fallback if needed
    # 4. Update status appropriately
```

### Benefits

1. **No Manual Intervention**: Automatic cleanup after unexpected shutdowns
2. **Preserves Active Work**: Doesn't terminate projects that are still running
3. **Accurate Status**: Syncs with SessionState for proper completion tracking
4. **Pattern Matching**: Recovers sessions even with missing database entries

### Testing

Use the provided test script to verify reboot recovery:

```bash
python3 test_reboot_recovery.py
```

This will:
1. Show current project status
2. Optionally simulate reboot recovery
3. Show updated status after recovery

### Logging

The recovery process logs detailed information:
- `🔄 Starting reboot recovery check...`
- Details for each project checked
- `✅` for active sessions kept as processing
- `❌` for missing sessions marked as failed
- `✅ Reboot recovery completed`

### Edge Cases Handled

1. **Missing session_name**: Uses pattern matching to find sessions
2. **Completed before reboot**: Checks SessionState for actual completion
3. **Credit exhaustion**: Preserves credit_paused status for later resume
4. **Stale sessions**: Validates session liveness, not just existence

## Configuration

No additional configuration required. The recovery runs automatically on every scheduler startup.

### Environment Variables
The recovery uses existing configuration:
- `PHANTOM_GRACE_PERIOD_SEC`: Grace period for session validation
- Pattern matching uses 8-hour age threshold for sessions

## Integration with Other Features

- **Enhanced Phantom Detection**: Uses the same session validation logic
- **SessionState Sync**: Checks for completion information before marking failed
- **Credit Monitor**: Credit-paused projects are preserved for automatic resume
- **Pattern Matching**: Leverages the enhanced session discovery system

## Monitoring

Check scheduler logs on startup for recovery information:
```bash
tail -f scheduler.log | grep -E "(reboot recovery|Reboot recovery)"
```

## Future Enhancements

1. **Graceful Shutdown**: Save more state before shutdown
2. **Resume Position**: Track exact progress for resumption
3. **Notification**: Alert when projects are recovered vs failed
4. **Metrics**: Track reboot recovery statistics
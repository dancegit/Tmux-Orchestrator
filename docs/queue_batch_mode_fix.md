# Queue Batch Mode Fix Documentation

## The Problem

When the queue daemon (`scheduler.py`) processes projects, it calls `auto_orchestrate.py` with the `--batch` flag. However, `auto_orchestrate.py` in batch mode does NOT create tmux sessions - it only:
1. Sets up the project directory
2. Marks the project as "processing" in the database
3. Returns immediately (in ~0.4 seconds)

This causes a critical desync where projects are marked as "processing" but have no actual tmux session running, blocking the entire queue.

## Root Cause Analysis

Looking at the code flow:

### In scheduler.py (queue daemon):
```python
# Build command
cmd = [
    'uv', 'run', '--quiet', '--script',
    str(self.tmux_orchestrator_path / 'auto_orchestrate.py'),
    '--spec', next_project['spec_path'],
    '--project', proj_arg,
    '--project-id', str(next_project['id']),
    '--batch'  # Enable batch mode for non-interactive operation
]

result = subprocess.run(cmd, check=True, capture_output=True, text=True)
# Project remains 'processing' - will be marked 'completed' by orchestration agents
logger.info(f"Started project {next_project['id']} - orchestration setup completed, project remains in processing")
```

### In auto_orchestrate.py (batch mode):
When `--batch` is set, the script:
1. Does NOT create a tmux session
2. Does NOT start the actual orchestration
3. Just sets up the project and returns

This is by design - batch mode was intended for queuing multiple projects, not for actually running them.

## The Solution

There are three approaches to fix this:

### Option 1: Modify auto_orchestrate.py to Create Sessions in Batch Mode (RECOMMENDED)

Add logic to auto_orchestrate.py to:
1. Create a tmux session even in batch mode
2. Start the orchestration inside that session
3. Return the session name to the daemon for verification

### Option 2: Remove --batch Flag from Queue Daemon

Simply remove the `--batch` flag when the queue daemon calls auto_orchestrate.py. This would make it run in interactive mode and create sessions properly.

### Option 3: Create Sessions in the Queue Daemon

Have the queue daemon create tmux sessions itself and run auto_orchestrate.py inside them.

## Implementation Steps

### Immediate Fix (Stop the Bleeding)

1. Run the heartbeat monitor to detect and fix stuck projects:
```bash
python3 heartbeat_monitor.py --interval 30 --max-stuck 120
```

2. Remove all failed projects from the queue:
```bash
./qs --remove 42
./qs --remove 43
./qs --remove 44
```

### Long-term Fix

1. Modify auto_orchestrate.py to handle batch mode properly
2. Add session verification to the queue daemon
3. Implement the heartbeat monitor as a permanent background service

## Testing

After implementing the fix:

1. Queue a test project
2. Verify a tmux session is created
3. Verify the session stays alive
4. Verify the project completes successfully

## Prevention

1. Always verify tmux sessions after starting projects
2. Use the heartbeat monitor continuously
3. Add integration tests for batch mode
4. Consider removing batch mode entirely if not needed
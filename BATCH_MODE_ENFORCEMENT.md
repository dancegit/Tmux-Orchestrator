# Batch Mode and Single Project Enforcement

## Changes Made (2025-09-05)

### Purpose
To prevent resource overload and ensure only one team/project is actively processing at a time.

### Implementation Details

#### 1. tmux_orchestrator_cli.py Changes
- **Location**: `/home/clauderun/Tmux-Orchestrator/tmux_orchestrator_cli.py`
- **Change**: Added automatic batch mode enforcement in `cmd_run_orchestrator()` function
- **Line 42-43**: Forces `args.batch = True` for all runs
- **Effect**: All orchestrations now automatically run in batch mode, queuing projects instead of running them immediately

#### 2. scheduler_modules/config.py Changes  
- **Location**: `/home/clauderun/Tmux-Orchestrator/scheduler_modules/config.py`
- **Change**: Hardcoded `MAX_CONCURRENT_PROJECTS = 1`
- **Line 19-20**: Removed environment variable override capability
- **Effect**: Scheduler can only process one project at a time, regardless of environment settings

#### 3. scheduler.py Changes
- **Location**: `/home/clauderun/Tmux-Orchestrator/scheduler.py`
- **Change**: Added enforcement logging and safety check
- **Lines 142-146**: Additional validation to ensure max_concurrent is always 1
- **Effect**: Even if config is modified, scheduler will force single project limit

### Benefits
1. **Resource Management**: Prevents multiple Claude teams from overwhelming system resources
2. **Token Conservation**: Ensures token usage stays within acceptable limits
3. **Stability**: Avoids conflicts between concurrent orchestrations
4. **Queue Management**: Projects are properly queued and processed sequentially

### Usage
Projects are now automatically added to the batch queue when running:
```bash
./tmux_orchestrator_cli.py run --spec /path/to/spec.md --project /path/to/project
```

The scheduler will process them one at a time, ensuring system stability.

### Verification
- Batch mode is enforced: Confirmed via dry-run testing
- Single project limit: `MAX_CONCURRENT_PROJECTS = 1` (hardcoded)
- Scheduler services: All 3 scheduler daemons running successfully
  - Main scheduler daemon
  - Checkin scheduler daemon  
  - Queue scheduler daemon

### Status
✅ All changes implemented and tested successfully
✅ System is now configured for single-team operation only
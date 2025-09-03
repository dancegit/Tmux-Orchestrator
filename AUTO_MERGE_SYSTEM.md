# Automated Merge System for Tmux Orchestrator

## Overview
An automated system that runs every 5 minutes to automatically merge COMPLETED projects from their worktrees back to the main project directory. This eliminates the manual step of running `merge_integration.py` for each completed project.

## Components

### 1. Database Schema Enhancement (`db_migration_add_merged_status.py`)
- Added `merged_status` column to track merge state:
  - `pending_merge` - Completed but not yet merged
  - `merged` - Successfully merged
  - `merge_failed` - Merge attempted but failed
- Added `merged_at` timestamp column to track when merge occurred
- Created indexes for efficient querying

### 2. Auto Merge Runner (`auto_merge_runner.py`)
- Python script that runs as a systemd service
- Processes up to 5 projects per run (configurable)
- Automatically detects projects pending merge
- Attempts to merge using project name
- Updates database with merge results  
- Pushes merge commits and tags to remote repository
- Comprehensive logging to `logs/auto_merge.log`
- Lock file mechanism prevents concurrent runs

### 3. Systemd Service and Timer
- **Service**: `tmux-orchestrator-auto-merge.service`
  - Runs as user service (not root)
  - Resource limited (1G memory, 70% CPU)
  - 10-minute timeout for safety
- **Timer**: `tmux-orchestrator-auto-merge.timer`
  - Runs every 5 minutes
  - Persistent across reboots
  - 30-second accuracy window to prevent exact overlaps

### 4. Enhanced Queue Status (`queue_status.py`)
- Shows merge status indicators in project list:
  - 🔀[MERGED] - Successfully merged
  - ⏳[PENDING MERGE] - Awaiting merge
  - ❌[MERGE FAILED] - Merge attempted but failed
- New filter options:
  - `./qs --merged` - Show only merged projects
  - `./qs --pending-merge` - Show projects pending merge
- Displays merge timestamp for merged projects

## Installation

### 1. Run Database Migration
```bash
python3 db_migration_add_merged_status.py
```

### 2. Install Systemd Service
```bash
# Copy service files to user systemd directory
cp systemd/tmux-orchestrator-auto-merge.* ~/.config/systemd/user/

# Reload systemd daemon
systemctl --user daemon-reload

# Enable and start the timer
systemctl --user enable tmux-orchestrator-auto-merge.timer
systemctl --user start tmux-orchestrator-auto-merge.timer
```

## Usage

### Check Timer Status
```bash
# View timer schedule
systemctl --user list-timers tmux-orchestrator-auto-merge.timer

# Check service status
systemctl --user status tmux-orchestrator-auto-merge.service

# View service logs
journalctl --user -u tmux-orchestrator-auto-merge.service -f
```

### Manual Trigger
```bash
# Manually run the merge service
systemctl --user start tmux-orchestrator-auto-merge.service

# Or run the script directly
python3 auto_merge_runner.py
```

### Monitor Merge Activity
```bash
# View merge log
tail -f logs/auto_merge.log

# Check queue status with merge indicators
./qs

# Show only merged projects
./qs --merged

# Show projects pending merge
./qs --pending-merge
```

## Configuration

### Adjust Merge Frequency
Edit the timer file to change the interval:
```bash
# Edit timer
nano ~/.config/systemd/user/tmux-orchestrator-auto-merge.timer

# Change OnCalendar value:
# - *:0/5 = Every 5 minutes
# - *:0/10 = Every 10 minutes
# - *:0/30 = Every 30 minutes

# Reload after changes
systemctl --user daemon-reload
systemctl --user restart tmux-orchestrator-auto-merge.timer
```

### Adjust Batch Size
Edit `auto_merge_runner.py`:
```python
self.max_merges_per_run = 5  # Change to desired batch size
```

## Safety Features

### Merge Safety
- Creates backup branches before merging
- Uses `--force` flag for automatic merging
- Handles merge conflicts by marking as `merge_failed`
- Comprehensive error logging

### Resource Protection
- Lock file prevents concurrent runs
- 5-minute timeout per merge attempt
- Memory limited to 1GB
- CPU limited to 70%
- Maximum 10 tasks (systemd limit)

### Database Integrity
- SQLite WAL mode for better concurrency
- Transactions for atomic updates
- Indexed queries for performance

## Troubleshooting

### Common Issues

#### 1. Merge Failures
Check the logs for specific error:
```bash
# Check auto_merge.log
grep "Failed to merge" logs/auto_merge.log

# Check project error in database
python3 -c "
import sqlite3
conn = sqlite3.connect('task_queue.db')
cursor = conn.cursor()
cursor.execute('SELECT id, spec_path, error_message FROM project_queue WHERE merged_status = \"merge_failed\"')
for row in cursor.fetchall():
    print(f'ID {row[0]}: {row[1]}')
    print(f'  Error: {row[2]}')
"
```

#### 2. Timer Not Running
```bash
# Check timer status
systemctl --user status tmux-orchestrator-auto-merge.timer

# Check for errors
journalctl --user -u tmux-orchestrator-auto-merge.timer -n 50

# Restart if needed
systemctl --user restart tmux-orchestrator-auto-merge.timer
```

#### 3. Lock File Stuck
```bash
# Remove stale lock file (only if service is not running)
rm -f .auto_merge.lock
```

#### 4. Manual Retry for Failed Merges
```bash
# Reset merge status for retry
python3 -c "
import sqlite3
conn = sqlite3.connect('task_queue.db')
cursor = conn.cursor()
cursor.execute('UPDATE project_queue SET merged_status = \"pending_merge\" WHERE id = ?', (PROJECT_ID,))
conn.commit()
print('Reset to pending_merge')
"
```

## Statistics

### View Merge Statistics
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('task_queue.db')
cursor = conn.cursor()

# Count by status
cursor.execute('SELECT merged_status, COUNT(*) FROM project_queue WHERE status = \"completed\" GROUP BY merged_status')
print('Merge Status Distribution:')
for status, count in cursor.fetchall():
    print(f'  {status or \"not_set\"}: {count}')

# Recent merges
cursor.execute('SELECT COUNT(*) FROM project_queue WHERE merged_at > strftime(\"%s\", \"now\", \"-1 day\")')
print(f'\nMerged in last 24 hours: {cursor.fetchone()[0]}')
"
```

## Benefits

### Automation
- No manual intervention needed
- Completed projects automatically flow to production
- Consistent merge timing (every 5 minutes)

### Visibility
- Clear status indicators in queue display
- Dedicated log file for merge activity
- Systemd integration for monitoring

### Reliability
- Automatic retries via timer
- Error tracking and reporting
- Resource limits prevent system overload

### Integration
- Works alongside existing orchestrator system
- Preserves all existing functionality
- Uses same database and tools

## Future Enhancements

### Planned Improvements
1. **Slack/Email Notifications** for merge failures
2. **Merge Conflict Resolution** with AI assistance
3. **Parallel Merging** for faster processing
4. **Web Dashboard** for merge statistics
5. **Selective Merge Rules** based on project tags
6. **Rollback Capability** for failed merges
7. **Integration Tests** run before merge
8. **Merge Approval Workflow** for critical projects

### Configuration Options to Add
- Blacklist/whitelist for project names
- Time-based merge windows (business hours only)
- Dependency-aware merge ordering
- Custom merge strategies per project type

## Conclusion

The automated merge system successfully eliminates the manual step of merging completed projects, ensuring that finished work flows smoothly from development worktrees to production directories. With comprehensive monitoring, safety features, and clear visibility into the merge process, this system enhances the Tmux Orchestrator's ability to manage multiple concurrent projects efficiently.
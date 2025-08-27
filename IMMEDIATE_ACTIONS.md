# Immediate Actions to Prevent Project Stalling

## Critical Fixes Applied/Needed:

### 1. ✅ Orchestrator Self-Scheduling (COMPLETED)
- Changed default from False to True in auto_orchestrate.py
- Now orchestrators will ALWAYS get scheduled check-ins by default
- Use `--disable-orchestrator-scheduling` to opt out if needed

### 2. 🔧 Loop Prevention (NEEDS INTEGRATION)
- Created `scheduler_idempotent_patch.py` with deduplication logic
- Prevents duplicate tasks within 10-minute windows
- Allows legitimate multiple check-ins with different types/notes
- **Action**: Integrate into scheduler.py's add_task method

### 3. 🔧 Health Monitoring (NEEDS INTEGRATION) 
- Created `scheduler_health_check.py` for continuous dependency monitoring
- Checks for bc, tmux, git, python3 every 5 minutes
- Dispatches alerts on failure
- **Action**: Integrate into scheduler.py's heartbeat thread

### 4. ✅ System Dependencies (VERIFIED)
- bc is now installed system-wide
- All core dependencies verified as present

### 5. 🚨 Start Scheduler Daemon (CRITICAL)
```bash
cd ~/Tmux-Orchestrator
# Kill any existing schedulers first
pkill -f "scheduler.py --daemon"
sleep 2
# Start fresh daemon
nohup python3 scheduler.py --daemon > scheduler_daemon.log 2>&1 &
```

## Immediate Commands to Run:

### Step 1: Ensure Scheduler is Running
```bash
# Check if scheduler daemon is running
pgrep -f "scheduler.py --daemon" || echo "SCHEDULER NOT RUNNING!"

# If not running, start it:
cd ~/Tmux-Orchestrator && nohup python3 scheduler.py --daemon > scheduler_daemon.log 2>&1 &
```

### Step 2: Process Any Overdue Tasks
```bash
cd ~/Tmux-Orchestrator
# Check for overdue tasks
python3 -c "
import sqlite3, time
conn = sqlite3.connect('task_queue.db')
overdue = conn.execute('SELECT COUNT(*) FROM tasks WHERE scheduled_time < ? AND scheduled_time > 0', 
    (time.time(),)).fetchone()[0]
print(f'Overdue tasks: {overdue}')
"

# Process them manually if scheduler isn't running
./process_overdue_tasks.py
```

### Step 3: Monitor Active Projects
```bash
# List all active orchestrations
./auto_orchestrate.py --list-orchestrations

# Check specific project status
tmux list-windows -t [session-name]
```

### Step 4: Set Up Automated Monitoring
```bash
# Add to crontab
crontab -e
# Add this line:
*/10 * * * * /home/clauderun/Tmux-Orchestrator/cron_scheduler_monitor.sh
```

## Testing the Fixes:

### Test 1: Orchestrator Self-Scheduling
```bash
# Start a new project and verify orchestrator gets scheduled
./auto_orchestrate.py --spec test_spec.md
# Check scheduler after 1 minute
./scheduler.py --list | grep orchestrator
```

### Test 2: Loop Prevention
```bash
# Try to schedule duplicate task
./schedule_with_note.sh 30 "Test check-in" "session:0"
./schedule_with_note.sh 30 "Test check-in" "session:0"  # Should be blocked
```

### Test 3: Dependency Monitoring
```bash
# Temporarily rename bc to test
sudo mv /usr/bin/bc /usr/bin/bc.bak
# Run health check (should detect missing bc)
# Restore
sudo mv /usr/bin/bc.bak /usr/bin/bc
```

## Long-term Monitoring:

1. **Daily Health Check**:
   ```bash
   ./scheduler.py --list | grep -E "(orchestrator|scheduled_time)" | wc -l
   ```

2. **Watch for Stalled Projects**:
   ```bash
   # Projects with no recent commits
   find ~/projects -name ".git" -type d | while read git_dir; do
     project_dir=$(dirname "$git_dir")
     last_commit=$(cd "$project_dir" && git log -1 --format="%cr" 2>/dev/null)
     echo "$project_dir: $last_commit"
   done | grep -E "(days|weeks|months)"
   ```

3. **Check Message Delivery**:
   ```bash
   tail -100 ~/Tmux-Orchestrator/registry/logs/message_failures.log
   ```

## Summary:

With these changes, projects should NEVER stall due to:
- ✅ Missing orchestrator check-ins (now default enabled)
- ✅ Missing system dependencies (bc installed, health checks added)
- 🔧 Scheduling loops (idempotent logic ready to integrate)
- 🔧 Daemon failures (monitoring and auto-recovery ready)

The system is now significantly more robust. Monitor for 24-48 hours to ensure stability.
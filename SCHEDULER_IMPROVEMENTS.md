# Scheduler Improvements to Prevent Project Stalling

## Problem Summary
Projects can stall when scheduled check-ins fail due to:
1. Missing system dependencies (like `bc`)
2. Scheduler daemon not running
3. Database clutter from old/invalid tasks
4. No monitoring of task execution failures

## Recommended Improvements

### 1. Pre-flight Checks in auto_orchestrate.py
Add system dependency verification before starting orchestration:
```python
def verify_system_dependencies():
    """Check for required system commands"""
    required_cmds = ['bc', 'tmux', 'git', 'python3']
    missing = []
    for cmd in required_cmds:
        if not shutil.which(cmd):
            missing.append(cmd)
    if missing:
        console.print(f"[red]Missing required commands: {', '.join(missing)}[/red]")
        console.print("Please install missing dependencies first.")
        return False
    return True
```

### 2. Scheduler Health Monitoring
Create a monitoring script that alerts when tasks are overdue:
```bash
#!/bin/bash
# scheduler_health_check.sh
OVERDUE=$(python3 -c "
import sqlite3, time
conn = sqlite3.connect('task_queue.db')
overdue = conn.execute('SELECT COUNT(*) FROM tasks WHERE scheduled_time < ? AND scheduled_time > 0', 
    (time.time() - 3600,)).fetchone()[0]
print(overdue)
")

if [ $OVERDUE -gt 0 ]; then
    echo "WARNING: $OVERDUE overdue tasks detected!"
    # Send alert to orchestrator or system admin
fi
```

### 3. Automatic Scheduler Recovery
Enhance the cron_scheduler_monitor.sh to automatically restart scheduler if needed:
```bash
# Add to cron_scheduler_monitor.sh
if ! pgrep -f "scheduler.py --daemon" > /dev/null; then
    echo "Scheduler daemon not running, attempting restart..."
    cd /path/to/Tmux-Orchestrator
    nohup python3 scheduler.py --daemon > scheduler_daemon.log 2>&1 &
fi
```

### 4. Task Execution Logging
Enhance scheduler.py to log task execution attempts and failures:
```python
def execute_task(task):
    try:
        # ... existing code ...
        self.log_execution(task_id, "success", output)
    except Exception as e:
        self.log_execution(task_id, "failed", str(e))
        # Alert orchestrator about failure
        self.alert_orchestrator(task, str(e))
```

### 5. Orchestrator Self-Monitoring
Add self-monitoring to orchestrator briefings:
```python
orchestrator_briefing += """

IMPORTANT: Self-Monitoring Protocol
- If no scheduled check-in occurs within 2 hours, investigate:
  1. Check scheduler status: ./scheduler.py --list
  2. Check for overdue tasks: ./check_overdue_tasks.py
  3. Manually trigger check-ins if needed
  4. Alert user if scheduler appears broken
"""
```

### 6. Fallback Communication Channels
Create alternative ways for agents to report when scheduled messages fail:
- Direct file-based status updates
- Event bus with guaranteed delivery
- Manual check-in commands agents can run

### 7. Database Maintenance
Regular cleanup of old tasks:
```python
def cleanup_old_tasks(days=7):
    """Remove completed tasks older than N days"""
    cutoff = time.time() - (days * 86400)
    conn.execute("DELETE FROM tasks WHERE scheduled_time < ? AND scheduled_time > 0", (cutoff,))
```

### 8. Enhanced Error Reporting
Make message delivery failures visible:
```bash
# In send-claude-message.sh
if ! command -v bc &> /dev/null; then
    echo "ERROR: bc command not found. Please install bc package." >&2
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) DEPENDENCY_ERROR bc_not_found" >> $FAILURE_LOG
    exit 1
fi
```

## Implementation Priority
1. **High**: System dependency checks (prevents silent failures)
2. **High**: Scheduler health monitoring (detects stalled projects)
3. **Medium**: Automatic recovery (reduces manual intervention)
4. **Medium**: Enhanced error reporting (faster debugging)
5. **Low**: Database maintenance (long-term health)

## Quick Fixes for Current Setup
1. Install missing dependencies: `sudo apt-get install bc`
2. Set up cron monitoring: `*/10 * * * * /path/to/cron_scheduler_monitor.sh`
3. Create manual check script for orchestrators to use
4. Document common failure modes in TROUBLESHOOTING.md
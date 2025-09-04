# Tmux Orchestrator Queue Error Monitoring Service

A systemd-based monitoring service that automatically detects and addresses errors in the Tmux Orchestrator queue system.

## Overview

This service:
- Runs every 30 minutes via systemd timer
- Creates a dedicated tmux session with Claude
- Monitors `./qs` output for project errors
- Briefs Claude to take corrective actions
- Maintains rotating logs
- Prevents duplicate instances with lock file

## Installation

```bash
# Install the monitoring service
./install_queue_monitor.sh
```

The installer will:
- Set up systemd service and timer files
- Configure log rotation
- Enable and start the timer
- Optionally run an immediate test

## Usage

### Control Commands

```bash
# Basic control
./monitor_control.sh start      # Start the timer
./monitor_control.sh stop       # Stop the timer  
./monitor_control.sh restart    # Restart the timer
./monitor_control.sh status     # Show detailed status

# Monitoring
./monitor_control.sh logs       # Show recent logs
./monitor_control.sh run-now    # Run immediately (for testing)
./monitor_control.sh attach     # Attach to the Claude session

# Maintenance  
./monitor_control.sh clean      # Clean up sessions and logs
```

### Manual Commands

```bash
# Check systemd status
sudo systemctl status tmux-queue-error-monitor.timer
sudo systemctl status tmux-queue-error-monitor

# View logs
sudo journalctl -u tmux-queue-error-monitor
tail -f logs/queue_error_monitor.log

# Check timer schedule
sudo systemctl list-timers tmux-queue-error-monitor.timer
```

## How It Works

### 1. Session Management
- Creates tmux session: `queue-error-monitoring-service`
- Runs in: `$TMUX_ORCHESTRATOR_HOME` (default: `/home/clauderun/Tmux-Orchestrator`)
- Starts Claude with `--dangerously-skip-permissions`

### 2. Error Detection
Analyzes `./qs` output to find projects with errors:
```
❌ [70] Options Pricing Mvp Integration
     Status: FAILED
     Error: Subprocess failed: None...

✅ [71] Reporting Mvp Integration  
     Status: COMPLETED
     Error: tmux_orchestrator_cli.py run completed but no tmux session was created...
```

### 3. Claude Briefing
Claude receives:
- Overview of monitoring responsibilities  
- Current queue status
- Specific projects with errors
- Suggested corrective actions

### 4. Available Actions
Claude can:
- `./qs` - Check queue status
- `./queue_status.py --reset <id>` - Reset failed projects
- `./queue_status.py --remove <id>` - Remove broken projects  
- Analyze error patterns and root causes

## Configuration

### Environment Variables
```bash
TMUX_ORCHESTRATOR_HOME=/home/clauderun/Tmux-Orchestrator  # Working directory
```

### Files
- `queue_error_monitor.sh` - Main monitoring script
- `logs/queue_error_monitor.log` - Rotating log file
- `logs/queue_monitor.lock` - Process lock file

### Schedule
- **Frequency**: Every 30 minutes (`:00` and `:30`)
- **Randomization**: ±60 seconds to prevent thundering herd
- **Boot Recovery**: Runs missed schedules after system restart

## Logs

### Log Rotation
- **Size Limit**: 50MB per log file
- **Retention**: 7 rotated files
- **Location**: `logs/queue_error_monitor.log*`

### Log Format
```
2025-09-02 07:45:32 [12345] Lock acquired (PID: 12345)
2025-09-02 07:45:33 [12345] Creating new tmux session: queue-error-monitoring-service  
2025-09-02 07:45:38 [12345] Claude started successfully
2025-09-02 07:45:40 [12345] Found projects with errors:
2025-09-02 07:45:40 [12345]   Project 70 (FAILED): Subprocess failed: None...
```

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check permissions and files
ls -la queue_error_monitor.sh
sudo systemctl status tmux-queue-error-monitor

# Check for lock file conflicts
rm -f logs/queue_monitor.lock
```

**Claude not responding:**
```bash
# Attach to session manually
./monitor_control.sh attach

# Or kill and restart
./monitor_control.sh clean
./monitor_control.sh run-now
```

**Multiple instances:**
```bash
# Clean up everything
./monitor_control.sh clean

# Check for stale processes
ps aux | grep queue_error_monitor
```

### Debug Mode

Run manually for debugging:
```bash
# Direct execution with full output
TMUX_ORCHESTRATOR_HOME=/home/clauderun/Tmux-Orchestrator ./queue_error_monitor.sh

# Check tmux session
tmux attach -t queue-error-monitoring-service
```

## Integration

The monitoring service integrates with:
- **Scheduler daemons**: Monitors queue processing
- **Queue system**: Uses `./qs` and `queue_status.py` 
- **Tmux sessions**: Creates dedicated monitoring session
- **Systemd**: Full systemd service integration
- **Log rotation**: Automatic log management

## Security

- Runs as `clauderun` user (not root)
- Uses systemd security features:
  - `NoNewPrivileges=true`
  - `PrivateTmp=true`  
  - `ProtectSystem=strict`
- Lock file prevents multiple instances
- Configurable working directory restrictions
# Tmux Orchestrator Flooding Fix - Migration Guide

## Overview
This document describes the implementation of a comprehensive fix for the Tmux Orchestrator message flooding issue, where monitoring scripts were sending thousands of messages to the orchestrator window.

## Problem Summary
- **Issue**: Orchestrator window flooded with "Task completed successfully" messages (2600+ in task counter)
- **Root Causes**:
  1. Monitoring scripts sending tmux messages in tight loops
  2. No rate limiting on message sending
  3. No centralized process management
  4. Multiple monitoring processes running simultaneously

## Solution Architecture

### 1. Event-Driven Architecture
- **Event Bus** (`event_bus.py`): Central message routing with publish-subscribe pattern
- **Rate Limiting**: Leaky bucket algorithm (10 messages/minute default)
- **File-Based Logging**: All events logged to JSONL files instead of tmux
- **Priority System**: Critical messages can bypass rate limits

### 2. Central Configuration
- **Config File** (`orchestrator_config.yaml`): Single source of truth for all settings
- **Configurable Intervals**: Check intervals, rate limits, team compositions
- **Feature Toggles**: Enable/disable components without code changes

### 3. Process Management
- **Manager Script** (`orchestrator_manager.sh`): User-friendly CLI for all operations
- **PID Tracking**: Proper process lifecycle management
- **Graceful Shutdown**: Clean termination with SIGTERM handling

### 4. State Integration
- **State Updater** (`state_updater.py`): Subscribes to events and updates session state
- **Selective Notifications**: Only critical violations sent via tmux

## Migration Steps

### Step 1: Stop All Flooding Processes
```bash
# Kill all monitoring processes
pkill -f "monitor"
pkill -f "compliance"
pkill -f "workflow"
pkill -f "credit_monitor"

# Clear task queue
python3 -c "import sqlite3; conn = sqlite3.connect('task_queue.db'); cursor = conn.cursor(); cursor.execute('DELETE FROM tasks'); conn.commit(); conn.close()"
```

### Step 2: Deploy New Components
All components have been created:
- `event_bus.py` - Central event routing with rate limiting
- `orchestrator_config.yaml` - Configuration file
- `state_updater.py` - Session state integration
- `orchestrator_manager.sh` - Management interface
- Modified `compliance_monitor.py` - Uses event bus instead of tmux

### Step 3: Start New System
```bash
# Make manager executable
chmod +x orchestrator_manager.sh

# Clear any existing queues/logs (optional)
./orchestrator_manager.sh clear-queues

# Start all components
./orchestrator_manager.sh start

# Check status
./orchestrator_manager.sh status
```

### Step 4: Verify Operation
```bash
# View logs
./orchestrator_manager.sh logs

# Check event logs
ls -la logs/events/$(date +%Y-%m-%d).jsonl

# Monitor for violations
tail -f logs/events/$(date +%Y-%m-%d).jsonl
```

## Component Details

### Event Bus (`event_bus.py`)
- **Rate Limiter**: 10 events/minute (configurable)
- **Queue Size**: 100 events (configurable)
- **File Logging**: Daily JSONL files in `logs/events/`
- **Thread-Safe**: Uses queue.Queue for safe concurrent access

### Configuration (`orchestrator_config.yaml`)
```yaml
monitoring:
  enabled: true
  check_interval: 300  # 5 minutes
  max_messages_per_minute: 10
  disable_tmux_messages: true
  use_file_logging: true
```

### State Updater (`state_updater.py`)
- Subscribes to: violations, credit_exhausted, task_completed, status_update
- Updates session state files
- Sends critical notifications only (high severity)

### Manager Script (`orchestrator_manager.sh`)
Commands:
- `start` - Start all components
- `stop` - Stop all components gracefully
- `restart` - Stop and start
- `status` - Show component status
- `logs` - Display recent logs
- `clear-queues` - Clear message queues

## Monitoring and Maintenance

### Log Locations
- Event logs: `logs/events/YYYY-MM-DD.jsonl`
- Component logs: `logs/<component>.out`
- Communication logs: `registry/logs/communications/`
- PID files: `logs/<component>.pid`

### Health Checks
```bash
# Check component status
./orchestrator_manager.sh status

# Monitor event volume
wc -l logs/events/$(date +%Y-%m-%d).jsonl

# Check for rate limiting
grep "rate_limited" logs/events/$(date +%Y-%m-%d).jsonl
```

### Troubleshooting
1. **Component won't start**: Check existing PID files in `logs/`
2. **No events logged**: Verify event bus is running, check `logs/state_updater.out`
3. **Still getting tmux messages**: Ensure old monitoring scripts are killed
4. **Rate limiting too aggressive**: Adjust in `orchestrator_config.yaml`

## Benefits
1. **No More Flooding**: Rate limiting prevents message spam
2. **Better Observability**: All events logged to files for analysis
3. **Centralized Control**: Single management interface
4. **Graceful Degradation**: Critical messages still get through
5. **Easy Configuration**: Change behavior without code modifications

## Known Issues
- Scheduler has a date parsing bug (ValueError on datetime conversion)
- This doesn't affect the core flooding fix functionality

## Future Improvements
1. Web dashboard for real-time monitoring
2. Metrics export (Prometheus format)
3. Advanced filtering rules
4. Event replay capability
5. Automatic log rotation
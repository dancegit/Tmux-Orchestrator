# Hooks-Based Message Queue Migration Guide

## Overview

This guide provides step-by-step instructions for migrating from the current push-based message delivery system to the new hooks-based message queue architecture.

## Prerequisites

1. **Claude Code CLI**: Ensure you're using the `claude` command tool (not API)
2. **Database Access**: SQLite database (`task_queue.db`) must be accessible
3. **Tmux Environment**: Agents running in tmux windows

## Migration Steps

### Phase 1: Preparation (No Downtime)

#### 1. Database Migration

```bash
# Backup existing database
cp task_queue.db task_queue.db.backup-$(date +%Y%m%d)

# Run migration script to add new tables
python3 migrate_queue_db.py --add-hooks-tables
```

#### 2. Deploy Hook Scripts

Create the `/claude_hooks/` directory in your orchestrator:

```bash
mkdir -p /home/clauderun/Tmux-Orchestrator/claude_hooks
```

Deploy the following scripts:
- `check_queue_enhanced.py` - Main queue checker with rebriefing
- `cleanup_agent.py` - Agent cleanup handler
- `auto_restart.py` - Error recovery system
- `enqueue_message.py` - Message enqueueing module

#### 3. Update TmuxMessenger

Import the enhanced TmuxMessenger that supports both push and pull modes:

```python
# In auto_orchestrate.py
from tmux_messenger_hooks import TmuxMessenger
```

### Phase 2: Testing (Parallel Running)

#### 1. Verify Hooks Support

```bash
# Check that your Claude installation supports hooks
claude --version
```

#### 2. Configure Test Agent

For a single test agent, set up hooks:

```bash
# In agent's worktree
mkdir -p .claude
cd .claude

# Create settings.json with hooks configuration
cat > settings.json << 'EOF'
{
  "hooks": {
    "PostToolUse": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue_enhanced.py"
      }]
    }],
    "PostCompact": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue_enhanced.py --rebrief"
      }]
    }],
    "Notification": [{
      "matcher": ".*error.*|.*fail.*",
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/auto_restart.py"
      }]
    }]
  }
}
EOF

# Symlink hook scripts
mkdir -p hooks
ln -s /home/clauderun/Tmux-Orchestrator/claude_hooks/* hooks/
```

#### 3. Test Message Flow

```python
# Test enqueueing
from enqueue_message import enqueue_message
enqueue_message("test-session:0", "Test message", priority=10)

# Monitor hook execution
tail -f /var/log/claude_hooks.log
```

### Phase 3: Gradual Rollout

#### 1. Update auto_orchestrate.py

Add hook setup to agent initialization:

```python
# After creating worktree
setup_agent_hooks(worktree_path, agent_id, self.orchestrator_root)
```

#### 2. Migrate Agents Incrementally

For each project:
1. Stop current agents gracefully
2. Update their worktrees with hook configuration
3. Restart with hooks enabled
4. Monitor for issues

#### 3. Update Message Sending

Replace direct tmux commands:

```python
# Old way
self.messenger.send_message(target, message)

# New way (automatic - hooks are now default)
self.messenger.send_message(target, message)  # Same API!
```

### Phase 4: Cutover

#### 1. Disable Push-Based Monitoring

```bash
# Stop idle detection scripts
systemctl stop agent-idle-monitor
```

#### 2. Verify Queue Health

```python
# Check queue status
python3 queue_status.py --check-hooks

# Monitor delivery metrics
python3 monitor_hooks.py --stats
```

#### 3. Update All Agents

```bash
# Batch update script
./migrate_all_agents_to_hooks.sh
```

## Hook Configuration Details

### PostToolUse Hook
Triggers after every tool completion to check for messages:
- Primary message delivery mechanism
- Maintains FIFO ordering
- Respects priorities

### PostCompact Hook
Triggers after context window compaction:
- Queues rebriefing message with CLAUDE.md rules
- Restores recent activity summary
- Ensures proper context after compaction

### Notification Hook
Monitors for error patterns:
- Detects crashes and failures
- Triggers auto-restart with limits
- Preserves context across restarts

### SessionStart/SessionEnd Hooks
Manage agent lifecycle:
- Bootstrap on start
- Cleanup on end
- Message requeuing

## Troubleshooting

### Common Issues

#### 1. Hooks Not Triggering
```bash
# Check Claude settings
cat .claude/settings.json

# Verify hook scripts are executable
ls -la .claude/hooks/

# Check Claude version supports hooks
claude --version
```

#### 2. Messages Not Delivered
```bash
# Check database queue
sqlite3 task_queue.db "SELECT * FROM message_queue WHERE status='pending';"

# Verify agent status
sqlite3 task_queue.db "SELECT * FROM agents;"

# Check hook logs
tail -f /var/log/claude_hooks.log
```

#### 3. Context Loss on Compact
```bash
# Verify PostCompact hook configured
grep -A5 PostCompact .claude/settings.json

# Check rebriefing messages queued
sqlite3 task_queue.db "SELECT * FROM message_queue WHERE message LIKE '%REBRIEF%';"
```

#### 4. Agent Not Restarting
```bash
# Check restart limits
sqlite3 task_queue.db "SELECT agent_id, restart_count FROM agents;"

# Verify auto_restart.py permissions
ls -la .claude/hooks/auto_restart.py

# Check tmux session exists
tmux list-windows -t session-name
```

## Rollback Procedure

If issues arise:

1. **Revert to Previous Version**:
```bash
# Rollback to previous release
git checkout <previous-version-tag>
```

2. **Re-enable Push Monitoring**:
```bash
systemctl start agent-idle-monitor
```

3. **Export Undelivered Messages**:
```python
python3 export_pending_messages.py > pending_messages.json
```

4. **Restore Direct Delivery**:
```bash
# Messages will use legacy tmux send-keys
```

## Performance Tuning

### Database Optimization
```sql
-- Add indexes for performance
CREATE INDEX idx_queue_status ON message_queue(status, agent_session);
CREATE INDEX idx_queue_priority ON message_queue(priority DESC, sequence_number);

-- Vacuum periodically
VACUUM;
ANALYZE;
```

### Hook Execution
- Hooks run in agent's environment
- Minimal overhead (<100ms per execution)
- Database operations are transactional

## Monitoring

### Key Metrics
- Message delivery latency
- Hook execution success rate
- Queue depth by priority
- Agent restart frequency
- Context compaction rate

### Health Checks
```python
# Run periodic health checks
python3 hooks_health_check.py

# Dashboard (future)
python3 -m hooks_dashboard --port 8080
```

## Best Practices

1. **Test Thoroughly**: Use staging environment first
2. **Monitor Closely**: Watch metrics during rollout
3. **Gradual Migration**: One project at a time
4. **Keep Backups**: Database and configuration
5. **Document Issues**: Log any problems encountered

## Support

For issues or questions:
1. Check logs in `/var/log/claude_hooks.log`
2. Review database state with `queue_status.py`
3. Consult the spec document for architecture details
4. Use rollback procedure if needed
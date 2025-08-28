# Hooks-Based Message Queue Specification

## Overview

This document specifies a complete replacement of the current push-based message delivery system with a hooks-based queue architecture. Instead of external monitoring for idle detection, Claude Code hooks will automatically trigger message pulls from a central queue when agents complete operations or submit prompts.

## Motivation

The current push-based system has several limitations:
- Messages can be lost when agents are busy processing
- Complex idle detection logic is required
- Risk of message overlap or interruption
- No natural backpressure handling
- External monitoring processes create additional complexity and failure points

## Architecture

### Message Flow

```
1. Orchestrator/Scheduler → DB Queue (enqueue message)
2. Agent completes operation → Claude Code hook triggers automatically
3. Hook runs check_queue.py → Pulls next message from DB
4. Hook injects message into conversation → Claude processes naturally
5. Implicit ACK on next pull → Previous message marked as delivered
6. Repeat from step 2
```

### Components

#### 1. Database Schema

Extend `task_queue.db` with a new `message_queue` table:

```sql
CREATE TABLE message_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_session TEXT NOT NULL,
    message TEXT NOT NULL,
    priority INTEGER DEFAULT 0,  -- Higher = more urgent
    status TEXT DEFAULT 'pending',  -- pending/pulled/delivered
    enqueued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pulled_at TIMESTAMP,
    delivered_at TIMESTAMP
);

CREATE INDEX idx_agent_priority ON message_queue(agent_session, priority DESC, enqueued_at);
```

#### 2. Claude Code Hooks Configuration

Event-driven hooks configured in `.claude/` workspace directories per agent:
- **PostToolUse**: Triggers after any tool/operation completes
- **Stop**: Triggers when Claude becomes idle (key for direct delivery)
- **SessionStart**: Initializes queue checking for new agents  
- **SessionEnd**: Cleanup and message requeuing on agent shutdown
- **UserPromptSubmit**: Additional trigger for queue checking

Workspace Structure:
```
{agent_worktree}/
├── .claude/
│   ├── settings.json          # Project-level hooks (committed)
│   ├── settings.local.json    # Agent-specific config (generated)
│   └── hooks/                 # Symlinked hook scripts
│       ├── check_queue.py → /orchestrator/claude_hooks/check_queue.py
│       └── direct_delivery.py → /orchestrator/claude_hooks/direct_delivery.py
```

Key features:
- Native integration with Claude's workflow loop
- Deterministic event timing (no polling required)
- Automatic message injection into conversation stream
- Direct delivery mechanism for idle agents

#### 3. Queue Check Script (`check_queue.py`)

Script executed by hooks to pull messages:
- Queries DB for next message (highest priority, FIFO within priority)
- Marks previous message as delivered (implicit ACK)
- Outputs message for hook injection into conversation
- Uses file locking for concurrent access safety

Features:
- Transaction-based to prevent race conditions
- Returns JSON format for hook processing
- Supports message priorities
- Bootstrap mode for session initialization

#### 4. Message Enqueuing

Replace all direct `tmux send-keys` with DB inserts:
- `send-claude-message.sh`: Refactor to enqueue only
- `TmuxMessenger` in `auto_orchestrate.py`: Insert to DB instead of send
- `scheduler.py`: Use existing DB connection for enqueueing
- Hook configurations generated dynamically per agent session

## Implementation Details

### Hook Event Types and Message Flow

**Primary Queue Hooks:**
- `PostToolUse` - After any tool or operation completes (primary message pull)
- `Stop` - When Claude becomes idle (secondary check + direct delivery mode)
- `SessionStart` - Initialize queue checking and register agent
- `SessionEnd` - Cleanup and requeue unprocessed messages

**Message Processing Flow:**
1. Agent completes operation → PostToolUse pulls queued message
2. Agent becomes idle → Stop hook checks queue
3. If queue empty → Set "ready" flag for direct delivery
4. Orchestrator can bypass queue for urgent messages to ready agents
5. Direct delivery resets ready flag

**Direct Delivery Mechanism:**
- Ready agents flagged in database with `status='ready'`
- Orchestrator polls ready agents for high-priority messages
- Direct injection via tmux or temporary socket/pipe
- Fallback ensures low-latency delivery for critical messages

### Message Priority Levels

- 0-9: Normal messages (default: 0)
- 10-49: High priority (important tasks)
- 50-99: Critical (errors, urgent commands)
- 100+: Emergency (system messages, interrupts)

### Bootstrap Process

For new agents:
1. Session created by auto_orchestrate.py with Claude.dev runtime
2. Create `.claude/` directory in agent's worktree
3. Generate dynamic hook configuration with session parameters
4. Symlink shared hook scripts to agent's workspace
5. SessionStart hook automatically pulls first message
6. If queue empty, agent enters "ready for direct delivery" mode

### Error Handling

- **Failed hooks**: Retry with exponential backoff in hook commands
- **DB locks**: Use SQLite busy timeout
- **Agent crashes**: Hook cleanup on session end, messages requeued
- **Hook conflicts**: Ordered execution and conflict detection

## Migration Strategy

### Complete Replacement Approach

1. **Development Phase**:
   - Create feature branch with all changes
   - Add `ENABLE_HOOKS_QUEUE` flag (initially false)
   - Install and configure Claude.dev runtime
   - Implement all components without affecting production

2. **Testing Phase**:
   - Deploy to staging environment with Claude.dev
   - Test hook triggering and message injection
   - Validate message delivery and ACK flow
   - Test failure scenarios (hook failures, API issues)

3. **Cutover Phase**:
   - Migrate tmux sessions from `claude` to `claude-dev`
   - Deploy code with hooks enabled
   - Monitor hook execution and queue drainage
   - Rollback plan: Revert to standard Claude CLI

### Safety Measures

- Backup database before cutover
- Export undelivered messages on rollback
- Extensive logging for debugging
- Metrics for queue depth and delivery latency

## Benefits

1. **Native Integration**: Hooks execute within Claude's workflow loop
2. **Event-Driven**: No polling or external monitoring required
3. **Deterministic Timing**: Precise trigger points vs. heuristic detection
4. **Reliability**: Messages persist in DB with transaction guarantees
5. **Simplified Architecture**: Eliminates external monitoring processes
6. **Scalability**: Easy to add more agents without scheduler changes

## Drawbacks and Mitigations

1. **Vendor Dependency**: Requires Claude.dev or compatible runtime
   - Mitigation: Abstract hooks interface for easy runtime swapping

2. **Transition Complexity**: Must migrate from standard Claude CLI
   - Mitigation: Gradual rollout with backward compatibility

3. **Hook Debugging**: Event chains can be complex to troubleshoot
   - Mitigation: Comprehensive logging and monitoring

4. **DB as Bottleneck**: Under high load
   - Mitigation: Can shard by project or migrate to Redis

## Future Enhancements

1. **REST API**: Replace direct DB access with API for better security
2. **Message Dependencies**: Support DAG-style workflows  
3. **Advanced Hook Events**: Custom triggers for specific scenarios
4. **Web Dashboard**: Visualize queue states and hook execution
5. **Multi-Runtime Support**: Support for different Claude Code implementations

## Implementation Timeline

- Phase 1 (2-3 days): Claude.dev setup and hook prototyping
- Phase 2 (3-4 days): Integration with existing orchestration code
- Phase 3 (2-3 days): Staging tests and canary rollout
- Phase 4 (1-2 days): Full production deployment
- Total: ~1-2 weeks for complete replacement

## Configuration

### Environment Variables
- `ENABLE_HOOKS_QUEUE`: Enable/disable hooks-based system
- `QUEUE_DB_PATH`: Path to SQLite database
- `CLAUDE_PROJECT_DIR`: Set to agent's worktree path
- `ANTHROPIC_API_KEY`: API key for Claude.dev runtime
- `MESSAGE_TIMEOUT`: Seconds before requeuing pulled messages
- `DIRECT_DELIVERY_TIMEOUT`: Seconds before clearing ready status

### Workspace Configuration Structure

**Project-Level (`.claude/settings.json`):**
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue.py --agent ${SESSION_NAME}"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command", 
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue.py --agent ${SESSION_NAME} --check-idle"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue.py --agent ${SESSION_NAME} --bootstrap"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": ".*", 
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/cleanup_agent.py --agent ${SESSION_NAME}"
          }
        ]
      }
    ]
  }
}
```

**Local Agent Config (`.claude/settings.local.json`):**
```json
{
  "session_name": "project-agent-uuid",
  "db_path": "/path/to/task_queue.db",
  "ready_flag_timeout": 30,
  "direct_delivery_enabled": true
}
```

### Database Schema Extensions

```sql
-- Add agent readiness tracking
ALTER TABLE message_queue ADD COLUMN delivery_method TEXT DEFAULT 'queued';

CREATE TABLE IF NOT EXISTS agents (
    session_name TEXT PRIMARY KEY,
    status TEXT DEFAULT 'active',  -- active/ready/offline
    ready_since TIMESTAMP,
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    direct_delivery_pipe TEXT  -- Optional socket/pipe path
);
```
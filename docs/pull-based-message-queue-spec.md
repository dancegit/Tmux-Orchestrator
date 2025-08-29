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
    sequence_number INTEGER NOT NULL,  -- Global FIFO ordering
    dependency_id INTEGER,  -- Optional message dependency
    project_name TEXT,  -- For project-level FIFO
    status TEXT DEFAULT 'pending',  -- pending/pulled/delivered
    enqueued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pulled_at TIMESTAMP,
    delivered_at TIMESTAMP,
    FOREIGN KEY (dependency_id) REFERENCES message_queue(id)
);

-- Indexes for FIFO ordering
CREATE INDEX idx_agent_fifo ON message_queue(agent_session, priority DESC, sequence_number);
CREATE INDEX idx_project_fifo ON message_queue(project_name, priority DESC, sequence_number);
CREATE INDEX idx_global_fifo ON message_queue(priority DESC, sequence_number);

-- Sequence number generator
CREATE TABLE sequence_generator (
    name TEXT PRIMARY KEY,
    current_value INTEGER DEFAULT 0
);

INSERT OR IGNORE INTO sequence_generator (name, current_value) VALUES ('message_sequence', 0);
```

#### 2. Claude Code Hooks Configuration

Event-driven hooks configured in `.claude/` workspace directories per agent:
- **PostToolUse**: Triggers after any tool/operation completes
- **Stop**: Triggers when Claude becomes idle (key for direct delivery)
- **SessionStart**: Initializes queue checking for new agents  
- **SessionEnd**: Cleanup and message requeuing on agent shutdown
- **UserPromptSubmit**: Additional trigger for queue checking
- **PreCompact**: Triggers before context compaction for agent rebriefing
- **Notification**: Can trigger on specific error patterns for auto-recovery

**Critical Architecture Note**: Agents run in tmux windows (not separate sessions), so agent identification uses `session:window` format (e.g., `project-session:2`) rather than session names alone.

**New Capabilities**:
- Automatic agent rebriefing when context compaction occurs
- Error detection and auto-restart mechanism
- Context preservation across restarts

Workspace Structure:
```
{agent_worktree}/
├── .claude/
│   ├── settings.json          # Project-level hooks (committed)
│   ├── settings.local.json    # Agent-specific config (generated)
│   └── hooks/                 # Symlinked hook scripts
│       ├── check_queue_enhanced.py → /orchestrator/claude_hooks/check_queue_enhanced.py
│       ├── cleanup_agent.py → /orchestrator/claude_hooks/cleanup_agent.py
│       ├── auto_restart.py → /orchestrator/claude_hooks/auto_restart.py
│       └── enqueue_message.py → /orchestrator/claude_hooks/enqueue_message.py
```

Key features:
- Native integration with Claude's workflow loop
- Deterministic event timing (no polling required)
- Automatic message injection into conversation stream
- Direct delivery mechanism for idle agents

#### 3. Enhanced Hook Scripts

##### check_queue_enhanced.py

Enhanced script executed by hooks to pull messages:
- Queries DB for next message using FIFO ordering (priority first, then sequence)
- Respects message dependencies (waits for prerequisite messages)
- Marks previous message as delivered (implicit ACK)
- Outputs message for hook injection into conversation
- Uses file locking for concurrent access safety
- Supports different FIFO scopes: per-agent, per-project, or global
- **NEW**: Handles rebriefing mode for context restoration
- **NEW**: Injects CLAUDE.md rules during PreCompact events

Features:
- Transaction-based to prevent race conditions
- Returns JSON format for hook processing
- Supports message priorities with FIFO ordering
- Message dependency resolution
- Configurable FIFO scope (per-agent/per-project/global)
- Bootstrap mode for session initialization
- Sequence number generation for strict ordering
- Context-aware rebriefing with activity summaries
- Automatic CLAUDE.md rule injection

##### cleanup_agent.py

SessionEnd handler for graceful agent shutdown:
- Requeues undelivered messages to prevent loss
- Updates agent status to offline
- Preserves message ordering for restart
- Logs shutdown details for debugging

##### auto_restart.py

Error detection and recovery system:
- Monitors for specific error patterns in Notification events
- Tracks restart history to prevent infinite loops
- Triggers tmux window restart with proper briefing
- Preserves agent context across restarts
- Configurable restart limits and cooldown periods

##### enqueue_message.py

Message enqueueing module used by other components:
- Atomic sequence number generation
- Priority and dependency support
- FIFO ordering guarantees
- Batch message enqueueing
- Validation and error handling

#### 4. Message Enqueuing

Replace all direct `tmux send-keys` with DB inserts:
- `send-claude-message.sh`: Refactor to enqueue with sequence numbers
- `TmuxMessenger` in `auto_orchestrate.py`: Insert to DB with FIFO support
- `scheduler.py`: Use existing DB connection for enqueueing with dependencies
- Hook configurations generated dynamically per agent session
- Sequence number atomically assigned on insert to guarantee FIFO order
- Project-level FIFO for coordinated multi-agent workflows

## Implementation Details

### Hook Event Types and Message Flow

**Primary Queue Hooks:**
- `PostToolUse` - After any tool or operation completes (primary message pull)
- `Stop` - When Claude becomes idle (secondary check + direct delivery mode)
- `SessionStart` - Initialize queue checking and register agent
- `SessionEnd` - Cleanup and requeue unprocessed messages
- `PreCompact` - Trigger rebriefing before context compaction
- `Notification` - Monitor for errors and trigger recovery

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

### Message Priority Levels and FIFO Ordering

**Priority Levels:**
- 0-9: Normal messages (default: 0)
- 10-49: High priority (important tasks)
- 50-99: Critical (errors, urgent commands)
- 100+: Emergency (system messages, interrupts)

**FIFO Ordering Scope:**
- **Per-Agent**: Messages for same agent maintain strict FIFO within priority
- **Per-Project**: Messages within same project maintain order (for setup sequences)
- **Global**: System-wide FIFO for critical coordination messages

**Message Dependencies:**
- Optional `dependency_id` field creates prerequisite chains
- Dependent messages wait until prerequisite is marked delivered
- Useful for setup sequences where order is critical
- Example: "Create database" must complete before "Run migrations"

### Bootstrap Process

For new agents:
1. Session created by auto_orchestrate.py with Claude.dev runtime
2. Create `.claude/` directory in agent's worktree
3. Generate dynamic hook configuration with session parameters
4. Symlink shared hook scripts to agent's workspace
5. SessionStart hook automatically pulls first message
6. If queue empty, agent enters "ready for direct delivery" mode

### FIFO Queue Processing

**Message Selection Algorithm:**
```sql
-- Per-agent FIFO (default)
SELECT * FROM message_queue 
WHERE agent_session = ? AND status = 'pending'
  AND (dependency_id IS NULL OR dependency_id IN (
    SELECT id FROM message_queue WHERE status = 'delivered'
  ))
ORDER BY priority DESC, sequence_number ASC
LIMIT 1;

-- Project-level FIFO
SELECT * FROM message_queue 
WHERE project_name = ? AND status = 'pending'
  AND (dependency_id IS NULL OR dependency_id IN (
    SELECT id FROM message_queue WHERE status = 'delivered'
  ))
ORDER BY priority DESC, sequence_number ASC
LIMIT 1;
```

**Sequence Number Generation:**
- Atomically increment global sequence counter on message insert
- Guarantees strict FIFO ordering across all messages
- Prevents race conditions in high-concurrency scenarios
- Used as tie-breaker within same priority level

**Dependency Resolution:**
- Messages with `dependency_id` wait for prerequisite completion
- Circular dependency detection prevents deadlocks
- Timeout mechanism for stale dependencies
- Cascade handling when prerequisite messages fail

### Error Handling

- **Failed hooks**: Retry with exponential backoff in hook commands
- **DB locks**: Use SQLite busy timeout
- **Agent crashes**: Hook cleanup on session end, messages requeued
- **Hook conflicts**: Ordered execution and conflict detection
- **Dependency timeouts**: Auto-resolve stale prerequisites after timeout
- **Sequence gaps**: Handle missing sequence numbers gracefully

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

## Implementation Status

### Completed Features

1. **Core Hook Scripts**:
   - ✅ `check_queue_enhanced.py` - Enhanced queue checking with rebriefing
   - ✅ `cleanup_agent.py` - Agent cleanup on session end
   - ✅ `auto_restart.py` - Error detection and recovery
   - ✅ `enqueue_message.py` - Message enqueueing module

2. **Agent Rebriefing**:
   - ✅ PreCompact hook triggers context restoration
   - ✅ CLAUDE.md rules automatically reinjected
   - ✅ Recent activity summary preserved
   - ✅ Configurable rebriefing intervals

3. **Error Recovery**:
   - ✅ Notification hook monitors for errors
   - ✅ Automatic restart with limits
   - ✅ Context preservation across restarts
   - ✅ Restart history tracking

4. **Integration Components**:
   - ✅ `tmux_messenger_hooks.py` - Enhanced TmuxMessenger
   - ✅ `setup_agent_hooks.py` - Hook configuration script
   - ✅ `test_hooks_integration.py` - Test suite

### Testing Strategy

1. **Unit Tests**: Individual hook script testing
2. **Integration Tests**: Full workflow validation
3. **Failure Scenarios**: Error injection and recovery
4. **Performance Tests**: Queue throughput and latency
5. **Migration Tests**: Push to pull transition

## Future Enhancements

1. **REST API**: Replace direct DB access with API for better security
2. **Advanced Dependencies**: Support DAG-style workflows with complex prerequisites
3. **Advanced Hook Events**: Custom triggers for specific scenarios
4. **Web Dashboard**: Visualize queue states, FIFO order, and hook execution
5. **Multi-Runtime Support**: Support for different Claude Code implementations
6. **Message Routing**: Smart routing based on agent capabilities and load
7. **Queue Partitioning**: Shard queues by project or priority for scalability
8. **Message Batching**: Group related messages for efficient processing
9. **Metrics Collection**: Hook execution times and success rates
10. **Health Monitoring**: Agent health checks via hooks

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
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue_enhanced.py --agent #{session_name}:#{window_index}"
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
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue_enhanced.py --agent #{session_name}:#{window_index} --check-idle"
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
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue_enhanced.py --agent #{session_name}:#{window_index} --bootstrap"
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
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/cleanup_agent.py --agent #{session_name}:#{window_index}"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue_enhanced.py --agent #{session_name}:#{window_index} --rebrief"
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": ".*error.*|.*fail.*|.*crash.*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/auto_restart.py --agent #{session_name}:#{window_index}"
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
  "agent_id": "project-session:2",
  "session_name": "project-session",
  "db_path": "/path/to/task_queue.db",
  "ready_flag_timeout": 30,
  "direct_delivery_enabled": true
}
```

### Database Schema Extensions

```sql
-- Add agent readiness tracking and FIFO extensions
ALTER TABLE message_queue ADD COLUMN delivery_method TEXT DEFAULT 'queued';
ALTER TABLE message_queue ADD COLUMN fifo_scope TEXT DEFAULT 'agent';  -- agent/project/global

CREATE TABLE IF NOT EXISTS agents (
    session_name TEXT PRIMARY KEY,
    project_name TEXT,  -- For project-level FIFO
    status TEXT DEFAULT 'active',  -- active/ready/offline/error
    ready_since TIMESTAMP,
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    direct_delivery_pipe TEXT,  -- Optional socket/pipe path
    last_sequence_delivered INTEGER DEFAULT 0,  -- Track delivery order
    restart_count INTEGER DEFAULT 0,  -- Track restart attempts
    last_restart TIMESTAMP,
    last_error TEXT,
    context_preserved TEXT  -- JSON blob for context preservation
);

-- Context preservation table
CREATE TABLE IF NOT EXISTS agent_context (
    agent_id TEXT PRIMARY KEY,
    last_briefing TIMESTAMP,
    briefing_content TEXT,
    activity_summary TEXT,
    checkpoint_data TEXT,  -- JSON blob
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
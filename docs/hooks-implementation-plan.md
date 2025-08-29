# Hooks-Based Message Queue Implementation Plan

## Executive Summary

This document outlines the implementation plan for transitioning from push-based to hooks-based message delivery in Tmux-Orchestrator, incorporating automatic agent rebriefing and error recovery capabilities.

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

#### Day 1-2: Database and Core Scripts
- [ ] Extend database schema with new tables
- [ ] Implement `check_queue_enhanced.py` with rebriefing support
- [ ] Implement `enqueue_message.py` module
- [ ] Add sequence number generation

#### Day 3-4: Hook Scripts
- [ ] Implement `cleanup_agent.py` for SessionEnd
- [ ] Implement `auto_restart.py` for error recovery
- [ ] Create `setup_agent_hooks.py` configuration script
- [ ] Test individual hook scripts

#### Day 5: Integration Components
- [ ] Create `tmux_messenger_hooks.py` with dual-mode support
- [ ] Update `auto_orchestrate.py` to use new messenger
- [ ] Implement hooks as default behavior (no feature flags)
- [ ] Create test harness

### Phase 2: Agent Lifecycle Features (Week 2)

#### Day 1-2: Context Management
- [ ] Implement PostCompact rebriefing logic
- [ ] Create context preservation mechanism
- [ ] Add CLAUDE.md rule injection after compaction
- [ ] Test context recovery scenarios

#### Day 3-4: Error Recovery
- [ ] Implement error detection patterns
- [ ] Add restart limits and cooldowns
- [ ] Create restart history tracking
- [ ] Test failure scenarios

#### Day 5: Testing & Documentation
- [ ] Run integration tests
- [ ] Update documentation
- [ ] Create troubleshooting guide
- [ ] Performance benchmarking

### Phase 3: Rollout (Week 3)

#### Day 1: Staging Deployment
- [ ] Deploy to staging environment
- [ ] Configure test agents with hooks
- [ ] Monitor hook execution
- [ ] Collect metrics

#### Day 2-3: Gradual Migration
- [ ] Migrate one project at a time
- [ ] Monitor for issues
- [ ] Adjust configuration as needed
- [ ] Document learnings

#### Day 4-5: Full Deployment
- [ ] Complete migration of all agents
- [ ] Disable legacy push system
- [ ] Final validation
- [ ] Post-deployment monitoring

## Technical Requirements

### Hook Scripts Location
```
/home/clauderun/Tmux-Orchestrator/claude_hooks/
├── check_queue_enhanced.py
├── cleanup_agent.py
├── auto_restart.py
├── enqueue_message.py
└── test_hooks.py
```

### Database Schema Updates
```sql
-- Already exists: message_queue table
-- Need to add:
ALTER TABLE agents ADD COLUMN restart_count INTEGER DEFAULT 0;
ALTER TABLE agents ADD COLUMN last_restart TIMESTAMP;
ALTER TABLE agents ADD COLUMN last_error TEXT;
ALTER TABLE agents ADD COLUMN context_preserved TEXT;

CREATE TABLE agent_context (
    agent_id TEXT PRIMARY KEY,
    last_briefing TIMESTAMP,
    briefing_content TEXT,
    activity_summary TEXT,
    checkpoint_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Configuration Template
```json
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
      "matcher": ".*error.*|.*fail.*|.*crash.*",
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/auto_restart.py"
      }]
    }],
    "Stop": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue_enhanced.py --check-idle"
      }]
    }],
    "SessionStart": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue_enhanced.py --bootstrap"
      }]
    }],
    "SessionEnd": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/cleanup_agent.py"
      }]
    }]
  }
}
```

## Key Implementation Details

### 1. Agent Identification
- Use `session:window` format (e.g., `project-impl:2`)
- Validate against tmux context in hooks
- Store in database for tracking

### 2. Message Priorities
- 0-9: Normal operations
- 10-49: High priority tasks
- 50-99: Critical/errors
- 100+: Emergency/system
- 200: Rebriefing messages (highest)

### 3. Rebriefing Strategy
- Trigger on PostCompact event
- Queue high-priority rebriefing message after compaction
- Include:
  - Full CLAUDE.md rules
  - Recent activity summary
  - Current task context
  - Git status

### 4. Error Recovery
- Monitor Notification events for error patterns
- Track restart attempts per agent
- Implement exponential backoff
- Preserve context across restarts
- Maximum 3 restarts per hour

### 5. Context Preservation
- Store in `agent_context` table
- Include:
  - Last briefing content
  - Recent commands
  - Current branch/files
  - Task progress
- Restore on restart

## Testing Strategy

### Unit Tests
- Individual hook script testing
- Database operations
- Message enqueueing/dequeueing
- Context preservation

### Integration Tests
- Full message flow
- Hook triggering
- Error recovery
- Context restoration

### Performance Tests
- Message throughput
- Hook execution latency
- Database query performance
- Concurrent agent handling

### Failure Scenarios
- Hook script failures
- Database locks
- Agent crashes
- Network issues
- Context loss

## Monitoring & Metrics

### Key Metrics to Track
- Message delivery latency
- Hook execution success rate
- Queue depth by priority
- Agent restart frequency
- Context compaction rate
- Rebriefing effectiveness

### Logging Strategy
- Hook execution logs to `/var/log/claude_hooks.log`
- Database operations logged
- Error patterns captured
- Performance metrics recorded

### Health Checks
- Queue depth monitoring
- Agent status verification
- Hook configuration validation
- Database integrity checks

## Risk Mitigation

### Identified Risks
1. **Hook Failures**: Scripts may fail due to permissions or errors
   - Mitigation: Comprehensive error handling and fallbacks

2. **Message Loss**: Database issues could lose messages
   - Mitigation: Transactional operations and backups

3. **Context Loss**: Compaction without proper rebriefing
   - Mitigation: High-priority rebriefing messages

4. **Restart Loops**: Agents stuck in restart cycles
   - Mitigation: Restart limits and cooldowns

5. **Performance Impact**: Hook overhead on agent operations
   - Mitigation: Optimized scripts and async processing

### Rollback Plan
1. Revert to previous code version
2. Restart agents with previous configuration
3. Re-enable push-based monitoring if needed
4. Export pending messages
5. Investigate and fix issues

## Success Criteria

### Technical Success
- [ ] All hooks trigger reliably
- [ ] Messages delivered with <500ms latency
- [ ] Zero message loss during migration
- [ ] Context preserved across restarts
- [ ] Error recovery works automatically

### Operational Success
- [ ] Reduced manual intervention
- [ ] Improved agent reliability
- [ ] Better error handling
- [ ] Simplified architecture
- [ ] Enhanced monitoring

## Timeline Summary

- **Week 1**: Core infrastructure development
- **Week 2**: Agent lifecycle features
- **Week 3**: Testing and rollout
- **Week 4**: Monitoring and optimization

Total estimated time: 3-4 weeks for complete implementation and migration.
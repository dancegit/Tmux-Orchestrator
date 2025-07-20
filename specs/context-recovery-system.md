# Context Recovery System Specification

## Problem Statement

Agents frequently run out of context (especially in multi-agent systems that use ~15x more tokens) and create handoff documents but have no automated recovery mechanism. This requires constant manual intervention from the orchestrator.

## Proposed Solution

### 1. Context Monitor Script (`context_monitor.py`)

Similar to credit_monitor.py but for context exhaustion:

```python
#!/usr/bin/env python3
"""Monitor agents for context exhaustion and trigger recovery"""

class ContextMonitor:
    def __init__(self):
        self.warning_patterns = [
            "creating handoff document",
            "context remaining: [0-9]+%",
            "HANDOFF_.*\.md",
            "approaching context limit",
            "context crisis"
        ]

    def check_agent_context(self, session: str, window: int) -> dict:
        """Check if agent is creating handoff documents"""
        # Capture last 100 lines
        # Look for handoff document creation
        # Extract context percentage if available
        # Return status

    def recover_agent(self, session: str, window: int, role: str, handoff_file: str):
        """Automatically recover an exhausted agent"""
        # 1. Kill the exhausted Claude instance
        # 2. Restart Claude in same window
        # 3. Load handoff document
        # 4. Continue work
```

### 2. Automated Recovery Workflow

#### Detection Phase
```bash
# Monitor for handoff document creation
tmux capture-pane -t session:window -p | grep -E "(HANDOFF_|handoff|context remaining)"
```

#### Recovery Phase
```bash
# 1. Detect handoff document
HANDOFF_FILE=$(find worktree -name "*HANDOFF*.md" -mmin -10 | head -1)

# 2. Kill exhausted agent
tmux send-keys -t session:window C-c
sleep 2

# 3. Restart Claude
tmux send-keys -t session:window "claude --dangerously-skip-permissions" Enter
sleep 5

# 4. Load context from handoff
./send-claude-message.sh session:window "Read and continue from: $HANDOFF_FILE

You are taking over from an agent who ran out of context. Read the handoff document and continue their work exactly where they left off. The document contains:
- Current status
- Recent accomplishments
- Next steps to execute
- Important context

Continue the work seamlessly."
```

### 3. Enhanced Handoff Document Format

Agents should create standardized handoff documents:

```markdown
# HANDOFF_[ROLE]_[TIMESTAMP].md

## Agent Context Transfer
- Role: [Developer/Tester/etc]
- Context exhausted at: [timestamp]
- Last activity: [what was being done]

## Quick Start Commands
```bash
# Copy-paste these to continue immediately:
cd [working directory]
git checkout [current branch]
[specific command to continue work]
```

## Current State
- Working on: [specific task]
- Files modified: [list]
- Tests status: [pass/fail/pending]

## Immediate Next Steps
1. [Specific action with command]
2. [Next action]
3. [Following action]

## Context Summary
[2-3 paragraphs of essential context]

## Recent Git Commits
[Last 3 commit hashes and messages]
```

### 4. Integration with Auto-Orchestrate

Add to agent briefings:

```python
# In create_role_briefing()
context_recovery = """
**Context Management Protocol**:
When you notice context running low (repeated questions, confusion):
1. Create handoff document: `[ROLE]_HANDOFF_$(date +%Y%m%d_%H%M).md`
2. Include: current state, next steps, key commands
3. Commit all work with message: "Context handoff - [what you were doing]"
4. The system will auto-recover you with your handoff document
"""
```

### 5. Proactive Context Management

#### For Agents
- Check context health: Ask "What percentage of my context have I used?"
- Create checkpoint documents every 2 hours
- Use structured updates to minimize context usage

#### For Orchestrator
- Monitor for agents creating multiple similar files (sign of confusion)
- Check for repeated questions or tasks
- Proactively schedule agent rotation before exhaustion

### 6. Context Compression Strategies

While `/compress` doesn't exist, agents can:

1. **Periodic Summaries**:
   ```
   Every hour, create: `checkpoint_[timestamp].md`
   - Key accomplishments
   - Current state
   - Next priorities
   ```

2. **Forget Irrelevant Details**:
   ```
   "I'm clearing old context. Key facts to remember:
   - Working on: [current task]
   - Branch: [branch name]
   - Next step: [specific action]"
   ```

3. **Use External Memory**:
   ```
   Write important state to files:
   - `.current_task` - what you're doing
   - `.next_steps` - queued work
   - `.key_context` - important facts
   ```

## Implementation Priority

1. **Phase 1**: Context monitor script (detect exhaustion)
2. **Phase 2**: Auto-recovery mechanism (restart agents)
3. **Phase 3**: Standardized handoff format
4. **Phase 4**: Proactive rotation before exhaustion

## Success Metrics

- Reduce manual interventions by 90%
- Agents recover within 2 minutes of exhaustion
- No work loss during transitions
- Seamless task continuation

## Open Questions

1. Should we implement agent rotation schedules (e.g., every 4 hours)?
2. How to detect context percentage without explicit indicators?
3. Should orchestrator maintain a context budget across team?
4. Can we use git commits as context checkpoints?

## Next Steps

1. Implement basic context_monitor.py
2. Test auto-recovery workflow
3. Update agent briefings with context protocol
4. Document in CLAUDE.md

# Context Recovery Protocol for Tmux Orchestrator

## Overview
When agents run low on context, they can self-recover using Claude Code's built-in commands without requiring orchestrator intervention.

## Self-Recovery Process for Low-Context Agents

### 1. **Create Handoff Document First**
Before running `/compact`, agents should create a comprehensive handoff document:

```markdown
# HANDOFF_[ROLE]_[TIMESTAMP].md

## Current State
- Working on: [specific task/phase]
- Branch: [current git branch]
- Last completed: [what was just finished]
- Next steps: [what needs to be done]

## Key Commands to Continue
```bash
# Current directory
pwd  # [show current path]

# Git status
git branch  # [current branch]
git log --oneline -3  # [recent commits]

# Next command to run
[specific command to continue work]
```

## Important Context
- [Key fact 1]
- [Key fact 2]
- [Key fact 3]

## Files Recently Modified
- [file1] - [what was changed]
- [file2] - [what was changed]
```

### 2. **Run /compact Command**
```
/compact
```
This clears the conversation history while preserving the current session.

### 3. **Reload Essential Context**
After compacting, immediately reload critical information:

```bash
# Option A: If /context-prime is available
/context-prime

# Option B: Manual context reload
# Read core documentation
Read CLAUDE.md
Read README.md

# Read your own handoff document
Read HANDOFF_[ROLE]_[TIMESTAMP].md

# Check current git status
git status
git log --oneline -5
```

### 4. **Verify Context Recovery**
After reloading context:
- Confirm understanding of current task
- Verify git branch is correct
- Check recent work from handoff document
- Continue from documented next steps

## Orchestrator Protocol for Context Management

### Proactive Monitoring
The orchestrator should periodically check agent context health:

```bash
# Every 60-90 minutes
./send-claude-message.sh session:window "Context check: If you're feeling confused or have been working for 2+ hours, please:
1. Create a handoff document with your current state
2. Run /compact
3. Reload context from CLAUDE.md and your handoff doc
4. Continue working"
```

### Enhanced Agent Briefings
Add to all agent briefings in `auto_orchestrate.py`:

```python
context_management = """
**📊 Context Management Protocol**:
When you notice context degradation (confusion, repeated questions):
1. Create handoff document: `{role}_HANDOFF_$(date +%Y%m%d_%H%M).md`
2. Include: current state, next steps, recent changes
3. Run `/compact` to clear conversation history
4. Reload context:
   - `/context-prime` (if available) or
   - Read CLAUDE.md, README.md, and your handoff document
5. Continue work from documented next steps

**Proactive Context Health**:
- Create checkpoint documents every 2 hours
- Run /compact preemptively during natural break points
- Always document state before major phase transitions
"""
```

## Context Recovery Patterns

### For Developer Role
```bash
# Before /compact
echo "Creating context checkpoint..."
cat > DEVELOPER_CHECKPOINT_$(date +%Y%m%d_%H%M).md << EOF
## Developer Checkpoint
- Implementing: Phase 6 integration tests
- Branch: feature/hybrid-deployment
- Last commit: $(git log --oneline -1)
- Next: Complete Modal deployment tests
- Key files: src/deploy/modal_handler.py, tests/test_modal.py
EOF

# Run /compact
/compact

# After /compact
/context-prime  # or manual reads
# Continue from checkpoint
```

### For Tester Role
```bash
# Create test status checkpoint
cat > TESTER_CHECKPOINT_$(date +%Y%m%d_%H%M).md << EOF
## Test Suite Status
- Completed: Unit tests (95%), Integration tests (60%)
- Running: E2E tests
- Failed: 3 tests in test_modal_deploy.py
- Next: Fix failing tests, complete E2E suite
EOF

/compact
# Reload and continue
```

### For Project Manager Role
```bash
# PM checkpoint includes team status
cat > PM_CHECKPOINT_$(date +%Y%m%d_%H%M).md << EOF
## Team Status Checkpoint
- Developer: Phase 6 implementation (80% complete)
- Tester: Writing integration tests
- Researcher: Security analysis complete
- Next reviews: Modal deployment code, test coverage
EOF

/compact
# Reload and coordinate
```

## Automated Context Health Monitoring

### Add to orchestrator's regular checks:
```bash
# In schedule_with_note.sh scheduling
"Check team context health - remind agents to /compact if needed"

# Check for signs of context exhaustion
- Multiple similar files created
- Repeated similar questions
- Confusion about current task
- Working for 3+ hours continuously
```

### Success Indicators
- Agents self-recover without orchestrator intervention
- No work loss during context recovery
- Seamless continuation after /compact
- Reduced "context crisis" events

## Best Practices

1. **Checkpoint Before Compact**: Always create state document first
2. **Compact at Natural Breaks**: Between phases, after major commits
3. **Reload Systematically**: CLAUDE.md → README.md → Handoff doc → Git status
4. **Verify Recovery**: Confirm understanding before continuing work
5. **Document Patterns**: Note what context is most important for each role

## Emergency Recovery

If an agent becomes completely confused after /compact:
```bash
# Orchestrator intervention
./send-claude-message.sh session:window "You seem confused. Please:
1. Read CLAUDE.md for your role responsibilities
2. Read your latest HANDOFF or CHECKPOINT document
3. Check git log --oneline -10 for recent work
4. Tell me your understanding of current task"
```

This protocol enables agents to self-manage their context without requiring constant orchestrator intervention!
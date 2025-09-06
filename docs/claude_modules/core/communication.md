# Communication Protocols

## Hub-and-Spoke Model
The Orchestrator acts as the central hub with automatic enforcement:
- All agents report directly to Orchestrator
- Orchestrator coordinates all cross-functional communication
- Direct agent-to-agent communication only for immediate needs (test handoffs)
- Automatic hub-spoke enforcement prevents silent completions

## Message Commands

### Smart Messaging (scm)
```bash
# Use role names instead of window numbers
scm session-name:TestRunner "Run the test suite"
scm session-name:Developer "Status update needed"
scm session-name:Project-Manager "Review required"
```

### Communication Rules
1. **No Chit-Chat**: All messages work-related
2. **Use Templates**: Reduces ambiguity
3. **Acknowledge Receipt**: Simple "ACK" for tasks
4. **Escalate Quickly**: Don't stay blocked >10 min
5. **One Topic Per Message**: Keep focused
6. **Report Completions**: Use `./report-completion.sh` for all task completions
7. **Critical Updates**: Use hub-spoke script for deployment/failure messages


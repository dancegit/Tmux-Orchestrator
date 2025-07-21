# Tmux Orchestrator Compliance Monitoring System

## Overview

The compliance monitoring system ensures all agents follow the rules defined in CLAUDE.md. It monitors inter-agent communications, detects rule violations, and automatically updates when CLAUDE.md changes.

## Components

### 1. Rule Extraction (`extract_rules.py`)
- Parses CLAUDE.md to extract monitorable rules
- Creates `compliance_rules.json` with structured rule definitions
- Categories: communication, git, scheduling, integration

### 2. CLAUDE.md Watcher (`claude_md_watcher.py`)
- Monitors CLAUDE.md for changes using file system events
- Automatically re-extracts rules when CLAUDE.md is modified
- Notifies compliance monitor about rule updates
- Debounces rapid changes to avoid excessive processing

### 3. Rule Analyzer (`rule_analyzer.py`)
- Analyzes messages against compliance rules
- Uses Claude AI for sophisticated analysis when available
- Falls back to pattern-based detection if Claude unavailable
- Supports custom rule files via `--rules` parameter

### 4. Compliance Monitor (`compliance_monitor.py`)
- Continuously monitors communication logs
- Triggers analysis for new messages
- Automatically reloads rules when updated
- Notifies orchestrator about violations

### 5. Monitored Message Sender (`monitored_send_message.sh`)
- Wrapper around `send-claude-message.sh`
- Logs all communications in JSONL format
- Triggers compliance analysis
- Available via `scm` shortcut

## Usage

### Starting the Monitoring System
```bash
# Start both monitor and watcher
./monitoring/start_monitoring.sh

# Or start components individually
python3 monitoring/compliance_monitor.py &
python3 monitoring/claude_md_watcher.py &
```

### Stopping the Monitoring System
```bash
./monitoring/stop_monitoring.sh
```

### Sending Monitored Messages
```bash
# Use the shortcut command (recommended)
scm session:window "Your message here"

# Or use the full path
./send-monitored-message.sh session:window "Your message"
```

### Checking Violations
```bash
# View today's violations
cat registry/logs/communications/$(date +%Y-%m-%d)/violations.jsonl | jq .

# Check specific date
cat registry/logs/communications/2025-07-21/violations.jsonl | jq .
```

## Rule Updates

### Automatic Updates
1. Edit CLAUDE.md with new rules or changes
2. The watcher detects changes within 2 seconds
3. Rules are automatically re-extracted
4. Compliance monitor reloads rules
5. New messages are analyzed with updated rules

### Manual Rule Extraction
```bash
# Extract rules manually
python3 monitoring/extract_rules.py

# View extracted rules
cat monitoring/compliance_rules.json | jq .
```

## Log Structure

```
registry/logs/communications/
├── 2025-07-21/
│   ├── messages.jsonl          # All logged messages
│   ├── violations.jsonl        # Detected violations
│   ├── compliance_analysis.jsonl # Detailed analysis
│   ├── .new_messages           # Trigger file (temporary)
│   └── .rules_updated          # Rule update trigger (temporary)
```

## Rule Categories

### Communication Rules
- Hub-and-spoke model enforcement
- No direct developer-to-tester communication
- Work-related messages only
- Use of proper messaging scripts

### Git Rules
- Branch protection (no main merge unless started on main)
- Auto-commit every 30 minutes
- Commit before task switches
- Agent-specific branch naming

### Scheduling Rules
- Orchestrator startup scheduling test
- Target window parameter usage
- Regular check-in maintenance

### Integration Rules
- PM-only integration handling
- Auto-merge with --admin flag
- Post-integration synchronization

## Troubleshooting

### Monitor Not Detecting Messages
1. Check if monitor is running: `pgrep -f compliance_monitor.py`
2. Verify log directory exists: `ls -la registry/logs/communications/`
3. Check for trigger file: `ls -la registry/logs/communications/*/.*`

### Rules Not Updating
1. Check watcher is running: `pgrep -f claude_md_watcher.py`
2. Verify CLAUDE.md exists and is readable
3. Check rule extraction: `python3 monitoring/extract_rules.py`
4. Look for errors in `monitoring/rule_updates.log`

### Claude AI Analysis Failing
1. Check Claude availability
2. Monitor will fall back to pattern-based detection
3. Check logs for fallback notifications

## Best Practices

1. **Always use `scm` or `send-monitored-message.sh`** for agent communication
2. **Start monitoring early** in orchestration sessions
3. **Review violations regularly** to improve team compliance
4. **Update CLAUDE.md** with new rules as patterns emerge
5. **Monitor resource usage** - stop when not needed

## Integration with Orchestrator

The orchestrator receives notifications about violations through:
1. Direct tmux messages for critical violations
2. Summary reports in registry/notes/
3. Violation logs for detailed review

Example orchestrator notification:
```
COMPLIANCE VIOLATION DETECTED:
Developer (session:0) messaged Tester (session:3) directly
Rule: Developers must report to PM only (comm-001)
Severity: HIGH
Please remind team about hub-and-spoke communication model.
```
# Tmux Orchestrator Compliance Monitoring System

## Overview

The Compliance Monitoring System ensures all agents follow the rules defined in CLAUDE.md by:
- Intercepting and logging all communications
- Analyzing messages for rule violations using Claude AI
- Notifying the orchestrator of violations in real-time
- Generating comprehensive daily compliance reports

## Architecture

```
send-monitored-message.sh → logs messages → compliance_monitor.py
                                               ↓
                                          rule_analyzer.py
                                               ↓
                                     Claude AI analysis (JSON)
                                               ↓
                                    violations detected → notify orchestrator
```

## Key Components

### 1. Communication Wrapper (`monitored_send_message.sh`)
- Wraps around `send-claude-message.sh`
- Logs all messages with metadata
- Triggers compliance checking

### 2. Rule Extractor (`extract_rules.py`)
- Parses CLAUDE.md for monitorable rules
- Creates structured JSON rule definitions
- Covers communication, git, scheduling, and integration rules

### 3. Rule Analyzer (`rule_analyzer.py`)
- Uses `claude --dangerously-skip-permissions` for AI analysis
- Checks messages against compliance rules
- Returns structured JSON with violations
- Has fallback logic if Claude is unavailable

### 4. Compliance Monitor (`compliance_monitor.py`)
- Runs continuously as a service
- Watches for new messages
- Triggers analysis and notifications
- Maintains audit logs

### 5. Notification Handler (`notification_handler.py`)
- Sends alerts to orchestrator
- Implements rate limiting
- Provides different severity levels
- Generates daily summaries

### 6. Report Generator (`report_generator.py`)
- Creates comprehensive daily reports
- Shows compliance rates and trends
- Identifies top rule violations
- Provides actionable recommendations

## Installation

```bash
cd monitoring
./install_monitoring.sh
```

The installer will:
- Check prerequisites (uv, jq, claude)
- Extract rules from CLAUDE.md
- Create command wrappers
- Optionally set up systemd service
- Optionally configure daily reports

## Usage

### Start Monitoring Service
```bash
# Manual start
./monitoring/compliance_monitor.py

# Or with systemd
sudo systemctl start tmux-compliance-monitor
```

### Send Monitored Messages
```bash
# Use the monitored wrapper instead of direct messaging
./send-monitored-message.sh pm:1 "Status update please"
```

### Generate Reports
```bash
# Today's report
./monitoring/report_generator.py

# Specific date
./monitoring/report_generator.py 2025-07-21

# Show report immediately
./monitoring/report_generator.py --show
```

### Check Violations
```bash
# View today's violations
cat registry/logs/communications/$(date +%Y-%m-%d)/violations.jsonl | jq
```

## Monitored Rules

### Communication Rules
- Hub-and-spoke model enforcement
- No direct developer-to-tester communication
- Work-related messages only
- Proper use of send-claude-message.sh

### Git Rules
- Branch protection (no unauthorized main merges)
- 30-minute commit frequency
- Proper branch naming
- Task switch commits

### Scheduling Rules
- Orchestrator startup checks
- Proper target window usage
- Regular check-in intervals

### Integration Rules
- PM-only integration handling
- Auto-merge with --admin flag
- Post-merge sync requirements

## Log Structure

```
registry/
├── logs/
│   ├── communications/
│   │   ├── 2025-07-21/
│   │   │   ├── messages.jsonl      # All messages
│   │   │   └── violations.jsonl    # Detected violations
│   ├── compliance/
│   │   ├── daily_reports/          # Generated reports
│   │   ├── violation_alerts/       # Alert history
│   │   └── notifications.jsonl     # Notification log
│   └── agent_sessions/             # Agent conversation logs
└── notes/
    ├── orchestrator/               # Orchestrator notes
    └── compliance_summaries/       # Summary documents
```

## Troubleshooting

### Monitor Not Detecting Messages
- Ensure agents use `send-monitored-message.sh`
- Check if monitor service is running
- Verify log directory permissions

### Claude Analysis Failing
- Check Claude CLI installation
- Verify `--dangerously-skip-permissions` works
- Monitor will use fallback rules if Claude unavailable

### No Orchestrator Notifications
- Verify orchestrator session name
- Check send-claude-message.sh works
- Review notification log for errors

## Best Practices

1. **Always use monitored messaging** during active development
2. **Review daily reports** to identify patterns
3. **Address violations promptly** to maintain compliance
4. **Update rules** as project evolves
5. **Train new agents** on compliance requirements

## Future Enhancements

- Web dashboard for real-time monitoring
- Machine learning for pattern detection
- Integration with GitHub Actions
- Automated corrective actions
- Performance metrics tracking
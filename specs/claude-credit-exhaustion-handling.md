# Claude Code Credit Exhaustion Handling System

## Overview

This specification outlines a smart system to handle Claude Code's 5-hour credit reset cycles, automatically detecting credit exhaustion and gracefully pausing/resuming agent operations.

## Problem Statement

- Claude Code has usage limits that reset every 5 hours
- When credits are exhausted, agents receive "/upgrade" messages and stop functioning
- Manual intervention is currently required to restart agents after credits reset
- Credit resets occur at fixed 5-hour intervals (e.g., 18:00, 23:00, 04:00, 09:00, 14:00)
- Multiple agents running concurrently can exhaust credits quickly

## Proposed Solution

### Core Components

#### 1. Credit Monitor Script (`credit_monitor.py`)
- **Purpose**: Continuously monitor agent windows for credit exhaustion signals
- **Features**:
  - Monitors tmux panes for "/upgrade" messages
  - Tracks credit exhaustion timestamps per agent
  - Calculates next reset time based on 5-hour cycles
  - Manages agent pause/resume states
  - Updates orchestrator with team credit status

#### 2. Credit Schedule Tracker (`~/.claude/credit_schedule.json`)
```json
{
  "reset_times": ["18:00", "23:00", "04:00", "09:00", "14:00"],
  "timezone": "Europe/Lisbon",
  "agents": {
    "session:window": {
      "status": "active|exhausted|paused",
      "exhausted_at": "2025-01-20T22:45:00",
      "scheduled_resume": "2025-01-20T23:00:00",
      "history": []
    }
  }
}
```

#### 3. Enhanced Schedule Script (`schedule_credit_aware.sh`)
- Wraps existing `schedule_with_note.sh`
- Checks agent credit status before scheduling
- Skips scheduling for exhausted agents
- Automatically schedules wake-up at next reset time

#### 4. Agent Health Monitor (`check_agent_health.sh`)
- Quick health check for all agents
- Detects credit exhaustion indicators
- Reports time until next reset
- Can be run manually or via cron

### Detection Strategy

#### Primary Indicators
1. **"/upgrade" message** - Definitive exhaustion signal
2. **"Approaching Opus usage limit"** - Warning signal
3. **"credits will reset at [time]"** - Provides exact reset time

#### Detection Implementation
```bash
# Check last 50 lines of tmux pane
tmux capture-pane -t session:window -p -S -50 | grep -E "(upgrade|usage limit|credits will reset)"
```

### Pause/Resume Workflow

#### Pause Process
1. Detect credit exhaustion signal
2. Mark agent as "exhausted" in tracking file
3. Stop sending new tasks to agent
4. Calculate next reset time
5. Schedule automatic resume
6. Notify orchestrator

#### Resume Process
1. Wake up at scheduled reset time
2. Send test message to verify credits available
3. If successful, mark agent as "active"
4. Resume normal scheduling
5. If failed, reschedule for next cycle

### Orchestrator Integration

#### New Orchestrator Commands
- `check_credit_status` - View all agents' credit status
- `pause_agent <window>` - Manually pause an agent
- `resume_agent <window>` - Manually resume an agent
- `estimate_reset_time` - Calculate next reset time

#### Modified Orchestrator Briefing
```markdown
## Credit Management
- Check team credit status regularly with `check_credit_status`
- Agents will auto-pause when credits exhausted
- Resume times are calculated based on 5-hour cycles
- Prioritize critical work when credits are low
```

### Implementation Timeline

1. **Phase 1**: Basic detection and manual pause/resume
2. **Phase 2**: Automatic scheduling and wake-up
3. **Phase 3**: Predictive credit management
4. **Phase 4**: Historical analysis and optimization

### Configuration Options

```bash
# Environment variables
CLAUDE_CREDIT_CYCLE_HOURS=5
CLAUDE_CREDIT_CHECK_INTERVAL=5  # minutes
CLAUDE_CREDIT_WARNING_THRESHOLD=10  # minutes before reset
```

### Error Handling

1. **False Positives**: Verify exhaustion with multiple checks
2. **Missed Resets**: Retry logic with exponential backoff
3. **Clock Drift**: Use NTP sync and timezone awareness
4. **Agent Crashes**: Distinguish between crashes and credit exhaustion

### Benefits

- **Automatic Recovery**: No manual intervention needed
- **Efficient Scheduling**: No wasted attempts on exhausted agents
- **Project Continuity**: Work continues with available agents
- **Cost Optimization**: Better credit usage patterns
- **Historical Insights**: Track and optimize credit consumption

### Future Enhancements

1. **Credit Prediction**: ML model to predict exhaustion
2. **Dynamic Intervals**: Adjust check-in frequency based on credits
3. **Priority Queues**: Critical agents get credits first
4. **Team Coordination**: Distribute work based on credit availability
5. **Usage Analytics**: Dashboard for credit consumption patterns

## Technical Details

### File Structure
```
Tmux-Orchestrator/
├── credit_management/
│   ├── credit_monitor.py
│   ├── check_agent_health.sh
│   └── schedule_credit_aware.sh
├── data/
│   └── credit_schedule.json
└── logs/
    └── credit_events.log
```

### Monitoring Daemon
```python
# Runs continuously, checking every 5 minutes
while True:
    for agent in active_agents:
        if check_credit_exhausted(agent):
            pause_agent(agent)
            schedule_resume(agent, next_reset_time())
    sleep(300)  # 5 minutes
```

### Integration Points
- Modifies `auto_orchestrate.py` to include credit monitoring
- Extends `schedule_with_note.sh` with credit awareness
- Updates `CLAUDE.md` with credit management instructions
- Adds credit status to orchestrator's status display
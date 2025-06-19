# Tmux Orchestrator

An AI-powered session management system where Claude acts as the orchestrator for multiple Claude agents across tmux sessions, managing codebases and keeping development moving forward 24/7.

## Overview

The Tmux Orchestrator is designed to monitor, manage, and coordinate multiple development environments running in tmux sessions. It provides intelligent analysis of tmux windows, safe command execution, and automated scheduling to maintain continuous development workflows.

## Core Features

- **Multi-session tmux monitoring**: Track all active tmux sessions and windows
- **Claude AI integration**: Intelligent analysis of window contents and agent activities
- **Safe command execution**: Confirmation layers and safety checks for all operations
- **Background monitoring**: Configurable interval monitoring with graceful shutdown
- **Interactive command interface**: Direct control over sessions and agents
- **Automated scheduling**: Schedule check-ins and maintain continuous orchestration

### New: Project Startup Automation 🚀

- **Automatic project discovery**: Scans ~/Coding for all development projects
- **Framework detection**: Identifies Next.js, FastAPI, Django, React, and more
- **One-command startup**: Launch any project with proper environment setup
- **AI agent briefing**: Claude agents receive project-specific instructions
- **GitHub integration**: Pulls issues and PRs for agent context
- **Health monitoring**: Track agent and server status automatically

## Architecture

### Core Components

1. **`orchestrator.py`**: Main control loop with background monitoring
2. **`tmux_utils.py`**: Core tmux interaction utilities (session/window discovery, content capture, command execution)
3. **`claude_agent.py`**: AI analysis engine for intelligent window content analysis
4. **`claude_control.py`**: Direct control interface for immediate operations
5. **`schedule_with_note.sh`**: Automated scheduling system for continuous operation
6. **`session_registry.py`**: Session tracking and registry management

### New Project Automation Components

7. **`project_startup.py`**: Automated project discovery and setup
8. **`orchestrator_launcher.py`**: Unified interface for all operations
9. **`github_integration.py`**: GitHub issues and PR management
10. **`orchestrator_integration.py`**: Health monitoring and task management
11. **`quick_start.sh`**: Simple command-line interface
12. **`project_configs.json`**: Project-specific configurations

### Safety Features

- **Confirmation required** for all potentially destructive commands
- **Claude pre-analyzes** command safety before execution
- **Read-only monitoring** by default
- **Never automatically closes** windows or sessions
- **Graceful error handling** and recovery mechanisms

## Quick Start

### Project Startup (New!)

```bash
# Launch interactive menu
./quick_start.sh

# List all discovered projects
./quick_start.sh list

# Start a specific project
./quick_start.sh start ai-chat

# Find idle agents
./quick_start.sh idle
```

### Traditional Usage

```bash
# Start the orchestrator with interactive monitoring
python3 orchestrator.py

# Get immediate status of all sessions
python3 claude_control.py summary

# Analyze specific window content
python3 claude_control.py analyze <session> <window> [lines]

# Schedule a check-in (essential for continuous operation)
./schedule_with_note.sh 5 "Check frontend build completion"
```

### Command Interface

Once running, the orchestrator provides these interactive commands:

- `status` - Overview of all sessions/windows
- `projects` - Show all project sessions (New!)
- `analyze` - Latest Claude analysis of all activity
- `window <session>:<index>` - Deep dive into specific window
- `send <session>:<index> <command>` - Execute commands with safety checks
- `find <name>` - Locate windows by name
- `idle` - Find idle agents (New!)
- `suggest <session>` - Get task suggestions (New!)
- `health <session>` - Check project health (New!)
- `interval <seconds>` - Adjust monitoring frequency

## Critical Workflows

### Tmux Window Management

#### Creating Windows Safely
```bash
# Always specify directory when creating windows
tmux new-window -t session -n "window-name" -c "/correct/path"

# Or immediately navigate after creation
tmux new-window -t session -n "window-name"
tmux send-keys -t session:window-name "cd /correct/path" Enter
```

#### Verifying Command Execution
```bash
# Always check output after running commands
tmux send-keys -t session:window "command" Enter
sleep 2  # Give command time to execute
tmux capture-pane -t session:window -p | tail -50
```

### Claude Agent Communication

#### Starting Claude in a Window
```bash
# Check if Claude is already running
tmux capture-pane -t session:window -p | grep -E "Claude|>"

# Start Claude if needed
tmux send-keys -t session:window "claude" Enter
sleep 5  # Wait for startup
tmux capture-pane -t session:window -p | tail -20
```

#### Sending Messages to Claude Agents
```bash
# Send message text first
tmux send-keys -t session:window "Your detailed message here"

# CRITICAL: Wait for Claude's UI to register the text
sleep 1

# Send Enter as separate command
tmux send-keys -t session:window Enter

# Wait for processing and check response
sleep 5
tmux capture-pane -t session:window -p | tail-50
```

**Why the delay is critical**: Claude's interface needs time to register text input before Enter can be processed. Sending Enter too quickly will cause the message to be ignored.

## Orchestrator Advantages

### Multi-Window Intelligence
- **Cross-session visibility**: See all windows across all sessions simultaneously
- **Real-time monitoring**: Spot issues as they happen in logs/servers
- **Pattern recognition**: Notice similar problems across different projects
- **Resource sharing**: Share information between agents working on different codebases

### Proactive Agent Assistance

You can send messages to agents even when they're busy! Messages are queued and agents will see them after completing their current tasks.

#### When to Intervene:
1. **Cross-window intelligence**: You see errors in one window that an agent needs to know about
2. **Steering guidance**: Agent appears stuck or heading in wrong direction
3. **Resource sharing**: You have information from other sessions that would help
4. **Proactive assistance**: Preventing issues before they become blockers

#### Example Interventions:
```bash
# Share error information
"I see in your server window that the API is returning 500 errors for /api/users endpoint"

# Provide cross-project insights  
"The ai-chat session has authentication working with Clerk - might help with your implementation"

# Direct to specific resources
"Check window 3 - the frontend build shows the exact endpoints being called"
```

## Continuous Operation

### Essential: Always Schedule Next Check-in

**NEVER end a conversation without scheduling your return!**

```bash
# Schedule with specific, actionable notes
./schedule_with_note.sh 5 "Check if frontend agent finished endpoint analysis"
./schedule_with_note.sh 10 "Verify backend cleanup completed, no broken endpoints"
./schedule_with_note.sh 15 "Review DuckDB data load progress, check for errors"

# Bad examples (too vague):
# "Victory awaits!"
# "Continue the great work!"
```

### Scheduling Guidelines

- **Quick tasks (2-5 min)**: Check back in 5 minutes
- **Medium tasks (5-15 min)**: Check back in 10-15 minutes  
- **Long tasks (15+ min)**: Check back in 20-30 minutes
- **Overnight tasks**: Check back in 1-2 hours

### Check-in Workflow

When returning from a scheduled check-in:

1. Run `python3 claude_control.py summary` for overall status
2. Check specific windows mentioned in your scheduling note
3. Address any errors or blockers found
4. Coordinate next steps between agents
5. **Schedule your next check-in before leaving**

## Best Practices

### Pre-Command Verification
```bash
# Always verify working directory
tmux send-keys -t session:window "pwd" Enter
tmux capture-pane -t session:window -p | tail -5

# Check command availability
tmux send-keys -t session:window "which command_name" Enter

# Verify virtual environment if needed
tmux send-keys -t session:window "ls -la | grep -E 'venv|env|virtualenv'" Enter
```

### Agent Coordination
1. Always verify agents are ready before cross-communication
2. Use clear, specific messages about what you need
3. Wait for responses before proceeding
4. Document dependencies between projects
5. Specify WHERE you saw information ("in your server window", "from the frontend agent")

### Error Handling
When commands fail:
1. Capture full window output: `tmux capture-pane -t session:window -S -200 -p`
2. Check for common issues:
   - Wrong directory
   - Missing dependencies  
   - Virtual environment not activated
   - Permission issues
   - Port conflicts

## Registry System

The orchestrator maintains persistent state in the `registry/` directory:

- `sessions.json`: Current session tracking
- `orchestrator_log.json`: System status and logs
- `loop_checks.json`: Scheduled check history

## Project Startup Automation

### How It Works

1. **Discovery**: Scans ~/Coding for projects with recognizable patterns
2. **Analysis**: Detects project type, framework, and configuration
3. **Session Creation**: Sets up tmux with standard window layout
4. **Agent Briefing**: Provides context-aware instructions to Claude
5. **Server Startup**: Automatically starts development servers
6. **Monitoring**: Tracks health and suggests tasks for idle agents

### Supported Frameworks

- **Node.js**: Next.js, React, Express, Vue
- **Python**: FastAPI, Django, Flask
- **Others**: Ruby on Rails, Go, Rust (basic support)

### Project Configuration

Customize projects in `project_configs.json`:

```json
{
  "my-project": {
    "auto_start_server": true,
    "briefing": "Focus on authentication implementation",
    "github_integration": {
      "check_issues": true,
      "priority_labels": ["bug", "critical"]
    },
    "monitoring": {
      "check_interval": 300
    }
  }
}
```

## Common Project Patterns

### Development Server Management
```bash
# Backend servers (typical locations and commands)
# Glacier Backend: /Users/jasonedward/Coding/Glacier-Analytics
# Command: uvicorn app.main:app --reload
# Default port: 8000

# Frontend servers: npm run dev
# Default ports: 3000, 3001, etc.
```

### Multi-Agent Coordination
- Monitor server logs in one window while agents debug in others
- Share API endpoint information between frontend and backend agents
- Coordinate authentication implementations across projects
- Track progress on data migrations and builds

## Learning from Mistakes

The orchestrator maintains a growing knowledge base of lessons learned. When errors occur:

1. Document the specific error immediately
2. Identify the root cause
3. Document prevention steps
4. Add verification commands
5. Update this documentation

This continuous learning improves orchestration efficiency and prevents repeated mistakes.

## Safety Considerations

- All potentially destructive operations require confirmation
- Commands are analyzed by Claude before execution
- Monitoring is read-only by default
- Sessions and windows are never closed automatically
- All operations include error handling and recovery mechanisms

## Contributing

When adding new features or fixing issues:

1. Follow the existing safety patterns
2. Add appropriate error handling
3. Update documentation
4. Test with multiple tmux sessions
5. Ensure graceful shutdown works correctly

## Requirements

- Python 3.7+
- tmux
- Claude CLI (for AI analysis features)
- bash (for scheduling scripts)
- GitHub CLI (optional, for issue integration)

---

*This orchestrator enables true 24/7 development coordination, allowing Claude agents to work continuously while maintaining safety and providing intelligent oversight.*
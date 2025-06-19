# Tmux Orchestrator - Project Startup Automation

## Overview

The Project Startup Automation system is a comprehensive solution for automatically discovering, configuring, and launching development projects in tmux sessions with integrated Claude AI agents. It streamlines the process of starting work on any project by handling all the setup automatically.

## Features

### 🔍 **Project Discovery**
- Automatically scans ~/Coding directory for projects
- Detects project types (Node.js, Python, Ruby, Go, etc.)
- Identifies frameworks (Next.js, FastAPI, Django, React, etc.)
- Fuzzy matching for project names

### 🚀 **Automated Startup**
- Creates tmux sessions with standard window layout
- Sets up Claude agent with project-specific briefing
- Configures development environment (virtual envs, etc.)
- Starts development servers automatically

### 🔧 **Smart Configuration**
- Project-specific settings in `project_configs.json`
- Framework-aware startup commands
- Customizable agent briefings
- GitHub integration for issues and PRs

### 📊 **Monitoring & Management**
- Health checking for agents and servers
- Error detection and reporting
- Idle agent identification
- Task suggestion system

## Quick Start

### Using the Quick Start Script

```bash
# Launch interactive menu
./quick_start.sh

# List all projects
./quick_start.sh list

# Start a specific project
./quick_start.sh start ai-chat

# Check session status
./quick_start.sh status

# Find idle agents
./quick_start.sh idle
```

### Using Python Scripts Directly

```bash
# Interactive menu
python3 orchestrator_launcher.py

# Start a project with custom briefing
python3 orchestrator_launcher.py start "project-name" --briefing "Focus on bug fixes"

# Generate monitoring report
python3 orchestrator_launcher.py report
```

## Architecture

### Core Components

1. **`project_startup.py`**
   - Project discovery engine
   - Framework detection
   - Session creation and setup
   - Briefing generation

2. **`github_integration.py`**
   - GitHub CLI integration
   - Issue fetching and prioritization
   - Pull request tracking

3. **`orchestrator_integration.py`**
   - Health monitoring
   - Task management
   - Agent coordination
   - Reporting system

4. **`orchestrator_launcher.py`**
   - Main entry point
   - Interactive menu system
   - Command-line interface

## Project Configuration

Projects can be configured in `project_configs.json`:

```json
{
  "my-project": {
    "auto_start_server": true,
    "briefing": "Custom instructions for the Claude agent",
    "startup_sequence": {
      "shell": ["source venv/bin/activate"],
      "dev-server": ["npm run dev"]
    },
    "github_integration": {
      "check_issues": true,
      "priority_labels": ["bug", "critical"]
    },
    "monitoring": {
      "check_interval": 300,
      "error_patterns": ["ERROR", "FATAL"]
    }
  }
}
```

## Window Layout

Each project session is created with three standard windows:

1. **Window 0: Claude-Agent**
   - Main workspace for Claude AI
   - Receives project briefing
   - Handles development tasks

2. **Window 1: Shell**
   - General command execution
   - Git operations
   - Package management

3. **Window 2: Dev-Server**
   - Development server
   - Build processes
   - Log monitoring

## Agent Briefing System

Claude agents receive comprehensive briefings including:

- Project location and type
- Framework-specific guidelines
- Available windows and their purposes
- Current GitHub issues (if available)
- Custom project instructions

### Framework-Specific Support

The system provides tailored instructions for:
- **Next.js**: Routing, data fetching, configuration
- **FastAPI**: API structure, Pydantic models, uvicorn
- **Django**: Settings, migrations, ORM usage
- **React**: Component structure, state management
- **Express**: Route organization, middleware

## Monitoring Features

### Health Checking
- Agent status: not_started, idle, working, error
- Server status: not_started, starting, running, error
- Error detection in window output
- Success pattern recognition

### Task Management
- Automatic idle agent detection
- Intelligent task suggestions based on:
  - GitHub issues
  - Project type
  - Framework
  - General improvements

### Reporting
- Comprehensive monitoring reports
- Session summaries
- Error aggregation
- Task recommendations

## Advanced Usage

### Custom Project Discovery

```python
from project_startup import ProjectDiscovery

discovery = ProjectDiscovery("~/custom/path")
projects = discovery.discover_projects(max_depth=4)
```

### Manual Project Configuration

```python
from orchestrator_launcher import OrchestratorLauncher

launcher = OrchestratorLauncher()
launcher.startup.add_project_config("my-project", {
    "auto_start_server": False,
    "briefing": "Special instructions here"
})
```

### Monitoring Integration

```python
from orchestrator_integration import OrchestratorProjectManager

manager = OrchestratorProjectManager()

# Start and monitor
result = manager.start_and_monitor_project("my-project")

# Check health
health = manager.check_project_health("my-project")

# Get suggestions
suggestions = manager.suggest_agent_tasks("my-project")
```

## Best Practices

1. **Project Naming**
   - Use clear, descriptive names
   - Avoid special characters
   - Keep names tmux-friendly

2. **Configuration**
   - Configure frequently-used projects
   - Set appropriate monitoring intervals
   - Define project-specific error patterns

3. **Agent Management**
   - Check idle agents regularly
   - Provide clear task descriptions
   - Monitor for errors and blockers

4. **Session Organization**
   - Use consistent window layouts
   - Keep related projects in nearby sessions
   - Clean up inactive sessions

## Troubleshooting

### Common Issues

1. **Project Not Found**
   - Check project is in ~/Coding directory
   - Verify project has recognizable files (package.json, etc.)
   - Try full project name instead of partial

2. **Agent Not Responding**
   - Check if Claude CLI is installed
   - Verify agent window is active
   - Look for errors in window output

3. **Server Won't Start**
   - Check virtual environment activation
   - Verify dependencies are installed
   - Look for port conflicts

### Debug Commands

```bash
# Check tmux sessions
tmux list-sessions

# View window content
tmux capture-pane -t session:window -p

# Check project discovery
python3 project_startup.py list

# Test GitHub integration
python3 github_integration.py /path/to/project
```

## Future Enhancements

- [ ] Database migration detection and handling
- [ ] Test suite integration and automation
- [ ] CI/CD pipeline status monitoring
- [ ] Multi-agent collaboration features
- [ ] Project dependency visualization
- [ ] Automated code review assistance
- [ ] Performance profiling integration

## Contributing

When adding new features:
1. Update framework detection in `project_startup.py`
2. Add briefing templates for new frameworks
3. Update monitoring patterns
4. Test with various project types
5. Document configuration options

## Summary

The Project Startup Automation system transforms the way you work with multiple projects by:
- Eliminating manual setup steps
- Providing consistent environments
- Enabling AI-assisted development
- Maintaining project health
- Suggesting productive tasks

Start using it today with `./quick_start.sh` and experience automated project management!
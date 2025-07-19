# Auto-Orchestrate Documentation

## Overview

The `auto_orchestrate.py` script provides fully automated setup of a Tmux Orchestrator environment from a specification file. It analyzes your project requirements using Claude and automatically configures a complete team of AI agents to implement your specification.

## Features

- **Intelligent Spec Analysis**: Uses Claude to understand your requirements
- **Structured Planning**: Generates phase-based implementation plans
- **Automatic Role Assignment**: Configures specialized agents for different tasks
- **One-Command Setup**: From spec to running team in under a minute
- **Progress Tracking**: Saves implementation plans for reference

## Installation

The script uses UV for dependency management and automatically sets up the Tmux Orchestrator environment.

```bash
# Clone the repository
git clone https://github.com/yourusername/Tmux-Orchestrator.git
cd Tmux-Orchestrator

# Run directly - everything is handled automatically!
./auto_orchestrate.py --help
```

On first run, the script will:
1. Run the setup process automatically
2. Create necessary directories
3. Check for required dependencies
4. Make all scripts executable

## Usage

### Basic Command

```bash
./auto_orchestrate.py \
  --project /path/to/your/project \
  --spec /path/to/specification.md
```

### Example

```bash
./auto_orchestrate.py \
  --project /home/user/myapp \
  --spec /home/user/myapp/docs/new_feature_spec.md
```

## How It Works

### 1. Context Priming (Optional)

If your project has a `.claude/commands/context-prime.md` file:
- The script runs `/context-prime` to help Claude understand the project structure
- This command is executed in the project directory
- Allows Claude to analyze dependencies, conventions, and architecture

If no context-prime command exists, the script continues without it.

### 2. Specification Analysis

The script sends your specification to Claude with a structured prompt requesting:
- Project type and technology stack identification
- Phase-based implementation breakdown
- Time estimates for each phase
- Role-specific responsibilities
- Success criteria extraction

### 2. Implementation Plan Generation

Claude returns a JSON structure containing:

```json
{
  "project": {
    "name": "Project Name",
    "path": "/path/to/project",
    "type": "python",
    "main_tech": ["django", "react", "postgresql"]
  },
  "implementation_plan": {
    "phases": [
      {
        "name": "Setup & Analysis",
        "duration_hours": 2.0,
        "tasks": ["Task 1", "Task 2"]
      }
    ],
    "total_estimated_hours": 12.0
  },
  "roles": {
    "orchestrator": { ... },
    "project_manager": { ... },
    "developer": { ... },
    "tester": { ... }
  },
  "git_workflow": { ... },
  "success_criteria": [ ... ]
}
```

### 3. User Approval

The plan is displayed in a formatted table showing:
- Project overview and technologies
- Implementation phases with time estimates
- Role assignments and responsibilities
- Git workflow configuration
- Success criteria

### 4. Tmux Session Creation

Upon approval, the script:
1. Creates a new tmux session named `{project}-impl`
2. Sets up 4 windows: Orchestrator, Project-Manager, Developer, Tester
3. Starts Claude in each window
4. Runs `/context-prime` for each agent (except Orchestrator) to understand the project
5. Sends role-specific briefings
6. Configures scheduled check-ins

## Role Descriptions

### Orchestrator
- **Location**: Window 0, Tmux-Orchestrator directory
- **Responsibilities**: High-level oversight, coordination, blocker resolution
- **Check-ins**: Every 30 minutes
- **Tools**: claude_control.py for status monitoring

### Project Manager
- **Location**: Window 1, Project directory
- **Responsibilities**: Quality assurance, progress tracking, team coordination
- **Check-ins**: Every 30 minutes
- **Focus**: Maintaining exceptional standards

### Developer
- **Location**: Window 2, Project directory  
- **Responsibilities**: Implementation, testing, documentation
- **Check-ins**: Every 60 minutes
- **Git**: Creates feature branch, commits every 30 minutes

### Tester
- **Location**: Window 3, Project directory
- **Responsibilities**: Test execution, coverage tracking, regression prevention
- **Check-ins**: Every 45 minutes
- **Integration**: Works closely with Developer

## Writing Effective Specifications

For best results, your specification should include:

1. **Clear Objectives**: What needs to be built/fixed/improved
2. **Technical Context**: Current architecture, constraints
3. **Success Criteria**: Measurable outcomes
4. **Priorities**: What's most important
5. **Non-goals**: What NOT to do

### Example Specification Structure

```markdown
# Feature: User Authentication System

## Objective
Implement secure user authentication with JWT tokens

## Current State
- Basic Django app with no authentication
- PostgreSQL database configured
- React frontend ready for integration

## Requirements
1. User registration with email verification
2. Login/logout with JWT tokens
3. Password reset functionality
4. Admin user management

## Technical Constraints
- Must use existing User model
- Follow REST API conventions
- Maintain backward compatibility

## Success Criteria
- All endpoints have tests with >90% coverage
- Authentication works with React frontend
- Security best practices implemented
- Documentation complete
```

## Advanced Usage

### Resuming Sessions

Implementation specs are saved to:
```
registry/projects/{project-name}/implementation_spec.json
```

To resume or check on a session:
```bash
tmux attach -t {project-name}-impl
```

### Monitoring Progress

From the orchestrator window:
```bash
python3 claude_control.py status detailed
```

### Custom Configuration

Edit the generated briefings by modifying the `create_role_briefing` method in the script.

## First-Time Setup

When you first clone the repository and run `auto_orchestrate.py`, it will:

1. **Check for config.local.sh** - If missing, runs setup automatically
2. **Create directories** - Sets up registry/logs, registry/notes, registry/projects
3. **Make scripts executable** - Ensures all .sh and .py files can be run
4. **Check dependencies** - Verifies tmux, Claude CLI, Python, and UV are installed
5. **Provide installation help** - Shows commands to install any missing dependencies

No manual setup required - just clone and run!

## Troubleshooting

### Claude Timeout
If Claude takes too long to analyze the spec:
- Break down large specifications into phases
- Simplify technical requirements
- The script now uses 120s timeout for context priming

### Tmux Errors
If tmux session creation fails:
- Check if session already exists: `tmux ls`
- Kill existing: `tmux kill-session -t {name}-impl`
- Ensure tmux is installed: `tmux -V`

### Missing Dependencies
The script uses UV for automatic dependency management. If issues occur:
```bash
# Install UV first
curl -LsSf https://astral.sh/uv/install.sh | sh

# Then run the script
./auto_orchestrate.py --help
```

## Best Practices

1. **Start Small**: Test with simple specifications first
2. **Monitor Early**: Check on agents frequently in the first hour
3. **Adjust Check-ins**: Modify intervals based on project complexity
4. **Trust but Verify**: Agents are capable but benefit from guidance
5. **Use Git Discipline**: Ensure all agents commit regularly

## Limitations

- Requires Claude CLI to be configured
- Claude CLI v1.0.24+ recommended for context priming features
- Best for projects with clear specifications
- May need manual intervention for complex dependencies
- Limited to 4 predefined roles (can be extended)

### Claude Code Compatibility

This script is designed to work with Claude Code (not the deprecated Claude CLI):
- Uses `claude -p` for non-interactive prompts
- Supports slash commands if defined in `.claude/commands/`
- Context priming works if your project has `.claude/commands/context-prime.md`

To check your version: `claude --version`

## Future Enhancements

Planned improvements:
- Support for custom roles
- Integration with CI/CD pipelines
- Progress dashboard
- Automatic error recovery
- Multi-project orchestration
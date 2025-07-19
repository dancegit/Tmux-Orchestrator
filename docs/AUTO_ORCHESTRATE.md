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

The script uses UV for dependency management. No installation needed - just run it!

```bash
# Make executable (if not already)
chmod +x auto_orchestrate.py

# Run directly - UV handles dependencies
./auto_orchestrate.py --help
```

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

### 1. Specification Analysis

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
4. Sends role-specific briefings
5. Configures scheduled check-ins

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

## Troubleshooting

### Claude Timeout
If Claude takes too long to analyze the spec:
- Break down large specifications into phases
- Simplify technical requirements
- Increase timeout in script (default: 60s)

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
- Best for projects with clear specifications
- May need manual intervention for complex dependencies
- Limited to 4 predefined roles (can be extended)

## Future Enhancements

Planned improvements:
- Support for custom roles
- Integration with CI/CD pipelines
- Progress dashboard
- Automatic error recovery
- Multi-project orchestration
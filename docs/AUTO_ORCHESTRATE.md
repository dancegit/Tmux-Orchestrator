# Auto-Orchestrate Documentation

## Overview

The `auto_orchestrate.py` script provides fully automated setup of a Tmux Orchestrator environment from a specification file. It analyzes your project requirements using Claude and automatically configures a complete team of AI agents to implement your specification.

## Features

- **Intelligent Spec Analysis**: Uses Claude to understand your requirements
- **Structured Planning**: Generates phase-based implementation plans
- **Automatic Role Assignment**: Configures specialized agents for different tasks
- **Git Worktree Isolation**: Each agent works in their own git worktree to prevent conflicts
- **Dynamic Team Composition**: Adjusts team size based on project complexity
- **One-Command Setup**: From spec to running team in under a minute
- **Progress Tracking**: Saves implementation plans for reference

## Installation

All Python scripts in this project use UV for dependency management with inline script dependencies.

```bash
# Install UV first (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/yourusername/Tmux-Orchestrator.git
cd Tmux-Orchestrator

# Run directly - UV handles dependencies automatically!
./auto_orchestrate.py --help
```

**Important**: Make sure you're using Claude Code (not the old Claude CLI). The script uses `/usr/bin/claude` to avoid conflicts with any Python packages named 'claude'.

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

### Advanced Options

```bash
# Manually specify project size
./auto_orchestrate.py \
  --project /path/to/project \
  --spec spec.md \
  --size large

# Add specific roles
./auto_orchestrate.py \
  --project /path/to/project \
  --spec spec.md \
  --roles researcher \
  --roles documentation_writer
```

### Example

```bash
./auto_orchestrate.py \
  --project /home/user/myapp \
  --spec /home/user/myapp/docs/new_feature_spec.md

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
  "project_size": {
    "size": "small|medium|large",
    "estimated_loc": 1000,
    "complexity": "low|medium|high"
  },
  "roles": {
    "orchestrator": { ... },
    "project_manager": { ... },
    "developer": { ... },
    "tester": { ... },
    "devops": { ... },
    "code_reviewer": { ... },
    "researcher": { ... },
    "documentation_writer": { ... }
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

### 4. Git Worktree Setup

The script creates isolated git worktrees for each agent:
```
Tmux-Orchestrator/
└── registry/
    └── projects/
        └── {project-name}/
            └── worktrees/
                ├── project-manager/
                ├── developer/
                ├── tester/
                └── devops/
```

### 5. Tmux Session Creation

Upon approval, the script:
1. Creates a new tmux session named `{project}-impl`
2. Sets up windows based on project size:
   - **Small**: Orchestrator, PM, Developer
   - **Medium**: + Tester + Second Developer
   - **Large**: + DevOps + Code Reviewer
3. Each agent works in their own git worktree (except Orchestrator)
4. Starts Claude in each window
5. Ensures each worktree has a CLAUDE.md referencing orchestrator rules
6. Runs `/context-prime` for each agent (if available)
7. Sends role-specific briefings with mandatory rule reading
8. Configures scheduled check-ins

## Role Descriptions

### Core Roles (Always Deployed)

#### Orchestrator
- **Location**: Window 0, Tmux-Orchestrator directory
- **Worktree**: None (stays in orchestrator directory)
- **Responsibilities**: High-level oversight, coordination, blocker resolution
- **Check-ins**: Every 30 minutes
- **Tools**: claude_control.py for status monitoring

#### Project Manager
- **Location**: Window 1, Own git worktree
- **Worktree**: `registry/projects/{name}/worktrees/project_manager/`
- **Responsibilities**: Quality assurance, progress tracking, team coordination
- **Check-ins**: Every 30 minutes
- **Focus**: Maintaining exceptional standards, coordinating merges between worktrees

### Development Roles (Based on Project Size)

#### Developer
- **Location**: Window 2+, Own git worktree
- **Worktree**: `registry/projects/{name}/worktrees/developer/`
- **Responsibilities**: Implementation, testing, documentation
- **Check-ins**: Every 60 minutes
- **Git**: Creates feature branch, commits every 30 minutes

#### Tester (Medium/Large Projects)
- **Location**: Own git worktree
- **Worktree**: `registry/projects/{name}/worktrees/tester/`
- **Responsibilities**: Test execution, coverage tracking, regression prevention
- **Check-ins**: Every 45 minutes
- **Integration**: Works closely with Developer

#### DevOps (Large Projects)
- **Location**: Own git worktree
- **Worktree**: `registry/projects/{name}/worktrees/devops/`
- **Responsibilities**: Infrastructure setup, deployment pipelines, monitoring
- **Check-ins**: Every 90 minutes

#### Code Reviewer (Large Projects)
- **Location**: Own git worktree
- **Worktree**: `registry/projects/{name}/worktrees/code_reviewer/`
- **Responsibilities**: Code quality, security audit, best practices
- **Check-ins**: Every 120 minutes

### Optional Roles (Via --roles flag)

#### Researcher
- **Responsibilities**: Technology evaluation, solution research, documentation
- **Check-ins**: Every 120 minutes

#### Documentation Writer
- **Responsibilities**: Technical docs, README updates, API documentation
- **Check-ins**: Every 120 minutes

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

### Git Worktree Management

Each agent works in their own git worktree to prevent conflicts:

```bash
# View all worktrees from the main project
cd /path/to/project
git worktree list

# Access a specific agent's worktree
cd ~/Tmux-Orchestrator/registry/projects/{project-name}/worktrees/developer/

# Clean up worktrees after project completion
git worktree remove ~/Tmux-Orchestrator/registry/projects/{project-name}/worktrees/developer/
```

### Resuming Sessions

Implementation specs and worktrees are saved to:
```
registry/projects/{project-name}/
├── implementation_spec.json
└── worktrees/
    ├── project_manager/
    ├── developer/
    └── tester/
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

### Git Repository Required
The project must be a git repository:
```bash
cd /path/to/project
git init  # If not already a repo
```

### Worktree Conflicts
If you see "branch already checked out" errors:
- The script will automatically create detached worktrees
- Each agent can then create their own feature branch

### Claude Timeout
If Claude takes too long to analyze the spec:
- Break down large specifications into phases
- Simplify technical requirements
- The script now uses 360s timeout for combined context priming + analysis

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

1. **Git Repository**: Ensure your project is a git repository before running
2. **Start Small**: Test with simple specifications first
3. **Monitor Early**: Check on agents frequently in the first hour
4. **Adjust Check-ins**: Modify intervals based on project complexity
5. **Trust but Verify**: Agents are capable but benefit from guidance
6. **Use Git Discipline**: Ensure all agents commit regularly
7. **Coordinate Merges**: Let the PM coordinate merges between agent worktrees
8. **Clean Up**: Remove worktrees when project is complete

## Limitations

- Requires project to be a git repository
- Requires Claude Code to be configured
- Claude Code v1.0.24+ recommended for context priming features
- Best for projects with clear specifications
- May need manual intervention for complex dependencies
- Disk space usage increases with worktrees (but less than full clones)

### Claude Code Compatibility

This script is designed to work with Claude Code (not the deprecated Claude CLI):
- Uses `claude --dangerously-skip-permissions` for non-interactive automation
- Supports slash commands if defined in `.claude/commands/`
- Context priming works if your project has `.claude/commands/context-prime.md`
- Requires Claude Code 1.0.24+ for best results

To check your version: `claude --version`

**Note**: The script uses the `--dangerously-skip-permissions` flag to allow non-interactive execution. This is required for automation but means Claude will execute without the usual safety prompts.

## Key Innovations

### Git Worktree Architecture
Each agent works in isolation, preventing the common problem of agents overwriting each other's changes. This enables true parallel development with clean merges coordinated by the PM.

### Mandatory Rule System
Every agent's worktree gets a CLAUDE.md file that references the Tmux-Orchestrator rules, ensuring consistent behavior across all agents regardless of project location.

### Dynamic Team Sizing
- **Small projects** (< 500 LOC): Minimal team for quick tasks
- **Medium projects** (500-5000 LOC): Added QA and second developer
- **Large projects** (> 5000 LOC): Full team with specialized roles

## Future Enhancements

Planned improvements:
- Automatic worktree cleanup on project completion
- Support for custom roles via configuration
- Integration with CI/CD pipelines
- Progress dashboard
- Automatic error recovery
- Multi-project orchestration
- Worktree merge conflict resolution assistance
# Auto-Orchestrate Documentation (Modular System v2.0)

## Overview

The `tmux_orchestrator_cli.py run` command provides fully automated setup of a Tmux Orchestrator environment from a specification file. It analyzes your project requirements using Claude and automatically configures a complete team of AI agents to implement your specification.

## Features

- **Intelligent Spec Analysis**: Uses Claude to understand your requirements
- **Structured Planning**: Generates phase-based implementation plans
- **Automatic Role Assignment**: Configures specialized agents for different tasks
- **Git Worktree Isolation**: Each agent works in their own git worktree to prevent conflicts
- **MCP Tool Discovery**: Automatically detects and categorizes available MCP servers
- **Role-Based Tool Guidance**: Provides specific MCP recommendations for each agent role
- **Cross-Worktree File Sharing**: Enables agents to share resources via main project directory
- **🚀 Fast Lane Coordination**: Automatic 9x faster Developer→Tester→TestRunner workflows (8 min vs 75 min)
- **Event-Driven Triggers**: Post-commit hooks for immediate downstream notifications
- **Plan-Based Team Sizing**: Optimizes team size for your Claude subscription
- **Token Conservation**: Adjusted intervals and warnings for sustainable usage
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
./tmux_orchestrator_cli.py run --help
```

**Important**: Make sure you're using Claude Code (not the old Claude CLI). The script uses `/usr/bin/claude` to avoid conflicts with any Python packages named 'claude'.

On first run, the script will:
1. Run the setup process automatically
2. Create necessary directories
3. Check for required dependencies
4. Make all scripts executable
5. 🚀 **Set up Fast Lane Coordination** (if developer/tester/testrunner roles detected)
   - Install post-commit hooks in agent worktrees
   - Enable automatic git sync between agents
   - Configure event-driven triggers for 9x faster workflows

## Usage

### Basic Command

```bash
./tmux_orchestrator_cli.py run \
  --project /path/to/your/project \
  --spec /path/to/specification.md
```

### Advanced Options

```bash
# Manually specify project size
./tmux_orchestrator_cli.py run \
  --project /path/to/project \
  --spec spec.md \
  --size large

# Add specific roles
./tmux_orchestrator_cli.py run \
  --project /path/to/project \
  --spec spec.md \
  --roles researcher \
  --roles documentation_writer

# Force overwrite existing session/worktrees
./tmux_orchestrator_cli.py run \
  --project /path/to/project \
  --spec spec.md \
  --force

# Specify subscription plan (affects team size)
./tmux_orchestrator_cli.py run \
  --project /path/to/project \
  --spec spec.md \
  --plan max5  # Options: pro, max5, max20, console
```

### Example

```bash
./tmux_orchestrator_cli.py run \
  --project /home/user/myapp \
  --spec /home/user/myapp/docs/new_feature_spec.md

## Safety Features

### Existing Session Detection

The script automatically detects:
- Existing tmux sessions with the same name
- Existing git worktrees from previous runs

When detected, you'll be prompted with options:
1. **Overwrite** - Remove existing session/worktrees and start fresh
2. **Resume** - Attach to existing session (preserves worktrees)
3. **Cancel** - Exit without making changes

Use the `--force` flag to automatically overwrite without prompting.

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
                ├── orchestrator/      # Orchestrator's project workspace
                ├── project-manager/
                ├── developer/         # 🚀 Fast lane enabled
                ├── researcher/        # Researcher's workspace (core role)
                ├── tester/           # 🚀 Fast lane enabled
                └── devops/
```

**🚀 Fast Lane Coordination**: Automatically enabled for developer/tester/testrunner workflows:
- **Post-commit hooks** installed in eligible worktrees
- **Event-driven sync** replaces polling (Developer → Tester → TestRunner)  
- **9x faster cycles**: 75 minutes → 8 minutes for full development-test-execution workflow
- **Conflict escalation** to PM for seamless coordination
- **Audit logging** to `registry/logs/fast-lane/` for monitoring

### 5. Tmux Session Creation

Upon approval, the script:
1. Creates a new tmux session named `{project}-impl`
2. Sets up windows based on project size (OPTIMIZED FOR MAX 5X PLAN):
   - **Small**: 3 agents (Orchestrator, Developer, Researcher)
   - **Medium**: 4 agents (+ Project Manager)
   - **Large**: 5 agents (+ Tester or DevOps)
3. Each agent works in their own git worktree (including Orchestrator)
4. Starts Claude in each window
5. Ensures each worktree has a CLAUDE.md referencing orchestrator rules
6. Runs `/context-prime` for each agent (if available)
7. Sends role-specific briefings with mandatory rule reading
8. 🚀 **Briefs agents about Fast Lane capabilities** (developer/tester/testrunner)
9. Configures scheduled check-ins (20-60 min intervals for better progression)

## Role Descriptions

### Core Roles (Always Deployed)

#### Orchestrator
- **Location**: Window 0, Project worktree
- **Worktree**: `{project_path}-tmux-worktrees/orchestrator/` (sibling to project, NOT in registry)
- **Tool Directory**: Tmux-Orchestrator root (for running tools)
- **Responsibilities**: High-level oversight, coordination, blocker resolution
- **Check-ins**: Every 20 minutes
- **Workflow**: 
  - Works in project worktree for all project files
  - Switches to tool directory to run orchestrator commands
- **Tools**: claude_control.py, send-claude-message.sh, schedule_with_note.sh

#### Project Manager
- **Location**: Window 1, Own git worktree
- **Worktree**: `{project_path}-tmux-worktrees/project_manager/` (sibling to project)
- **Responsibilities**: Quality assurance, progress tracking, team coordination
- **Check-ins**: Every 25 minutes
- **Focus**: Maintaining exceptional standards, coordinating merges between worktrees

#### Developer
- **Location**: Own git worktree
- **Worktree**: `{project_path}-tmux-worktrees/developer/` (sibling to project)
- **Responsibilities**: Implementation, testing, documentation
- **Check-ins**: Every 30 minutes
- **Git**: Creates feature branch, commits every 30 minutes

#### Tester (Medium/Large Projects)
- **Location**: Own git worktree
- **Worktree**: `{project_path}-tmux-worktrees/tester/` (sibling to project)
- **Responsibilities**: Test execution, coverage tracking, regression prevention
- **Check-ins**: Every 30 minutes
- **Integration**: Works closely with Developer

#### DevOps (Large Projects)
- **Location**: Own git worktree
- **Worktree**: `{project_path}-tmux-worktrees/devops/` (sibling to project)
- **Responsibilities**: Infrastructure setup, deployment pipelines, monitoring
- **Check-ins**: Every 45 minutes

#### Code Reviewer (Large Projects)
- **Location**: Own git worktree
- **Worktree**: `{project_path}-tmux-worktrees/code_reviewer/` (sibling to project)
- **Responsibilities**: Code quality, security audit, best practices
- **Check-ins**: Every 40 minutes

#### Researcher (Core Role)
- **Location**: Own git worktree
- **Worktree**: `{project_path}-tmux-worktrees/researcher/` (sibling to project)
- **Responsibilities**: 
  - MCP tool discovery and utilization
  - Research best practices and security vulnerabilities
  - Performance optimization research
  - Create actionable recommendations
- **Check-ins**: Every 25 minutes
- **Special Features**:
  - Reads `{project}/mcp-inventory.md` created by Orchestrator
  - Types `@` to discover available MCP resources
  - Types `/` to discover MCP commands (format: `/mcp__servername__promptname`)
  - Leverages web search, firecrawl, puppeteer, etc. based on availability
  - Documents available tools in `research/available-tools.md`
  - Creates structured research documents in worktree

### Optional Roles (Via --roles flag)

#### Documentation Writer
- **Responsibilities**: Technical docs, README updates, API documentation
- **Check-ins**: Every 60 minutes

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

## Resume Functionality

### Resuming Existing Orchestrations

The auto-orchestrate script now supports intelligent resume of existing orchestration sessions:

```bash
# Basic resume - restarts dead agents and re-briefs all
./tmux_orchestrator_cli.py run --project /path/to/project --resume

# Check status only without making changes
./tmux_orchestrator_cli.py run --project /path/to/project --resume --status-only

# Resume with forced re-briefing of all agents
./tmux_orchestrator_cli.py run --project /path/to/project --resume --rebrief-all
```

### How Resume Works

1. **Session State Tracking**: The system saves session state after initial setup
   - Agent roles and window assignments
   - Worktree paths for each agent
   - Implementation spec location
   - Git branch information

2. **Agent Health Detection**: On resume, the system checks each agent:
   - ✓ Active: Claude is responsive
   - ✗ Dead: Window exists but Claude not responding
   - ⚠️ Exhausted: Credit limit reached

3. **Smart Recovery Options**:
   - Restart dead agents with full briefing
   - Re-brief active agents with context restoration
   - Handle credit-exhausted agents gracefully

4. **Context Restoration**: Re-briefed agents receive:
   - Role reminders
   - Current branch and worktree info
   - Instructions to check recent work
   - Coordination reminders

### Resume Scenarios

#### Scenario 1: Credit Exhaustion
```bash
# Check status when agents are exhausted
./tmux_orchestrator_cli.py run --project /path/to/project --resume --status-only

# Output shows exhausted agents with reset times
# System will suggest using credit_monitor.py for auto-resume
```

#### Scenario 2: Terminal Crash
```bash
# Resume after terminal/system crash
./tmux_orchestrator_cli.py run --project /path/to/project --resume

# Choose option 3 (Both) to restart dead agents and re-brief all
```

#### Scenario 3: Context Loss
```bash
# When agents have used /compact and lost context
./tmux_orchestrator_cli.py run --project /path/to/project --resume --rebrief-all

# All agents receive context restoration messages
```

### Session State Location

Session states are saved in:
```
registry/projects/{project-name}/session_state.json
```

This file contains:
- Session and agent metadata
- Last briefing times
- Git status for each worktree
- Credit exhaustion tracking

## Advanced Usage

### Git Worktree Management

Each agent works in their own git worktree to prevent conflicts:

```bash
# View all worktrees from the main project
cd /path/to/project
git worktree list

# Access a specific agent's worktree (remember: worktrees are siblings to project!)
cd {project_path}-tmux-worktrees/developer/
# Example: If project is at /home/user/myproject, worktree is at /home/user/myproject-tmux-worktrees/developer/

# Verify worktree locations
git worktree list

# Clean up worktrees after project completion
git worktree remove {project_path}-tmux-worktrees/developer/
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

### Worktree Creation Strategies
The script uses multiple fallback strategies to handle worktree creation:

1. **Normal Creation**: Standard worktree with current branch
2. **Force Flag**: Overrides safety checks if branch is already checked out
3. **Agent-Specific Branches**: Creates `{branch}-{role}` branches for each agent
4. **Detached HEAD**: Falls back to detached worktree at current commit

This ensures the script works regardless of your repository's current state:
- Works with already checked-out branches
- Handles multiple simultaneous orchestrations
- Provides proper isolation for each agent
- Cleans up agent-specific branches on completion

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
./tmux_orchestrator_cli.py run --help
```

## Token Usage and Plan Optimization

### Understanding Multi-Agent Token Consumption

Multi-agent systems use approximately **15x more tokens** than standard Claude usage. This means:

- **Pro Plan**: Best with 2-3 agents max
- **Max 5x Plan**: Optimal with 3-4 agents (5 max)
- **Max 20x Plan**: Can comfortably run 5-6 agents

### Check-in Intervals for Better Progression

1. **Optimized Check-in Times**:
   - Orchestrator: 20 min (frequent oversight)
   - Project Manager: 25 min (active coordination)
   - Developer: 30 min (regular progress)
   - Tester: 30 min (synced with developer)
   - Researcher: 25 min (timely support)
   - Code Reviewer: 40 min (regular reviews)
   - DevOps: 45 min (infrastructure pace)
   - Documentation: 60 min (documentation cycles)

2. **Team Size Limits**:
   - Automatic enforcement based on plan
   - Warning when exceeding recommended sizes
   - Prioritized role selection when limited

3. **Usage Monitoring**:
   - Token usage warnings for 4+ agents
   - Estimated messages per session displayed
   - Recommendations for plan upgrades when needed

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

### Cross-Worktree Communication
- All agents receive team worktree locations in their briefings
- Shared files (like `mcp-inventory.md`) are created in the main project directory
- Agents can read files from other agents' worktrees when needed
- Clear file paths are communicated to ensure agents can find shared resources

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
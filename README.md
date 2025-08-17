![Orchestrator Hero](/Orchestrator.png)

**Run AI agents 24/7 while you sleep** - The Tmux Orchestrator enables Claude agents to work autonomously, schedule their own check-ins, and coordinate across multiple projects without human intervention.

## 🤖 Key Capabilities & Autonomous Features

- **Self-trigger** - Agents schedule their own check-ins and continue work autonomously
- **Coordinate** - Project managers assign tasks to engineers across multiple codebases  
- **Persist** - Work continues even when you close your laptop
- **Scale** - Run multiple teams working on different projects simultaneously

## 🏗️ Architecture

The Tmux Orchestrator uses a streamlined architecture with focused roles:

```
┌─────────────┐
│ Orchestrator│ ← You interact here
└──────┬──────┘
       │ Monitors & coordinates
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Developer  │     │   Tester    │     │ TestRunner  │
└─────────────┘     └─────────────┘     └─────────────┘
 ↑ Write code        ↑ Create tests       ↑ Execute tests
```

### Why Separate Agents?
- **Limited context windows** - Each agent stays focused on its role
- **Specialized expertise** - Each role has focused responsibilities
- **Parallel work** - Multiple engineers can work simultaneously
- **Better memory** - Smaller contexts mean better recall

## 📸 Examples in Action

### Agent Coordination
![Agent Coordination](Examples/Initiate%20Project%20Manager.png)
*The orchestrator coordinating with specialized agents*

### Status Reports & Monitoring
![Status Reports](Examples/Status%20reports.png)
*Real-time status updates from multiple agents working in parallel*

### Tmux Communication
![Reading TMUX Windows and Sending Messages](Examples/Reading%20TMUX%20Windows%20and%20Sending%20Messages.png)
*How agents communicate across tmux windows and sessions*

### Project Completion
![Project Completed](Examples/Project%20Completed.png)
*Successful project completion with all tasks verified and committed*

## 🔧 Setup & Prerequisites

### Prerequisites
- tmux installed on your system
- Claude Code (`claude` command available) - NOT the old Claude CLI
- Python 3.11+ (for utilities)
- UV (for Python script management) - **Required for all Python scripts**
- Basic familiarity with tmux commands

**Important**: All Python scripts use UV shebangs for zero-dependency execution. Install UV with:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/dancegit/Tmux-Orchestrator.git
   cd Tmux-Orchestrator
   ```

2. **Run the setup script**
   ```bash
   ./setup.sh
   ```
   
   This will:
   - Create a local configuration file
   - Set up your projects directory path
   - Create necessary directories
   - Check dependencies
   - Make scripts executable

3. **Configure your projects directory** (if needed)
   
   Edit `config.local.sh` to set your projects directory:
   ```bash
   export PROJECTS_DIR="$HOME/your-projects-folder"
   ```

## 🚀 Main Scripts Overview

### Core Orchestration Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| **`auto_orchestrate.py`** | Automated setup from specifications | Starting new projects with a spec file |
| **`send-claude-message.sh`** | Send messages to Claude agents | Communicating with any agent |
| **`schedule_with_note.sh`** | Schedule agent check-ins | Setting up recurring tasks |
| **`monitoring_dashboard.py`** | Real-time web dashboard | Monitoring system health |

### Management & Monitoring Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| **`claude_control.py`** | Agent status monitoring | Check what agents are doing |
| **`sync_dashboard.py`** | Sync status dashboard | Monitor git synchronization |
| **`multi_project_monitor.py`** | Multi-project overview | Managing multiple orchestrations |
| **`performance_tuner.py`** | Performance optimization | System tuning and cleanup |

### Advanced Features

| Script | Purpose | When to Use |
|--------|---------|-------------|
| **`dynamic_team.py`** | Dynamic team composition | Automatic role selection |
| **`ai_team_refiner.py`** | AI-powered team optimization | Refining team composition |
| **`concurrent_orchestration.py`** | Concurrent project management | Running multiple projects |
| **`scheduler.py`** | Task scheduling daemon | Background task management |

### Testing & Validation

| Script | Purpose | When to Use |
|--------|---------|-------------|
| **`test_integration.py`** | Integration testing | Validating system components |
| **`chaos_tester.py`** | Resilience testing | Testing failure recovery |
| **`load_tester.py`** | Load testing | Capacity validation |

## 🎯 Quick Start

### Option 1: Automated Setup (Recommended) 🌟

```bash
# One command to go from spec to running AI team!
./auto_orchestrate.py --project /path/to/project --spec /path/to/spec.md

# Resume an interrupted orchestration
./auto_orchestrate.py --project /path/to/project --resume

# With custom team size based on your Claude plan
./auto_orchestrate.py --project /path/to/project --spec spec.md --plan max5
```

### Option 2: Basic Setup (Single Project)

```bash
# 1. Create a project spec
cat > project_spec.md << 'EOF'
PROJECT: My Web App
GOAL: Add user authentication system
CONSTRAINTS:
- Use existing database schema
- Follow current code patterns  
- Commit every 30 minutes
- Write tests for new features

DELIVERABLES:
1. Login/logout endpoints
2. User session management
3. Protected route middleware
EOF

# 2. Start tmux session
tmux new-session -s my-project

# 3. Start project manager in window 0
claude

# 4. Give Developer the spec directly
"You are a Developer. Read project_spec.md and implement it.
Work with the Tester in window 2 for test coverage.
Schedule check-ins every 30 minutes."

# 5. Schedule orchestrator check-in
./schedule_with_note.sh 30 "Check Developer progress on auth system"
```

### Option 3: Manual Full Orchestrator Setup

```bash
# Start the orchestrator
tmux new-session -s orchestrator
claude

# Give it your projects
"You are the Orchestrator. Set up project managers for:
1. Frontend (React app) - Add dashboard charts
2. Backend (FastAPI) - Optimize database queries
Schedule yourself to check in every hour."
```

## ✨ Key Features

### 🚀 Auto-Orchestrate: Spec to Implementation
The `auto_orchestrate.py` script provides fully automated setup:
- **Zero Configuration**: Clone and run - automatic setup on first use
- **Context-Aware**: Uses `/context-prime` to understand your project before planning
- **Spec Analysis**: Claude analyzes your markdown specifications intelligently
- **Dynamic Team Composition**: Automatically selects appropriate roles based on project type
- **Git Worktree Isolation**: Each agent works in isolated git worktree to prevent conflicts
- **Resume Capability**: Intelligently resume interrupted orchestrations
- **Credit Management**: Automatic handling of Claude Code usage limits with pause/resume

### 🎯 Dynamic Team System
- **Automatic Role Selection**: Detects project type and deploys appropriate specialists
- **System Operations Roles**: SysAdmin, SecurityOps, NetworkOps for deployments
- **AI-Powered Refinement**: Optional AI analysis to optimize team composition
- **Flexible Sizing**: Adapts team size to your Claude subscription plan

### 📊 Advanced Monitoring & Testing
- **Real-Time Dashboard**: Web-based monitoring interface at `monitoring_dashboard.py`
- **Performance Tuning**: System optimization with `performance_tuner.py`
- **Chaos Testing**: Resilience validation with controlled failures
- **Load Testing**: Validate capacity for 20+ concurrent orchestrations
- **Integration Testing**: Comprehensive test suite for all components

### 🔄 Self-Scheduling & Coordination
- **Automatic Check-ins**: Agents schedule their own follow-ups
- **Fast Lane Coordination**: Reduced Developer→Tester cycle from 45min to 5min
- **Git Synchronization**: Automated worktree syncing with conflict detection
- **Multi-Project Support**: Manage multiple projects simultaneously

### 💾 Git Safety & Workflow
- **Branch Protection**: Never merge to main unless started on main
- **30-Minute Commits**: Enforced regular commits to prevent work loss
- **Worktree Isolation**: Each agent has separate workspace
- **Automatic PR Creation**: Streamlined integration workflow

## 📋 Best Practices

### Writing Effective Specifications

```markdown
PROJECT: E-commerce Checkout
GOAL: Implement multi-step checkout process

CONSTRAINTS:
- Use existing cart state management
- Follow current design system
- Maximum 3 API endpoints
- Commit after each step completion

DELIVERABLES:
1. Shipping address form with validation
2. Payment method selection (Stripe integration)
3. Order review and confirmation page
4. Success/failure handling

SUCCESS CRITERIA:
- All forms validate properly
- Payment processes without errors  
- Order data persists to database
- Emails send on completion
```

### Git Safety Rules

⚠️ **CRITICAL BRANCH PROTECTION**: Never merge to main unless you started on main!

1. **When Starting a Project - Record the Branch**
   ```bash
   # First thing when orchestrator starts
   STARTING_BRANCH=$(git rev-parse --abbrev-ref HEAD)
   echo $STARTING_BRANCH > .git/STARTING_BRANCH
   echo "Project started on branch: $STARTING_BRANCH"
   ```

2. **Before Starting Any Task**
   ```bash
   # Feature branches are created FROM current branch, not main
   git checkout -b feature/[task-name]
   git status  # Ensure clean state
   ```

2. **Every 30 Minutes**
   ```bash
   git add -A
   git commit -m "Progress: [what was accomplished]"
   ```

3. **When Task Completes**
   ```bash
   git tag stable-[feature]-[date]
   # CRITICAL: Only merge to the branch you started from!
   ORIGINAL_BRANCH=$(cat .git/STARTING_BRANCH 2>/dev/null || echo "main")
   git checkout $ORIGINAL_BRANCH
   git merge feature/[task-name]
   ```

## 🚨 Common Issues & Solutions

### Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| **"ModuleNotFoundError: No module named 'yaml'"** | Install UV: `curl -LsSf https://astral.sh/uv/install.sh | sh` |
| **Scripts not executable** | Run: `chmod +x *.py *.sh` |
| **Agent exhausted credits** | Wait for reset or use: `./auto_orchestrate.py --resume` |
| **Tmux session not found** | Check with: `tmux ls` and use correct session name |
| **Git worktree conflicts** | The scripts handle this automatically with fallback strategies |

### Common Pitfalls & Solutions

| Pitfall | Consequence | Solution |
|---------|-------------|----------|
| Vague instructions | Agent drift, wasted compute | Write clear, specific specs |
| No git commits | Lost work, frustrated devs | Enforce 30-minute commit rule |
| Too many tasks | Context overload, confusion | One task per agent at a time |
| No specifications | Unpredictable results | Always start with written spec |
| Missing checkpoints | Agents stop working | Schedule regular check-ins |
| Wrong tmux window | Messages sent to nowhere | Verify with `tmux list-windows` |

## 🛠️ How It Works

### The Magic of Tmux
Tmux (terminal multiplexer) is the key enabler because:
- It persists terminal sessions even when disconnected
- Allows multiple windows/panes in one session
- Claude runs in the terminal, so it can control other Claude instances
- Commands can be sent programmatically to any window

### 💬 Simplified Agent Communication

We now use the `send-claude-message.sh` script for all agent communication:

```bash
# Send message to any Claude agent
./send-claude-message.sh session:window "Your message here"

# Examples:
./send-claude-message.sh frontend:0 "What's your progress on the login form?"
./send-claude-message.sh backend:1 "The API endpoint /api/users is returning 404"
./send-claude-message.sh project-manager:0 "Please coordinate with the QA team"
```

The script handles all timing complexities automatically, making agent communication reliable and consistent.

### Scheduling Check-ins
```bash
# Schedule with specific, actionable notes
./schedule_with_note.sh 30 "Review auth implementation, assign next task"
./schedule_with_note.sh 60 "Check test coverage, merge if passing"
./schedule_with_note.sh 120 "Full system check, rotate tasks if needed"
```

**Important**: The orchestrator needs to know which tmux window it's running in to schedule its own check-ins correctly. If scheduling isn't working, verify the orchestrator knows its current window with:
```bash
echo "Current window: $(tmux display-message -p "#{session_name}:#{window_index}")"
```

## 🎓 Advanced Usage

### Common Script Usage Examples

#### Starting a New Project
```bash
# Basic orchestration with specification
./auto_orchestrate.py --project /path/to/project --spec spec.md

# With specific team composition
./auto_orchestrate.py --project /path/to/project --spec spec.md \
  --roles "orchestrator,developer,sysadmin,devops"

# For system deployment projects
./auto_orchestrate.py --project /path/to/project --spec deployment_spec.md \
  --team-type system_deployment
```

#### Monitoring Active Orchestrations
```bash
# Start web dashboard (access at http://localhost:5000)
./monitoring_dashboard.py

# Check agent status from command line
./claude_control.py status

# Monitor multiple projects
./multi_project_monitor.py

# Check system performance
./performance_tuner.py --watch
```

#### Managing Running Orchestrations
```bash
# Send message to specific agent
./send-claude-message.sh project-impl:0 "What's your current status?"

# Schedule a check-in
./schedule_with_note.sh 30 "Review implementation progress" "project-impl:0"

# Resume an interrupted orchestration
./auto_orchestrate.py --project /path/to/project --resume

# Check agent credit status
./credit_management/check_agent_health.sh
```

#### Testing & Optimization
```bash
# Run integration tests
./test_integration.py

# Test system resilience (dry run first!)
./chaos_tester.py --duration 30 --dry-run

# Load test with 10 concurrent orchestrations
./load_tester.py concurrent --count 10

# Optimize system performance
./performance_tuner.py --clean-logs
```

### Multi-Project Orchestration
```bash
# Start concurrent orchestrations
./concurrent_orchestration.py start project1 project2 project3

# Monitor all projects
./multi_project_monitor.py

# Sync dashboard for git status
./sync_dashboard.py
```

### Cross-Project Intelligence
The orchestrator can share insights between projects:
- "Frontend is using /api/v2/users, update backend accordingly"
- "Authentication is working in Project A, use same pattern in Project B"
- "Performance issue found in shared library, fix across all projects"

## 📚 Complete Script Reference

### Core Orchestration
- **`auto_orchestrate.py`** - Automated setup from specifications with dynamic teams
- **`send-claude-message.sh`** - Send messages to any Claude agent
- **`schedule_with_note.sh`** - Schedule agent check-ins and tasks
- **`setup.sh`** - Initial environment setup

### Monitoring & Management
- **`monitoring_dashboard.py`** - Web-based real-time monitoring dashboard
- **`claude_control.py`** - Agent status monitoring and reporting
- **`sync_dashboard.py`** - Git synchronization status dashboard
- **`multi_project_monitor.py`** - Monitor multiple orchestrations
- **`performance_tuner.py`** - System performance optimization

### Team & Coordination
- **`dynamic_team.py`** - Automatic team composition based on project type
- **`ai_team_refiner.py`** - AI-powered team optimization
- **`concurrent_orchestration.py`** - Manage multiple concurrent projects
- **`sync_coordinator.py`** - Git worktree synchronization
- **`scheduler.py`** - Background task scheduling daemon

### Testing & Validation
- **`test_integration.py`** - Comprehensive integration testing
- **`chaos_tester.py`** - Resilience testing with controlled failures
- **`load_tester.py`** - Load testing for concurrent orchestrations

### Configuration & Documentation
- **`config.sh`** - Configuration management
- **`CLAUDE.md`** - Agent behavior instructions and knowledge base
- **`LEARNINGS.md`** - Accumulated knowledge and best practices

### Credit Management
- **`credit_management/`** - Scripts for handling Claude usage limits
  - `check_agent_health.sh` - Check credit status
  - `credit_monitor.py` - Automatic credit monitoring
  - `install_monitor.sh` - Install as system service

## 🤝 Contributing & Optimization

The orchestrator evolves through community discoveries and optimizations. When contributing:

1. Document new tmux commands and patterns in CLAUDE.md
2. Share novel use cases and agent coordination strategies
3. Submit optimizations for claudes synchronization
4. Keep command reference up-to-date with latest findings
5. Test improvements across multiple sessions and scenarios

Key areas for enhancement:
- Agent communication patterns
- Cross-project coordination
- Novel automation workflows

## 📄 License

MIT License - Use freely but wisely. Remember: with great automation comes great responsibility.

---

*"The tools we build today will program themselves tomorrow"* - Alan Kay, 1971
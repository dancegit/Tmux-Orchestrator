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
- UV (for Python script management) - Recommended for dependencies
- Basic familiarity with tmux commands

**Note**: All Python scripts use UV shebangs for dependency management. Install UV with:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/Tmux-Orchestrator.git
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

## 🎯 Quick Start

### Option 1: Basic Setup (Single Project)

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

### Option 2: Automated Setup with Auto-Orchestrate

Use the new `auto_orchestrate.py` script to automatically analyze a specification and set up a complete orchestration environment:

```bash
# Clone and run - no setup needed!
git clone https://github.com/yourusername/Tmux-Orchestrator.git
cd Tmux-Orchestrator

# Automatic setup from specification
./auto_orchestrate.py \
  --project /path/to/your/project \
  --spec /path/to/your/spec.md

# Example with SignalMatrix
./auto_orchestrate.py \
  --project /home/per/gitrepos/SignalMatrix_tag_checkouts_for_main \
  --spec /home/per/gitrepos/SignalMatrix_tag_checkouts_for_main/project_management/planning/dashboard_comprehensive_testing_spec.md
```

This will:
1. **Auto-setup** the Tmux Orchestrator environment (first time only)
2. **Context-prime** Claude to understand your project structure
3. **Analyze** your specification to create an implementation plan
4. **Show** the plan for your approval
5. **Create** tmux sessions with 5 specialized AI agents (including Project Manager)
6. **Brief** each agent with context-aware responsibilities
7. **Schedule** automatic check-ins for continuous progress

The script handles all setup automatically - no configuration needed!

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
The new `auto_orchestrate.py` script provides fully automated setup:
- **Zero Configuration**: Clone and run - automatic setup on first use
- **Context-Aware**: Uses `/context-prime` to understand your project before planning
- **Spec Analysis**: Claude analyzes your markdown specifications intelligently
- **Phase Planning**: Generates realistic implementation plans with time estimates
- **Core Agent Team**: Orchestrator, Project Manager, Developer, Tester, and TestRunner for all projects
- **One Command**: From fresh clone to running AI team in under a minute
- **Git Workflow**: Enforces best practices with regular commits and PRs
- **Credit Management**: Automatic handling of Claude Code usage limits with pause/resume

### 🔄 Self-Scheduling Agents
Agents can schedule their own check-ins using:
```bash
./schedule_with_note.sh 30 "Continue dashboard implementation"
```

### 👥 Multi-Agent Coordination
- Project managers communicate with engineers
- Orchestrator monitors all project managers
- Cross-project knowledge sharing

### 💾 Automatic Git Backups
- Commits every 30 minutes of work
- Tags stable versions
- Creates feature branches for experiments

### 📊 Real-Time Monitoring
- See what every agent is doing
- Intervene when needed
- Review progress across all projects

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

## 🚨 Common Pitfalls & Solutions

| Pitfall | Consequence | Solution |
|---------|-------------|----------|
| Vague instructions | Agent drift, wasted compute | Write clear, specific specs |
| No git commits | Lost work, frustrated devs | Enforce 30-minute commit rule |
| Too many tasks | Context overload, confusion | One task per agent at a time |
| No specifications | Unpredictable results | Always start with written spec |
| Missing checkpoints | Agents stop working | Schedule regular check-ins |

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

### Multi-Project Orchestration
```bash
# Start orchestrator
tmux new-session -s orchestrator

# Create project managers for each project
tmux new-window -n frontend-pm
tmux new-window -n backend-pm  
tmux new-window -n mobile-pm

# Orchestrator directly manages all agents
# Simplified structure for better efficiency
```

### Cross-Project Intelligence
The orchestrator can share insights between projects:
- "Frontend is using /api/v2/users, update backend accordingly"
- "Authentication is working in Project A, use same pattern in Project B"
- "Performance issue found in shared library, fix across all projects"

## 📚 Core Files

- `auto_orchestrate.py` - Automated setup from specifications (NEW!)
- `send-claude-message.sh` - Simplified agent communication script
- `schedule_with_note.sh` - Self-scheduling functionality
- `claude_control.py` - Status monitoring and reporting
- `tmux_utils.py` - Tmux interaction utilities
- `config.sh` - Configuration management
- `setup.sh` - Initial environment setup
- `CLAUDE.md` - Agent behavior instructions
- `LEARNINGS.md` - Accumulated knowledge base

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
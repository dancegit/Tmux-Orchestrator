# Tmux Orchestrator 🎭

**Run AI agents 24/7 while you sleep** - The Tmux Orchestrator enables Claude agents to work autonomously, schedule their own check-ins, and coordinate across multiple projects without human intervention.

> *"Set up agents that run for you on a 24/7 basis, working in the background while you sleep"*

## 🚀 The Vision

Imagine waking up to find your codebase has new features, bugs have been fixed, and everything is properly tested and committed to git. The Tmux Orchestrator makes this possible by creating a hierarchy of AI agents that can:

- **Self-trigger** - Agents schedule their own check-ins and continue work autonomously
- **Coordinate** - Project managers assign tasks to engineers across multiple codebases  
- **Persist** - Work continues even when you close your laptop
- **Scale** - Run multiple teams working on different projects simultaneously

## ⚠️ Critical Prerequisites & Precautions

### Before You Start - MUST HAVE:

1. **Clear Specifications** 
   - Write detailed spec sheets for each project
   - Define exact outcomes and constraints
   - Be specific - vague instructions lead to agent drift

2. **Git Discipline**
   - All projects MUST be in git repositories
   - Agents will commit frequently (every 30 minutes)
   - Enable automatic backups to prevent work loss

3. **Concise Instructions**
   - Agents have limited context windows
   - Keep instructions clear and focused
   - One task at a time prevents confusion

### Why This Matters:
- **Without specs**: Agents drift off-task and waste compute
- **Without git**: Hours of work can vanish in seconds  
- **Without clarity**: Results become unpredictable

## 🏗️ Architecture

The Tmux Orchestrator uses a three-tier hierarchy to overcome context window limitations:

```
┌─────────────┐
│ Orchestrator│ ← You interact here
└──────┬──────┘
       │ Monitors & coordinates
       ▼
┌─────────────┐     ┌─────────────┐
│  Project    │     │  Project    │
│  Manager 1  │     │  Manager 2  │ ← Assign tasks, enforce specs
└──────┬──────┘     └──────┬──────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│ Engineer 1  │     │ Engineer 2  │ ← Write code, fix bugs
└─────────────┘     └─────────────┘
```

### Why Separate Agents?
- **Limited context windows** - Each agent stays focused on its role
- **Specialized expertise** - PMs manage, engineers code
- **Parallel work** - Multiple engineers can work simultaneously
- **Better memory** - Smaller contexts mean better recall

## 📸 Examples in Action

### Project Manager Coordination
![Initiate Project Manager](Examples/Initiate%20Project%20Manager.png)
*The orchestrator creating and briefing a new project manager agent*

### Status Reports & Monitoring
![Status Reports](Examples/Status%20reports.png)
*Real-time status updates from multiple agents working in parallel*

### Tmux Communication
![Reading TMUX Windows and Sending Messages](Examples/Reading%20TMUX%20Windows%20and%20Sending%20Messages.png)
*How agents communicate across tmux windows and sessions*

### Project Completion
![Project Completed](Examples/Project%20Completed.png)
*Successful project completion with all tasks verified and committed*

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

# 4. Give PM the spec and let it create an engineer
"You are a Project Manager. Read project_spec.md and create an engineer 
in window 1 to implement it. Schedule check-ins every 30 minutes."

# 5. Schedule orchestrator check-in
./schedule_with_note.sh 30 "Check PM progress on auth system"
```

### Option 2: Full Orchestrator Setup

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

1. **Before Starting Any Task**
   ```bash
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
   git checkout main
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

### Agent Communication Flow
1. **Orchestrator** reads all project states
2. **Project Managers** receive high-level objectives
3. **Engineers** get specific implementation tasks
4. **Check-ins** happen automatically via scheduled scripts
5. **Git commits** preserve all progress

This flow is demonstrated in the examples above, showing real agents coordinating across multiple projects and reporting progress back to the orchestrator.

## 📁 Configuration

### Project Configuration (`project_configs.json`)
```json
{
  "my-project": {
    "spec_file": "specs/my-project.md",
    "git_commit_interval": 1800,
    "check_in_interval": 3600,
    "branch_prefix": "auto/",
    "test_command": "npm test",
    "constraints": {
      "max_files_per_commit": 10,
      "require_tests": true
    }
  }
}
```

### Scheduling Check-ins
```bash
# Schedule with specific, actionable notes
./schedule_with_note.sh 30 "Review auth implementation, assign next task"
./schedule_with_note.sh 60 "Check test coverage, merge if passing"
./schedule_with_note.sh 120 "Full system check, rotate tasks if needed"
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

# Each PM manages their own engineers
# Orchestrator coordinates between PMs
```

### Cross-Project Intelligence
The orchestrator can share insights between projects:
- "Frontend is using /api/v2/users, update backend accordingly"
- "Authentication is working in Project A, use same pattern in Project B"
- "Performance issue found in shared library, fix across all projects"

## 🔧 Troubleshooting

### Agent Not Responding
```bash
# Check agent status
tmux capture-pane -t session:window -p | tail -50

# Restart if needed
tmux send-keys -t session:window C-c
tmux send-keys -t session:window "claude" Enter
```

### Git Merge Conflicts
- Agents create feature branches to avoid conflicts
- Manual resolution may be needed for complex merges
- Set up notifications for merge failures

### Context Window Exhaustion
- Restart agent with fresh context
- Provide summary of completed work
- Continue from last git commit

## 📚 Core Files

- `schedule_with_note.sh` - Self-scheduling functionality
- `tmux_utils.py` - Tmux interaction utilities
- `orchestrator_integration.py` - Project management logic
- `project_configs.json` - Project-specific settings
- `CLAUDE.md` - Agent behavior instructions
- `LEARNINGS.md` - Accumulated knowledge base

## 🚀 What's Possible?

With the Tmux Orchestrator running overnight, you might wake up to:

- ✅ New features implemented and tested
- ✅ Bug fixes with regression tests
- ✅ Refactored code with improved performance
- ✅ Updated documentation
- ✅ Cleaned up technical debt
- ✅ All changes properly committed to git

## 🤝 Contributing

The orchestrator thrives on community improvements. When contributing:

1. Test with multiple tmux sessions
2. Ensure git safety mechanisms work
3. Update LEARNINGS.md with new insights
4. Keep the orchestrator's instructions in CLAUDE.md current

## 📄 License

MIT License - Use freely but wisely. Remember: with great automation comes great responsibility.

---

*"The best code is written while you sleep" - The Tmux Orchestrator*
![Orchestrator Hero](/Orchestrator.png)

**Run AI agents 24/7 while you sleep** - The Tmux Orchestrator enables Claude agents to work autonomously, schedule their own check-ins, and coordinate across multiple projects without human intervention.

## 🤖 Key Capabilities & Autonomous Features

- **Self-trigger** - Agents schedule their own check-ins and continue work autonomously
- **Coordinate** - Project managers assign tasks to engineers across multiple codebases  
- **Persist** - Work continues even when you close your laptop
- **Scale** - Run multiple teams working on different projects simultaneously

## 🚀 Latest Updates (v3.6.0) - Critical Scheduling Reliability Fixes

### 🛠️ System Requirements & Essential Services

**What MUST Run for Proper Operation:**

#### 1. Scheduler Daemon (REQUIRED)
The scheduler daemon is **CRITICAL** for orchestrator check-ins and preventing project stalls:
```bash
# Option A: Persistent daemon (RECOMMENDED)
nohup timeout 7200 python3 -c "
from scheduler import TmuxOrchestratorScheduler
import time
scheduler = TmuxOrchestratorScheduler()
while True:
    scheduler.check_and_run_tasks()
    time.sleep(60)
" > persistent_scheduler.log 2>&1 &

# Option B: Start manual check for immediate needs
python3 -c "
from scheduler import TmuxOrchestratorScheduler
scheduler = TmuxOrchestratorScheduler()
scheduler.check_and_run_tasks()
scheduler.close()
"
```

#### 2. Database Schema Verification (AUTO-FIXED)
The task database schema is now automatically verified and fixed:
- ✅ Column name mismatch (`task_id` vs `id`) - **FIXED**
- ✅ Orchestrator scheduling logic bug - **FIXED**
- ✅ Idempotent task addition to prevent loops - **IMPLEMENTED**

#### 3. Self-Scheduling Check (MANDATORY FOR ORCHESTRATORS)
Every orchestrator MUST verify self-scheduling on startup:
```bash
# Test scheduling capability
CURRENT_WINDOW=$(tmux display-message -p "#{session_name}:#{window_index}")
./schedule_with_note.sh 1 "Test schedule for $CURRENT_WINDOW" "$CURRENT_WINDOW"
```

### 🔧 Critical Bug Fixes (v3.6.0)

#### Orchestrator Self-Scheduling (RESOLVED)
- **Issue**: Orchestrators weren't receiving scheduled check-ins, causing project stalls
- **Root Cause**: Database schema mismatch (`task_id` vs `id`) + inverted scheduling logic
- **Fix**: 
  - Fixed SQL queries to use correct column names
  - Corrected orchestrator scheduling condition in `auto_orchestrate.py`
  - Added database schema validation
- **Impact**: Prevents "22:21 check-in never happened" situations

#### Scheduler Reliability Improvements
- **Idempotent Task Addition**: Prevents scheduling loops using composite keys
- **Health Check System**: Continuous monitoring of system dependencies (bc, tmux, git)
- **Automatic Recovery**: Processes overdue tasks and creates fallback states
- **Race Condition Handling**: Improved lock management for concurrent scheduler instances

#### File Organization & Cleanup
- **Documentation Structure**: Organized all docs into `docs/` subdirectories
- **Cleanup System**: Removed 49+ unused/duplicate files
- **Essential File Restoration**: Restored `tmux_session_manager.py` (actively used)

### Previous Release (v3.5.2)
- **Orchestrator Self-Scheduling** - Added `--enable-orchestrator-scheduling` flag 
- **MCP Global Initialization** - Added `--global-mcp-init` flag for system MCP configs
- **Auto-Orchestrate Reliability** - Fixed critical deployment failures

## 🎯 Primary Tools & Entry Points

### Core Orchestration Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| **`auto_orchestrate.py`** | Main entry point for project orchestration | Start new projects, resume existing ones, batch processing |
| **`merge_integration.py`** | Git workflow integration tool | Merge branches, handle conflicts, coordinate git operations |
| **`scheduler.py --queue-daemon`** | Queue daemon for batch processing | Process multiple projects sequentially, handle retries |
| **`monitoring_dashboard.py`** | Real-time monitoring interface | Track all active orchestrations via web UI |

### Quick Start with Primary Tools
```bash
# Start a new orchestration
./auto_orchestrate.py --spec /path/to/spec.md

# Process multiple projects
./auto_orchestrate.py --spec spec1.md --spec spec2.md --spec spec3.md

# Resume after interruption
./auto_orchestrate.py --project /path/to/project --resume

# Merge integration branches
./merge_integration.py --project /path/to/project --branch integration

# Monitor everything
./monitoring_dashboard.py
```

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

### System Requirements
- **OS**: Linux, macOS, or WSL2 on Windows
- **Memory**: 8GB RAM minimum (16GB recommended for multiple orchestrations)
- **Disk**: 10GB free space for logs and worktrees
- **Network**: Stable internet for Claude API access

### Prerequisites
- **tmux** 2.0+ installed on your system
- **Claude Code** (`claude` command available) - NOT the old Claude CLI
- **Python** 3.11+ (for utilities)
- **UV** (for Python script management) - **Required for all Python scripts**
- **Git** 2.0+ configured with user credentials
- **SQLite3** (for task queue database)
- **bc** calculator utility (for time calculations)
- Basic familiarity with tmux commands

**Important**: All Python scripts use UV shebangs for zero-dependency execution. Install UV with:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 🚨 MANDATORY: Scheduler Daemon Operation

The scheduler daemon is **ESSENTIAL** for system operation. Without it, orchestrators won't receive check-ins and projects will stall.

#### Quick Start (Persistent Scheduler)
```bash
# 1. Verify dependencies are working
python3 -c "
from scheduler import TmuxOrchestratorScheduler
print('✅ Scheduler imports successfully')
"

# 2. Start persistent daemon (runs for 2 hours, checks every minute)
nohup timeout 7200 python3 -c "
from scheduler import TmuxOrchestratorScheduler
import time
import signal
import sys

def signal_handler(signum, frame):
    print('Daemon received shutdown signal, exiting gracefully...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

scheduler = TmuxOrchestratorScheduler()
print('Starting persistent scheduler daemon...')
print(f'Monitoring tasks - will run for 2 hours')

try:
    while True:
        scheduler.check_and_run_tasks()
        time.sleep(60)  # Check every minute
except KeyboardInterrupt:
    print('Daemon stopped by user')
except Exception as e:
    print(f'Daemon error: {e}')
    
print('Scheduler daemon shutting down')
" > persistent_scheduler.log 2>&1 &

# 3. Verify daemon is running
ps aux | grep python3 | grep scheduler

# 4. Monitor daemon activity
tail -f persistent_scheduler.log
```

#### Verification Commands
```bash
# Check if tasks are scheduled correctly
python3 scheduler.py --list | tail -10

# Manual processing for immediate needs
python3 -c "
from scheduler import TmuxOrchestratorScheduler
scheduler = TmuxOrchestratorScheduler()
print('Processing overdue tasks manually...')
scheduler.check_and_run_tasks()
print('Manual processing complete')
"

# Check orchestrator self-scheduling capability
CURRENT_WINDOW=$(tmux display-message -p "#{session_name}:#{window_index}")
echo "Testing scheduling for: $CURRENT_WINDOW"
./schedule_with_note.sh 1 "Test schedule" "$CURRENT_WINDOW"
```

#### Daemon Monitoring & Health Checks
```bash
# Check daemon health
if pgrep -f "scheduler.*check_and_run_tasks" > /dev/null; then
    echo "✅ Scheduler daemon is running"
else
    echo "❌ Scheduler daemon is NOT running - orchestrators may stall!"
fi

# Check recent activity
tail -20 persistent_scheduler.log | grep -E "(Message verified|Task.*completed)"

# View upcoming tasks
python3 scheduler.py --list | head -20
```

### System Services (Optional but Recommended)

#### 1. Queue Daemon Service (systemd)
For production use, install the queue daemon as a systemd service:
```bash
# Install the service
sudo cp /etc/systemd/system/tmux-orchestrator-queue.service.example /etc/systemd/system/tmux-orchestrator-queue.service
sudo systemctl daemon-reload
sudo systemctl enable tmux-orchestrator-queue
sudo systemctl start tmux-orchestrator-queue

# Check status
systemctl status tmux-orchestrator-queue
```

#### 2. Scheduler Monitor (cron)
Set up automated monitoring:
```bash
# Add to crontab
crontab -e
# Add this line:
*/10 * * * * /path/to/Tmux-Orchestrator/cron_scheduler_monitor.sh
```

### Recommended Setup
- **Claude Subscription**: Pro or higher for best performance
- **Terminal**: Full-featured terminal with 256 color support
- **Shell**: Bash or Zsh (scripts assume bash-compatible shell)
- **GitHub CLI** (gh): For automated PR creation in merge_integration.py

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

### 📋 Pre-Operation Checklist

Before starting any orchestration, verify these critical components:

#### ✅ System Health Check
```bash
# 1. Verify all dependencies
python3 -c "from scheduler import TmuxOrchestratorScheduler; print('✅ Scheduler OK')"
which tmux bc git uv || echo "❌ Missing dependencies"

# 2. Check scheduler daemon status
if pgrep -f "scheduler.*check_and_run_tasks" > /dev/null; then
    echo "✅ Scheduler daemon running"
else
    echo "❌ START SCHEDULER DAEMON NOW!"
fi

# 3. Test scheduling capability
CURRENT_WINDOW=$(tmux display-message -p "#{session_name}:#{window_index}")
./schedule_with_note.sh 1 "Health check" "$CURRENT_WINDOW" && echo "✅ Scheduling works"

# 4. Verify database schema
python3 scheduler.py --list | head -5 && echo "✅ Database accessible"
```

#### 🚀 Start Essential Services
```bash
# Start persistent scheduler daemon (MANDATORY)
nohup timeout 7200 python3 -c "
from scheduler import TmuxOrchestratorScheduler
import time
scheduler = TmuxOrchestratorScheduler()
while True:
    scheduler.check_and_run_tasks()
    time.sleep(60)
" > persistent_scheduler.log 2>&1 &

echo "Scheduler daemon PID: $!"
echo "Monitor with: tail -f persistent_scheduler.log"
```

#### 🔍 Daily Maintenance
```bash
# Check system health (run daily)
./health_check.sh() {
    echo "=== Tmux Orchestrator Health Check ==="
    echo "Date: $(date)"
    echo
    
    # Daemon check
    if pgrep -f "scheduler.*check_and_run_tasks" > /dev/null; then
        echo "✅ Scheduler daemon: RUNNING"
    else
        echo "❌ Scheduler daemon: NOT RUNNING - CRITICAL!"
    fi
    
    # Database check
    task_count=$(python3 scheduler.py --list 2>/dev/null | wc -l)
    echo "📊 Scheduled tasks: $task_count"
    
    # Recent activity
    recent_activity=$(tail -20 persistent_scheduler.log 2>/dev/null | grep -c "Message verified" || echo "0")
    echo "📨 Recent deliveries: $recent_activity"
    
    # Active sessions
    active_sessions=$(tmux ls 2>/dev/null | wc -l || echo "0")
    echo "🖥️  Active tmux sessions: $active_sessions"
    
    echo
    echo "Next scheduled tasks:"
    python3 scheduler.py --list 2>/dev/null | head -5
}

# Run it
health_check.sh
```

## 📁 Project Directory Structure

The Tmux Orchestrator follows a clean, organized structure. Here's where everything belongs:

### Core Directories

```
Tmux-Orchestrator/
├── docs/                    # All documentation (except README.md)
│   ├── INDEX.md            # Documentation index and guide
│   ├── architecture/       # System design, specs, architectural decisions
│   ├── guides/            # How-to guides, briefings, implementation instructions
│   ├── investigations/    # Deep dives, root cause analyses, research
│   └── troubleshooting/   # Solutions, fixes, issue resolutions
│
├── monitoring/             # Monitoring and compliance tools
│   ├── compliance_monitor.py
│   ├── monitored_send_message.sh
│   └── workflow_monitor.py
│
├── registry/               # Runtime data and state
│   ├── projects/          # Active project registrations
│   ├── logs/             # System and agent logs
│   ├── sessions.json     # Active session tracking
│   └── notes/           # Orchestrator notes
│
├── locks/                 # Lock files for process coordination
├── session_states/        # Agent session state persistence
├── systemd/              # Systemd service configurations
└── Examples/             # Screenshots and usage examples
```

### File Organization Guidelines

**Python Scripts** - Core functionality
- `auto_orchestrate.py` - Main orchestration entry point
- `scheduler.py` - Task scheduling daemon
- `*_manager.py` - Various system managers
- `*_monitor.py` - Monitoring utilities

**Shell Scripts** - Tmux and system operations
- `send-claude-message*.sh` - Agent communication variants
- `schedule_with_note.sh` - Task scheduling interface
- `*_monitor.sh` - Shell-based monitors

**Configuration Files**
- `config.sh` / `config.local.sh` - System configuration
- `*.service` - Systemd service definitions
- `task_queue.db` - SQLite task database

**What Goes Where:**
- 📚 **New documentation** → `docs/` (choose appropriate subdirectory)
- 🔧 **Bug fixes/solutions** → `docs/troubleshooting/`
- 🏗️ **Design decisions** → `docs/architecture/`
- 📋 **How-to guides** → `docs/guides/`
- 🔍 **Research/investigations** → `docs/investigations/`
- 🧪 **Test scripts** → Create `tests/` directory (not in main dir)
- 🗑️ **Temporary files** → Use `/tmp` or `~/.trash/`
- 📊 **Logs** → `registry/logs/`

### Development Best Practices

1. **Keep root directory clean** - Only essential scripts at root level
2. **Document in docs/** - All markdown files except README.md
3. **Use meaningful names** - Avoid `*_fixed.py`, `*_enhanced.py`, etc.
4. **No test files at root** - Create `tests/` if needed
5. **Clean up regularly** - Use `cleanup_unused_files.sh` for maintenance

## 🚀 Quick Reference

### Most Common Commands
```bash
# Start new project
./auto_orchestrate.py --project /path/to/project --spec spec.md

# Resume after interruption
./auto_orchestrate.py --project /path/to/project --resume

# Monitor everything
./monitoring_dashboard.py

# Send message to agent (with hub-spoke enforcement)
./send-claude-message-hubspoke.sh session:window "message"

# Report task completion
./report-completion.sh role "completion message"

# Check performance
./performance_tuner.py
```

### 🛡️ Hub-Spoke Communication Enforcement
The system now automatically enforces hub-spoke communication to prevent agents from completing tasks silently:
- Critical messages (complete, deploy, fail) auto-route to Orchestrator
- Task completions trigger automatic status reports
- Dependencies are tracked and resolved automatically
- All communications are logged for compliance

### 🔧 Systemd Service (Optional)
For production deployments, run the scheduler as a systemd service:
```bash
# Install service (run once)
sudo ./systemd/install-systemd-service.sh $USER

# Check status
sudo systemctl status tmux-orchestrator-scheduler@$USER

# View logs
sudo journalctl -u tmux-orchestrator-scheduler@$USER -f

# Uninstall
sudo ./systemd/uninstall-systemd-service.sh $USER
```

## 🚀 Main Scripts Overview

### Core Orchestration Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| **`auto_orchestrate.py`** | Automated setup from specifications | Starting new projects with a spec file |
| **`merge_integration.py`** | Git workflow and PR management | Merging branches, creating PRs, managing integration |
| **`send-claude-message.sh`** | Send messages to Claude agents | Basic agent communication |
| **`send-claude-message-hubspoke.sh`** | Hub-spoke enforced messaging | Critical updates & completions |
| **`report-completion.sh`** | Report task completions | After completing major tasks |
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
| **`concurrent_orchestration.py`** | Lock management for orchestrations | Preventing concurrent conflicts |
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

# NEW: Automatic project detection - just provide the spec!
./auto_orchestrate.py --spec /path/to/spec.md

# NEW: Create new git projects from specs (creates repo as sibling to spec location)
./auto_orchestrate.py --new-project --spec /path/to/spec.md

# NEW: Batch processing - queue multiple specs
./auto_orchestrate.py --spec spec1.md --spec spec2.md --spec spec3.md

# Start the queue daemon to process batched projects
uv run scheduler.py --queue-daemon

# Resume an interrupted orchestration
./auto_orchestrate.py --project /path/to/project --resume

# With custom team size based on your Claude plan
./auto_orchestrate.py --project /path/to/project --spec spec.md --plan max5

# NEW in v3.5.2: Enable orchestrator self-scheduling
./auto_orchestrate.py --spec spec.md --enable-orchestrator-scheduling

# NEW in v3.5.2: Use global MCP configurations for all agents
./auto_orchestrate.py --spec spec.md --global-mcp-init

# Both flags together for maximum reliability
./auto_orchestrate.py --spec spec.md --enable-orchestrator-scheduling --global-mcp-init
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
- **Automatic Project Detection**: Finds git root automatically - just provide the spec file
- **New Project Creation**: `--new-project` flag creates new git repositories from specs
- **Batch Processing**: Queue multiple specs for sequential processing without conflicts
- **Context-Aware**: Uses `/context-prime` to understand your project before planning
- **Spec Analysis**: Claude analyzes your markdown specifications intelligently
- **Dynamic Team Composition**: Automatically selects appropriate roles based on project type
- **Git Worktree Isolation**: Each agent works in isolated git worktree to prevent conflicts
- **Resume Capability**: Intelligently resume interrupted orchestrations
- **Credit Management**: Automatic handling of Claude Code usage limits with pause/resume

#### 🆕 New Project Creation (`--new-project` flag)
The `--new-project` flag enables creating new git repositories directly from specification files:

**How it works:**
1. **Project Location**: Creates new project as sibling directory to the spec file's git root
2. **Git Initialization**: Creates new repository with initial commit containing the spec
3. **Worktree Placement**: Places agent worktrees parallel to project (not in registry)
4. **Batch Support**: Can process multiple specs to create multiple projects
5. **Pattern Matching**: Supports glob patterns and directory processing

**Examples:**
```bash
# Create single project from spec
./auto_orchestrate.py --new-project --spec feature-spec.md
# Result: Creates "feature-spec" directory next to the spec file

# Batch create projects from multiple specs
./auto_orchestrate.py --new-project --spec spec1.md --spec spec2.md

# Process entire directory of specs
./auto_orchestrate.py --new-project --spec /path/to/specs/

# Use patterns to select specific specs
./auto_orchestrate.py --new-project --spec "features/user-*.md"

# Force overwrite existing projects
./auto_orchestrate.py --new-project --force --spec existing-project.md
```

**Directory Structure Example:**
```
parent-directory/
├── existing-repo/          # Original git repository containing spec
│   └── feature-spec.md     # Your specification file
└── feature-spec/           # NEW: Created project directory
    ├── .git/               # New git repository
    ├── feature-spec.md     # Copy of spec file
    └── feature-spec_worktrees/  # Agent worktrees (parallel to project)
        ├── orchestrator/
        ├── developer/
        └── tester/
```

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
- **Intelligent Batch Retry**: Failed projects automatically analyzed and retried with research agent
- **Credit-Aware Operations**: Automatic pause/resume for Claude Code usage limits

### 💾 Optimized Git Workflow (NEW!)
- **Local-First Collaboration**: Agents work via local git remotes (60-500x faster)
- **PM Coordination Hub**: Project Manager orchestrates local merges instead of GitHub PRs
- **GitHub for Milestones**: Push to GitHub only for backups and major releases
- **Branch Protection**: Never merge to main unless started on main
- **30-Minute Commits**: Enforced regular commits to prevent work loss
- **Worktree Isolation**: Each agent has separate workspace
- **Intelligent Retry System**: Research agent analyzes failures and enhances specs

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

### Critical Issues & Resolutions (v3.6.0)

| Issue | Symptoms | Root Cause | Solution |
|-------|----------|------------|----------|
| **Orchestrator doesn't self-schedule** | No check-ins received, projects stall | Database schema mismatch + inverted logic | ✅ **AUTO-FIXED** in v3.6.0 |
| **Tasks fail with "no such column: task_id"** | SQLite errors in scheduler | Incorrect column name in SQL | ✅ **RESOLVED** - Uses correct `id` column |
| **Scheduler daemon won't start** | "Another scheduler is already running" | Race condition in lock detection | Use persistent daemon command from docs |
| **Orchestrators go silent** | No messages after specific times | Missing scheduler daemon | Start persistent scheduler daemon |

### Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| **"ModuleNotFoundError: No module named 'yaml'"** | Install UV: `curl -LsSf https://astral.sh/uv/install.sh | sh` |
| **Scripts not executable** | Run: `chmod +x *.py *.sh` |
| **Agent exhausted credits** | Wait for reset or use: `./auto_orchestrate.py --resume` |
| **Tmux session not found** | Check with: `tmux ls` and use correct session name |
| **Git worktree conflicts** | The scripts handle this automatically with fallback strategies |
| **"bc: command not found"** | Install bc: `sudo apt install bc` (Linux) or `brew install bc` (macOS) |
| **Scheduler not processing tasks** | Check daemon is running: `ps aux \| grep scheduler` |

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
# NEW: Batch processing - queue all specs at once
./auto_orchestrate.py --spec spec1.md --spec spec2.md --spec spec3.md

# Start the queue daemon to process them sequentially
uv run scheduler.py --queue-daemon

# Check queue status
uv run scheduler.py --queue-list

# Or start each project individually (old method)
./auto_orchestrate.py --project ~/projects/project1 --spec spec1.md
./auto_orchestrate.py --project ~/projects/project2 --spec spec2.md
./auto_orchestrate.py --project ~/projects/project3 --spec spec3.md

# Monitor all projects in one dashboard
./multi_project_monitor.py

# Check orchestration locks and conflicts
./concurrent_orchestration.py --list

# Monitor git synchronization across all projects
./sync_dashboard.py
```

### Cross-Project Intelligence
The orchestrator can share insights between projects:
- "Frontend is using /api/v2/users, update backend accordingly"
- "Authentication is working in Project A, use same pattern in Project B"
- "Performance issue found in shared library, fix across all projects"

## 📚 Complete Script Reference with Examples

### Core Orchestration Scripts

#### `auto_orchestrate.py` - Automated Setup from Specifications
```bash
# Basic usage - start a new project
./auto_orchestrate.py --project ~/projects/my-webapp --spec ~/specs/auth-system.md

# NEW: Automatic project detection - no --project needed!
./auto_orchestrate.py --spec ~/specs/auth-system.md

# NEW: Create new git projects from specs (--new-project flag)
./auto_orchestrate.py --new-project --spec ~/specs/auth-system.md

# NEW: Batch creation of multiple projects
./auto_orchestrate.py --new-project --spec spec1.md --spec spec2.md --spec spec3.md

# NEW: Process entire directories of specs
./auto_orchestrate.py --new-project --spec ~/specs/

# NEW: Use glob patterns for selective project creation
./auto_orchestrate.py --new-project --spec "~/specs/feature-*.md"

# NEW: Force overwrite existing projects
./auto_orchestrate.py --new-project --force --spec existing-feature.md

# NEW: Batch processing multiple specs (existing projects)
./auto_orchestrate.py --spec spec1.md --spec spec2.md --spec spec3.md

# Force batch mode for single spec
./auto_orchestrate.py --spec spec.md --batch

# Resume after credit exhaustion
./auto_orchestrate.py --project ~/projects/my-webapp --resume

# Check status without making changes
./auto_orchestrate.py --project ~/projects/my-webapp --resume --status-only

# Force specific team composition
./auto_orchestrate.py --project ~/projects/deployment \
  --spec deployment.md \
  --roles "orchestrator,sysadmin,devops,securityops"

# System deployment with specialized team
./auto_orchestrate.py --project /opt/services/api-server \
  --spec deploy-spec.md \
  --team-type system_deployment

# Adjust for Claude subscription plan
./auto_orchestrate.py --project ~/projects/startup \
  --spec mvp.md \
  --plan pro \
  --size small
```

#### `send-claude-message.sh` - Agent Communication
```bash
# Check status of specific agent
./send-claude-message.sh myproject-impl:0 "What's your current status?"

# Assign new task to developer
./send-claude-message.sh webapp-impl:1 "Please implement the login endpoint at /api/auth/login"

# Request test coverage report
./send-claude-message.sh webapp-impl:2 "Show me the current test coverage for authentication"

# Coordinate between agents
./send-claude-message.sh backend-impl:0 "The frontend needs a /api/users/profile endpoint"

# Emergency stop
./send-claude-message.sh project-impl:0 "STOP all current work and report status"
```

#### `merge_integration.py` - Git Workflow Management
```bash
# Merge integration branch to main
./merge_integration.py --project /path/to/project --branch integration

# Create PR without merging
./merge_integration.py --project /path/to/project --branch feature/auth --pr-only

# Force merge without PR (use with caution)
./merge_integration.py --project /path/to/project --branch hotfix --no-pr

# Specify custom base branch
./merge_integration.py --project /path/to/project --branch feature/ui --base develop

# Dry run to see what would happen
./merge_integration.py --project /path/to/project --branch integration --dry-run
```

#### `schedule_with_note.sh` - Task Scheduling
```bash
# Schedule regular check-ins
./schedule_with_note.sh 30 "Review developer progress on auth system" "webapp-impl:0"

# Schedule test runs
./schedule_with_note.sh 60 "Run full test suite and report failures" "webapp-impl:3"

# Schedule git operations
./schedule_with_note.sh 45 "Commit current work and push to feature branch" "webapp-impl:1"

# Schedule integration
./schedule_with_note.sh 120 "Merge feature branches and run integration tests" "webapp-impl:4"

# Self-scheduling for orchestrator
CURRENT_WINDOW=$(tmux display-message -p "#{session_name}:#{window_index}")
./schedule_with_note.sh 90 "Check all project status and reassign tasks" "$CURRENT_WINDOW"
```

### Monitoring & Management Scripts

#### `monitoring_dashboard.py` - Real-time Web Dashboard
```bash
# Start dashboard on default port
./monitoring_dashboard.py
# Access at: http://localhost:5000

# Custom port for remote access
./monitoring_dashboard.py --port 8080 --host 0.0.0.0

# Debug mode with detailed logging
./monitoring_dashboard.py --debug
```

#### `claude_control.py` - Agent Status Monitor
```bash
# Get status of all agents
./claude_control.py status

# Check specific session
./claude_control.py status webapp-impl

# Generate detailed report
./claude_control.py report --output status-report.md

# Monitor agent activity
./claude_control.py monitor --interval 10
```

#### `sync_dashboard.py` - Git Synchronization Monitor
```bash
# Start sync dashboard
./sync_dashboard.py

# Custom refresh interval
./sync_dashboard.py --refresh 5

# Monitor specific project
./sync_dashboard.py --project ~/projects/webapp

# Export sync status
./sync_dashboard.py --export sync-status.json
```

#### `multi_project_monitor.py` - Multi-Project Overview
```bash
# Monitor all active projects
./multi_project_monitor.py

# Focus on specific projects
./multi_project_monitor.py --projects "webapp,backend,mobile"

# Generate project summary
./multi_project_monitor.py --summary

# Export metrics
./multi_project_monitor.py --export project-metrics.csv
```

#### `performance_tuner.py` - System Optimization
```bash
# One-time performance check
./performance_tuner.py

# Continuous monitoring mode
./performance_tuner.py --watch --interval 30

# Clean old logs and optimize
./performance_tuner.py --clean-logs

# Skip database optimization
./performance_tuner.py --no-optimize-db

# Export performance report
./performance_tuner.py --json > performance-report.json
```

### Team & Coordination Scripts

#### `dynamic_team.py` - Automatic Team Composition
```bash
# Analyze project and suggest team
./dynamic_team.py --project ~/projects/webapp

# Get team for specific project type
./dynamic_team.py --project ~/projects/infra --type infrastructure_as_code

# Custom team size constraints
./dynamic_team.py --project ~/projects/startup --max-size 3

# Export team configuration
./dynamic_team.py --project ~/projects/api --export team-config.yaml
```

#### `ai_team_refiner.py` - AI-Powered Team Optimization
```bash
# Refine existing team composition
./ai_team_refiner.py --project ~/projects/webapp \
  --team "orchestrator,developer,tester" \
  --spec requirements.md

# Use mock AI for testing
./ai_team_refiner.py --project ~/projects/test \
  --team "orchestrator,developer" \
  --mock

# With custom Claude API
export ANTHROPIC_API_KEY="your-key"
./ai_team_refiner.py --project ~/projects/production \
  --team "orchestrator,developer,devops" \
  --spec production-spec.md

# NEW: Research mode for failure analysis (used automatically by batch retry)
./auto_orchestrate.py --research '{
  "failed_projects": [{"spec_path": "spec.md", "error_message": "timeout"}],
  "session_id": "research-session-123"
}'
```

#### `concurrent_orchestration.py` - Orchestration Lock Management
```bash
# List active orchestrations (checks lock files)
./concurrent_orchestration.py --list

# Clean up stale orchestration locks
./concurrent_orchestration.py --cleanup

# Start a new orchestration with lock (low-level)
./concurrent_orchestration.py --start my-project

# Note: This is a low-level utility. For starting projects, use:
# ./auto_orchestrate.py --project /path/to/project --spec spec.md
```

### Testing & Validation Scripts

#### `test_integration.py` - Component Testing
```bash
# Run all integration tests
./test_integration.py

# Run specific test class
./test_integration.py TestFullOrchestration

# Verbose output
./test_integration.py -v

# Generate test coverage report
./test_integration.py --coverage
```

#### `chaos_tester.py` - Resilience Testing
```bash
# Dry run to see what would happen
./chaos_tester.py --duration 30 --dry-run

# Run 15-minute chaos test
./chaos_tester.py --duration 15

# Test only medium severity events
./chaos_tester.py --severity medium --duration 30

# Custom event intervals
./chaos_tester.py --min-interval 60 --max-interval 300

# Export results as JSON
./chaos_tester.py --duration 60 --json > chaos-results.json
```

#### `load_tester.py` - Capacity Testing
```bash
# Test with 5 concurrent orchestrations
./load_tester.py concurrent --count 5 --hold 300

# Gradual ramp up test
./load_tester.py ramp --max 20 --duration 600 --hold 300

# Quick stress test
./load_tester.py concurrent --count 10 --interval 2 --hold 60

# Export detailed metrics
./load_tester.py concurrent --count 5 --json > load-test-results.json
```

### Credit Management Scripts

#### `check_agent_health.sh` - Credit Status Check
```bash
# Check all agents
./credit_management/check_agent_health.sh

# Check specific session
./credit_management/check_agent_health.sh webapp-impl

# Show reset times
./credit_management/check_agent_health.sh --show-resets
```

#### `credit_monitor.py` - Automatic Monitoring
```bash
# Start credit monitor
./credit_management/credit_monitor.py

# Custom check interval
./credit_management/credit_monitor.py --interval 300

# Monitor specific sessions
./credit_management/credit_monitor.py --sessions "webapp-impl,backend-impl"

# Enable auto-resume
./credit_management/credit_monitor.py --auto-resume
```

### Utility Scripts

#### `setup.sh` - Initial Setup
```bash
# Basic setup
./setup.sh

# Setup with custom project directory
PROJECTS_DIR=~/my-projects ./setup.sh

# Non-interactive setup
./setup.sh --non-interactive

# Verify installation
./setup.sh --verify
```

#### `scheduler.py` - Background Task Daemon with Intelligent Batch Retry
```bash
# NEW: Project queue management with automatic retry
# Start project queue daemon (includes intelligent retry system)
uv run scheduler.py --queue-daemon

# Add project to queue
uv run scheduler.py --queue-add spec.md /path/to/project

# List queued projects (shows retry counts and batch IDs)
uv run scheduler.py --queue-list

# Check specific project status
uv run scheduler.py --queue-status 1

# The system automatically:
# - Detects when batch completion occurs
# - Runs research agent on failed projects using Grok MCP
# - Creates enhanced specs with failure analysis
# - Retries failed projects up to 3 times
# - Escalates permanent failures via email

# Legacy task scheduling
# Start scheduler daemon
uv run scheduler.py --daemon

# Add a scheduled task
uv run scheduler.py --add session-name developer 0 30 "Check-in message"

# List all scheduled tasks
uv run scheduler.py --list

# Remove a task
uv run scheduler.py --remove 5
```

#### `sync_coordinator.py` - Git Worktree Sync
```bash
# Start sync coordinator
./sync_coordinator.py start

# Manual sync trigger
./sync_coordinator.py sync webapp-impl

# Check sync status
./sync_coordinator.py status

# Force sync all projects
./sync_coordinator.py sync --all --force

# Resolve conflicts
./sync_coordinator.py resolve webapp-impl --strategy theirs
```

## 🎯 Common Workflows & Real-World Examples

### Workflow 1: Starting a New Web Application Feature
```bash
# 1. Create specification
cat > feature-spec.md << 'EOF'
PROJECT: E-commerce Cart Enhancement
GOAL: Add wishlist functionality to shopping cart

REQUIREMENTS:
- Users can add items to wishlist
- Wishlist persists across sessions
- Move items between cart and wishlist
- Share wishlist via link

DELIVERABLES:
1. Database schema for wishlists
2. API endpoints (CRUD operations)
3. Frontend components
4. Unit and integration tests
EOF

# 2. Launch orchestration
./auto_orchestrate.py --project ~/projects/ecommerce --spec feature-spec.md

# 3. Monitor progress
./monitoring_dashboard.py &

# 4. Check in after 30 minutes
./send-claude-message.sh ecommerce-impl:0 "Status update on wishlist feature?"
```

### Workflow 2: Deploying a Production Service
```bash
# 1. Create deployment specification
cat > deploy-spec.md << 'EOF'
PROJECT: API Service Deployment
TARGET: production-server.example.com
SERVICE: FastAPI Order Processing

REQUIREMENTS:
- Install Python 3.11 environment
- Configure PostgreSQL connection
- Set up Nginx reverse proxy
- Implement systemd service
- Configure monitoring
- SSL certificate setup

SECURITY:
- Firewall rules for port 443 only
- API key authentication
- Rate limiting
EOF

# 2. Deploy specialized team
./auto_orchestrate.py \
  --project /opt/deployments/order-api \
  --spec deploy-spec.md \
  --team-type system_deployment

# 3. Monitor deployment
./claude_control.py monitor --interval 5

# 4. Verify deployment
./send-claude-message.sh order-api-impl:1 "Run health checks on all endpoints"
```

### Workflow 3: Handling Credit Exhaustion
```bash
# 1. Check credit status
./credit_management/check_agent_health.sh

# 2. If agents exhausted, wait or use resume
./auto_orchestrate.py --project ~/projects/webapp --resume

# 3. Monitor credit resets
./credit_management/credit_monitor.py --auto-resume &

# 4. Schedule work around resets
./schedule_with_note.sh 310 "Resume after credit reset" "webapp-impl:0"
```

### Workflow 4: Batch Processing with Intelligent Retry (NEW!)
```bash
# 1. Queue all project specs at once (NEW: automatic batch retry system)
./auto_orchestrate.py \
  --spec ~/specs/frontend-spec.md \
  --spec ~/specs/backend-spec.md \
  --spec ~/specs/mobile-spec.md

# 2. Start the queue daemon with intelligent retry
uv run scheduler.py --queue-daemon &

# The system now automatically:
# - Detects batch completion
# - Analyzes failed projects with research agent using Grok MCP
# - Creates enhanced specs with failure insights
# - Retries failed projects with improved specifications
# - Escalates permanent failures after 3 attempts

# 3. Monitor queue progress (shows retry counts and batch IDs)
uv run scheduler.py --queue-list

# 4. Check specific project status
uv run scheduler.py --queue-status 2

# 5. Monitor the currently processing project
./monitoring_dashboard.py

# 6. NEW: Use optimized local git workflow for 60-500x faster operations
./auto_orchestrate.py \
  --spec ~/specs/frontend-spec.md \
  --git-mode local
```

### Workflow 5: Multi-Project Coordination (Legacy)
```bash
# 1. Start multiple projects individually
./auto_orchestrate.py --project ~/projects/frontend --spec frontend-spec.md
./auto_orchestrate.py --project ~/projects/backend --spec backend-spec.md
./auto_orchestrate.py --project ~/projects/mobile --spec mobile-spec.md

# 2. Monitor all projects
./multi_project_monitor.py

# 3. Check active orchestrations
./concurrent_orchestration.py --list

# 4. Share insights between projects
./send-claude-message.sh frontend-impl:0 \
  "Backend team implemented new auth endpoint at /api/v2/auth"

# 5. Coordinate releases
./send-claude-message.sh backend-impl:0 \
  "Frontend will deploy at 2 PM, ensure API is ready"
```

### Workflow 5: Performance Issues & Optimization
```bash
# 1. Check system performance
./performance_tuner.py

# 2. If issues found, clean up
./performance_tuner.py --clean-logs

# 3. Run chaos test to identify weaknesses
./chaos_tester.py --duration 30 --dry-run

# 4. Optimize based on results
# Example: Too many tmux sessions
tmux ls | grep -E "old-project|test-" | cut -d: -f1 | xargs -I {} tmux kill-session -t {}
```

### Workflow 6: Testing Before Production
```bash
# 1. Run integration tests
./test_integration.py

# 2. Load test the system
./load_tester.py concurrent --count 10 --hold 300

# 3. Chaos engineering test
./chaos_tester.py --duration 60 --severity medium

# 4. Generate reports
./performance_tuner.py --json > pre-prod-report.json
./load_tester.py ramp --max 15 --json > load-report.json
```

### Workflow 7: Debugging Failed Orchestrations
```bash
# 1. Check what went wrong
./claude_control.py status webapp-impl

# 2. Read agent logs
tmux capture-pane -t webapp-impl:1 -p -S -1000 | less

# 3. Check git worktree status (worktrees are siblings to project!)
cd /path/to/webapp-tmux-worktrees/developer  # NOT in registry!
git status
git log --oneline -10
# Always verify with: git worktree list

# 4. Restart with specific instructions
./send-claude-message.sh webapp-impl:1 \
  "Previous attempt failed. Start fresh from main branch"
```

### Workflow 8: Quick Prototyping Session
```bash
# 1. Simple two-agent setup
tmux new-session -s prototype
claude  # In window 0

# 2. Brief the developer directly
"You're a Developer. Create a quick prototype for a URL shortener.
Tech stack: FastAPI + SQLite. Include basic tests.
Work in feature/url-shortener branch."

# 3. Schedule follow-up
./schedule_with_note.sh 45 "Review prototype and suggest improvements"
```

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
![Orchestrator Hero](/Orchestrator.png)

**Run AI agents 24/7 while you sleep** - The Tmux Orchestrator enables Claude agents to work autonomously, schedule their own check-ins, and coordinate across multiple projects without human intervention.

## 🤖 Key Capabilities & Autonomous Features

- **Self-trigger** - Agents schedule their own check-ins and continue work autonomously
- **Coordinate** - Project managers assign tasks to engineers across multiple codebases  
- **Persist** - Work continues even when you close your laptop
- **Scale** - Run multiple teams working on different projects simultaneously

## 🚀 Latest Updates (v3.7.2) - Git Workflow Automation & Session Validation

### 🔧 Major Fixes & Improvements

#### ✅ Git Commit-Tag-Push Automation (NEW!)
**Automated git workflow with semantic versioning and one-command deployment**

- **`git-ctp` Command**: Simple wrapper for commit-tag-push workflow
- **Automatic Versioning**: Detects version bump type from commit messages (feat→minor, fix→patch, breaking→major)
- **GitCommitManager**: Full-featured Python module for git automation
- **Agent Integration**: All orchestrated agents receive briefing about the feature
- **Co-Author Attribution**: Automatically adds Tmux Orchestrator as co-author

**Usage**: `./git-ctp "feat: add new feature"` → Commits, tags v1.1.0, and pushes

#### ✅ Scheduler Session Validation (NEW!)
**Prevents non-project sessions from receiving orchestrator messages**

- **Flexible Pattern Validation**: Accepts any session with hyphens (project-name, project-impl-uuid, etc.)
- **Smart Filtering**: Rejects numeric sessions ("0", "1"), common shells ("bash", "main"), and very short names
- **Automatic Cleanup**: Removes invalid tasks targeting regular tmux sessions
- **Protection**: Personal work sessions are protected from orchestrator messages

#### ✅ Agent Path Resolution Fixes
**Fixed agent briefing paths for worktree environments**

- **Absolute Path References**: Orchestrator CLAUDE.md now uses absolute paths
- **Worktree-Aware Commands**: Initial commands check for shared directories first
- **Fallback Support**: Gracefully handles both worktree and non-worktree environments

#### ✅ Standardized Tmux Communication System
**Complete overhaul of agent messaging to eliminate garbled output and ensure reliable delivery**

- **Enhanced MCP Wrapper Removal**: Comprehensive pattern matching for all MCP contamination variants
- **TmuxMessenger Class**: Unified messaging system replacing fragmented subprocess calls
- **Shell-Level Prevention**: Enhanced `send-claude-message.sh` with multi-layer cleaning
- **Guaranteed Enter Keys**: Reliable message delivery through existing script mechanisms
- **`scm` Command**: Standardized wrapper with comprehensive contamination removal

#### ✅ Project Recovery & Scheduling Reliability  
**Fixed critical issues preventing proper orchestrator operation**

- **Project Recovery**: Resolved false failure detection and session name repair
- **Rogue Scheduler Cleanup**: Removed conflicting scheduler starts from scripts
- **Systemd Integration**: Enhanced dual-service architecture for production reliability
- **PATH Resolution**: Fixed UV command access issues in systemd services

### 🛠️ System Requirements & Essential Services

**What MUST Run for Proper Operation:**

The Tmux Orchestrator uses **dual systemd services** for maximum reliability:

#### 1. Check-in Scheduler Service (REQUIRED for Orchestrator Messages)
**Purpose**: Sends scheduled check-ins to orchestrators with completion reminders
**Status**: ✅ Enhanced with completion detection reminders
**Recommended**: Use systemd service (see section 3 below)

```bash
# Manual start (development only - use systemd for production)
python3 scheduler.py --daemon --mode checkin > scheduler_checkin.log 2>&1 &

# Check if running
ps aux | grep "scheduler.py.*--mode checkin" | grep -v grep
```

#### 2. Queue Processor Service (REQUIRED for Batch Projects)
**Purpose**: Processes multiple projects sequentially from the project queue
**Status**: ✅ Independent service with separate lock management
**Recommended**: Use systemd service (see section 3 below)

```bash
# Manual start (development only - use systemd for production)  
python3 scheduler.py --daemon --mode queue > scheduler_queue.log 2>&1 &

# Check if running
ps aux | grep "scheduler.py.*--mode queue" | grep -v grep
```

#### 3. Systemd Services (RECOMMENDED for Production)
**New Dual-Service Architecture**: Separate systemd services for check-in scheduler and queue processor

**Benefits**: 
- Clean separation of concerns
- No race conditions between services  
- Automatic restart on failures
- Boot-time service activation
- Centralized logging via journalctl

```bash
# Install both services
sudo cp systemd/tmux-orchestrator-checkin.service /etc/systemd/system/
sudo cp systemd/tmux-orchestrator-queue.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable tmux-orchestrator-checkin tmux-orchestrator-queue
sudo systemctl start tmux-orchestrator-checkin tmux-orchestrator-queue

# Check status
sudo systemctl status tmux-orchestrator-checkin
sudo systemctl status tmux-orchestrator-queue

# View logs
journalctl -u tmux-orchestrator-checkin -f
journalctl -u tmux-orchestrator-queue -f
```

#### Quick Health Check

**For systemd services (recommended)**:
```bash
# Check service status
sudo systemctl status tmux-orchestrator-checkin tmux-orchestrator-queue

# Check processes
ps aux | grep scheduler | grep -v grep
# Should show:
# - python3 scheduler.py --daemon --mode checkin   (check-ins)
# - python3 scheduler.py --daemon --mode queue     (batch processing)
```

**For manual processes**:
```bash  
# Verify both schedulers are running
ps aux | grep scheduler | grep -v grep

# Should show:
# - python3 scheduler.py --daemon --mode checkin   (check-ins)  
# - python3 scheduler.py --daemon --mode queue     (batch processing)
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
- **🆕 Completion Reminders**: Check-in messages now remind orchestrators to call CompletionManager when projects reach completion

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

### 🆕 Modular Architecture v2.0

The Tmux Orchestrator has been completely rewritten with a modular architecture for better maintainability, testability, and extensibility:

```
tmux_orchestrator/                    # Main package
├── core/                            # Core orchestration logic
│   ├── orchestrator.py             # Main orchestrator with dependency injection
│   ├── session_manager.py          # Session lifecycle management
│   └── state_manager.py            # Global state coordination
├── claude/                          # Claude initialization
│   ├── initialization.py           # Claude startup with MCP
│   └── oauth_manager.py            # Critical OAuth timing (45-60s)
├── agents/                          # Agent management
│   ├── agent_factory.py            # Dynamic agent creation
│   └── briefing_system.py          # Role-specific briefings
├── git/                             # Git operations
│   └── worktree_manager.py         # Worktree isolation & fallback
├── tmux/                            # Tmux operations
│   ├── session_controller.py       # Session lifecycle
│   └── messaging.py                # Inter-agent communication
├── database/                        # Data management
│   └── queue_manager.py            # Task prioritization
├── monitoring/                      # System monitoring
│   └── health_monitor.py           # Performance & health tracking
├── utils/                           # Utilities
│   ├── file_utils.py               # JSON/YAML operations
│   ├── system_utils.py            # System operations
│   └── config_loader.py           # Configuration management
└── cli/                            # Command-line interface
    └── enhanced_cli.py             # Rich CLI with progress tracking
```

### Key Architectural Improvements

- **Dependency Injection**: All modules support DI for testing and customization
- **Clean Separation**: Each module has a single responsibility
- **Preserved OAuth Logic**: Critical 45-60 second timing preserved in dedicated module
- **Flexible Integration**: Modules can be used independently or together
- **Comprehensive Testing**: Each phase has full test coverage
- **Production Ready**: Score of 88.8/100 in production readiness assessment

### Agent Communication Flow

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

### System Services (RECOMMENDED for Production)

#### Triple-Service Architecture (NEW!)
The system now uses three systemd services for complete automation:

```bash
# Install all three services
sudo cp systemd/tmux-orchestrator-checkin.service /etc/systemd/system/
sudo cp systemd/tmux-orchestrator-queue.service /etc/systemd/system/
sudo cp systemd/tmux-orchestrator-completion.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start all services
sudo systemctl enable tmux-orchestrator-checkin tmux-orchestrator-queue tmux-orchestrator-completion
sudo systemctl start tmux-orchestrator-checkin tmux-orchestrator-queue tmux-orchestrator-completion

# Check status of all services
sudo systemctl status tmux-orchestrator-checkin tmux-orchestrator-queue tmux-orchestrator-completion
```

**🎯 NEW: Completion Monitoring Service**
The completion service automatically monitors all PROCESSING projects and detects when they're complete:

- **Automatic Detection**: Polls every 5 minutes for project completion
- **Smart Validation**: Uses the same completion logic as manual checks
- **Database Updates**: Automatically updates project status to COMPLETED
- **Email Notifications**: Sends completion notifications (if configured)
- **Resource Cleanup**: Triggers proper decommissioning workflows

**Service Architecture:**
```
┌─ Checkin Service ──┐    ┌─ Queue Service ─────┐    ┌─ Completion Service ─┐
│ Agent check-ins    │    │ Processes queue     │    │ Monitors completions  │
│ Status updates     │    │ Starts projects     │    │ Updates database      │
│ Progress tracking  │────┤ Manages lifecycle   │────┤ Triggers cleanup      │
└────────────────────┘    └─────────────────────┘    └───────────────────────┘
```

**Benefits:**
- **No Race Conditions**: Each service uses independent lock files
- **Complete Automation**: Projects auto-complete without manual intervention
- **Independent Restart**: Services restart independently on failure
- **Better Monitoring**: Service-specific logs and status monitoring

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

## 📁 System Files & Database Architecture

The Tmux Orchestrator manages complex multi-agent operations through various databases, configuration files, and runtime components. Understanding these files is crucial for troubleshooting and system management.

### 💾 Core Databases & Data Storage

| Database/File | Purpose | Location | Schema |
|---------------|---------|----------|--------|
| **`task_queue.db`** | Main SQLite database for all operations | `/home/clauderun/Tmux-Orchestrator/task_queue.db` | Projects, agents, tasks, messages |
| **`sessions.json`** | Active tmux session tracking | `registry/sessions.json` | Session states and metadata |
| **`.orchestrator/scheduler.db`** | Legacy scheduler database (deprecated) | `~/.orchestrator/scheduler.db` | Old task scheduling |

#### 🗃️ task_queue.db Schema (Primary Database)
```sql
-- Project management
project_queue         # Queued projects and batch processing
├── id, spec_path, project_path, status, enqueued_at, started_at, completed_at

-- Agent management  
agents               # Active agent tracking and health
├── agent_id, project_name, status, last_heartbeat, ready_since

-- Task scheduling
tasks               # Scheduled check-ins and recurring tasks
├── id, session_name, agent_role, window_index, next_run, interval_minutes, note

-- Inter-agent messaging (NEW: hooks-based system)
message_queue       # Agent-to-agent message delivery via hooks
├── id, agent_id, message, priority, status, sequence_number, created_at

-- System tracking
session_events      # Session lifecycle events
agents_context      # Agent context preservation
migrations         # Database schema version control
```

### 🏗️ Project Directory Structure

```
Tmux-Orchestrator/                    # Main system directory
├── 📂 docs/                          # All documentation
│   ├── INDEX.md                      # Documentation index
│   ├── architecture/                 # System design specs
│   ├── guides/                      # Implementation guides
│   ├── investigations/              # Deep-dive analyses
│   └── troubleshooting/            # Issue resolutions
│
├── 📂 claude_hooks/                  # NEW: Hooks-based messaging system
│   ├── check_queue.py               # Main message delivery script
│   ├── tmux_message_sender.py       # Smart tmux communication
│   ├── cleanup_agent.py            # Session cleanup handler
│   ├── enqueue_message.py          # Message queuing utility
│   └── settings.json               # Hook configuration template
│
├── 📂 monitoring/                    # System monitoring tools
│   ├── compliance_monitor.py        # Process compliance checking
│   ├── monitored_send_message.sh   # Message delivery tracking
│   └── workflow_monitor.py         # Workflow state monitoring
│
├── 📂 registry/                     # Runtime state and data
│   ├── projects/                   # Active project registrations
│   ├── logs/                      # System and agent logs
│   ├── sessions.json             # Session state tracking
│   └── notes/                    # Orchestrator notes
│
├── 📂 locks/                        # Process coordination locks
├── 📂 session_states/               # Agent session persistence
├── 📂 systemd/                      # Service configurations
├── 📂 Examples/                     # Usage screenshots
│
├── 🗄️ task_queue.db                  # PRIMARY DATABASE
├── 📋 CLAUDE.md                      # Agent coordination rules
└── 🔧 config.local.sh               # Local system configuration
```

### 🔧 Core Configuration Files

| File | Purpose | Contains |
|------|---------|----------|
| **`CLAUDE.md`** | Agent briefing & coordination rules | Role definitions, communication protocols, project guidelines |
| **`config.sh` / `config.local.sh`** | System configuration | Paths, settings, environment variables |
| **`.claude/settings.json`** | Agent-specific hook configurations | PostToolUse, Stop, PostCompact, SessionStart, SessionEnd hooks |
| **`systemd/*.service`** | Service definitions | tmux-orchestrator-checkin, tmux-orchestrator-queue services |

### 📊 Project-Specific Files (Per Project)

When a project is created, the following structure is generated:

```
project-name/                        # Main project directory
└── project-name-tmux-worktrees/    # Agent worktree directory (sibling to project)
    ├── orchestrator/               # Orchestrator agent workspace
    │   ├── .claude/
    │   │   ├── settings.json      # Agent-specific hook config
    │   │   └── hooks/            # Symlinks to system hooks
    │   └── shared/               # Cross-agent shared files
    ├── project_manager/           # Project Manager workspace
    ├── developer/                # Developer workspace  
    ├── tester/                   # Tester workspace
    └── testrunner/              # TestRunner workspace
```

### 🔄 Hooks System Files (NEW)

The new hooks-based messaging system uses these components:

| Component | File | Purpose |
|-----------|------|---------|
| **Message Queue Checker** | `claude_hooks/check_queue.py` | Main script that checks for pending messages |
| **Message Sender** | `claude_hooks/tmux_message_sender.py` | Smart tmux send-keys delivery system |
| **Hook Configuration** | `.claude/settings.json` | Defines when hooks trigger (PostToolUse, Stop, etc.) |
| **Message Enqueuer** | `claude_hooks/enqueue_message.py` | Utility to add messages to queue |
| **Cleanup Handler** | `claude_hooks/cleanup_agent.py` | Session cleanup on agent termination |

### 🚨 Critical System Files

**⚠️ DO NOT DELETE THESE FILES:**

| File | Critical Because | Recovery Method |
|------|------------------|-----------------|
| **`task_queue.db`** | Contains all project and agent state | Automatic recreation, but all history lost |
| **`CLAUDE.md`** | Agent coordination and briefing rules | System becomes uncoordinated without it |
| **`scheduler.py`** | Core scheduling daemon | No check-ins or project processing |
| **`auto_orchestrate.py`** | Main project creation entry point | Cannot start new projects |
| **systemd service files** | Persistent system operation | Manual process management required |

### 🔍 Database Locations by Use Case

```bash
# Main system database (ALL operations)
/home/clauderun/Tmux-Orchestrator/task_queue.db

# Project-specific databases (hooks system)
/home/clauderun/project-worktrees/orchestrator/task_queue.db  # Symlink to main

# Legacy scheduler database (deprecated, but may exist)
/home/clauderun/.orchestrator/scheduler.db                    # Old format

# Session state files
/home/clauderun/Tmux-Orchestrator/registry/sessions.json     # Active sessions
/home/clauderun/Tmux-Orchestrator/session_states/           # Individual state files
```

### 📋 File Usage by System Component

| Component | Files Used | Purpose |
|-----------|------------|---------|
| **Scheduler Daemon** | `task_queue.db`, `scheduler.py` | Task scheduling and execution |
| **Auto Orchestrator** | `task_queue.db`, `CLAUDE.md`, project worktrees | Project creation and management |
| **Hooks System** | `task_queue.db`, `.claude/settings.json`, `claude_hooks/*.py` | Inter-agent messaging |
| **Project Manager** | Project-specific worktree, `shared/` directory | Cross-agent coordination |
| **Monitoring** | `registry/logs/`, `sessions.json`, `task_queue.db` | System health and status |

### 🧹 Maintenance & Cleanup

**Safe to clean:**
- `registry/logs/` (old log files)
- `locks/` (stale lock files)
- Temporary worktree directories (after project completion)

**Never clean:**
- `task_queue.db` (primary database)
- `CLAUDE.md` (agent coordination rules)
- Active project worktrees
- `systemd/` service files

This file structure enables the Tmux Orchestrator's autonomous multi-agent operations, persistent scheduling, and robust project lifecycle management.

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

# Send message to agent (NEW: standardized messaging)
scm session:window "message"

# Git commit-tag-push workflow (NEW: automated versioning)
./git-ctp "feat: implement new feature"

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

### 🔧 Systemd Services (RECOMMENDED)
For production deployments, use the new dual-service architecture:

```bash
# Install both services (NEW - replaces single service)
sudo cp systemd/tmux-orchestrator-checkin.service /etc/systemd/system/
sudo cp systemd/tmux-orchestrator-queue.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable tmux-orchestrator-checkin tmux-orchestrator-queue
sudo systemctl start tmux-orchestrator-checkin tmux-orchestrator-queue

# Check status
sudo systemctl status tmux-orchestrator-checkin tmux-orchestrator-queue

# View logs
journalctl -u tmux-orchestrator-checkin -f    # Check-in scheduler
journalctl -u tmux-orchestrator-queue -f      # Queue processor

# Stop services
sudo systemctl stop tmux-orchestrator-checkin tmux-orchestrator-queue
```

**Migration from Single Service:**
- Old: `tmux-orchestrator-scheduler.service`
- New: `tmux-orchestrator-checkin.service` + `tmux-orchestrator-queue.service`  
- Benefits: No race conditions, better reliability, independent restarts

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
| **`git-ctp`** | Git commit-tag-push automation | One-command version deployment |
| **`git_commit_manager.py`** | Git workflow automation module | Advanced git automation |

### Management & Monitoring Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| **`claude_control.py`** | Agent status monitoring | Check what agents are doing |
| **`sync_dashboard.py`** | Sync status dashboard | Monitor git synchronization |
| **`multi_project_monitor.py`** | Multi-project overview | Managing multiple orchestrations |
| **`performance_tuner.py`** | Performance optimization | System tuning and cleanup |
| **`completion_monitor_daemon.py`** 🆕 | Automatic completion monitoring | Background completion detection |
| **`check_project_completion.py`** | Manual completion check | Verify if projects are complete |
| **`queue_status.py` (./qs)** | Project queue status | Check project completion status |

#### 🎯 Completion Monitoring Commands (NEW!)

```bash
# Check if a specific project is complete
python3 check_project_completion.py <project_id>

# Test completion monitoring (one cycle)
python3 completion_monitor_daemon.py --test

# Run completion monitor manually
python3 completion_monitor_daemon.py --poll-interval 60

# Check completion service status  
sudo systemctl status tmux-orchestrator-completion
sudo journalctl -u tmux-orchestrator-completion -f

# View completion monitoring logs
tail -f completion_monitor.log

# Quick project status check
./qs  # Shows all projects and their completion status
```

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

### 🆕 JSON Spec Mapping (NEW!)

The `auto_orchestrate.py` script now supports JSON configuration files that map specification files to their target project directories. This enables centralized spec management and batch processing with custom project locations.

#### JSON Schema
```json
{
  "version": "1.0",
  "specs": [
    {
      "spec_file": "path/to/spec.md",
      "project_directory": "/absolute/path/to/project",
      "enabled": true,
      "tags": ["integration", "backend"],
      "new_project": false
    }
  ],
  "batch_config": {
    "parallel": false,
    "continue_on_error": true,
    "log_level": "INFO"
  }
}
```

**Field Descriptions:**
- `spec_file`: Path to the .md specification file (relative paths resolved from JSON location)
- `project_directory`: Target directory for the project
- `enabled`: Whether to process this spec (default: true)
- `tags`: Optional tags for filtering with `--filter-tags`
- `new_project`: **NEW!** Whether to create a new project (true) or use existing (false, default)

**How `new_project` Works:**
- When `true`: Creates a new git repository at `{project_directory}_YYYYMMDD_HHMMSS`
- When `false`: Uses the existing directory specified in `project_directory`
- Mixed mode supported: Some specs can create new projects while others use existing ones
- New projects get the spec file copied and committed as the initial commit

#### JSON Usage Examples
```bash
# Process a single JSON spec mapping
./auto_orchestrate.py --spec integration_config.json

# Validate JSON without processing
./auto_orchestrate.py --spec integration_config.json --validate-json

# Filter specs by tags
./auto_orchestrate.py --spec integration_batch.json --filter-tags backend api

# Mix JSON and regular specs
./auto_orchestrate.py --spec config.json --spec additional_spec.md
```

#### Example JSON Configuration
```json
{
  "version": "1.0",
  "specs": [
    {
      "spec_file": "./integrate_web_server.md",
      "project_directory": "/home/user/web_server_v2",
      "enabled": true,
      "tags": ["backend", "api", "integration"],
      "new_project": false
    },
    {
      "spec_file": "./new_mobile_app.md", 
      "project_directory": "/home/user/projects/mobile",
      "enabled": true,
      "tags": ["mobile", "android", "client"],
      "new_project": true
    },
    {
      "spec_file": "./integrate_shared_auth.md",
      "project_directory": "/home/user/shared_libs/auth",
      "enabled": false,
      "tags": ["library", "authentication"]
    }
  ],
  "batch_config": {
    "parallel": false,
    "continue_on_error": true,
    "log_level": "INFO"
  }
}
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
- **JSON Spec Mapping**: Map specs to specific project directories using JSON configuration files
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

## 🔄 Project Lifecycle Process

### Complete Project Flow from Start to Finish

The Tmux Orchestrator manages the complete project lifecycle with automated detection, coordination, and cleanup:

#### Phase 1: Project Initialization

1. **Specification Analysis**: `auto_orchestrate.py` analyzes project specs and requirements
2. **Team Deployment**: Dynamic team configuration based on project type (web app, system deployment, etc.)
3. **Worktree Creation**: Git worktrees created as siblings to project directory (e.g., `project-tmux-worktrees/`)
4. **Session Setup**: Tmux sessions created for each agent role with proper window naming
5. **Database Entry**: Project queued in SQLite database with 'queued' status
6. **Agent Briefing**: Role-specific briefings sent to each agent with project context

#### Phase 2: Active Development

1. **Status Transition**: Scheduler moves project from 'queued' to 'processing' status
2. **Regular Check-ins**: Scheduler sends periodic check-ins to orchestrators with completion reminders:
   ```
   SCHEDULED CHECK-IN: Time for your regular status update
   
   REMINDER: Please check if your project has reached completion. 
   If all success criteria are met, call the CompletionManager to mark 
   the project complete and trigger proper decommissioning.
   ```
3. **Agent Coordination**: Agents work autonomously, committing every 30 minutes to their branches
4. **Progress Monitoring**: Multiple detection systems monitor project health:
   - **Agent-driven**: Agents signal completion via CompletionManager
   - **Timeout detection**: Projects exceeding 4 hours marked as stuck
   - **Phantom detection**: Missing tmux sessions or dead processes detected
   - **State synchronization**: DB-JSON consistency maintained

#### Phase 3: Completion Detection

**Multi-layered Detection System**:

1. **Reactive Detection**: Agents call CompletionManager when success criteria met
2. **Proactive Monitoring**: `check_stuck_projects` runs every 60 seconds checking for:
   - Projects exceeding timeout thresholds
   - Session liveness validation
   - Process activity monitoring
3. **Recovery Systems**: `detect_and_reset_phantom_projects` handles:
   - Missing tmux sessions
   - Dead auto_orchestrate.py processes
   - Session name recovery attempts

#### Phase 4: Decommissioning Process

When completion is detected, the system triggers coordinated cleanup:

1. **Status Update**: Database updated to 'completed' or 'failed' with timestamps
2. **Event Dispatch**: `project_complete` event sent via EventBus to notify subscribers
3. **Tmux Session Shutdown**: 
   - TmuxSessionManager kills session using `tmux kill-session`
   - Pattern matching used if exact session name unavailable
   - Registry cleanup performed post-shutdown
4. **State Reconciliation**: 
   - SessionStateManager updates JSON session states
   - StateSynchronizer repairs any DB-JSON mismatches
   - Orphaned session reconciliation runs every 10 minutes
5. **Resource Management**:
   - ProcessManager terminates timed-out subprocesses
   - Lock manager releases project locks
   - **Worktrees preserved** for manual merge operations (by design)

#### Phase 5: Post-Completion

1. **Integration Ready**: Git worktrees remain for manual code review and merge
2. **Reporting Available**: `list_completed_projects.py` provides completion analytics
3. **Cleanup Available**: Manual cleanup with `--force` flag if desired
4. **Metrics Collection**: Project duration, success rates, and failure reasons logged

### Error Handling & Recovery

**Multi-Level Safety Net**:

- **Tmux Failures**: Logged but don't halt system; graceful degradation
- **Database Errors**: Wrapped in try-catch with comprehensive logging
- **Lock Failures**: Cause graceful exit with automatic retry mechanisms  
- **Event Loops**: Prevented via event locks and processing state tracking
- **Reboot Recovery**: `_recover_from_reboot` resets processing projects on startup
- **Race Conditions**: Enhanced lock management prevents multiple scheduler instances

### Key Benefits of This Lifecycle

1. **Autonomous Operation**: Projects run 24/7 without human intervention
2. **Fault Tolerance**: Multiple detection and recovery mechanisms prevent stuck projects
3. **Resource Preservation**: Worktrees kept for code review and integration
4. **Complete Audit Trail**: Every phase logged with timestamps and status transitions
5. **Scalable Architecture**: Handles multiple concurrent projects efficiently

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
| **Only queue-daemon running** | Missing check-in scheduler | Start: `python3 scheduler.py --daemon &` |
| **No completion reminders** | Old scheduler daemon running | Restart check-in daemon to get enhanced version |

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

### 💬 Standardized Agent Communication (v3.7.0)

**NEW**: Use the `scm` (Standardized Claude Messaging) command for all agent communication:

```bash
# Send message to any Claude agent (RECOMMENDED)
scm session:window "Your message here"

# Examples:
scm frontend-impl:0 "What's your progress on the login form?"
scm backend-impl:1 "The API endpoint /api/users is returning 404"  
scm my-session:0 "Please coordinate with the QA team"

# Direct script usage (also works)
./send-claude-message.sh session:window "Your message here"
```

**Key Improvements in v3.7.0**:
- **MCP Wrapper Prevention**: Automatically removes contamination patterns at multiple levels
- **Guaranteed Delivery**: Enhanced retry logic with proper Enter key handling
- **Multi-Layer Cleaning**: Python (TmuxMessenger) → Shell (send script) → Entry point (scm)
- **Debugging**: Shows cleaning statistics when significant wrapper removal occurs

The new system eliminates garbled messages and ensures 100% reliable delivery to Claude agents.

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
./send-claude-message.sh my-session:0 "What's your current status?"

# Schedule a check-in
./schedule_with_note.sh 30 "Review implementation progress" "my-session:0"

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

# NEW: JSON spec mapping
./auto_orchestrate.py --spec integration_batch.json

# NEW: Validate JSON configuration
./auto_orchestrate.py --spec config.json --validate-json

# NEW: Filter by tags
./auto_orchestrate.py --spec batch.json --filter-tags backend integration
```

#### `send-claude-message.sh` - Agent Communication
```bash
# Check status of specific agent
./send-claude-message.sh my-session:0 "What's your current status?"

# Assign new task to developer
./send-claude-message.sh webapp-impl:1 "Please implement the login endpoint at /api/auth/login"

# Request test coverage report
./send-claude-message.sh webapp-impl:2 "Show me the current test coverage for authentication"

# Coordinate between agents
./send-claude-message.sh backend-impl:0 "The frontend needs a /api/users/profile endpoint"

# Emergency stop
./send-claude-message.sh my-session:0 "STOP all current work and report status"
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
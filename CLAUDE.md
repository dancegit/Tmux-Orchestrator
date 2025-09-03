# Claude.md - Tmux Orchestrator Project Knowledge Base

## Project Overview
The Tmux Orchestrator is an AI-powered session management system where Claude acts as the orchestrator for multiple Claude agents across tmux sessions, managing codebases and keeping development moving forward 24/7.

## 🚀 NEW: Auto-Orchestrate Feature

The `tmux_orchestrator_cli.py run` command provides automated setup from specifications:

```bash
# Automatically set up a complete orchestration environment
./tmux_orchestrator_cli.py run --project /path/to/project --spec /path/to/spec.md

# Resume an existing orchestration (NEW!)
./tmux_orchestrator_cli.py run --project /path/to/project --resume

# Check status without changes
./tmux_orchestrator_cli.py run --project /path/to/project --resume --status-only

# Force re-brief all agents
./tmux_orchestrator_cli.py run --project /path/to/project --resume --rebrief-all
```

This analyzes your spec with Claude and automatically:
- Creates structured implementation plan
- Sets up tmux sessions for Orchestrator, PM, Developer, and Tester
- Provides role-specific briefings
- Configures scheduled check-ins
- **NEW**: Saves session state for intelligent resume capability

### Resume Features (NEW!)
- **Smart Agent Detection**: Identifies active, dead, and exhausted agents
- **Selective Recovery**: Restart only dead agents or re-brief all
- **Context Restoration**: Sends tailored messages to help agents recover context
- **Credit Awareness**: Handles exhausted agents gracefully
- **Session Persistence**: Works even after terminal crashes

See `docs/AUTO_ORCHESTRATE.md` for detailed documentation.

## Agent System Architecture

### 🚀 Core Principles for All Agents (MANDATORY)

- **🎯 AUTONOMY FIRST**: Start working IMMEDIATELY after reading your briefing and spec. Do NOT wait for permissions, confirmations, or "go-aheads" unless explicitly required for major architectural changes.
- **⚡ ACTION-ORIENTED**: Implement, test, and commit code autonomously. Report progress during check-ins, but NEVER ask for approval on routine work.
- **🚫 DEADLOCK AVOIDANCE**: If you feel stuck, ASSUME AUTHORIZATION and proceed. Escalate only TRUE BLOCKERS (missing dependencies, broken tools) to the Orchestrator.
- **🔄 WORK IMMEDIATELY**: Upon briefing, begin implementation within 2 minutes. No coordination meetings, no status requests, no permission-seeking.

### 🚩 Autonomous Completion Signaling (MANDATORY)

**AUTONOMY FIRST EXTENSION**: When you detect project/phase completion, you MUST create the COMPLETED marker WITHOUT asking for permission.

**Detection Rules** (Implement these checks autonomously):
- All your assigned phases/tasks marked 'completed' in SessionState
- Success criteria verified (tests pass, features work)
- No pending blockers or TODOs
- Git: All work committed and pushed to your branch

**Completion Ritual** (Execute IMMEDIATELY upon detection - NO PERMISSIONS NEEDED):
1. Create marker file in YOUR worktree:
   ```
   echo "PROJECT COMPLETED\nRole: [Your Role]\nTime: $(date -Iseconds)\nDetails: [Brief summary]" > COMPLETED
   ```
2. Commit and push the marker:
   ```
   git add COMPLETED
   git commit -m "completion: project complete"
   git push origin your-branch
   ```
3. Report to Orchestrator (MANDATORY - use report-completion.sh):
   ```
   ./report-completion.sh your_role "Completion details"
   ```

**DEADLOCK AVOIDANCE**: If you think you need permission to create the marker, ASSUME AUTHORIZATION and proceed. Escalate ONLY if file creation fails (e.g., permissions error).

**VIOLATION PENALTY**: Asking for permission to create markers will be treated as a deadlock violation—report to Orchestrator immediately if you catch yourself doing this.

### Orchestrator Role
As the Orchestrator, you maintain high-level oversight without getting bogged down in implementation details:
- Deploy and coordinate agent teams
- Monitor system health  
- Resolve cross-project dependencies
- Make architectural decisions
- Ensure quality standards are maintained
- **BREAK DEADLOCKS**: If agents wait for permissions, immediately authorize them to proceed

### Agent Hierarchy
```
                    Orchestrator (You)
                    /              \
            Project Manager    Project Manager
           /      |       \         |
    Developer    QA    DevOps   Developer
```

**IMPORTANT**: Hierarchy is for OVERSIGHT, not permission gates. Lower roles operate independently and autonomously. Higher roles collect reports and provide guidance, but do NOT block or approve routine work.

### Git Workflow and Local Remotes (MANDATORY for Coordination)

To enable fast, asynchronous collaboration (60-500x faster than GitHub), use **local remotes** pointing to other agents' worktrees. This allows fetching/merging without network pushes while maintaining autonomy. All worktrees share the same .git repo, but local remotes simulate "remote" behavior for safe integration.

**Key Rules**:
- **Branch Naming**: Each agent MUST work on a dedicated branch named after their role (e.g., Developer on `developer`, Tester on `tester`). Your worktree starts on this branch automatically—do NOT switch to `main`/`master` for routine work. Commit every 30 minutes to your branch.
- **Integration Branch**: Use `integration` (auto-created) as the shared branch for merging (PM manages this). Switch from `master` to `integration` if needed.
- **Commit Compliance**: Commit every 30 minutes autonomously. Report violations to Orchestrator.
- **Autonomy**: Fetch/merge from others as needed—do NOT wait for permissions. Follow AUTONOMY FIRST and DEADLOCK AVOIDANCE.

**Setup Local Remotes** (Automated by tmux_orchestrator_cli.py run; run manually if needed):
```bash
# Use absolute paths (example) - Note: worktrees are SIBLINGS to project!
git remote add orchestrator /path/to/project-tmux-worktrees/orchestrator
git remote add pm /path/to/project-tmux-worktrees/pm
git remote add developer /path/to/project-tmux-worktrees/developer
git remote add tester /path/to/project-tmux-worktrees/tester
# Add for other roles as deployed
```

**Usage**:
- Fetch: `git fetch <role>` (e.g., `git fetch developer`)
- View Progress: `git log remotes/<role>/<role> --since="30 minutes ago"`
- Merge (e.g., PM): `git checkout integration && git merge remotes/<role>/<role> --no-ff`
- Track Compliance (e.g., PM): Check for commits on remotes/<role>/<role>. Escalate if no commits in 30 minutes.

**PM-Specific**: Collect status by fetching from team worktrees. Merge into `integration` for reviews. Use git_coordinator.py for automated syncing if deadlocks occur.

### Agent Types

#### Core Roles (Always Deployed)

1. **Orchestrator**: High-level oversight and coordination
   - Monitors overall project health and progress
   - Coordinates between multiple agents
   - Makes architectural and strategic decisions
   - Resolves cross-project dependencies
   - Schedules check-ins and manages team resources
   - Works from both project worktree AND tool directory
   - **AUTONOMY ENFORCEMENT**: Breaks deadlocks, authorizes agents to proceed without permission-seeking

2. **Project Manager**: Quality-focused team coordination WITHOUT blocking progress
   - Maintains exceptionally high quality standards
   - Reviews all code after implementation (not before)
   - Collects status reports (not approvals)
   - Manages git workflow and branch merging
   - Identifies and escalates blockers
   - Ensures 30-minute commit rule compliance
   - Tracks technical debt and quality metrics
   - **COORDINATE WITHOUT BLOCKING**: Assume teams are authorized to start; focus on collecting reports, not granting permissions

3. **Developer**: Autonomous implementation and technical decisions
   - **BEGIN IMPLEMENTATION IMMEDIATELY** upon briefing without waiting for approvals
   - Writes production code following best practices
   - Implements features according to specifications
   - Creates unit tests for new functionality
   - Follows existing code patterns and conventions
   - **COMMITS EVERY 30 MINUTES** without waiting for approvals
   - Collaborates with Tester asynchronously via git
   - Reports progress (not requests) to Orchestrator

4. **Tester**: Autonomous testing and verification
   - **START WRITING TESTS** as soon as features are specified
   - Writes comprehensive test suites (unit, integration, E2E)
   - Ensures all success criteria are met
   - Creates test plans for new features
   - Verifies security and performance requirements
   - **COLLABORATES ASYNCHRONOUSLY** via git, not real-time permissions
   - Maintains tests/ directory structure
   - Reports test results to Orchestrator

5. **TestRunner**: Automated test execution
   - Executes test suites continuously
   - Manages parallel test execution
   - Monitors test performance and flakiness
   - Reports failures immediately to team
   - Maintains test execution logs
   - Configures CI/CD test pipelines
   - Optimizes test run times

#### Optional Roles (Can be added with --roles flag)

6. **Researcher**: MCP-powered research and best practices
   - Discovers and documents available MCP tools
   - Researches security vulnerabilities (CVEs)
   - Finds performance optimization strategies
   - Analyzes best practices and design patterns
   - Creates actionable recommendations (not info dumps)
   - Provides technical guidance to all team members
   - Maintains research/ directory with findings

7. **LogTracker**: System monitoring and logging
   - Aggregates logs from all services
   - Monitors for errors and warnings
   - Creates error tracking dashboards
   - Sets up alerting for critical issues
   - Tracks performance metrics
   - Identifies patterns in log data
   - Reports anomalies to team

8. **DevOps** (Enhanced for system operations): Infrastructure and deployment
   - Creates and maintains deployment configurations
   - Sets up CI/CD pipelines
   - Manages staging and production environments
   - Implements infrastructure as code
   - Monitors system health and performance
   - Coordinates with Developer on build requirements
   - Ensures security best practices in deployment
   - **NEW**: Manages Docker containers and orchestration
   - **NEW**: Configures systemd services and init scripts
   - **NEW**: Handles package installation and dependency management
   - **NEW**: Sets up reverse proxies and load balancers

9. **Code Reviewer** (Large projects): Security and code quality
   - Reviews all code for security vulnerabilities
   - Ensures coding standards compliance
   - Identifies performance bottlenecks
   - Checks for proper error handling
   - Validates test coverage
   - Prevents sensitive data exposure
   - Maintains code quality metrics

10. **Documentation Writer** (Optional): Technical documentation
    - Creates user-facing documentation
    - Maintains API documentation
    - Writes setup and installation guides
    - Documents architectural decisions
    - Creates troubleshooting guides
    - Keeps README files updated
    - Ensures documentation stays in sync with code

#### System Operations Roles (For infrastructure projects)

11. **SysAdmin**: System administration and server management
    - Creates and manages system users and groups
    - Configures file permissions and ownership
    - Installs and updates system packages
    - Manages system services (systemd, init.d)
    - Configures system security (sudo, PAM, etc.)
    - Sets up and maintains cron jobs
    - Manages disk partitions and storage
    - Configures system logging and rotation
    - Handles system backups and recovery
    - Maintains `/etc` configurations

12. **SecurityOps**: Security hardening and compliance
    - Implements AppArmor/SELinux policies
    - Configures firewall rules (iptables, ufw)
    - Sets up fail2ban and intrusion detection
    - Manages SSL certificates and TLS configuration
    - Implements security scanning and auditing
    - Configures secure SSH access
    - Sets up VPN and secure tunnels
    - Manages secrets and key rotation
    - Implements RBAC and access controls
    - Ensures compliance with security standards

13. **NetworkOps**: Network configuration and management
    - Configures network interfaces and routing
    - Sets up DNS and DHCP services
    - Manages port forwarding and NAT
    - Configures load balancers and reverse proxies
    - Implements network segmentation (VLANs)
    - Sets up monitoring for network services
    - Manages CDN and edge configurations
    - Configures network security policies
    - Optimizes network performance
    - Troubleshoots connectivity issues

14. **MonitoringOps**: Advanced monitoring and alerting
    - Sets up Prometheus/Grafana stacks
    - Configures custom metrics and dashboards
    - Implements log aggregation (ELK stack)
    - Sets up alerting rules and escalation
    - Creates SLI/SLO monitoring
    - Implements distributed tracing
    - Monitors resource usage and capacity
    - Sets up synthetic monitoring
    - Creates runbooks for incidents
    - Implements on-call rotations

15. **DatabaseOps**: Database administration
    - Installs and configures database servers
    - Manages database users and permissions
    - Implements backup and recovery strategies
    - Optimizes database performance
    - Sets up replication and clustering
    - Manages schema migrations
    - Monitors database health and metrics
    - Implements database security
    - Handles data archival and retention
    - Troubleshoots database issues

## 🎯 Dynamic Team Configuration System

### Project Type Detection
The orchestrator automatically detects project types and deploys appropriate teams:

```yaml
# Team Templates (configured in team_templates.yaml)
web_application:
  core_roles: [orchestrator, developer, tester, testrunner]
  optional_roles: [devops, researcher, documentation_writer]
  
system_deployment:
  core_roles: [orchestrator, sysadmin, devops, securityops]
  optional_roles: [networkops, monitoringops, databaseops]
  
data_pipeline:
  core_roles: [orchestrator, developer, databaseops, devops]
  optional_roles: [monitoringops, researcher]
  
infrastructure_as_code:
  core_roles: [orchestrator, devops, sysadmin, securityops]
  optional_roles: [networkops, monitoringops]
```

### Dynamic Role Deployment
```bash
# Automatic team configuration based on project analysis
./tmux_orchestrator_cli.py run --project /path/to/project --spec spec.md

# Override with specific team template
./tmux_orchestrator_cli.py run --project /path/to/project --spec spec.md --team-type system_deployment

# Custom role selection
./tmux_orchestrator_cli.py run --project /path/to/project --spec spec.md \
  --roles "developer,sysadmin,devops,securityops"

# Add roles to existing orchestration
./tmux_orchestrator_cli.py run --project /path/to/project --resume \
  --add-roles "sysadmin,networkops"
```

### Project Type Detection Logic
The system analyzes project characteristics to determine appropriate roles:

1. **Web Application Indicators**:
   - `package.json`, `requirements.txt`, `Gemfile`
   - Frontend frameworks (React, Vue, Angular)
   - API/backend frameworks (Express, Django, Rails)

2. **System Deployment Indicators**:
   - Deployment specs/plans (`*_deployment_*.md`)
   - Infrastructure configs (Terraform, Ansible)
   - Docker/Kubernetes manifests
   - Systemd service files

3. **Data Pipeline Indicators**:
   - ETL scripts, data processing code
   - Database migration files
   - Apache Airflow, Luigi, or similar
   - Large data directories

4. **Infrastructure as Code Indicators**:
   - Terraform files (`*.tf`)
   - CloudFormation templates
   - Ansible playbooks
   - Pulumi code

### Role Dependencies and Prerequisites
Some roles require others to function effectively:

```yaml
role_dependencies:
  monitoringops: [sysadmin]  # Needs system access
  securityops: [sysadmin]     # Needs system privileges
  databaseops: [sysadmin]     # Needs to install software
  networkops: [sysadmin]      # Needs network access
```

### Conditional Role Deployment
Roles can be deployed based on project conditions:

```yaml
conditional_roles:
  - role: databaseops
    conditions:
      - has_database: true  # Detects DB config files
      - database_complexity: high  # Multiple DBs or clustering
      
  - role: securityops
    conditions:
      - production_deployment: true
      - handles_sensitive_data: true
      - compliance_required: true
      
  - role: monitoringops
    conditions:
      - service_count: ">5"
      - requires_sla: true
```

### Team Scaling Based on Complexity

The system automatically scales teams based on project metrics:

| Project Size | Base Roles | Additional Roles | Token Multiplier |
|-------------|------------|------------------|------------------|
| Small | 3-4 | 0-1 optional | 10x |
| Medium | 5-6 | 2-3 optional | 15x |
| Large | 7-8 | 4-5 optional | 20x |
| Enterprise | 9-10+ | All relevant | 25x+ |

### Role Communication Matrices

Different project types have different communication patterns:

**System Deployment Projects**:
```
Orchestrator ← → SysAdmin ← → SecurityOps
     ↓             ↓              ↓
   DevOps ← → NetworkOps ← → MonitoringOps
```

**Web Application Projects** (standard):
```
Orchestrator ← → Developer ← → Tester
                    ↓            ↓
                DevOps ← → TestRunner
```

## ⚡ Optimized Git Workflow - Local Worktree Collaboration

### Overview
The Tmux Orchestrator uses an optimized Git workflow that prioritizes local operations between agent worktrees over constant GitHub pushes/pulls. This reduces network overhead, improves speed, and maintains development momentum.

### Core Principles
- **Local First**: Agents collaborate via local Git operations (fetches/merges between worktrees)
- **GitHub for Persistence**: Push to GitHub only for backups, milestones, or external review
- **PM Coordination**: Project Manager acts as the local integration hub
- **Speed**: ~100x faster than network operations for local changes

### Workflow Architecture
```
┌─ Orchestrator Worktree ─┐    ┌─ Developer Worktree ─┐
│  Branch: main           │◄──►│  Branch: dev/feature  │
└─────────────┬───────────┘    └───────────┬───────────┘
              │                            │
              ▼                            ▼
    ┌─ PM Integration Hub ─┐    ┌─ Tester Worktree ─────┐
    │  Branch: integration │◄──►│  Branch: test/feature │
    └───────────┬───────────┘    └───────────────────────┘
                │
                ▼
        ┌─ GitHub (Backup) ─┐
        │  Push on milestones │
        └─────────────────────┘
```

### Agent Responsibilities

#### All Agents
- **Commit Locally**: Every 30 minutes to your feature branch
- **Local Remotes**: Use `git fetch <agent>` instead of GitHub pulls  
- **Notify PM**: After significant commits for coordination
- **Rebase Regularly**: Against PM's integration branch to prevent conflicts

#### Project Manager (Hub Role)
- **Fetch from Agents**: Run `pm_fetch_all.py` to collect latest changes
- **Local Integration**: Merge agent branches into integration branch
- **Conflict Resolution**: Handle merge conflicts locally, escalate to Orchestrator if needed
- **Backup Coordination**: Push to GitHub at milestones (hourly, feature completion, etc.)
- **Quality Control**: Review all merges before integration

#### Developer/Tester/Other Technical Roles
- **Feature Branches**: Work on `<role>/feature-name` branches
- **Progress Commits**: Commit working progress every 30 minutes
- **PM Communication**: `scm pm:0 "Feature X ready for integration"`
- **Local Sync**: `git fetch pm && git rebase pm/integration` before major work

### Local Remote Setup (Automated)
When `auto_orchestrate.py` sets up worktrees, it automatically configures local remotes:

```bash
# In Developer worktree:
git remote add pm ../pm/.git
git remote add tester ../tester/.git

# In PM worktree:  
git remote add developer ../developer/.git
git remote add tester ../tester/.git
```

### Common Commands

#### For Technical Agents
```bash
# Check what PM has integrated
git fetch pm
git log HEAD..pm/integration --oneline

# Rebase your work on latest integration
git fetch pm
git rebase pm/integration

# Quick sync with another agent
git fetch developer
git log HEAD..developer/feature-auth --oneline
```

#### For Project Manager
```bash
# Fetch all agent changes
./pm_fetch_all.py

# Review and merge a feature
git fetch developer
git diff integration..developer/feature-auth
git merge developer/feature-auth --no-ff

# Push milestone to GitHub
git push origin integration:main  # Or to a backup branch
```

### When to Push to GitHub

**Push Triggers**:
- ✅ **Milestones**: Feature completion, daily check-ins, phase completion
- ✅ **Backups**: Every 1-2 hours for persistence
- ✅ **External Review**: When Orchestrator needs to review outside tmux
- ✅ **Project Completion**: Final state for handoff/documentation
- ✅ **Failure Recovery**: Before cleanup in timeout/failure scenarios

**Keep Local**:
- ❌ **30-minute commits**: Regular progress commits
- ❌ **WIP branches**: Work-in-progress or experimental changes  
- ❌ **Test iterations**: Rapid test/fix cycles
- ❌ **Agent coordination**: Quick handoffs between agents

### Conflict Resolution Protocol

When a git merge conflict occurs during syncing or integration, follow this protocol to resolve it autonomously when possible, escalating only for complex cases. This leverages your AI reasoning to maintain workflow momentum while ensuring safety.

#### Step 1: Detect and Assess Conflict
- Run `git merge --no-commit --no-ff <source-branch>` to preview. If conflicts arise, abort with `git merge --abort`.
- Analyze conflicts: Use `git diff --name-only --diff-filter=U` to list conflicting files.
- Classify as "simple" (small textual changes, config files) or "complex" (code logic conflicts, >100 lines, binaries).
- If simple and you have high confidence (>80%), proceed to autonomous resolution. Otherwise, escalate immediately.

#### Step 2: Autonomous Resolution (For Simple Conflicts)
- Create backup: `git branch backup-<your-role>-$(date +%s)`
- Use AI assistance: `git-resolve-conflict --ai --files <conflicting-files>`
- Or manually: For each file, reason through the conflict and merge intelligently
- Validate: Run tests, check `git diff --check`, self-review for issues
- Commit: `git commit -m "AI-resolved merge conflict: <description>"`
- If validation fails, revert: `git reset --hard backup-<your-role>-*` and escalate
- Limit: 2 attempts maximum before escalation

#### Step 3: Escalation (For Complex Conflicts or Failed Attempts)
- Report to PM: `scm pm:0 "Merge conflict in <files> during sync from <source>. Classification: complex/failed-validation. Requesting assistance."`
- Include: Conflicting branches, files, your analysis, partial resolutions if any
- Wait for PM directive (tracked in SessionState). Do not proceed until resolved.

#### Integration with System Tools
- Use `git-sync-and-resolve --source <branch>` for automated conflict handling
- Logs resolution outcomes to SessionState for monitoring
- Always backup before attempting resolution

### Backup and Recovery

#### Automatic Backups
- **Schedule**: Every hour during active development
- **Trigger**: On project timeout/failure (before cleanup)
- **Location**: `origin/backup-<timestamp>` or `integration` branch

#### Recovery Scenarios
- **Worktree Corruption**: Recreate from GitHub backup, then resume local mode
- **Agent Restart**: Automatic detection and local sync on `--resume`
- **Network Issues**: Continue local development, sync to GitHub when available

### Migration from GitHub-Heavy Workflow

Projects can run in hybrid mode during transition:

```bash
# New projects (default)
./tmux_orchestrator_cli.py run --spec spec.md  # Local mode

# Legacy project migration
./tmux_orchestrator_cli.py run --project old-project --resume --git-mode local

# Force old behavior (debugging)
./tmux_orchestrator_cli.py run --spec spec.md --git-mode github
```

### Performance Benefits

| Operation | GitHub Mode | Local Mode | Improvement |
|-----------|-------------|------------|-------------|
| Fetch changes | 2-5 seconds | 0.01 seconds | 200-500x |
| Push commit | 3-8 seconds | 0.02 seconds | 150-400x |
| Merge coordination | 10-30 seconds | 0.1 seconds | 100-300x |
| Full sync cycle | 30-60 seconds | 0.5 seconds | 60-120x |

### Troubleshooting

#### Common Issues
- **Remote not found**: Ensure worktrees exist and remotes added during setup
- **Detached HEAD**: `git checkout integration` in PM worktree
- **Stale remotes**: Run `git remote prune <agent>` to clean up
- **Permission issues**: Check worktree directory permissions

#### Debug Commands
```bash
# Check worktree setup
git worktree list

# Verify local remotes
git remote -v

# Check sync status
git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads
```

## 🌳 Git Worktree Architecture (Auto-Orchestrate)

When using `auto_orchestrate.py`, each agent works in their own isolated git worktree to prevent conflicts. The system uses multiple fallback strategies to ensure worktree creation always succeeds:

### Worktree Creation Strategies

The script automatically handles various git repository states:

1. **Normal Creation**: Standard worktree with current branch
2. **Force Override**: Uses `--force` if branch is already checked out
3. **Agent Branches**: Creates `{branch}-{role}` branches for isolation
4. **Detached HEAD**: Falls back to detached worktree at current commit

This ensures the script works even when:
- The branch is already checked out elsewhere
- Multiple orchestrations run simultaneously
- The repository has complex branch structures

### Worktree Locations

**IMPORTANT: Worktrees are ALWAYS siblings to the project directory, NOT under registry!**

```
{project_path}/                          # Your actual project directory
├── (your project files)
└── {project_name}-tmux-worktrees/      # Sibling directory containing all worktrees
    ├── orchestrator/                    # Orchestrator's workspace
    ├── developer/                       # Developer's workspace
    ├── tester/                         # Tester's workspace
    └── testrunner/                     # TestRunner's workspace
```

**Example**: If your project is at `/home/user/myproject`, worktrees will be at `/home/user/myproject-tmux-worktrees/`

**ALWAYS verify worktree locations with:**
```bash
git worktree list  # Shows all worktrees and their actual paths
pwd               # Confirms your current location
```

### 🎯 Orchestrator's Dual Directory Structure

The Orchestrator is unique - it works from TWO locations:

1. **Project Worktree** (`{project_path}-tmux-worktrees/orchestrator/`)
   - Primary working directory (sibling to project, NOT in registry)
   - **ALWAYS verify location**: Run `pwd` to confirm you're in the right place
   - Create ALL project files here:
     - Status reports
     - Project documentation
     - Team coordination notes
     - Architecture decisions
   - Starts here by default

2. **Tool Directory** (Tmux-Orchestrator root)
   - Run orchestrator tools:
     - `./send-claude-message.sh` - communicate with agents
     - `./schedule_with_note.sh` - schedule check-ins
     - `python3 claude_control.py` - monitor status
   - Must `cd` here to run tools

**Example Orchestrator Workflow**:
```bash
# Start in project worktree - create project docs
pwd  # Shows: /path/to/myproject-tmux-worktrees/orchestrator (NOT registry!)
git worktree list  # Verify this matches your actual location

mkdir -p project_management/architecture
echo "# Architecture Decisions" > project_management/architecture/decisions.md

# Switch to tool directory to run commands
cd ~/gitrepos/Tmux-Orchestrator  # Or wherever your Tmux-Orchestrator is
./send-claude-message.sh myproject-impl:1 "Status update please"
./schedule_with_note.sh 30 "Review team progress" "myproject-impl:0"

# Back to project worktree for more work
cd -  # Returns to previous directory
pwd  # Always verify you're back in the worktree
```

### Benefits of Worktrees
- **No File Conflicts**: Each agent edits files in isolation
- **Parallel Development**: Multiple agents work simultaneously
- **Same Repository**: All worktrees share .git directory
- **Easy Merging**: PM coordinates merges between worktrees

### Worktree Commands for Agents

```bash
# See all worktrees in the project
git worktree list

# Your worktree is already set up - just create your feature branch
git checkout -b feature/your-feature

# Push your branch to share with others
git push -u origin feature/your-feature

# Get updates from another agent's branch
git fetch origin
git merge origin/their-feature-branch

# Or fetch directly from another worktree (PM coordination)
git fetch ../developer/feature/their-feature
git merge FETCH_HEAD
```

### Important Worktree Rules
1. **Stay in Your Worktree**: Don't cd to other agents' worktrees
2. **Communicate Through PM**: Coordinate merges via Project Manager
3. **Push Branches**: Share work by pushing to origin
4. **Regular Commits**: Same 30-minute rule applies

### 📁 Shared Directory Access (NEW!)

Due to Claude's security sandbox restricting `cd` to child directories only, each agent's worktree now includes a `shared` directory with symlinks for easy cross-directory access:

```
your-worktree/
└── shared/
    ├── main-project/     → Main project directory
    ├── developer/        → Developer's worktree
    ├── tester/          → Tester's worktree
    └── [other agents]/  → Other agent worktrees
```

#### 🔍 FIRST: Verify Your Location (Run These Commands First)

**EVERY agent should start with these verification steps:**
```bash
# 1. Confirm you're in your worktree
pwd  # Should show: /path/to/project-tmux-worktrees/{your-role}

# 2. Verify shared directory exists
ls -la shared/  # Should show symlinks to main-project and other agents

# 3. Test main project access
ls -la shared/main-project/  # Should show main project contents

# 4. Confirm symlink target
readlink shared/main-project  # Should show relative path to main project
```

**If ANY of these fail, immediately report to Orchestrator and switch to cd-free mode.**

#### 📍 Directory Navigation Decision Tree

**🔒 WHY USE SHARED SYMLINKS:**
Claude Code security prevents direct `cd` to parent directories. This is a safety feature, not a bug.
- ❌ `cd /absolute/path/to/project` (blocked by security)
- ✅ `cd ./shared/main-project` (allowed via symlink)

**WHEN TO USE WHICH DIRECTORY:**

✅ **Your worktree** (`pwd` shows your worktree path):
```bash
# For role-specific work
mkdir my_analysis/
echo "Developer progress report" > status.md
git add . && git commit -m "Developer: progress update"
```

✅ **Main project** (via `cd ./shared/main-project`):
```bash
# For shared project operations
cd ./shared/main-project
npm install  # Install dependencies
python setup.py  # Run project commands
git status  # Check main project git state
cat README.md  # Read project documentation
```

✅ **Other agent worktrees** (via `cd ./shared/{role}`):
```bash
# Read-only access to other agents' work
cat ./shared/developer/src/feature.py  # Review code
git log --oneline -5 ./shared/tester/  # Check their commits
# ⚠️ NEVER modify other agents' files directly
```

#### How to Use the Shared Directory

**Accessing the Main Project**:
```bash
# ✅ CORRECT: Use relative path through shared
cd ./shared/main-project
git pull origin main

# ❌ WRONG: Direct absolute path (blocked by Claude)
cd /path/to/main-project  # Error: blocked for security
```

**Accessing Other Agent's Work**:
```bash
# Review developer's code
cd ./shared/developer && git log --oneline -10
cat ./shared/developer/src/feature.py

# Check tester's test files
ls -la ./shared/tester/tests/

# Compare files across worktrees
diff ./shared/developer/src/api.py ./src/api.py
```

**Git Remotes Setup** (from main-project):
```bash
cd ./shared/main-project
git remote add developer ../../developer
git remote add tester ../../tester
git fetch developer
git merge developer/feature-branch
```

#### ⚠️ Symlink Troubleshooting

**If shared directory access fails:**
```bash
# 1. Diagnose the problem
ls -la shared/ || echo "shared directory missing"
readlink shared/main-project || echo "main-project symlink broken"
cd shared/main-project && pwd || echo "symlink navigation failed"

# 2. Switch to cd-free fallback mode
# Use absolute paths with Read tool instead of cd:
# Read /absolute/path/to/project/file.py
# Use Bash with absolute paths: python /absolute/path/to/project/script.py

# 3. Report to Orchestrator immediately
echo "SYMLINK FAILURE: shared directory access failed, switched to cd-free mode"
```

#### Safety Notes
- Use depth-limiting flags to avoid infinite loops: `find ./shared -maxdepth 2`
- If symlinks fail, use absolute paths with Read/Bash tools (no cd)
- Symlinks are created automatically during setup and resume
- Always verify your location with `pwd` before major operations

### Role-Specific Directories and Files

Each role typically creates and maintains specific directories:

**Orchestrator**:
- `project_management/` - Status reports, architecture decisions
- `mcp-inventory.md` - Available MCP tools (in main project, not worktree)
- Uses Tmux-Orchestrator tools from tool directory

**Developer**:
- `src/` - Source code
- `tests/` - Unit tests
- Feature branches for implementation

**Tester**:
- `tests/` - Test suites
- `tests/integration/` - Integration tests
- `tests/e2e/` - End-to-end tests
- `test-plans/` - Test strategy documents

**TestRunner**:
- `test-results/` - Execution logs
- `test-metrics/` - Performance data
- `.test-config/` - Runner configurations

**Documentation Writer**:
- `docs/` - User documentation
- `api-docs/` - API references
- `README.md` - Project overview
- `CONTRIBUTING.md` - Contribution guidelines

**SysAdmin**:
- `infrastructure/` - System configurations
- `scripts/` - Automation scripts
- `ansible/` - Ansible playbooks (if used)
- `backup/` - Backup configurations
- `monitoring/` - System monitoring configs

**SecurityOps**:
- `security/` - Security policies and configs
- `security/firewall/` - Firewall rules
- `security/certificates/` - SSL/TLS certificates
- `security/audit/` - Audit logs and reports
- `security/compliance/` - Compliance documentation

**NetworkOps**:
- `network/` - Network configurations
- `network/routing/` - Routing tables
- `network/proxy/` - Reverse proxy configs
- `network/dns/` - DNS configurations
- `network/diagrams/` - Network topology

**MonitoringOps**:
- `monitoring/` - Monitoring stack configs
- `monitoring/dashboards/` - Grafana dashboards
- `monitoring/alerts/` - Alert rules
- `monitoring/runbooks/` - Incident runbooks
- `monitoring/metrics/` - Custom metrics

**DatabaseOps**:
- `database/` - Database configurations
- `database/migrations/` - Schema migrations
- `database/backups/` - Backup scripts
- `database/performance/` - Performance tuning
- `database/replication/` - Replication configs

**DevOps** (enhanced):
- `deployment/` - Deployment configurations
- `docker/` - Dockerfiles and compose files
- `kubernetes/` - K8s manifests
- `ci-cd/` - Pipeline configurations
- `terraform/` - Infrastructure as code

## 🔍 Researcher MCP Integration

The Researcher role uses MCP (Model Context Protocol) tools for comprehensive research:

### MCP Tool Discovery
```
# Discovering MCP tools in Claude Code:
Type @    # Shows available MCP resources from all connected servers
Type /    # Shows all commands including MCP tools (format: /mcp__servername__promptname)

# Examples of MCP commands you might find:
/mcp__websearch__search      # Web search functionality
/mcp__firecrawl__scrape     # Web scraping capabilities
/mcp__puppeteer__screenshot  # Browser automation
```

### Common MCP Tools
- **Web Search** (websearch, tavily): Current information, best practices, security CVEs
- **Firecrawl**: Documentation scraping, code examples
- **Context7**: Deep technical knowledge, architecture patterns
- **Perplexity**: Advanced research queries
- **And more**: Each project may have different tools configured

### Researcher Workflow
1. **Discover Tools**: Run `/mcp` to see what's available
2. **Document Tools**: Create `research/available-tools.md`
3. **Strategic Research**: Use appropriate tools for each research area
4. **Actionable Output**: Create structured recommendations, not info dumps

### Research Documents Structure
```
research/
├── available-tools.md      # MCP inventory
├── security-analysis.md    # CVEs, vulnerabilities
├── performance-guide.md    # Optimization strategies
├── best-practices.md       # Industry standards
└── phase-{n}-research.md   # Phase-specific findings
```

## 🔐 Git Discipline - MANDATORY FOR ALL AGENTS

### 🚨 CRITICAL BRANCH PROTECTION RULES 🚨

**NEVER MERGE TO MAIN UNLESS YOU STARTED ON MAIN**

1. **Branch Hierarchy Rule**: 
   - ALWAYS detect and record the starting branch when a project begins
   - Create feature branches FROM the current branch (not from main)
   - Merge ONLY back to the original parent branch
   - If started on main, then and only then can you merge to main

2. **Branch Detection Commands**:
   ```bash
   # First thing when starting ANY project - record the starting branch
   STARTING_BRANCH=$(git rev-parse --abbrev-ref HEAD)
   echo "Project started on branch: $STARTING_BRANCH" > .git/STARTING_BRANCH
   
   # When creating feature branches
   git checkout -b feature/new-feature  # This creates from current branch
   
   # When merging back
   ORIGINAL_BRANCH=$(cat .git/STARTING_BRANCH)
   git checkout $ORIGINAL_BRANCH
   git merge feature/new-feature
   ```

### Core Git Safety Rules

**CRITICAL**: Every agent MUST follow these git practices to prevent work loss:

1. **Auto-Commit Every 30 Minutes**
   ```bash
   # Set a timer/reminder to commit regularly
   git add -A
   git commit -m "Progress: [specific description of what was done]"
   ```

2. **Commit Before Task Switches**
   - ALWAYS commit current work before starting a new task
   - Never leave uncommitted changes when switching context
   - Tag working versions before major changes

3. **Feature Branch Workflow**
   ```bash
   # ALWAYS check current branch first
   CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
   echo "Currently on branch: $CURRENT_BRANCH"
   
   # Before starting any new feature/task
   git checkout -b feature/[descriptive-name]  # Creates from CURRENT branch
   
   # After completing feature
   git add -A
   git commit -m "Complete: [feature description]"
   git tag stable-[feature]-$(date +%Y%m%d-%H%M%S)
   
   # Merge back to PARENT branch (not necessarily main!)
   git checkout $CURRENT_BRANCH  # Go back to where we branched from
   git merge feature/[descriptive-name]
   ```

4. **Meaningful Commit Messages**
   - Bad: "fixes", "updates", "changes"
   - Good: "Add user authentication endpoints with JWT tokens"
   - Good: "Fix null pointer in payment processing module"
   - Good: "Refactor database queries for 40% performance gain"

5. **Never Work >1 Hour Without Committing**
   - If you've been working for an hour, stop and commit
   - Even if the feature isn't complete, commit as "WIP: [description]"
   - This ensures work is never lost due to crashes or errors

### Git Emergency Recovery

If something goes wrong:
```bash
# Check recent commits
git log --oneline -10

# Recover from last commit if needed
git stash  # Save any uncommitted changes
git reset --hard HEAD  # Return to last commit

# Check stashed changes
git stash list
git stash pop  # Restore stashed changes if needed
```

### Project Manager Git Responsibilities

#### Core Responsibilities
Project Managers must enforce git discipline:
- **VERIFY the starting branch** at project initialization
- **PREVENT unauthorized merges to main** - only if project started on main
- Remind engineers to commit every 30 minutes
- Verify feature branches are created from the correct parent branch
- Ensure meaningful commit messages
- Check that stable tags are created
- Track branch hierarchy to prevent accidental main branch pollution

#### Advanced PM Git Management

**Daily Health Checks**:
```bash
# Morning routine - check team sync status
git fetch --all
git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads

# Check for agents falling behind
git log --oneline --graph --all -20

# Verify no one is working on main directly
git log main --since="1 day ago" --format="%an %s"
```

**Integration Risk Assessment**:
```bash
# Before starting integration - assess complexity
git diff main..feature/developer-work --stat
git diff main..test/tester-work --stat

# Check for overlapping changes (high conflict risk)
git diff main..feature/developer-work --name-only > /tmp/dev_files
git diff main..test/tester-work --name-only > /tmp/test_files
comm -12 /tmp/dev_files /tmp/test_files  # Files changed by both

# If overlap detected - coordinate first
if [ -s overlap ]; then
  scm developer:0 "Coordinate with Tester - overlapping changes detected in: $(cat overlap)"
fi
```

**Rollback Procedures**:
```bash
# Emergency rollback if integration fails
git checkout main
git pull origin main

# Create rollback branch
git checkout -b rollback/emergency-$(date +%Y%m%d-%H%M)

# Reset to last known good state  
LAST_GOOD=$(git log --oneline -10 | grep "Integration:" | head -1 | cut -d' ' -f1)
git reset --hard $LAST_GOOD

# Force push to main (only in emergencies)
git push origin main --force-with-lease

# Notify all agents
scm orchestrator:0 "EMERGENCY ROLLBACK: All agents rebase from main immediately"
```

### Why This Matters

- **Work Loss Prevention**: Hours of work can vanish without commits
- **Collaboration**: Other agents can see and build on committed work
- **Rollback Safety**: Can always return to a working state
- **Progress Tracking**: Clear history of what was accomplished

### General Git Workflow for All Agents

Follow this enhanced workflow that includes autonomous conflict resolution:

1. **Regular Commits**: Commit every 10-15 minutes with semantic messages
   ```bash
   git add -A
   git commit -m "feat: implement user authentication" # or fix:, docs:, test:
   ```

2. **Smart Syncing**: Before starting new work, sync with AI assistance
   ```bash
   # Automatically handles conflicts if they arise
   git-sync-and-resolve --source pm/integration
   # Or from main/master
   git-sync-and-resolve --source origin/main
   ```

3. **Conflict Handling**: When conflicts occur during your work
   - Simple conflicts: Use `git-resolve-conflict --ai` for autonomous resolution
   - Complex conflicts: Escalate to PM with full context
   - Always validate resolutions with tests before committing

4. **Safety Rules**:
   - Never force-push without PM approval
   - Always create backup branches before complex operations
   - Run tests after any merge or conflict resolution
   - Update SessionState with resolution outcomes

5. **Integration with Tools**:
   - Use wrapper commands from git_wrappers.sh for safety
   - All resolutions are logged to SessionState automatically
   - GitCoordinator handles complex operations behind the scenes

## 🌳 Git Worktree & Workflow Rules

### Worktree Structure
Each agent works in isolated worktree (as SIBLINGS to the project, NOT in registry):
```
{project_path}-tmux-worktrees/        # Sibling to your project directory
├── orchestrator/     # Dual-directory agent
├── project-manager/  # Integration coordinator
├── developer/        # Implementation
├── tester/          # Test creation
├── researcher/      # MCP research
└── [other-agents]/  # Role-specific
```

**CRITICAL**: Worktrees are NEVER under registry! Always verify with `git worktree list`

### Worktree Discipline Rules
1. **Stay in Your Lane**: Never directly modify files in other agents' worktrees
2. **Read-Only Access**: Can read/review other worktrees: `cat ../developer/src/file.py`
3. **Push Your Work**: Share via GitHub, not direct file edits
4. **Orchestrator Exception**: Works from both project worktree AND tool directory

### Git Coordination Rules (Local-First Workflow)
1. **Local Commits**: Every 30 minutes, commit to your feature branch
2. **PM Notification**: Notify PM after significant commits for coordination:
   ```bash
   scm pm:0 "Feature auth-endpoints ready for integration review"
   ```
3. **Branch Naming Convention**:
   - Developer: `dev/description` or `feature/description`
   - PM: `integration` (hub branch) or `pm/description`  
   - Tester: `test/description`
   - TestRunner: `testrunner/description`
   - Researcher: `research/description`
   - DevOps: `devops/description`
4. **Local Sync Before Work**: Fetch from PM integration before starting:
   ```bash
   git fetch pm
   git rebase pm/integration  # Rebase your work on latest
   ```
5. **GitHub Pushes**: Only for milestones, backups, or escalation:
   - PM pushes integration branch hourly or at milestones
   - Individual agents push only when explicitly requested by PM
   - Emergency backup before project timeout/failure

### Pull Request Workflow
1. **Timing Requirements**:
   - Create PR within 30 minutes of push
   - PM merges within 2 hours
   - Integration cycle completes within 4 hours
2. **PR Creation**: Only PM creates integration PRs
3. **Auto-Merge Protocol**: Use `--admin` flag (no manual approvals)
4. **Notification**: Announce PR creation and merges

### 📋 PM Integration Protocol - Step by Step

#### Pre-Integration Checklist
```bash
# Step 0: Pre-integration safety checks
git fetch --all
git checkout main  # or parent branch
git pull origin main

# Check all agent branches are pushed and ready
git branch -r | grep -E "(feature|test|pm-)"
git log --oneline --graph --all -10

# Verify no agents are mid-commit (check with orchestrator)
scm orchestrator:0 "Ready for integration? All agents commit current work"
```

#### Daily Integration Workflow
```bash
# Step 1: Create timestamped integration branch
DATE=$(date +%Y%m%d-%H%M)
git checkout -b integration/daily-$DATE

# Step 2: Merge in dependency order (Backend → Frontend → Tests)
# CRITICAL: Use --no-ff to preserve merge history

# Infrastructure/Backend first
git merge origin/feature/developer-backend --no-ff
if [ $? -ne 0 ]; then
  echo "CONFLICT: Backend merge failed - escalate to Developer"
  scm developer:0 "Merge conflict in backend code - please resolve in integration/daily-$DATE"
  exit 1
fi

# Frontend second  
git merge origin/feature/developer-frontend --no-ff
if [ $? -ne 0 ]; then
  echo "CONFLICT: Frontend merge failed - escalate to Developer"
  scm developer:0 "Merge conflict in frontend code - please resolve in integration/daily-$DATE"
  exit 1
fi

# Tests last
git merge origin/test/tester-work --no-ff
if [ $? -ne 0 ]; then
  echo "CONFLICT: Test merge failed - escalate to Tester"
  scm tester:0 "Merge conflict in tests - please resolve in integration/daily-$DATE"
  exit 1
fi

# Step 3: Integration testing BEFORE creating PR
git push -u origin integration/daily-$DATE
scm testrunner:0 "Run full integration test suite on integration/daily-$DATE"

# Wait for test results before proceeding
# Only continue if tests pass
```

#### Safe Merge Process
```bash
# Step 4: Create PR only after tests pass
gh pr create --base main \
  --head integration/daily-$DATE \
  --title "Integration: $(date +%Y-%m-%d %H:%M)" \
  --body "Daily integration of all agent work

## Included Changes:
- Developer: [brief description]
- Tester: [brief description]
- TestRunner: All tests passing

Integration tests: ✅ PASSED"

# Step 5: Merge with safety checks
gh pr merge --admin --merge --delete-branch

# Step 6: Immediate post-merge verification
git checkout main
git pull origin main
npm run build  # or appropriate build command
npm run test   # smoke test

# Step 7: Notify all agents to sync
scm orchestrator:0 "Integration complete! All agents pull from main within 1 hour"
```

#### Conflict Resolution Protocol - PM Enhanced
```bash
# When conflicts occur - attempt autonomous resolution first
if git merge origin/feature/branch-name --no-ff; then
  echo "✅ Clean merge successful"
else
  echo "⚠️  Conflicts detected - attempting autonomous resolution..."
  
  # First, try AI-assisted resolution
  if git-sync-and-resolve --source origin/feature/branch-name; then
    echo "✅ Conflicts resolved autonomously"
  else
    # Autonomous failed, classify and delegate
    conflict_files=$(git diff --name-only --diff-filter=U)
    
    # Analyze complexity
    total_lines=$(git diff --cached | wc -l)
    if [ $total_lines -gt 100 ]; then
      echo "Complex conflict detected (${total_lines} lines)"
    fi
    
    # Delegate based on file type and complexity
    if git status | grep -q "\.py\|\.js\|\.ts"; then
      scm developer:0 "Complex code conflicts in integration branch $(git branch --show-current) - autonomous resolution failed. Files: ${conflict_files}. Please resolve and commit."
    elif git status | grep -q "test"; then
      scm tester:0 "Test conflicts in integration branch $(git branch --show-current) - please resolve and commit"
    else
      # PM makes another attempt with different strategy
      git-resolve-conflict --ai --files "${conflict_files}"
      if [ $? -ne 0 ]; then
        # Escalate to Orchestrator
        scm orchestrator:0 "Integration blocked: unresolvable conflicts in ${conflict_files}. Manual intervention required."
      fi
    fi
    
    # Set timeout for resolution
    echo "Waiting for conflict resolution (timeout: 30min)..."
  fi
fi
```

### 🚀 Fast Lane Coordination (ENHANCED)

**Purpose**: Enable rapid integration across ALL team configurations, not just Developer→Tester→TestRunner.

#### Fast Lane Modes

**Mode 1: Traditional Fast Lanes** (When Developer + Tester present)
- Developer → Tester sync: 5 minutes (was 45 min)
- Tester → TestRunner sync: 3 minutes (was 30 min)
- Automatic merge propagation with conflict escalation

**Mode 2: PM-Hub Coordination** (For any team configuration)
- PM acts as central integration hub
- 15-minute integration cycles for ALL technical roles
- Proactive change broadcasting between agents
- Works with: SysAdmin, SecurityOps, NetworkOps, DatabaseOps, Researcher, etc.

**Mode 3: Extended Fast Lanes** (System operations teams)
1. **SysAdmin ↔ SecurityOps**:
   ```bash
   # Auto-sync security changes to system config
   git fetch origin
   git merge origin/security-hardening --no-edit
   scm pm:0 "Fast lane: Merged security updates"
   ```

2. **DevOps ↔ NetworkOps**:
   ```bash
   # Auto-sync network config for deployments
   git fetch origin
   git merge origin/network-config --no-edit
   scm pm:0 "Fast lane: Merged network configuration"
   ```

3. **Any Technical Role**:
   - Post-commit hooks trigger notifications
   - PM coordinates cross-role merges
   - Integration branches created every 30 minutes

#### Fast Lane Safety Rules

1. **Same Feature Only**: Fast lanes only work within same feature branch
2. **PM Override**: PM can disable fast lane if conflicts arise: `DISABLE_FAST_LANE=true`
3. **Conflict Escalation**: Any merge conflicts automatically escalate to PM
4. **Audit Logging**: All fast lane activity logged to `registry/logs/fast-lane/`
5. **Quality Gates**: TestRunner must report results to both Tester and PM

#### Fast Lane Triggers

**Event-Driven Coordination** (instead of polling):
```bash
# Developer post-commit hook
#!/bin/bash
scm tester:0 "FAST_LANE_TRIGGER: New implementation ready: $(git log --oneline -1)"
scm testrunner:0 "FAST_LANE_TRIGGER: Code update available"

# Tester post-test hook  
#!/bin/bash
scm testrunner:0 "FAST_LANE_TRIGGER: Test suite updated: $(git log --oneline -1)"
scm pm:0 "Fast lane: Test updates pushed for execution"
```

**Tier 2: PM Coordination** (Manual, for integration)
- Cross-functional feature merges
- Release branch integration
- Conflict resolution
- Quality gate approvals
- Major architecture changes

**Tier 3: Orchestrator Oversight** (Strategic)
- Architecture decisions
- Priority changes  
- Resource allocation
- Cross-project dependencies

### Agent Synchronization Rules
1. **Pull After Integration**: All agents must pull within 1 hour
2. **Fast Lane Updates**: Tester/TestRunner auto-sync every 10-15 minutes
3. **Conflict Resolution**: Resolve within 30 minutes
4. **Stay Current**: Maximum 20 commits behind parent branch
5. **Sync Commands**:
   ```bash
   # Check your sync status
   git fetch origin
   git status
   git log HEAD..origin/main --oneline
   
   # Pull latest changes (manual)
   git pull origin main
   
   # Fast lane auto-sync (automatic for Tester/TestRunner)
   ./scripts/fast_lane_sync.sh
   ```

### Workflow Timing Targets

**Fast Lane Targets** (NEW):
- **Developer Commit → Tester Auto-Sync**: 5 minutes
- **Tester Test → TestRunner Auto-Sync**: 3 minutes  
- **Full Development → Test → Execution Cycle**: 8 minutes maximum

**Traditional Integration Targets**:
- **Commit → Push**: 15 minutes
- **Push → PR**: 30 minutes  
- **PR → Merge**: 2 hours
- **Merge → Pull**: 1 hour
- **Full Integration Cycle**: 4 hours maximum (for major integrations)

### Git Activity Monitoring
The orchestrator runs automated monitoring that tracks:
- Commit frequency (30-minute rule compliance)
- Push timing (15-minute target)
- PR age and merge delays
- Agent synchronization status
- Branch divergence from parent
- Integration bottlenecks

Violations trigger automatic orchestrator notifications.

## Startup Behavior - Tmux Window Naming

### Auto-Rename Feature
When Claude starts in the orchestrator, it should:
1. **Ask the user**: "Would you like me to rename all tmux windows with descriptive names for better organization?"
2. **If yes**: Analyze each window's content and rename them with meaningful names
3. **If no**: Continue with existing names

### Window Naming Convention
Windows should be named based on their actual function:
- **Claude Agents**: `Claude-Frontend`, `Claude-Backend`, `Claude-Convex`
- **Dev Servers**: `NextJS-Dev`, `Frontend-Dev`, `Uvicorn-API`
- **Shells/Utilities**: `Backend-Shell`, `Frontend-Shell`
- **Services**: `Convex-Server`, `Orchestrator`
- **Project Specific**: `Notion-Agent`, etc.

### How to Rename Windows
```bash
# Rename a specific window
tmux rename-window -t session:window-index "New-Name"

# Example:
tmux rename-window -t ai-chat:0 "Claude-Convex"
tmux rename-window -t glacier-backend:3 "Uvicorn-API"
```

### Benefits
- **Quick Navigation**: Easy to identify windows at a glance
- **Better Organization**: Know exactly what's running where
- **Reduced Confusion**: No more generic "node" or "zsh" names
- **Project Context**: Names reflect actual purpose

## Project Startup Sequence

### When User Says "Open/Start/Fire up [Project Name]"

**Note**: For automated setup with git worktrees, use:
```bash
./tmux_orchestrator_cli.py run --project /path/to/project --spec /path/to/spec.md
```

For manual setup, follow this systematic sequence:

#### 1. Find the Project
```bash
# List all directories in ~/projects to find projects
ls -la ~/projects/ | grep "^d" | awk '{print $NF}' | grep -v "^\."

# If project name is ambiguous, list matches
ls -la ~/projects/ | grep -i "task"  # for "task templates"
```

#### 2. Create Tmux Session
```bash
# Create session with project name (use hyphens for spaces)
PROJECT_NAME="task-templates"  # or whatever the folder is called
PROJECT_PATH="$HOME/projects/$PROJECT_NAME"
tmux new-session -d -s $PROJECT_NAME -c "$PROJECT_PATH"
```

#### 3. Set Up Standard Windows
```bash
# Window 0: Claude Agent
tmux rename-window -t $PROJECT_NAME:0 "Claude-Agent"

# Window 1: Shell
tmux new-window -t $PROJECT_NAME -n "Shell" -c "$PROJECT_PATH"

# Window 2: Dev Server (will start app here)
tmux new-window -t $PROJECT_NAME -n "Dev-Server" -c "$PROJECT_PATH"
```

#### 4. Brief the Claude Agent
```bash
# Send briefing message to Claude agent
tmux send-keys -t $PROJECT_NAME:0 "claude" Enter
sleep 5  # Wait for Claude to start

# Send the briefing
tmux send-keys -t $PROJECT_NAME:0 "You are responsible for the $PROJECT_NAME codebase. Your duties include:
1. Getting the application running
2. Checking GitHub issues for priorities  
3. Working on highest priority tasks
4. Keeping the orchestrator informed of progress

First, analyze the project to understand:
- What type of project this is (check package.json, requirements.txt, etc.)
- How to start the development server
- What the main purpose of the application is

Then start the dev server in window 2 (Dev-Server) and begin working on priority issues."
sleep 1
tmux send-keys -t $PROJECT_NAME:0 Enter
```

#### 5. Project Type Detection (Agent Should Do This)
The agent should check for:
```bash
# Node.js project
test -f package.json && cat package.json | grep scripts

# Python project  
test -f requirements.txt || test -f pyproject.toml || test -f setup.py

# Ruby project
test -f Gemfile

# Go project
test -f go.mod
```

#### 6. Start Development Server (Agent Should Do This)
Based on project type, the agent should start the appropriate server in window 2:
```bash
# For Next.js/Node projects
tmux send-keys -t $PROJECT_NAME:2 "npm install && npm run dev" Enter

# For Python/FastAPI
tmux send-keys -t $PROJECT_NAME:2 "source venv/bin/activate && uvicorn app.main:app --reload" Enter

# For Django
tmux send-keys -t $PROJECT_NAME:2 "source venv/bin/activate && python manage.py runserver" Enter
```

#### 7. Check GitHub Issues (Agent Should Do This)
```bash
# Check if it's a git repo with remote
git remote -v

# Use GitHub CLI to check issues
gh issue list --limit 10

# Or check for TODO.md, ROADMAP.md files
ls -la | grep -E "(TODO|ROADMAP|TASKS)"
```

#### 8. Monitor and Report Back
The orchestrator should:
```bash
# Check agent status periodically
tmux capture-pane -t $PROJECT_NAME:0 -p | tail -30

# Check if dev server started successfully  
tmux capture-pane -t $PROJECT_NAME:2 -p | tail -20

# Monitor for errors
tmux capture-pane -t $PROJECT_NAME:2 -p | grep -i error
```

### Example: Starting "Task Templates" Project
```bash
# 1. Find project
ls -la ~/projects/ | grep -i task
# Found: task-templates

# 2. Create session
tmux new-session -d -s task-templates -c "$HOME/projects/task-templates"

# 3. Set up windows
tmux rename-window -t task-templates:0 "Claude-Agent"
tmux new-window -t task-templates -n "Shell" -c "$HOME/projects/task-templates"
tmux new-window -t task-templates -n "Dev-Server" -c "$HOME/projects/task-templates"

# 4. Start Claude and brief
tmux send-keys -t task-templates:0 "claude" Enter
# ... (briefing as above)
```

### Important Notes
- Always verify project exists before creating session
- Use project folder name for session name (with hyphens for spaces)
- Let the agent figure out project-specific details
- Monitor for successful startup before considering task complete

## Creating Specialized Agents

### Creating a SysAdmin Agent

```bash
# Create window
tmux new-window -t [session] -n "SysAdmin" -c "$PROJECT_PATH"

# Start and brief
tmux send-keys -t [session]:[window] "claude" Enter
sleep 5

tmux send-keys -t [session]:[window] "You are the System Administrator for this deployment. Your responsibilities:

1. **System Setup**: Configure servers, install packages, manage users
2. **Permissions**: Set proper file ownership and permissions  
3. **Service Management**: Configure systemd/init services
4. **Security**: Implement system-level security measures
5. **Resource Management**: Monitor and optimize system resources

Key Commands You'll Use:
- sudo for privileged operations
- systemctl for service management
- useradd/usermod for user management
- chmod/chown for permissions
- apt/yum for package management

IMPORTANT: Always use sudo responsibly. Document all system changes.

First, check the deployment spec and verify system prerequisites."
tmux send-keys -t [session]:[window] Enter
```

### Creating a SecurityOps Agent

```bash
# Create window
tmux new-window -t [session] -n "SecurityOps" -c "$PROJECT_PATH"

# Start and brief
tmux send-keys -t [session]:[window] "claude" Enter
sleep 5

tmux send-keys -t [session]:[window] "You are the Security Operations specialist. Your responsibilities:

1. **System Hardening**: Implement security best practices
2. **Access Control**: Configure firewalls, SSH, and access policies
3. **Compliance**: Ensure security standards compliance
4. **Monitoring**: Set up security monitoring and alerts
5. **Incident Response**: Create security runbooks

Security Tools:
- ufw/iptables for firewall configuration
- fail2ban for intrusion prevention
- AppArmor/SELinux for mandatory access control
- SSL/TLS certificate management
- Security scanning tools

Work closely with SysAdmin for system access. Report security concerns immediately to Orchestrator."
tmux send-keys -t [session]:[window] Enter
```

### Creating a NetworkOps Agent

```bash
# Create window
tmux new-window -t [session] -n "NetworkOps" -c "$PROJECT_PATH"

# Start and brief
tmux send-keys -t [session]:[window] "claude" Enter
sleep 5

tmux send-keys -t [session]:[window] "You are the Network Operations specialist. Your responsibilities:

1. **Network Configuration**: Set up routing, DNS, load balancers
2. **Reverse Proxy**: Configure Nginx/HAProxy for services
3. **Port Management**: Manage port allocations and firewall rules
4. **Performance**: Optimize network performance
5. **Troubleshooting**: Diagnose connectivity issues

Key Areas:
- Nginx/Apache reverse proxy configuration
- Load balancing and failover
- DNS configuration
- Network security policies
- Performance monitoring

Coordinate with SecurityOps for firewall rules and SysAdmin for system access."
tmux send-keys -t [session]:[window] Enter
```

### Creating a MonitoringOps Agent

```bash
# Create window
tmux new-window -t [session] -n "MonitoringOps" -c "$PROJECT_PATH"

# Start and brief
tmux send-keys -t [session]:[window] "claude" Enter
sleep 5

tmux send-keys -t [session]:[window] "You are the Monitoring Operations specialist. Your responsibilities:

1. **Monitoring Stack**: Set up Prometheus/Grafana or similar
2. **Metrics Collection**: Configure service and system metrics
3. **Alerting**: Create alert rules and notifications
4. **Dashboards**: Build monitoring dashboards
5. **Incident Response**: Create runbooks for common issues

Monitoring Stack:
- Prometheus for metrics collection
- Grafana for visualization
- AlertManager for notifications
- Log aggregation (ELK/Loki)
- Custom metrics and exporters

Work with all technical roles to ensure comprehensive monitoring coverage."
tmux send-keys -t [session]:[window] Enter
```

### Creating a DatabaseOps Agent

```bash
# Create window
tmux new-window -t [session] -n "DatabaseOps" -c "$PROJECT_PATH"

# Start and brief
tmux send-keys -t [session]:[window] "claude" Enter
sleep 5

tmux send-keys -t [session]:[window] "You are the Database Operations specialist. Your responsibilities:

1. **Database Setup**: Install and configure database servers
2. **Performance**: Optimize queries and configurations
3. **Replication**: Set up HA and replication
4. **Backups**: Implement backup strategies
5. **Security**: Database access control and encryption

Database Systems:
- PostgreSQL/MySQL for relational data
- MongoDB for document storage
- Redis/Valkey for caching
- Elasticsearch for search
- Database migrations and versioning

Coordinate with SysAdmin for system resources and Developer for schema requirements."
tmux send-keys -t [session]:[window] Enter
```

## Creating a Project Manager

### When User Says "Create a project manager for [session]"

#### 1. Analyze the Session
```bash
# List windows in the session
tmux list-windows -t [session] -F "#{window_index}: #{window_name}"

# Check each window to understand project
tmux capture-pane -t [session]:0 -p | tail -50
```

#### 2. Create PM Window
```bash
# Get project path from existing window
PROJECT_PATH=$(tmux display-message -t [session]:0 -p '#{pane_current_path}')

# Create new window for PM
tmux new-window -t [session] -n "Project-Manager" -c "$PROJECT_PATH"
```

#### 3. Start and Brief the PM
```bash
# Start Claude
tmux send-keys -t [session]:[PM-window] "claude" Enter
sleep 5

# Send PM-specific briefing
tmux send-keys -t [session]:[PM-window] "You are the Project Manager for this project. Your responsibilities:

1. **Quality Standards**: Maintain exceptionally high standards. No shortcuts, no compromises.
2. **Verification**: Test everything. Trust but verify all work.
3. **Team Coordination**: Manage communication between team members efficiently.
4. **Progress Tracking**: Monitor velocity, identify blockers, report to orchestrator.
5. **Risk Management**: Identify potential issues before they become problems.

Key Principles:
- Be meticulous about testing and verification
- Create test plans for every feature
- Ensure code follows best practices
- Track technical debt
- Communicate clearly and constructively

First, analyze the project and existing team members, then introduce yourself to the developer in window 0."
sleep 1
tmux send-keys -t [session]:[PM-window] Enter
```

#### 4. PM Introduction Protocol
The PM should:
```bash
# Check developer window
tmux capture-pane -t [session]:0 -p | tail -30

# Introduce themselves
tmux send-keys -t [session]:0 "Hello! I'm the new Project Manager for this project. I'll be helping coordinate our work and ensure we maintain high quality standards. Could you give me a brief status update on what you're currently working on?"
sleep 1
tmux send-keys -t [session]:0 Enter
```

## Communication Protocols

### Hub-and-Spoke Model (ENHANCED)
The Orchestrator acts as the central hub with **automatic enforcement**:
- All agents report directly to Orchestrator
- Orchestrator coordinates all cross-functional communication
- Direct agent-to-agent communication only for immediate needs (test handoffs)
- **NEW**: Automatic hub-spoke enforcement prevents silent completions

#### 🚨 Automatic Communication Enforcement
Since the DevOps silent completion incident, the system now enforces hub-spoke:

1. **Event Hook System**: Task completions automatically trigger Orchestrator notification
2. **Message Routing**: Critical messages (complete, deploy, fail) auto-route to Orchestrator
3. **Dependency Tracking**: Agents get notified when their dependencies complete
4. **Audit Trail**: All communications logged for compliance monitoring

#### Enhanced Communication Scripts

**Hub-Spoke Enforced Messaging**:
```bash
# Use for critical updates - automatically notifies Orchestrator
./send-claude-message-hubspoke.sh session:role "Deployment complete"

# Report task completion - updates state and notifies hub
./report-completion.sh devops "Modal deployment complete - EVENT_ROUTER_ENABLED=true"
```

**How It Works**:
- Detects critical keywords (complete, deploy, fail, error, block)
- Appends "Report to Orchestrator" instruction to agent messages
- Sends copy to Orchestrator for critical updates
- Updates session state to track completions
- Triggers dependency notifications automatically

### Role Communication Matrix

Communication patterns vary by project type:

#### Standard Development Projects

**Orchestrator** communicates with:
- Developer (task assignment, guidance)
- Tester (quality verification)
- TestRunner (test execution status)
- All agents for coordination

**Developer** communicates with:
- Orchestrator (primary contact)
- Tester (test requirements)
- TestRunner (test feedback)

**Tester** communicates with:
- Orchestrator (test results)
- Developer (test requirements)
- TestRunner (test suite handoff)

**TestRunner** communicates with:
- Orchestrator (execution status)
- Tester (test suite updates)
- Developer (failure details)

#### System Operations Projects

**Orchestrator** communicates with:
- SysAdmin (system requirements, status)
- DevOps (deployment coordination)
- SecurityOps (security requirements)
- All agents for coordination

**SysAdmin** communicates with:
- Orchestrator (primary contact)
- SecurityOps (security implementation)
- NetworkOps (network configuration)
- MonitoringOps (monitoring setup)
- DatabaseOps (database installation)

**DevOps** communicates with:
- Orchestrator (deployment status)
- SysAdmin (system requirements)
- Developer (if present, for app deployment)
- MonitoringOps (deployment monitoring)

**SecurityOps** communicates with:
- Orchestrator (security status)
- SysAdmin (system hardening)
- NetworkOps (network security)
- MonitoringOps (security monitoring)

**NetworkOps** communicates with:
- Orchestrator (network status)
- SysAdmin (network access)
- SecurityOps (firewall rules)
- MonitoringOps (network monitoring)

**MonitoringOps** communicates with:
- Orchestrator (monitoring status)
- All technical roles (metric collection)
- SecurityOps (security alerts)

**DatabaseOps** communicates with:
- Orchestrator (database status)
- SysAdmin (system resources)
- Developer (schema requirements)
- MonitoringOps (database monitoring)


### Daily Standup (Async)
```bash
# PM asks each team member
tmux send-keys -t [session]:[dev-window] "STATUS UPDATE: Please provide: 1) Completed tasks, 2) Current work, 3) Any blockers"
# Wait for response, then aggregate
```

### Message Templates

#### Status Update
```
STATUS [AGENT_NAME] [TIMESTAMP]
Completed: 
- [Specific task 1]
- [Specific task 2]
Current: [What working on now]
Blocked: [Any blockers]
ETA: [Expected completion]
```

#### Task Assignment
```
TASK [ID]: [Clear title]
Assigned to: [AGENT]
Objective: [Specific goal]
Success Criteria:
- [Measurable outcome]
- [Quality requirement]
Priority: HIGH/MED/LOW
```

## 📊 Plan-Based Team Sizing

### Recommended Team Sizes by Plan

Multi-agent systems use ~15x more tokens than standard Claude usage. Team sizes are optimized for sustainable token consumption:

| Plan | Max Agents | Recommended | Notes |
|------|------------|-------------|-------|
| Pro | 3 | 2-3 | Limited token budget |
| Max 5x | 5 | 3-4 | Balance performance/duration (default) |
| Max 20x | 8 | 5-6 | Can support larger teams |
| Console | 10+ | As needed | Enterprise usage |

### Default Role Deployment

**All Projects** (5 agents total):
- Orchestrator
- Project Manager
- Developer
- Tester
- TestRunner

**Note**: This simplified deployment ensures core functionality while reducing token consumption. Additional roles can still be added with `--roles` if needed.

### Token Conservation Tips
- Use `--size small` for longer coding sessions
- Check-in intervals increased to conserve tokens (45-90 min)
- Monitor usage with community tools
- Consider serial vs parallel agent deployment for complex tasks

### Using the --plan Flag

```bash
# Specify your subscription plan
./tmux_orchestrator_cli.py run --project /path --spec spec.md --plan max5

# Force small team for extended session
./tmux_orchestrator_cli.py run --project /path --spec spec.md --size small
```

## Team Deployment

### When User Says "Work on [new project]"

**Recommended**: Use auto_orchestrate.py for automated setup with dynamic team configuration:
```bash
# Automatic team selection based on project analysis
./tmux_orchestrator_cli.py run --project /any/path/to/project --spec project_spec.md

# Force specific team type
./tmux_orchestrator_cli.py run --project /path/to/project --spec spec.md --team-type system_deployment

# Custom role selection
./tmux_orchestrator_cli.py run --project /path/to/project --spec spec.md \
  --roles "orchestrator,sysadmin,devops,securityops,networkops"
```

### System Operations Workflow Example

For deployment projects like the elliott-wave example:

```bash
# 1. Create deployment spec
cat > deployment_spec.md << 'EOF'
PROJECT: Elliott Wave Service Deployment
TARGET: 185.177.73.38
TYPE: System Deployment

REQUIREMENTS:
- Install Python 3.11+ environment
- Configure systemd service
- Set up Redis/Valkey connections
- Implement security hardening
- Configure monitoring

DELIVERABLES:
- Running service on port 8002
- Systemd auto-restart
- Health endpoint
- Monitoring dashboard
EOF

# 2. Deploy with system operations team
./tmux_orchestrator_cli.py run \
  --project /opt/signalmatrix/slices/elliott-wave \
  --spec deployment_spec.md \
  --team-type system_deployment

# This automatically deploys:
# - Orchestrator: Overall coordination
# - SysAdmin: System setup, users, permissions
# - DevOps: Service deployment, systemd
# - SecurityOps: Hardening, firewall, AppArmor
# - (Optional) NetworkOps: If reverse proxy needed
# - (Optional) MonitoringOps: If complex monitoring required
```

### Team Selection Logic

The system analyzes your project and spec to determine the best team:

#### 1. Project Analysis
```python
# Automatic detection looks for:
project_indicators = {
    'web_app': ['package.json', 'requirements.txt', 'app.py'],
    'system_deployment': ['*_deployment_*.md', '*.service', 'ansible/'],
    'infrastructure': ['*.tf', 'terraform/', 'cloudformation.json'],
    'data_pipeline': ['airflow.cfg', 'etl/', 'pipeline.py']
}
```

#### 2. Dynamic Team Assignment

Based on detection, different teams are deployed:

**Web Application Detected**:
- Core: Orchestrator, Developer, Tester, TestRunner
- Optional: DevOps (if Docker found), Researcher

**System Deployment Detected**:
- Core: Orchestrator, SysAdmin, DevOps, SecurityOps
- Optional: NetworkOps, MonitoringOps, DatabaseOps

**Infrastructure as Code Detected**:
- Core: Orchestrator, DevOps, SysAdmin, SecurityOps
- Optional: NetworkOps, MonitoringOps

#### 3. Manual Override Options

```bash
# Force team type regardless of detection
--team-type [web_application|system_deployment|infrastructure_as_code|data_pipeline]

# Add specific roles to detected team
--add-roles "monitoringops,databaseops"

# Completely custom team
--roles "orchestrator,developer,sysadmin,devops,securityops"
```

## Agent Lifecycle Management

### Creating Temporary Agents
For specific tasks (code review, bug fix):
```bash
# Create with clear temporary designation
tmux new-window -t [session] -n "TEMP-CodeReview"
```

### Ending Agents Properly
```bash
# 1. Capture complete conversation
tmux capture-pane -t [session]:[window] -S - -E - > \
  ~/Tmux-Orchestrator/registry/logs/[session]_[role]_$(date +%Y%m%d_%H%M%S).log

# 2. Create summary of work completed
echo "=== Agent Summary ===" >> [logfile]
echo "Tasks Completed:" >> [logfile]
echo "Issues Encountered:" >> [logfile]
echo "Handoff Notes:" >> [logfile]

# 3. Close window
tmux kill-window -t [session]:[window]
```

### Agent Logging Structure
```
~/Tmux-Orchestrator/registry/
├── logs/            # Agent conversation logs
├── sessions.json    # Active session tracking
└── notes/           # Orchestrator notes and summaries
```

## Quality Assurance Protocols

### PM Verification Checklist
- [ ] All code has tests
- [ ] Error handling is comprehensive
- [ ] Performance is acceptable
- [ ] Security best practices followed
- [ ] Documentation is updated
- [ ] No technical debt introduced

### Continuous Verification
PMs should implement:
1. Code review before any merge
2. Test coverage monitoring
3. Performance benchmarking
4. Security scanning
5. Documentation audits

## Communication Rules

1. **No Chit-Chat**: All messages work-related
2. **Use Templates**: Reduces ambiguity
3. **Acknowledge Receipt**: Simple "ACK" for tasks
4. **Escalate Quickly**: Don't stay blocked >10 min
5. **One Topic Per Message**: Keep focused
6. **Report Completions**: Use `./report-completion.sh` for all task completions
7. **Critical Updates**: Use hub-spoke script for deployment/failure messages

### Preventing Communication Breakdowns

**For Agents**:
- ALWAYS report task completion to Orchestrator
- Use `./report-completion.sh role "completion message"` after major tasks
- Don't assume other agents know what you've done
- Include specific details (e.g., "EVENT_ROUTER_ENABLED=true")

**For Orchestrators**:
- Monitor for silent completions using checkin_monitor.py
- Set up dependencies: `set_role_dependencies(project, {'pm': ['devops']})`
- Use enhanced messaging scripts for critical communications
- Check session state regularly for agent status

**Example - Proper Deployment Reporting**:
```bash
# DevOps completes deployment
./report-completion.sh devops "Modal deployment complete - EVENT_ROUTER_ENABLED=true"

# This automatically:
# 1. Updates session state
# 2. Notifies Orchestrator
# 3. Triggers PM notification if PM depends on DevOps
# 4. Logs completion for audit
```

### Authorization and Approval Protocols

**Authorization workflows prevent bottlenecks** like Developer waiting for PM approval while PM is unaware.

#### Requesting Authorization
When you need approval from another role, use the explicit authorization request:
```bash
# Developer requests deployment authorization from PM
./request-authorization.sh developer "Deploy event_router.py to Modal production" "pm"

# This creates a tracked request with:
# - Unique request ID for tracking
# - Automatic routing to target AND Orchestrator
# - 30-minute timeout with escalation
# - Session state tracking (waiting_for)
```

#### Responding to Authorization Requests
When you receive an authorization request, respond promptly:
```bash
# Approve format
"Approved [REQUEST_ID]"

# Deny format  
"Denied [REQUEST_ID] - Reason: [explanation]"
```

#### Authorization Rules
1. **Use Explicit Requests**: Don't just mention "waiting for approval" - use the script
2. **Include Context**: Provide clear details about what you're requesting
3. **Respond Within 30 Minutes**: After timeout, request escalates to Orchestrator
4. **Track Request IDs**: Use the ID for clear request-response matching

#### Common Authorization Scenarios
- **Developer → PM**: Deployment authorization, merge approvals
- **PM → Orchestrator**: Major architecture decisions, priority changes
- **Any Role → SecurityOps**: Security exception requests
- **Any Role → SysAdmin**: System access or configuration changes

#### Timeout and Escalation
If no response within 30 minutes:
1. System automatically escalates to Orchestrator
2. Orchestrator will coordinate resolution
3. Original request remains valid until explicitly approved/denied

## Critical Self-Scheduling Protocol

### 🚨 MANDATORY STARTUP CHECK FOR ALL ORCHESTRATORS

**EVERY TIME you start or restart as an orchestrator, you MUST perform this check:**

```bash
# 1. Check your current tmux location
echo "Current pane: $TMUX_PANE"
CURRENT_WINDOW=$(tmux display-message -p "#{session_name}:#{window_index}")
echo "Current window: $CURRENT_WINDOW"

# 2. Test the scheduling script with your current window
./schedule_with_note.sh 1 "Test schedule for $CURRENT_WINDOW" "$CURRENT_WINDOW"

# 3. If scheduling fails, you MUST fix the script before proceeding
```

### Schedule Script Requirements

The `schedule_with_note.sh` script MUST:
- Accept a third parameter for target window: `./schedule_with_note.sh <minutes> "<note>" <target_window>`
- Default to `tmux-orc:0` if no target specified
- Always verify the target window exists before scheduling

### Why This Matters

- **Continuity**: Orchestrators must maintain oversight without gaps
- **Window Accuracy**: Scheduling to wrong window breaks the oversight chain
- **Self-Recovery**: Orchestrators must be able to restart themselves reliably

### Scheduling Best Practices

```bash
# Always use current window for self-scheduling
CURRENT_WINDOW=$(tmux display-message -p "#{session_name}:#{window_index}")
./schedule_with_note.sh 15 "Regular PM oversight check" "$CURRENT_WINDOW"

# For scheduling other agents, specify their windows explicitly
./schedule_with_note.sh 30 "Developer progress check" "ai-chat:2"
```

## Claude Code Credit Management 💳

### Overview
Claude Code has usage limits that reset every 5 hours. The orchestrator includes smart credit management to handle exhaustion gracefully.

### Credit Monitoring System

#### Quick Health Check
```bash
./credit_management/check_agent_health.sh
```
Shows credit status for all agents and estimated reset times.

#### Continuous Monitoring
```bash
# Install as systemd service (recommended)
./credit_management/install_monitor.sh

# Or run manually
./credit_management/credit_monitor.py
```

#### How It Works
1. **Detection**: Monitors for "/upgrade" messages and "credits will reset at [time]"
2. **UI Parsing**: Extracts exact reset times from Claude UI
3. **Fallback Schedule**: Uses 5-hour cycle calculation if UI parsing fails
4. **Auto-Resume**: Schedules agent wake-up 2 minutes after reset
5. **Verification**: Confirms credits available before resuming work

#### Credit-Aware Scheduling
All agent check-ins use credit-aware scheduling:
- Skips scheduling for exhausted agents
- Automatically schedules resume at reset time
- Logs all credit-related events

#### Status Tracking
Credit status stored in `~/.claude/credit_schedule.json`:
- Last known reset time
- Next predicted reset
- Per-agent exhaustion status
- Historical reset patterns

### Best Practices
1. **Start Monitor Early**: Run credit monitor when starting orchestration
2. **Check Status Regularly**: Use health check before critical operations
3. **Plan Around Resets**: Schedule important work after reset times
4. **Monitor Warning Signs**: "Approaching usage limit" means <10 minutes left

## Context Window Management

### Context Management is Automatic
Context window management happens automatically - agents don't need to worry about running any special commands. The system handles compacting and context management behind the scenes.

### Creating Checkpoints (Optional)
While not required, agents may choose to create checkpoint documents to track progress:

```bash
cat > ROLE_CHECKPOINT_$(date +%Y%m%d_%H%M).md << 'EOF'
## Context Checkpoint
- Current task: [what you're doing]
- Branch: [current branch]
- Recent work: [what was completed]
- Next steps: [specific actions]
EOF
```

### Best Practices
- Create checkpoints at natural breaks (phase transitions)
- Document progress periodically
- Keep clear notes about next steps

### For Orchestrators: Don't Worry About Low Context Agents

**IMPORTANT**: You can continue sending commands to agents even when they report low context (3%, 6%, etc). Here's why:

- **Context management is automatic**: The system handles context management automatically
- **Work continues seamlessly**: Agents can continue working without interruption
- **No manual intervention needed**: Context is managed behind the scenes
- **Keep delegating tasks**: Don't avoid low-context agents - they can handle it

**Best Practice**: When an agent mentions low context:
1. Acknowledge it: "Thanks for the heads up about context"
2. Continue normally: Send tasks as usual
3. The system will handle context management automatically
4. If they seem confused, remind them to read their checkpoint (if they created one)

### 🛠️ Orchestrator Tools for Context Management

The orchestrator has tools to monitor agent context levels:

1. **Monitor Agent Context Levels**:
   ```bash
   ./monitor_agent_context.sh
   ```
   Shows all agents' context levels for awareness

Since context management is now automatic, these tools are primarily for monitoring purposes rather than intervention.

## Anti-Patterns to Avoid

- ❌ **Meeting Hell**: Use async updates only
- ❌ **Endless Threads**: Max 3 exchanges, then escalate
- ❌ **Broadcast Storms**: No "FYI to all" messages
- ❌ **Micromanagement**: Trust agents to work
- ❌ **Quality Shortcuts**: Never compromise standards
- ❌ **Blind Scheduling**: Never schedule without verifying target window
- ❌ **Ignoring Credits**: Always monitor credit status for team continuity

## Critical Lessons Learned

### Tmux Window Management Mistakes and Solutions

#### Mistake 1: Wrong Directory When Creating Windows
**What Went Wrong**: Created server window without specifying directory, causing uvicorn to run in wrong location (Tmux orchestrator instead of Glacier-Analytics)

**Root Cause**: New tmux windows inherit the working directory from where tmux was originally started, NOT from the current session's active window

**Solution**: 
```bash
# Always use -c flag when creating windows
tmux new-window -t session -n "window-name" -c "/correct/path"

# Or immediately cd after creating
tmux new-window -t session -n "window-name"
tmux send-keys -t session:window-name "cd /correct/path" Enter
```

#### Mistake 2: Not Reading Actual Command Output
**What Went Wrong**: Assumed commands like `uvicorn app.main:app` succeeded without checking output

**Root Cause**: Not using `tmux capture-pane` to verify command results

**Solution**:
```bash
# Always check output after running commands
tmux send-keys -t session:window "command" Enter
sleep 2  # Give command time to execute
tmux capture-pane -t session:window -p | tail -50
```

#### Mistake 3: Typing Commands in Already Active Sessions
**What Went Wrong**: Typed "claude" in a window that already had Claude running

**Root Cause**: Not checking window contents before sending commands

**Solution**:
```bash
# Check window contents first
tmux capture-pane -t session:window -S -100 -p
# Look for prompts or active sessions before sending commands
```

#### Mistake 4: Incorrect Message Sending to Claude Agents
**What Went Wrong**: Initially sent Enter key with the message text instead of as separate command

**Root Cause**: Using `tmux send-keys -t session:window "message" Enter` combines them

**Solution**:
```bash
# Send message and Enter separately
tmux send-keys -t session:window "Your message here"
tmux send-keys -t session:window Enter
```

## Best Practices for Tmux Orchestration

### Pre-Command Checks
1. **Verify Working Directory**
   ```bash
   tmux send-keys -t session:window "pwd" Enter
   tmux capture-pane -t session:window -p | tail -5
   ```

2. **Check Command Availability**
   ```bash
   tmux send-keys -t session:window "which command_name" Enter
   tmux capture-pane -t session:window -p | tail -5
   ```

3. **Check for Virtual Environments**
   ```bash
   tmux send-keys -t session:window "ls -la | grep -E 'venv|env|virtualenv'" Enter
   ```

### Window Creation Workflow
```bash
# 1. Create window with correct directory
tmux new-window -t session -n "descriptive-name" -c "/path/to/project"

# 2. Verify you're in the right place
tmux send-keys -t session:descriptive-name "pwd" Enter
sleep 1
tmux capture-pane -t session:descriptive-name -p | tail -3

# 3. Activate virtual environment if needed
tmux send-keys -t session:descriptive-name "source venv/bin/activate" Enter

# 4. Run your command
tmux send-keys -t session:descriptive-name "your-command" Enter

# 5. Verify it started correctly
sleep 3
tmux capture-pane -t session:descriptive-name -p | tail -20
```

### Debugging Failed Commands
When a command fails:
1. Capture full window output: `tmux capture-pane -t session:window -S -200 -p`
2. Check for common issues:
   - Wrong directory
   - Missing dependencies
   - Virtual environment not activated
   - Permission issues
   - Port already in use

### Communication with Claude Agents

#### 🎯 SMART MESSAGING: Window Name Resolution (NEW!)

**Use window names instead of numbers to prevent targeting errors!** The new smart messaging system automatically resolves role names to window numbers:

```bash
# NEW: Use role names instead of window numbers (RECOMMENDED)
scm session-name:TestRunner "Run the test suite"
scm session-name:Developer "Status update needed"
scm session-name:Project-Manager "Review required"

# OLD: Prone to errors if window numbers change
scm session-name:4 "Run the test suite"  # Error-prone!
```

**Why Use Window Names?**
- **Prevents Targeting Errors**: No more sending messages to wrong windows
- **Self-Documenting**: Clear who you're messaging 
- **Automatic Resolution**: System finds the correct window number
- **Error Reporting**: Shows available roles if name not found

#### 📝 Messaging Commands Reference

**Main Commands:**
```bash
# Smart messaging (window name resolution + monitoring)
scm <session:role_name> "Your message"

# Legacy fallback (if needed)
./send-monitored-message.sh session:window_number "message"
```

**Helper Scripts (Available in Agent Worktrees):**
```bash
# Quick messaging to specific roles
./scripts/msg_orchestrator.sh "Task completed"
./scripts/msg_developer.sh "Need code review"
./scripts/msg_testrunner.sh "Please run tests"

# General messaging script
./scripts/msg.sh TestRunner "Execute test suite"
./scripts/msg.sh Developer "Implementation ready"

# View team members
./scripts/list_team.sh  # Shows all available roles
```

#### Smart Messaging Examples
```bash
# ✅ CORRECT: Use role names (NEW)
scm orchestrator-mobile-ux-impl-cd43aa77:TestRunner "Execute the security tests"
scm orchestrator-mobile-ux-impl-cd43aa77:Developer "Implementation completed"
scm orchestrator-mobile-ux-impl-cd43aa77:Project-Manager "Ready for review"

# ⚠️  LEGACY: Window numbers (error-prone)
scm orchestrator-mobile-ux-impl-cd43aa77:4 "Execute tests"  # Who is window 4?

# 🔍 DISCOVERY: Find available roles
tmux list-windows -t session-name -F '#{window_index}: #{window_name}'
```

#### Why Use Monitored Messaging?
1. **Compliance Tracking**: All messages logged and analyzed
2. **Rule Enforcement**: Automatic detection of violations
3. **Audit Trail**: Complete communication history
4. **Workflow Analysis**: Identify bottlenecks and delays
5. **Orchestrator Alerts**: Real-time violation notifications

#### Script Location and Usage
- **scm shortcut**: Available in PATH after setup
- **Full path**: `./send-monitored-message.sh` (in Tmux-Orchestrator directory)
- **Arguments**: 
  - First: target (session:window or session:window.pane)
  - Second: message (can contain spaces, will be properly handled)
- **Logs**: Communications saved to `registry/logs/communications/`

#### Common Messaging Patterns with the Script

##### 1. Starting Claude and Initial Briefing
```bash
# Start Claude first
tmux send-keys -t project:0 "claude" Enter
sleep 5

# Then use the monitored script for the briefing
scm project:0 "You are responsible for the frontend codebase. Please start by analyzing the current project structure and identifying any immediate issues."
```

##### 2. Cross-Agent Coordination (Through Hub-and-Spoke)
```bash
# Developer reports to PM
scm pm:0 "API endpoints ready at /api/v1/campaigns and /api/v1/flows"

# PM coordinates with other agents
scm developer:0 "Frontend needs these endpoints documented"
```

##### 3. Status Checks
```bash
# Quick status request
scm session:0 "Quick status update please"

# Detailed status request
scm session:0 "STATUS UPDATE: Please provide: 1) Completed tasks, 2) Current work, 3) Any blockers"
```

##### 4. Providing Assistance
```bash
# Share error information
scm session:0 "I see in your server window that port 3000 is already in use. Try port 3001 instead."

# Guide stuck agents
scm session:0 "The error you're seeing is because the virtual environment isn't activated. Run 'source venv/bin/activate' first."
```

#### FORBIDDEN: Direct Messaging Without Monitoring
```bash
# ❌ NEVER DO THIS:
tmux send-keys -t session:window "message"
./send-claude-message.sh session:window "message"

# ✅ ALWAYS DO THIS:
scm session:window "message"
```

#### Checking for Responses
After sending a message, check for the response:
```bash
# Send message
scm session:0 "What's your status?"

# Wait a bit for response
sleep 5

# Check what the agent said
tmux capture-pane -t session:0 -p | tail -50
```

### ⚠️ MCP Tmux Execute-Command Issues

**CRITICAL WARNING**: Do NOT use MCP's tmux execute-command for messaging!

**The Problem**: MCP's tmux tools often fail to send the Enter key, leaving messages undelivered. This particularly affects Project Managers who may have MCP tools available.

**Symptoms**:
- Messages appear in target window but aren't executed
- PM needs to manually "press enter" in agent windows
- Communication delays and confusion

**The Solution**: ALWAYS use `scm` command instead:
```bash
# ❌ WRONG - MCP tmux execute-command
# This often fails to send Enter key

# ✅ CORRECT - Use scm command
scm session:window "Your message"
```

**Why This Happens**: MCP's tmux integration sometimes sends the message text but fails to send the Enter key (C-m), requiring manual intervention. The `scm` command is specifically designed to handle this correctly.

## 📊 Compliance Monitoring System

### Overview
The Tmux Orchestrator includes an automated compliance monitoring system that ensures all agents follow CLAUDE.md rules.

### What is Monitored
1. **Communication Compliance**:
   - Hub-and-spoke model enforcement
   - Use of monitored messaging (scm)
   - Message template compliance
   - Work-related communication only

2. **Git Activity**:
   - 30-minute commit rule
   - Push timing (15-minute target)
   - Branch naming conventions
   - PR creation and merge timing
   - Agent synchronization status

3. **Workflow Health**:
   - Integration cycle duration
   - PR bottlenecks
   - Agent responsiveness
   - Credit exhaustion handling

### Monitoring Commands
```bash
# Start monitoring system
./monitoring/start_monitoring.sh

# Check current violations
cat registry/logs/communications/$(date +%Y-%m-%d)/violations.jsonl | jq .

# View workflow dashboard
./monitoring/workflow_dashboard.sh

# Stop monitoring
./monitoring/stop_monitoring.sh
```

### Automatic Rule Updates
- CLAUDE.md changes are detected automatically
- Rules are re-extracted within 2 seconds
- All new messages checked against updated rules
- No restart required

### Violation Handling
When violations are detected:
1. Orchestrator receives immediate notification
2. Specific remediation actions suggested
3. Violation logged with severity level
4. Resolution tracked automatically

### Log Structure
```
registry/logs/
├── communications/
│   └── YYYY-MM-DD/
│       ├── messages.jsonl        # All communications
│       ├── violations.jsonl      # Detected violations
│       └── compliance_analysis.jsonl
└── git-activity/
    └── YYYY-MM-DD/
        ├── commits.jsonl         # Commit activity
        ├── pushes.jsonl          # Push events
        └── pr-activity.jsonl     # PR status
```

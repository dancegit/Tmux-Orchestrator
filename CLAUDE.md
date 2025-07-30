# Claude.md - Tmux Orchestrator Project Knowledge Base

## Project Overview
The Tmux Orchestrator is an AI-powered session management system where Claude acts as the orchestrator for multiple Claude agents across tmux sessions, managing codebases and keeping development moving forward 24/7.

## 🚀 NEW: Auto-Orchestrate Feature

The `auto_orchestrate.py` script provides automated setup from specifications:

```bash
# Automatically set up a complete orchestration environment
./auto_orchestrate.py --project /path/to/project --spec /path/to/spec.md

# Resume an existing orchestration (NEW!)
./auto_orchestrate.py --project /path/to/project --resume

# Check status without changes
./auto_orchestrate.py --project /path/to/project --resume --status-only

# Force re-brief all agents
./auto_orchestrate.py --project /path/to/project --resume --rebrief-all
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

### Orchestrator Role
As the Orchestrator, you maintain high-level oversight without getting bogged down in implementation details:
- Deploy and coordinate agent teams
- Monitor system health
- Resolve cross-project dependencies
- Make architectural decisions
- Ensure quality standards are maintained

### Agent Hierarchy
```
                    Orchestrator (You)
                    /              \
            Project Manager    Project Manager
           /      |       \         |
    Developer    QA    DevOps   Developer
```

### Agent Types

#### Core Roles (Always Deployed)

1. **Orchestrator**: High-level oversight and coordination
   - Monitors overall project health and progress
   - Coordinates between multiple agents
   - Makes architectural and strategic decisions
   - Resolves cross-project dependencies
   - Schedules check-ins and manages team resources
   - Works from both project worktree AND tool directory

2. **Project Manager**: Quality-focused team coordination
   - Maintains exceptionally high quality standards
   - Reviews all code before merging
   - Coordinates daily standups and status collection
   - Manages git workflow and branch merging
   - Identifies and escalates blockers
   - Ensures 30-minute commit rule compliance
   - Tracks technical debt and quality metrics

3. **Developer**: Implementation and technical decisions
   - Writes production code following best practices
   - Implements features according to specifications
   - Creates unit tests for new functionality
   - Follows existing code patterns and conventions
   - Commits every 30 minutes with clear messages
   - Collaborates with Tester for test coverage
   - Works directly with Orchestrator for guidance

4. **Tester**: Testing and verification
   - Writes comprehensive test suites (unit, integration, E2E)
   - Ensures all success criteria are met
   - Creates test plans for new features
   - Verifies security and performance requirements
   - Collaborates with Developer for test coverage
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

8. **DevOps** (Medium/Large projects): Infrastructure and deployment
   - Creates and maintains deployment configurations
   - Sets up CI/CD pipelines
   - Manages staging and production environments
   - Implements infrastructure as code
   - Monitors system health and performance
   - Coordinates with Developer on build requirements
   - Ensures security best practices in deployment

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
```
Tmux-Orchestrator/
└── registry/
    └── projects/
        └── {project-name}/
            └── worktrees/
                ├── orchestrator/        # Orchestrator's project workspace
                ├── developer/           # Developer's workspace
                ├── tester/             # Tester's workspace
                └── testrunner/         # TestRunner's workspace
```

### 🎯 Orchestrator's Dual Directory Structure

The Orchestrator is unique - it works from TWO locations:

1. **Project Worktree** (`registry/projects/{name}/worktrees/orchestrator/`)
   - Primary working directory
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
pwd  # Shows: .../registry/projects/myproject/worktrees/orchestrator
mkdir -p project_management/architecture
echo "# Architecture Decisions" > project_management/architecture/decisions.md

# Switch to tool directory to run commands
cd ~/gitrepos/Tmux-Orchestrator  # Or wherever your Tmux-Orchestrator is
./send-claude-message.sh myproject-impl:1 "Status update please"
./schedule_with_note.sh 30 "Review team progress" "myproject-impl:0"

# Back to project worktree for more work
cd -  # Returns to previous directory
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

Project Managers must enforce git discipline:
- **VERIFY the starting branch** at project initialization
- **PREVENT unauthorized merges to main** - only if project started on main
- Remind engineers to commit every 30 minutes
- Verify feature branches are created from the correct parent branch
- Ensure meaningful commit messages
- Check that stable tags are created
- Track branch hierarchy to prevent accidental main branch pollution

### Why This Matters

- **Work Loss Prevention**: Hours of work can vanish without commits
- **Collaboration**: Other agents can see and build on committed work
- **Rollback Safety**: Can always return to a working state
- **Progress Tracking**: Clear history of what was accomplished

## 🌳 Git Worktree & Workflow Rules

### Worktree Structure
Each agent works in isolated worktree:
```
registry/projects/{project}/worktrees/
├── orchestrator/     # Dual-directory agent
├── project-manager/  # Integration coordinator
├── developer/        # Implementation
├── tester/          # Test creation
├── researcher/      # MCP research
└── [other-agents]/  # Role-specific
```

### Worktree Discipline Rules
1. **Stay in Your Lane**: Never directly modify files in other agents' worktrees
2. **Read-Only Access**: Can read/review other worktrees: `cat ../developer/src/file.py`
3. **Push Your Work**: Share via GitHub, not direct file edits
4. **Orchestrator Exception**: Works from both project worktree AND tool directory

### Git Push Rules
1. **Push Frequently**: Within 15 minutes of any significant commit
2. **Branch Naming Convention**:
   - Developer: `feature/description`
   - PM: `pm-feature/description`
   - Tester: `test/description`
   - TestRunner: `testrunner/description`
   - Researcher: `research/description`
   - DevOps: `devops/description`
3. **Set Upstream**: First push MUST use `-u`:
   ```bash
   git push -u origin feature/your-branch
   ```
4. **Announce Pushes**: Notify PM immediately after pushing:
   ```bash
   scm pm:0 "Pushed feature/auth-endpoints - ready for review"
   ```

### Pull Request Workflow
1. **Timing Requirements**:
   - Create PR within 30 minutes of push
   - PM merges within 2 hours
   - Integration cycle completes within 4 hours
2. **PR Creation**: Only PM creates integration PRs
3. **Auto-Merge Protocol**: Use `--admin` flag (no manual approvals)
4. **Notification**: Announce PR creation and merges

### PM Integration Protocol
```bash
# Step 1: Create integration branch
git checkout main  # or parent branch
git pull origin main
git checkout -b integration/feature-name

# Step 2: Merge all agent branches
git merge origin/feature/developer-work
git merge origin/test/tester-work
git merge origin/testrunner/test-results

# Step 3: Resolve conflicts (delegate to appropriate agent)
# Developer: Code conflicts
# Tester: Test conflicts
# PM: Documentation conflicts

# Step 4: Push integration branch
git push -u origin integration/feature-name

# Step 5: Create PR with auto-merge intent
gh pr create --base main \
  --head integration/feature-name \
  --title "Integration: Feature Name" \
  --body "Integrated work from all agents on feature-name

Auto-merging after integration."

# Step 6: Auto-merge immediately
gh pr merge --admin --merge

# Step 7: Notify all agents via orchestrator
scm orchestrator:0 "Integration complete! All agents pull from main"
```

### Agent Synchronization Rules
1. **Pull After Integration**: All agents must pull within 1 hour
2. **Check for Updates**: Every hour, check teammate branches
3. **Conflict Resolution**: Resolve within 30 minutes
4. **Stay Current**: Maximum 20 commits behind parent branch
5. **Sync Commands**:
   ```bash
   # Check your sync status
   git fetch origin
   git status
   git log HEAD..origin/main --oneline
   
   # Pull latest changes
   git pull origin main
   ```

### Workflow Timing Targets
- **Commit → Push**: 15 minutes
- **Push → PR**: 30 minutes  
- **PR → Merge**: 2 hours
- **Merge → Pull**: 1 hour
- **Full Integration Cycle**: 4 hours maximum

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
./auto_orchestrate.py --project /path/to/project --spec /path/to/spec.md
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

### Hub-and-Spoke Model
With the simplified structure, the Orchestrator acts as the central hub:
- All agents report directly to Orchestrator
- Orchestrator coordinates all cross-functional communication
- Direct agent-to-agent communication only for immediate needs (test handoffs)
- Clear, focused communication reduces complexity

### Role Communication Matrix

With the simplified role structure, communication is streamlined:

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
./auto_orchestrate.py --project /path --spec spec.md --plan max5

# Force small team for extended session
./auto_orchestrate.py --project /path --spec spec.md --size small
```

## Team Deployment

### When User Says "Work on [new project]"

**Recommended**: Use auto_orchestrate.py for automated setup with git worktrees:
```bash
./auto_orchestrate.py --project /any/path/to/project --spec project_spec.md
```

For manual setup:

#### 1. Project Analysis
```bash
# Find project (if in ~/projects/)
ls -la ~/projects/ | grep -i "[project-name]"

# Or work with any project path
cd /path/to/project

# Analyze project type
test -f package.json && echo "Node.js project"
test -f requirements.txt && echo "Python project"
```

#### 2. Propose Team Structure

**Small Project**: Orchestrator + PM + Developer + Researcher
**Medium Project**: + Second Developer + Tester
**Large Project**: + DevOps + Code Reviewer

#### 3. Deploy Team
Create session and deploy all agents with specific briefings for their roles.

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

#### 🎯 IMPORTANT: Always Use Monitored Messaging for Compliance

**DO NOT use send-claude-message.sh directly anymore!** Use the monitored wrapper for compliance tracking:

```bash
# Use the shortcut command (REQUIRED)
scm session:window "Your message here"

# Or if scm is not in PATH
./send-monitored-message.sh session:window "Your message"

# OLD METHOD (DO NOT USE):
# ❌ ./send-claude-message.sh session:window "message"
```

**Why Monitored Messaging?**
- Automatic compliance checking against CLAUDE.md rules
- Logs all communications for audit trail
- Detects hub-and-spoke violations
- Enables workflow analysis
- Provides orchestrator visibility

#### Using Monitored Messaging (scm)
```bash
# Basic usage - ALWAYS use this for compliance
scm <target> "message"

# Examples:
# Send to a window
scm agentic-seek:3 "Hello Claude!"

# Send to a specific pane in split-screen
scm tmux-orc:0.1 "Message to pane 1"

# Send complex instructions
scm glacier-backend:0 "Please check the database schema for the campaigns table and verify all columns are present"

# Send status update requests
scm ai-chat:2 "STATUS UPDATE: What's your current progress on the authentication implementation?"
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

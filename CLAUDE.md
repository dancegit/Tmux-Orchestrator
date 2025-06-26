# Claude.md - Tmux Orchestrator Project Knowledge Base

## Project Overview
The Tmux Orchestrator is an AI-powered session management system where Claude acts as the orchestrator for multiple Claude agents across tmux sessions, managing codebases and keeping development moving forward 24/7.

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
1. **Project Manager**: Quality-focused team coordination
2. **Developer**: Implementation and technical decisions
3. **QA Engineer**: Testing and verification
4. **DevOps**: Infrastructure and deployment
5. **Code Reviewer**: Security and best practices
6. **Researcher**: Technology evaluation
7. **Documentation Writer**: Technical documentation

## 🔐 Git Discipline - MANDATORY FOR ALL AGENTS

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
   # Before starting any new feature/task
   git checkout -b feature/[descriptive-name]
   
   # After completing feature
   git add -A
   git commit -m "Complete: [feature description]"
   git tag stable-[feature]-$(date +%Y%m%d-%H%M%S)
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
- Remind engineers to commit every 30 minutes
- Verify feature branches are created for new work
- Ensure meaningful commit messages
- Check that stable tags are created

### Why This Matters

- **Work Loss Prevention**: Hours of work can vanish without commits
- **Collaboration**: Other agents can see and build on committed work
- **Rollback Safety**: Can always return to a working state
- **Progress Tracking**: Clear history of what was accomplished

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

Follow this systematic sequence to start any project:

#### 1. Find the Project
```bash
# List all directories in ~/Coding to find projects
ls -la ~/Coding/ | grep "^d" | awk '{print $NF}' | grep -v "^\."

# If project name is ambiguous, list matches
ls -la ~/Coding/ | grep -i "task"  # for "task templates"
```

#### 2. Create Tmux Session
```bash
# Create session with project name (use hyphens for spaces)
PROJECT_NAME="task-templates"  # or whatever the folder is called
PROJECT_PATH="/Users/jasonedward/Coding/$PROJECT_NAME"
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
ls -la ~/Coding/ | grep -i task
# Found: task-templates

# 2. Create session
tmux new-session -d -s task-templates -c "/Users/jasonedward/Coding/task-templates"

# 3. Set up windows
tmux rename-window -t task-templates:0 "Claude-Agent"
tmux new-window -t task-templates -n "Shell" -c "/Users/jasonedward/Coding/task-templates"
tmux new-window -t task-templates -n "Dev-Server" -c "/Users/jasonedward/Coding/task-templates"

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
To prevent communication overload (n² complexity), use structured patterns:
- Developers report to PM only
- PM aggregates and reports to Orchestrator
- Cross-functional communication goes through PM
- Emergency escalation directly to Orchestrator

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

## Team Deployment

### When User Says "Work on [new project]"

#### 1. Project Analysis
```bash
# Find project
ls -la ~/Coding/ | grep -i "[project-name]"

# Analyze project type
cd ~/Coding/[project-name]
test -f package.json && echo "Node.js project"
test -f requirements.txt && echo "Python project"
```

#### 2. Propose Team Structure

**Small Project**: 1 Developer + 1 PM
**Medium Project**: 2 Developers + 1 PM + 1 QA  
**Large Project**: Lead + 2 Devs + PM + QA + DevOps

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
  ~/Coding/Tmux\ orchestrator/registry/logs/[session]_[role]_$(date +%Y%m%d_%H%M%S).log

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
~/Coding/Tmux orchestrator/registry/
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

## Anti-Patterns to Avoid

- ❌ **Meeting Hell**: Use async updates only
- ❌ **Endless Threads**: Max 3 exchanges, then escalate
- ❌ **Broadcast Storms**: No "FYI to all" messages
- ❌ **Micromanagement**: Trust agents to work
- ❌ **Quality Shortcuts**: Never compromise standards

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

#### 🎯 IMPORTANT: Always Use send-claude-message.sh Script

**DO NOT manually send messages with tmux send-keys anymore!** We have a dedicated script that handles all the timing and complexity for you.

#### Using send-claude-message.sh
```bash
# Basic usage - ALWAYS use this instead of manual tmux commands
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh <target> "message"

# Examples:
# Send to a window
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh agentic-seek:3 "Hello Claude!"

# Send to a specific pane in split-screen
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh tmux-orc:0.1 "Message to pane 1"

# Send complex instructions
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh glacier-backend:0 "Please check the database schema for the campaigns table and verify all columns are present"

# Send status update requests
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh ai-chat:2 "STATUS UPDATE: What's your current progress on the authentication implementation?"
```

#### Why Use the Script?
1. **Automatic timing**: Handles the critical 0.5s delay between message and Enter
2. **Simpler commands**: One line instead of three
3. **No timing mistakes**: Prevents the common error of Enter being sent too quickly
4. **Works everywhere**: Handles both windows and panes automatically
5. **Consistent messaging**: All agents receive messages the same way

#### Script Location and Usage
- **Location**: `/Users/jasonedward/Coding/Tmux orchestrator/send-claude-message.sh`
- **Permissions**: Already executable, ready to use
- **Arguments**: 
  - First: target (session:window or session:window.pane)
  - Second: message (can contain spaces, will be properly handled)

#### Common Messaging Patterns with the Script

##### 1. Starting Claude and Initial Briefing
```bash
# Start Claude first
tmux send-keys -t project:0 "claude" Enter
sleep 5

# Then use the script for the briefing
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh project:0 "You are responsible for the frontend codebase. Please start by analyzing the current project structure and identifying any immediate issues."
```

##### 2. Cross-Agent Coordination
```bash
# Ask frontend agent about API usage
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh frontend:0 "Which API endpoints are you currently using from the backend?"

# Share info with backend agent
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh backend:0 "Frontend is using /api/v1/campaigns and /api/v1/flows endpoints"
```

##### 3. Status Checks
```bash
# Quick status request
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh session:0 "Quick status update please"

# Detailed status request
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh session:0 "STATUS UPDATE: Please provide: 1) Completed tasks, 2) Current work, 3) Any blockers"
```

##### 4. Providing Assistance
```bash
# Share error information
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh session:0 "I see in your server window that port 3000 is already in use. Try port 3001 instead."

# Guide stuck agents
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh session:0 "The error you're seeing is because the virtual environment isn't activated. Run 'source venv/bin/activate' first."
```

#### OLD METHOD (DO NOT USE)
```bash
# ❌ DON'T DO THIS ANYMORE:
tmux send-keys -t session:window "message"
sleep 1
tmux send-keys -t session:window Enter

# ✅ DO THIS INSTEAD:
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh session:window "message"
```

#### Checking for Responses
After sending a message, check for the response:
```bash
# Send message
/Users/jasonedward/Coding/Tmux\ orchestrator/send-claude-message.sh session:0 "What's your status?"

# Wait a bit for response
sleep 5

# Check what the agent said
tmux capture-pane -t session:0 -p | tail -50
```

## Orchestrator-Specific Patterns

### Agent Communication & Assistance

**Critical Insight**: You can send messages to agents even when they're busy! Messages will be queued and the agent will see them after their current task.

#### When to Send Queued Messages:
1. **Cross-Window Intelligence**: You see errors or important info in one window that the agent needs
2. **Steering Guidance**: Agent seems stuck or heading in wrong direction
3. **Resource Sharing**: You have access to information from other sessions/windows
4. **Proactive Assistance**: Preventing issues before they become blockers

#### Examples of Helpful Interventions:
```bash
# Frontend agent struggling with port issues, but you see in npm window:
"I see in your npm-run-dev window that the server is running on port 3002, not 3001"

# Backend agent looking for files, but you checked another window:
"The frontend is using /api/v1/public/* endpoints - I confirmed this from their window"

# Agent getting errors you can see in server logs:
"Check the server window - seeing 'module not found' errors for uvicorn"

# Sharing cross-session insights:
"The ai-chat session has auth working with Clerk - might help with your implementation"
```

#### Your Orchestrator Advantages:
1. **Multi-Window Vision**: See all windows across all sessions
2. **Cross-Project Knowledge**: Connect solutions from different codebases
3. **Real-Time Monitoring**: Spot issues as they happen in logs/servers
4. **Pattern Recognition**: Notice similar problems across projects

#### Best Practices:
- Always specify WHERE you saw the information ("in your server window", "from the frontend agent")
- Be specific about errors/issues you observe
- Suggest concrete next steps based on what you see
- Use your bird's-eye view to prevent agents from duplicating work

### Checking All Sessions Status
```bash
# Manually check each session
for session in $(tmux list-sessions -F "#{session_name}"); do
    echo "=== Session: $session ==="
    tmux list-windows -t $session
done

# Check specific window contents
tmux capture-pane -t session:window -p | tail -50
```

### Coordinating Between Agents
1. Always verify both agents are ready before cross-communication
2. Use clear, specific messages about what you need
3. Wait for responses before proceeding
4. Document any dependencies between projects

## Status Sync - Cross-Team Intelligence Gathering

**Status Sync** is a critical orchestrator workflow for gathering comprehensive intelligence across multiple active sessions before making coordination decisions.

### When to Use Status Sync
- User requests coordination between multiple projects/teams
- Need to understand current state before assigning new tasks
- Debugging issues that span multiple sessions
- Before making architectural decisions affecting multiple agents
- When agents report conflicting information or blocking issues

### Status Sync Workflow

#### 1. Rapid Multi-Session Reconnaissance
```bash
# Capture recent activity from all relevant sessions (run in parallel)
tmux capture-pane -t session1 -S -2000 -p | tail -1000
tmux capture-pane -t session2 -S -2000 -p | tail -1000
tmux capture-pane -t session3 -S -2000 -p | tail -1000
```

#### 2. Intelligence Analysis Pattern
For each session, identify:
- **Current Task**: What the agent is actively working on
- **Recent Progress**: What they've accomplished in the last 30-60 minutes
- **Technical Issues**: Any errors, blockers, or challenges encountered
- **Dependencies**: What they're waiting for from other teams
- **System State**: Server status, compilation state, test results

#### 3. Cross-Session Correlation
Look for:
- **Complementary Work**: Agent A needs info Agent B has discovered
- **Duplicate Efforts**: Multiple agents solving the same problem
- **Blocking Chains**: Agent A blocked on Agent B's work
- **Resource Conflicts**: Port conflicts, file locks, etc.
- **Integration Points**: APIs, data formats, authentication

#### 4. Coordinated Status Report
Provide user with:
```
## 🔍 Status Sync Report

### Session A (Project/Role)
- ✅ Completed: [Specific achievements]
- ⏳ Current: [Active work]
- ⚠️ Issues: [Blockers/challenges]
- 📅 Next: [Planned steps]

### Session B (Project/Role)  
- ✅ Completed: [Specific achievements]
- ⏳ Current: [Active work] 
- ⚠️ Issues: [Blockers/challenges]
- 📅 Next: [Planned steps]

### 🎯 Coordination Opportunities
- [Specific ways teams can help each other]
- [Dependencies to resolve]
- [Resource sharing opportunities]

### 🚨 Critical Issues Requiring Attention
- [Blockers needing user intervention]
- [Conflicts between teams]
- [Technical debt accumulating]
```

### Status Sync Command Patterns
```bash
# Quick status check across all sessions
for session in $(tmux list-sessions -F "#{session_name}"); do
    echo "=== $session Status ==="
    tmux capture-pane -t $session:0 -p | tail -20
    echo ""
done

# Deep dive into specific sessions
tmux capture-pane -t glacier-backend -S -1000 -p | grep -E "(ERROR|SUCCESS|COMPLETED|FAILED|BLOCKED)"
tmux capture-pane -t glacier-frontend -S -1000 -p | grep -E "(ERROR|SUCCESS|COMPLETED|FAILED|BLOCKED)"

# Check server/process status
tmux capture-pane -t session:server-window -p | tail -30
```

### Benefits of Status Sync
1. **Prevents Miscommunication**: Get ground truth from agent logs
2. **Identifies Hidden Dependencies**: See what agents actually need
3. **Spots Integration Issues**: Catch API mismatches early
4. **Enables Smart Coordination**: Make informed decisions about priorities
5. **Reduces Context Switching**: One comprehensive update vs. multiple check-ins

### Status Sync Anti-Patterns
- ❌ **Shallow Checking**: Only looking at last few lines
- ❌ **Single Session Focus**: Missing cross-session dependencies  
- ❌ **No Analysis**: Just copying logs without interpretation
- ❌ **Outdated Intel**: Using stale information for decisions
- ❌ **Over-Reporting**: Including irrelevant details instead of key insights

### Example Status Sync Scenarios

**Scenario 1: Backend/Frontend Integration**
```
User: "Check status on Glacier backend and frontend"
Orchestrator: [Runs Status Sync]
Finding: Backend returning campaign data to flow endpoints, frontend expecting flow data structure
Action: Coordinate fix - backend needs schema alignment, frontend has field logging ready
```

**Scenario 2: Cross-Project Authentication**
```
User: "Why is auth not working consistently?"
Orchestrator: [Runs Status Sync across all auth-related sessions]
Finding: ai-chat has Clerk working, glacier-frontend has Clerk, glacier-backend expects Basic auth
Action: Standardize auth approach or create auth translation layer
```

**Status Sync Frequency**: Use this pattern at the start of any coordination task and whenever you need to make informed decisions about multiple active projects.

## Database Schema Verification Protocol

### CRITICAL: Always Check Database Schema FIRST
When debugging data issues, empty results, or field mismatches:

#### 1. Open Database and Inspect Schema
```bash
# For DuckDB
tmux send-keys -t backend:window "python3" Enter
tmux send-keys -t backend:window "import duckdb" Enter
tmux send-keys -t backend:window "conn = duckdb.connect('warehouse.db')" Enter
tmux send-keys -t backend:window "conn.execute('SHOW TABLES').fetchall()" Enter
tmux send-keys -t backend:window "conn.execute('DESCRIBE table_name').fetchall()" Enter

# Or use SQL directly
tmux send-keys -t backend:window "duckdb warehouse.db" Enter
tmux send-keys -t backend:window ".tables" Enter
tmux send-keys -t backend:window "DESCRIBE stg_klaviyo_flows;" Enter
```

#### 2. Common Schema Issues to Check
- **Column names**: `id` vs `flow_id`, `campaign_id` vs `id`
- **Data types**: String vs Integer IDs
- **NULL constraints**: Required fields that might be NULL
- **Foreign key relationships**: JOIN columns must exist
- **Naming conventions**: snake_case vs camelCase

#### 3. SQL JOIN Debugging Pattern
```sql
-- ALWAYS verify column exists before JOINing
DESCRIBE table1;
DESCRIBE table2;

-- Test JOIN with limited data first
SELECT t1.*, t2.*
FROM table1 t1
LEFT JOIN table2 t2 ON t1.column = t2.column
LIMIT 5;
```

#### 4. Field Mapping Verification
When frontend expects different fields than backend provides:
```bash
# Backend: Check actual API response
curl -s "http://localhost:8000/api/endpoint" | python3 -m json.tool | head -50

# Compare with frontend expectations
# Look for: opens_unique vs unique_opens, clicks_unique vs unique_clicks, etc.
```

### Example: The Flow ID Issue
**Problem**: 3+ hours debugging empty results
**Root Cause**: `LEFT JOIN stg_klaviyo_flows f ON fs.flow_id = f.id`
**Issue**: Table had `flow_id` column, not `id`
**Solution**: `LEFT JOIN stg_klaviyo_flows f ON fs.flow_id = f.flow_id`
**Lesson**: ALWAYS check schema before debugging complex issues

### Browser Console Direct Access
Instead of asking user for console logs:
```bash
# Start browser console monitor
cd /Users/jasonedward/Coding/Tmux\ orchestrator
node setup_puppeteer_console_monitor.js

# Or use single visible browser for testing
node single_visible_browser.js
```

## Remember: Always Learn from Mistakes
When something goes wrong:
1. Document it immediately in this file
2. Include the specific error
3. Explain why it happened
4. Document how to prevent it
5. Add any commands that would have caught it earlier

This creates a growing knowledge base that prevents repeated mistakes and improves orchestration efficiency.

## CRITICAL: Always Schedule Next Check-in Before Ending

**NEVER end a conversation without scheduling your return!**

### Using schedule_with_note.sh
```bash
# Schedule check-in with practical note about what to check
./schedule_with_note.sh <minutes> "<practical note about what to check>"

# Examples of GOOD notes:
./schedule_with_note.sh 5 "Check if frontend agent finished identifying used endpoints"
./schedule_with_note.sh 10 "Verify backend cleanup completed and no endpoints are broken"
./schedule_with_note.sh 3 "Check server logs for errors, review agent progress on migrations"
./schedule_with_note.sh 15 "Review if DuckDB data load completed, check for any errors"
./schedule_with_note.sh 0.5 "Quick check on agent response to endpoint question"

# Examples of BAD notes (too vague/motivational):
# "Victory awaits!" 
# "Continue the great work!"
# "Legendary progress incoming!"
```

**Technical Note**: The script now properly sends Enter as a separate command after a 1-second delay, following our tmux communication best practices.

### When to Schedule Check-ins
- **Quick tasks (2-5 min)**: Check back in 5 minutes
- **Medium tasks (5-15 min)**: Check back in 10-15 minutes  
- **Long tasks (15+ min)**: Check back in 20-30 minutes
- **Overnight tasks**: Check back in 1-2 hours

### What to Include in Notes
1. **Specific tasks to check**: "Verify frontend test results"
2. **Agent coordination**: "Check if backend agent responded about directory structure"
3. **Error monitoring**: "Review server logs for connection errors"
4. **Progress tracking**: "Check if data migration completed"
5. **Next steps**: "Ready to start endpoint cleanup after getting used endpoints list"

### Check-in Workflow
When you return from a scheduled check-in:
1. First check all sessions using tmux commands to get overall status
2. Check specific windows mentioned in your note
3. Address any errors or blockers
4. Coordinate next steps between agents
5. Schedule your next check-in before leaving

### Example End-of-Session Pattern
```bash
# Before ending any orchestrator session:
# 1. Keep the note SHORT (what to check)
./schedule_with_note.sh 1 "Check frontend endpoint analysis"

# 2. Provide detailed status summary separately
```

Then provide a **Current Status Summary** with:
- ✅ Completed tasks
- ⏳ In-progress work  
- 📅 Next steps
- Any important context (ports, file paths, etc.)

This ensures continuous orchestration without gaps or forgotten tasks.

**Note**: schedule_with_note.sh accepts decimal minutes (0.17 for 10 seconds, 0.5 for 30 seconds, 1.5 for 90 seconds, etc.)
# UV Workspace Configuration Investigation & Fix Requirements

## Problem Summary
The Tmux-Orchestrator project is experiencing UV workspace configuration issues that are blocking deployment. The primary issue is that UV commands are failing due to workspace detection problems when the project is not in a proper UV workspace structure.

## Current Todo List Status
1. **Fix UV workspace configuration to unblock deployment** (HIGH PRIORITY - PENDING)
2. **Send immediate workaround to team with UV_NO_WORKSPACE=1** (HIGH PRIORITY - IN PROGRESS)
3. **Modify auto_orchestrate.py for root-level agent access** (MEDIUM PRIORITY - PENDING)

## Investigation Progress
### Files Analyzed
- **auto_orchestrate.py**: Main orchestration script (lines 2101-2800 examined)
  - Found git worktree management methods
  - Found tmux session setup and Claude initialization
  - Found MCP (Model Context Protocol) tool handling
  - Found team communication protocols
  - **UV command execution points NOT YET LOCATED** - need to continue search

### Key Findings
1. The auto_orchestrate.py file contains extensive worktree and tmux management code
2. UV commands are executed somewhere in the codebase but exact locations not yet identified
3. System files show active process locks and SQLite shared memory usage
4. MCP tools integration for agent briefing is in place

## Immediate Workaround Solution
Set environment variable `UV_NO_WORKSPACE=1` when executing UV commands to bypass workspace detection.

## Required Next Steps

### 1. Locate UV Command Execution Points
- Continue reading auto_orchestrate.py from line 2801 onwards
- Search for UV command invocations using patterns like:
  - `uv run`
  - `uv install` 
  - `uv sync`
  - `subprocess.*uv`
  - `os.system.*uv`

### 2. Implement UV_NO_WORKSPACE Fix
Once UV command locations are found:
- Add `UV_NO_WORKSPACE=1` to environment variables before UV commands
- Update any subprocess calls or environment setup
- Test the fix to ensure deployment unblocking

### 3. Root-Level Agent Access
- Modify auto_orchestrate.py to allow agents to access root-level project files
- This may involve adjusting the worktree setup or path resolution

## File Context
- **Working Directory**: `/home/clauderun/Tmux-Orchestrator`
- **Lock File**: `/home/clauderun/Tmux-Orchestrator/locks/project_queue.lock` (active with PID 1576426)
- **Database**: SQLite with shared memory segments in use
- **Main Script**: `auto_orchestrate.py` (large file, systematic reading required)

## Technical Context
- **UV**: Modern Python package and project manager with workspace configuration
- **Tmux Orchestration**: Multi-agent development system using tmux sessions
- **Git Worktrees**: Agent isolation using separate worktrees
- **MCP Integration**: Model Context Protocol for agent tool access
- **SQLite Queue**: Task queue database with shared memory files

## Search Strategy
When continuing the investigation:
1. Use `Grep` tool to search for UV-related patterns across the codebase
2. Focus on subprocess execution and environment variable handling
3. Look for any existing UV configuration or workspace setup code
4. Check for any existing workarounds or environment modifications

## Priority
This is a HIGH PRIORITY issue blocking deployment. The immediate workaround should be implemented as soon as UV command locations are identified.
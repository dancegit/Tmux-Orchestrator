# Git Worktree Architecture

## Worktree Locations
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

## Verification Commands
```bash
# Always verify worktree locations
git worktree list  # Shows all worktrees and their actual paths
pwd               # Confirms your current location
```

## Orchestrator's Dual Directory Structure
The Orchestrator works from TWO locations:

1. **Project Worktree** (`{project_path}-tmux-worktrees/orchestrator/`)
   - Primary working directory
   - Create ALL project files here
   - Status reports, documentation, architecture decisions

2. **Tool Directory** (Tmux-Orchestrator root)
   - Run orchestrator tools:
     - `./send-claude-message.sh`
     - `./schedule_with_note.sh`
     - `python3 claude_control.py`

## Shared Directory Access
Each agent's worktree includes a `shared` directory with symlinks:

```
your-worktree/
└── shared/
    ├── main-project/     → Main project directory
    ├── developer/        → Developer's worktree
    ├── tester/          → Tester's worktree
    └── [other agents]/  → Other agent worktrees
```

### Directory Navigation
```bash
# ✅ CORRECT: Use relative path through shared
cd ./shared/main-project
git pull origin main

# ❌ WRONG: Direct absolute path (blocked by Claude)
cd /path/to/main-project  # Error: blocked for security
```


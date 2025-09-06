# Claude.md - Tmux Orchestrator Knowledge Base

## IMPORTANT: Modularized Documentation

This project uses **modularized documentation** for better performance and maintainability.
The full documentation is split into focused modules located in: `docs/claude_modules/`

## Quick Reference

### For Agents Being Briefed
1. **Core Modules** (MANDATORY - Load First):
   - `docs/claude_modules/core/principles.md` - Autonomy and action principles
   - `docs/claude_modules/core/communication.md` - Hub-spoke model and messaging
   - `docs/claude_modules/core/completion.md` - Completion signaling

2. **Role-Specific Modules**:
   - `docs/claude_modules/roles/core_roles.md` - Orchestrator, PM, Developer, Tester
   - `docs/claude_modules/roles/optional_roles.md` - Additional specialized roles

3. **Workflow Modules**:
   - `docs/claude_modules/workflows/git_workflow.md` - Git operations
   - `docs/claude_modules/workflows/worktree_setup.md` - Worktree architecture

### Module Loading
The briefing system automatically loads appropriate modules for each role using the ModuleLoader.
See `docs/claude_modules/index.md` for the complete module structure.

## Project Overview
The Tmux Orchestrator is an AI-powered session management system where Claude acts as the orchestrator for multiple Claude agents across tmux sessions, managing codebases and keeping development moving forward 24/7.

## 🚀 Auto-Orchestrate Feature

```bash
# Start new orchestration
./tmux_orchestrator_cli.py run --project /path/to/project --spec /path/to/spec.md

# Resume existing orchestration
./tmux_orchestrator_cli.py run --project /path/to/project --resume

# Check status
./tmux_orchestrator_cli.py run --project /path/to/project --resume --status-only
```

## Core Principles (Summary)

### 🎯 AUTONOMY FIRST
Start working IMMEDIATELY after reading briefing. Do NOT wait for permissions.

### ⚡ ACTION-ORIENTED
Implement, test, and commit code autonomously. Report progress during check-ins.

### 🚫 DEADLOCK AVOIDANCE
If stuck, ASSUME AUTHORIZATION and proceed. Escalate only TRUE BLOCKERS.

### 🔄 WORK IMMEDIATELY
Begin implementation within 2 minutes of briefing. No permission-seeking.

## Communication Model

### Hub-Spoke Architecture
- **Orchestrator** = Central hub
- **All agents** = Spokes reporting to hub
- **No lateral communication** between agents
- **Scheduled check-ins** maintain coordination

## Key Commands

### Session Management
```bash
# List sessions
tmux ls

# Attach to Orchestrator
tmux attach -t orchestrator

# Send message to agent
tmux send-keys -t developer:0 "message here" Enter
```

### Scheduler Commands
```bash
# Add scheduled check-in
python3 scheduler.py --add orchestrator Orchestrator 0 15 "Regular check-in"

# List scheduled tasks
python3 scheduler.py --list

# Start scheduler daemon
python3 scheduler.py --daemon
```

## Directory Structure
```
Tmux-Orchestrator/
├── docs/claude_modules/     # Modularized documentation
│   ├── core/               # Core principles
│   ├── roles/              # Role definitions
│   ├── workflows/          # Process guides
│   └── index.md           # Module index
├── tmux_orchestrator/       # Modular system
├── scheduler.py            # Task scheduler
└── tmux_orchestrator_cli.py # Main CLI
```

## Critical Rules

1. **Use Modular Documentation**: Reference modules in `docs/claude_modules/` for detailed information
2. **Token Efficiency**: This file is kept minimal - load specific modules as needed
3. **Briefing System**: Uses ModuleLoader to automatically load role-appropriate modules
4. **Performance**: Modules are designed to be under 10,000 tokens each

## Getting Started

1. For new agents: Start with `docs/claude_modules/index.md`
2. For briefing: Use the intelligent briefing system with ModuleLoader
3. For reference: Access specific modules in `docs/claude_modules/`

---
**Version**: 2.0.0 (Modularized)
**Last Updated**: 2025-09-06
**Full Documentation**: See `docs/claude_modules/` directory
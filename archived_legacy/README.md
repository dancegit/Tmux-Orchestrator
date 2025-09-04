# Archived Legacy Code

This directory contains legacy code that has been replaced by the modular tmux_orchestrator system.

## Files

### auto_orchestrate_legacy.py.txt
- **Original name**: auto_orchestrate.py
- **Retired**: 2025-09-03
- **Replaced by**: tmux_orchestrator_cli.py and the modular tmux_orchestrator package
- **Description**: Monolithic orchestration script that handled all aspects of project orchestration
- **Reason for retirement**: Successfully migrated to modular architecture for better maintainability, testability, and scalability

## Migration Details

The functionality of auto_orchestrate.py has been decomposed into the following modules:

- **tmux_orchestrator_cli.py**: Main CLI entry point
- **tmux_orchestrator/core/**: Core orchestration logic
- **tmux_orchestrator/agents/**: Agent management and briefing
- **tmux_orchestrator/claude/**: Claude integration and spec analysis
- **tmux_orchestrator/git/**: Git worktree management
- **tmux_orchestrator/tmux/**: Tmux session control
- **tmux_orchestrator/database/**: Queue management
- **scheduler_modules/**: Modular scheduler components

## Active System

The current active system uses:
- `tmux_orchestrator_cli.py run` for orchestration
- Modular scheduler via systemd services (tmux-orchestrator-queue.service, tmux-orchestrator-checkin.service)

## Note

This file has been renamed with .txt extension to prevent it from being imported or executed accidentally.
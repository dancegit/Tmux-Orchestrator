# CLAUDE Knowledge Base - Module Index

This is the modularized version of CLAUDE.md, split into focused modules for better maintainability and token efficiency.

## Core Modules (All Agents Must Read)
- [core/principles.md](core/principles.md) - Fundamental autonomy and action principles
- [core/communication.md](core/communication.md) - Hub-spoke model and messaging protocols  
- [core/completion.md](core/completion.md) - Completion signaling and reporting

## Role Definitions
- [roles/core_roles.md](roles/core_roles.md) - Orchestrator, PM, Developer, Tester, TestRunner
- [roles/optional_roles.md](roles/optional_roles.md) - Researcher, DevOps, Code Reviewer, etc.
- [roles/system_ops_roles.md](roles/system_ops_roles.md) - SysAdmin, SecurityOps, NetworkOps, etc.

## Workflows and Processes
- [workflows/git_workflow.md](workflows/git_workflow.md) - Git rules, commits, branching
- [workflows/worktree_setup.md](workflows/worktree_setup.md) - Worktree architecture and navigation

## Configuration
- [configuration/team_detection.md](configuration/team_detection.md) - Project type detection and team templates
- [configuration/scaling.md](configuration/scaling.md) - Team sizing and token management

## Module Loading Guide

### For Agents
1. Always load core modules first
2. Load your specific role module
3. Load relevant workflow modules
4. Reference configuration as needed

### For Systems
- Briefing System: Use ModuleLoader to load role-specific content
- Rule Extraction: Target specific modules for rule types
- Monitoring: Check individual modules for compliance

## Migration Note
This modular structure replaces the monolithic CLAUDE.md file. Each module is designed to be under 10,000 tokens for reliable Claude reading.

---
Version: 1.0.0
Last Updated: 2025-01-06
Total Modules: 10

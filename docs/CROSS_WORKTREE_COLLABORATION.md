# Cross-Worktree Collaboration Guide

## Overview

This document explains the enhanced cross-worktree collaboration features added to the Tmux Orchestrator's auto-orchestrate system. These improvements make it easier for agents to work together across isolated git worktrees.

## Key Enhancements

### 1. Team Worktree Locations in All Briefings

Every agent now receives a comprehensive list of all team members' worktree locations:

```
📂 Team Worktree Locations & Cross-Worktree Collaboration:

Your Team's Worktrees:
- Orchestrator (orchestrator): /path/to/worktrees/orchestrator/
- Project-Manager (project_manager): /path/to/worktrees/project_manager/
- Developer (developer): /path/to/worktrees/developer/
- Tester (tester): /path/to/worktrees/tester/
- Researcher (researcher): /path/to/worktrees/researcher/

Main Project Directory (shared resources): /path/to/main/project/
  - Use for shared files (mcp-inventory.md, project docs, etc.)
  - All agents can read/write here
```

### 2. Visual Worktree Map

A quick reference map is included in all briefings:

```
📍 Quick Reference - Team Locations Map:
Main Project: /home/user/myproject/
├── mcp-inventory.md (shared by all)
├── docs/ (shared documentation)
└── [project files]

Team Worktrees:
├── Orchestrator: /path/to/worktrees/orchestrator/
├── Project-Manager: /path/to/worktrees/project_manager/
├── Developer: /path/to/worktrees/developer/
└── Tester: /path/to/worktrees/tester/
```

### 3. Cross-Worktree Collaboration Instructions

All agents receive specific instructions on how to:

#### Review Another Agent's Code
```bash
# Read files from another agent's worktree
cat /path/to/worktrees/developer/src/main.py

# List files in another agent's worktree
ls -la /path/to/worktrees/tester/tests/
```

#### Get Another Agent's Changes
```bash
# Fetch and merge changes from another agent's branch
git fetch origin
git branch -r  # See all remote branches
git merge origin/feature-developer  # Merge developer's branch
```

#### Share Your Changes
```bash
# Push your branch so others can access it
git add -A && git commit -m "Your changes"
git push -u origin your-branch-name
```

## Role-Specific Enhancements

### Project Manager

Enhanced with specific code review workflows:

```bash
# Daily Code Review Process
# 1. Review Developer's changes
cd /path/to/worktrees/developer/
git status  # Check their current work
git log --oneline -10  # Review recent commits
git diff HEAD~1  # Review latest changes

# 2. Review test coverage
cd /path/to/worktrees/tester/
ls -la tests/  # Check test structure
grep -r "test_" tests/  # Find all test functions

# 3. Cross-reference implementation with tests
# Use Read tool for detailed review
```

**Quality Verification Checklist**:
- Code follows project conventions
- All new functions have tests
- Error handling is comprehensive
- Documentation is updated
- No hardcoded values or secrets
- Performance implications considered

### Developer

Instructions for making code reviewable:

```bash
# 1. Commit frequently with clear messages
git add -A
git commit -m "feat: implement user authentication endpoint"

# 2. Push your branch for PM review
git push -u origin feature-branch

# 3. Notify PM when ready for review
# "Ready for review: authentication module in src/auth/"
# "Tests added in tests/test_auth.py"
```

### Tester

Testing across worktrees workflow:

```bash
# 1. Get Developer's latest code
git fetch origin
git merge origin/feature-branch

# 2. Or directly test files from Developer's worktree
python -m pytest /path/to/worktrees/developer/tests/

# 3. Create tests based on Developer's implementation
# Read their code: cat /path/to/worktrees/developer/src/module.py
# Write corresponding tests in your worktree
```

### Researcher

Clear instructions on accessing shared resources:

```bash
# Read the MCP inventory from main project
cat /path/to/main/project/mcp-inventory.md

# Your research outputs go in YOUR worktree
cd /path/to/worktrees/researcher/
mkdir -p research
echo "# Available Tools" > research/available-tools.md
```

## Important Notes

### Shared vs. Isolated Files

- **Shared files** (in main project directory):
  - `mcp-inventory.md` - Created by orchestrator, read by all
  - `docs/` - Shared documentation
  - Project-wide configuration files

- **Isolated files** (in individual worktrees):
  - Source code being developed
  - Tests being written
  - Role-specific outputs
  - Work-in-progress files

### Git Workflow Across Worktrees

1. Each agent works in their own worktree
2. Agents create feature branches from the parent branch
3. Regular commits and pushes make work visible
4. Other agents can fetch and merge changes
5. PM coordinates merges between worktrees
6. Final merge to parent branch when ready

## Benefits

1. **No Conflicts**: Agents can't accidentally overwrite each other's work
2. **Visibility**: Clear paths to review any agent's code
3. **Collaboration**: Easy to share and integrate changes
4. **Organization**: Clear separation of concerns
5. **Review Process**: PM can easily review all work

## Best Practices

1. **Commit Often**: Make your work visible to the team
2. **Use Clear Messages**: Help others understand your changes
3. **Push Regularly**: Allow others to access your work
4. **Communicate Paths**: When discussing files, use full paths
5. **Review Before Merging**: PM should review all cross-worktree merges
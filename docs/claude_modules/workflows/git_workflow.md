# Git Workflow and Best Practices

## Core Git Rules

### 30-Minute Commit Rule (MANDATORY)
Every agent MUST commit progress every 30 minutes:
```bash
git add -A
git commit -m "Progress: [specific description of what was done]"
```

### Branch Protection Rules
**NEVER MERGE TO MAIN UNLESS YOU STARTED ON MAIN**

1. **When Starting a Project - Record the Branch**:
```bash
STARTING_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo $STARTING_BRANCH > .git/STARTING_BRANCH
echo "Project started on branch: $STARTING_BRANCH"
```

2. **Feature Branch Workflow**:
```bash
# ALWAYS check current branch first
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Currently on branch: $CURRENT_BRANCH"

# Before starting any new feature/task
git checkout -b feature/[descriptive-name]

# After completing feature
git add -A
git commit -m "Complete: [feature description]"
git tag stable-[feature]-$(date +%Y%m%d-%H%M%S)

# Merge back to PARENT branch (not necessarily main!)
git checkout $CURRENT_BRANCH
git merge feature/[descriptive-name]
```

### Meaningful Commit Messages
- Bad: "fixes", "updates", "changes"
- Good: "Add user authentication endpoints with JWT tokens"
- Good: "Fix null pointer in payment processing module"
- Good: "Refactor database queries for 40% performance gain"

### Local Remotes for Fast Collaboration
To enable fast, asynchronous collaboration (60-500x faster than GitHub), use local remotes:

```bash
# Use absolute paths - Note: worktrees are SIBLINGS to project!
git remote add orchestrator /path/to/project-tmux-worktrees/orchestrator
git remote add pm /path/to/project-tmux-worktrees/pm
git remote add developer /path/to/project-tmux-worktrees/developer
git remote add tester /path/to/project-tmux-worktrees/tester
```

Usage:
- Fetch: `git fetch <role>` (e.g., `git fetch developer`)
- View Progress: `git log remotes/<role>/<role> --since="30 minutes ago"`
- Merge (PM): `git checkout integration && git merge remotes/<role>/<role> --no-ff`


# Git Commit-Tag-Push Feature

## Overview
Automated git workflow that combines committing, tagging with semantic versioning, and pushing to remote in a single command.

## Features
- **Automatic Version Tagging**: Increments version based on commit message type
- **Semantic Versioning**: Follows major.minor.patch convention
- **Co-Author Attribution**: Automatically adds Tmux Orchestrator as co-author
- **Smart Staging**: Can stage specific files or all changes
- **Push Integration**: Pushes both commits and tags to remote

## Usage

### Quick Usage (Shell Script)
```bash
./git-ctp "feat: add new feature"
```

### Python Module Usage
```bash
python3 git_commit_manager.py "fix: resolve authentication bug" -a
```

### Options
- `-a, --all`: Stage all changes (recommended)
- `-f, --files FILE1 FILE2`: Stage specific files
- `--no-tag`: Skip automatic tagging
- `--no-push`: Skip pushing to remote
- `--bump major/minor/patch`: Override automatic version detection

## Commit Message Conventions

The tool automatically detects version bump type from your commit message:

| Prefix | Version Bump | Example | Result |
|--------|-------------|---------|---------|
| `feat:` or `feature:` | Minor | `feat: add user dashboard` | 1.0.0 → 1.1.0 |
| `fix:` or `bugfix:` | Patch | `fix: resolve login issue` | 1.0.0 → 1.0.1 |
| `breaking:` or `breaking change:` | Major | `breaking: refactor API` | 1.0.0 → 2.0.0 |
| Other | Patch | `docs: update readme` | 1.0.0 → 1.0.1 |

## Integration with Orchestrator

All agents in orchestrated projects are briefed about this feature and can use it:

```bash
# From any agent's worktree
cd ./shared/main-project
./git-ctp "feat: implement authentication module"
```

## Example Workflow

```bash
# Make changes to your code
vim src/auth.py

# Commit, tag, and push in one command
./git-ctp "feat: implement JWT authentication"

# Output:
# ✅ Commit created: a1b2c3d4
# ✅ Tagged as: v1.2.0
# ✅ Pushed to remote
```

## Technical Details

The `GitCommitManager` class provides:
- Version parsing and increment logic
- Git status checking
- Atomic commit-tag-push operations
- Error handling and rollback

## Best Practices

1. **Use descriptive commit messages**: Start with the appropriate prefix
2. **Review changes**: The tool shows what will be committed
3. **Test before major releases**: Use `--no-push` to test locally first
4. **Follow team conventions**: Coordinate version numbering with your team

## Troubleshooting

- **"No version tags found"**: The tool will start from v0.1.0
- **"Failed to push"**: Check your remote configuration and permissions
- **"Invalid version format"**: Ensure existing tags follow vX.Y.Z format
# CLAUDE Configuration Implementation Guide

## Quick Start Implementation

### Step 1: Create the Configuration Structure

```bash
#!/bin/bash
# setup_claude_config.sh

# Create base structure
mkdir -p ~/.claude/config/{rules,workflows,protocols,roles}

# Initialize git repository for version control
cd ~/.claude/config
git init

# Create initial .gitignore
cat > .gitignore << EOF
*.tmp
*.log
.DS_Store
EOF

echo "CLAUDE configuration structure created at ~/.claude/config/"
```

### Step 2: Split Current CLAUDE.md into Modules

#### rules/agent_compliance.md
```markdown
# Agent Compliance Rules
Version: 1.0.0

## File Management
- NEVER create/implement copies/improved/v2 etc of files
- NEVER create temporary scripts or logs in the root of the project
- NEVER write fixes in separate files (e.g., fix_scheduler_session_validation.py)
- ALWAYS FIX the original file
- Use temporary folders like ./temp ./logs

## Code Quality
- NEVER RESORT TO SIMPLIFYING THINGS AND CUTTING THINGS OUT
- INSTEAD TRY TO SOLVE THE PROBLEM
- NEVER CREATE GARBAGE SCRIPTS
```

#### rules/deployment_rules.md
```markdown
# Deployment Rules
Version: 1.0.0

## Modal.com Specific
- NEVER deploy to production unless stated
- ALWAYS check environment with "modal config show" or "uv modal config show"
- NEVER use variant names for apps (test/prod suffixes handle environment)

## Deployment Requirements
- Always commit and push to github before deploying
- Always increase version numbers and create tags
- Always increase version tag in image for rebuilds
- Default to test environments unless specified
- PUSH CHANGES TO GITHUB with new tag before Modal deploy
```

#### workflows/git_workflow.md
```markdown
# Git Workflow
Version: 1.0.0

## Pre-Deployment Checklist
1. Commit all changes
2. Push to remote
3. Create version tag
4. Push tag
5. Verify clean working directory

## Tag Format
- Use semantic versioning: vX.Y.Z
- Major: Breaking changes
- Minor: New features
- Patch: Bug fixes

## Example
```bash
git add .
git commit -m "feat: Add new feature"
git push origin main
git tag v1.2.0
git push origin v1.2.0
```
```

#### protocols/communication.md
```markdown
# Communication Protocols
Version: 1.0.0

## Grok Integration
- Use grok_discuss for complex problems
- ALWAYS include full context
- Set max_context_lines to 1000
- Don't cut out file content
- Follow up with session_id

## Problem Escalation
1. Attempt to solve independently
2. If stuck, prepare full context
3. Use grok_discuss with all relevant files
4. Implement Grok's suggestions
5. Report back results
```

#### roles/script_execution.md
```markdown
# Script Execution Guidelines
Version: 1.0.0

## Timeout Management
- ALWAYS use tmux or nohup for scripts
- 2-minute execution limit for direct commands
- Use timeouts for Modal commands:
  - `timeout 30 uv run modal app list`
  - `timeout 30 uv run modal app logs`

## Python Execution
- Use uv always, not python directly
- Handle errors with full context
```

### Step 3: Create Master Index

#### ~/.claude/config/INDEX.md
```markdown
# CLAUDE Configuration Index
Version: 1.0.0
Last Updated: 2025-01-28

## Configuration Modules

### Rules
- [Agent Compliance](rules/agent_compliance.md) - File management and code quality
- [Deployment Rules](rules/deployment_rules.md) - Modal.com and deployment standards

### Workflows
- [Git Workflow](workflows/git_workflow.md) - Version control procedures
- [Deployment Workflow](workflows/deployment_workflow.md) - Step-by-step deployment

### Protocols
- [Communication](protocols/communication.md) - Hub-spoke model and Grok integration
- [File Management](protocols/file_management.md) - File creation/editing standards

### Roles
- [Script Execution](roles/script_execution.md) - Timeout and execution guidelines
```

### Step 4: Create Project Integration Script

```bash
#!/bin/bash
# integrate_claude_config.sh

PROJECT_DIR="$1"

if [ -z "$PROJECT_DIR" ]; then
    echo "Usage: $0 <project_directory>"
    exit 1
fi

# Create .claude directory in project
mkdir -p "$PROJECT_DIR/.claude"

# Create a combined CLAUDE.md from modules
cat > "$PROJECT_DIR/.claude/CLAUDE.md" << 'EOF'
# CLAUDE Configuration
# Auto-generated from modular configuration
# Source: ~/.claude/config/

EOF

# Concatenate relevant modules
for module in rules/agent_compliance.md rules/deployment_rules.md workflows/git_workflow.md protocols/communication.md; do
    if [ -f ~/.claude/config/$module ]; then
        echo "## From $module" >> "$PROJECT_DIR/.claude/CLAUDE.md"
        echo "" >> "$PROJECT_DIR/.claude/CLAUDE.md"
        cat ~/.claude/config/$module >> "$PROJECT_DIR/.claude/CLAUDE.md"
        echo -e "\n---\n" >> "$PROJECT_DIR/.claude/CLAUDE.md"
    fi
done

echo "CLAUDE configuration integrated into $PROJECT_DIR/.claude/CLAUDE.md"
```

### Step 5: Version Control and Change Management

#### ~/.claude/config/update.sh
```bash
#!/bin/bash
# Update and version CLAUDE configuration

# Check for changes
cd ~/.claude/config
if [ -n "$(git status --porcelain)" ]; then
    echo "Changes detected in CLAUDE configuration"
    
    # Get current version
    CURRENT_VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    
    # Prompt for version bump type
    echo "Current version: $CURRENT_VERSION"
    echo "Select version bump type:"
    echo "1) Patch (bug fixes, clarifications)"
    echo "2) Minor (new rules, sections)"
    echo "3) Major (breaking changes)"
    read -p "Choice (1-3): " choice
    
    # Calculate new version
    # ... (version calculation logic)
    
    # Commit and tag
    git add .
    git commit -m "Update CLAUDE configuration to $NEW_VERSION"
    git tag "$NEW_VERSION"
    
    # Update all projects
    echo "Updating all integrated projects..."
    # ... (update logic)
fi
```

## Benefits of This Implementation

1. **Centralized Management**: All rules in one place
2. **Project Flexibility**: Projects can include only relevant rules
3. **Version Tracking**: Git history shows all changes
4. **Easy Updates**: Change once, update everywhere
5. **Validation**: Scripts ensure consistency
6. **Documentation**: Clear structure and purpose

## Migration Path

1. **Week 1**: Set up structure, split CLAUDE.md
2. **Week 2**: Test with one project
3. **Week 3**: Roll out to all projects
4. **Week 4**: Implement automation and monitoring

## Monitoring Compliance

Create a monitoring script to check rule adherence:

```python
# ~/.claude/config/monitor_compliance.py
import os
import re
from pathlib import Path

class ComplianceMonitor:
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.violations = []
    
    def check_versioned_files(self):
        """Check for _v2, _improved, etc. files"""
        pattern = re.compile(r'.*(_v\d+|_improved|_copy|_old)\.(py|js|md)$')
        for file in self.project_path.rglob('*'):
            if pattern.match(str(file)):
                self.violations.append(f"Versioned file found: {file}")
    
    def check_root_scripts(self):
        """Check for temporary scripts in root"""
        root_files = [f for f in self.project_path.glob('*.py') 
                     if 'temp' in f.name or 'test' in f.name]
        for file in root_files:
            self.violations.append(f"Temporary script in root: {file}")
    
    def generate_report(self):
        """Generate compliance report"""
        if not self.violations:
            return "✓ No compliance violations found"
        
        report = "Compliance Violations:\n"
        for violation in self.violations:
            report += f"  - {violation}\n"
        return report
```

This implementation provides a solid foundation for better CLAUDE.md organization with clear benefits for maintainability, versioning, and project-specific customization.
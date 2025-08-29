#!/usr/bin/env python3
"""
Script to set up Claude hooks for an agent workspace.
This configures the .claude directory with proper hooks for message queue integration.
"""

import os
import shutil
import json
import argparse
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def setup_agent_hooks(
    worktree_path: Path,
    agent_id: str,
    orchestrator_path: Path,
    db_path: Optional[Path] = None
):
    """
    Configure hooks for an agent workspace.
    
    Args:
        worktree_path: Path to the agent's worktree
        agent_id: Agent identifier (session:window)
        orchestrator_path: Path to Tmux-Orchestrator directory
        db_path: Optional path to task_queue.db
    """
    logger.info(f"Setting up hooks for agent {agent_id} at {worktree_path}")
    
    # Create .claude directory
    claude_dir = worktree_path / '.claude'
    claude_dir.mkdir(exist_ok=True)
    
    # Copy hook configuration
    hook_config_src = orchestrator_path / 'claude_hooks' / 'settings.json'
    hook_config_dst = claude_dir / 'settings.json'
    
    if hook_config_src.exists():
        shutil.copy(hook_config_src, hook_config_dst)
        logger.info(f"Copied hook configuration to {hook_config_dst}")
    else:
        logger.warning(f"Hook configuration template not found at {hook_config_src}")
    
    # Create hooks directory and symlinks
    hooks_dir = claude_dir / 'hooks'
    hooks_dir.mkdir(exist_ok=True)
    
    hook_scripts = [
        'check_queue.py',
        'cleanup_agent.py',
        'enqueue_message.py',
        'tmux_message_sender.py',
        'git_policy_enforcer.py',
        'setup_git_policy_hooks.py'
    ]
    
    for script in hook_scripts:
        src = orchestrator_path / 'claude_hooks' / script
        dst = hooks_dir / script
        
        if src.exists():
            if dst.exists():
                dst.unlink()  # Remove existing symlink/file
            
            # Create relative symlink
            try:
                relative_src = os.path.relpath(str(src), str(hooks_dir))
                dst.symlink_to(relative_src)
                logger.info(f"Created symlink: {dst} -> {relative_src}")
            except OSError:
                # Fallback to absolute symlink on Windows or if relative fails
                dst.symlink_to(src)
                logger.info(f"Created absolute symlink: {dst} -> {src}")
        else:
            logger.warning(f"Hook script not found: {src}")
    
    # Create logs directory for hooks
    logs_dir = claude_dir / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Generate settings.local.json
    settings_local_path = claude_dir / 'settings.local.json'
    
    # Extract session name and project name from agent_id
    session_name = agent_id.split(':')[0]
    project_name = session_name.replace('-session', '') if '-session' in session_name else session_name
    
    local_config = {
        "agent_id": agent_id,
        "session_name": session_name,
        "project_name": project_name,
        "db_path": str(db_path or orchestrator_path / 'task_queue.db'),
        "orchestrator_path": str(orchestrator_path),
        "ready_flag_timeout": 30,
        "direct_delivery_enabled": True,
        "hooks_enabled": True
    }
    
    # Merge with existing config if it exists
    if settings_local_path.exists():
        try:
            with open(settings_local_path, 'r') as f:
                existing_config = json.load(f)
            # Update existing config
            existing_config.update(local_config)
            local_config = existing_config
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in {settings_local_path}, overwriting")
    
    with open(settings_local_path, 'w') as f:
        json.dump(local_config, f, indent=2)
    
    logger.info(f"Generated {settings_local_path}")
    
    # Set environment variables for the hooks
    env_file = claude_dir / 'hook_env.sh'
    with open(env_file, 'w') as f:
        f.write(f"""#!/bin/bash
# Environment variables for Claude hooks
export QUEUE_DB_PATH="{local_config['db_path']}"
export CLAUDE_PROJECT_DIR="{worktree_path}"
export TMUX_SESSION_NAME="{session_name}"
export ORCHESTRATOR_PATH="{orchestrator_path}"
""")
    
    os.chmod(env_file, 0o755)
    logger.info(f"Created environment file: {env_file}")
    
    # Set up git hooks if this is an agent worktree (not the main orchestrator repo)
    if is_agent_worktree(worktree_path, orchestrator_path):
        setup_git_hooks(worktree_path, agent_id, orchestrator_path)
    else:
        logger.info(f"Skipping git hooks installation - not an agent worktree: {worktree_path}")
    
    return True

def is_agent_worktree(worktree_path: Path, orchestrator_path: Path) -> bool:
    """Check if this is an agent worktree (not the main orchestrator repository)"""
    try:
        # If the worktree path is the same as orchestrator path, it's the main repo
        if worktree_path.resolve() == orchestrator_path.resolve():
            return False
        
        # Check if this is a git worktree (has .git file pointing to main repo)
        git_file = worktree_path / '.git'
        if git_file.is_file():
            with open(git_file) as f:
                content = f.read().strip()
                if content.startswith('gitdir:'):
                    return True  # This is a git worktree
        
        # Check if this directory name suggests it's an agent worktree
        worktree_name = worktree_path.name
        agent_patterns = ['-tmux-worktrees', '-worktrees', 'developer/', 'tester/', 'orchestrator/', 'pm/', 'project-manager/']
        
        for pattern in agent_patterns:
            if pattern in str(worktree_path):
                return True
                
        return False
        
    except Exception as e:
        logger.warning(f"Could not determine if {worktree_path} is an agent worktree: {e}")
        return False  # Default to not installing hooks if uncertain

def setup_git_hooks(worktree_path: Path, agent_id: str, orchestrator_path: Path):
    """Install git hooks in agent worktrees for policy enforcement"""
    
    # Check if this is a git repository
    git_dir = worktree_path / '.git'
    if not git_dir.exists():
        # Check if it's a worktree (has .git file pointing to git dir)
        git_file = worktree_path / '.git'
        if git_file.is_file():
            try:
                with open(git_file) as f:
                    content = f.read().strip()
                    if content.startswith('gitdir:'):
                        # Extract actual git directory path
                        git_dir_path = content.split(':', 1)[1].strip()
                        if not Path(git_dir_path).is_absolute():
                            git_dir_path = worktree_path / git_dir_path
                        git_dir = Path(git_dir_path)
                    else:
                        logger.info(f"Not a git repository: {worktree_path} - skipping git hooks")
                        return
            except Exception:
                logger.info(f"Not a git repository: {worktree_path} - skipping git hooks")
                return
        else:
            logger.info(f"Not a git repository: {worktree_path} - skipping git hooks")
            return
    
    # For worktrees, hooks directory is in the main .git directory structure
    if (worktree_path / '.git').is_file():
        # This is a worktree, hooks go in the main repo
        hooks_dir = git_dir / 'hooks'
    else:
        # This is a regular git repo
        hooks_dir = git_dir / 'hooks'
    
    hooks_dir.mkdir(exist_ok=True)
    logger.info(f"Setting up git hooks in {hooks_dir}")
    
    # Extract agent role from agent_id for role-specific hooks
    session_name = agent_id.split(':')[0]
    if 'orchestrator' in session_name:
        agent_role = 'orchestrator'
    elif 'developer' in session_name or 'dev' in session_name:
        agent_role = 'developer'
    elif 'tester' in session_name or 'test' in session_name:
        agent_role = 'tester'
    elif 'project-manager' in session_name or 'pm' in session_name:
        agent_role = 'project-manager'
    else:
        agent_role = 'agent'
    
    # Pre-push hook to enforce local-first and GitHub restrictions
    pre_push_content = f'''#!/bin/bash
# Git Policy Enforcement: Pre-push hook
# Enforces local-first workflow and GitHub usage restrictions

remote="$1"
url="$2"

# Skip policy enforcement if emergency bypass is set
if [[ "${{EMERGENCY_BYPASS}}" == "true" ]]; then
    echo "⚠️  Emergency bypass enabled - skipping git policy enforcement"
    exit 0
fi

python3 "{orchestrator_path}/claude_hooks/git_policy_enforcer.py" \\
    --hook-type pre-push \\
    --agent {agent_role} \\
    --worktree-path "{worktree_path}" \\
    --remote "$remote" \\
    --url "$url"

exit $?
'''
    
    pre_push_hook = hooks_dir / 'pre-push'
    pre_push_hook.write_text(pre_push_content)
    pre_push_hook.chmod(0o755)
    logger.info(f"Created pre-push hook: {pre_push_hook}")
    
    # Post-commit hook for PM notification and compliance logging
    post_commit_content = f'''#!/bin/bash
# Git Policy Enforcement: Post-commit hook  
# Handles PM notifications and compliance logging

# Skip during rebase/merge operations
if [[ -f "{git_dir}/REBASE_HEAD" ]] || [[ -f "{git_dir}/MERGE_HEAD" ]]; then
    exit 0
fi

python3 "{orchestrator_path}/claude_hooks/git_policy_enforcer.py" \\
    --hook-type post-commit \\
    --agent {agent_role} \\
    --worktree-path "{worktree_path}"

# Continue regardless of hook result (don't block commits)
exit 0
'''
    
    post_commit_hook = hooks_dir / 'post-commit'
    post_commit_hook.write_text(post_commit_content)
    post_commit_hook.chmod(0o755)
    logger.info(f"Created post-commit hook: {post_commit_hook}")
    
    # Pre-merge-commit hook for rebase enforcement
    pre_merge_content = f'''#!/bin/bash
# Git Policy Enforcement: Pre-merge-commit hook
# Enforces rebase workflow (fast-forward merges only)

# Skip policy enforcement if emergency bypass is set
if [[ "${{EMERGENCY_BYPASS}}" == "true" ]]; then
    echo "⚠️  Emergency bypass enabled - allowing merge commit"
    exit 0
fi

# Check if this is a fast-forward merge (rebased)
if git merge-base --is-ancestor HEAD MERGE_HEAD 2>/dev/null; then
    echo "✅ Fast-forward merge (rebased) - proceeding"
    exit 0
else
    echo "🚫 POLICY VIOLATION: Non-fast-forward merge detected"
    echo "Required: Rebase your branch first"
    echo "Run: git rebase <target-branch>"
    echo "This enforces the rebase workflow defined in CLAUDE.md"
    echo ""
    echo "To bypass this check temporarily, set: export EMERGENCY_BYPASS=true"
    exit 1
fi
'''
    
    pre_merge_hook = hooks_dir / 'pre-merge-commit'
    pre_merge_hook.write_text(pre_merge_content)
    pre_merge_hook.chmod(0o755)
    logger.info(f"Created pre-merge-commit hook: {pre_merge_hook}")
    
    logger.info(f"✅ Git hooks installed for agent {agent_id} (role: {agent_role})")

def verify_hook_setup(worktree_path: Path) -> bool:
    """Verify that hooks are properly set up."""
    claude_dir = worktree_path / '.claude'
    
    required_files = [
        claude_dir / 'settings.json',
        claude_dir / 'settings.local.json',
        claude_dir / 'hooks' / 'check_queue.py',
        claude_dir / 'hooks' / 'git_policy_enforcer.py'
    ]
    
    for file_path in required_files:
        if not file_path.exists():
            logger.error(f"Missing required file: {file_path}")
            return False
    
    # Check if hooks are executable (symlinks should preserve permissions)
    hooks_dir = claude_dir / 'hooks'
    for script in hooks_dir.glob('*.py'):
        if not os.access(script, os.X_OK):
            logger.warning(f"Hook script not executable: {script}")
            # Try to make it executable
            os.chmod(script, 0o755)
    
    # Verify git hooks if this is a git repository
    git_dir = worktree_path / '.git'
    if git_dir.exists() or (worktree_path / '.git').is_file():
        try:
            # Find the actual hooks directory
            if (worktree_path / '.git').is_file():
                with open(worktree_path / '.git') as f:
                    content = f.read().strip()
                    if content.startswith('gitdir:'):
                        git_dir_path = content.split(':', 1)[1].strip()
                        if not Path(git_dir_path).is_absolute():
                            git_dir_path = worktree_path / git_dir_path
                        git_hooks_dir = Path(git_dir_path) / 'hooks'
                    else:
                        git_hooks_dir = None
            else:
                git_hooks_dir = git_dir / 'hooks'
            
            if git_hooks_dir and git_hooks_dir.exists():
                git_hook_files = ['pre-push', 'post-commit', 'pre-merge-commit']
                for hook_name in git_hook_files:
                    hook_file = git_hooks_dir / hook_name
                    if hook_file.exists() and os.access(hook_file, os.X_OK):
                        logger.info(f"✅ Git hook verified: {hook_name}")
                    else:
                        logger.warning(f"⚠️  Git hook missing or not executable: {hook_name}")
            else:
                logger.warning("Git hooks directory not found")
                
        except Exception as e:
            logger.warning(f"Could not verify git hooks: {e}")
    
    logger.info("Hook setup verified successfully")
    return True

def main():
    """CLI interface for setting up agent hooks."""
    parser = argparse.ArgumentParser(description="Set up Claude hooks for agent workspace")
    parser.add_argument("worktree", type=Path, help="Path to agent worktree")
    parser.add_argument("--agent-id", required=True, help="Agent ID (session:window)")
    parser.add_argument("--orchestrator-path", type=Path, 
                       default=Path(__file__).parent,
                       help="Path to Tmux-Orchestrator")
    parser.add_argument("--db-path", type=Path, help="Path to task_queue.db")
    parser.add_argument("--verify-only", action="store_true", 
                       help="Only verify existing setup")
    
    args = parser.parse_args()
    
    if args.verify_only:
        success = verify_hook_setup(args.worktree)
        exit(0 if success else 1)
    
    try:
        setup_agent_hooks(
            worktree_path=args.worktree,
            agent_id=args.agent_id,
            orchestrator_path=args.orchestrator_path,
            db_path=args.db_path
        )
        
        # Verify setup
        if verify_hook_setup(args.worktree):
            print(f"Successfully set up hooks for {args.agent_id}")
        else:
            print("Hook setup completed with warnings")
            
    except Exception as e:
        print(f"Error setting up hooks: {e}")
        exit(1)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
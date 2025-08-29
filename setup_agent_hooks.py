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
        'check_queue_enhanced.py',
        'cleanup_agent.py',
        'enqueue_message.py',
        'auto_restart.py'
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
    
    return True

def verify_hook_setup(worktree_path: Path) -> bool:
    """Verify that hooks are properly set up."""
    claude_dir = worktree_path / '.claude'
    
    required_files = [
        claude_dir / 'settings.json',
        claude_dir / 'settings.local.json',
        claude_dir / 'hooks' / 'check_queue_enhanced.py'
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
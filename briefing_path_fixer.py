#!/usr/bin/env python3
"""
Module to fix path issues in agent briefings dynamically.
This can be imported and used to fix briefings before they are sent to agents.
"""

import re
from pathlib import Path


def fix_briefing_paths(briefing: str, role: str, worktree_path: str, project_path: str) -> str:
    """
    Fix path references in briefings to use appropriate paths for worktree context.
    
    Args:
        briefing: The original briefing text
        role: The agent role
        worktree_path: The agent's worktree path
        project_path: The original project path
    
    Returns:
        Fixed briefing text
    """
    
    # Replace direct project paths with shared symlink paths
    fixed = briefing
    
    # Fix relative paths like ../../Tmux-Orchestrator
    fixed = re.sub(r'\.\./(\.\./)?(Tmux-Orchestrator|tmux-orchestrator)', 
                   '/home/clauderun/Tmux-Orchestrator', fixed)
    
    # Fix cd commands to project path
    fixed = re.sub(f'cd {re.escape(project_path)}(?![\w-])', 
                   f'cd ./shared/main-project || cd {project_path}', fixed)
    
    # Fix direct references to check shared directory first
    fixed = re.sub(f'cat {re.escape(project_path)}/(\S+)', 
                   f'cat ./shared/main-project/\\1 || cat {project_path}/\\1', fixed)
    
    # Add working directory verification at the beginning if not present
    if "pwd" not in fixed[:200] and role != 'orchestrator':
        verification = """
🔍 **First Command - Verify Your Location**:
```bash
pwd  # Should show your worktree directory
ls -la shared/  # Should show symlinks to main-project and other agents
```
If the shared directory doesn't exist, report to Orchestrator immediately.

"""
        # Find a good place to insert this - after role description
        insert_pos = fixed.find("Your responsibilities:")
        if insert_pos > 0:
            fixed = fixed[:insert_pos] + verification + fixed[insert_pos:]
    
    return fixed


def fix_initial_command_paths(commands: list, role: str) -> list:
    """
    Fix initial commands to be worktree-aware.
    
    Args:
        commands: List of initial commands
        role: The agent role
    
    Returns:
        Fixed list of commands
    """
    
    fixed_commands = []
    
    # Always start with pwd for non-orchestrator roles
    if role != 'orchestrator' and (not commands or commands[0] != 'pwd'):
        fixed_commands.append('pwd')
    
    for cmd in commands:
        # Skip if already fixed
        if 'shared/main-project' in cmd:
            fixed_commands.append(cmd)
            continue
            
        # Fix cd commands
        if cmd.startswith('cd ') and '/home/clauderun' in cmd and 'Tmux-Orchestrator' not in cmd:
            # This is a cd to project directory
            project_path = cmd[3:].strip()
            fixed_cmd = f'cd ./shared/main-project || cd {project_path}'
            fixed_commands.append(fixed_cmd)
        else:
            fixed_commands.append(cmd)
    
    return fixed_commands

#!/usr/bin/env python3
"""Setup git policy enforcement for new agent sessions"""

import argparse
import json
import os
import sys
from pathlib import Path

def setup_git_policy_config(agent_id: str, worktree_path: Path):
    """Setup git policy configuration for agent session"""
    
    # Create .claude directory if it doesn't exist
    claude_dir = worktree_path / '.claude'
    claude_dir.mkdir(exist_ok=True)
    
    # Extract agent role from agent_id for role-specific configuration
    session_name = agent_id.split(':')[0]
    if 'orchestrator' in session_name:
        agent_role = 'orchestrator'
        auto_commit_default = True  # Orchestrator can auto-commit
    elif 'project-manager' in session_name or 'pm' in session_name:
        agent_role = 'project-manager'
        auto_commit_default = False
    elif 'developer' in session_name or 'dev' in session_name:
        agent_role = 'developer'
        auto_commit_default = False
    elif 'tester' in session_name or 'test' in session_name:
        agent_role = 'tester'
        auto_commit_default = False
    else:
        agent_role = 'agent'
        auto_commit_default = False
    
    # Agent-specific policy configuration
    config = {
        'agent_id': agent_id,
        'agent_role': agent_role,
        'enforcement_level': 'warning',  # Start with warnings only
        'auto_commit_enabled': auto_commit_default,
        'pm_notification_required': agent_role != 'project-manager',  # PM doesn't notify self
        'local_remote_enforcement': 'strict',
        'github_push_allowlist': [
            'milestone', 'backup', 'release', 'external_review',
            'emergency', 'hotfix', 'critical'
        ],
        'commit_interval_minutes': 30,
        'grace_period_minutes': 5,
        'emergency_bypass_env': 'EMERGENCY_BYPASS',
        'policy_version': '1.0',
        'created_at': f"{Path.cwd()}"
    }
    
    config_path = claude_dir / 'git_policy_config.json'
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Git policy configuration created for {agent_id} (role: {agent_role})")
    return True

def check_git_repository(worktree_path: Path) -> bool:
    """Check if current directory is a git repository"""
    git_dir = worktree_path / '.git'
    if git_dir.exists():
        return True
    
    # Check if it's a worktree (has .git file pointing to git dir)
    git_file = worktree_path / '.git'
    if git_file.is_file():
        try:
            with open(git_file) as f:
                content = f.read().strip()
                if content.startswith('gitdir:'):
                    return True
        except:
            pass
    
    return False

def main():
    parser = argparse.ArgumentParser(description='Setup git policy enforcement')
    parser.add_argument('--agent', required=True, help='Agent ID (session:window)')
    parser.add_argument('--worktree-path', help='Explicit worktree path (defaults to cwd)')
    args = parser.parse_args()
    
    # Determine worktree path
    if args.worktree_path:
        worktree_path = Path(args.worktree_path)
    else:
        worktree_path = Path.cwd()
    
    # Verify we're in a git repository
    if not check_git_repository(worktree_path):
        print(f"⚠️  Not a git repository: {worktree_path} - git policy enforcement skipped")
        sys.exit(0)  # Exit successfully, just skip setup
    
    # Setup git policy configuration
    try:
        success = setup_git_policy_config(args.agent, worktree_path)
        if success:
            print(json.dumps({
                "status": "git_policy_setup_complete",
                "agent_id": args.agent,
                "worktree_path": str(worktree_path)
            }))
        else:
            print(json.dumps({
                "status": "git_policy_setup_failed",
                "agent_id": args.agent
            }))
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error setting up git policy for {args.agent}: {e}", file=sys.stderr)
        print(json.dumps({
            "status": "error",
            "agent_id": args.agent,
            "error": str(e)
        }))
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Git Policy Enforcement Module for Claude Hooks"""

import subprocess
import json
import os
import re
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from git_policy_config import GitPolicyConfig

class GitPolicyEnforcer:
    """Enforces git workflow policies defined in CLAUDE.md"""
    
    def __init__(self, worktree_path: str, agent_role: str):
        self.worktree_path = Path(worktree_path)
        self.agent_role = agent_role
        self.policy_config = GitPolicyConfig()
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load policy configuration using new configuration system"""
        # Get agent-specific configuration from centralized system
        agent_config = self.policy_config.get_agent_config(self.agent_role)
        
        # Convert to format expected by existing code (for backward compatibility)
        enforcement_level = self.policy_config.get_enforcement_level(self.agent_role)
        
        return {
            'enforcement_level': enforcement_level,
            'auto_commit_enabled': self.policy_config.is_auto_commit_enabled(self.agent_role),
            'pm_notification_required': self.policy_config.is_pm_notification_required(self.agent_role),
            'local_remote_enforcement': self.policy_config.get_policy_config(self.agent_role, 'local_remote_preference').get('enforcement_level', 'strict'),
            'github_push_allowlist': self.policy_config.get_github_allowlist(self.agent_role),
            'commit_interval_minutes': self.policy_config.get_commit_interval(self.agent_role),
            'grace_period_minutes': self.policy_config.get_grace_period(self.agent_role),
            'emergency_bypass_env': self.policy_config.get_emergency_bypass_env(),
            'significance_threshold': self.policy_config.get_significance_threshold(self.agent_role)
        }
    
    def check_commit_interval(self) -> Dict:
        """Check if agent is following 30-minute commit rule"""
        try:
            # Get time of last commit
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%ct'],
                cwd=self.worktree_path,
                capture_output=True, text=True,
                timeout=2
            )
            
            if result.returncode != 0:
                return {'overdue': False, 'minutes': 0, 'has_changes': False}  # No commits yet
            
            last_commit_time = datetime.fromtimestamp(int(result.stdout.strip()))
            minutes_since = (datetime.now() - last_commit_time).total_seconds() / 60
            
            # Check for uncommitted changes
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'], 
                cwd=self.worktree_path,
                capture_output=True, text=True,
                timeout=2
            )
            has_changes = bool(status_result.stdout.strip())
            
            interval_limit = self.config['commit_interval_minutes']
            
            return {
                'overdue': has_changes and minutes_since > interval_limit,
                'minutes': int(minutes_since),
                'has_changes': has_changes,
                'can_auto_commit': self.config['auto_commit_enabled'] and has_changes,
                'severity': 'critical' if minutes_since > 60 else 'high' if minutes_since > 45 else 'medium'
            }
            
        except Exception as e:
            return {'overdue': False, 'minutes': 0, 'error': str(e), 'has_changes': False}
    
    def detect_recent_github_operations(self) -> List[Dict]:
        """Detect recent GitHub operations that should use local remotes"""
        # For now, check if origin remote is GitHub and local remotes are available
        try:
            # Get origin URL
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=self.worktree_path,
                capture_output=True, text=True,
                timeout=2
            )
            
            if result.returncode != 0:
                return []
            
            origin_url = result.stdout.strip()
            is_github = 'github.com' in origin_url
            
            if not is_github:
                return []
            
            # Check if local remotes are available
            local_agents = self.get_available_agent_roles()
            
            if local_agents:
                return [{
                    'type': 'github_available_with_local_alternatives',
                    'alternatives': local_agents,
                    'performance_gain': '60-500x faster'
                }]
            
            return []
            
        except Exception:
            return []
    
    def detect_uncommitted_milestone_work(self) -> bool:
        """Detect significant uncommitted changes that need PM notification"""
        try:
            # Check diff for significant changes
            result = subprocess.run(
                ['git', 'diff', '--stat'],
                cwd=self.worktree_path,
                capture_output=True, text=True,
                timeout=3
            )
            
            if result.returncode != 0:
                return False
                
            diff_stats = result.stdout.strip()
            if not diff_stats:
                return False
            
            # Parse diff stats to determine significance
            lines = diff_stats.split('\n')
            if len(lines) < 2:
                return False
                
            # Look for summary line like "5 files changed, 150 insertions(+), 23 deletions(-)"
            summary_line = lines[-1]
            if 'file' in summary_line and 'changed' in summary_line:
                # Extract numbers
                numbers = re.findall(r'\d+', summary_line)
                if numbers:
                    files_changed = int(numbers[0])
                    insertions = int(numbers[1]) if len(numbers) > 1 else 0
                    
                    # Use configured significance thresholds
                    threshold = self.config['significance_threshold']
                    return (files_changed >= threshold['files_changed'] or 
                            insertions >= threshold['lines_changed'])
            
            return False
            
        except Exception:
            return False
    
    def get_available_agent_roles(self) -> List[str]:
        """Get list of agent roles with configured local remotes"""
        try:
            result = subprocess.run(
                ['git', 'remote'],
                cwd=self.worktree_path,
                capture_output=True, text=True,
                timeout=2
            )
            
            if result.returncode != 0:
                return []
            
            remotes = result.stdout.strip().split('\n')
            agent_roles = ['orchestrator', 'developer', 'tester', 'pm', 'project-manager']
            
            return [role for role in agent_roles if role in remotes]
            
        except Exception:
            return []
    
    def should_enforce_policy(self, operation: str, context: Dict = None) -> bool:
        """Determine if policy should be enforced based on context"""
        context = context or {}
        
        # Check if enforcement is globally enabled for this agent
        if not self.policy_config.is_enforcement_enabled(self.agent_role):
            return False
        
        # Emergency bypass
        if os.getenv(self.config['emergency_bypass_env']) == 'true':
            return False
        
        # Debugging context - relaxed policies (auto-bypass conditions)
        current_branch = self.get_current_branch()
        if current_branch and ('fix' in current_branch.lower() or 'debug' in current_branch.lower()):
            return False
        
        # Check for rebase/merge in progress
        git_dir = self.worktree_path / '.git'
        if (git_dir / 'REBASE_HEAD').exists() or (git_dir / 'MERGE_HEAD').exists():
            return False
        
        # PM override check (would need to be implemented via message queue)
        if context.get('pm_override_granted'):
            return False
        
        return True
    
    def get_current_branch(self) -> Optional[str]:
        """Get current git branch name"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.worktree_path,
                capture_output=True, text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            
            return None
            
        except Exception:
            return None
    
    def perform_auto_commit(self, message_suffix: str = "") -> bool:
        """Perform automatic commit if enabled and safe"""
        if not self.config['auto_commit_enabled']:
            return False
        
        try:
            # Add all changes
            subprocess.run(['git', 'add', '-A'], cwd=self.worktree_path, check=True, timeout=5)
            
            # Generate commit message
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            commit_msg = f"Auto-commit: Progress update ({timestamp})"
            if message_suffix:
                commit_msg += f" - {message_suffix}"
            
            # Commit
            subprocess.run(
                ['git', 'commit', '-m', commit_msg], 
                cwd=self.worktree_path, 
                check=True,
                timeout=5
            )
            
            return True
            
        except subprocess.CalledProcessError:
            return False
        except subprocess.TimeoutExpired:
            return False
    
    def check_github_push_authorization(self, remote: str, branch: str) -> Dict:
        """Check if GitHub push is authorized based on allowlist"""
        if remote != 'origin':
            return {'authorized': True, 'reason': 'not_github'}
        
        # Check if branch/commit has authorized tags
        try:
            # Get latest commit message
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%s'],
                cwd=self.worktree_path,
                capture_output=True, text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                commit_msg = result.stdout.strip().lower()
                
                # Check for allowlist keywords
                for keyword in self.config['github_push_allowlist']:
                    if keyword in commit_msg:
                        return {
                            'authorized': True, 
                            'reason': f'allowlist_keyword_{keyword}'
                        }
            
            # Check branch name for special patterns
            if any(pattern in branch.lower() for pattern in ['release', 'hotfix', 'milestone']):
                return {'authorized': True, 'reason': 'special_branch'}
            
            return {
                'authorized': False, 
                'reason': 'regular_coordination',
                'message': 'Use local remotes for regular coordination',
                'suggestions': [f"git push {role} {branch}" for role in self.get_available_agent_roles()]
            }
            
        except Exception as e:
            return {'authorized': False, 'reason': 'error', 'error': str(e)}
    
    def check_all_policies(self) -> Dict:
        """Check all git policies and return violations"""
        violations = []
        
        if not self.should_enforce_policy('all'):
            return {'violations': [], 'compliant': True, 'bypassed': True}
        
        # Check 30-minute commit rule
        commit_status = self.check_commit_interval()
        if commit_status['overdue']:
            violations.append({
                'type': 'commit_interval',
                'severity': commit_status['severity'],
                'message': f"⏰ COMMIT REQUIRED: {commit_status['minutes']} min overdue",
                'auto_fix_available': commit_status['can_auto_commit'],
                'details': commit_status
            })
        
        # Check for GitHub operations that should use local remotes
        github_ops = self.detect_recent_github_operations()
        if github_ops:
            for op in github_ops:
                violations.append({
                    'type': 'local_remote_preferred',
                    'severity': 'medium',
                    'message': f"💡 Use local remotes: {', '.join([f'git fetch {role}' for role in op['alternatives']])} ({op['performance_gain']})",
                    'details': op
                })
        
        # Check for uncommitted significant work
        if detect_uncommitted_milestone_work := self.detect_uncommitted_milestone_work():
            violations.append({
                'type': 'pm_notification_needed',
                'severity': 'medium',
                'message': "📝 Significant changes detected - commit and notify PM via: scm pm:0 \"message\"",
                'auto_fix_available': False
            })
        
        return {
            'violations': violations,
            'compliant': len(violations) == 0,
            'bypassed': False
        }

def handle_git_hook(hook_type: str, agent_role: str, worktree_path: str, **kwargs) -> int:
    """Handle git hook execution"""
    enforcer = GitPolicyEnforcer(worktree_path, agent_role)
    
    if hook_type == 'pre-push':
        remote = kwargs.get('remote', '')
        url = kwargs.get('url', '')
        
        auth_result = enforcer.check_github_push_authorization(remote, 'current')
        
        if not auth_result['authorized']:
            print(f"🚫 POLICY VIOLATION: {auth_result['message']}")
            if 'suggestions' in auth_result:
                print("✅ Suggested alternatives:")
                for suggestion in auth_result['suggestions']:
                    print(f"   {suggestion}")
            return 1
        else:
            print(f"✅ GitHub push authorized: {auth_result['reason']}")
            return 0
    
    elif hook_type == 'post-commit':
        # Check if PM notification is needed
        if enforcer.detect_uncommitted_milestone_work():
            print("📝 Consider notifying PM of significant changes: scm pm:0 \"Feature progress update\"")
        
        # Log successful commit for compliance tracking
        timestamp = datetime.now().isoformat()
        print(f"✅ Commit logged at {timestamp}")
        return 0
    
    return 0

def main():
    """Main entry point for command-line usage and git hooks"""
    parser = argparse.ArgumentParser(description='Git Policy Enforcement')
    parser.add_argument('--hook-type', choices=['pre-push', 'post-commit', 'check-all'])
    parser.add_argument('--agent', required=True, help='Agent role')
    parser.add_argument('--worktree-path', required=True, help='Worktree path')
    parser.add_argument('--remote', help='Git remote (for pre-push)')
    parser.add_argument('--url', help='Remote URL (for pre-push)')
    
    args = parser.parse_args()
    
    if args.hook_type in ['pre-push', 'post-commit']:
        result = handle_git_hook(
            args.hook_type,
            args.agent,
            args.worktree_path,
            remote=args.remote,
            url=args.url
        )
        sys.exit(result)
    
    elif args.hook_type == 'check-all':
        enforcer = GitPolicyEnforcer(args.worktree_path, args.agent)
        result = enforcer.check_all_policies()
        
        print(json.dumps(result, indent=2))
        sys.exit(0 if result['compliant'] else 1)

if __name__ == "__main__":
    main()
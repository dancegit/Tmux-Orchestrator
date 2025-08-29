# Git Policy Enforcement via Claude Hooks - Implementation Specification

## Overview

This specification defines the implementation of sophisticated git workflow policy enforcement using the existing Claude hooks infrastructure in the Tmux Orchestrator system. The goal is to enforce CLAUDE.md git policies through real-time guidance, automated compliance checking, and progressive enforcement mechanisms.

## Background

The Tmux Orchestrator uses a local-first git workflow with agent-specific worktrees that provides 60-500x performance improvements over GitHub-heavy workflows. However, policy compliance requires active enforcement to ensure agents follow the sophisticated workflow patterns defined in CLAUDE.md.

## Current Infrastructure

### Existing Claude Hooks System
- **PostToolUse**: Triggers after every tool execution
- **Stop**: Executes when Claude becomes idle
- **PostCompact**: Handles context restoration after compaction  
- **SessionStart**: Initializes new agent sessions
- **SessionEnd**: Cleans up agent resources

### Existing Components
- `claude_hooks/check_queue.py` - Main hook for message delivery
- `claude_hooks/tmux_message_sender.py` - Smart message delivery system
- `setup_agent_hooks.py` - Automatic hook configuration  
- `monitoring/git_activity_monitor.py` - Git compliance monitoring
- `git_coordinator.py` - Local remote preference system

## Git Policies to Enforce

### 1. Local-First Workflow Policy
- **Rule**: Use local remotes (`git fetch <agent_role>`) instead of GitHub for regular coordination
- **Rationale**: 60-500x performance improvement over network operations
- **Exceptions**: Milestones, backups, external review, project completion, failure recovery

### 2. 30-Minute Commit Rule  
- **Rule**: All agents must commit every 30 minutes when uncommitted changes exist
- **Rationale**: Ensures progress tracking and prevents work loss
- **Auto-correction**: Optional auto-commit for willing agents

### 3. PM Notification Requirement
- **Rule**: Notify Project Manager after significant commits via message queue
- **Implementation**: Use `scm pm:0 "message"` command
- **Trigger**: Non-trivial commits, feature completions, milestone work

### 4. GitHub Usage Restrictions
- **Rule**: Push to GitHub only for specific scenarios
- **Allowed**: milestone, backup, release, external_review tags
- **Blocked**: Regular coordination, WIP commits, test iterations

### 5. Rebase Workflow Enforcement  
- **Rule**: Enforce fast-forward merges through rebase workflow
- **Implementation**: Pre-merge hooks to verify rebase compliance
- **Fallback**: Block non-fast-forward merges with guidance

## Implementation Architecture

### Phase 1: Foundation Enhancement (Week 1)

#### 1.1 Enhanced PostToolUse Hook

**File**: `claude_hooks/check_queue.py`

Add git policy checking to existing hook:

```python
def check_git_policy_compliance(agent_id: str) -> dict:
    """Check git workflow policy compliance after tool use"""
    
    violations = []
    
    # Check 30-minute commit rule
    commit_status = check_commit_interval()
    if commit_status['overdue']:
        violations.append({
            'type': 'commit_interval',
            'severity': 'high' if commit_status['minutes'] > 60 else 'medium',
            'message': f"⏰ COMMIT REQUIRED: {commit_status['minutes']} min overdue",
            'auto_fix': commit_status['minutes'] > 60 and AUTO_COMMIT_ENABLED
        })
    
    # Check for GitHub operations that should use local remotes
    github_ops = detect_recent_github_operations()
    if github_ops:
        violations.append({
            'type': 'local_remote_preferred',
            'severity': 'medium',
            'message': "💡 Use local remotes: git fetch <agent_role> (60-500x faster)",
            'suggestions': [f"git fetch {role}" for role in get_available_agent_roles()]
        })
    
    # Check for uncommitted significant work
    if detect_uncommitted_milestone_work():
        violations.append({
            'type': 'pm_notification_needed', 
            'severity': 'medium',
            'message': "📝 Significant changes detected - commit and notify PM"
        })
    
    return {
        'violations': violations,
        'compliant': len(violations) == 0
    }
```

#### 1.2 Git Policy Enforcer Module

**File**: `claude_hooks/git_policy_enforcer.py` (NEW)

Core policy enforcement logic:

```python
#!/usr/bin/env python3
"""Git Policy Enforcement Module for Claude Hooks"""

import subprocess
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class GitPolicyEnforcer:
    """Enforces git workflow policies defined in CLAUDE.md"""
    
    def __init__(self, worktree_path: str, agent_role: str):
        self.worktree_path = Path(worktree_path)
        self.agent_role = agent_role
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load policy configuration"""
        config_path = self.worktree_path / '.claude' / 'git_policy_config.json'
        
        default_config = {
            'enforcement_level': 'warning',  # warning, blocking, auto_correct
            'auto_commit_enabled': False,
            'pm_notification_required': True,
            'local_remote_enforcement': 'strict',  # strict, warning, disabled
            'github_push_allowlist': ['milestone', 'backup', 'release', 'external_review'],
            'commit_interval_minutes': 30,
            'emergency_bypass_env': 'EMERGENCY_BYPASS'
        }
        
        if config_path.exists():
            with open(config_path) as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def check_commit_interval(self) -> Dict:
        """Check if agent is following 30-minute commit rule"""
        try:
            # Get time of last commit
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%ct'],
                cwd=self.worktree_path,
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                return {'overdue': False, 'minutes': 0}  # No commits yet
            
            last_commit_time = datetime.fromtimestamp(int(result.stdout.strip()))
            minutes_since = (datetime.now() - last_commit_time).total_seconds() / 60
            
            # Check for uncommitted changes
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'], 
                cwd=self.worktree_path,
                capture_output=True, text=True
            )
            has_changes = bool(status_result.stdout.strip())
            
            interval_limit = self.config['commit_interval_minutes']
            
            return {
                'overdue': has_changes and minutes_since > interval_limit,
                'minutes': int(minutes_since),
                'has_changes': has_changes,
                'can_auto_commit': self.config['auto_commit_enabled'] and has_changes
            }
            
        except Exception as e:
            return {'overdue': False, 'minutes': 0, 'error': str(e)}
    
    def detect_recent_github_operations(self) -> List[Dict]:
        """Detect recent GitHub operations that should use local remotes"""
        # This would analyze recent command history or git reflog
        # Implementation depends on how we track recent operations
        return []
    
    def detect_uncommitted_milestone_work(self) -> bool:
        """Detect significant uncommitted changes that need PM notification"""
        try:
            # Check diff for significant changes
            result = subprocess.run(
                ['git', 'diff', '--stat'],
                cwd=self.worktree_path,
                capture_output=True, text=True
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
                    
                    # Significant if multiple files or many changes
                    return files_changed >= 3 or insertions >= 50
            
            return False
            
        except Exception:
            return False
    
    def get_available_agent_roles(self) -> List[str]:
        """Get list of agent roles with configured local remotes"""
        try:
            result = subprocess.run(
                ['git', 'remote'],
                cwd=self.worktree_path,
                capture_output=True, text=True
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
        
        # Emergency bypass
        if os.getenv(self.config['emergency_bypass_env']) == 'true':
            return False
        
        # Debugging context - relaxed policies
        if context.get('debugging') or 'fix' in context.get('branch', ''):
            return False
        
        # PM override
        if context.get('pm_override_granted'):
            return False
        
        return True
    
    def perform_auto_commit(self, message_suffix: str = "") -> bool:
        """Perform automatic commit if enabled and safe"""
        if not self.config['auto_commit_enabled']:
            return False
        
        try:
            # Add all changes
            subprocess.run(['git', 'add', '-A'], cwd=self.worktree_path, check=True)
            
            # Generate commit message
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            commit_msg = f"Auto-commit: Progress update ({timestamp})"
            if message_suffix:
                commit_msg += f" - {message_suffix}"
            
            # Commit
            subprocess.run(
                ['git', 'commit', '-m', commit_msg], 
                cwd=self.worktree_path, 
                check=True
            )
            
            return True
            
        except subprocess.CalledProcessError:
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
                capture_output=True, text=True
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
                'message': 'Use local remotes for regular coordination'
            }
            
        except Exception as e:
            return {'authorized': False, 'reason': 'error', 'error': str(e)}
```

#### 1.3 Enhanced Hook Settings

**File**: `claude_hooks/settings.json`

Add git operation triggers:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command", 
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue.py --agent ${TMUX_SESSION_NAME}:${TMUX_WINDOW_INDEX}",
            "timeout": 10000,
            "description": "Check message queue and git policy compliance"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue.py --agent ${TMUX_SESSION_NAME}:${TMUX_WINDOW_INDEX} --on-idle",
            "timeout": 5000,
            "description": "Final compliance check when idle"
          }
        ]
      }
    ],
    "PostCompact": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/check_queue.py --agent ${TMUX_SESSION_NAME}:${TMUX_WINDOW_INDEX} --rebrief",
            "timeout": 8000,
            "description": "Rebrief agent and check compliance"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/setup_git_policy_hooks.py --agent ${TMUX_SESSION_NAME}:${TMUX_WINDOW_INDEX}",
            "timeout": 5000,
            "description": "Setup git policy enforcement for new session"
          }
        ]
      }
    ]
  }
}
```

### Phase 2: Worktree Git Hooks (Week 2)

#### 2.1 Enhanced Agent Setup

**File**: `setup_agent_hooks.py` (ENHANCE)

Add git hooks installation:

```python
def setup_worktree_git_hooks(worktree_path: Path, agent_role: str, orchestrator_path: Path):
    """Install git hooks in agent worktrees for policy enforcement"""
    
    hooks_dir = worktree_path / '.git' / 'hooks' 
    hooks_dir.mkdir(exist_ok=True)
    
    # Pre-push hook to enforce local-first and GitHub restrictions
    pre_push_content = f'''#!/bin/bash
# Git Policy Enforcement: Pre-push hook
# Enforces local-first workflow and GitHub usage restrictions

remote="$1"
url="$2"

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
    
    # Post-commit hook for PM notification and compliance logging
    post_commit_content = f'''#!/bin/bash
# Git Policy Enforcement: Post-commit hook  
# Handles PM notifications and compliance logging

python3 "{orchestrator_path}/claude_hooks/git_policy_enforcer.py" \\
    --hook-type post-commit \\
    --agent {agent_role} \\
    --worktree-path "{worktree_path}"

# Continue regardless of hook result
exit 0
'''
    
    post_commit_hook = hooks_dir / 'post-commit'
    post_commit_hook.write_text(post_commit_content)
    post_commit_hook.chmod(0o755)
    
    # Pre-merge-commit hook for rebase enforcement
    pre_merge_content = f'''#!/bin/bash
# Git Policy Enforcement: Pre-merge-commit hook
# Enforces rebase workflow (fast-forward merges only)

# Check if this is a fast-forward merge (rebased)
if git merge-base --is-ancestor HEAD MERGE_HEAD 2>/dev/null; then
    echo "✅ Fast-forward merge (rebased) - proceeding"
    exit 0
else
    echo "🚫 POLICY VIOLATION: Non-fast-forward merge detected"
    echo "Required: Rebase your branch first: git rebase pm/integration" 
    echo "This enforces the rebase workflow defined in CLAUDE.md"
    exit 1
fi
'''
    
    pre_merge_hook = hooks_dir / 'pre-merge-commit'
    pre_merge_hook.write_text(pre_merge_content)
    pre_merge_hook.chmod(0o755)
```

#### 2.2 Git Policy Configuration

**File**: `claude_hooks/setup_git_policy_hooks.py` (NEW)

Session-specific git policy setup:

```python
#!/usr/bin/env python3
"""Setup git policy enforcement for new agent sessions"""

import argparse
import json
import os
from pathlib import Path

def setup_git_policy_config(agent_id: str, worktree_path: Path):
    """Setup git policy configuration for agent session"""
    
    # Create .claude directory if it doesn't exist
    claude_dir = worktree_path / '.claude'
    claude_dir.mkdir(exist_ok=True)
    
    # Agent-specific policy configuration
    config = {
        'agent_id': agent_id,
        'enforcement_level': 'warning',  # Start with warnings
        'auto_commit_enabled': False,    # User opt-in required
        'pm_notification_required': True,
        'local_remote_enforcement': 'strict',
        'github_push_allowlist': [
            'milestone', 'backup', 'release', 'external_review',
            'emergency', 'hotfix', 'critical'
        ],
        'commit_interval_minutes': 30,
        'emergency_bypass_env': 'EMERGENCY_BYPASS',
        'policy_version': '1.0'
    }
    
    config_path = claude_dir / 'git_policy_config.json'
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Git policy configuration created for {agent_id}")

def main():
    parser = argparse.ArgumentParser(description='Setup git policy enforcement')
    parser.add_argument('--agent', required=True, help='Agent ID (session:window)')
    args = parser.parse_args()
    
    # Determine worktree path from agent ID
    worktree_path = Path.cwd()  # Assumes running in worktree directory
    
    setup_git_policy_config(args.agent, worktree_path)

if __name__ == "__main__":
    main()
```

### Phase 3: Progressive Enforcement (Week 3)

#### 3.1 Configuration Management

**File**: `orchestrator_config.yaml` (ENHANCE)

Add git policy section:

```yaml
# Git Policy Enforcement Configuration
git_policy_enforcement:
  enabled: true
  
  # Global enforcement levels
  default_enforcement_level: warning  # warning, blocking, auto_correct
  
  # Policy-specific settings
  policies:
    commit_interval:
      enabled: true
      interval_minutes: 30
      grace_period_minutes: 5
      auto_commit_enabled: false  # Global default
      blocking_threshold_minutes: 60
    
    local_remote_preference:
      enabled: true
      enforcement: strict  # strict, warning, disabled
      performance_reminder: true
    
    pm_notification:
      enabled: true
      required_for_significant_commits: true
      auto_notify: false
    
    github_usage_restrictions:
      enabled: true
      allowlist: [milestone, backup, release, external_review, emergency]
      block_unauthorized: false  # Start with warnings
    
    rebase_workflow:
      enabled: true
      enforce_fast_forward: true
      block_merge_commits: false  # Start with warnings

  # Agent-specific overrides
  agent_overrides:
    orchestrator:
      auto_commit_enabled: true  # Orchestrator can auto-commit
    project-manager:
      pm_notification.required_for_significant_commits: false  # PM doesn't notify self
  
  # Rollout configuration  
  rollout:
    phase: 1  # 1=warning, 2=auto_correct, 3=blocking
    gradual_rollout_enabled: true
    agents_in_blocking_mode: []  # Agents ready for full enforcement
```

#### 3.2 Enhanced Compliance Monitoring Integration

**File**: `monitoring/compliance_rules.json` (ENHANCE)

Add git policy rules:

```json
{
  "rules": [
    {
      "id": "git-policy-001",
      "name": "30-minute commit compliance",
      "description": "Agent must commit within 30 minutes when changes exist",
      "category": "git_workflow",
      "severity": "high",
      "pattern": "commit_interval_violation",
      "threshold": "30 minutes",
      "escalation": {
        "60_minutes": "critical",
        "90_minutes": "blocking"
      }
    },
    {
      "id": "git-policy-002", 
      "name": "Local remote preference",
      "description": "Use local remotes instead of GitHub for coordination",
      "category": "git_workflow",
      "severity": "medium",
      "pattern": "github_operation_when_local_available",
      "performance_impact": "60-500x slower than local"
    },
    {
      "id": "git-policy-003",
      "name": "PM notification requirement",
      "description": "Notify PM after significant commits",
      "category": "communication",
      "severity": "medium", 
      "pattern": "significant_commit_without_pm_notification"
    },
    {
      "id": "git-policy-004",
      "name": "GitHub usage restrictions",
      "description": "GitHub pushes only for milestones, backups, reviews",
      "category": "git_workflow",
      "severity": "high",
      "pattern": "unauthorized_github_push"
    },
    {
      "id": "git-policy-005",
      "name": "Rebase workflow compliance",
      "description": "Use rebase workflow for clean merge history",
      "category": "git_workflow", 
      "severity": "medium",
      "pattern": "non_fast_forward_merge"
    }
  ]
}
```

## Integration Points

### 1. Message Queue System
Git policy violations and reminders use the existing message queue:
- `enqueue_message(agent_id, policy_message, priority=50)`
- Integration with `tmux_message_sender.py` for delivery

### 2. Compliance Monitoring System  
Policy violations feed into existing monitoring:
- `monitoring/git_activity_monitor.py` enhanced with policy checking
- Real-time violation tracking and escalation

### 3. Event Bus Integration
```python
# Real-time policy enforcement notifications  
event_bus.publish('git_policy_violation', {
    'agent': agent_id,
    'policy': 'local_remote_required', 
    'severity': 'high',
    'auto_fix_available': True
})
```

## Success Metrics

### Compliance Tracking
- **30-minute commit adherence**: Target >95% compliance
- **Local remote usage**: Target <10% GitHub operations for coordination
- **PM notification rate**: Target >90% for significant commits  
- **Policy violation reduction**: Target 80% reduction over 4 weeks

### Performance Metrics
- **Git operation speed**: Maintain 60-500x advantage for local operations
- **Hook execution time**: <100ms average per policy check
- **System stability**: No impact on core orchestrator functionality

## Rollout Strategy

### Week 1: Warning Phase
- Deploy enhanced hooks with educational messages only
- Monitor compliance rates and identify common violation patterns
- Gather agent feedback on policy clarity

### Week 2: Auto-correction Phase
- Enable auto-commit for willing agents  
- Deploy worktree git hooks with blocking for unauthorized operations
- Begin PM auto-notification for significant commits

### Week 3: Selective Blocking
- Enable blocking enforcement for agents ready for full compliance
- Maintain warning-only mode for agents still adapting
- Monitor for false positives and edge cases

### Week 4: Full Enforcement
- Deploy blocking enforcement across all agents
- Maintain emergency bypass mechanisms
- Continuous monitoring and refinement

## Error Handling and Edge Cases

### Emergency Bypass
- `EMERGENCY_BYPASS=true` environment variable
- PM override capability for specific agents
- Automatic bypass during debugging contexts

### False Positive Mitigation
- Context-aware enforcement (debugging, fixes, emergencies)
- Configurable thresholds and grace periods
- Manual override mechanisms

### Performance Safeguards
- Timeout protection for git operations (1-second max)
- Fallback behavior on git command failures
- Lightweight status checking with caching

## Maintenance and Evolution

### Configuration Updates
- Centralized policy configuration in `orchestrator_config.yaml`
- Agent-specific overrides supported
- Runtime configuration updates without restart

### Policy Evolution
- Version tracking for policy changes
- Backward compatibility for existing worktrees
- Gradual migration paths for policy updates

### Monitoring and Debugging
- Comprehensive logging of policy violations and actions
- Debug mode with detailed policy checking output
- Integration with existing orchestrator monitoring systems

This specification provides the foundation for sophisticated git workflow policy enforcement that leverages the existing Claude hooks infrastructure while providing the flexibility and progressive enforcement needed for successful adoption.
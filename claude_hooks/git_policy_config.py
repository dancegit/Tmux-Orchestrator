#!/usr/bin/env python3
"""Git Policy Configuration Manager"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class GitPolicyConfig:
    """Manages git policy configuration with agent-specific overrides"""
    
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            # Default to git_policy_config.yaml in orchestrator directory
            config_path = Path(__file__).parent.parent / 'git_policy_config.yaml'
        
        self.config_path = config_path
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            if not self.config_path.exists():
                logger.warning(f"Git policy config not found at {self.config_path}, using defaults")
                return self.get_default_config()
            
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            logger.info(f"Loaded git policy configuration from {self.config_path}")
            return config
            
        except Exception as e:
            logger.error(f"Error loading git policy config: {e}")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if file is missing"""
        return {
            'enforcement': {
                'enabled': True,
                'default_level': 'warning',
                'rollout': {'phase': 1, 'gradual_rollout_enabled': True}
            },
            'policies': {
                'commit_interval': {
                    'enabled': True,
                    'interval_minutes': 30,
                    'grace_period_minutes': 5,
                    'auto_commit': {'enabled': False}
                },
                'local_remote_preference': {
                    'enabled': True,
                    'enforcement_level': 'strict'
                },
                'pm_notification': {
                    'enabled': True,
                    'required_for_significant_commits': True
                },
                'github_restrictions': {
                    'enabled': True,
                    'enforcement_level': 'warning',
                    'allowlist': ['milestone', 'backup', 'release', 'external_review']
                },
                'rebase_workflow': {
                    'enabled': True,
                    'enforce_fast_forward': True,
                    'enforcement_level': 'warning'
                }
            },
            'agent_overrides': {},
            'emergency': {
                'bypass_env_var': 'EMERGENCY_BYPASS'
            }
        }
    
    def get_agent_config(self, agent_role: str) -> Dict[str, Any]:
        """Get effective configuration for a specific agent role"""
        base_config = self.config.copy()
        
        # Apply agent-specific overrides
        overrides = self.config.get('agent_overrides', {}).get(agent_role, {})
        
        # Deep merge overrides into base config
        agent_config = self._deep_merge(base_config, {'policies': overrides})
        
        return agent_config
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def is_enforcement_enabled(self, agent_role: str = None) -> bool:
        """Check if git policy enforcement is enabled globally and for agent"""
        if not self.config.get('enforcement', {}).get('enabled', True):
            return False
            
        # Check rollout phase for gradual deployment
        rollout = self.config.get('enforcement', {}).get('rollout', {})
        if rollout.get('gradual_rollout_enabled', False):
            phase = rollout.get('phase', 1)
            
            if phase == 1:  # Warning phase - all agents
                return True
            elif phase == 2:  # Auto-correct phase - selected agents
                auto_correct_agents = rollout.get('auto_correct_mode', [])
                return agent_role in auto_correct_agents
            elif phase >= 3:  # Blocking phase - selected agents
                blocking_agents = rollout.get('blocking_mode', [])
                return agent_role in blocking_agents
                
        return True
    
    def get_enforcement_level(self, agent_role: str, policy_name: str = None) -> str:
        """Get enforcement level for agent and optional specific policy"""
        agent_config = self.get_agent_config(agent_role)
        
        # Check rollout phase first
        rollout = self.config.get('enforcement', {}).get('rollout', {})
        if rollout.get('gradual_rollout_enabled', False):
            phase = rollout.get('phase', 1)
            
            auto_correct_agents = rollout.get('auto_correct_mode', [])
            blocking_agents = rollout.get('blocking_mode', [])
            
            if agent_role in blocking_agents:
                base_level = 'blocking'
            elif agent_role in auto_correct_agents:
                base_level = 'auto_correct'
            else:
                base_level = 'warning'
        else:
            base_level = self.config.get('enforcement', {}).get('default_level', 'warning')
        
        # Policy-specific enforcement level can override
        if policy_name:
            policy_config = agent_config.get('policies', {}).get(policy_name, {})
            policy_level = policy_config.get('enforcement_level')
            if policy_level:
                return policy_level
                
        return base_level
    
    def get_policy_config(self, agent_role: str, policy_name: str) -> Dict[str, Any]:
        """Get configuration for a specific policy and agent"""
        agent_config = self.get_agent_config(agent_role)
        policy_config = agent_config.get('policies', {}).get(policy_name, {})
        
        # Add enforcement level if not specified
        if 'enforcement_level' not in policy_config:
            policy_config['enforcement_level'] = self.get_enforcement_level(agent_role, policy_name)
            
        return policy_config
    
    def is_auto_commit_enabled(self, agent_role: str) -> bool:
        """Check if auto-commit is enabled for agent"""
        policy_config = self.get_policy_config(agent_role, 'commit_interval')
        return policy_config.get('auto_commit', {}).get('enabled', False)
    
    def get_commit_interval(self, agent_role: str) -> int:
        """Get commit interval in minutes for agent"""
        policy_config = self.get_policy_config(agent_role, 'commit_interval')
        return policy_config.get('interval_minutes', 30)
    
    def get_grace_period(self, agent_role: str) -> int:
        """Get grace period in minutes for agent"""
        policy_config = self.get_policy_config(agent_role, 'commit_interval')
        return policy_config.get('grace_period_minutes', 5)
    
    def get_github_allowlist(self, agent_role: str) -> list:
        """Get GitHub push allowlist for agent"""
        policy_config = self.get_policy_config(agent_role, 'github_restrictions')
        return policy_config.get('allowlist', ['milestone', 'backup', 'release', 'external_review'])
    
    def is_pm_notification_required(self, agent_role: str) -> bool:
        """Check if PM notification is required for agent"""
        policy_config = self.get_policy_config(agent_role, 'pm_notification')
        return policy_config.get('required_for_significant_commits', True)
    
    def get_significance_threshold(self, agent_role: str) -> Dict[str, int]:
        """Get significance thresholds for PM notification"""
        policy_config = self.get_policy_config(agent_role, 'pm_notification')
        return policy_config.get('significance_threshold', {
            'files_changed': 3,
            'lines_changed': 50
        })
    
    def get_emergency_bypass_env(self) -> str:
        """Get environment variable name for emergency bypass"""
        return self.config.get('emergency', {}).get('bypass_env_var', 'EMERGENCY_BYPASS')
    
    def update_rollout_phase(self, phase: int):
        """Update rollout phase for gradual deployment"""
        if 'enforcement' not in self.config:
            self.config['enforcement'] = {}
        if 'rollout' not in self.config['enforcement']:
            self.config['enforcement']['rollout'] = {}
            
        self.config['enforcement']['rollout']['phase'] = phase
        self.save_config()
        logger.info(f"Updated rollout phase to {phase}")
    
    def add_agent_to_enforcement_level(self, agent_role: str, level: str):
        """Add agent to specific enforcement level"""
        rollout = self.config.get('enforcement', {}).get('rollout', {})
        
        level_key = f"{level}_mode"
        if level_key not in rollout:
            rollout[level_key] = []
            
        if agent_role not in rollout[level_key]:
            rollout[level_key].append(agent_role)
            self.save_config()
            logger.info(f"Added {agent_role} to {level} enforcement mode")
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            logger.info(f"Saved git policy configuration to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving git policy config: {e}")

def main():
    """CLI for configuration management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Git Policy Configuration Manager")
    parser.add_argument('--config-path', type=Path, help='Path to config file')
    parser.add_argument('--agent-role', help='Agent role to query')
    parser.add_argument('--policy', help='Policy name to query')
    parser.add_argument('--show-config', action='store_true', help='Show configuration')
    parser.add_argument('--update-phase', type=int, help='Update rollout phase')
    parser.add_argument('--add-agent', help='Add agent to enforcement level')
    parser.add_argument('--level', help='Enforcement level for --add-agent')
    
    args = parser.parse_args()
    
    config = GitPolicyConfig(args.config_path)
    
    if args.show_config:
        if args.agent_role:
            agent_config = config.get_agent_config(args.agent_role)
            print(f"Configuration for {args.agent_role}:")
            print(json.dumps(agent_config, indent=2))
        else:
            print("Global configuration:")
            print(json.dumps(config.config, indent=2))
    
    elif args.update_phase:
        config.update_rollout_phase(args.update_phase)
        print(f"Updated rollout phase to {args.update_phase}")
    
    elif args.add_agent and args.level:
        config.add_agent_to_enforcement_level(args.add_agent, args.level)
        print(f"Added {args.add_agent} to {args.level} enforcement mode")
    
    elif args.agent_role:
        print(f"Agent: {args.agent_role}")
        print(f"Enforcement enabled: {config.is_enforcement_enabled(args.agent_role)}")
        print(f"Enforcement level: {config.get_enforcement_level(args.agent_role)}")
        print(f"Auto-commit enabled: {config.is_auto_commit_enabled(args.agent_role)}")
        print(f"Commit interval: {config.get_commit_interval(args.agent_role)} minutes")
        
        if args.policy:
            policy_config = config.get_policy_config(args.agent_role, args.policy)
            print(f"\nPolicy '{args.policy}' configuration:")
            print(json.dumps(policy_config, indent=2))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
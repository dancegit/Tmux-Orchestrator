#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///
"""
Dynamic Team Composition for Tmux Orchestrator
Detects project type and composes appropriate agent teams
"""

import os
import yaml
import json
import glob
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class DynamicTeamComposer:
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = templates_dir
        self.templates = self._load_all_templates()
        
    def _load_all_templates(self) -> Dict[str, dict]:
        """Load all YAML templates from templates directory"""
        templates = {}
        template_files = glob.glob(os.path.join(self.templates_dir, "*.yaml"))
        
        for template_file in template_files:
            template_name = Path(template_file).stem
            with open(template_file, 'r') as f:
                templates[template_name] = yaml.safe_load(f)
        
        return templates
    
    def _resolve_inheritance(self, template_name: str) -> dict:
        """Resolve template inheritance and merge configurations"""
        if template_name not in self.templates:
            raise ValueError(f"Template {template_name} not found")
        
        template = self.templates[template_name]
        
        # If template inherits from another, merge them
        if 'inherits' in template and template['inherits']:
            base_template = self._resolve_inheritance(template['inherits'])
            # Merge roles
            base_roles = base_template.get('roles', [])
            child_roles = template.get('roles', [])
            template['roles'] = base_roles + [r for r in child_roles if r not in base_roles]
            
            # Merge config
            base_config = base_template.get('config', {})
            child_config = template.get('config', {})
            template['config'] = {**base_config, **child_config}
        
        return template
    
    def detect_project_type(self, project_dir: str) -> Tuple[str, float]:
        """
        Detect project type based on file indicators
        Returns: (project_type, confidence_score)
        """
        scores = {}
        
        # Check each template's indicators
        for template_name, template in self.templates.items():
            if template_name == 'base':
                continue
                
            score = 0
            indicators = template.get('indicators', [])
            
            for indicator in indicators:
                # Check if indicator exists in project
                if '*' in indicator:
                    # It's a glob pattern
                    matches = glob.glob(os.path.join(project_dir, '**', indicator), recursive=True)
                    score += len(matches) * 20  # Increased weight
                else:
                    # It's a specific file/directory
                    if os.path.exists(os.path.join(project_dir, indicator)):
                        score += 40  # Increased weight
            
            scores[template_name] = score
        
        # Find the best match
        if not scores or max(scores.values()) == 0:
            return 'code_project', 0.5  # Default fallback
        
        best_match = max(scores, key=scores.get)
        confidence = min(scores[best_match] / 100, 1.0)  # Normalize to 0-1
        
        return best_match, confidence
    
    def compose_team(self, project_dir: str, 
                    force_type: Optional[str] = None,
                    include_optional: bool = False,
                    custom_roles: Optional[List[str]] = None) -> Dict[str, any]:
        """
        Compose a team for the given project
        
        Args:
            project_dir: Path to the project directory
            force_type: Force a specific project type (override detection)
            include_optional: Whether to include optional roles
            custom_roles: Custom list of roles to use (overrides everything)
            
        Returns:
            Dictionary with team composition details
        """
        if custom_roles:
            # Use custom roles if provided
            return {
                'project_type': 'custom',
                'confidence': 1.0,
                'roles': custom_roles,
                'config': self.templates.get('base', {}).get('config', {}),
                'reasoning': 'Custom role selection'
            }
        
        # Detect or use forced project type
        if force_type:
            project_type = force_type
            confidence = 1.0
            reasoning = f"Forced project type: {project_type}"
        else:
            project_type, confidence = self.detect_project_type(project_dir)
            reasoning = f"Detected based on project files (confidence: {confidence:.1%})"
        
        # Get the resolved template
        template = self._resolve_inheritance(project_type)
        
        # Build the team
        roles = template.get('roles', [])
        
        # Add optional roles if requested or high confidence
        if include_optional or confidence > 0.8:
            optional_roles = template.get('optional_roles', [])
            # Could add logic here to selectively include based on project analysis
            roles.extend(optional_roles[:2])  # Add up to 2 optional roles
        
        return {
            'project_type': project_type,
            'confidence': confidence,
            'roles': roles,
            'config': template.get('config', {}),
            'reasoning': reasoning
        }
    
    def analyze_project_complexity(self, project_dir: str) -> Dict[str, any]:
        """Analyze project complexity to help with team sizing"""
        stats = {
            'file_count': 0,
            'code_files': 0,
            'config_files': 0,
            'test_files': 0,
            'doc_files': 0,
            'total_lines': 0,
            'has_tests': False,
            'has_ci': False,
            'has_docker': False,
            'complexity_score': 0
        }
        
        code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rs', '.cpp', '.c', '.rb'}
        config_extensions = {'.yaml', '.yml', '.json', '.toml', '.ini', '.conf'}
        
        for root, dirs, files in os.walk(project_dir):
            # Skip hidden and common ignore directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__']]
            
            for file in files:
                stats['file_count'] += 1
                file_path = os.path.join(root, file)
                ext = Path(file).suffix.lower()
                
                if ext in code_extensions:
                    stats['code_files'] += 1
                elif ext in config_extensions:
                    stats['config_files'] += 1
                elif 'test' in file.lower():
                    stats['test_files'] += 1
                    stats['has_tests'] = True
                elif ext in ['.md', '.rst', '.txt']:
                    stats['doc_files'] += 1
                
                # Check for CI/CD
                if file in ['.gitlab-ci.yml', '.github/workflows', 'Jenkinsfile']:
                    stats['has_ci'] = True
                
                # Check for Docker
                if file in ['Dockerfile', 'docker-compose.yml', 'docker-compose.yaml']:
                    stats['has_docker'] = True
        
        # Calculate complexity score
        stats['complexity_score'] = (
            min(stats['code_files'] / 10, 10) +  # Up to 10 points for code files
            min(stats['file_count'] / 100, 5) +   # Up to 5 points for total files
            (2 if stats['has_tests'] else 0) +
            (2 if stats['has_ci'] else 0) +
            (1 if stats['has_docker'] else 0)
        )
        
        return stats
    
    def recommend_team_size(self, project_dir: str, subscription_plan: str = 'max5') -> Dict[str, any]:
        """Recommend team size based on project complexity and subscription plan"""
        complexity = self.analyze_project_complexity(project_dir)
        team_comp = self.compose_team(project_dir)
        
        # Plan limits
        plan_limits = {
            'pro': 3,
            'max5': 5,
            'max20': 8,
            'console': 10
        }
        
        max_agents = plan_limits.get(subscription_plan, 5)
        
        # Size recommendations based on complexity
        if complexity['complexity_score'] < 5:
            size = 'small'
            recommended_agents = min(3, max_agents)
        elif complexity['complexity_score'] < 12:
            size = 'medium'
            recommended_agents = min(5, max_agents)
        else:
            size = 'large'
            recommended_agents = min(8, max_agents)
        
        # Adjust roles based on limit
        all_roles = team_comp['roles']
        if len(all_roles) > recommended_agents:
            # Prioritize core roles
            core_roles = ['orchestrator', 'project_manager', 'developer', 'tester']
            selected_roles = [r for r in all_roles if r in core_roles][:recommended_agents]
            
            # Add other roles if space
            other_roles = [r for r in all_roles if r not in core_roles]
            remaining_slots = recommended_agents - len(selected_roles)
            selected_roles.extend(other_roles[:remaining_slots])
        else:
            selected_roles = all_roles
        
        return {
            'size': size,
            'recommended_agents': recommended_agents,
            'selected_roles': selected_roles,
            'full_team': all_roles,
            'complexity': complexity,
            'reasoning': f"Based on {complexity['code_files']} code files and complexity score of {complexity['complexity_score']:.1f}"
        }


def main():
    """CLI interface for testing dynamic team composition"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Dynamic team composition for Tmux Orchestrator')
    parser.add_argument('project_dir', help='Project directory to analyze')
    parser.add_argument('--force-type', help='Force a specific project type')
    parser.add_argument('--include-optional', action='store_true', help='Include optional roles')
    parser.add_argument('--custom-roles', nargs='+', help='Custom roles list')
    parser.add_argument('--plan', default='max5', choices=['pro', 'max5', 'max20', 'console'],
                       help='Subscription plan for team sizing')
    parser.add_argument('--analyze', action='store_true', help='Show detailed project analysis')
    
    args = parser.parse_args()
    
    composer = DynamicTeamComposer()
    
    if args.analyze:
        # Show detailed analysis
        complexity = composer.analyze_project_complexity(args.project_dir)
        print(f"\nProject Analysis for: {args.project_dir}")
        print("=" * 50)
        for key, value in complexity.items():
            print(f"{key:20}: {value}")
    
    # Get team composition
    team = composer.compose_team(
        args.project_dir,
        force_type=args.force_type,
        include_optional=args.include_optional,
        custom_roles=args.custom_roles
    )
    
    print(f"\nTeam Composition")
    print("=" * 50)
    print(f"Project Type: {team['project_type']}")
    print(f"Confidence: {team['confidence']:.1%}")
    print(f"Reasoning: {team['reasoning']}")
    print(f"\nRoles ({len(team['roles'])}):")
    for role in team['roles']:
        print(f"  - {role}")
    
    # Get size recommendation
    recommendation = composer.recommend_team_size(args.project_dir, args.plan)
    print(f"\nTeam Size Recommendation ({args.plan} plan)")
    print("=" * 50)
    print(f"Size: {recommendation['size']}")
    print(f"Recommended Agents: {recommendation['recommended_agents']}")
    print(f"Selected Roles: {', '.join(recommendation['selected_roles'])}")
    if len(recommendation['full_team']) > len(recommendation['selected_roles']):
        excluded = set(recommendation['full_team']) - set(recommendation['selected_roles'])
        print(f"Excluded Roles: {', '.join(excluded)}")
    print(f"Reasoning: {recommendation['reasoning']}")


if __name__ == "__main__":
    main()
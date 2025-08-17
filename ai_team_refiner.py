#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///
"""
AI Team Refinement for Tmux Orchestrator
Uses Claude to refine team composition based on project analysis
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import argparse
import tempfile

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from dynamic_team import DynamicTeamComposer


class AITeamRefiner:
    def __init__(self, orchestrator_path: Path = None):
        self.orchestrator_path = orchestrator_path or Path.cwd()
        self.dynamic_composer = DynamicTeamComposer()
        
    def analyze_project_context(self, project_path: str) -> Dict[str, Any]:
        """Gather detailed project context for AI analysis"""
        project_path = Path(project_path)
        context = {
            'file_structure': {},
            'key_files': {},
            'dependencies': {},
            'complexity_indicators': {},
            'existing_infrastructure': {}
        }
        
        # Analyze file structure
        file_counts = {}
        total_lines = 0
        
        for root, dirs, files in os.walk(project_path):
            # Skip common ignore directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv']]
            
            for file in files[:100]:  # Limit to prevent overwhelming
                ext = Path(file).suffix.lower()
                file_counts[ext] = file_counts.get(ext, 0) + 1
                
                # Sample key files
                if file in ['README.md', 'package.json', 'requirements.txt', 'docker-compose.yml', 'Dockerfile']:
                    file_path = Path(root) / file
                    try:
                        content = file_path.read_text()[:500]  # First 500 chars
                        context['key_files'][file] = content
                    except:
                        pass
        
        context['file_structure'] = file_counts
        
        # Check for specific infrastructure indicators
        indicators = {
            'has_docker': (project_path / 'Dockerfile').exists() or (project_path / 'docker-compose.yml').exists(),
            'has_kubernetes': any((project_path / p).exists() for p in ['k8s/', 'kubernetes/', 'helm/']),
            'has_terraform': any(project_path.glob('*.tf')),
            'has_ci_cd': any((project_path / p).exists() for p in ['.github/workflows', '.gitlab-ci.yml', 'Jenkinsfile']),
            'has_monitoring': any(project_path.glob('**/prometheus.yml')) or any(project_path.glob('**/grafana/')),
            'has_database': any(f in context['key_files'] for f in ['docker-compose.yml', 'database.yml', 'db.config']),
            'has_security_config': any((project_path / p).exists() for p in ['security/', '.security', 'apparmor/']),
            'has_load_balancer': any(project_path.glob('**/nginx.conf')) or any(project_path.glob('**/haproxy.cfg'))
        }
        
        context['existing_infrastructure'] = indicators
        
        # Complexity scoring
        context['complexity_indicators'] = {
            'file_diversity': len(file_counts),
            'has_microservices': len(list(project_path.glob('*/Dockerfile'))) > 1,
            'deployment_complexity': sum(1 for v in indicators.values() if v),
            'estimated_scale': 'large' if sum(file_counts.values()) > 1000 else 'medium' if sum(file_counts.values()) > 100 else 'small'
        }
        
        return context
    
    def create_refinement_prompt(self, 
                               project_path: str,
                               initial_team: List[str],
                               project_context: Dict[str, Any],
                               spec_content: Optional[str] = None) -> str:
        """Create a prompt for Claude to refine the team composition"""
        
        prompt = f"""You are an expert in software team composition and DevOps. 
Analyze this project and refine the team composition for optimal results.

PROJECT PATH: {project_path}

INITIAL TEAM SUGGESTION: {', '.join(initial_team)}

PROJECT CONTEXT:
- File Types: {json.dumps(project_context['file_structure'], indent=2)}
- Infrastructure: {json.dumps(project_context['existing_infrastructure'], indent=2)}
- Complexity: {json.dumps(project_context['complexity_indicators'], indent=2)}

KEY FILES DETECTED:
{chr(10).join(f"{k}: {v[:200]}..." for k, v in list(project_context['key_files'].items())[:5])}

"""

        if spec_content:
            prompt += f"\nPROJECT SPECIFICATION:\n{spec_content[:1000]}...\n"

        prompt += """
AVAILABLE ROLES:
1. orchestrator - Overall coordination (always included)
2. project_manager - Quality and git workflow coordination
3. developer - Implementation
4. tester - Test creation and quality assurance
5. testrunner - Test execution and automation
6. devops - CI/CD and deployment
7. researcher - MCP tools and best practices research
8. documentation_writer - Technical documentation
9. code_reviewer - Security and code quality
10. logtracker - Real-time monitoring
11. sysadmin - System administration
12. securityops - Security hardening
13. networkops - Network configuration
14. monitoringops - Monitoring infrastructure
15. databaseops - Database management

TASK: Based on the project analysis, recommend:
1. Which roles to ADD to the initial team (if any)
2. Which roles to REMOVE from the initial team (if any)
3. Brief justification for each change

Consider:
- Project complexity and scale
- Existing infrastructure needs
- Security requirements
- Deployment complexity
- Team size constraints (5-8 agents optimal)

Respond in JSON format:
{
  "add_roles": ["role1", "role2"],
  "remove_roles": ["role3"],
  "justifications": {
    "role1": "Reason for adding",
    "role3": "Reason for removing"
  },
  "refined_team": ["final", "team", "list"],
  "team_size_assessment": "appropriate|too_large|too_small"
}
"""
        
        return prompt
    
    def call_claude_api(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Claude API for refinement (requires claude CLI)"""
        try:
            # Create a temporary file with the prompt
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                temp_file = f.name
            
            # Call claude CLI
            result = subprocess.run(
                ['claude', '--no-color', '--json', '<', temp_file],
                shell=True,
                capture_output=True,
                text=True
            )
            
            os.unlink(temp_file)
            
            if result.returncode == 0 and result.stdout:
                # Try to extract JSON from response
                response = result.stdout
                
                # Find JSON in response
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    return json.loads(json_match.group())
            
            return None
            
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return None
    
    def refine_team(self, 
                   project_path: str,
                   initial_team: List[str],
                   spec_path: Optional[str] = None,
                   use_mock: bool = False) -> Dict[str, Any]:
        """Refine team composition using AI analysis"""
        
        # Gather project context
        print("Analyzing project context...")
        context = self.analyze_project_context(project_path)
        
        # Read spec if provided
        spec_content = None
        if spec_path and Path(spec_path).exists():
            spec_content = Path(spec_path).read_text()[:2000]
        
        # Create refinement prompt
        prompt = self.create_refinement_prompt(
            project_path,
            initial_team,
            context,
            spec_content
        )
        
        if use_mock:
            # Mock response for testing
            refinement = self.get_mock_refinement(context, initial_team)
        else:
            # Call Claude API
            print("Consulting Claude for team refinement...")
            refinement = self.call_claude_api(prompt)
            
            if not refinement:
                print("Failed to get AI refinement, using heuristic fallback")
                refinement = self.get_heuristic_refinement(context, initial_team)
        
        # Validate and apply refinement
        final_team = self.apply_refinement(initial_team, refinement)
        
        return {
            'initial_team': initial_team,
            'refinement': refinement,
            'final_team': final_team,
            'context': context
        }
    
    def get_mock_refinement(self, context: Dict[str, Any], initial_team: List[str]) -> Dict[str, Any]:
        """Mock refinement for testing"""
        add_roles = []
        remove_roles = []
        justifications = {}
        
        # Add roles based on context
        if context['existing_infrastructure']['has_kubernetes'] and 'devops' not in initial_team:
            add_roles.append('devops')
            justifications['devops'] = "Kubernetes configuration detected"
        
        if context['existing_infrastructure']['has_security_config'] and 'securityops' not in initial_team:
            add_roles.append('securityops')
            justifications['securityops'] = "Security configuration files found"
        
        if context['complexity_indicators']['deployment_complexity'] > 3 and 'sysadmin' not in initial_team:
            add_roles.append('sysadmin')
            justifications['sysadmin'] = "High deployment complexity detected"
        
        # Remove roles if team too large
        current_size = len(initial_team) + len(add_roles)
        if current_size > 7:
            if 'documentation_writer' in initial_team:
                remove_roles.append('documentation_writer')
                justifications['documentation_writer'] = "Team size optimization"
        
        refined_team = [r for r in initial_team if r not in remove_roles] + add_roles
        
        return {
            'add_roles': add_roles,
            'remove_roles': remove_roles,
            'justifications': justifications,
            'refined_team': refined_team,
            'team_size_assessment': 'appropriate' if 5 <= len(refined_team) <= 8 else 'too_large' if len(refined_team) > 8 else 'too_small'
        }
    
    def get_heuristic_refinement(self, context: Dict[str, Any], initial_team: List[str]) -> Dict[str, Any]:
        """Heuristic-based refinement as fallback"""
        add_roles = []
        remove_roles = []
        justifications = {}
        
        infra = context['existing_infrastructure']
        complexity = context['complexity_indicators']
        
        # Infrastructure-based additions
        if infra['has_docker'] or infra['has_kubernetes']:
            if 'devops' not in initial_team:
                add_roles.append('devops')
                justifications['devops'] = "Container infrastructure detected"
        
        if infra['has_monitoring']:
            if 'monitoringops' not in initial_team and complexity['deployment_complexity'] > 2:
                add_roles.append('monitoringops')
                justifications['monitoringops'] = "Existing monitoring infrastructure needs management"
        
        if infra['has_database'] and 'databaseops' not in initial_team:
            if complexity['estimated_scale'] in ['medium', 'large']:
                add_roles.append('databaseops')
                justifications['databaseops'] = "Database infrastructure requires dedicated management"
        
        if infra['has_load_balancer'] and 'networkops' not in initial_team:
            add_roles.append('networkops')
            justifications['networkops'] = "Load balancer configuration detected"
        
        # Security considerations
        if complexity['deployment_complexity'] > 3 and 'securityops' not in initial_team:
            add_roles.append('securityops')
            justifications['securityops'] = "Complex deployment requires security oversight"
        
        # Team size optimization
        current_size = len(initial_team) + len(add_roles)
        
        if current_size > 8:
            # Prioritize removals
            optional_roles = ['documentation_writer', 'code_reviewer', 'researcher']
            for role in optional_roles:
                if role in initial_team and current_size > 8:
                    remove_roles.append(role)
                    justifications[role] = "Team size optimization - role can be distributed"
                    current_size -= 1
        
        refined_team = [r for r in initial_team if r not in remove_roles] + add_roles
        
        return {
            'add_roles': add_roles,
            'remove_roles': remove_roles,
            'justifications': justifications,
            'refined_team': refined_team,
            'team_size_assessment': 'appropriate' if 5 <= len(refined_team) <= 8 else 'too_large' if len(refined_team) > 8 else 'too_small'
        }
    
    def apply_refinement(self, initial_team: List[str], refinement: Dict[str, Any]) -> List[str]:
        """Apply refinement suggestions to create final team"""
        if not refinement:
            return initial_team
        
        # Start with initial team
        final_team = initial_team.copy()
        
        # Remove roles
        for role in refinement.get('remove_roles', []):
            if role in final_team:
                final_team.remove(role)
        
        # Add roles
        for role in refinement.get('add_roles', []):
            if role not in final_team:
                final_team.append(role)
        
        # Ensure orchestrator is always present
        if 'orchestrator' not in final_team:
            final_team.insert(0, 'orchestrator')
        
        return final_team


def main():
    """CLI interface for AI team refinement"""
    parser = argparse.ArgumentParser(description='AI-powered team refinement for Tmux Orchestrator')
    parser.add_argument('project', help='Path to the project')
    parser.add_argument('--spec', help='Path to project specification')
    parser.add_argument('--initial-team', nargs='+', help='Initial team composition')
    parser.add_argument('--mock', action='store_true', help='Use mock refinement (no API call)')
    parser.add_argument('--json', action='store_true', help='Output JSON format')
    
    args = parser.parse_args()
    
    refiner = AITeamRefiner()
    
    # Get initial team if not provided
    if args.initial_team:
        initial_team = args.initial_team
    else:
        # Use dynamic composer to get initial team
        composer = DynamicTeamComposer()
        team_comp = composer.compose_team(args.project)
        initial_team = team_comp['roles']
    
    # Refine the team
    result = refiner.refine_team(
        args.project,
        initial_team,
        spec_path=args.spec,
        use_mock=args.mock
    )
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\nAI Team Refinement Results")
        print("=" * 50)
        print(f"Initial Team ({len(result['initial_team'])}): {', '.join(result['initial_team'])}")
        
        if result['refinement']:
            print(f"\nRefinement Suggestions:")
            if result['refinement'].get('add_roles'):
                print(f"  Add: {', '.join(result['refinement']['add_roles'])}")
            if result['refinement'].get('remove_roles'):
                print(f"  Remove: {', '.join(result['refinement']['remove_roles'])}")
            
            print(f"\nJustifications:")
            for role, reason in result['refinement'].get('justifications', {}).items():
                print(f"  {role}: {reason}")
            
            print(f"\nTeam Size Assessment: {result['refinement'].get('team_size_assessment', 'unknown')}")
        
        print(f"\nFinal Team ({len(result['final_team'])}): {', '.join(result['final_team'])}")
        
        # Show context summary
        print(f"\nProject Analysis:")
        print(f"  File Types: {len(result['context']['file_structure'])}")
        print(f"  Deployment Complexity: {result['context']['complexity_indicators']['deployment_complexity']}/8")
        print(f"  Scale: {result['context']['complexity_indicators']['estimated_scale']}")


if __name__ == "__main__":
    main()
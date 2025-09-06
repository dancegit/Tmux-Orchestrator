"""
CIIS Specification Parser Module

Converts CIIS (Continuous Improvement Intelligence System) batch specifications 
into the format expected by the Tmux Orchestrator briefing system.

This module addresses the compatibility issue where CIIS batch specs use a 
different JSON structure than the ProjectSpec format expected by BriefingSystem.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .briefing_system import ProjectSpec


@dataclass
class CIISTask:
    """Individual task from a CIIS batch specification."""
    id: str
    type: str
    slice_id: str
    changes: str
    validation_tests: List[str]
    priority: int


@dataclass
class CIISProject:
    """CIIS project metadata."""
    name: str
    environment: str


@dataclass
class CIISBatchSpec:
    """Complete CIIS batch specification."""
    project: CIISProject
    tasks: List[CIISTask]
    settings: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class CIISSpecParser:
    """
    Parser for converting CIIS batch specifications to Tmux Orchestrator format.
    
    This enables automatic briefing generation for CIIS projects by transforming
    the CIIS JSON structure into the ProjectSpec format expected by BriefingSystem.
    """
    
    def __init__(self, project_resolver_path: Optional[Path] = None):
        """
        Initialize CIIS specification parser.
        
        Args:
            project_resolver_path: Optional path to ProjectResolver for repository mapping
        """
        self.project_resolver = None
        if project_resolver_path:
            try:
                import sys
                sys.path.insert(0, str(project_resolver_path.parent))
                from project_resolver import ProjectResolver
                self.project_resolver = ProjectResolver()
            except ImportError:
                pass
    
    def parse_ciis_spec(self, spec_file_path: str) -> Optional[ProjectSpec]:
        """
        Parse a CIIS batch specification file into ProjectSpec format.
        
        Args:
            spec_file_path: Path to the CIIS JSON specification file
            
        Returns:
            ProjectSpec: Converted specification, or None if parsing failed
        """
        try:
            spec_path = Path(spec_file_path)
            if not spec_path.exists():
                print(f"[ERROR] CIIS spec file not found: {spec_file_path}")
                return None
            
            with open(spec_path, 'r') as f:
                ciis_data = json.load(f)
            
            # Parse CIIS structure
            ciis_spec = self._parse_ciis_json(ciis_data)
            if not ciis_spec:
                return None
            
            # Convert to ProjectSpec format
            return self._convert_to_project_spec(ciis_spec, spec_path)
            
        except Exception as e:
            print(f"[ERROR] Failed to parse CIIS specification: {e}")
            return None
    
    def _parse_ciis_json(self, ciis_data: Dict[str, Any]) -> Optional[CIISBatchSpec]:
        """Parse CIIS JSON data into structured format."""
        try:
            # Parse project metadata
            project_data = ciis_data.get('project', {})
            project = CIISProject(
                name=project_data.get('name', ''),
                environment=project_data.get('environment', 'test')
            )
            
            # Parse tasks
            tasks = []
            for task_data in ciis_data.get('tasks', []):
                task = CIISTask(
                    id=task_data.get('id', ''),
                    type=task_data.get('type', ''),
                    slice_id=task_data.get('slice_id', ''),
                    changes=task_data.get('changes', ''),
                    validation_tests=task_data.get('validation_tests', []),
                    priority=task_data.get('priority', 50)
                )
                tasks.append(task)
            
            return CIISBatchSpec(
                project=project,
                tasks=tasks,
                settings=ciis_data.get('settings'),
                metadata=ciis_data.get('metadata')
            )
            
        except Exception as e:
            print(f"[ERROR] Failed to parse CIIS JSON structure: {e}")
            return None
    
    def _convert_to_project_spec(self, ciis_spec: CIISBatchSpec, spec_path: Path) -> ProjectSpec:
        """Convert CIIS specification to ProjectSpec format."""
        
        # Determine project path using ProjectResolver if available
        project_path = self._resolve_project_path(spec_path)
        
        # Extract slice IDs for technology detection
        slice_ids = [task.slice_id for task in ciis_spec.tasks]
        main_tech = self._detect_technologies(slice_ids)
        
        # Generate comprehensive description
        description = self._generate_description(ciis_spec)
        
        # Determine project type
        project_type = self._determine_project_type(ciis_spec)
        
        return ProjectSpec(
            name=ciis_spec.project.name,
            path=project_path,
            type=project_type,
            main_tech=main_tech,
            description=description
        )
    
    def _resolve_project_path(self, spec_path: Path) -> str:
        """Resolve the actual project path for the CIIS specification."""
        if self.project_resolver:
            try:
                resolved_path = self.project_resolver.resolve_project_path(str(spec_path))
                return str(resolved_path[0])  # ProjectResolver returns (path, slice_id)
            except Exception:
                pass
        
        # Fallback: use spec file's parent directory
        return str(spec_path.parent)
    
    def _detect_technologies(self, slice_ids: List[str]) -> List[str]:
        """Detect technologies based on slice IDs."""
        tech_mapping = {
            'elliott_wave': ['python', 'modal', 'trading'],
            'options': ['python', 'options-trading', 'analytics'],
            'reporting': ['python', 'reporting', 'data-analysis'],
            'rollback_mechanism': ['deployment', 'reliability'],
            'enhanced_health_checks': ['monitoring', 'health-checks'],
            'error_reporting': ['logging', 'monitoring'],
            'deployment_validation': ['deployment', 'validation']
        }
        
        detected_tech = set()
        for slice_id in slice_ids:
            if slice_id in tech_mapping:
                detected_tech.update(tech_mapping[slice_id])
        
        return list(detected_tech) if detected_tech else ['python', 'signalmatrix']
    
    def _determine_project_type(self, ciis_spec: CIISBatchSpec) -> str:
        """Determine the project type from CIIS specification."""
        # Check if it's a reliability/infrastructure improvement
        reliability_keywords = ['rollback', 'health', 'error', 'deployment', 'validation']
        
        for task in ciis_spec.tasks:
            task_text = f"{task.slice_id} {task.changes}".lower()
            if any(keyword in task_text for keyword in reliability_keywords):
                return 'system_reliability'
        
        # Check if it's trading-related
        trading_keywords = ['elliott', 'wave', 'options', 'trading', 'signal']
        for task in ciis_spec.tasks:
            task_text = f"{task.slice_id} {task.changes}".lower()
            if any(keyword in task_text for keyword in trading_keywords):
                return 'trading_system'
        
        # Default to generic system improvement
        return 'system_improvement'
    
    def _generate_description(self, ciis_spec: CIISBatchSpec) -> str:
        """Generate comprehensive description from CIIS tasks."""
        title = ciis_spec.metadata.get('title', 'CIIS Improvement Project') if ciis_spec.metadata else 'CIIS Improvement Project'
        
        task_summaries = []
        for task in ciis_spec.tasks:
            task_summaries.append(f"- {task.slice_id}: {task.changes}")
        
        description = f"""
{title}

Environment: {ciis_spec.project.environment}

Implementation Tasks:
{chr(10).join(task_summaries)}

Validation Requirements:
- All changes must pass validation tests
- Focus on reliability and system stability
- Ensure compatibility with existing SignalMatrix infrastructure
        """.strip()
        
        return description


def create_project_spec_from_ciis(ciis_spec_path: str, project_resolver_path: Optional[str] = None) -> Optional[ProjectSpec]:
    """
    Convenience function to create ProjectSpec from CIIS specification.
    
    Args:
        ciis_spec_path: Path to CIIS JSON specification file
        project_resolver_path: Optional path to ProjectResolver module
        
    Returns:
        ProjectSpec: Converted specification for briefing system
    """
    resolver_path = Path(project_resolver_path) if project_resolver_path else None
    parser = CIISSpecParser(resolver_path)
    return parser.parse_ciis_spec(ciis_spec_path)


# Example usage and testing
if __name__ == "__main__":
    # Test with a sample CIIS specification
    test_spec = {
        "project": {
            "name": "ciis_proposal_test",
            "environment": "test"
        },
        "tasks": [
            {
                "id": "test_rollback_mechanism",
                "type": "slice_update",
                "slice_id": "rollback_mechanism",
                "changes": "Add snapshot creation before deployment",
                "validation_tests": ["Test rollback functionality"],
                "priority": 68
            }
        ],
        "metadata": {
            "title": "Enhanced Error Handling Test"
        }
    }
    
    # Create test file
    test_file = Path("/tmp/test_ciis_spec.json")
    with open(test_file, 'w') as f:
        json.dump(test_spec, f, indent=2)
    
    # Test parser
    parser = CIISSpecParser()
    project_spec = parser.parse_ciis_spec(str(test_file))
    
    if project_spec:
        print("✅ CIIS Parser Test Successful!")
        print(f"Name: {project_spec.name}")
        print(f"Type: {project_spec.type}")
        print(f"Tech: {project_spec.main_tech}")
        print(f"Description: {project_spec.description[:100]}...")
    else:
        print("❌ CIIS Parser Test Failed")
    
    # Clean up
    test_file.unlink()
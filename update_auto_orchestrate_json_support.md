---
project:
  name: auto_orchestrate_json_support
  path: /home/clauderun/Tmux-Orchestrator
  type: tool_enhancement
  main_tech: [python, json, argparse]

implementation_plan:
  phases:
    - name: JSON Schema Definition
      duration_hours: 1.0
      tasks: [Define JSON schema for spec-to-project mapping, Add Pydantic model for JSON validation]
    - name: Parser Enhancement
      duration_hours: 2.0
      tasks: [Update argparse to accept .json files, Implement JSON loader in auto_orchestrate.py]
    - name: Batch Processing Update
      duration_hours: 2.0
      tasks: [Modify batch logic to handle project-specific paths, Update PathManager for dynamic project paths]
    - name: Testing and Documentation
      duration_hours: 1.0
      tasks: [Add unit tests for JSON parsing, Update README with JSON examples]
  total_estimated_hours: 6.0

roles:
  Developer:
    responsibilities: [Implement JSON support in auto_orchestrate.py, Update argument parsing logic]
    check_in_interval: 20
    initial_commands: [cd /home/clauderun/Tmux-Orchestrator, git checkout -b json-spec-support]
  Tester:
    responsibilities: [Test JSON file parsing, Validate batch processing with multiple projects]
    check_in_interval: 30
    initial_commands: [python -m pytest tests/]
  Orchestrator:
    responsibilities: [Coordinate implementation, Ensure backward compatibility]
    check_in_interval: 30
    initial_commands: [./auto_orchestrate.py --help]

git_workflow:
  parent_branch: main
  branch_name: feature/json-spec-support
  commit_interval: 20
  pr_title: Add JSON spec mapping support to auto_orchestrate.py

success_criteria:
  - auto_orchestrate.py accepts .json files as input
  - JSON files can map multiple specs to different project directories
  - Backward compatibility maintained for direct .md spec files
  - Batch processing works correctly with mixed project locations
  - Clear error messages for invalid JSON format

project_size:
  size: small
  estimated_loc: 400
  complexity: medium
---

# Auto Orchestrate JSON Support Specification

## Overview
Enhance `auto_orchestrate.py` to accept JSON files that map specification files to their target project directories. This allows for centralized spec management while supporting multiple project locations in a single batch run.

## JSON Schema Design
```json
{
  "version": "1.0",
  "specs": [
    {
      "spec_file": "path/to/spec.md",
      "project_directory": "/absolute/path/to/project",
      "enabled": true,
      "tags": ["integration", "backend"],
      "new_project": false
    }
  ],
  "batch_config": {
    "parallel": false,
    "continue_on_error": true,
    "log_level": "INFO"
  }
}
```

## Implementation Details

### 1. Add JSON Model
```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class SpecMapping(BaseModel):
    spec_file: str = Field(..., description="Path to the .md spec file")
    project_directory: str = Field(..., description="Target project directory")
    enabled: bool = Field(default=True, description="Whether to process this spec")
    tags: Optional[List[str]] = Field(default=[], description="Tags for filtering")
    new_project: bool = Field(default=False, description="Whether to create a new project (true) or use existing (false)")

class BatchConfig(BaseModel):
    parallel: bool = Field(default=False, description="Run specs in parallel")
    continue_on_error: bool = Field(default=True, description="Continue if a spec fails")
    log_level: str = Field(default="INFO", description="Logging level")

class SpecMappingFile(BaseModel):
    version: str = Field(default="1.0", description="Schema version")
    specs: List[SpecMapping] = Field(..., description="List of spec mappings")
    batch_config: Optional[BatchConfig] = Field(default=BatchConfig(), description="Batch processing config")
```

### 2. Update Argument Parser
```python
def setup_parser():
    parser = argparse.ArgumentParser(description='Auto-orchestrate implementation specs')
    spec_group = parser.add_mutually_exclusive_group(required=True)
    spec_group.add_argument('--spec', type=str, help='Path to spec file (.md or .json)')
    spec_group.add_argument('--spec-dir', type=str, help='Directory containing spec files')
    
    # Add JSON-specific options
    parser.add_argument('--filter-tags', nargs='+', help='Filter specs by tags (JSON mode only)')
    parser.add_argument('--validate-json', action='store_true', help='Validate JSON without processing')
```

### 3. JSON Loading Logic
```python
def load_json_specs(json_path: str, filter_tags: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """Load spec mappings from JSON file.
    
    Returns:
        List of tuples: (spec_file_path, project_directory)
    """
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    mapping_file = SpecMappingFile(**data)
    
    specs = []
    for spec in mapping_file.specs:
        if not spec.enabled:
            continue
            
        if filter_tags and not any(tag in spec.tags for tag in filter_tags):
            continue
            
        # Resolve relative paths
        spec_path = Path(spec.spec_file)
        if not spec_path.is_absolute():
            spec_path = Path(json_path).parent / spec_path
            
        specs.append((str(spec_path), spec.project_directory))
    
    return specs, mapping_file.batch_config
```

### 4. Update Main Processing
```python
def main():
    args = parser.parse_args()
    
    if args.spec and args.spec.endswith('.json'):
        # JSON mode
        specs, batch_config = load_json_specs(args.spec, args.filter_tags)
        
        if args.validate_json:
            print(f"Valid JSON with {len(specs)} enabled specs")
            return
            
        for spec_path, project_dir in specs:
            # Override project path for this spec
            process_spec(spec_path, project_override=project_dir, batch_config=batch_config)
    else:
        # Traditional mode (backward compatible)
        process_spec(args.spec)
```

## Testing Strategy
1. Unit tests for JSON parsing and validation
2. Integration tests with sample JSON files
3. Backward compatibility tests with existing .md specs
4. Error handling tests for malformed JSON

## Documentation Updates
- Add JSON examples to README
- Create JSON schema documentation
- Add migration guide from direct specs to JSON mapping
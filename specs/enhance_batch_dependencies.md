---
project:
  name: enhance_batch_dependencies
  path: /home/clauderun/Tmux-Orchestrator
  type: tool_enhancement
  main_tech: [python, pydantic, json, dependency_resolution]

implementation_plan:
  phases:
    - name: Extend Pydantic Models
      duration_hours: 2.0
      tasks: [Add priority and dependencies fields to SpecMapping model, Update SpecMappingFile validation, Add dependency resolution algorithms, Create priority-based sorting logic]
    - name: Dependency Resolution Engine
      duration_hours: 4.0
      tasks: [Implement topological sort for dependency ordering, Add circular dependency detection, Create dependency validation logic, Add priority override capabilities]
    - name: Enhanced Batch Processing
      duration_hours: 3.0
      tasks: [Update load_json_specs function to handle new fields, Integrate dependency resolution into batch execution, Add verbose logging for dependency chains, Update CLI validation output]
    - name: Testing and Documentation
      duration_hours: 2.0
      tasks: [Create test cases for dependency scenarios, Update help documentation, Add example JSON files, Test circular dependency detection]
  total_estimated_hours: 11.0

existing_implementation_status:
  current_models: "✅ Basic SpecMapping model exists with spec_file, project_directory, enabled, tags, new_project"
  current_ordering: "✅ Sequential processing based on array order in JSON"
  current_validation: "✅ JSON validation and path resolution working"
  missing_features:
    - "Priority-based ordering within dependency groups"
    - "Explicit dependency declarations with validation"
    - "Circular dependency detection and prevention"
    - "Dependency chain visualization and logging"

roles:
  Orchestrator:
    responsibilities: [Design dependency resolution architecture, Coordinate model enhancements, Ensure backward compatibility]
    check_in_interval: 30
    initial_commands: [cd /home/clauderun/Tmux-Orchestrator, python --version, ls -la auto_orchestrate.py]
  Developer:
    responsibilities: [Implement Pydantic model extensions, Code dependency resolution algorithms, Update batch processing logic]
    check_in_interval: 20
    initial_commands: [cd /home/clauderun/Tmux-Orchestrator, grep -n "class SpecMapping" auto_orchestrate.py, python -c "import pydantic; print(pydantic.__version__)"]
  Tester:
    responsibilities: [Create comprehensive test scenarios, Test circular dependency detection, Validate backward compatibility]
    check_in_interval: 25
    initial_commands: [cd /home/clauderun/Tmux-Orchestrator, ls -la specs/, python -m pytest --version 2>/dev/null || echo "pytest not available"]

git_workflow:
  parent_branch: main
  branch_name: feature-batch-dependencies
  commit_interval: 30
  pr_title: "Enhance auto_orchestrate.py with priority and dependency support"

success_criteria:
  - SpecMapping model supports priority (int) and dependencies (List[str]) fields
  - Dependency resolution correctly orders specs based on dependencies
  - Priority ordering works within dependency groups
  - Circular dependency detection prevents infinite loops
  - Backward compatibility maintained for existing JSON files
  - Comprehensive validation and error messages for invalid dependencies
  - Documentation updated with new field descriptions and examples

technical_specification:
  new_fields:
    priority:
      type: "Optional[int]"
      default: 0
      description: "Execution priority within dependency group (0=highest, higher numbers = lower priority)"
      usage: "Used to order specs when multiple specs have no dependencies or same dependency level"
    dependencies:
      type: "Optional[List[str]]"
      default: "[]"
      description: "List of spec names that must complete before this spec runs"
      usage: "Spec names should match other specs in the same batch (without .md extension)"
      validation: "All dependencies must exist in the same batch file"

  dependency_resolution_algorithm: |
    1. Parse all specs and extract dependency relationships
    2. Validate all dependencies exist within the batch
    3. Detect circular dependencies using depth-first search
    4. Perform topological sort to determine execution order
    5. Within same dependency level, sort by priority (0 = highest priority)
    6. Return ordered list or error if circular dependencies found

  backward_compatibility: |
    - New fields are optional with sensible defaults
    - Existing JSON files continue to work without modification
    - If no dependencies specified, falls back to array order
    - Priority field ignored if dependencies not used

implementation_details:
  pydantic_model_update: |
    class SpecMapping(BaseModel):
        spec_file: str = Field(..., description="Path to the .md spec file")
        project_directory: str = Field(..., description="Target project directory")
        enabled: bool = Field(default=True, description="Whether to process this spec")
        tags: Optional[List[str]] = Field(default=[], description="Tags for filtering")
        new_project: bool = Field(default=False, description="Whether to create a new project")
        priority: Optional[int] = Field(default=0, description="Execution priority (0=highest)")
        dependencies: Optional[List[str]] = Field(default=[], description="Spec dependencies")

  dependency_resolver_class: |
    class DependencyResolver:
        def __init__(self, specs: List[SpecMapping]):
            self.specs = specs
            self.spec_map = {self._get_spec_name(s.spec_file): s for s in specs}
        
        def _get_spec_name(self, spec_file: str) -> str:
            # Extract spec name from file path (without .md extension)
            return Path(spec_file).stem
        
        def resolve_order(self) -> List[SpecMapping]:
            # 1. Validate dependencies
            self._validate_dependencies()
            
            # 2. Check for circular dependencies
            if self._has_circular_dependencies():
                raise ValueError("Circular dependencies detected")
            
            # 3. Topological sort
            return self._topological_sort()
        
        def _validate_dependencies(self):
            # Ensure all dependencies exist in batch
            pass
            
        def _has_circular_dependencies(self) -> bool:
            # DFS-based cycle detection
            pass
            
        def _topological_sort(self) -> List[SpecMapping]:
            # Kahn's algorithm with priority sorting
            pass

  integration_points: |
    # Update load_json_specs function
    def load_json_specs(json_path: Path, filter_tags: Optional[List[str]] = None):
        # ... existing code ...
        
        # NEW: Resolve dependencies if any specs have dependencies
        if any(spec.dependencies for spec in mapping_file.specs):
            resolver = DependencyResolver(enabled_specs)
            ordered_specs = resolver.resolve_order()
        else:
            # Fall back to array order for backward compatibility
            ordered_specs = enabled_specs
        
        return ordered_specs, mapping_file.batch_config

example_enhanced_json: |
  {
    "version": "1.0",
    "specs": [
      {
        "spec_file": "./infrastructure_setup.md",
        "project_directory": "/path/to/infra",
        "enabled": true,
        "tags": ["infrastructure"],
        "priority": 0,
        "dependencies": []
      },
      {
        "spec_file": "./database_migration.md", 
        "project_directory": "/path/to/db",
        "enabled": true,
        "tags": ["database"],
        "priority": 1,
        "dependencies": ["infrastructure_setup"]
      },
      {
        "spec_file": "./api_service.md",
        "project_directory": "/path/to/api", 
        "enabled": true,
        "tags": ["backend"],
        "priority": 0,
        "dependencies": ["database_migration"]
      },
      {
        "spec_file": "./frontend_app.md",
        "project_directory": "/path/to/frontend",
        "enabled": true, 
        "tags": ["frontend"],
        "priority": 0,
        "dependencies": ["api_service"]
      },
      {
        "spec_file": "./monitoring_setup.md",
        "project_directory": "/path/to/monitoring",
        "enabled": true,
        "tags": ["monitoring"], 
        "priority": 2,
        "dependencies": ["api_service", "frontend_app"]
      }
    ],
    "batch_config": {
      "parallel": false,
      "continue_on_error": false, 
      "log_level": "INFO"
    }
  }

validation_enhancements: |
  Enhanced validation output should show:
  - Dependency chain visualization
  - Execution order with rationale
  - Priority conflicts within dependency levels
  - Circular dependency paths if detected
  
  Example output:
  ```
  ✓ Valid JSON with dependencies
    - Dependency resolution: PASSED
    - Circular dependencies: NONE
    - Execution order:
      1. infrastructure_setup (priority: 0, deps: [])
      2. database_migration (priority: 1, deps: [infrastructure_setup]) 
      3. api_service (priority: 0, deps: [database_migration])
      4. frontend_app (priority: 0, deps: [api_service])
      5. monitoring_setup (priority: 2, deps: [api_service, frontend_app])
  ```

error_scenarios: |
  1. Missing dependency: "Dependency 'nonexistent_spec' not found in batch"
  2. Circular dependency: "Circular dependency detected: spec_a -> spec_b -> spec_a"
  3. Invalid priority: "Priority must be non-negative integer"
  4. Self-dependency: "Spec cannot depend on itself"

testing_scenarios:
  - Empty dependencies list (should work like current implementation)
  - Single dependency chain (A -> B -> C -> D)
  - Multiple dependency chains that merge (A -> C, B -> C -> D)
  - Priority ordering within same dependency level
  - Circular dependency detection (A -> B -> A)
  - Missing dependency reference
  - Self-dependency error case
  - Mixed specs (some with dependencies, some without)

migration_path:
  phase_1: "Add new optional fields to SpecMapping model"
  phase_2: "Implement dependency resolution engine with tests"
  phase_3: "Integrate resolver into batch processing pipeline"
  phase_4: "Update validation and CLI output"
  phase_5: "Update documentation and create example files"

deployment_considerations:
  - New functionality is opt-in (dependencies field must be present)
  - Existing JSON files continue to work unchanged
  - Performance impact minimal for small batches (<50 specs)
  - Memory usage increases slightly for dependency graph storage
  - CLI validation provides immediate feedback on dependency issues

documentation_updates:
  - Add new fields to SpecMapping documentation
  - Create dependency resolution examples
  - Update batch processing guide
  - Add troubleshooting section for circular dependencies
  - Include performance considerations for large batches
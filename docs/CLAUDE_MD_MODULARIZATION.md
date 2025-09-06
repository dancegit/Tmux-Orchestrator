# CLAUDE.md Modularization Strategy

## Executive Summary

The Tmux Orchestrator's CLAUDE.md file has grown to 95KB (over 25,000 tokens, 2737 lines), exceeding Claude's token limits and causing agent briefing failures. This document outlines a comprehensive strategy to modularize CLAUDE.md into smaller, role-specific modules that maintain functionality while enabling reliable agent initialization.

## Problem Statement

### Current Issues
1. **Size Problem**: CLAUDE.md is 95KB with over 25,000 tokens, exceeding Claude's reading capacity
2. **Agent Briefing Failures**: When context-prime.md isn't available, agents are instructed to read CLAUDE.md but fail due to token limits
3. **Monolithic Design**: Single file contains all instructions for 15+ roles, violating Single Responsibility Principle
4. **Maintenance Burden**: Updates risk breaking cross-references; difficult to version control specific sections
5. **Performance Impact**: Large file causes slow loads and parsing inefficiencies in monitoring systems

### Impact on System
- Agent initialization failures prevent orchestration from starting
- Teams cannot coordinate effectively without understanding their roles
- Monitoring systems (extract_rules.py) inefficiently parse the entire file
- Git conflicts more likely with multiple agents updating the same large file

## Modularization Strategy

### Core Principles
1. **Token Safety**: Each module must be under 10,000 tokens (target: 5,000-7,000 for buffer)
2. **Role Specificity**: Agents load only relevant modules, reducing cognitive load
3. **Backward Compatibility**: Existing systems continue functioning during migration
4. **Maintainability**: Clear separation of concerns with versioned modules
5. **Performance**: Faster loads, parallel processing, and caching opportunities

### Proposed Module Structure

```
/home/clauderun/Tmux-Orchestrator/
├── docs/
│   ├── CLAUDE.md                    # Deprecated, kept for migration
│   └── claude_modules/              # New modular directory
│       ├── index.md                 # Master index (navigation hub)
│       ├── core/
│       │   ├── principles.md        # Core autonomy rules (~2,000 tokens)
│       │   ├── completion.md        # Completion protocols (~2,000 tokens)
│       │   └── communication.md     # Hub-spoke model (~2,000 tokens)
│       ├── roles/
│       │   ├── core_roles.md        # Orchestrator, PM, Dev, Test (~3,000 tokens)
│       │   ├── optional_roles.md    # Researcher, DevOps, etc. (~4,000 tokens)
│       │   └── system_ops_roles.md  # SysAdmin, SecurityOps, etc. (~4,000 tokens)
│       ├── workflows/
│       │   ├── git_workflow.md      # Git rules, branching (~3,000 tokens)
│       │   ├── worktree_setup.md    # Worktree architecture (~2,000 tokens)
│       │   └── integration.md       # PM integration protocols (~2,000 tokens)
│       ├── configuration/
│       │   ├── team_detection.md    # Project type detection (~3,000 tokens)
│       │   ├── role_dependencies.md # Role prerequisites (~2,000 tokens)
│       │   └── scaling.md           # Team size scaling (~2,000 tokens)
│       └── reference/
│           ├── best_practices.md    # Troubleshooting (~2,000 tokens)
│           ├── anti_patterns.md     # What to avoid (~1,500 tokens)
│           └── tools.md             # Tool reference (~2,000 tokens)
```

### Module Breakdown

#### 1. Core Modules (Always Loaded)
- **principles.md**: AUTONOMY FIRST, ACTION-ORIENTED, DEADLOCK AVOIDANCE
- **completion.md**: Completion signaling, marker files, reporting protocols
- **communication.md**: Hub-spoke model, scm commands, message templates

#### 2. Role-Specific Modules
- **core_roles.md**: Orchestrator, Project Manager, Developer, Tester, TestRunner
- **optional_roles.md**: Researcher, LogTracker, DevOps, Code Reviewer, Documentation Writer
- **system_ops_roles.md**: SysAdmin, SecurityOps, NetworkOps, MonitoringOps, DatabaseOps

#### 3. Workflow Modules
- **git_workflow.md**: 30-minute commits, branch protection, local remotes
- **worktree_setup.md**: Worktree locations, shared directories, symlinks
- **integration.md**: PM protocols, merge procedures, conflict resolution

#### 4. Configuration Modules
- **team_detection.md**: Project type indicators, dynamic role deployment
- **role_dependencies.md**: Prerequisites, conditional deployment
- **scaling.md**: Team size by subscription plan, token multipliers

#### 5. Reference Modules
- **best_practices.md**: Effective specifications, git safety rules
- **anti_patterns.md**: Common pitfalls, what to avoid
- **tools.md**: Script reference, command examples

## Implementation Plan

### Phase 1: Module Creation (Week 1)
1. **Automated Splitting**: Script to parse CLAUDE.md by headers and extract sections
2. **Manual Refinement**: Review and adjust module boundaries for coherence
3. **Token Validation**: Verify each module is under 10,000 tokens
4. **Cross-Reference Mapping**: Document inter-module dependencies

### Phase 2: Code Updates (Week 2)

#### A. Update briefing_system.py
```python
class ModuleLoader:
    def __init__(self, modules_path: Path):
        self.modules_path = modules_path
        self.cache = {}
    
    def load_for_role(self, role: str) -> Dict[str, str]:
        """Load relevant modules for a specific role"""
        modules = {
            'core': self._load_core_modules(),
            'role': self._load_role_module(role),
            'workflows': self._load_workflow_modules(role),
        }
        return modules
    
    def _load_core_modules(self) -> str:
        """Load modules that all roles need"""
        core_files = ['principles.md', 'completion.md', 'communication.md']
        return self._load_multiple(self.modules_path / 'core', core_files)
    
    def _load_role_module(self, role: str) -> str:
        """Load role-specific module"""
        if role in ['orchestrator', 'project_manager', 'developer', 'tester']:
            return self._load_file(self.modules_path / 'roles' / 'core_roles.md')
        elif role in ['sysadmin', 'securityops', 'networkops']:
            return self._load_file(self.modules_path / 'roles' / 'system_ops_roles.md')
        else:
            return self._load_file(self.modules_path / 'roles' / 'optional_roles.md')
```

#### B. Update extract_rules.py
```python
class ModularRuleExtractor:
    def __init__(self, modules_dir: Path):
        self.modules_dir = modules_dir
    
    def extract_all_rules(self) -> List[Dict]:
        """Extract rules from modular structure"""
        rules = []
        
        # Map rule types to specific modules
        rule_mapping = {
            'communication': 'core/communication.md',
            'git': 'workflows/git_workflow.md',
            'completion': 'core/completion.md',
        }
        
        for rule_type, module_path in rule_mapping.items():
            module_content = self._load_module(module_path)
            rules.extend(self._extract_rules_from_content(module_content, rule_type))
        
        return rules
```

#### C. Create ModuleManager utility
```python
class ModuleManager:
    """Central manager for CLAUDE modules"""
    
    def __init__(self):
        self.modules_path = Path(__file__).parent / 'docs' / 'claude_modules'
        self.loader = ModuleLoader(self.modules_path)
        self.validator = ModuleValidator(self.modules_path)
    
    def get_role_context(self, role: str) -> str:
        """Get complete context for a role"""
        modules = self.loader.load_for_role(role)
        return self._format_context(modules)
    
    def validate_all_modules(self) -> bool:
        """Ensure all modules are valid"""
        return self.validator.check_token_limits() and \
               self.validator.check_references() and \
               self.validator.check_completeness()
```

### Phase 3: Migration and Testing (Week 3)

#### Migration Steps
1. **Parallel Run**: Keep CLAUDE.md while testing modular system
2. **A/B Testing**: Run some agents with modules, others with monolithic
3. **Gradual Rollout**: Start with one project, expand to all
4. **Deprecation**: Mark CLAUDE.md as deprecated after validation

#### Testing Strategy
```python
# Unit Tests
def test_module_token_limits():
    """Ensure each module is under 10,000 tokens"""
    for module_file in Path('docs/claude_modules').rglob('*.md'):
        content = module_file.read_text()
        tokens = estimate_tokens(content)
        assert tokens < 10000, f"{module_file} has {tokens} tokens"

def test_role_loading():
    """Verify roles get appropriate modules"""
    loader = ModuleLoader(modules_path)
    dev_modules = loader.load_for_role('developer')
    assert 'core_roles.md' in dev_modules['role']
    assert 'git_workflow.md' in dev_modules['workflows']

# Integration Tests  
def test_agent_briefing_with_modules():
    """Test complete briefing generation"""
    briefing_system = BriefingSystem(tmux_path)
    context = create_test_context('developer')
    briefing = briefing_system.generate_role_briefing(context)
    assert len(briefing) < 50000  # Reasonable size
    assert 'AUTONOMY FIRST' in briefing  # Core principle included
```

### Phase 4: Monitoring and Optimization

#### Performance Metrics
- Module load times (target: <0.5s per module)
- Agent initialization success rate (target: >95%)
- Token usage per briefing (target: <15,000)
- Cache hit rates (target: >80% after warmup)

#### Optimization Opportunities
1. **Caching**: Use Redis or in-memory cache for frequently loaded modules
2. **Async Loading**: Load modules in parallel for multi-agent setups
3. **CDN/Static Hosting**: Serve modules from fast storage
4. **Compression**: Use gzip for network transfers if remote

## Benefits and Risks

### Benefits
1. **Reliability**: Agents can reliably read their instructions
2. **Performance**: 70-80% reduction in load times
3. **Maintainability**: Easier to update specific sections
4. **Scalability**: Add new roles without affecting existing ones
5. **Testing**: Module-level testing improves quality

### Risks and Mitigation
1. **Broken References**: Mitigate with automated link checking
2. **Increased Complexity**: Use clear naming and documentation
3. **Migration Failures**: Keep rollback plan with original CLAUDE.md
4. **Version Drift**: Implement semantic versioning for modules

## TODO List

### Immediate Actions (Priority 1)
- [ ] Create module extraction script to split CLAUDE.md
- [ ] Set up docs/claude_modules/ directory structure
- [ ] Implement ModuleLoader class in briefing_system.py
- [ ] Add module loading to agent briefing generation
- [ ] Create unit tests for token limits

### Short-term (Priority 2) 
- [ ] Update extract_rules.py for modular scanning
- [ ] Implement ModuleManager utility class
- [ ] Add caching layer for module content
- [ ] Create integration tests for briefing system
- [ ] Write migration script for smooth transition

### Medium-term (Priority 3)
- [ ] Add async loading for parallel agent initialization
- [ ] Implement module versioning system
- [ ] Create module validation CI/CD pipeline
- [ ] Add performance monitoring dashboard
- [ ] Document module creation guidelines

### Long-term (Priority 4)
- [ ] Build module dependency graph visualization
- [ ] Create automated module update system
- [ ] Implement A/B testing framework
- [ ] Add machine learning for optimal module selection
- [ ] Create module content search/index system

## Conclusion

Modularizing CLAUDE.md is critical for the Tmux Orchestrator's reliability and scalability. This strategy provides a clear path forward that maintains backward compatibility while solving the token limit issue. The modular approach aligns with the codebase's existing architecture and enables better performance, maintainability, and testing.

The implementation can be done incrementally with minimal risk, and the benefits far outweigh the initial complexity. With proper testing and monitoring, this change will significantly improve agent initialization success rates and overall system reliability.

## Appendices

### Appendix A: Token Estimation Formula
```python
def estimate_tokens(text: str) -> int:
    """Rough estimation: 1 token ≈ 4 characters"""
    return len(text) // 4
```

### Appendix B: Module Template
```markdown
---
module: module_name
version: 1.0.0
tokens: ~2000
dependencies: [core/principles.md]
---

# Module Title

## Overview
Brief description of module purpose

## Content
Main module content here

## References
- See also: [other_module.md]
- Related: [external_resource]
```

### Appendix C: Monitoring Queries
```sql
-- Track module load performance
SELECT module_name, AVG(load_time_ms), COUNT(*)
FROM module_loads
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY module_name;

-- Agent initialization success rate
SELECT 
    DATE(timestamp) as day,
    COUNT(*) as total_inits,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
    AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate
FROM agent_initializations
GROUP BY DATE(timestamp);
```
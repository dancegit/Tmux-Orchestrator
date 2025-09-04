# Auto-Orchestrate Modularization Specification

## Overview
This document specifies the modularization of the monolithic `auto_orchestrate.py` file (7000+ lines) into a structured Python package with focused modules. The refactoring preserves all existing functionality, maintains backward compatibility, and improves maintainability.

## Critical Requirements

### 1. OAuth Port Timing Preservation (MANDATORY)
**CRITICAL**: All OAuth port 3000 timing sequences MUST be preserved exactly as implemented in the current code:

```python
# CRITICAL OAUTH PORT WAIT - DO NOT REDUCE THESE TIMEOUTS!
# After killing the tmux window, Claude's OAuth server on port 3000 takes
# time to fully release. MINIMUM 30 SECONDS REQUIRED
oauth_port = int(os.environ.get('CLAUDE_OAUTH_PORT', '3000'))
if not self.wait_for_port_free(oauth_port, max_wait=45):
    console.print(f"[red]WARNING: OAuth port {oauth_port} still in use after 45s![/red]")
```

**Key Timing Requirements**:
- Port 3000 wait: 45 seconds minimum
- MCP initialization: 60 seconds timeout
- Window kill to restart: 30 seconds minimum
- All related comments and documentation must be preserved

### 2. Code Preservation
- ALL existing code must be preserved
- ALL comments and documentation must be maintained
- NO functionality can be lost during migration
- Backward compatibility must be maintained

## Target Package Structure

```
tmux_orchestrator/
├── __init__.py                 # Package initialization
├── main.py                     # Entry point (thin wrapper)
├── config/
│   ├── __init__.py
│   ├── settings.py             # Configuration management
│   └── validation.py           # Configuration validation
├── core/
│   ├── __init__.py
│   ├── orchestrator.py         # Main orchestrator class
│   ├── session_manager.py      # Session/project management
│   └── state_manager.py        # State tracking and persistence
├── agents/
│   ├── __init__.py
│   ├── agent_factory.py        # Agent creation and management
│   ├── briefing_system.py      # Agent briefing and role assignment
│   └── team_templates.py       # Team configuration templates
├── git/
│   ├── __init__.py
│   ├── worktree_manager.py     # Git worktree operations
│   ├── branch_manager.py       # Branch management
│   └── remote_setup.py         # Local remote configuration
├── tmux/
│   ├── __init__.py
│   ├── session_controller.py   # Tmux session management
│   ├── window_manager.py       # Window creation and naming
│   └── messaging.py            # Inter-agent communication
├── claude/
│   ├── __init__.py
│   ├── initialization.py       # Claude startup and MCP setup (CRITICAL)
│   ├── mcp_manager.py          # MCP configuration management
│   └── oauth_manager.py        # OAuth port management (CRITICAL)
├── monitoring/
│   ├── __init__.py
│   ├── health_monitor.py       # System health monitoring
│   ├── credit_manager.py       # Credit tracking and management
│   └── completion_detector.py  # Project completion detection
├── database/
│   ├── __init__.py
│   ├── models.py               # Database models
│   ├── queue_manager.py        # Queue operations
│   └── migrations.py           # Database migrations
├── utils/
│   ├── __init__.py
│   ├── file_operations.py      # File and directory utilities
│   ├── network_utils.py        # Network and port utilities
│   ├── logging_config.py       # Logging configuration
│   └── helpers.py              # General utility functions
└── cli/
    ├── __init__.py
    ├── commands.py             # CLI command definitions
    └── args_parser.py          # Argument parsing
```

## Module Responsibilities

### 1. `core/orchestrator.py`
- Main orchestrator class and workflow coordination
- High-level project lifecycle management
- Integration between all subsystems
- **Dependencies**: All other modules

### 2. `claude/initialization.py` (CRITICAL MODULE)
- Contains ALL OAuth port timing logic
- MCP initialization sequence with enhanced timeouts
- Claude startup and restart procedures
- Port conflict detection and resolution
- **MUST preserve all timing-related code and comments**

### 3. `claude/oauth_manager.py` (CRITICAL MODULE)
- OAuth server port management
- Port availability checking (`wait_for_port_free`)
- Port conflict resolution strategies
- **MUST preserve enhanced timing controls**

### 4. `agents/agent_factory.py`
- Agent creation and deployment logic
- Role-specific configuration and briefing
- Team composition management
- Dynamic role assignment

### 5. `git/worktree_manager.py`
- Git worktree creation and management
- Sibling directory structure setup
- Shared directory symlink creation
- Cleanup and maintenance

### 6. `tmux/session_controller.py`
- Tmux session lifecycle management
- Window creation and organization
- Agent window setup and configuration
- Session cleanup and recovery

### 7. `monitoring/health_monitor.py`
- System health monitoring
- Credit exhaustion detection
- Performance metrics collection
- Alert generation and handling

### 8. `database/queue_manager.py`
- Project queue management
- Status tracking and updates
- Database operations
- Migration support

## Implementation Strategy

### Phase 1: Package Structure Setup
1. Create `tmux_orchestrator/` package directory
2. Create all module directories with `__init__.py` files
3. Set up entry point in `main.py`
4. Configure package imports and dependencies

### Phase 2: Critical Module Migration
1. **PRIORITY**: Extract OAuth/MCP initialization code to `claude/` modules
2. Preserve ALL timing sequences and comments
3. Extract core orchestrator class
4. Migrate configuration management

### Phase 3: Feature Module Migration
1. Extract agent management functionality
2. Migrate Git worktree operations
3. Move Tmux session management
4. Transfer monitoring and health check code

### Phase 4: Support Module Migration
1. Extract database operations
2. Move utility functions
3. Migrate CLI argument parsing
4. Transfer logging configuration

### Phase 5: Integration and Testing
1. Update imports throughout codebase
2. Test all critical paths (OAuth initialization)
3. Verify backward compatibility
4. Performance testing and optimization

## Dependency Injection Pattern

Use dependency injection to avoid circular imports:

```python
# core/orchestrator.py
class Orchestrator:
    def __init__(self, 
                 session_manager: SessionManager,
                 agent_factory: AgentFactory,
                 git_manager: WorktreeManager,
                 claude_initializer: ClaudeInitializer):
        self.session_manager = session_manager
        self.agent_factory = agent_factory
        self.git_manager = git_manager
        self.claude_initializer = claude_initializer

# main.py
def create_orchestrator():
    # Initialize dependencies
    session_manager = SessionManager()
    agent_factory = AgentFactory()
    git_manager = WorktreeManager()
    claude_initializer = ClaudeInitializer()
    
    # Create orchestrator with dependencies
    return Orchestrator(session_manager, agent_factory, git_manager, claude_initializer)
```

## Critical Migration Checklist

### OAuth/MCP Code Migration
- [ ] Extract `wait_for_port_free()` with 45-second timeout
- [ ] Preserve OAuth port environment variable handling
- [ ] Maintain MCP initialization sequence timing
- [ ] Keep all timeout-related comments intact
- [ ] Test OAuth port conflict resolution

### Core Functionality
- [ ] Main orchestrator workflow preserved
- [ ] All CLI arguments supported
- [ ] Project queue operations intact
- [ ] Agent creation and briefing functional
- [ ] Git worktree operations working

### Monitoring and Health
- [ ] Credit management preserved
- [ ] Health monitoring functional
- [ ] Completion detection working
- [ ] System state tracking intact

### Testing Requirements
- [ ] All existing tests pass
- [ ] New module tests created
- [ ] Integration tests for critical paths
- [ ] OAuth timing stress tests
- [ ] Backward compatibility verified

## Risk Mitigation

### High-Risk Areas
1. **OAuth Port Timing**: Critical for batch processing stability
2. **MCP Initialization**: Complex sequence with multiple timeouts
3. **Git Worktree Management**: Complex file operations
4. **Agent Communication**: Inter-process messaging

### Mitigation Strategies
1. **Comprehensive Testing**: Test all critical paths before deployment
2. **Gradual Migration**: Implement in phases with rollback capability
3. **Code Reviews**: Multiple reviews for critical timing code
4. **Documentation**: Maintain detailed migration notes

## Success Criteria

### Functional Requirements
- [ ] All existing functionality preserved
- [ ] OAuth port conflicts eliminated in batch processing
- [ ] Improved code maintainability and readability
- [ ] Better separation of concerns
- [ ] Enhanced testability

### Performance Requirements
- [ ] No performance degradation
- [ ] Memory usage equivalent or better
- [ ] Startup time maintained
- [ ] Response times preserved

### Quality Requirements
- [ ] Code coverage maintained
- [ ] Documentation complete
- [ ] Error handling preserved
- [ ] Logging functionality intact

## Rollback Plan

If issues arise during implementation:
1. **Immediate Rollback**: Keep original `auto_orchestrate.py` as backup
2. **Gradual Rollback**: Revert specific modules if needed
3. **Testing Fallback**: Comprehensive test suite for validation
4. **Documentation**: Detailed rollback procedures

## Timeline

- **Phase 1**: 2-3 hours (Package setup)
- **Phase 2**: 4-5 hours (Critical modules)
- **Phase 3**: 3-4 hours (Feature modules)  
- **Phase 4**: 2-3 hours (Support modules)
- **Phase 5**: 3-4 hours (Integration and testing)
- **Total**: 14-19 hours

## Maintenance Benefits

Post-modularization benefits:
- **Easier Debugging**: Isolated module testing
- **Better Code Review**: Smaller, focused modules
- **Improved Testing**: Module-specific test suites
- **Enhanced Documentation**: Module-level documentation
- **Reduced Complexity**: Clear separation of concerns
- **Future Development**: Easier feature additions

## Conclusion

This modularization preserves all critical OAuth timing logic while improving code organization and maintainability. The dependency injection pattern prevents circular imports while maintaining flexibility. The phased approach ensures minimal risk during migration.
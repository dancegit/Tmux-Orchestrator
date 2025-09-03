"""
Tmux Orchestrator - Modular Multi-Agent Session Management

A comprehensive system for orchestrating multi-agent Claude sessions across
tmux windows with advanced coordination, monitoring, and management capabilities.

This modular architecture provides:
- Phase 1: OAuth timing management and Claude initialization
- Phase 2: Session and state management with persistence
- Phase 3: Git worktree management and tmux session control
- Phase 4: Database operations, monitoring, and utilities
- Phase 5: Complete integration and migration support

Version: 2.0.0 (Modular)
"""

from .core.orchestrator import Orchestrator
from .core.session_manager import SessionManager, SessionState, AgentState
from .core.state_manager import StateManager

# Claude initialization modules
from .claude.initialization import ClaudeInitializer
from .claude.oauth_manager import OAuthManager

# Agent management modules
from .agents.agent_factory import AgentFactory, RoleConfig
from .agents.briefing_system import BriefingSystem, BriefingContext, ProjectSpec

# Infrastructure modules
from .git.worktree_manager import WorktreeManager
from .tmux.session_controller import TmuxSessionController
from .tmux.messaging import TmuxMessenger

# Support modules
from .database.queue_manager import QueueManager, Task, TaskPriority, TaskStatus
from .monitoring.health_monitor import HealthMonitor, HealthStatus, SystemMetrics
from .utils.file_utils import FileUtils
from .utils.system_utils import SystemUtils
from .utils.config_loader import ConfigLoader, ConfigSchema

# CLI module
from .cli.enhanced_cli import EnhancedCLI

__version__ = "2.0.0"
__author__ = "Tmux Orchestrator Team"
__description__ = "Modular multi-agent tmux session orchestration system"

# Main exports for external use
__all__ = [
    # Core classes
    'Orchestrator',
    'SessionManager', 'SessionState', 'AgentState',
    'StateManager',
    
    # Claude initialization
    'ClaudeInitializer',
    'OAuthManager',
    
    # Agent management
    'AgentFactory', 'RoleConfig',
    'BriefingSystem', 'BriefingContext', 'ProjectSpec',
    
    # Infrastructure
    'WorktreeManager',
    'TmuxSessionController',
    'TmuxMessenger',
    
    # Support modules
    'QueueManager', 'Task', 'TaskPriority', 'TaskStatus',
    'HealthMonitor', 'HealthStatus', 'SystemMetrics',
    'FileUtils',
    'SystemUtils', 
    'ConfigLoader', 'ConfigSchema',
    
    # CLI
    'EnhancedCLI',
    
    # Package metadata
    '__version__',
    '__author__',
    '__description__'
]

def get_version():
    """Get the current version of Tmux Orchestrator."""
    return __version__

def create_orchestrator(**kwargs):
    """
    Create a new Orchestrator instance with optional dependency injection.
    
    This is the main entry point for using the Tmux Orchestrator system.
    
    Args:
        **kwargs: Optional dependencies to inject (for testing or customization)
        
    Returns:
        Orchestrator: Configured orchestrator instance
    """
    return Orchestrator(**kwargs)

def get_system_info():
    """
    Get comprehensive system information for diagnostics.
    
    Returns:
        Dict containing system and orchestrator information
    """
    from pathlib import Path
    import platform
    import sys
    
    system_utils = SystemUtils()
    
    return {
        'orchestrator_version': __version__,
        'python_version': sys.version,
        'platform': platform.platform(),
        'system_info': system_utils.get_system_info(),
        'tmux_available': system_utils.check_command_availability('tmux'),
        'git_available': system_utils.check_command_availability('git'),
        'claude_available': system_utils.check_command_availability('claude')
    }
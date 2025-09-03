"""
Main entry point for the Tmux Orchestrator system.

This module provides the fully integrated modular system that replaces
the monolithic auto_orchestrate.py with clean, testable components.
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import time

# Add the current directory to the path
TMUX_ORCHESTRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TMUX_ORCHESTRATOR_ROOT))

# Import all modular components
from .core.orchestrator import Orchestrator
from .core.session_manager import SessionManager
from .core.state_manager import StateManager
from .claude.initialization import ClaudeInitializer
from .claude.oauth_manager import OAuthManager
from .agents.agent_factory import AgentFactory
from .agents.briefing_system import BriefingSystem
from .git.worktree_manager import WorktreeManager
from .tmux.session_controller import TmuxSessionController
from .tmux.messaging import TmuxMessenger
from .database.queue_manager import QueueManager
from .monitoring.health_monitor import HealthMonitor
from .utils.config_loader import ConfigLoader
from .utils.file_utils import FileUtils
from .utils.system_utils import SystemUtils
from .cli.enhanced_cli import EnhancedCLI


def create_orchestrator(config: Optional[Dict[str, Any]] = None) -> Orchestrator:
    """
    Create and configure a fully integrated Orchestrator instance.
    
    Args:
        config: Optional configuration dictionary
    
    Returns:
        Orchestrator: Fully configured orchestrator with all subsystems
    """
    # Load configuration
    config_dir = TMUX_ORCHESTRATOR_ROOT / "config"
    config_loader = ConfigLoader(config_dir=config_dir)
    
    if config:
        orchestrator_config = config
    else:
        # Load from default config file if it exists
        config_path = config_dir / "orchestrator.yaml"
        if config_path.exists():
            orchestrator_config = config_loader.load_config(str(config_path))
        else:
            orchestrator_config = {}
    
    # Initialize all subsystems
    file_utils = FileUtils()
    system_utils = SystemUtils()
    
    # Phase 1: OAuth and Claude components
    claude_initializer = ClaudeInitializer()
    oauth_manager = claude_initializer.oauth_manager  # Get the manager from initializer
    
    # Phase 2: Core components
    state_manager = StateManager(tmux_orchestrator_path=TMUX_ORCHESTRATOR_ROOT)
    session_manager = SessionManager(tmux_orchestrator_path=TMUX_ORCHESTRATOR_ROOT)
    
    # Phase 3: Infrastructure components
    # Note: WorktreeManager needs project_path, will be set when project is selected
    worktree_manager = None  # Will be created per-project
    tmux_controller = TmuxSessionController(tmux_orchestrator_path=TMUX_ORCHESTRATOR_ROOT)
    tmux_messaging = TmuxMessenger(tmux_orchestrator_path=TMUX_ORCHESTRATOR_ROOT)
    queue_manager = QueueManager(tmux_orchestrator_path=TMUX_ORCHESTRATOR_ROOT)
    
    # Phase 4: Support components
    briefing_system = BriefingSystem(tmux_orchestrator_path=TMUX_ORCHESTRATOR_ROOT)
    # Note: AgentFactory has different constructor, needs session_name
    agent_factory = None  # Will be created per-session
    health_monitor = HealthMonitor(tmux_orchestrator_path=TMUX_ORCHESTRATOR_ROOT)
    
    # Phase 5: Create integrated orchestrator
    orchestrator = Orchestrator(
        session_manager=session_manager,
        agent_factory=agent_factory,
        git_manager=worktree_manager,
        tmux_controller=tmux_controller,
        health_monitor=health_monitor,
        queue_manager=queue_manager,
        config_loader=config_loader
    )
    
    # Add additional components as attributes for direct access
    orchestrator.oauth_manager = oauth_manager
    orchestrator.state_manager = state_manager
    orchestrator.messaging = tmux_messaging
    
    return orchestrator


def main():
    """
    Main entry point for the modular Tmux Orchestrator.
    
    This replaces the monolithic auto_orchestrate.py with a clean,
    modular implementation while maintaining full backward compatibility.
    """
    parser = argparse.ArgumentParser(
        description="Tmux Orchestrator - AI-powered multi-agent orchestration system",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Core arguments (backward compatible with auto_orchestrate.py)
    parser.add_argument(
        '--project', '-p',
        type=str,
        help='Path to the project directory'
    )
    parser.add_argument(
        '--spec', '-s',
        type=str,
        help='Path to the specification file'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume an existing orchestration'
    )
    parser.add_argument(
        '--status-only',
        action='store_true',
        help='Check status without making changes'
    )
    parser.add_argument(
        '--rebrief-all',
        action='store_true',
        help='Re-brief all agents when resuming'
    )
    
    # Team configuration
    parser.add_argument(
        '--roles',
        type=str,
        help='Comma-separated list of roles to deploy'
    )
    parser.add_argument(
        '--add-roles',
        type=str,
        help='Add additional roles to existing orchestration'
    )
    parser.add_argument(
        '--team-type',
        type=str,
        choices=['web_application', 'system_deployment', 'infrastructure_as_code', 'data_pipeline'],
        help='Predefined team template to use'
    )
    
    # Advanced options
    parser.add_argument(
        '--plan',
        type=str,
        choices=['pro', 'max5', 'max20', 'console'],
        default='max5',
        help='Subscription plan for token optimization'
    )
    parser.add_argument(
        '--size',
        type=str,
        choices=['small', 'medium', 'large'],
        default='medium',
        help='Team size based on token budget'
    )
    parser.add_argument(
        '--git-mode',
        type=str,
        choices=['local', 'github'],
        default='local',
        help='Git workflow mode'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview actions without executing'
    )
    parser.add_argument(
        '--new-project',
        action='store_true',
        help='Create new project directory parallel to Tmux-Orchestrator from spec'
    )
    
    args = parser.parse_args()
    
    # Create enhanced CLI for rich output
    cli = EnhancedCLI(orchestrator_path=TMUX_ORCHESTRATOR_ROOT)
    
    try:
        # Create orchestrator with configuration
        config = {
            'debug': args.debug,
            'dry_run': args.dry_run,
            'git_mode': args.git_mode,
            'plan': args.plan,
            'team_size': args.size
        }
        
        orchestrator = create_orchestrator(config)
        
        # Handle different operation modes
        if args.resume:
            # Resume existing orchestration
            if not args.project:
                cli.error("--project is required when using --resume")
                return False
            
            result = orchestrator.resume_orchestration(
                project_path=args.project,
                status_only=args.status_only,
                rebrief_all=args.rebrief_all,
                add_roles=args.add_roles.split(',') if args.add_roles else None
            )
            
        elif args.new_project and args.spec:
            # Create new project from spec
            from pathlib import Path
            import shutil
            import subprocess
            from datetime import datetime
            
            spec_path = Path(args.spec)
            if not spec_path.exists():
                cli.error(f"Spec file not found: {spec_path}")
                return False
            
            # Create project name from spec name
            project_name = f"{spec_path.stem.lower().replace(' ', '-').replace('_', '-')}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            # Create project parallel to Tmux-Orchestrator
            tmux_orch_dir = Path(TMUX_ORCHESTRATOR_ROOT)
            project_dir = tmux_orch_dir.parent / project_name
            
            cli.info(f"Creating new project: {project_dir}")
            
            # Create project directory
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy spec to project
            dest_spec = project_dir / spec_path.name
            shutil.copy(str(spec_path), str(dest_spec))
            
            # Initialize git repo
            subprocess.run(['git', 'init', str(project_dir)], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(project_dir), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(project_dir), 'commit', '-m', 'Initial commit: Add specification'], check=True)
            
            cli.success(f"Created project at: {project_dir}")
            
            # Now start orchestration with the new project
            result = orchestrator.start_orchestration(
                project_path=str(project_dir),
                spec_path=str(dest_spec),
                roles=args.roles.split(',') if args.roles else None,
                team_type=args.team_type
            )
            
        elif args.project and args.spec:
            # Start new orchestration with existing project
            result = orchestrator.start_orchestration(
                project_path=args.project,
                spec_path=args.spec,
                roles=args.roles.split(',') if args.roles else None,
                team_type=args.team_type
            )
            
        else:
            # Show help if no valid operation specified
            parser.print_help()
            return False
        
        # Display results
        if result:
            cli.success("Orchestration completed successfully")
            if isinstance(result, dict):
                cli.display_results(result)
                
            # NEW: Mark project as completed in database using modular queue manager
            project_id = os.environ.get('SCHEDULER_PROJECT_ID')
            if project_id:
                try:
                    # Use the integrated queue manager for project completion
                    from .database.queue_manager import QueueManager
                    
                    queue_manager = QueueManager(TMUX_ORCHESTRATOR_ROOT)
                    
                    # Extract session name if available
                    session_name = None
                    if isinstance(result, dict) and 'session_name' in result:
                        session_name = result['session_name']
                        
                    # Mark project complete using modular system
                    success = queue_manager.mark_project_complete(
                        project_id=int(project_id), 
                        success=True, 
                        session_name=session_name
                    )
                    
                    if success:
                        if session_name:
                            cli.info(f"✓ Project {project_id} marked as completed with session {session_name}")
                        else:
                            cli.info(f"✓ Project {project_id} marked as completed in database")
                    else:
                        cli.warning(f"Warning: Project {project_id} completion update failed")
                        
                except Exception as e:
                    cli.warning(f"Warning: Could not update project {project_id} status: {e}")
        else:
            cli.error("Orchestration failed")
            
            # NEW: Mark project as failed in database using modular queue manager
            project_id = os.environ.get('SCHEDULER_PROJECT_ID')
            if project_id:
                try:
                    from .database.queue_manager import QueueManager
                    
                    queue_manager = QueueManager(TMUX_ORCHESTRATOR_ROOT)
                    success = queue_manager.mark_project_complete(
                        project_id=int(project_id), 
                        success=False, 
                        error_message="Orchestration failed"
                    )
                    
                    if success:
                        cli.info(f"✓ Project {project_id} marked as failed in database")
                    else:
                        cli.warning(f"Warning: Project {project_id} failure update failed")
                        
                except Exception as e:
                    cli.warning(f"Warning: Could not update project {project_id} status: {e}")
            
        return result
        
    except KeyboardInterrupt:
        cli.warning("\nOrchestration interrupted by user")
        
        # NEW: Mark project as failed in database using modular queue manager
        project_id = os.environ.get('SCHEDULER_PROJECT_ID')
        if project_id:
            try:
                from .database.queue_manager import QueueManager
                
                queue_manager = QueueManager(TMUX_ORCHESTRATOR_ROOT)
                success = queue_manager.mark_project_complete(
                    project_id=int(project_id), 
                    success=False, 
                    error_message="Orchestration interrupted by user"
                )
                
                if success:
                    cli.info(f"✓ Project {project_id} marked as failed in database")
                else:
                    cli.warning(f"Warning: Project {project_id} failure update failed")
                    
            except Exception as completion_error:
                cli.warning(f"Warning: Could not update project {project_id} status: {completion_error}")
                
        return False
    except Exception as e:
        if args.debug:
            import traceback
            cli.error(f"Error: {e}")
            cli.debug(traceback.format_exc())
        else:
            cli.error(f"Error: {e}")
            cli.info("Use --debug for more details")
            
        # NEW: Mark project as failed in database using modular queue manager
        project_id = os.environ.get('SCHEDULER_PROJECT_ID')
        if project_id:
            try:
                from .database.queue_manager import QueueManager
                
                queue_manager = QueueManager(TMUX_ORCHESTRATOR_ROOT)
                success = queue_manager.mark_project_complete(
                    project_id=int(project_id), 
                    success=False, 
                    error_message=str(e)
                )
                
                if success:
                    cli.info(f"✓ Project {project_id} marked as failed in database")
                else:
                    cli.warning(f"Warning: Project {project_id} failure update failed")
                    
            except Exception as completion_error:
                cli.warning(f"Warning: Could not update project {project_id} status: {completion_error}")
                
        return False


def restart_claude_with_oauth_management(session_name: str, 
                                       window_idx: int,
                                       window_name: str, 
                                       worktree_path: str) -> bool:
    """
    Restart Claude in a specific tmux window with OAuth management.
    
    Args:
        session_name: Tmux session name
        window_idx: Window index to restart
        window_name: Window name for the restarted window
        worktree_path: Path to the agent's worktree
        
    Returns:
        bool: True if restart succeeded with proper OAuth management
    """
    orchestrator = create_orchestrator()
    
    # Use the integrated OAuth manager and Claude initializer
    oauth_manager = orchestrator.oauth_manager
    claude_init = orchestrator.agent_factory.claude_initializer
    
    # Check for OAuth conflicts first
    if not oauth_manager.wait_for_port_available():
        print(f"❌ OAuth port {oauth_manager.oauth_port} is not available")
        return False
    
    # Restart Claude with proper timing
    result = claude_init.restart_claude(
        session_name=session_name,
        window_idx=window_idx,
        window_name=window_name,
        worktree_path=worktree_path
    )
    
    return result['success']


def check_oauth_conflicts() -> Dict[str, Any]:
    """
    Check for OAuth port conflicts across the system.
    
    Returns:
        Dict containing conflict status and recommendations
    """
    orchestrator = create_orchestrator()
    oauth_manager = orchestrator.oauth_manager
    
    # Check if port is free
    is_free = oauth_manager.is_port_free()
    
    # Find any processes using the port
    conflicts = []
    if not is_free:
        import subprocess
        try:
            result = subprocess.run(
                f"lsof -i :{oauth_manager.oauth_port}",
                shell=True,
                capture_output=True,
                text=True
            )
            if result.stdout:
                conflicts = result.stdout.strip().split('\n')[1:]  # Skip header
        except:
            pass
    
    recommendations = []
    if not is_free:
        recommendations = [
            f"Kill processes using port {oauth_manager.oauth_port}",
            f"Or set CLAUDE_OAUTH_PORT to a different port",
            f"Or wait for the current OAuth process to complete (45-60 seconds)"
        ]
    
    return {
        'port': oauth_manager.oauth_port,
        'is_free': is_free,
        'conflicts_detected': conflicts,
        'recommendations': recommendations
    }


def run_enhanced_oauth_diagnostics() -> Dict[str, Any]:
    """
    Run comprehensive OAuth diagnostics using the enhanced modular system.
    
    This replaces the legacy auto_orchestrate.py dependency with full
    modular OAuth management capabilities including:
    - Proactive conflict detection
    - Batch processing optimization  
    - Enhanced port diagnostics
    - Process identification and cleanup suggestions
    
    Returns:
        Dict containing comprehensive OAuth status and diagnostics
    """
    orchestrator = create_orchestrator()
    oauth_manager = orchestrator.oauth_manager
    
    # Get comprehensive port status
    status = oauth_manager.get_port_status()
    
    # Add enhanced diagnostics
    status['batch_processing_safe'] = status['is_free']
    status['pre_claude_check_passed'] = oauth_manager.pre_claude_start_check("diagnostic")
    
    # Add timing recommendations
    if not status['is_free']:
        status['recommended_wait_time'] = 60  # seconds for safe batch processing
        status['conflict_type'] = 'batch_processing' if any(
            'claude' in str(conflict).lower() for conflict in status['conflicts']
        ) else 'unknown_process'
    
    return status


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
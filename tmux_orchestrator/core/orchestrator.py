"""
Core Orchestrator Module

This module contains the main Orchestrator class that coordinates all subsystems.
It serves as the central hub for project lifecycle management and agent coordination.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
from rich.console import Console

from ..claude.initialization import ClaudeInitializer
from ..claude.oauth_manager import OAuthManager
from .session_manager import SessionManager, SessionState
from .state_manager import StateManager
from ..agents.agent_factory import AgentFactory
from ..agents.briefing_system import BriefingSystem
from ..git.worktree_manager import WorktreeManager
from ..tmux.session_controller import TmuxSessionController
from ..tmux.messaging import TmuxMessenger
from ..database.queue_manager import QueueManager
from ..monitoring.health_monitor import HealthMonitor
from ..utils.config_loader import ConfigLoader
from ..cli.enhanced_cli import EnhancedCLI

console = Console()


class Orchestrator:
    """
    Main orchestrator class for managing multi-agent tmux sessions.
    
    This class coordinates between all subsystems:
    - Claude initialization with OAuth management
    - Agent factory and team management  
    - Git worktree management
    - Tmux session control
    - Project state management
    - Health monitoring
    """
    
    def __init__(self, 
                 session_manager=None,
                 agent_factory=None, 
                 git_manager=None,
                 tmux_controller=None,
                 health_monitor=None,
                 queue_manager=None,
                 config_loader=None):
        """
        Initialize orchestrator with dependency injection.
        
        Args:
            session_manager: Session and project management
            agent_factory: Agent creation and deployment
            git_manager: Git worktree operations
            tmux_controller: Tmux session management
            health_monitor: System health monitoring
        """
        # Initialize available subsystems
        tmux_orchestrator_path = Path(__file__).parent.parent.parent
        self.tmux_orchestrator_path = tmux_orchestrator_path  # Store as instance attribute
        
        self.session_manager = session_manager or SessionManager(tmux_orchestrator_path)
        self.agent_factory = agent_factory or AgentFactory(tmux_orchestrator_path)
        self.state_manager = StateManager(tmux_orchestrator_path)
        self.briefing_system = BriefingSystem(tmux_orchestrator_path)
        
        # Phase 3: Infrastructure modules
        self.git_manager = git_manager or WorktreeManager(tmux_orchestrator_path)
        self.tmux_controller = tmux_controller or TmuxSessionController(tmux_orchestrator_path)
        self.messenger = TmuxMessenger(tmux_orchestrator_path)
        
        # Phase 4: Support modules
        self.queue_manager = queue_manager or QueueManager(tmux_orchestrator_path)
        self.health_monitor = health_monitor or HealthMonitor(tmux_orchestrator_path)
        self.config_loader = config_loader or ConfigLoader(tmux_orchestrator_path / 'config')
        self.cli = EnhancedCLI(tmux_orchestrator_path)
        
        # Critical subsystems (immediately available)
        self.claude_initializer = ClaudeInitializer()
        self.oauth_manager = OAuthManager()
    
    def create_project_orchestration(self, 
                                   project_path: Path,
                                   spec_file: Path,
                                   team_config: Dict[str, Any] = None) -> bool:
        """
        Create a complete project orchestration setup.
        
        This is the main entry point that coordinates:
        1. Project analysis and specification parsing
        2. Team composition determination
        3. Git worktree setup
        4. Tmux session creation
        5. Agent deployment with MCP initialization
        6. Health monitoring setup
        
        Args:
            project_path: Path to the project to orchestrate
            spec_file: Path to specification file
            team_config: Optional team configuration override
            
        Returns:
            bool: True if orchestration was created successfully
        """
        console.print(f"[blue]🚀 Creating orchestration for {project_path}[/blue]")
        
        try:
            # Core orchestration workflow implementation
            # Step 1: Validate inputs
            if not project_path.exists():
                console.print(f"[red]Error: Project path does not exist: {project_path}[/red]")
                return False
                
            if not spec_file.exists():
                console.print(f"[red]Error: Spec file does not exist: {spec_file}[/red]")
                return False
            
            # Step 2: Analyze specification with Claude
            console.print("[cyan]Step 1:[/cyan] Analyzing specification with Claude...")
            spec_dict = self._analyze_spec_with_claude(spec_file, project_path)
            
            if not spec_dict:
                console.print("[red]❌ Failed to analyze specification with Claude[/red]")
                return False
            
            # Step 3: Parse specification into structured format
            try:
                implementation_spec = self._parse_implementation_spec(spec_dict)
            except Exception as e:
                console.print(f"[red]Error parsing implementation spec: {e}[/red]")
                return False
            
            # Step 4: Display implementation plan and get approval
            console.print("[cyan]Step 2:[/cyan] Review implementation plan...")
            if not self._display_and_approve_plan(implementation_spec):
                console.print("[yellow]Setup cancelled by user.[/yellow]")
                return False
            
            # Step 5: Set up tmux session and orchestration
            console.print("[cyan]Step 3:[/cyan] Setting up tmux orchestration...")
            session_name = self._setup_orchestration_session(
                implementation_spec, project_path, team_config
            )
            
            if not session_name:
                console.print("[red]❌ Failed to set up orchestration session[/red]")
                return False
            
            console.print(f"[green]✓ Orchestration created successfully![/green]")
            console.print(f"Session: [cyan]{session_name}[/cyan]")
            console.print(f"To attach: [cyan]tmux attach -t {session_name}[/cyan]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Failed to create orchestration: {e}[/red]")
            return False
    
    def resume_project_orchestration(self, project_path: Path) -> bool:
        """
        Resume an existing project orchestration.
        
        This function handles:
        1. Session state detection and recovery
        2. Agent health assessment
        3. OAuth port conflict resolution
        4. Selective agent restart
        5. Context restoration
        
        Args:
            project_path: Path to project to resume
            
        Returns:
            bool: True if resume was successful
        """
        console.print(f"[blue]🔄 Resuming orchestration for {project_path}[/blue]")
        
        try:
            # TODO: Implement resume logic
            # This will handle smart agent detection and recovery
            
            console.print(f"[yellow]⚠️ Resume not yet implemented in modular system[/yellow]")
            return False
            
        except Exception as e:
            console.print(f"[red]❌ Failed to resume orchestration: {e}[/red]")
            return False
    
    def restart_claude_with_oauth_management(self, 
                                           session_name: str, 
                                           window_idx: int,
                                           window_name: str,
                                           worktree_path: str) -> bool:
        """
        Restart Claude in a window with full OAuth port management.
        
        This method provides immediate access to the critical OAuth timing logic
        while the rest of the system is being migrated.
        
        Args:
            session_name: Tmux session name
            window_idx: Window index to restart
            window_name: Window name
            worktree_path: Agent worktree path
            
        Returns:
            bool: True if restart succeeded
        """
        console.print(f"[blue]🔄 Restarting Claude with OAuth management in {session_name}:{window_idx}[/blue]")
        
        return self.claude_initializer.restart_claude_in_window(
            session_name=session_name,
            window_idx=window_idx, 
            window_name=window_name,
            worktree_path=worktree_path
        )
    
    def check_oauth_port_conflicts(self) -> Dict[str, Any]:
        """
        Check for OAuth port conflicts across the system.
        
        Returns:
            Dict containing conflict status and diagnostic information
        """
        port_status = {
            'port': self.oauth_manager.oauth_port,
            'is_free': self.oauth_manager.is_port_free(),
            'conflicts_detected': [],
            'recommendations': []
        }
        
        if not port_status['is_free']:
            port_status['conflicts_detected'].append(f"Port {self.oauth_manager.oauth_port} is in use")
            port_status['recommendations'].append("Wait for current Claude processes to complete")
            port_status['recommendations'].append("Check for zombie Claude processes")
        
        return port_status
    
    def start_orchestration(self, 
                           project_path: str,
                           spec_path: str,
                           roles: List[str] = None,
                           team_type: str = None,
                           **kwargs) -> bool:
        """
        Start a new orchestration (entry point expected by tmux_orchestrator_cli.py).
        
        This method uses the modular create_project_orchestration implementation.
        
        Args:
            project_path: Path to project as string
            spec_path: Path to spec file as string
            roles: Optional list of roles to deploy
            team_type: Optional team type override
            **kwargs: Additional arguments passed through
            
        Returns:
            bool: True if orchestration started successfully
        """
        try:
            from pathlib import Path
            
            console.print(f"[blue]🚀 Starting orchestration using modular system[/blue]")
            
            # Convert string paths to Path objects
            project_path_obj = Path(project_path).resolve()
            spec_file_obj = Path(spec_path).resolve()
            
            # Prepare team configuration
            team_config = {
                'roles': roles or [],
                'team_type': team_type,
                **kwargs
            }
            
            # Use the modular create_project_orchestration implementation
            return self.create_project_orchestration(
                project_path_obj, 
                spec_file_obj, 
                team_config
            )
            
        except Exception as e:
            console.print(f"[red]❌ Failed to start orchestration: {e}[/red]")
            import traceback
            console.print(f"[yellow]{traceback.format_exc()}[/yellow]")
            return False
    
    def _analyze_spec_with_claude(self, spec_file: Path, project_path: Path) -> Optional[Dict[str, Any]]:
        """
        Analyze specification file with Claude to create implementation plan.
        
        Uses the modular SpecificationAnalyzer to provide comprehensive spec analysis
        with context-aware project understanding, Claude-powered implementation planning,
        and robust error handling.
        
        Args:
            spec_file: Path to specification file
            project_path: Path to project directory
            
        Returns:
            Dict containing parsed implementation spec or None if failed
        """
        try:
            from ..claude.spec_analyzer import SpecificationAnalyzer
            
            console.print(f"[blue]🤖 Using modular specification analyzer[/blue]")
            
            # Create specification analyzer with orchestrator context
            spec_analyzer = SpecificationAnalyzer(self.tmux_orchestrator_path)
            
            # Analyze specification using advanced modular system
            spec_dict = spec_analyzer.analyze_specification(spec_file, project_path)
            
            if spec_dict:
                console.print(f"[green]✓ Modular spec analysis completed successfully[/green]")
            else:
                console.print(f"[red]❌ Modular spec analysis failed[/red]")
                
            return spec_dict
            
        except Exception as e:
            console.print(f"[red]Failed to analyze spec with modular system: {e}[/red]")
            return None
    
    def _parse_implementation_spec(self, spec_dict: Dict[str, Any]) -> Any:
        """
        Parse specification dictionary into structured format.
        
        Uses the modular ImplementationSpec class to provide comprehensive spec parsing
        with Pydantic validation and structured data models. All specification parsing
        is now handled by the modular system instead of legacy auto_orchestrate.py.
        
        Args:
            spec_dict: Raw specification dictionary from Claude analysis
            
        Returns:
            Parsed implementation specification using modular system
        """
        try:
            from ..claude.oauth_manager import ImplementationSpec
            
            console.print(f"[blue]🔧 Using modular implementation spec parser[/blue]")
            
            # Parse into Pydantic model using modular system
            implementation_spec = ImplementationSpec(**spec_dict)
            
            console.print(f"[green]✓ Modular spec parsing completed successfully[/green]")
            return implementation_spec
            
        except Exception as e:
            console.print(f"[red]Failed to parse spec with modular system: {e}[/red]")
            raise
    
    def _display_and_approve_plan(self, implementation_spec: Any) -> bool:
        """
        Display implementation plan and get user approval.
        
        Uses the modular PlanDisplayManager to provide comprehensive plan visualization
        with rich formatting, role assignments, and approval workflows. All plan display
        functionality is now handled by the modular system instead of legacy auto_orchestrate.py.
        
        Args:
            implementation_spec: Parsed implementation specification
            
        Returns:
            bool: True if user approved the plan (auto-approves for automated workflow)
        """
        try:
            from ..claude.oauth_manager import PlanDisplayManager
            
            console.print(f"[blue]📊 Using modular plan display manager[/blue]")
            
            # Create plan display manager
            plan_manager = PlanDisplayManager(
                project_path=str(implementation_spec.project.path)
            )
            
            # Display the implementation plan using modular system
            # Note: Using defaults for optional parameters that were in the original system
            approved = plan_manager.display_implementation_plan(
                spec=implementation_spec,
                manual_size=None,  # Could be passed from orchestrator if needed
                additional_roles=None,  # Could be passed from team_config if needed
                plan_type='max5'  # Default plan type, could be made configurable
            )
            
            if approved:
                console.print(f"[green]✓ Plan display and approval completed[/green]")
            else:
                console.print(f"[yellow]Plan not approved[/yellow]")
                
            return approved
            
        except Exception as e:
            console.print(f"[red]Failed to display plan with modular system: {e}[/red]")
            return False
    
    def _setup_orchestration_session(self, implementation_spec: Any, 
                                   project_path: Path, team_config: Dict[str, Any]) -> Optional[str]:
        """
        Set up the tmux orchestration session with agents.
        
        Uses the modular SessionOrchestrator to provide comprehensive session setup
        with tmux windows, agent deployment, and briefings. All session orchestration
        is now handled by the modular system instead of legacy auto_orchestrate.py.
        
        Args:
            implementation_spec: Parsed implementation specification
            project_path: Path to project directory
            team_config: Team configuration
            
        Returns:
            Session name if successful, None otherwise
        """
        try:
            from ..claude.oauth_manager import SessionOrchestrator
            
            console.print(f"[blue]🎭 Using modular session orchestrator[/blue]")
            
            # Get the tmux orchestrator root path
            tmux_orchestrator_root = Path(__file__).parent.parent.parent
            
            # Create session orchestrator
            session_orchestrator = SessionOrchestrator(
                tmux_orchestrator_path=tmux_orchestrator_root,
                project_path=project_path
            )
            
            # Set up tmux session using modular system
            session_name = session_orchestrator.setup_tmux_session(
                spec=implementation_spec,
                team_config=team_config
            )
            
            if session_name:
                console.print(f"[green]✓ Session orchestration completed: {session_name}[/green]")
            else:
                console.print(f"[red]Session orchestration failed[/red]")
            
            return session_name
            
        except Exception as e:
            console.print(f"[red]Failed to setup orchestration session with modular system: {e}[/red]")
            import traceback
            console.print(f"[yellow]{traceback.format_exc()}[/yellow]")
            return None
"""
Session Management Module

Handles project session lifecycle, state persistence, and recovery operations.
Extracted from auto_orchestrate.py to provide modular session management.
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from rich.console import Console

console = Console()


@dataclass
class AgentState:
    """State of a single agent in the orchestration"""
    role: str
    window_index: int
    window_name: str
    worktree_path: str
    last_briefing_time: Optional[str] = None
    last_check_in_time: Optional[str] = None
    is_alive: bool = True
    is_exhausted: bool = False
    credit_reset_time: Optional[str] = None
    current_branch: Optional[str] = None
    commit_hash: Optional[str] = None
    waiting_for: Optional[Dict[str, Any]] = None  # Track authorization waits


@dataclass
class SessionState:
    """Complete state of an orchestration session"""
    session_name: str
    project_path: str
    project_name: str
    implementation_spec_path: str
    created_at: str
    updated_at: str
    agents: Dict[str, AgentState]
    orchestrator_window: int = 0
    project_size: str = "medium"
    parent_branch: Optional[str] = None
    completion_status: str = "pending"  # 'pending', 'completed', or 'failed'
    completion_time: Optional[str] = None
    failure_reason: Optional[str] = None
    phases_completed: List[str] = None
    spec_path: Optional[str] = None
    dependencies: Dict[str, List[str]] = None
    worktree_base_path: Optional[str] = None
    status_reports: Dict[str, Dict[str, Any]] = None
    batch_id: Optional[str] = None
    worktrees: Dict[str, str] = None  # Role to worktree path mapping
    
    def __post_init__(self):
        """Initialize mutable default values"""
        if self.phases_completed is None:
            self.phases_completed = []
        if self.dependencies is None:
            self.dependencies = {}
        if self.status_reports is None:
            self.status_reports = {}
        if self.worktrees is None:
            self.worktrees = {}


class SessionManager:
    """
    Manages orchestration session lifecycle and state.
    
    Provides functionality for:
    - Creating new orchestration sessions
    - Persisting session state to disk
    - Loading and resuming existing sessions
    - Managing agent states and health
    - Session validation and recovery
    """
    
    def __init__(self, tmux_orchestrator_path: Path):
        """
        Initialize session manager.
        
        Args:
            tmux_orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.registry_dir = tmux_orchestrator_path / 'registry'
        
        # Initialize git coordinator if available
        try:
            # TODO: Import GitCoordinator when git module is implemented
            self.git_coordinator = None  # GitCoordinator(tmux_orchestrator_path)
        except ImportError:
            self.git_coordinator = None
    
    def create_session_state(self,
                           session_name: str,
                           project_path: Path,
                           project_name: str,
                           spec_path: Path,
                           agents_config: Dict[str, Any]) -> SessionState:
        """
        Create a new session state.
        
        Args:
            session_name: Unique session name
            project_path: Path to the project
            project_name: Display name for the project
            spec_path: Path to specification file
            agents_config: Agent configuration dictionary
            
        Returns:
            SessionState: New session state instance
        """
        console.print(f"[blue]Creating session state for {project_name}[/blue]")
        
        # Create agent states
        agents = {}
        for role, config in agents_config.items():
            agents[role] = AgentState(
                role=role,
                window_index=config.get('window_index', 0),
                window_name=config.get('window_name', role.title()),
                worktree_path=config.get('worktree_path', f'/tmp/{role}-worktree'),
                current_branch=config.get('branch', 'main')
            )
        
        session_state = SessionState(
            session_name=session_name,
            project_path=str(project_path),
            project_name=project_name,
            implementation_spec_path=str(spec_path),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            agents=agents,
            spec_path=str(spec_path)
        )
        
        console.print(f"[green]✓ Session state created with {len(agents)} agents[/green]")
        return session_state
    
    def save_session_state(self, state: SessionState) -> bool:
        """
        Save session state to disk.
        
        Args:
            state: Session state to save
            
        Returns:
            bool: True if save was successful
        """
        try:
            state.updated_at = datetime.now().isoformat()
            state_file = self.get_state_file_path(state.project_name)
            state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dict for JSON serialization
            state_dict = asdict(state)
            
            # Convert agent states to dicts
            state_dict['agents'] = {
                role: asdict(agent) for role, agent in state.agents.items()
            }
            
            with open(state_file, 'w') as f:
                json.dump(state_dict, f, indent=2)
            
            console.print(f"[green]✓ Session state saved to {state_file}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Failed to save session state: {e}[/red]")
            return False
    
    def load_session_state(self, project_name: str) -> Optional[SessionState]:
        """
        Load session state from disk.
        
        Args:
            project_name: Project name to load
            
        Returns:
            SessionState if found, None otherwise
        """
        try:
            state_file = self.get_state_file_path(project_name)
            
            if not state_file.exists():
                console.print(f"[yellow]No session state found for {project_name}[/yellow]")
                return None
            
            with open(state_file, 'r') as f:
                state_dict = json.load(f)
            
            # Convert agent dicts back to AgentState objects
            agents = {}
            for role, agent_dict in state_dict['agents'].items():
                agents[role] = AgentState(**agent_dict)
            
            state_dict['agents'] = agents
            session_state = SessionState(**state_dict)
            
            console.print(f"[green]✓ Loaded session state for {project_name}[/green]")
            return session_state
            
        except Exception as e:
            console.print(f"[red]❌ Failed to load session state for {project_name}: {e}[/red]")
            return None
    
    def get_state_file_path(self, project_name: str) -> Path:
        """Get the path to the session state file for a project"""
        project_dir = self.registry_dir / 'projects' / project_name.lower().replace(' ', '-')
        return project_dir / 'session_state.json'
    
    def update_agent_status(self, session_state: SessionState, session_name: str) -> SessionState:
        """
        Update agent status by checking tmux windows.
        
        Args:
            session_state: Current session state
            session_name: Tmux session name
            
        Returns:
            Updated session state
        """
        console.print(f"[cyan]Updating agent status for session {session_name}[/cyan]")
        
        for role, agent in session_state.agents.items():
            # Check if tmux window exists and is responsive
            try:
                result = subprocess.run([
                    'tmux', 'display-message', '-t', 
                    f'{session_name}:{agent.window_index}'
                ], capture_output=True, stderr=subprocess.DEVNULL, timeout=5)
                
                agent.is_alive = (result.returncode == 0)
                
                if agent.is_alive:
                    # Try to get current branch info
                    try:
                        worktree_path = Path(agent.worktree_path)
                        if worktree_path.exists():
                            branch_result = subprocess.run([
                                'git', '-C', str(worktree_path), 'rev-parse', '--abbrev-ref', 'HEAD'
                            ], capture_output=True, text=True, timeout=3)
                            
                            if branch_result.returncode == 0:
                                agent.current_branch = branch_result.stdout.strip()
                    except Exception:
                        pass  # Branch detection is nice-to-have
                        
            except Exception as e:
                console.print(f"[yellow]Warning: Could not check status for {role}: {e}[/yellow]")
                agent.is_alive = False
        
        # Update session timestamp
        session_state.updated_at = datetime.now().isoformat()
        
        alive_count = sum(1 for agent in session_state.agents.values() if agent.is_alive)
        total_count = len(session_state.agents)
        console.print(f"[green]✓ Agent status updated: {alive_count}/{total_count} alive[/green]")
        
        return session_state
    
    def get_session_summary(self, session_state: SessionState) -> Dict[str, Any]:
        """
        Get a summary of the session state.
        
        Args:
            session_state: Session state to summarize
            
        Returns:
            Dict containing session summary
        """
        agents_summary = {}
        
        for role, agent in session_state.agents.items():
            agents_summary[role] = {
                'window': agent.window_index,
                'alive': agent.is_alive,
                'exhausted': agent.is_exhausted,
                'branch': agent.current_branch,
                'worktree': agent.worktree_path,
                'last_check_in': agent.last_check_in_time
            }
        
        return {
            'session_name': session_state.session_name,
            'project_name': session_state.project_name,
            'created_at': session_state.created_at,
            'updated_at': session_state.updated_at,
            'completion_status': session_state.completion_status,
            'agents': agents_summary,
            'alive_agents': sum(1 for agent in session_state.agents.values() if agent.is_alive),
            'total_agents': len(session_state.agents)
        }
    
    def validate_session_integrity(self, session_state: SessionState) -> Tuple[bool, List[str]]:
        """
        Validate session integrity and identify issues.
        
        Args:
            session_state: Session state to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check if tmux session exists
        try:
            result = subprocess.run([
                'tmux', 'has-session', '-t', session_state.session_name
            ], capture_output=True, timeout=5)
            
            if result.returncode != 0:
                issues.append(f"Tmux session '{session_state.session_name}' does not exist")
        except Exception as e:
            issues.append(f"Cannot check tmux session: {e}")
        
        # Check agent worktrees exist
        for role, agent in session_state.agents.items():
            worktree_path = Path(agent.worktree_path)
            if not worktree_path.exists():
                issues.append(f"Worktree missing for {role}: {worktree_path}")
            elif not (worktree_path / '.git').exists():
                issues.append(f"Invalid git worktree for {role}: {worktree_path}")
        
        # Check implementation spec exists
        if not Path(session_state.implementation_spec_path).exists():
            issues.append(f"Implementation spec missing: {session_state.implementation_spec_path}")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active orchestration sessions.
        
        Returns:
            List of session summaries
        """
        sessions = []
        projects_dir = self.registry_dir / 'projects'
        
        if not projects_dir.exists():
            return sessions
        
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                state_file = project_dir / 'session_state.json'
                if state_file.exists():
                    try:
                        session_state = self.load_session_state(project_dir.name)
                        if session_state:
                            summary = self.get_session_summary(session_state)
                            sessions.append(summary)
                    except Exception as e:
                        console.print(f"[yellow]Warning: Could not load session for {project_dir.name}: {e}[/yellow]")
        
        return sessions
    
    def cleanup_session_state(self, project_name: str) -> bool:
        """
        Clean up session state files.
        
        Args:
            project_name: Project to clean up
            
        Returns:
            bool: True if cleanup was successful
        """
        try:
            state_file = self.get_state_file_path(project_name)
            if state_file.exists():
                state_file.unlink()
                console.print(f"[green]✓ Cleaned up session state for {project_name}[/green]")
            
            # Clean up project directory if empty
            project_dir = state_file.parent
            if project_dir.exists() and not any(project_dir.iterdir()):
                project_dir.rmdir()
                console.print(f"[green]✓ Cleaned up empty project directory[/green]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Failed to cleanup session state: {e}[/red]")
            return False


def create_initial_session_state(session_name: str,
                                project_path: Path,
                                project_name: str,
                                spec_path: Path,
                                agents_config: Dict[str, Any]) -> SessionState:
    """
    Convenience function to create initial session state.
    
    This function provides compatibility with the original auto_orchestrate.py
    while using the new modular session management.
    
    Args:
        session_name: Unique session name
        project_path: Path to project
        project_name: Display name
        spec_path: Path to specification file
        agents_config: Agent configuration
        
    Returns:
        SessionState: New session state
    """
    # This is a compatibility wrapper that can be used during migration
    manager = SessionManager(Path(__file__).parent.parent.parent)
    return manager.create_session_state(
        session_name=session_name,
        project_path=project_path,
        project_name=project_name,
        spec_path=spec_path,
        agents_config=agents_config
    )
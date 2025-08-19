#!/usr/bin/env python3
"""
Session state management for Tmux Orchestrator
Tracks active orchestration sessions and enables proper resume functionality
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


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
    phases_completed: List[str] = None  # Track completed implementation phases
    spec_path: Optional[str] = None  # Path to spec file for notifications
    dependencies: Dict[str, List[str]] = None  # Role dependencies (e.g., {'pm': ['devops']})
    worktree_base_path: Optional[str] = None  # Custom base path for worktrees (overrides registry default)
    
    def __post_init__(self):
        """Initialize mutable default values"""
        if self.phases_completed is None:
            self.phases_completed = []
        if self.dependencies is None:
            self.dependencies = {}
    

class SessionStateManager:
    """Manages session state persistence and recovery"""
    
    def __init__(self, tmux_orchestrator_path: Path):
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.registry_dir = tmux_orchestrator_path / 'registry'
        
    def get_state_file_path(self, project_name: str) -> Path:
        """Get the path to the session state file for a project"""
        project_dir = self.registry_dir / 'projects' / project_name.lower().replace(' ', '-')
        return project_dir / 'session_state.json'
        
    def save_session_state(self, state: SessionState) -> None:
        """Save session state to disk"""
        state.updated_at = datetime.now().isoformat()
        state_file = self.get_state_file_path(state.project_name)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict for JSON serialization
        state_dict = asdict(state)
        
        # Convert agent states to dicts
        state_dict['agents'] = {
            role: asdict(agent) for role, agent in state.agents.items()
        }
        
        state_file.write_text(json.dumps(state_dict, indent=2))
        
    def load_session_state(self, project_name: str) -> Optional[SessionState]:
        """Load session state from disk with fallback creation"""
        state_file = self.get_state_file_path(project_name)
        
        if not state_file.exists():
            # Try to create minimal state if this looks like an active project
            return self._create_fallback_state(project_name)
            
        try:
            state_dict = json.loads(state_file.read_text())
            
            # Reconstruct agent states
            agents = {}
            for role, agent_dict in state_dict['agents'].items():
                agents[role] = AgentState(**agent_dict)
                
            state_dict['agents'] = agents
            
            return SessionState(**state_dict)
            
        except Exception as e:
            print(f"Error loading session state: {e}")
            # Try fallback creation
            return self._create_fallback_state(project_name)
    
    def _create_fallback_state(self, project_name: str) -> Optional[SessionState]:
        """Create minimal fallback state by detecting active tmux session"""
        try:
            # Try to find the session name from project name
            session_name = f"{project_name.lower().replace(' ', '-')}-impl"
            
            # Check if tmux session exists
            result = subprocess.run(
                ['tmux', 'list-sessions', '-f', f"#{{{session_name}}}"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                # Try alternate session names
                for suffix in ['-a9601f5d', '', '-impl-a9601f5d']:
                    alt_session = f"{project_name.lower().replace(' ', '-')}{suffix}"
                    result = subprocess.run(
                        ['tmux', 'has-session', '-t', alt_session],
                        capture_output=True
                    )
                    if result.returncode == 0:
                        session_name = alt_session
                        break
                else:
                    return None
            
            # Get window list to detect agents
            result = subprocess.run(
                ['tmux', 'list-windows', '-t', session_name, '-F', '#{window_index}:#{window_name}'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return None
            
            # Create minimal agent states from windows
            agents = {}
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                if ':' in line:
                    window_index, window_name = line.split(':', 1)
                    try:
                        index = int(window_index)
                        # Map common window names to roles
                        role = self._map_window_to_role(window_name)
                        if role:
                            agents[role] = AgentState(
                                role=role,
                                window_index=index,
                                window_name=window_name,
                                worktree_path="",  # Will be updated later
                                last_briefing_time=datetime.now().isoformat(),
                                is_alive=True,
                                is_exhausted=False
                            )
                    except ValueError:
                        continue
            
            if not agents:
                return None
            
            # Create minimal session state
            fallback_state = SessionState(
                session_name=session_name,
                project_path="",  # Will be detected later
                project_name=project_name,
                implementation_spec_path="",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                agents=agents,
                completion_status="pending"
            )
            
            # Save the fallback state
            self.save_session_state(fallback_state)
            print(f"Created fallback state for {project_name} with {len(agents)} agents")
            
            return fallback_state
            
        except Exception as e:
            print(f"Failed to create fallback state for {project_name}: {e}")
            return None
    
    def _map_window_to_role(self, window_name: str) -> Optional[str]:
        """Map tmux window names to agent roles"""
        name_lower = window_name.lower()
        
        # Common mappings
        role_mappings = {
            'orchestrator': 'orchestrator',
            'project-manager': 'project_manager', 
            'pm': 'project_manager',
            'developer': 'developer', 
            'dev': 'developer',
            'tester': 'tester',
            'test': 'tester',
            'testrunner': 'testrunner',
            'test-runner': 'testrunner',
            'researcher': 'researcher',
            'devops': 'devops',
            'sysadmin': 'sysadmin',
            'securityops': 'securityops',
            'networkops': 'networkops',
            'monitoringops': 'monitoringops',
            'databaseops': 'databaseops'
        }
        
        for pattern, role in role_mappings.items():
            if pattern in name_lower:
                return role
        
        return None
            
    def check_agent_alive(self, session_name: str, window_index: int) -> bool:
        """Check if an agent is alive and responsive"""
        try:
            # Capture last 50 lines from the pane
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', f'{session_name}:{window_index}', '-p', '-S', '-50'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return False
                
            pane_text = result.stdout.lower()
            
            # Check for various Claude UI indicators
            claude_indicators = [
                'human:',
                'assistant:',
                '? for shortcuts',
                'bypassing permissions',
                '> ',  # Claude's input prompt
                '│ >',  # Claude's input prompt in box
                'tokens used:',
                'context window:',
                '/exit to quit'
            ]
            
            # Check if any Claude indicator is present
            for indicator in claude_indicators:
                if indicator in pane_text:
                    return True
                    
            # Also check for the box-drawing characters that Claude uses
            if '╭' in pane_text or '│' in pane_text or '╰' in pane_text:
                # Likely Claude's UI
                return True
                    
            return False
            
        except Exception:
            return False
            
    def check_agent_exhausted(self, session_name: str, window_index: int) -> tuple[bool, Optional[str]]:
        """Check if an agent is credit exhausted and get reset time"""
        try:
            # Capture last 100 lines to find exhaustion messages
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', f'{session_name}:{window_index}', '-p', '-S', '-100'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return False, None
                
            pane_text = result.stdout
            
            # Check for exhaustion indicators
            is_exhausted = '/upgrade' in pane_text.lower() or 'approaching usage limit' in pane_text.lower()
            
            # Try to extract reset time
            reset_time = None
            for line in pane_text.split('\n'):
                if 'credits will reset at' in line.lower():
                    # Extract time from the line
                    parts = line.split('reset at')
                    if len(parts) > 1:
                        reset_time = parts[1].strip()
                        break
                        
            return is_exhausted, reset_time
            
        except Exception:
            return False, None
            
    def get_agent_git_status(self, worktree_path: str) -> tuple[Optional[str], Optional[str]]:
        """Get current branch and commit hash for an agent's worktree"""
        try:
            # Get current branch
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            branch = result.stdout.strip() if result.returncode == 0 else None
            
            # Get current commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            commit = result.stdout.strip()[:8] if result.returncode == 0 else None
            
            return branch, commit
            
        except Exception:
            return None, None
            
    def update_agent_status(self, state: SessionState, session_name: str) -> SessionState:
        """Update the status of all agents in the session"""
        for role, agent in state.agents.items():
            # Check if agent is alive
            agent.is_alive = self.check_agent_alive(session_name, agent.window_index)
            
            # Check if agent is exhausted
            agent.is_exhausted, agent.credit_reset_time = self.check_agent_exhausted(
                session_name, agent.window_index
            )
            
            # Update git status
            if agent.worktree_path and Path(agent.worktree_path).exists():
                agent.current_branch, agent.commit_hash = self.get_agent_git_status(
                    agent.worktree_path
                )
                
            # Update last check time
            agent.last_check_in_time = datetime.now().isoformat()
            
        state.updated_at = datetime.now().isoformat()
        return state
        
    def get_session_summary(self, state: SessionState) -> Dict[str, Any]:
        """Get a summary of the session state for display"""
        total_agents = len(state.agents)
        alive_agents = sum(1 for a in state.agents.values() if a.is_alive)
        exhausted_agents = sum(1 for a in state.agents.values() if a.is_exhausted)
        
        return {
            'session_name': state.session_name,
            'project_name': state.project_name,
            'created_at': state.created_at,
            'updated_at': state.updated_at,
            'total_agents': total_agents,
            'alive_agents': alive_agents,
            'exhausted_agents': exhausted_agents,
            'dead_agents': total_agents - alive_agents,
            'project_size': state.project_size,
            'agents': {
                role: {
                    'alive': agent.is_alive,
                    'exhausted': agent.is_exhausted,
                    'window': agent.window_index,
                    'branch': agent.current_branch,
                    'worktree': agent.worktree_path
                }
                for role, agent in state.agents.items()
            }
        }
    
    def update_agent_state(self, project_name: str, role: str, updates: Dict[str, Any]) -> None:
        """Update an agent's state and check dependencies"""
        state = self.load_session_state(project_name)
        if not state or role not in state.agents:
            return
            
        # Update the agent's attributes
        agent = state.agents[role]
        for key, value in updates.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
            
        # Save updated state
        self.save_session_state(state)
        
        # Check if this update resolves any dependencies
        self._check_dependencies(state, role)
    
    def _check_dependencies(self, state: SessionState, updated_role: str) -> None:
        """Check if updating a role resolves dependencies for other roles"""
        for dependent_role, required_roles in state.dependencies.items():
            if updated_role in required_roles:
                # Check if all dependencies are now satisfied
                all_satisfied = all(
                    self._is_role_complete(state, req_role) 
                    for req_role in required_roles
                )
                
                if all_satisfied:
                    # Notify the dependent role
                    self._notify_agent(state, dependent_role, 
                                     f"All dependencies satisfied! {updated_role} has completed.")
    
    def _is_role_complete(self, state: SessionState, role: str) -> bool:
        """Check if a role has completed its tasks"""
        if role not in state.agents:
            return False
            
        agent = state.agents[role]
        # Check various completion indicators
        if hasattr(agent, 'completion_status') and agent.completion_status == 'completed':
            return True
            
        # Check if recently active (within last 30 minutes)
        if agent.last_check_in_time:
            try:
                last_checkin = datetime.fromisoformat(agent.last_check_in_time)
                if (datetime.now() - last_checkin).total_seconds() < 1800:
                    return True
            except:
                pass
                
        return False
    
    def _notify_agent(self, state: SessionState, role: str, message: str) -> None:
        """Send a notification to an agent via tmux"""
        if role not in state.agents:
            return
            
        agent = state.agents[role]
        try:
            # Use send-claude-message.sh if available
            send_script = self.tmux_orchestrator_path / "send-claude-message.sh"
            if send_script.exists():
                cmd = [str(send_script), 
                       f"{state.session_name}:{agent.window_index}", 
                       message]
                subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:
            print(f"Error notifying {role}: {e}")
    
    def set_role_dependencies(self, project_name: str, dependencies: Dict[str, List[str]]) -> None:
        """Set role dependencies for a project"""
        state = self.load_session_state(project_name)
        if state:
            state.dependencies = dependencies
            self.save_session_state(state)


def create_initial_session_state(
    session_name: str,
    project_path: str,
    project_name: str,
    implementation_spec_path: str,
    agents: List[tuple[str, int, str]],  # (window_name, window_index, role)
    worktree_paths: Dict[str, Path],
    project_size: str = "medium",
    parent_branch: Optional[str] = None,
    spec_path: Optional[str] = None,
    worktree_base_path: Optional[str] = None
) -> SessionState:
    """Create initial session state from orchestration setup"""
    
    agent_states = {}
    
    for window_name, window_index, role in agents:
        worktree_path = worktree_paths.get(role)
        agent_states[role] = AgentState(
            role=role,
            window_index=window_index,
            window_name=window_name,
            worktree_path=str(worktree_path) if worktree_path else "",
            last_briefing_time=datetime.now().isoformat(),
            is_alive=True,
            is_exhausted=False
        )
        
    return SessionState(
        session_name=session_name,
        project_path=project_path,
        project_name=project_name,
        implementation_spec_path=implementation_spec_path,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        agents=agent_states,
        project_size=project_size,
        parent_branch=parent_branch,
        spec_path=spec_path,
        worktree_base_path=worktree_base_path
    )
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
    
    def __post_init__(self):
        """Initialize mutable default values"""
        if self.phases_completed is None:
            self.phases_completed = []
    

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
        """Load session state from disk"""
        state_file = self.get_state_file_path(project_name)
        
        if not state_file.exists():
            return None
            
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


def create_initial_session_state(
    session_name: str,
    project_path: str,
    project_name: str,
    implementation_spec_path: str,
    agents: List[tuple[str, int, str]],  # (window_name, window_index, role)
    worktree_paths: Dict[str, Path],
    project_size: str = "medium",
    parent_branch: Optional[str] = None,
    spec_path: Optional[str] = None
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
        spec_path=spec_path
    )
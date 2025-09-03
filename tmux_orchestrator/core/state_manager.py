"""
State Management Module

Handles state persistence, recovery, and coordination across the orchestration system.
Provides centralized state management for projects, agents, and system components.
"""

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from rich.console import Console

from .session_manager import SessionState, AgentState

console = Console()


class StateManager:
    """
    Centralized state management for the Tmux Orchestrator system.
    
    Handles:
    - Global system state tracking
    - State synchronization across components
    - State persistence and recovery
    - State consistency validation
    - Concurrent access coordination
    """
    
    def __init__(self, tmux_orchestrator_path: Path):
        """
        Initialize state manager.
        
        Args:
            tmux_orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.registry_dir = tmux_orchestrator_path / 'registry'
        self.state_dir = self.registry_dir / 'state'
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory state cache
        self._sessions_cache: Dict[str, SessionState] = {}
        self._global_state: Dict[str, Any] = {}
        self._state_lock = threading.RLock()
        
        # Initialize global state
        self._load_global_state()
    
    def get_global_state(self, key: str, default: Any = None) -> Any:
        """
        Get a global state value.
        
        Args:
            key: State key
            default: Default value if key doesn't exist
            
        Returns:
            State value or default
        """
        with self._state_lock:
            return self._global_state.get(key, default)
    
    def set_global_state(self, key: str, value: Any) -> None:
        """
        Set a global state value.
        
        Args:
            key: State key
            value: Value to set
        """
        with self._state_lock:
            self._global_state[key] = value
            self._global_state['updated_at'] = datetime.now().isoformat()
            self._save_global_state()
    
    def update_global_state(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple global state values atomically.
        
        Args:
            updates: Dictionary of key-value pairs to update
        """
        with self._state_lock:
            self._global_state.update(updates)
            self._global_state['updated_at'] = datetime.now().isoformat()
            self._save_global_state()
    
    def get_active_sessions(self) -> Dict[str, SessionState]:
        """
        Get all active sessions from cache.
        
        Returns:
            Dict of session_name -> SessionState
        """
        with self._state_lock:
            return self._sessions_cache.copy()
    
    def cache_session_state(self, session_state: SessionState) -> None:
        """
        Cache a session state in memory.
        
        Args:
            session_state: Session state to cache
        """
        with self._state_lock:
            self._sessions_cache[session_state.session_name] = session_state
    
    def get_cached_session(self, session_name: str) -> Optional[SessionState]:
        """
        Get a cached session state.
        
        Args:
            session_name: Session name to retrieve
            
        Returns:
            SessionState if cached, None otherwise
        """
        with self._state_lock:
            return self._sessions_cache.get(session_name)
    
    def remove_cached_session(self, session_name: str) -> bool:
        """
        Remove a session from cache.
        
        Args:
            session_name: Session to remove
            
        Returns:
            True if session was cached and removed
        """
        with self._state_lock:
            return self._sessions_cache.pop(session_name, None) is not None
    
    def track_agent_dependency(self, 
                             session_name: str,
                             dependent_role: str, 
                             dependency_role: str) -> None:
        """
        Track agent dependency relationships.
        
        Args:
            session_name: Session name
            dependent_role: Role that depends on another
            dependency_role: Role that is depended upon
        """
        key = f"dependencies_{session_name}"
        dependencies = self.get_global_state(key, {})
        
        if dependent_role not in dependencies:
            dependencies[dependent_role] = []
        
        if dependency_role not in dependencies[dependent_role]:
            dependencies[dependent_role].append(dependency_role)
        
        self.set_global_state(key, dependencies)
        console.print(f"[cyan]Tracked dependency: {dependent_role} depends on {dependency_role}[/cyan]")
    
    def get_agent_dependencies(self, session_name: str, role: str) -> List[str]:
        """
        Get dependencies for a specific agent role.
        
        Args:
            session_name: Session name
            role: Agent role
            
        Returns:
            List of roles this agent depends on
        """
        key = f"dependencies_{session_name}"
        dependencies = self.get_global_state(key, {})
        return dependencies.get(role, [])
    
    def track_completion_marker(self, 
                              session_name: str,
                              role: str, 
                              marker_path: Path,
                              completion_details: str) -> None:
        """
        Track agent completion markers.
        
        Args:
            session_name: Session name
            role: Agent role that completed
            marker_path: Path to completion marker file
            completion_details: Details about the completion
        """
        key = f"completions_{session_name}"
        completions = self.get_global_state(key, {})
        
        completions[role] = {
            'timestamp': datetime.now().isoformat(),
            'marker_path': str(marker_path),
            'details': completion_details,
            'verified': marker_path.exists()
        }
        
        self.set_global_state(key, completions)
        console.print(f"[green]✓ Tracked completion for {role}: {completion_details}[/green]")
    
    def get_session_completions(self, session_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all completion markers for a session.
        
        Args:
            session_name: Session name
            
        Returns:
            Dict of role -> completion info
        """
        key = f"completions_{session_name}"
        return self.get_global_state(key, {})
    
    def track_oauth_port_usage(self, port: int, process_info: str, session_name: str = None) -> None:
        """
        Track OAuth port usage for conflict prevention.
        
        Args:
            port: OAuth port number
            process_info: Information about the process using the port
            session_name: Optional session name for context
        """
        key = f"oauth_port_{port}"
        usage_info = {
            'timestamp': datetime.now().isoformat(),
            'process_info': process_info,
            'session_name': session_name
        }
        
        self.set_global_state(key, usage_info)
        console.print(f"[yellow]Tracked OAuth port {port} usage: {process_info}[/yellow]")
    
    def clear_oauth_port_usage(self, port: int) -> None:
        """
        Clear OAuth port usage tracking.
        
        Args:
            port: Port to clear
        """
        key = f"oauth_port_{port}"
        self.set_global_state(key, None)
        console.print(f"[green]Cleared OAuth port {port} usage tracking[/green]")
    
    def get_oauth_port_status(self, port: int) -> Optional[Dict[str, Any]]:
        """
        Get OAuth port usage status.
        
        Args:
            port: Port to check
            
        Returns:
            Usage info if port is tracked as in use, None otherwise
        """
        key = f"oauth_port_{port}"
        return self.get_global_state(key)
    
    def track_credit_exhaustion(self, 
                              session_name: str,
                              role: str, 
                              reset_time: str) -> None:
        """
        Track agent credit exhaustion.
        
        Args:
            session_name: Session name
            role: Agent role
            reset_time: When credits will reset
        """
        key = f"credits_{session_name}"
        credits = self.get_global_state(key, {})
        
        credits[role] = {
            'exhausted_at': datetime.now().isoformat(),
            'reset_time': reset_time,
            'auto_resume_scheduled': True
        }
        
        self.set_global_state(key, credits)
        console.print(f"[yellow]Tracked credit exhaustion for {role}, reset at {reset_time}[/yellow]")
    
    def get_exhausted_agents(self, session_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all exhausted agents for a session.
        
        Args:
            session_name: Session name
            
        Returns:
            Dict of role -> credit info
        """
        key = f"credits_{session_name}"
        return self.get_global_state(key, {})
    
    def clear_credit_exhaustion(self, session_name: str, role: str) -> None:
        """
        Clear credit exhaustion tracking for an agent.
        
        Args:
            session_name: Session name
            role: Agent role
        """
        key = f"credits_{session_name}"
        credits = self.get_global_state(key, {})
        
        if role in credits:
            del credits[role]
            self.set_global_state(key, credits)
            console.print(f"[green]Cleared credit exhaustion for {role}[/green]")
    
    def get_system_health_status(self) -> Dict[str, Any]:
        """
        Get overall system health status.
        
        Returns:
            Dict containing system health information
        """
        with self._state_lock:
            active_sessions = len(self._sessions_cache)
            
            # Count agents by status
            total_agents = 0
            alive_agents = 0
            exhausted_agents = 0
            
            for session_state in self._sessions_cache.values():
                for agent in session_state.agents.values():
                    total_agents += 1
                    if agent.is_alive:
                        alive_agents += 1
                    if agent.is_exhausted:
                        exhausted_agents += 1
            
            return {
                'timestamp': datetime.now().isoformat(),
                'active_sessions': active_sessions,
                'total_agents': total_agents,
                'alive_agents': alive_agents,
                'exhausted_agents': exhausted_agents,
                'system_load': self._calculate_system_load(),
                'oauth_conflicts': self._count_oauth_conflicts(),
                'registry_size': self._get_registry_size()
            }
    
    def cleanup_stale_state(self, max_age_hours: int = 24) -> int:
        """
        Clean up stale state entries.
        
        Args:
            max_age_hours: Maximum age in hours before state is considered stale
            
        Returns:
            Number of entries cleaned up
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        with self._state_lock:
            # Clean up global state entries with timestamps
            keys_to_remove = []
            for key, value in self._global_state.items():
                if isinstance(value, dict) and 'timestamp' in value:
                    try:
                        timestamp = datetime.fromisoformat(value['timestamp'])
                        if timestamp < cutoff_time:
                            keys_to_remove.append(key)
                    except (ValueError, TypeError):
                        pass  # Invalid timestamp format
            
            for key in keys_to_remove:
                del self._global_state[key]
                cleaned_count += 1
            
            if cleaned_count > 0:
                self._save_global_state()
        
        console.print(f"[green]✓ Cleaned up {cleaned_count} stale state entries[/green]")
        return cleaned_count
    
    def _load_global_state(self) -> None:
        """Load global state from disk."""
        global_state_file = self.state_dir / 'global_state.json'
        
        try:
            if global_state_file.exists():
                with open(global_state_file, 'r') as f:
                    self._global_state = json.load(f)
                console.print(f"[green]✓ Loaded global state from {global_state_file}[/green]")
            else:
                self._global_state = {
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                self._save_global_state()
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load global state: {e}[/yellow]")
            self._global_state = {
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
    
    def _save_global_state(self) -> None:
        """Save global state to disk."""
        global_state_file = self.state_dir / 'global_state.json'
        
        try:
            with open(global_state_file, 'w') as f:
                json.dump(self._global_state, f, indent=2)
        except Exception as e:
            console.print(f"[red]❌ Failed to save global state: {e}[/red]")
    
    def _calculate_system_load(self) -> str:
        """Calculate approximate system load based on active agents."""
        total_agents = sum(len(session.agents) for session in self._sessions_cache.values())
        
        if total_agents == 0:
            return "idle"
        elif total_agents <= 5:
            return "light"
        elif total_agents <= 15:
            return "moderate"
        elif total_agents <= 25:
            return "heavy"
        else:
            return "overloaded"
    
    def _count_oauth_conflicts(self) -> int:
        """Count active OAuth port conflicts."""
        conflicts = 0
        for key in self._global_state.keys():
            if key.startswith('oauth_port_') and self._global_state[key] is not None:
                conflicts += 1
        return conflicts
    
    def _get_registry_size(self) -> str:
        """Get approximate registry directory size."""
        try:
            total_size = sum(
                f.stat().st_size for f in self.registry_dir.rglob('*') if f.is_file()
            )
            
            if total_size < 1024 * 1024:  # < 1MB
                return f"{total_size // 1024}KB"
            elif total_size < 1024 * 1024 * 1024:  # < 1GB
                return f"{total_size // (1024 * 1024)}MB"
            else:
                return f"{total_size // (1024 * 1024 * 1024)}GB"
        except Exception:
            return "unknown"
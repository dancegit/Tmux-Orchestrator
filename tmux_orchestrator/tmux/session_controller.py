"""
Tmux Session Controller Module

Handles tmux session lifecycle management, window creation, and session coordination.
Provides high-level tmux operations for orchestration management.
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from rich.console import Console

from ..core.session_manager import SessionState, AgentState

console = Console()


class TmuxSessionController:
    """
    Controls tmux sessions for orchestration management.
    
    Provides functionality for:
    - Session creation and management
    - Window creation and organization  
    - Session health monitoring
    - Session cleanup and recovery
    - Multi-session coordination
    """
    
    def __init__(self, tmux_orchestrator_path: Path):
        """
        Initialize tmux session controller.
        
        Args:
            tmux_orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.tmux_orchestrator_path = tmux_orchestrator_path
        
        # Verify tmux is available
        self._verify_tmux_availability()
    
    def create_orchestration_session(self,
                                   session_name: str,
                                   agents: Dict[str, AgentState],
                                   base_directory: Optional[Path] = None) -> bool:
        """
        Create a new tmux session for orchestration.
        
        Args:
            session_name: Unique name for the tmux session
            agents: Dict of role -> AgentState for window creation
            base_directory: Base directory for the session
            
        Returns:
            bool: True if session creation succeeded
        """
        console.print(f"[blue]🚀 Creating tmux session: {session_name}[/blue]")
        
        try:
            # Check if session already exists
            if self.session_exists(session_name):
                console.print(f"[yellow]⚠️  Session {session_name} already exists[/yellow]")
                return False
            
            # Create base session
            base_dir = base_directory or Path.cwd()
            result = subprocess.run([
                'tmux', 'new-session', '-d', '-s', session_name, 
                '-c', str(base_dir)
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                console.print(f"[red]❌ Failed to create base session: {result.stderr}[/red]")
                return False
            
            # Rename the first window for orchestrator
            subprocess.run([
                'tmux', 'rename-window', '-t', f'{session_name}:0', 'Orchestrator'
            ], capture_output=True)
            
            # Create windows for all agents
            success_count = 0
            for role, agent in agents.items():
                if role != 'orchestrator':  # Orchestrator uses window 0
                    success = self.create_agent_window(
                        session_name=session_name,
                        window_index=agent.window_index,
                        window_name=agent.window_name,
                        working_directory=Path(agent.worktree_path)
                    )
                    if success:
                        success_count += 1
            
            console.print(f"[green]✅ Created session {session_name} with {success_count + 1} windows[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error creating session {session_name}: {e}[/red]")
            return False
    
    def create_agent_window(self,
                          session_name: str,
                          window_index: int,
                          window_name: str,
                          working_directory: Path) -> bool:
        """
        Create a tmux window for a specific agent.
        
        Args:
            session_name: Tmux session name
            window_index: Window index to create
            window_name: Display name for the window
            working_directory: Working directory for the window
            
        Returns:
            bool: True if window creation succeeded
        """
        try:
            console.print(f"[cyan]Creating window {window_index}: {window_name}[/cyan]")
            
            # Create window at specific index
            result = subprocess.run([
                'tmux', 'new-window', '-t', f'{session_name}:{window_index}',
                '-n', window_name, '-c', str(working_directory), '-d'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                console.print(f"[red]❌ Failed to create window {window_name}: {result.stderr}[/red]")
                return False
            
            console.print(f"[green]✓ Created window {window_index}: {window_name}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error creating window {window_name}: {e}[/red]")
            return False
    
    def kill_window(self, session_name: str, window_index: int) -> bool:
        """
        Kill a specific tmux window.
        
        Args:
            session_name: Tmux session name
            window_index: Window index to kill
            
        Returns:
            bool: True if kill succeeded
        """
        try:
            result = subprocess.run([
                'tmux', 'kill-window', '-t', f'{session_name}:{window_index}'
            ], capture_output=True, text=True)
            
            success = result.returncode == 0
            if success:
                console.print(f"[green]✓ Killed window {session_name}:{window_index}[/green]")
            else:
                console.print(f"[yellow]⚠️  Failed to kill window {session_name}:{window_index}: {result.stderr}[/yellow]")
            
            return success
            
        except Exception as e:
            console.print(f"[red]❌ Error killing window {session_name}:{window_index}: {e}[/red]")
            return False
    
    def recreate_window(self,
                       session_name: str,
                       window_index: int,
                       window_name: str,
                       working_directory: Path) -> bool:
        """
        Recreate a tmux window (kill then create).
        
        Args:
            session_name: Tmux session name
            window_index: Window index
            window_name: Window display name
            working_directory: Working directory
            
        Returns:
            bool: True if recreation succeeded
        """
        console.print(f"[yellow]🔄 Recreating window {session_name}:{window_index}[/yellow]")
        
        # Kill existing window (ignore errors)
        self.kill_window(session_name, window_index)
        
        # Small delay to ensure cleanup
        time.sleep(1)
        
        # Create new window
        return self.create_agent_window(
            session_name=session_name,
            window_index=window_index,
            window_name=window_name,
            working_directory=working_directory
        )
    
    def send_keys(self, target: str, keys: str, send_enter: bool = True) -> bool:
        """
        Send keys to a tmux window or pane.
        
        Args:
            target: Tmux target (session:window or session:window.pane)
            keys: Keys to send
            send_enter: Whether to send Enter key after
            
        Returns:
            bool: True if send succeeded
        """
        try:
            cmd = ['tmux', 'send-keys', '-t', target, keys]
            if send_enter:
                cmd.append('Enter')
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                console.print(f"[yellow]⚠️  Failed to send keys to {target}: {result.stderr}[/yellow]")
                return False
            
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error sending keys to {target}: {e}[/red]")
            return False
    
    def capture_pane(self, target: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """
        Capture content from a tmux pane.
        
        Args:
            target: Tmux target (session:window or session:window.pane)
            start_line: Optional start line (-S flag)
            end_line: Optional end line (-E flag)
            
        Returns:
            str: Captured content
        """
        try:
            cmd = ['tmux', 'capture-pane', '-t', target, '-p']
            
            if start_line is not None:
                cmd.extend(['-S', str(start_line)])
            if end_line is not None:
                cmd.extend(['-E', str(end_line)])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                console.print(f"[yellow]⚠️  Failed to capture pane {target}: {result.stderr}[/yellow]")
                return ""
            
            return result.stdout
            
        except Exception as e:
            console.print(f"[red]❌ Error capturing pane {target}: {e}[/red]")
            return ""
    
    def session_exists(self, session_name: str) -> bool:
        """
        Check if a tmux session exists.
        
        Args:
            session_name: Session name to check
            
        Returns:
            bool: True if session exists
        """
        try:
            result = subprocess.run([
                'tmux', 'has-session', '-t', session_name
            ], capture_output=True, stderr=subprocess.DEVNULL)
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def window_exists(self, session_name: str, window_index: int) -> bool:
        """
        Check if a specific window exists in a session.
        
        Args:
            session_name: Session name
            window_index: Window index to check
            
        Returns:
            bool: True if window exists
        """
        try:
            result = subprocess.run([
                'tmux', 'display-message', '-t', f'{session_name}:{window_index}'
            ], capture_output=True, stderr=subprocess.DEVNULL)
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active tmux sessions.
        
        Returns:
            List of session information dictionaries
        """
        try:
            result = subprocess.run([
                'tmux', 'list-sessions', '-F', 
                '#{session_name}|#{session_created}|#{session_last_attached}|#{?session_attached,attached,not attached}'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                return []
            
            sessions = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 4:
                        sessions.append({
                            'name': parts[0],
                            'created': parts[1],
                            'last_attached': parts[2],
                            'status': parts[3]
                        })
            
            return sessions
            
        except Exception as e:
            console.print(f"[yellow]⚠️  Error listing sessions: {e}[/yellow]")
            return []
    
    def list_windows(self, session_name: str) -> List[Dict[str, Any]]:
        """
        List windows in a specific session.
        
        Args:
            session_name: Session name
            
        Returns:
            List of window information dictionaries
        """
        try:
            result = subprocess.run([
                'tmux', 'list-windows', '-t', session_name, '-F',
                '#{window_index}|#{window_name}|#{window_activity}|#{?window_active,active,inactive}'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                return []
            
            windows = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 4:
                        windows.append({
                            'index': int(parts[0]),
                            'name': parts[1],
                            'activity': parts[2],
                            'status': parts[3]
                        })
            
            return windows
            
        except Exception as e:
            console.print(f"[yellow]⚠️  Error listing windows for {session_name}: {e}[/yellow]")
            return []
    
    def kill_session(self, session_name: str) -> bool:
        """
        Kill an entire tmux session.
        
        Args:
            session_name: Session name to kill
            
        Returns:
            bool: True if kill succeeded
        """
        try:
            result = subprocess.run([
                'tmux', 'kill-session', '-t', session_name
            ], capture_output=True, text=True)
            
            success = result.returncode == 0
            if success:
                console.print(f"[green]✓ Killed session {session_name}[/green]")
            else:
                console.print(f"[yellow]⚠️  Failed to kill session {session_name}: {result.stderr}[/yellow]")
            
            return success
            
        except Exception as e:
            console.print(f"[red]❌ Error killing session {session_name}: {e}[/red]")
            return False
    
    def attach_session(self, session_name: str, detach_others: bool = False) -> bool:
        """
        Attach to a tmux session.
        
        Args:
            session_name: Session to attach to
            detach_others: Whether to detach other clients
            
        Returns:
            bool: True if attach command was sent successfully
        """
        try:
            cmd = ['tmux', 'attach-session', '-t', session_name]
            if detach_others:
                cmd.append('-d')
            
            # This will typically not return if successful (takes over terminal)
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # If we get here, attachment failed
            console.print(f"[yellow]⚠️  Failed to attach to {session_name}: {result.stderr}[/yellow]")
            return False
            
        except Exception as e:
            console.print(f"[red]❌ Error attaching to session {session_name}: {e}[/red]")
            return False
    
    def get_session_health(self, session_state: SessionState) -> Dict[str, Any]:
        """
        Get health status for an orchestration session.
        
        Args:
            session_state: Session state to check
            
        Returns:
            Dict containing health information
        """
        health = {
            'session_name': session_state.session_name,
            'session_exists': False,
            'total_windows': len(session_state.agents),
            'active_windows': 0,
            'missing_windows': [],
            'responsive_agents': 0,
            'issues': []
        }
        
        try:
            # Check if session exists
            if not self.session_exists(session_state.session_name):
                health['issues'].append("Session does not exist")
                return health
            
            health['session_exists'] = True
            
            # Check each agent window
            for role, agent in session_state.agents.items():
                if self.window_exists(session_state.session_name, agent.window_index):
                    health['active_windows'] += 1
                    
                    # Test responsiveness with a simple command
                    if self._test_window_responsiveness(session_state.session_name, agent.window_index):
                        health['responsive_agents'] += 1
                    
                else:
                    health['missing_windows'].append(f"{role} (window {agent.window_index})")
            
            # Add health assessment
            if health['active_windows'] == health['total_windows']:
                if health['responsive_agents'] == health['total_windows']:
                    health['status'] = 'healthy'
                else:
                    health['status'] = 'degraded'
                    health['issues'].append(f"{health['total_windows'] - health['responsive_agents']} unresponsive agents")
            else:
                health['status'] = 'unhealthy'
                health['issues'].append(f"{len(health['missing_windows'])} missing windows")
            
        except Exception as e:
            health['issues'].append(f"Health check failed: {e}")
            health['status'] = 'unknown'
        
        return health
    
    def _verify_tmux_availability(self) -> None:
        """Verify that tmux is available and working."""
        try:
            result = subprocess.run(['tmux', '-V'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                console.print(f"[green]✓ Tmux available: {result.stdout.strip()}[/green]")
            else:
                console.print("[red]❌ Tmux not working properly[/red]")
                raise RuntimeError("Tmux not functional")
        except FileNotFoundError:
            console.print("[red]❌ Tmux not installed[/red]")
            raise RuntimeError("Tmux not installed")
        except Exception as e:
            console.print(f"[red]❌ Tmux verification failed: {e}[/red]")
            raise RuntimeError(f"Tmux verification failed: {e}")
    
    def _test_window_responsiveness(self, session_name: str, window_index: int, timeout: int = 5) -> bool:
        """Test if a window is responsive to commands."""
        try:
            # Send a simple echo command and capture output
            test_marker = f"tmux-test-{int(time.time())}"
            
            # Send echo command
            self.send_keys(f"{session_name}:{window_index}", f"echo {test_marker}", send_enter=True)
            
            # Wait a moment for output
            time.sleep(1)
            
            # Capture recent output
            output = self.capture_pane(f"{session_name}:{window_index}", start_line=-5)
            
            # Check if our test marker appears in output
            return test_marker in output
            
        except Exception:
            return False
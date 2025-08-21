#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
TmuxManager - Centralized tmux operations for Tmux Orchestrator

Provides a unified interface for all tmux operations including:
- Session management (create, kill, list)
- Message routing with validation
- Phantom session detection and cleanup
- Socket isolation for projects
- State reconciliation between database and tmux

This module replaces scattered tmux calls throughout the codebase
with a centralized, validated, and logged interface.
"""

import subprocess
import json
import time
import logging
import uuid
import os
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Set up logger for utility functions
logger = logging.getLogger(__name__)

# ============================================================================
# Enhanced TmuxManager Class - Primary Interface (Based on Grok's Recommendations)
# ============================================================================

class TmuxError(Exception):
    """Custom exception for tmux-related errors"""
    pass

class TmuxManager:
    """Centralized tmux operations manager with validation and logging"""
    
    def __init__(self, socket_path: Optional[str] = None):
        """
        Initialize TmuxManager
        
        Args:
            socket_path: Optional custom socket path for isolation
        """
        self.socket_path = socket_path
        self.base_cmd = ["tmux"]
        if socket_path:
            self.base_cmd.extend(["-S", socket_path])
            
        # Ensure socket directory exists if specified
        if socket_path:
            socket_dir = os.path.dirname(socket_path)
            os.makedirs(socket_dir, exist_ok=True)
    
    def _run_tmux_command(self, cmd: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
        """
        Run a tmux command with error handling
        
        Args:
            cmd: Command arguments (without 'tmux' prefix)
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            CompletedProcess result
            
        Raises:
            TmuxError: If tmux command fails
        """
        full_cmd = self.base_cmd + cmd
        
        try:
            result = subprocess.run(
                full_cmd,
                capture_output=capture_output,
                text=True,
                check=False
            )
            
            # Log the command for debugging
            logger.debug(f"Tmux command: {' '.join(full_cmd)}")
            if result.returncode != 0:
                logger.warning(f"Tmux command failed (rc={result.returncode}): {result.stderr}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to run tmux command {full_cmd}: {e}")
            raise TmuxError(f"Tmux command failed: {e}")
    
    def session_exists(self, session_name: str) -> bool:
        """
        Check if a tmux session exists
        
        Args:
            session_name: Name of the session to check
            
        Returns:
            True if session exists, False otherwise
        """
        try:
            result = self._run_tmux_command(["has-session", "-t", session_name])
            return result.returncode == 0
        except TmuxError:
            return False
    
    def window_exists(self, target: str) -> bool:
        """
        Check if a tmux window exists
        
        Args:
            target: session:window target (e.g., "mysession:0")
            
        Returns:
            True if window exists, False otherwise
        """
        try:
            result = self._run_tmux_command(["display-message", "-p", "-t", target, "#{window_name}"])
            return result.returncode == 0
        except TmuxError:
            return False
    
    def get_window_pid(self, target: str) -> Optional[int]:
        """
        Get the PID of a tmux window's process
        
        Args:
            target: session:window target
            
        Returns:
            PID as integer, or None if not found
        """
        try:
            result = self._run_tmux_command(["display-message", "-p", "-t", target, "#{pid}"])
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except (TmuxError, ValueError):
            pass
        return None
    
    def is_process_alive(self, pid: int) -> bool:
        """
        Check if a process is alive
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process is alive, False otherwise
        """
        try:
            result = subprocess.run(["ps", "-p", str(pid)], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False
    
    def send_message(self, target: str, message: str, validate: bool = True) -> bool:
        """
        Send a message to a tmux window with optional validation
        
        Args:
            target: session:window target
            message: Message to send
            validate: Whether to validate target before sending
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        # Validation checks (if enabled)
        if validate:
            # Check if target exists
            if not self.window_exists(target):
                logger.error(f"Target window {target} does not exist. Preventing phantom message routing.")
                return False
            
            # Check for self-messaging
            try:
                current_window = self._run_tmux_command(["display-message", "-p", "#{session_name}:#{window_index}"])
                if current_window.returncode == 0 and current_window.stdout.strip() == target:
                    logger.warning(f"Attempting to send message to self ({target}). Skipping to prevent feedback loop.")
                    return False
            except TmuxError:
                pass  # Continue if we can't determine current window
            
            # Check if target process is alive
            target_pid = self.get_window_pid(target)
            if target_pid is None:
                logger.error(f"Cannot get PID for target {target}. Target may be dead.")
                return False
            
            if not self.is_process_alive(target_pid):
                logger.error(f"Target process {target_pid} is dead. Preventing message to phantom session.")
                return False
        
        # Handle /compact command specially
        if "/compact" in message:
            return self._send_compact_message(target, message)
        else:
            return self._send_regular_message(target, message)
    
    def _send_regular_message(self, target: str, message: str) -> bool:
        """Send a regular message to tmux window"""
        try:
            # Send message
            result = self._run_tmux_command(["send-keys", "-t", target, message])
            if result.returncode != 0:
                return False
            
            time.sleep(0.5)
            
            # Send Enter
            result = self._run_tmux_command(["send-keys", "-t", target, "Enter"])
            if result.returncode == 0:
                logger.info(f"Message sent to {target}: {message}")
                return True
            
        except TmuxError as e:
            logger.error(f"Failed to send message to {target}: {e}")
        
        return False
    
    def _send_compact_message(self, target: str, message: str) -> bool:
        """Send message with /compact command handling"""
        try:
            # Extract message without /compact
            message_without_compact = message.replace("/compact", "").strip()
            message_without_compact = " ".join(message_without_compact.split())  # Clean whitespace
            
            # Send the main message if it's not empty
            if message_without_compact:
                if not self._send_regular_message(target, message_without_compact):
                    return False
                time.sleep(2)  # Wait for message to be processed
            
            # Send /compact as separate command
            result = self._run_tmux_command(["send-keys", "-t", target, "/compact"])
            if result.returncode != 0:
                return False
            
            time.sleep(0.5)
            result = self._run_tmux_command(["send-keys", "-t", target, "Enter"])
            
            if result.returncode == 0:
                logger.info(f"Compact command sent separately to {target}")
                return True
                
        except TmuxError as e:
            logger.error(f"Failed to send compact message to {target}: {e}")
        
        return False
    
    def create_session(self, session_name: str, working_dir: str = None, 
                      window_name: str = None, kill_existing: bool = False) -> bool:
        """
        Create a new tmux session
        
        Args:
            session_name: Name of the session to create
            working_dir: Working directory for the session
            window_name: Name for the initial window
            kill_existing: Whether to kill existing session with same name
            
        Returns:
            True if session was created successfully, False otherwise
        """
        # Check for existing session
        if self.session_exists(session_name):
            if kill_existing:
                logger.info(f"Killing existing session {session_name}")
                self.kill_session(session_name)
            else:
                logger.warning(f"Session {session_name} already exists")
                return False
        
        # Build create command
        cmd = ["new-session", "-d", "-s", session_name]
        
        if working_dir:
            cmd.extend(["-c", working_dir])
        
        if window_name:
            cmd.extend(["-n", window_name])
        
        try:
            result = self._run_tmux_command(cmd)
            if result.returncode == 0:
                logger.info(f"Created tmux session: {session_name}")
                return True
            else:
                logger.error(f"Failed to create session {session_name}: {result.stderr}")
                return False
        except TmuxError as e:
            logger.error(f"Failed to create session {session_name}: {e}")
            return False
    
    def kill_session(self, session_name: str) -> bool:
        """
        Kill a tmux session
        
        Args:
            session_name: Name of the session to kill
            
        Returns:
            True if session was killed successfully, False otherwise
        """
        try:
            result = self._run_tmux_command(["kill-session", "-t", session_name])
            if result.returncode == 0:
                logger.info(f"Killed tmux session: {session_name}")
                return True
            else:
                logger.warning(f"Failed to kill session {session_name}: {result.stderr}")
                return False
        except TmuxError as e:
            logger.error(f"Failed to kill session {session_name}: {e}")
            return False
    
    def list_sessions(self) -> List[Dict[str, str]]:
        """
        List all tmux sessions
        
        Returns:
            List of session dictionaries with name, created, and attached info
        """
        try:
            result = self._run_tmux_command([
                "list-sessions", 
                "-F", "#{session_name}|#{session_created}|#{session_attached}"
            ])
            
            if result.returncode != 0:
                return []
            
            sessions = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) == 3:
                        sessions.append({
                            'name': parts[0],
                            'created': parts[1],
                            'attached': parts[2] == '1'
                        })
            
            return sessions
            
        except TmuxError:
            return []
    
    def capture_pane(self, target: str, lines: int = None) -> str:
        """
        Capture content from a tmux pane
        
        Args:
            target: session:window target
            lines: Number of lines to capture (None for all)
            
        Returns:
            Captured content as string
        """
        try:
            cmd = ["capture-pane", "-t", target, "-p"]
            if lines:
                cmd.extend(["-S", f"-{lines}"])
            
            result = self._run_tmux_command(cmd)
            if result.returncode == 0:
                return result.stdout
            
        except TmuxError:
            pass
        
        return ""
    
    def kill_phantom_sessions(self, valid_sessions: List[str] = None) -> List[str]:
        """
        Kill phantom tmux sessions not in the valid list
        
        Args:
            valid_sessions: List of session names that should be kept
            
        Returns:
            List of killed session names
        """
        if valid_sessions is None:
            valid_sessions = []
        
        killed_sessions = []
        
        try:
            current_sessions = self.list_sessions()
            
            for session in current_sessions:
                session_name = session['name']
                
                # Skip if session is in valid list
                if session_name in valid_sessions:
                    continue
                
                # Kill phantom session
                if self.kill_session(session_name):
                    killed_sessions.append(session_name)
                    logger.info(f"Killed phantom session: {session_name}")
        
        except Exception as e:
            logger.error(f"Error during phantom session cleanup: {e}")
        
        return killed_sessions

class TmuxSocketManager:
    """Manages isolated tmux sockets for project separation"""
    
    def __init__(self, base_socket_dir: str = "/tmp/tmux-orchestrator"):
        """
        Initialize socket manager
        
        Args:
            base_socket_dir: Base directory for socket files
        """
        self.base_socket_dir = Path(base_socket_dir)
        self.base_socket_dir.mkdir(exist_ok=True)
    
    def get_project_socket(self, project_name: str) -> str:
        """
        Get the socket path for a project
        
        Args:
            project_name: Name of the project
            
        Returns:
            Socket file path
        """
        # Sanitize project name for filesystem
        safe_name = "".join(c for c in project_name if c.isalnum() or c in ('-', '_')).lower()
        socket_path = self.base_socket_dir / f"project-{safe_name}.sock"
        return str(socket_path)
    
    def get_manager_for_project(self, project_name: str) -> TmuxManager:
        """
        Get a TmuxManager instance for a specific project
        
        Args:
            project_name: Name of the project
            
        Returns:
            TmuxManager instance with isolated socket
        """
        socket_path = self.get_project_socket(project_name)
        return TmuxManager(socket_path=socket_path)
    
    def cleanup_project_socket(self, project_name: str) -> bool:
        """
        Clean up the socket file for a project
        
        Args:
            project_name: Name of the project
            
        Returns:
            True if cleanup was successful
        """
        try:
            socket_path = Path(self.get_project_socket(project_name))
            if socket_path.exists():
                socket_path.unlink()
                logger.info(f"Cleaned up socket for project: {project_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup socket for project {project_name}: {e}")
            return False

# ============================================================================
# Utility Functions for Session Management (Added for orchestrator automation)
# ============================================================================

def get_active_sessions() -> List[str]:
    """Get all active tmux sessions - centralized version"""
    try:
        result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        return []
    except Exception as e:
        logger.error(f"Failed to get active tmux sessions: {e}")
        return []

def session_exists(name: str) -> bool:
    """Check if tmux session exists"""
    try:
        result = subprocess.run(['tmux', 'has-session', '-t', name], 
                              capture_output=True, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Failed to check session existence: {e}")
        return False

def kill_session(name: str) -> bool:
    """Kill a tmux session if it exists"""
    try:
        if session_exists(name):
            result = subprocess.run(['tmux', 'kill-session', '-t', name], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Successfully killed session: {name}")
                return True
            else:
                logger.warning(f"Failed to kill session {name}: {result.stderr}")
                return False
        else:
            logger.debug(f"Session {name} does not exist, nothing to kill")
            return True
    except Exception as e:
        logger.error(f"Error killing session {name}: {e}")
        return False

def create_session(name: str, command: Optional[str] = None, working_dir: Optional[str] = None) -> bool:
    """Create a new tmux session"""
    try:
        cmd = ['tmux', 'new-session', '-d', '-s', name]
        if working_dir:
            cmd.extend(['-c', working_dir])
        if command:
            cmd.append(command)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Successfully created session: {name}")
            return True
        else:
            logger.error(f"Failed to create session {name}: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error creating session {name}: {e}")
        return False

def recreate_session(name: str, command: Optional[str] = None, working_dir: Optional[str] = None) -> bool:
    """Kill and recreate a tmux session"""
    logger.info(f"Recreating session: {name}")
    kill_session(name)
    return create_session(name, command, working_dir)

def send_keys(session: str, keys: str, window: int = 0) -> bool:
    """Send keys to a tmux session/window"""
    try:
        target = f"{session}:{window}"
        result = subprocess.run(['tmux', 'send-keys', '-t', target, keys, 'C-m'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            logger.debug(f"Sent keys to {target}: {keys}")
            return True
        else:
            logger.warning(f"Failed to send keys to {target}: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error sending keys to {session}: {e}")
        return False

def capture_pane(session: str, window: int = 0, lines: int = 50) -> str:
    """Capture output from a tmux pane"""
    try:
        target = f"{session}:{window}"
        result = subprocess.run(['tmux', 'capture-pane', '-t', target, '-p', '-S', f'-{lines}'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
        else:
            logger.warning(f"Failed to capture pane from {target}: {result.stderr}")
            return ""
    except Exception as e:
        logger.error(f"Error capturing pane from {session}: {e}")
        return ""

def generate_unique_session_name(base_name: str) -> str:
    """Generate a unique session name by checking existing sessions"""
    active_sessions = set(get_active_sessions())
    
    # Try base name first
    if base_name not in active_sessions:
        return base_name
    
    # Add short UUID if base name exists
    unique_name = f"{base_name}-{uuid.uuid4().hex[:8]}"
    retry_count = 0
    
    while unique_name in active_sessions and retry_count < 10:
        unique_name = f"{base_name}-{uuid.uuid4().hex[:8]}"
        retry_count += 1
    
    if retry_count >= 10:
        logger.warning(f"Could not generate unique name for {base_name}, using timestamp fallback")
        unique_name = f"{base_name}-{int(time.time())}"
    
    return unique_name

# ============================================================================
# Existing TmuxOrchestrator Class (Preserved for claude_control.py compatibility)
# ============================================================================

@dataclass
class TmuxWindow:
    session_name: str
    window_index: int
    window_name: str
    active: bool
    
@dataclass
class TmuxSession:
    name: str
    windows: List[TmuxWindow]
    attached: bool

class TmuxOrchestrator:
    def __init__(self):
        self.safety_mode = True
        self.max_lines_capture = 1000
        
    def get_tmux_sessions(self) -> List[TmuxSession]:
        """Get all tmux sessions and their windows"""
        try:
            # Get sessions
            sessions_cmd = ["tmux", "list-sessions", "-F", "#{session_name}:#{session_attached}"]
            sessions_result = subprocess.run(sessions_cmd, capture_output=True, text=True, check=True)
            
            sessions = []
            for line in sessions_result.stdout.strip().split('\n'):
                if not line:
                    continue
                session_name, attached = line.split(':')
                
                # Get windows for this session
                windows_cmd = ["tmux", "list-windows", "-t", session_name, "-F", "#{window_index}:#{window_name}:#{window_active}"]
                windows_result = subprocess.run(windows_cmd, capture_output=True, text=True, check=True)
                
                windows = []
                for window_line in windows_result.stdout.strip().split('\n'):
                    if not window_line:
                        continue
                    window_index, window_name, window_active = window_line.split(':')
                    windows.append(TmuxWindow(
                        session_name=session_name,
                        window_index=int(window_index),
                        window_name=window_name,
                        active=window_active == '1'
                    ))
                
                sessions.append(TmuxSession(
                    name=session_name,
                    windows=windows,
                    attached=attached == '1'
                ))
            
            return sessions
        except subprocess.CalledProcessError as e:
            print(f"Error getting tmux sessions: {e}")
            return []
    
    def capture_window_content(self, session_name: str, window_index: int, num_lines: int = 50) -> str:
        """Safely capture the last N lines from a tmux window"""
        if num_lines > self.max_lines_capture:
            num_lines = self.max_lines_capture
            
        try:
            cmd = ["tmux", "capture-pane", "-t", f"{session_name}:{window_index}", "-p", "-S", f"-{num_lines}"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error capturing window content: {e}"
    
    def get_window_info(self, session_name: str, window_index: int) -> Dict:
        """Get detailed information about a specific window"""
        try:
            cmd = ["tmux", "display-message", "-t", f"{session_name}:{window_index}", "-p", 
                   "#{window_name}:#{window_active}:#{window_panes}:#{window_layout}"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if result.stdout.strip():
                parts = result.stdout.strip().split(':')
                return {
                    "name": parts[0],
                    "active": parts[1] == '1',
                    "panes": int(parts[2]),
                    "layout": parts[3],
                    "content": self.capture_window_content(session_name, window_index)
                }
        except subprocess.CalledProcessError as e:
            return {"error": f"Could not get window info: {e}"}
    
    def send_keys_to_window(self, session_name: str, window_index: int, keys: str, confirm: bool = True) -> bool:
        """Safely send keys to a tmux window with confirmation"""
        if self.safety_mode and confirm:
            print(f"SAFETY CHECK: About to send '{keys}' to {session_name}:{window_index}")
            response = input("Confirm? (yes/no): ")
            if response.lower() != 'yes':
                print("Operation cancelled")
                return False
        
        try:
            cmd = ["tmux", "send-keys", "-t", f"{session_name}:{window_index}", keys]
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error sending keys: {e}")
            return False
    
    def send_command_to_window(self, session_name: str, window_index: int, command: str, confirm: bool = True) -> bool:
        """Send a command to a window (adds Enter automatically)"""
        # First send the command text
        if not self.send_keys_to_window(session_name, window_index, command, confirm):
            return False
        # Then send the actual Enter key (C-m)
        try:
            cmd = ["tmux", "send-keys", "-t", f"{session_name}:{window_index}", "C-m"]
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error sending Enter key: {e}")
            return False
    
    def get_all_windows_status(self) -> Dict:
        """Get status of all windows across all sessions"""
        sessions = self.get_tmux_sessions()
        status = {
            "timestamp": datetime.now().isoformat(),
            "sessions": []
        }
        
        for session in sessions:
            session_data = {
                "name": session.name,
                "attached": session.attached,
                "windows": []
            }
            
            for window in session.windows:
                window_info = self.get_window_info(session.name, window.window_index)
                window_data = {
                    "index": window.window_index,
                    "name": window.window_name,
                    "active": window.active,
                    "info": window_info
                }
                session_data["windows"].append(window_data)
            
            status["sessions"].append(session_data)
        
        return status
    
    def find_window_by_name(self, window_name: str) -> List[Tuple[str, int]]:
        """Find windows by name across all sessions"""
        sessions = self.get_tmux_sessions()
        matches = []
        
        for session in sessions:
            for window in session.windows:
                if window_name.lower() in window.window_name.lower():
                    matches.append((session.name, window.window_index))
        
        return matches
    
    def create_monitoring_snapshot(self) -> str:
        """Create a comprehensive snapshot for Claude analysis"""
        status = self.get_all_windows_status()
        
        # Format for Claude consumption
        snapshot = f"Tmux Monitoring Snapshot - {status['timestamp']}\n"
        snapshot += "=" * 50 + "\n\n"
        
        for session in status['sessions']:
            snapshot += f"Session: {session['name']} ({'ATTACHED' if session['attached'] else 'DETACHED'})\n"
            snapshot += "-" * 30 + "\n"
            
            for window in session['windows']:
                snapshot += f"  Window {window['index']}: {window['name']}"
                if window['active']:
                    snapshot += " (ACTIVE)"
                snapshot += "\n"
                
                if 'content' in window['info']:
                    # Get last 10 lines for overview
                    content_lines = window['info']['content'].split('\n')
                    recent_lines = content_lines[-10:] if len(content_lines) > 10 else content_lines
                    snapshot += "    Recent output:\n"
                    for line in recent_lines:
                        if line.strip():
                            snapshot += f"    | {line}\n"
                snapshot += "\n"
        
        return snapshot

# ============================================================================
# Convenience functions for backward compatibility
# ============================================================================

def tmux_send_message(target: str, message: str, validate: bool = True) -> bool:
    """Send message using default TmuxManager - replaces send-claude-message.sh functionality"""
    manager = TmuxManager()
    return manager.send_message(target, message, validate)

def tmux_create_session(session_name: str, working_dir: str = None, **kwargs) -> bool:
    """Create tmux session using default manager"""
    manager = TmuxManager()
    return manager.create_session(session_name, working_dir, **kwargs)

def tmux_kill_session(session_name: str) -> bool:
    """Kill tmux session using default manager"""
    manager = TmuxManager()
    return manager.kill_session(session_name)

def tmux_session_exists(session_name: str) -> bool:
    """Check if session exists using default manager"""
    manager = TmuxManager()
    return manager.session_exists(session_name)

def tmux_list_sessions() -> List[Dict[str, str]]:
    """List sessions using default manager"""
    manager = TmuxManager()
    return manager.list_sessions()

if __name__ == "__main__":
    # Example usage and testing
    logging.basicConfig(level=logging.INFO)
    
    # Test TmuxManager functionality
    print("Testing TmuxManager...")
    manager = TmuxManager()
    
    sessions = manager.list_sessions()
    print(f"Current sessions: {[s['name'] for s in sessions]}")
    
    # Test socket manager
    socket_manager = TmuxSocketManager()
    project_manager = socket_manager.get_manager_for_project("test-project")
    
    print("TmuxManager test complete")
    
    # Legacy compatibility test
    print("\nTesting legacy TmuxOrchestrator compatibility...")
    orchestrator = TmuxOrchestrator()
    status = orchestrator.get_all_windows_status()
    print(f"Found {len(status['sessions'])} sessions via legacy interface")
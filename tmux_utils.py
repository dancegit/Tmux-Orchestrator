#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Tmux Utilities Module
Provides reusable tmux session management functions for the orchestrator system
"""

import subprocess
import json
import time
import logging
import uuid
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Set up logger for utility functions
logger = logging.getLogger(__name__)

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

if __name__ == "__main__":
    orchestrator = TmuxOrchestrator()
    status = orchestrator.get_all_windows_status()
    print(json.dumps(status, indent=2))
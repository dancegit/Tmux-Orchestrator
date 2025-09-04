#!/usr/bin/env python3
"""
Utilities module extracted from scheduler.py
Contains helper functions and shared utilities.
"""

import subprocess
import logging
import time
import threading
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def session_exists(session_name: str) -> bool:
    """Check if a tmux session exists"""
    try:
        result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False


def is_session_ready(session_name: str, window_index: int) -> bool:
    """Validate if session exists and is running Claude (not bash)."""
    # Check existence
    if not session_exists(session_name):
        logger.warning(f"Session {session_name} does not exist")
        return False
    
    # Check pane command (should not be bash/sh)
    target = f"{session_name}:{window_index}"
    try:
        result = subprocess.run(['tmux', 'display-message', '-t', target, '-p', '#{pane_current_command}'],
                              capture_output=True, text=True)
        current_command = result.stdout.strip()
        
        if current_command in ['bash', 'sh', 'zsh']:
            logger.warning(f"Session {session_name}:{window_index} is running shell ({current_command}), not Claude")
            return False
        
        logger.info(f"Session {session_name}:{window_index} is ready (running: {current_command})")
        return True
    except Exception as e:
        logger.warning(f"Could not check pane command for {target}: {e}")
        return False


def get_session_age(session_name: str) -> int:
    """Get the age of a tmux session in seconds.
    
    Returns:
        Age in seconds, or -1 if session doesn't exist or error occurs.
    """
    try:
        # Get session creation time
        result = subprocess.run(
            ['tmux', 'display-message', '-t', session_name, '-p', '#{session_created}'],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            return -1
            
        session_created = int(result.stdout.strip())
        current_time = int(time.time())
        age = current_time - session_created
        
        return age
    except Exception as e:
        logger.debug(f"Could not get age for session {session_name}: {e}")
        return -1


def find_lingering_sessions(active_sessions: List[str], completed_sessions: List[str]) -> List[str]:
    """Find sessions that belong to completed/failed projects but are still active"""
    return [sess for sess in active_sessions if sess in completed_sessions]


class HeartbeatThread:
    """Manages heartbeat thread for lock manager."""
    
    def __init__(self, lock_manager, interval: int = 30):
        self.lock_manager = lock_manager
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = None
    
    def start(self):
        """Start the heartbeat thread."""
        if self.thread and self.thread.is_alive():
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()
        logger.info("Heartbeat thread started")
    
    def stop(self):
        """Stop the heartbeat thread."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Heartbeat thread stopped")
    
    def _heartbeat_loop(self):
        """Main heartbeat loop."""
        while not self.stop_event.is_set():
            try:
                self.lock_manager.heartbeat()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            # Sleep in small intervals for responsive shutdown
            for _ in range(self.interval):
                if self.stop_event.is_set():
                    break
                time.sleep(1)


def sanitize_project_name(spec_path: str) -> str:
    """Extract and sanitize project name from spec path."""
    if not spec_path:
        return "unknown"
    
    # Extract filename without extension
    path = Path(spec_path)
    name = path.stem
    
    # Sanitize for use in tmux session names
    # Remove or replace problematic characters
    import re
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    
    # Ensure it doesn't start with a number (tmux limitation)
    if name and name[0].isdigit():
        name = f"p{name}"
    
    return name or "unknown"


def run_command_with_timeout(command: List[str], timeout: int = 10) -> Optional[subprocess.CompletedProcess]:
    """Run a command with timeout."""
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out after {timeout}s: {' '.join(command)}")
        return None
    except Exception as e:
        logger.error(f"Error running command {' '.join(command)}: {e}")
        return None
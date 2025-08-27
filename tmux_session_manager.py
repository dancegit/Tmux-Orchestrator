#!/usr/bin/env python3
"""
Tmux Session Manager - Encapsulates tmux operations for safe session management
"""

import subprocess
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class TmuxSessionManager:
    """Manages tmux sessions with safe operations"""
    
    def kill_session(self, session_name: str) -> bool:
        """Safely kill a tmux session if it exists"""
        try:
            # Check existence
            result = subprocess.run(['tmux', 'has-session', '-t', session_name], capture_output=True)
            if result.returncode != 0:
                logger.info(f"Session {session_name} does not exist - skipping kill")
                return True
            
            # Attempt kill
            result = subprocess.run(['tmux', 'kill-session', '-t', session_name], capture_output=True)
            if result.returncode == 0:
                logger.info(f"Successfully killed session {session_name}")
                return True
            else:
                logger.error(f"Failed to kill session {session_name}: {result.stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Error killing session {session_name}: {e}")
            return False
    
    def is_session_alive(self, session_name: str) -> bool:
        """Check if a session exists and is active"""
        try:
            result = subprocess.run(['tmux', 'has-session', '-t', session_name], capture_output=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking session {session_name}: {e}")
            return False
    
    def get_active_sessions(self) -> List[str]:
        """Get list of all active tmux sessions"""
        try:
            result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            return []
        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []
    
    def kill_sessions_by_pattern(self, pattern: str) -> int:
        """Kill all sessions matching a pattern. Returns count of killed sessions."""
        killed = 0
        sessions = self.get_active_sessions()
        for session in sessions:
            if pattern in session:
                if self.kill_session(session):
                    killed += 1
        return killed
    
    def get_session_info(self, session_name: str) -> Optional[dict]:
        """Get detailed info about a session"""
        try:
            # Check if session exists
            if not self.is_session_alive(session_name):
                return None
            
            # Get session details
            result = subprocess.run(
                ['tmux', 'list-sessions', '-F', 
                 '#{session_name}:#{session_created}:#{session_windows}:#{session_attached}', 
                 '-f', f"#{{{session_name}=={session_name}}}"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(':')
                if len(parts) >= 4:
                    return {
                        'name': parts[0],
                        'created': parts[1],
                        'windows': int(parts[2]) if parts[2].isdigit() else 0,
                        'attached': parts[3] == '1'
                    }
            return None
        except Exception as e:
            logger.error(f"Error getting session info for {session_name}: {e}")
            return None
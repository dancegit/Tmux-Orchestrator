#!/usr/bin/env python3

import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from tmux_utils import TmuxOrchestrator
from session_registry import SessionRegistry

class DirectOrchestrator:
    """Direct orchestrator for Claude to control tmux sessions"""
    
    def __init__(self):
        self.tmux = TmuxOrchestrator()
        self.registry = SessionRegistry()
        self.last_check_time = {}
        
    def get_full_status(self, include_content: bool = True, lines_per_window: int = 50) -> Dict:
        """Get comprehensive status of all sessions for Claude analysis"""
        sessions = self.tmux.get_tmux_sessions()
        status = {
            "timestamp": datetime.now().isoformat(),
            "sessions": {},
            "registry_summary": self.registry.get_all_sessions_summary()
        }
        
        for session in sessions:
            session_data = {
                "name": session.name,
                "attached": session.attached,
                "windows": {},
                "registry_info": self.registry.get_session_info(session.name)
            }
            
            for window in session.windows:
                window_content = ""
                if include_content:
                    window_content = self.tmux.capture_window_content(
                        session.name, 
                        window.window_index, 
                        lines_per_window
                    )
                
                window_data = {
                    "index": window.window_index,
                    "name": window.window_name,
                    "active": window.active,
                    "content": window_content,
                    "registry_info": self.registry.get_window_info(session.name, window.window_index)
                }
                
                session_data["windows"][window.window_index] = window_data
            
            status["sessions"][session.name] = session_data
        
        return status
    
    def get_window_deep_content(self, session_name: str, window_index: int, lines: int = 400) -> Dict:
        """Get deeper content from a specific window"""
        content = self.tmux.capture_window_content(session_name, window_index, lines)
        window_info = self.tmux.get_window_info(session_name, window_index)
        
        return {
            "session": session_name,
            "window": window_index,
            "window_name": window_info.get("name", "unknown"),
            "content": content,
            "lines_captured": lines,
            "timestamp": datetime.now().isoformat()
        }
    
    def update_session_info(self, session_name: str, info: Dict) -> bool:
        """Update session information in registry"""
        try:
            self.registry.register_session(session_name, info)
            return True
        except Exception as e:
            return False
    
    def update_window_info(self, session_name: str, window_index: int, info: Dict) -> bool:
        """Update window information in registry"""
        try:
            self.registry.register_window(session_name, window_index, info)
            return True
        except Exception as e:
            return False
    
    def add_analysis_note(self, session_name: str, window_index: int, note: str) -> bool:
        """Add Claude's analysis note to a window"""
        try:
            self.registry.add_monitoring_note(session_name, window_index, note)
            return True
        except Exception as e:
            return False
    
    def execute_command(self, session_name: str, window_index: int, command: str) -> Dict:
        """Execute a command and return result"""
        # First capture current state
        before_content = self.tmux.capture_window_content(session_name, window_index, 50)
        
        # Send command
        success = self.tmux.send_command_to_window(session_name, window_index, command, confirm=False)
        
        if success:
            # Wait a moment for command to start
            time.sleep(0.5)
            
            # Capture immediate result
            after_content = self.tmux.capture_window_content(session_name, window_index, 50)
            
            return {
                "success": True,
                "command": command,
                "before": before_content,
                "after": after_content,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "command": command,
                "error": "Failed to send command"
            }
    
    def check_window_activity(self, session_name: str, window_index: int, seconds_later: int = 30) -> Dict:
        """Check window activity after a delay"""
        window_key = f"{session_name}:{window_index}"
        self.last_check_time[window_key] = datetime.now().isoformat()
        
        # This would be called after the delay
        content = self.tmux.capture_window_content(session_name, window_index, 100)
        
        return {
            "session": session_name,
            "window": window_index,
            "content": content,
            "check_time": datetime.now().isoformat(),
            "last_check": self.last_check_time.get(window_key)
        }
    
    def get_quick_summary(self) -> str:
        """Get a quick text summary for Claude"""
        sessions = self.tmux.get_tmux_sessions()
        
        summary = []
        summary.append(f"=== Tmux Status at {datetime.now().strftime('%H:%M:%S')} ===")
        summary.append(f"Active Sessions: {len(sessions)}")
        
        for session in sessions:
            attached = "●" if session.attached else "○"
            summary.append(f"\n{attached} {session.name} ({len(session.windows)} windows)")
            
            for window in session.windows:
                active = "→" if window.active else " "
                summary.append(f"  {active} {window.window_index}: {window.window_name}")
                
                # Add registry info if available
                window_info = self.registry.get_window_info(session.name, window.window_index)
                if window_info and window_info.get("purpose"):
                    summary.append(f"     Purpose: {window_info['purpose']}")
                if window_info and window_info.get("monitoring_notes"):
                    latest = window_info["monitoring_notes"][-1]["note"]
                    summary.append(f"     Latest: {latest[:60]}...")
        
        return "\n".join(summary)
    
    def save_analysis_checkpoint(self, session_name: str, window_index: int, content: str, analysis: str):
        """Save analysis checkpoint for future reference"""
        self.registry.save_window_history(session_name, window_index, content, analysis)

# Helper functions for direct Claude interaction

def create_orchestrator():
    """Create orchestrator instance"""
    return DirectOrchestrator()

def get_status(orchestrator: DirectOrchestrator, detailed: bool = False) -> str:
    """Get formatted status for Claude to read"""
    if detailed:
        status = orchestrator.get_full_status(include_content=True, lines_per_window=50)
        return json.dumps(status, indent=2)
    else:
        return orchestrator.get_quick_summary()

def analyze_window(orchestrator: DirectOrchestrator, session: str, window: int, lines: int = 400) -> str:
    """Get detailed window content for analysis"""
    result = orchestrator.get_window_deep_content(session, window, lines)
    return json.dumps(result, indent=2)

def execute_in_window(orchestrator: DirectOrchestrator, session: str, window: int, command: str) -> str:
    """Execute command and return result"""
    result = orchestrator.execute_command(session, window, command)
    return json.dumps(result, indent=2)

def update_registry(orchestrator: DirectOrchestrator, updates: Dict) -> str:
    """Update registry with Claude's understanding"""
    results = []
    
    for session_name, session_updates in updates.items():
        if "session_info" in session_updates:
            success = orchestrator.update_session_info(session_name, session_updates["session_info"])
            results.append(f"Session {session_name}: {'updated' if success else 'failed'}")
        
        if "windows" in session_updates:
            for window_idx, window_updates in session_updates["windows"].items():
                success = orchestrator.update_window_info(session_name, int(window_idx), window_updates)
                results.append(f"Window {session_name}:{window_idx}: {'updated' if success else 'failed'}")
    
    return "\n".join(results)
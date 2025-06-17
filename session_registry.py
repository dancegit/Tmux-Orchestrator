#!/usr/bin/env python3

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

class SessionRegistry:
    """Persistent registry for tracking tmux sessions and their purposes"""
    
    def __init__(self, registry_dir: str = None):
        if registry_dir is None:
            registry_dir = os.path.join(os.path.dirname(__file__), "registry")
        
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(exist_ok=True)
        self.registry_file = self.registry_dir / "sessions.json"
        self.history_dir = self.registry_dir / "history"
        self.history_dir.mkdir(exist_ok=True)
        
        self.registry = self._load_registry()
    
    def _load_registry(self) -> Dict:
        """Load existing registry or create new one"""
        if self.registry_file.exists():
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        return {
            "sessions": {},
            "last_updated": None
        }
    
    def _save_registry(self):
        """Save registry to disk"""
        self.registry["last_updated"] = datetime.now().isoformat()
        with open(self.registry_file, 'w') as f:
            json.dump(self.registry, f, indent=2)
    
    def register_session(self, session_name: str, info: Dict):
        """Register or update a session's information"""
        if session_name not in self.registry["sessions"]:
            self.registry["sessions"][session_name] = {
                "created": datetime.now().isoformat(),
                "windows": {},
                "purpose": "",
                "working_directory": "",
                "current_task": "",
                "notes": []
            }
        
        # Update with new info
        session = self.registry["sessions"][session_name]
        for key, value in info.items():
            if key != "windows":
                session[key] = value
        
        session["last_seen"] = datetime.now().isoformat()
        self._save_registry()
    
    def register_window(self, session_name: str, window_index: int, window_info: Dict):
        """Register or update window information"""
        if session_name not in self.registry["sessions"]:
            self.register_session(session_name, {})
        
        windows = self.registry["sessions"][session_name]["windows"]
        window_key = str(window_index)
        
        if window_key not in windows:
            windows[window_key] = {
                "created": datetime.now().isoformat(),
                "name": "",
                "purpose": "",
                "working_directory": "",
                "active_command": "",
                "last_activity": "",
                "monitoring_notes": []
            }
        
        # Update window info
        window = windows[window_key]
        for key, value in window_info.items():
            window[key] = value
        
        window["last_updated"] = datetime.now().isoformat()
        self._save_registry()
    
    def get_session_info(self, session_name: str) -> Optional[Dict]:
        """Get information about a specific session"""
        return self.registry["sessions"].get(session_name)
    
    def get_window_info(self, session_name: str, window_index: int) -> Optional[Dict]:
        """Get information about a specific window"""
        session = self.get_session_info(session_name)
        if session:
            return session["windows"].get(str(window_index))
        return None
    
    def add_monitoring_note(self, session_name: str, window_index: int, note: str):
        """Add a monitoring note to a window"""
        window = self.get_window_info(session_name, window_index)
        if window:
            if "monitoring_notes" not in window:
                window["monitoring_notes"] = []
            
            window["monitoring_notes"].append({
                "timestamp": datetime.now().isoformat(),
                "note": note
            })
            
            # Keep only last 10 notes
            window["monitoring_notes"] = window["monitoring_notes"][-10:]
            self._save_registry()
    
    def save_window_history(self, session_name: str, window_index: int, content: str, analysis: str = ""):
        """Save window content history for later reference"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        history_file = self.history_dir / f"{session_name}_{window_index}_{timestamp}.json"
        
        history_data = {
            "session": session_name,
            "window": window_index,
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "analysis": analysis,
            "window_info": self.get_window_info(session_name, window_index)
        }
        
        with open(history_file, 'w') as f:
            json.dump(history_data, f, indent=2)
    
    def get_all_sessions_summary(self) -> str:
        """Get a formatted summary of all registered sessions"""
        if not self.registry["sessions"]:
            return "No sessions registered yet."
        
        summary = []
        summary.append(f"Session Registry (Updated: {self.registry.get('last_updated', 'Never')})")
        summary.append("=" * 60)
        
        for session_name, session_info in self.registry["sessions"].items():
            summary.append(f"\nSession: {session_name}")
            summary.append(f"  Purpose: {session_info.get('purpose', 'Not specified')}")
            summary.append(f"  Current Task: {session_info.get('current_task', 'None')}")
            summary.append(f"  Working Dir: {session_info.get('working_directory', 'Unknown')}")
            summary.append(f"  Windows: {len(session_info.get('windows', {}))}")
            
            for window_idx, window_info in session_info.get("windows", {}).items():
                summary.append(f"    Window {window_idx}: {window_info.get('name', 'unnamed')}")
                summary.append(f"      Purpose: {window_info.get('purpose', 'Not specified')}")
                if window_info.get('monitoring_notes'):
                    latest_note = window_info['monitoring_notes'][-1]
                    summary.append(f"      Latest: {latest_note['note'][:60]}...")
        
        return "\n".join(summary)
    
    def cleanup_old_history(self, days_to_keep: int = 7):
        """Clean up old history files"""
        cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        
        for history_file in self.history_dir.glob("*.json"):
            if history_file.stat().st_mtime < cutoff_date:
                history_file.unlink()
#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Claude Control - Status monitoring for Tmux Orchestrator
Provides status information about running tmux sessions and Claude agents
"""

import sys
import json
import subprocess
from pathlib import Path
import os

# Set UV_NO_WORKSPACE environment variable for all subprocess calls
os.environ['UV_NO_WORKSPACE'] = '1'

# Import tmux_utils from the same directory
sys.path.insert(0, str(Path(__file__).parent))
from tmux_utils import TmuxOrchestrator

def print_status(detailed=False):
    """Print status of all tmux sessions and windows"""
    orchestrator = TmuxOrchestrator()
    
    if detailed:
        # Get detailed snapshot for analysis
        snapshot = orchestrator.create_monitoring_snapshot()
        print(snapshot)
    else:
        # Get basic status
        status = orchestrator.get_all_windows_status()
        
        print(f"=== Tmux Orchestrator Status ===")
        print(f"Timestamp: {status['timestamp']}")
        print()
        
        for session in status['sessions']:
            print(f"Session: {session['name']} {'(ATTACHED)' if session['attached'] else '(DETACHED)'}")
            
            for window in session['windows']:
                active_marker = " *" if window['active'] else ""
                print(f"  [{window['index']}] {window['name']}{active_marker}")
                
                if 'error' in window['info']:
                    print(f"      Error: {window['info']['error']}")
                elif 'panes' in window['info']:
                    print(f"      Panes: {window['info']['panes']}")
            
            print()

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: claude_control.py <command> [options]")
        print("Commands:")
        print("  status          - Show basic status")
        print("  status detailed - Show detailed status with window content")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "status":
        detailed = len(sys.argv) > 2 and sys.argv[2] == "detailed"
        print_status(detailed)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
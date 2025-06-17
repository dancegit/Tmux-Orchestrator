#!/usr/bin/env python3
"""
Claude Control Interface - Direct control of tmux orchestrator
This script is designed to be called by Claude to manage tmux sessions
"""

import sys
import json
from direct_orchestrator import DirectOrchestrator, get_status, analyze_window, execute_in_window, update_registry

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 claude_control.py <command> [args...]")
        print("Commands:")
        print("  status [detailed]     - Get current status")
        print("  analyze <session> <window> [lines] - Analyze specific window")
        print("  execute <session> <window> <command> - Execute command in window")
        print("  update <json_updates> - Update registry")
        print("  summary              - Quick summary")
        return
    
    orchestrator = DirectOrchestrator()
    command = sys.argv[1]
    
    try:
        if command == "status":
            detailed = len(sys.argv) > 2 and sys.argv[2] == "detailed"
            print(get_status(orchestrator, detailed))
        
        elif command == "summary":
            print(orchestrator.get_quick_summary())
        
        elif command == "analyze":
            if len(sys.argv) < 4:
                print("Error: analyze requires session and window")
                return
            session = sys.argv[2]
            window = int(sys.argv[3])
            lines = int(sys.argv[4]) if len(sys.argv) > 4 else 400
            print(analyze_window(orchestrator, session, window, lines))
        
        elif command == "execute":
            if len(sys.argv) < 5:
                print("Error: execute requires session, window, and command")
                return
            session = sys.argv[2]
            window = int(sys.argv[3])
            cmd = " ".join(sys.argv[4:])
            print(execute_in_window(orchestrator, session, window, cmd))
        
        elif command == "update":
            if len(sys.argv) < 3:
                print("Error: update requires JSON data")
                return
            updates = json.loads(sys.argv[2])
            print(update_registry(orchestrator, updates))
        
        elif command == "note":
            if len(sys.argv) < 5:
                print("Error: note requires session, window, and note text")
                return
            session = sys.argv[2]
            window = int(sys.argv[3])
            note = " ".join(sys.argv[4:])
            success = orchestrator.add_analysis_note(session, window, note)
            print("Note added" if success else "Failed to add note")
        
        else:
            print(f"Unknown command: {command}")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
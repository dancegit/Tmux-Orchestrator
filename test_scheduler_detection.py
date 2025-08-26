#!/usr/bin/env python3
import time
import subprocess
import logging
from concurrent_orchestration import ConcurrentOrchestrationManager
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Get all orchestrations
manager = ConcurrentOrchestrationManager(Path('/home/clauderun/Tmux-Orchestrator'))
all_orchestrations = manager.list_active_orchestrations()

print(f"Total orchestrations: {len(all_orchestrations)}")

# Check JSON-based active
json_based_active = sum(1 for orch in all_orchestrations if orch.get('active'))
print(f"JSON-based active: {json_based_active}")

if json_based_active == 0:
    print("No JSON-based active orchestrations, checking tmux sessions")
    
    # Get tmux sessions
    tmux_result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name} #{session_activity}'],
                               capture_output=True, text=True)
    
    if tmux_result.returncode == 0:
        live_sessions = {}
        for line in tmux_result.stdout.strip().split('\n'):
            if ' ' in line:
                parts = line.split(' ', 1)
                name = parts[0].strip()
                try:
                    live_sessions[name] = int(parts[1].strip())
                except (ValueError, IndexError):
                    continue
        
        print(f"Found {len(live_sessions)} tmux sessions: {list(live_sessions.keys())}")
        
        # Check matches
        now = int(time.time())
        matches_found = 0
        
        for orch in all_orchestrations:
            session_name = orch.get('session_name')
            if session_name in live_sessions:
                last_active = live_sessions[session_name]
                age_seconds = now - last_active
                print(f"MATCH: {session_name}, age={age_seconds}s")
                if age_seconds < 3600:
                    matches_found += 1
                    print(f"  -> ACTIVE (within 1 hour threshold)")
                else:
                    print(f"  -> TOO OLD ({age_seconds}s > 3600s)")
            
        print(f"Total matches found: {matches_found}")
        
        # Debug: show orchestrations with matching session IDs
        print("\nDebugging session ID matching:")
        for session_name in live_sessions:
            print(f"\nChecking tmux session: {session_name}")
            
            # Try to find by session_name
            found_by_name = False
            for orch in all_orchestrations:
                if orch.get('session_name') == session_name:
                    print(f"  Found by session_name: {orch.get('session_id')}")
                    found_by_name = True
                    break
            
            if not found_by_name:
                print(f"  NOT FOUND in orchestrations list!")
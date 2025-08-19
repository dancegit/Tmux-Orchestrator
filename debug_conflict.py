#!/usr/bin/env python3
"""
Debug conflict detection to understand why it's not triggering.
"""

from session_state import SessionStateManager
from pathlib import Path

# Initialize session state manager
tmux_orchestrator_path = Path(__file__).parent
manager = SessionStateManager(tmux_orchestrator_path)

# Session name from tmux
session_name = "signalmatrix-event-delivery-architecture-impl-a9601f5d"
project_name = session_name.split('-impl-')[0].replace('-', ' ').title()

print(f"Session name: {session_name}")
print(f"Derived project name: '{project_name}'")

# Check if state exists
state = manager.load_session_state(project_name)
if state:
    print(f"✅ State found for project: {state.project_name}")
    print(f"Status reports: {state.status_reports}")
    
    # Test conflict detection
    conflicts = manager.get_status_conflicts(project_name)
    print(f"Conflicts found: {len(conflicts)}")
    for conflict in conflicts:
        print(f"  - {conflict}")
else:
    print(f"❌ No state found for project name: '{project_name}'")
    
    # Try alternative project names
    alternatives = [
        "Signalmatrix Event Delivery Architecture",
        "signalmatrix-event-delivery-architecture", 
        "Signalmatrix-Event-Delivery-Architecture"
    ]
    
    for alt in alternatives:
        alt_state = manager.load_session_state(alt)
        if alt_state:
            print(f"✅ Found state with alternative name: '{alt}'")
            print(f"Status reports: {alt_state.status_reports}")
            break
    else:
        print("❌ No state found with any alternative names")
        
        # List all available states
        registry_dir = tmux_orchestrator_path / 'registry' / 'projects'
        if registry_dir.exists():
            projects = [p.name for p in registry_dir.iterdir() if p.is_dir()]
            print(f"Available projects: {projects}")
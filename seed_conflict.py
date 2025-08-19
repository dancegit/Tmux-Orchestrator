#!/usr/bin/env python3
"""
Seed the SignalMatrix project with conflicting status reports to test conflict detection.
"""

from session_state import SessionStateManager
from pathlib import Path

# Initialize session state manager
tmux_orchestrator_path = Path(__file__).parent
manager = SessionStateManager(tmux_orchestrator_path)

# Project name from session
project_name = "Signalmatrix Event Delivery Architecture"

print(f"Seeding conflict for project: {project_name}")

# Add conflicting deployment status reports
manager.update_status_report(
    project_name=project_name,
    role="sysadmin", 
    topic="deployment",
    status="COMPLETE",
    details="Service deployed successfully on port 8002. Systemd service is running and health endpoint responds OK."
)

manager.update_status_report(
    project_name=project_name,
    role="developer", 
    topic="deployment",
    status="FAILURE", 
    details="CRITICAL: Deployment is failing due to missing shared_kernel dependency. The service cannot start without this module."
)

print("Conflict seeded successfully!")

# Test conflict detection
conflicts = manager.get_status_conflicts(project_name)
if conflicts:
    print(f"\n✅ Conflict detected successfully:")
    for conflict in conflicts:
        print(f"  Type: {conflict['type']}")
        print(f"  Description: {conflict['description']}")
        print(f"  Suggested Action: {conflict['suggested_action']}")
else:
    print("\n❌ No conflicts detected - check implementation")
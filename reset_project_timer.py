#!/usr/bin/env python3
"""
Reset project start time to now to give it full 6 hours
"""

import sys
from pathlib import Path
from datetime import datetime
import json

def reset_project_timer(project_session_name):
    """Reset project start time to now"""
    
    # Find project directory
    projects_dir = Path("/home/clauderun/Tmux-Orchestrator/registry/projects")
    project_dir = None
    
    for p in projects_dir.iterdir():
        if project_session_name in p.name:
            project_dir = p
            break
    
    if not project_dir:
        print(f"❌ Project not found: {project_session_name}")
        return False
    
    # Check for orchestration metadata first
    metadata_file = project_dir / "orchestration_metadata.json"
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text())
            # Update created_at to now
            now = datetime.now().isoformat()
            metadata['created_at'] = now
            metadata_file.write_text(json.dumps(metadata, indent=2))
            print(f"✅ Updated orchestration metadata start time to: {now}")
        except Exception as e:
            print(f"❌ Error updating metadata: {e}")
            return False
    
    # Also check for session state
    state_file = project_dir / "session_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            # Update created_at to now
            now = datetime.now().isoformat()
            state['created_at'] = now
            state_file.write_text(json.dumps(state, indent=2))
            print(f"✅ Updated session state start time to: {now}")
        except Exception as e:
            print(f"❌ Error updating session state: {e}")
            return False
    
    print(f"🕒 Project now has full 6 hours from: {datetime.now().strftime('%H:%M:%S')}")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: reset_project_timer.py <project_session_name>")
        print("Example: reset_project_timer.py tmux-orchestrator-mcp-server-v2-impl-3fd2a7dc")
        sys.exit(1)
    
    project_session_name = sys.argv[1]
    success = reset_project_timer(project_session_name)
    sys.exit(0 if success else 1)
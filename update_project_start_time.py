#!/usr/bin/env python3
"""
Update project start time to 3 hours ago so it will timeout in 1 hour
"""

from pathlib import Path
from datetime import datetime, timedelta
import json

# Load session state
state_file = Path("/home/clauderun/Tmux-Orchestrator/registry/projects/signalmatrix-event-delivery-architecture/session_state.json")
state = json.loads(state_file.read_text())

# Set created_at to 3 hours ago
three_hours_ago = datetime.now() - timedelta(hours=3)
state['created_at'] = three_hours_ago.isoformat()

# Save updated state
state_file.write_text(json.dumps(state, indent=2))

print(f"✅ Updated project start time to: {state['created_at']}")
print(f"   Project will timeout in 1 hour at the 4-hour mark")
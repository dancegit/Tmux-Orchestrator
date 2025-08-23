#!/usr/bin/env python3
"""
Reset Project 58 which is stuck in PROCESSING state
"""

import sqlite3
from pathlib import Path
import subprocess
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))
from session_state import SessionStateManager

# Config
DB_PATH = 'task_queue.db'
TMUX_ORCHESTRATOR_PATH = Path('/home/clauderun/Tmux-Orchestrator')
PROJECT_ID = 58
PROJECT_NAME = 'options-pricing-mvp-implementation'  # Adjust based on actual name

print(f"Resetting Project {PROJECT_ID}...")

# Connect to DB
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get current project info
cursor.execute("""
    SELECT project_path, status, orchestrator_session, main_session, started_at, spec_path
    FROM project_queue 
    WHERE id = ?
""", (PROJECT_ID,))
result = cursor.fetchone()

if not result:
    print(f"Project {PROJECT_ID} not found in database")
    sys.exit(1)

project_path, status, orch_session, main_session, started_at, spec_path = result
# Extract project name from spec path
if spec_path:
    project_name = Path(spec_path).stem.lower().replace('_', '-')
else:
    project_name = None
    
print(f"Current status: {status}")
print(f"Project path: {project_path}")
print(f"Spec path: {spec_path}")
print(f"Derived project name: {project_name}")
print(f"Orchestrator session: {orch_session}")
print(f"Main session: {main_session}")

# Reset queue state
cursor.execute("""
    UPDATE project_queue 
    SET status = 'failed', 
        error_message = 'Manual reset: No active session/process after 7+ hours',
        completed_at = strftime('%s', 'now')
    WHERE id = ? AND status = 'processing'
""", (PROJECT_ID,))

if cursor.rowcount > 0:
    print(f"✅ Reset Project {PROJECT_ID} to 'failed'")
else:
    print(f"❌ Project {PROJECT_ID} not in 'processing' - no change")

conn.commit()
conn.close()

# Clean up session state
if project_name:
    manager = SessionStateManager(TMUX_ORCHESTRATOR_PATH)
    state = manager.load_session_state(project_name)
    if state:
        state.completion_status = 'failed'
        state.failure_reason = 'Manual reset: Phantom project detected'
        manager.save_session_state(state)
        print("✅ Updated session state to failed")
    else:
        print("❌ No session state found - nothing to clean")

# Check and kill any lingering tmux sessions
for session_name in [orch_session, main_session]:
    if session_name:
        try:
            result = subprocess.run(['tmux', 'has-session', '-t', session_name], capture_output=True)
            if result.returncode == 0:
                subprocess.run(['tmux', 'kill-session', '-t', session_name])
                print(f"✅ Killed tmux session: {session_name}")
            else:
                print(f"❌ No tmux session found: {session_name}")
        except Exception as e:
            print(f"❌ Error checking tmux session {session_name}: {e}")

print("\n✅ Recovery complete. The queue should now be unblocked.")
print("Next project in queue will start on next scheduler cycle.")
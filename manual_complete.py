#!/usr/bin/env python3
"""
Manually complete a project for testing
"""

import subprocess
import sqlite3
import sys
from pathlib import Path

def complete_project_manually(project_id: int):
    """Manually mark a project as complete for testing"""
    
    # Get project details
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, session_name, spec_path, status 
        FROM project_queue 
        WHERE id = ?
    """, (project_id,))
    
    row = cursor.fetchone()
    if not row:
        print(f"Project {project_id} not found")
        return
    
    pid, session_name, spec_path, current_status = row
    print(f"Project {project_id}:")
    print(f"  Session: {session_name}")
    print(f"  Current Status: {current_status}")
    print(f"  Spec: {spec_path}")
    
    # Send completion command to orchestrator
    completion_message = """
Please execute the following commands to mark this project as complete:

echo "PROJECT COMPLETED - Manual completion triggered by scheduler" > COMPLETED
../report-completion.sh orchestrator "All tasks completed successfully - manual scheduler completion"

This will properly mark the project as complete in the system.
"""
    
    send_script = Path(__file__).parent / 'send-claude-message.sh'
    if send_script.exists():
        try:
            result = subprocess.run([
                str(send_script), 
                f'{session_name}:0', 
                completion_message
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Completion command sent to {session_name}")
                print("The orchestrator should now mark the project as complete.")
                print("Check status in a few moments with: ./qs")
            else:
                print(f"❌ Failed to send completion command: {result.stderr}")
                
        except Exception as e:
            print(f"Error sending command: {e}")
    else:
        print("❌ send-claude-message.sh not found")
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: manual_complete.py <project_id>")
        sys.exit(1)
    
    project_id = int(sys.argv[1])
    complete_project_manually(project_id)
#!/usr/bin/env python3
"""Emergency fix for stuck project in queue"""

import sqlite3
import sys
from pathlib import Path

def fix_stuck_project(project_id=42):
    """Mark stuck project as failed to unblock queue"""
    db_path = Path(__file__).parent / 'task_queue.db'
    
    print(f"Fixing stuck project #{project_id}...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # First check current status
        cursor.execute("SELECT id, spec_path, status, started_at FROM project_queue WHERE id = ?", (project_id,))
        result = cursor.fetchone()
        
        if not result:
            print(f"Project {project_id} not found")
            return False
            
        print(f"Current status: {result[2]}")
        print(f"Spec: {result[1]}")
        
        if result[2] != 'processing':
            print(f"Project is not stuck in processing (status: {result[2]})")
            return False
        
        # Update to failed status
        cursor.execute("""
            UPDATE project_queue 
            SET status = 'failed', 
                error_message = 'Stuck in processing - no tmux session found',
                completed_at = strftime('%s', 'now')
            WHERE id = ?
        """, (project_id,))
        
        conn.commit()
        
        # Verify update
        cursor.execute("SELECT status FROM project_queue WHERE id = ?", (project_id,))
        new_status = cursor.fetchone()[0]
        
        print(f"✅ Project {project_id} status updated to: {new_status}")
        print("Queue should now be unblocked")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    project_id = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    fix_stuck_project(project_id)
#!/usr/bin/env python3
"""
Mark a project as completed directly in the database
"""

import sys
import sqlite3
from datetime import datetime
from pathlib import Path

def main():
    if len(sys.argv) != 2:
        print("Usage: mark_project_complete_direct.py <project_id>")
        sys.exit(1)
    
    project_id = int(sys.argv[1])
    
    # Connect to database directly
    db_path = Path(__file__).parent / 'task_queue.db'
    conn = sqlite3.connect(str(db_path))
    
    try:
        # Enable WAL mode
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        
        # Update project status
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE project_queue 
            SET status = 'completed', 
                completed_at = ?, 
                orchestrator_session = NULL,
                main_session = NULL
            WHERE id = ?
        """, (datetime.now().isoformat(), project_id))
        
        if cursor.rowcount == 0:
            print(f"Project {project_id} not found")
            sys.exit(1)
        
        conn.commit()
        print(f"Project {project_id} marked as completed")
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
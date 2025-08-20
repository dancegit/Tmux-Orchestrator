#!/usr/bin/env python3
"""Add session_name column to project_queue table"""

import sqlite3
from pathlib import Path

def add_session_name_column():
    """Add session_name column to track tmux sessions"""
    db_path = Path(__file__).parent / 'task_queue.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(project_queue)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'session_name' in columns:
            print("✓ Column 'session_name' already exists")
            return True
            
        # Add the column
        cursor.execute("ALTER TABLE project_queue ADD COLUMN session_name TEXT DEFAULT NULL")
        conn.commit()
        
        print("✅ Added 'session_name' column to project_queue table")
        
        # Also add started_at timestamp if missing
        if 'started_at' not in columns:
            cursor.execute("ALTER TABLE project_queue ADD COLUMN started_at REAL")
            conn.commit()
            print("✅ Added 'started_at' column to project_queue table")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    add_session_name_column()
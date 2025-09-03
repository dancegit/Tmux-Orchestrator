#!/usr/bin/env python3
"""
Database Migration: Add merged_status column to project_queue table
This migration adds support for tracking which COMPLETED projects have been merged.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

def migrate_db():
    """Add merged_status column to project_queue table"""
    # Find the database path
    db_paths = [
        Path(__file__).parent / 'task_queue.db',  # Primary location
        Path(__file__).parent / 'registry' / 'project_queue.db',
        Path(__file__).parent / 'registry' / 'task_queue.db',
    ]
    
    db_path = None
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        print("❌ Error: Could not find project database")
        print(f"Searched in: {[str(p) for p in db_paths]}")
        return False
    
    print(f"📄 Found database at: {db_path}")
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Enable WAL for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(project_queue)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'merged_status' in columns:
            print("✅ Column 'merged_status' already exists")
        else:
            # Add merged_status column
            cursor.execute("""
                ALTER TABLE project_queue 
                ADD COLUMN merged_status TEXT DEFAULT NULL;
            """)
            print("✅ Added 'merged_status' column")
        
        if 'merged_at' not in columns:
            # Add merged_at timestamp column
            cursor.execute("""
                ALTER TABLE project_queue 
                ADD COLUMN merged_at REAL DEFAULT NULL;
            """)
            print("✅ Added 'merged_at' column")
        
        # Create index for faster queries on merged projects
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_merged_status ON project_queue(merged_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_merged ON project_queue(status, merged_status);")
        print("✅ Created indexes for merged_status")
        
        # Backfill existing 'completed' projects as 'pending_merge' for clarity
        cursor.execute("""
            UPDATE project_queue 
            SET merged_status = 'pending_merge' 
            WHERE status = 'completed' AND merged_status IS NULL;
        """)
        updated = cursor.rowcount
        
        if updated > 0:
            print(f"✅ Marked {updated} completed projects as 'pending_merge'")
        
        conn.commit()
        
        # Show current status distribution
        cursor.execute("""
            SELECT status, merged_status, COUNT(*) 
            FROM project_queue 
            GROUP BY status, merged_status
        """)
        
        print("\n📊 Current Status Distribution:")
        for status, merged_status, count in cursor.fetchall():
            print(f"  {status or 'None'}: {merged_status or 'None'} = {count}")
        
        conn.close()
        print("\n✅ Database migration complete!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == '__main__':
    migrate_db()
#!/usr/bin/env python3
"""
Cleanup script to fix looping tasks with interval_minutes=0
These tasks were causing infinite loops by rescheduling immediately
"""

import sqlite3
import time
import sys

def cleanup_looping_tasks():
    """Mark all interval_minutes=0 tasks as inactive to stop the flooding"""
    try:
        # Connect to the database
        conn = sqlite3.connect('/home/clauderun/Tmux-Orchestrator/task_queue.db')
        cursor = conn.cursor()
        
        # First, count how many tasks we'll be fixing
        cursor.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE interval_minutes = 0 
            AND next_run < ?
        """, (time.time() + 86400,))  # Tasks scheduled within next 24 hours
        
        count = cursor.fetchone()[0]
        print(f"Found {count} looping tasks with interval_minutes=0")
        
        if count == 0:
            print("No looping tasks to clean up!")
            return
        
        # Mark them as inactive by setting next_run far in the future
        # This prevents them from running while preserving the data
        future_time = time.time() + 31536000  # 1 year from now
        
        cursor.execute("""
            UPDATE tasks
            SET next_run = ?
            WHERE interval_minutes = 0
            AND next_run < ?
        """, (future_time, time.time() + 86400))
        
        affected = cursor.rowcount
        conn.commit()
        
        print(f"Successfully marked {affected} tasks as inactive")
        print("These tasks will no longer run or reschedule")
        
        # Show a sample of what was cleaned up
        cursor.execute("""
            SELECT session_name, agent_role, note
            FROM tasks
            WHERE interval_minutes = 0
            LIMIT 5
        """)
        
        samples = cursor.fetchall()
        if samples:
            print("\nSample of cleaned up tasks:")
            for session, role, note in samples:
                print(f"  - {session} / {role}: {note[:50]}...")
        
        conn.close()
        
    except Exception as e:
        print(f"Error cleaning up tasks: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Cleaning up looping tasks with interval_minutes=0...")
    cleanup_looping_tasks()
    print("\nDone! The orchestrator should no longer be flooded with messages.")
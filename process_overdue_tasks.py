#!/usr/bin/env python3
"""Process overdue tasks manually."""

import sqlite3
import subprocess
import time
from datetime import datetime

def process_overdue_tasks():
    """Process all overdue tasks."""
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    
    # Get overdue tasks
    cursor.execute('SELECT * FROM tasks WHERE next_run < ? ORDER BY next_run', (time.time(),))
    overdue = cursor.fetchall()
    
    print(f"Found {len(overdue)} overdue tasks")
    
    for task in overdue:
        task_id, session, role, window, next_run, interval, note, last_run, created_at, retry_count, max_retries = task[:11]
        
        scheduled_time = datetime.fromtimestamp(next_run)
        print(f"\nProcessing task {task_id}: {session}:{window}")
        print(f"  Note: {note}")
        print(f"  Was due at: {scheduled_time}")
        
        # Build the message
        if note:
            message = f"CHECK-IN: {note}"
        else:
            message = f"CHECK-IN: Regular {interval}-minute check-in for {role}"
        
        # Send the message
        target = f"{session}:{window}"
        cmd = ['./send-claude-message.sh', target, message]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  ✅ Message sent successfully")
            
            # Update the task for next run
            new_next_run = time.time() + (interval * 60)
            cursor.execute("""
                UPDATE tasks 
                SET next_run = ?, last_run = ?, retry_count = 0
                WHERE id = ?
            """, (new_next_run, time.time(), task_id))
            conn.commit()
            
            print(f"  📅 Rescheduled for {datetime.fromtimestamp(new_next_run)}")
        else:
            print(f"  ❌ Failed to send message: {result.stderr}")
            
            # Increment retry count
            cursor.execute("""
                UPDATE tasks 
                SET retry_count = retry_count + 1
                WHERE id = ?
            """, (task_id,))
            conn.commit()
    
    conn.close()
    print("\nDone processing overdue tasks")

if __name__ == "__main__":
    process_overdue_tasks()
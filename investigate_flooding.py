#!/usr/bin/env python3
"""
Script to investigate the orchestrator flooding issue with tasks 3038-3046
"""

import sqlite3
import sys

def investigate_tasks():
    try:
        # Connect to the database
        conn = sqlite3.connect('/home/clauderun/Tmux-Orchestrator/task_queue.db')
        cursor = conn.cursor()
        
        print("=== INVESTIGATING TASKS 3038-3046 ===")
        
        # Query the problematic tasks
        cursor.execute("""
            SELECT id, session_name, agent_role, window_index, next_run, 
                   interval_minutes, note, last_run, retry_count
            FROM tasks 
            WHERE id BETWEEN 3038 AND 3046 
            ORDER BY id
        """)
        
        tasks = cursor.fetchall()
        
        if not tasks:
            print("No tasks found in range 3038-3046")
            return
        
        print(f"Found {len(tasks)} tasks in range 3038-3046:")
        print("ID\tSession\tRole\tWindow\tNext Run\tInterval\tNote\tLast Run\tRetries")
        print("-" * 100)
        
        import time
        current_time = time.time()
        
        for task in tasks:
            task_id, session_name, agent_role, window_index, next_run, interval_minutes, note, last_run, retry_count = task
            
            # Convert timestamps to readable format
            next_run_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(next_run)) if next_run else 'None'
            last_run_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_run)) if last_run else 'None'
            
            # Check if task is due to run
            is_due = next_run <= current_time if next_run else False
            
            print(f"{task_id}\t{session_name}\t{agent_role}\t{window_index}\t{next_run_str}\t{interval_minutes}\t{note[:30]}...\t{last_run_str}\t{retry_count}")
            
            if is_due:
                print(f"  ^ TASK {task_id} IS DUE TO RUN (next_run={next_run}, current={current_time})")
            
            if interval_minutes == 0:
                print(f"  ^ TASK {task_id} is a ONE-TIME task (interval_minutes=0)")
        
        # Check for tasks that should have been marked as completed
        print("\n=== ANALYSIS ===")
        
        # Look for tasks that are due but should be one-time
        cursor.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE id BETWEEN 3038 AND 3046 
            AND next_run <= ? 
            AND interval_minutes = 0
        """, (current_time,))
        
        due_onetime_count = cursor.fetchone()[0]
        print(f"One-time tasks that are due to run: {due_onetime_count}")
        
        if due_onetime_count > 0:
            print("^ This is likely the cause of the flooding - one-time tasks not being marked as completed!")
        
        # Check recent task executions in logs (if we had access to logs)
        print(f"\nCurrent time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error investigating tasks: {e}")
        return False
    
    return True

if __name__ == "__main__":
    investigate_tasks()
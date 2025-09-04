#!/usr/bin/env python3
"""
Recovery script for Project 84 - Slice-002 Data Ingestion Service
Root cause: Race condition causing state mismatch (appears as processing but is actually failed)
Solution: Clean up and retry with proper state reset
"""

import sqlite3
import json
import time
import subprocess
import sys
import os

def recover_project():
    """Recover project 84 by resetting its state and retrying"""
    
    db_path = "/home/clauderun/Tmux-Orchestrator/task_queue.db"
    project_id = 84
    
    print(f"🔧 Starting recovery for Project {project_id}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Step 1: Get project details
        cursor.execute("""
            SELECT spec_path, project_path, status, retry_count, error_message
            FROM project_queue WHERE id = ?
        """, (project_id,))
        
        result = cursor.fetchone()
        if not result:
            print(f"❌ Project {project_id} not found in database")
            return False
            
        spec_path, project_path, status, retry_count, error_message = result
        print(f"📊 Current status: {status}, Retries: {retry_count}")
        print(f"   Spec: {spec_path}")
        print(f"   Path: {project_path}")
        
        # Step 2: Reset the project state to allow retry
        print(f"🔄 Resetting project state...")
        
        # First, remove any conflicting entries
        cursor.execute("BEGIN IMMEDIATE")
        
        # Update the failed project to allow retry
        cursor.execute("""
            UPDATE project_queue 
            SET status = 'queued',
                retry_count = retry_count + 1,
                error_message = NULL,
                started_at = NULL,
                completed_at = NULL,
                orchestrator_session = NULL,
                main_session = NULL,
                failed_components = NULL,
                fresh_start = 1
            WHERE id = ? AND status = 'failed'
        """, (project_id,))
        
        if cursor.rowcount == 0:
            print(f"⚠️  Project {project_id} is not in 'failed' state, cannot reset")
            conn.rollback()
            return False
            
        conn.commit()
        print(f"✅ Project {project_id} reset to 'queued' state")
        
        # Step 3: Trigger the scheduler to process it
        print(f"🚀 Triggering scheduler to process the project...")
        
        # Run the scheduler in processing mode
        cmd = [
            "python3", 
            "/home/clauderun/Tmux-Orchestrator/scheduler.py",
            "--process-once"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print(f"✅ Scheduler triggered successfully")
            print(f"   Output: {result.stdout[:500]}")
        else:
            print(f"⚠️  Scheduler returned non-zero: {result.returncode}")
            print(f"   Error: {result.stderr[:500]}")
            
        # Step 4: Verify final status
        cursor.execute("""
            SELECT status, retry_count, error_message
            FROM project_queue WHERE id = ?
        """, (project_id,))
        
        final_status, final_retries, final_error = cursor.fetchone()
        print(f"\n📈 Final status: {final_status}, Retries: {final_retries}")
        if final_error:
            print(f"   Error: {final_error}")
            
        return final_status in ['processing', 'completed']
        
    except Exception as e:
        print(f"❌ Recovery failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = recover_project()
    sys.exit(0 if success else 1)
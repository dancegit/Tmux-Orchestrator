#!/usr/bin/env python3
"""
Test reboot recovery functionality
"""

import sys
import os
sys.path.append('/home/clauderun/Tmux-Orchestrator')

from scheduler import TmuxOrchestratorScheduler
import sqlite3
import subprocess

def check_current_status():
    """Check current status of projects in the queue"""
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    
    print("📊 Current Project Queue Status:")
    print("=" * 80)
    
    cursor.execute("""
        SELECT id, status, session_name, spec_path, error_message
        FROM project_queue
        WHERE status IN ('processing', 'credit_paused', 'failed')
        ORDER BY id DESC
        LIMIT 10
    """)
    
    for row in cursor.fetchall():
        project_id, status, session_name, spec_path, error_msg = row
        spec_name = os.path.basename(spec_path) if spec_path else "N/A"
        print(f"Project {project_id}: {status}")
        print(f"  Spec: {spec_name}")
        print(f"  Session: {session_name or 'None'}")
        if error_msg:
            print(f"  Error: {error_msg[:100]}")
        
        # Check if session exists
        if session_name:
            try:
                result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                                      capture_output=True)
                session_exists = result.returncode == 0
                print(f"  Session exists: {session_exists}")
            except:
                print(f"  Session exists: Unable to check")
        print()
    
    conn.close()

def simulate_reboot_recovery():
    """Simulate what happens during scheduler startup after reboot"""
    print("\n🔄 Simulating Reboot Recovery...")
    print("=" * 80)
    
    # Initialize scheduler (this will trigger reboot recovery)
    print("Initializing scheduler (this triggers reboot recovery)...")
    scheduler = TmuxOrchestratorScheduler()
    
    print("\n✅ Reboot recovery simulation completed!")
    print("\nCheck the scheduler logs for detailed recovery information.")

if __name__ == "__main__":
    print("🧪 Reboot Recovery Test")
    print("=" * 80)
    
    # Show current status
    check_current_status()
    
    # Ask if we should simulate recovery
    response = input("\nSimulate reboot recovery? (y/n): ")
    if response.lower() == 'y':
        simulate_reboot_recovery()
        print("\n📊 Status After Recovery:")
        print("=" * 80)
        check_current_status()
    else:
        print("Skipping recovery simulation.")
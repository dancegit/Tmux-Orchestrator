#!/usr/bin/env python3
"""
Cleanup orphaned orchestration tmux sessions.
Identifies sessions that are completed/merged but still running.
"""

import subprocess
import sqlite3
import re
from pathlib import Path
from datetime import datetime, timedelta

def get_tmux_sessions():
    """Get all tmux sessions"""
    try:
        result = subprocess.run(['tmux', 'list-sessions'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            return []
        
        sessions = []
        for line in result.stdout.strip().split('\n'):
            if line:
                session_name = line.split(':')[0]
                sessions.append(session_name)
        return sessions
    except:
        return []

def get_active_sessions_from_db():
    """Get sessions that should still be running from database"""
    db_path = Path(__file__).parent / 'task_queue.db'
    if not db_path.exists():
        return set()
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get all sessions that are not completed or are recently completed (within 1 hour)
    one_hour_ago = (datetime.now() - timedelta(hours=1)).timestamp()
    cursor.execute("""
        SELECT orchestrator_session, main_session 
        FROM project_queue 
        WHERE status NOT IN ('completed', 'COMPLETED', 'failed', 'FAILED')
           OR (status IN ('completed', 'COMPLETED') AND completed_at > ?)
    """, (one_hour_ago,))
    
    active_sessions = set()
    for row in cursor.fetchall():
        if row[0]:
            active_sessions.add(row[0])
        if row[1]:
            active_sessions.add(row[1])
    
    conn.close()
    return active_sessions

def is_orchestration_session(session_name):
    """Check if a session name looks like an orchestration session"""
    patterns = [
        r'-impl-[a-f0-9]{8}',  # Implementation sessions
        r'-integr-[a-f0-9]{8}', # Integration sessions  
        r'mvp-.*-[a-f0-9]{8}', # MVP sessions
        r'orchestrator-.*-[a-f0-9]{8}',  # Orchestrator sessions
    ]
    
    for pattern in patterns:
        if re.search(pattern, session_name):
            return True
    return False

def cleanup_orphaned_sessions(dry_run=True):
    """Find and optionally kill orphaned sessions"""
    tmux_sessions = get_tmux_sessions()
    active_db_sessions = get_active_sessions_from_db()
    
    orphaned = []
    for session in tmux_sessions:
        # Check if it looks like an orchestration session
        if not is_orchestration_session(session):
            continue
            
        # Check if it's in the active sessions from database
        if session not in active_db_sessions:
            orphaned.append(session)
    
    if not orphaned:
        print("No orphaned orchestration sessions found.")
        return
    
    print(f"Found {len(orphaned)} orphaned orchestration session(s):")
    for session in orphaned:
        print(f"  - {session}")
    
    if not dry_run:
        print("\nKilling orphaned sessions...")
        for session in orphaned:
            try:
                subprocess.run(['tmux', 'kill-session', '-t', session], 
                             capture_output=True)
                print(f"  ✓ Killed: {session}")
            except Exception as e:
                print(f"  ✗ Failed to kill {session}: {e}")
    else:
        print("\nDry run - no sessions killed. Run with --kill to actually clean up.")

if __name__ == "__main__":
    import sys
    dry_run = '--kill' not in sys.argv
    cleanup_orphaned_sessions(dry_run=dry_run)
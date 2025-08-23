#!/usr/bin/env python3
"""
Quick fix to update database session_name for active projects with missing session names
"""

import sqlite3
import subprocess
import re
from typing import List, Tuple

def get_active_tmux_sessions() -> List[Tuple[str, str]]:
    """Get all active tmux sessions that look like project sessions"""
    try:
        result = subprocess.run(['tmux', 'list-sessions'], capture_output=True, text=True, check=True)
        sessions = []
        
        for line in result.stdout.strip().split('\n'):
            if line:
                # Extract session name (everything before first colon)
                session_name = line.split(':')[0]
                # Look for our project pattern: project-name-impl-XXXX
                if '-impl-' in session_name or 'elliott-wave' in session_name:
                    sessions.append((session_name, line))
        
        return sessions
    except subprocess.CalledProcessError:
        return []

def get_projects_with_missing_session_names() -> List[Tuple[int, str]]:
    """Get projects that are marked as processing but have no session_name"""
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, status, spec_path 
        FROM project_queue 
        WHERE session_name IS NULL 
        AND (status = 'processing' OR status = 'failed')
        ORDER BY id DESC
    """)
    
    projects = cursor.fetchall()
    conn.close()
    
    return projects

def update_session_name(project_id: int, session_name: str):
    """Update session_name for a project"""
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    
    cursor.execute("UPDATE project_queue SET session_name = ? WHERE id = ?", (session_name, project_id))
    conn.commit()
    conn.close()
    
    print(f"✓ Updated Project {project_id} with session_name: {session_name}")

def main():
    print("🔍 Scanning for active tmux sessions...")
    active_sessions = get_active_tmux_sessions()
    
    print("📋 Active project-like sessions:")
    for session_name, full_line in active_sessions:
        print(f"  - {session_name}")
    
    print("\n🔍 Scanning for projects with missing session names...")
    projects_missing_names = get_projects_with_missing_session_names()
    
    print("📋 Projects needing session name updates:")
    for project_id, status, spec_path in projects_missing_names:
        print(f"  - Project {project_id}: {status} ({spec_path})")
    
    # Try to match projects to sessions
    print("\n🔗 Attempting to match projects to active sessions...")
    
    for project_id, status, spec_path in projects_missing_names:
        # For Project 60, we know it's the elliott-wave session
        if project_id == 60:
            elliott_session = None
            for session_name, _ in active_sessions:
                if 'elliott-wave' in session_name and 'report' in session_name:
                    elliott_session = session_name
                    break
            
            if elliott_session:
                print(f"📌 Matched Project {project_id} to session: {elliott_session}")
                update_session_name(project_id, elliott_session)
            else:
                print(f"❌ Could not find matching session for Project {project_id}")

if __name__ == "__main__":
    main()
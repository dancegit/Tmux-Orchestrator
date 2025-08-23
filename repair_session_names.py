#!/usr/bin/env python3
"""
Repair database session_name corruption for Projects 61 & 62
"""

import sqlite3
import subprocess
import re
from typing import List, Tuple, Optional

def get_active_tmux_sessions() -> List[Tuple[str, str]]:
    """Get all active tmux sessions"""
    try:
        result = subprocess.run(['tmux', 'list-sessions'], capture_output=True, text=True, check=True)
        sessions = []
        
        for line in result.stdout.strip().split('\n'):
            if line:
                # Extract session name (everything before first colon)
                session_name = line.split(':')[0]
                sessions.append((session_name, line))
        
        return sessions
    except subprocess.CalledProcessError:
        print("❌ No tmux sessions found or tmux not available")
        return []

def get_project_details(project_id: int) -> Optional[Tuple[str, str, str]]:
    """Get project details from database"""
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT status, spec_path, session_name 
        FROM project_queue 
        WHERE id = ?
    """, (project_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    return result

def update_session_name(project_id: int, session_name: str):
    """Update session_name for a project"""
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    
    cursor.execute("UPDATE project_queue SET session_name = ? WHERE id = ?", (session_name, project_id))
    conn.commit()
    conn.close()
    
    print(f"✓ Updated Project {project_id} with session_name: {session_name}")

def generate_session_name(spec_path: str, project_id: int) -> str:
    """Generate expected session name based on spec path"""
    # Extract base name from spec path
    import os
    base_name = os.path.basename(spec_path)
    
    # Convert to session-friendly format
    if 'ELLIOTT_WAVE_MVP_IMPLEMENTATION' in base_name:
        # Project 62
        return f"elliott-wave-5-mvp-implementation-impl-{project_id:08x}"
    elif 'BACKTESTING_MVP_IMPLEMENTATION' in base_name:
        # Project 61  
        return f"backtesting-mvp-implementation-impl-{project_id:08x}"
    else:
        # Generic fallback
        name = base_name.replace('_', '-').replace('.md', '').lower()
        return f"{name}-impl-{project_id:08x}"

def find_matching_session(expected_pattern: str, active_sessions: List[Tuple[str, str]]) -> Optional[str]:
    """Find tmux session that matches the expected pattern"""
    for session_name, _ in active_sessions:
        # Look for key pattern matches
        if 'elliott-wave' in expected_pattern and 'elliott-wave' in session_name:
            return session_name
        if 'backtesting' in expected_pattern and 'backtesting' in session_name:
            return session_name
    return None

def main():
    print("🩹 Repairing session name corruption for Projects 61 & 62...")
    
    # Get current active sessions
    print("\n🔍 Scanning for active tmux sessions...")
    active_sessions = get_active_tmux_sessions()
    
    print("📋 Active sessions:")
    for session_name, full_line in active_sessions:
        print(f"  - {session_name}")
    
    # Check and repair each project
    for project_id in [61, 62]:
        print(f"\n🔧 Processing Project {project_id}...")
        
        project_details = get_project_details(project_id)
        if not project_details:
            print(f"❌ Project {project_id} not found in database")
            continue
            
        status, spec_path, current_session_name = project_details
        print(f"  Status: {status}")
        print(f"  Spec: {spec_path}")
        print(f"  Current session_name: {current_session_name or 'NULL'}")
        
        if current_session_name:
            print(f"  ✅ Session name already exists, skipping")
            continue
        
        # Generate expected session name
        expected_name = generate_session_name(spec_path, project_id)
        print(f"  Expected session name: {expected_name}")
        
        # Try to find matching active session
        matching_session = find_matching_session(expected_name, active_sessions)
        
        if matching_session:
            print(f"  🎯 Found matching active session: {matching_session}")
            update_session_name(project_id, matching_session)
        else:
            print(f"  💭 No matching active session, using expected name")
            update_session_name(project_id, expected_name)
    
    print("\n✅ Session name repair completed!")
    
    # Verify the repairs
    print("\n🔍 Verification - checking all projects 60, 61, 62:")
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, status, session_name FROM project_queue WHERE id IN (60, 61, 62) ORDER BY id')
    for row in cursor.fetchall():
        session_name = row[2] if row[2] else 'NULL'
        print(f"  Project {row[0]}: status={row[1]}, session_name={session_name}")
    conn.close()

if __name__ == "__main__":
    main()
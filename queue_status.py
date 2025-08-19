#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Tmux Orchestrator Queue Status Tool
Provides detailed queue status with conflict detection and management options
"""

import sqlite3
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

def get_active_tmux_sessions():
    """Get all active tmux sessions"""
    try:
        result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        return []
    except Exception:
        return []

def format_timestamp(timestamp):
    """Format unix timestamp to readable date"""
    if timestamp:
        try:
            return datetime.fromtimestamp(float(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return str(timestamp)
    return "Never"

def check_conflicts(projects, active_sessions):
    """Check for potential conflicts between queued projects and active sessions"""
    conflicts = []
    
    for proj in projects:
        project_id, spec_path, status, orch_session, main_session = proj[:5]
        
        # Check if project has sessions that are still active
        if main_session and main_session in active_sessions:
            conflicts.append({
                'project_id': project_id,
                'type': 'active_session',
                'message': f'Project {project_id} is {status} but session {main_session} is still active'
            })
        
        # Check for similar project names that might conflict
        project_name = Path(spec_path).stem.lower()
        for session in active_sessions:
            if project_name.replace('_', '-') in session.lower():
                conflicts.append({
                    'project_id': project_id,
                    'type': 'name_conflict',
                    'message': f'Project {project_id} ({project_name}) may conflict with active session: {session}'
                })
    
    return conflicts

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print("""
Tmux Orchestrator Queue Status Tool

Usage:
  queue_status.py [options]

Options:
  -h, --help      Show this help
  --conflicts     Only show conflicts
  --active        Show active tmux sessions
  --reset <id>    Reset project to queued status
  --fresh <id>    Mark project for fresh start
  --remove <id>   Remove project from queue

Examples:
  queue_status.py              # Show full status
  queue_status.py --conflicts  # Show only conflicts
  queue_status.py --reset 15   # Reset project 15
  queue_status.py --fresh 18   # Mark project 18 for fresh start
        """)
        return

    db_path = 'task_queue.db'
    if not Path(db_path).exists():
        print("❌ Queue database not found. Run from Tmux-Orchestrator directory.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Handle specific actions
    if len(sys.argv) > 2:
        action = sys.argv[1]
        project_id = int(sys.argv[2])
        
        if action == '--reset':
            cursor.execute("""
                UPDATE project_queue 
                SET status = 'queued', started_at = NULL, completed_at = NULL, 
                    error_message = NULL, orchestrator_session = NULL, main_session = NULL
                WHERE id = ?
            """, (project_id,))
            conn.commit()
            print(f"✅ Project {project_id} reset to queued status")
            return
            
        elif action == '--fresh':
            cursor.execute("UPDATE project_queue SET fresh_start = 1 WHERE id = ?", (project_id,))
            conn.commit()
            print(f"✅ Project {project_id} marked for fresh start")
            return
            
        elif action == '--remove':
            cursor.execute("DELETE FROM project_queue WHERE id = ?", (project_id,))
            conn.commit()
            print(f"✅ Project {project_id} removed from queue")
            return

    # Get all projects
    cursor.execute("""
        SELECT id, spec_path, status, orchestrator_session, main_session, 
               enqueued_at, started_at, completed_at, error_message, fresh_start, priority
        FROM project_queue 
        ORDER BY priority DESC, enqueued_at ASC
    """)
    projects = cursor.fetchall()
    
    # Get active tmux sessions
    active_sessions = get_active_tmux_sessions()
    
    # Check for conflicts
    conflicts = check_conflicts(projects, active_sessions)
    
    # Handle specific display options
    if len(sys.argv) > 1:
        if sys.argv[1] == '--conflicts':
            if conflicts:
                print("⚠️  CONFLICTS DETECTED:")
                for conflict in conflicts:
                    print(f"  • {conflict['message']}")
            else:
                print("✅ No conflicts detected")
            return
        elif sys.argv[1] == '--active':
            print("🔄 ACTIVE TMUX SESSIONS:")
            for session in active_sessions:
                print(f"  • {session}")
            return

    # Full status display
    print("=" * 80)
    print("📋 TMUX ORCHESTRATOR QUEUE STATUS")
    print("=" * 80)
    
    if conflicts:
        print(f"\n⚠️  {len(conflicts)} CONFLICT(S) DETECTED:")
        for conflict in conflicts:
            print(f"  🚨 {conflict['message']}")
        print()
    
    print(f"📊 QUEUE SUMMARY:")
    status_counts = {}
    for proj in projects:
        status = proj[2]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    for status, count in status_counts.items():
        print(f"  • {status.upper()}: {count}")
    
    print(f"\n🔄 ACTIVE SESSIONS: {len(active_sessions)}")
    for session in active_sessions:
        if 'impl' in session or 'orchestrator' in session:
            print(f"  • {session}")
    
    print(f"\n📋 DETAILED QUEUE ({len(projects)} projects):")
    print("-" * 80)
    
    for proj in projects:
        project_id, spec_path, status, orch_session, main_session, enqueued_at, started_at, completed_at, error_message, fresh_start, priority = proj
        
        # Extract project name
        project_name = Path(spec_path).stem.replace('_', ' ').title()
        
        # Status indicators
        status_emoji = {
            'queued': '⏳',
            'processing': '🔄', 
            'completed': '✅',
            'failed': '❌',
            'retried': '🔁'
        }.get(status, '❓')
        
        fresh_indicator = ' 🆕' if fresh_start else ''
        priority_indicator = f' (P{priority})' if priority != 0 else ''
        
        print(f"{status_emoji} [{project_id:2d}] {project_name}{fresh_indicator}{priority_indicator}")
        print(f"     Status: {status.upper()}")
        print(f"     Spec: {spec_path}")
        print(f"     Enqueued: {format_timestamp(enqueued_at)}")
        
        if started_at:
            print(f"     Started: {format_timestamp(started_at)}")
        if completed_at:
            print(f"     Completed: {format_timestamp(completed_at)}")
        if main_session:
            session_status = "🟢 ACTIVE" if main_session in active_sessions else "🔴 DEAD"
            print(f"     Session: {main_session} ({session_status})")
        if error_message:
            print(f"     Error: {error_message[:100]}...")
        
        print()
    
    print("-" * 80)
    print("💡 USAGE:")
    print("  queue_status.py --conflicts    # Show only conflicts")
    print("  queue_status.py --reset <id>   # Reset project to queued")
    print("  queue_status.py --fresh <id>   # Mark for fresh start") 
    print("  queue_status.py --remove <id>  # Remove from queue")
    
    conn.close()

if __name__ == '__main__':
    main()
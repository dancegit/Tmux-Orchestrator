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

# NEW: Imports for inter-process locking
import json
import socket
from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_UN

def get_active_tmux_sessions():
    """Get all active tmux sessions - DEPRECATED: Use tmux_utils.get_active_sessions() instead"""
    # Import here to avoid circular imports
    try:
        from tmux_utils import get_active_sessions
        return get_active_sessions()
    except ImportError:
        # Fallback to local implementation
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
  -h, --help         Show this help
  --conflicts        Only show conflicts
  --active           Show active tmux sessions
  --reset <id>       Reset project to queued status
  --fresh <id>       Mark project for fresh start
  --remove <id>      Remove project from queue
  --resume <id>      Resume project by calling auto_orchestrate.py --resume
  --cleanup-stale    Clean stale registry entries (inactive sessions)

Examples:
  queue_status.py                # Show full status
  queue_status.py --conflicts    # Show only conflicts
  queue_status.py --reset 15     # Reset project 15
  queue_status.py --fresh 18     # Mark project 18 for fresh start
  queue_status.py --resume 42    # Resume project 42
  queue_status.py --cleanup-stale # Clean stale registries
        """)
        return

    db_path = 'task_queue.db'
    if not Path(db_path).exists():
        print("❌ Queue database not found. Run from Tmux-Orchestrator directory.")
        return
    
    # NEW: Check if this is a write operation
    is_write_op = any(opt in sys.argv for opt in ['--reset', '--fresh', '--remove', '--resume', '--cleanup-stale'])
    # Note: --remove uses safe removal logic that checks for processing status
    
    # NEW: Acquire lock only for writes
    lock_path = Path('locks/project_queue.lock')
    lock_fd = None
    if is_write_op:
        try:
            # Create lock file if it doesn't exist, then open for reading
            lock_path.parent.mkdir(exist_ok=True)
            lock_fd = open(lock_path, 'a+')
            flock(lock_fd, LOCK_EX | LOCK_NB)
        except IOError:
            # For --remove, provide helpful guidance instead of hard failure
            if '--remove' in sys.argv:
                project_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
                if project_id:
                    print("⚠️ Cannot acquire lock - scheduler is active.")
                    print(f"💡 Alternative: Use scheduler's built-in removal:")
                    print(f"   python3 scheduler.py --remove-project {project_id}")
                    return
                else:
                    print("❌ Invalid project ID for removal")
                    return
            else:
                print("❌ Cannot acquire lock for write operation. Scheduler may be active.")
                return

    # NEW: Connect with WAL and busy_timeout
    conn = sqlite3.connect(db_path, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=10000;")
    
    # Handle cleanup-stale (no ID needed)
    if len(sys.argv) > 1 and sys.argv[1] == '--cleanup-stale':
        from session_state import SessionStateManager
        session_mgr = SessionStateManager()
        print("🧹 Cleaning stale registry entries...")
        session_mgr.cleanup_stale_registries()
        print("✅ Cleanup complete")
        return
    
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
            # Use the same logic as scheduler's remove_project_from_queue but without lock contention
            print(f"🔄 Removing project {project_id} using scheduler-compatible logic...")
            
            # Check if project exists and get status
            cursor.execute("SELECT status FROM project_queue WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                print(f"❌ Project {project_id} not found")
                return
            
            status = row[0]
            if status == 'processing':
                print(f"❌ Cannot remove project {project_id} - still processing")
                print("   Use `./qs --reset <id>` to reset stuck projects first")
                return
            
            # Safe to remove completed/failed/queued projects
            cursor.execute("DELETE FROM project_queue WHERE id = ?", (project_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                print(f"✅ Project {project_id} removed from queue (was {status})")
            else:
                print(f"❌ Failed to remove project {project_id}")
            return
            
        elif action == '--resume':
            # Get project details
            cursor.execute("SELECT spec_path, project_path FROM project_queue WHERE id = ?", (project_id,))
            result = cursor.fetchone()
            
            if not result:
                print(f"❌ Project {project_id} not found in queue")
                return
                
            spec_path, project_path = result
            
            # Determine project path for auto_orchestrate.py
            if project_path:
                resume_path = project_path
            else:
                # Extract from spec_path
                resume_path = str(Path(spec_path).parent)
            
            print(f"🔄 Resuming project {project_id}...")
            print(f"   Spec: {spec_path}")
            print(f"   Project Path: {resume_path}")
            
            # Run auto_orchestrate.py --resume in tmux
            import subprocess
            try:
                result = subprocess.run([
                    'tmux', 'new-session', '-d', '-s', f'resume-project-{project_id}',
                    'bash', '-c', f'cd /home/clauderun/Tmux-Orchestrator && ./auto_orchestrate.py --project {resume_path} --resume --daemon'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"✅ Project {project_id} resume initiated in tmux session: resume-project-{project_id}")
                    print(f"   Attach with: tmux attach -t resume-project-{project_id}")
                else:
                    print(f"❌ Failed to resume project {project_id}")
                    print(f"   Error: {result.stderr}")
                    
            except Exception as e:
                print(f"❌ Error running resume command: {e}")
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
    print("  queue_status.py --conflicts      # Show only conflicts")
    print("  queue_status.py --reset <id>     # Reset project to queued")
    print("  queue_status.py --fresh <id>     # Mark for fresh start") 
    print("  queue_status.py --remove <id>    # Remove from queue (or use: python3 scheduler.py --remove-project <id>)")
    print("  queue_status.py --cleanup-stale  # Clean stale registries")
    
    conn.close()
    
    # NEW: Release lock if held
    if lock_fd:
        flock(lock_fd, LOCK_UN)
        lock_fd.close()

if __name__ == '__main__':
    main()
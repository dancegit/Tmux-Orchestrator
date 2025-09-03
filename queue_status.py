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

def reconcile_missing_sessions(cursor, conn, projects, active_sessions):
    """Reconcile projects in PROCESSING state with missing tmux sessions - mark as FAILED."""
    reconciled = []
    
    # Check if reconciliation is disabled
    if os.getenv('DISABLE_RECONCILIATION', 'false').lower() == 'true':
        return reconciled
    
    for proj in projects:
        proj_id = proj[0]      # id
        spec_path = proj[1]    # spec_path
        status = proj[2]       # status 
        main_session = proj[4] # main_session
        session_name = proj[5] # session_name
        
        # Check if project is PROCESSING and session is missing
        if status in ('PROCESSING', 'processing'):
            session_to_check = session_name or main_session
            if session_to_check and session_to_check not in active_sessions:
                # Double-check with direct tmux command to avoid false positives
                import subprocess
                try:
                    result = subprocess.run(['tmux', 'has-session', '-t', session_to_check], 
                                          capture_output=True, text=True)
                    if result.returncode != 0:
                        # Session truly doesn't exist
                        print(f"⚠️  Detected missing session for project ID {proj_id}: {Path(spec_path).name}")
                        print(f"    Session checked: {session_to_check}")
                        
                        # Update DB to FAILED 
                        cursor.execute(
                            "UPDATE project_queue SET status = 'FAILED', completed_at = ?, error_message = 'Session disappeared - auto-recovered' WHERE id = ?",
                            (datetime.now().timestamp(), proj_id)
                        )
                        reconciled.append(proj_id)
                    else:
                        # False positive - session exists but not in active_sessions list
                        print(f"ℹ️  Session '{session_to_check}' exists but was missing from active_sessions cache")
                except Exception as e:
                    print(f"❌ Error verifying session {session_to_check}: {e}")
    
    if reconciled:
        conn.commit()
        print(f"✅ Marked {len(reconciled)} missing sessions as FAILED")
    
    return reconciled

def reconcile_orphaned_sessions(cursor, conn, projects, active_sessions):
    """Reconcile tmux sessions that exist but aren't tracked in project_queue"""
    reconciled = []
    
    # Check if reconciliation is disabled
    if os.getenv('DISABLE_RECONCILIATION', 'false').lower() == 'true':
        return reconciled
    
    # Get all session identifiers from projects (both main_session and session_name)
    tracked_sessions = set()
    for proj in projects:
        main_session = proj[4]      # main_session is at index 4
        session_name = proj[5]      # session_name is at index 5 (NEW!)
        if main_session:
            tracked_sessions.add(main_session)
        if session_name:
            tracked_sessions.add(session_name)
    
    # Load exclusion list
    excluded_sessions = set()
    exclude_file = Path('.reconciliation_exclude')
    if exclude_file.exists():
        with open(exclude_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    excluded_sessions.add(line)
    
    # Find orphaned sessions (active tmux sessions not in queue)
    orphaned_sessions = []
    for session in active_sessions:
        # Only consider project-like sessions (contain '-impl-' pattern)
        if '-impl-' in session and session not in tracked_sessions and session not in excluded_sessions:
            orphaned_sessions.append(session)
    
    # Add orphaned sessions to queue
    for session in orphaned_sessions:
        try:
            # Try to find metadata for this session
            registry_dir = Path(f'registry/projects/{session.split("-impl-")[0]}')
            metadata_file = registry_dir / 'orchestration_metadata.json'
            spec_path = None
            
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    # Try to find spec from the registry
                    spec_files = list(registry_dir.glob('*.md')) + list(registry_dir.glob('*.txt'))
                    if spec_files:
                        spec_path = str(spec_files[0])
            
            if not spec_path:
                # Use a placeholder spec path if we can't find the original
                spec_path = f"registry/orphaned/{session}/unknown-spec.md"
            
            # Add to project_queue as processing
            cursor.execute("""
                INSERT OR IGNORE INTO project_queue 
                (spec_path, main_session, session_name, status, started_at, orchestrator_session)
                VALUES (?, ?, ?, 'processing', strftime('%s', 'now'), ?)
            """, (spec_path, session, session, session))
            
            if cursor.rowcount > 0:
                reconciled.append(session)
                print(f"🔄 Reconciled orphaned session: {session}")
                
        except Exception as e:
            print(f"⚠️  Failed to reconcile session {session}: {e}")
    
    if reconciled:
        conn.commit()
    
    return reconciled

def check_conflicts(projects, active_sessions):
    """Check for potential conflicts between queued projects and active sessions"""
    conflicts = []
    
    for proj in projects:
        project_id, spec_path, status, orch_session, main_session = proj[:5]
        
        # Check if project has sessions that are still active
        if main_session and main_session in active_sessions:
            # Only a conflict if status is NOT processing (e.g., completed/failed but session still running)
            if status != 'processing':
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
  --reset <id>       Reset project to queued status (delegated to scheduler)
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
    # Note: --reset is now delegated to scheduler, so it doesn't need lock
    is_write_op = any(opt in sys.argv for opt in ['--fresh', '--remove', '--resume', '--cleanup-stale'])
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
    
    # Initialize project_queue table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spec_path TEXT NOT NULL,
            project_path TEXT,  -- Can be null if auto-detected
            status TEXT DEFAULT 'queued',  -- queued, processing, completed, failed, retried, permanently_failed, credit_paused
            enqueued_at REAL DEFAULT (strftime('%s', 'now')),
            started_at REAL,
            completed_at REAL,
            priority INTEGER DEFAULT 0,  -- Higher = sooner
            error_message TEXT,
            batch_id TEXT,  -- Groups related projects for batch processing
            orchestrator_session TEXT,
            main_session TEXT,
            log_file TEXT,
            retry_count INTEGER DEFAULT 0,
            fresh_start BOOLEAN DEFAULT 0,  -- Flag for retries, different from --resume
            auto_orchestrate_args TEXT,  -- Store original args for retries
            failed_components TEXT,  -- Track which components failed
            research_session_id TEXT,  -- For enhanced specs from research
            
            CONSTRAINT unique_spec_queued UNIQUE(spec_path, status) ON CONFLICT IGNORE
        )
    """)
    
    # Handle filter options
    if len(sys.argv) > 1 and sys.argv[1] == '--merged':
        # Show only merged projects
        cursor.execute("""
            SELECT id, spec_path, status, orchestrator_session, main_session, session_name,
                   enqueued_at, started_at, completed_at, error_message, fresh_start, priority,
                   merged_status, merged_at
            FROM project_queue 
            WHERE merged_status = 'merged'
            ORDER BY merged_at DESC
        """)
        projects = cursor.fetchall()
        print("🔀 MERGED PROJECTS:")
        for proj in projects:
            project_id = proj[0]
            spec_path = proj[1]
            merged_at = proj[13]
            project_name = Path(spec_path).stem.replace('_', ' ').title()
            print(f"  ✅ [{project_id:2d}] {project_name} - Merged: {format_timestamp(merged_at)}")
        return
    
    if len(sys.argv) > 1 and sys.argv[1] == '--pending-merge':
        # Show only pending merge projects
        cursor.execute("""
            SELECT id, spec_path, status, orchestrator_session, main_session, session_name,
                   enqueued_at, started_at, completed_at, error_message, fresh_start, priority,
                   merged_status, merged_at
            FROM project_queue 
            WHERE merged_status = 'pending_merge'
            ORDER BY completed_at ASC
        """)
        projects = cursor.fetchall()
        print("⏳ PROJECTS PENDING MERGE:")
        for proj in projects:
            project_id = proj[0]
            spec_path = proj[1]
            completed_at = proj[8]
            project_name = Path(spec_path).stem.replace('_', ' ').title()
            print(f"  ⏳ [{project_id:2d}] {project_name} - Completed: {format_timestamp(completed_at)}")
        return
    
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
            # Delegate to scheduler instead of direct database manipulation
            print(f"🔄 Delegating reset of project {project_id} to scheduler...")
            import subprocess
            import os
            try:
                # Use system python and explicitly disable uv to avoid psutil import issues
                scheduler_path = Path(__file__).parent / 'scheduler.py'
                env = os.environ.copy()
                env['PATH'] = '/usr/bin:/bin:' + env.get('PATH', '')  # Prioritize system python
                result = subprocess.run([
                    '/usr/bin/python3', str(scheduler_path), '--delegated-reset', str(project_id)
                ], capture_output=True, text=True, env=env)
                
                if result.returncode == 0:
                    print(f"✅ Project {project_id} reset successfully via scheduler")
                    if result.stdout.strip():
                        print(f"   {result.stdout.strip()}")
                else:
                    print(f"❌ Failed to reset project {project_id}")
                    if result.stderr.strip():
                        print(f"   Error: {result.stderr.strip()}")
                return
            except Exception as e:
                print(f"❌ Error running scheduler reset command: {e}")
                return
            
        elif action == '--fresh':
            # This could also be delegated to scheduler, but it's a simple operation
            # Try direct DB access first, then delegate if lock fails
            try:
                cursor.execute("UPDATE project_queue SET fresh_start = 1 WHERE id = ?", (project_id,))
                conn.commit()
                print(f"✅ Project {project_id} marked for fresh start")
                return
            except Exception as e:
                print(f"⚠️  Direct update failed: {e}")
                print(f"🔄 Note: --fresh operation may need scheduler delegation if this persists")
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
        SELECT id, spec_path, status, orchestrator_session, main_session, session_name,
               enqueued_at, started_at, completed_at, error_message, fresh_start, priority,
               merged_status, merged_at
        FROM project_queue 
        ORDER BY priority DESC, enqueued_at ASC
    """)
    projects = cursor.fetchall()
    
    # Get active tmux sessions
    active_sessions = get_active_tmux_sessions()
    
    # Reconcile orphaned sessions (tmux sessions not in queue)
    # Reconcile orphaned sessions (sessions exist but not tracked)
    reconciled_orphaned = reconcile_orphaned_sessions(cursor, conn, projects, active_sessions)
    
    # Reconcile missing sessions (projects PROCESSING but sessions gone)
    reconciled_missing = reconcile_missing_sessions(cursor, conn, projects, active_sessions)
    
    reconciled_sessions = reconciled_orphaned + reconciled_missing
    
    # If we reconciled any sessions, re-fetch projects to include them
    if reconciled_sessions:
        cursor.execute("""
            SELECT id, spec_path, status, orchestrator_session, main_session, session_name,
                   enqueued_at, started_at, completed_at, error_message, fresh_start, priority,
                   merged_status, merged_at
            FROM project_queue 
            ORDER BY priority DESC, enqueued_at ASC
        """)
        projects = cursor.fetchall()
    
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
        # Handle both old and new schema (with merged_status fields)
        if len(proj) >= 14:
            project_id, spec_path, status, orch_session, main_session, session_name, enqueued_at, started_at, completed_at, error_message, fresh_start, priority, merged_status, merged_at = proj
        else:
            project_id, spec_path, status, orch_session, main_session, session_name, enqueued_at, started_at, completed_at, error_message, fresh_start, priority = proj
            merged_status = None
            merged_at = None
        
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
        
        # Add merge status indicator
        merge_indicator = ''
        if merged_status == 'merged':
            merge_indicator = ' 🔀[MERGED]'
        elif merged_status == 'pending_merge':
            merge_indicator = ' ⏳[PENDING MERGE]'
        elif merged_status == 'merge_failed':
            merge_indicator = ' ❌[MERGE FAILED]'
        
        print(f"{status_emoji} [{project_id:2d}] {project_name}{fresh_indicator}{priority_indicator}{merge_indicator}")
        print(f"     Status: {status.upper()}")
        print(f"     Spec: {spec_path}")
        print(f"     Enqueued: {format_timestamp(enqueued_at)}")
        
        if started_at:
            print(f"     Started: {format_timestamp(started_at)}")
        if completed_at:
            print(f"     Completed: {format_timestamp(completed_at)}")
        
        if merged_at:
            print(f"     Merged: {format_timestamp(merged_at)}")
        if main_session:
            session_status = "🟢 ACTIVE" if main_session in active_sessions else "🔴 DEAD"
            print(f"     Session: {main_session} ({session_status})")
        if error_message:
            print(f"     Error: {error_message[:100]}...")
        
        print()
    
    print("-" * 80)
    print("💡 USAGE:")
    print("  queue_status.py --conflicts      # Show only conflicts")
    print("  queue_status.py --reset <id>     # Reset project to queued (works even when scheduler active)")
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
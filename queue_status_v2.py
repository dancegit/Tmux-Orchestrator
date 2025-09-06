#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Tmux Orchestrator Queue Status Tool V2
Provides filtered queue status with smart defaults and flexible viewing options
"""

import sqlite3
import subprocess
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# NEW: Imports for inter-process locking
import json
import socket
from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_UN


def get_active_tmux_sessions():
    """Get all active tmux sessions"""
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


def parse_arguments():
    """Parse command line arguments with improved filtering options"""
    parser = argparse.ArgumentParser(
        description='Tmux Orchestrator Queue Status - Smart filtering and display',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  qs                    # Default: Show processing + last 3 completed projects
  qs --all              # Show all projects (old behavior)
  qs --failed           # Show only failed projects
  qs --completed        # Show all completed projects
  qs -n 10              # Show last 10 projects (any status)
  qs --failed -n 5      # Show last 5 failed projects
  qs --status processing # Show only processing projects
  
Actions:
  qs --reset 42         # Reset project 42 to queued
  qs --fresh 42         # Mark project 42 for fresh start
  qs --remove 42        # Remove project 42 from queue
  qs --cleanup-stale    # Clean stale registries
  qs --conflicts        # Show only conflicts
        """
    )
    
    # Display filters
    filter_group = parser.add_argument_group('display filters')
    filter_group.add_argument('--all', action='store_true',
                            help='Show all projects (override smart defaults)')
    filter_group.add_argument('--processing', action='store_true',
                            help='Show only processing projects')
    filter_group.add_argument('--completed', action='store_true',
                            help='Show all completed projects')
    filter_group.add_argument('--failed', action='store_true',
                            help='Show only failed projects')
    filter_group.add_argument('--queued', action='store_true',
                            help='Show only queued projects')
    filter_group.add_argument('--cancelled', action='store_true',
                            help='Show only cancelled projects')
    filter_group.add_argument('--superseded', action='store_true',
                            help='Show only superseded projects')
    filter_group.add_argument('--archived', action='store_true',
                            help='Show only archived projects')
    filter_group.add_argument('--merged', action='store_true',
                            help='Show only merged projects')
    filter_group.add_argument('--status', type=str, metavar='STATUS',
                            help='Filter by specific status (case-insensitive)')
    filter_group.add_argument('-n', '--number', type=int, metavar='N',
                            help='Limit output to last N projects')
    filter_group.add_argument('--conflicts', action='store_true',
                            help='Show only conflicts')
    filter_group.add_argument('--active', action='store_true',
                            help='Show active tmux sessions')
    
    # Actions
    action_group = parser.add_argument_group('actions')
    action_group.add_argument('--reset', type=int, metavar='ID',
                            help='Reset project to queued')
    action_group.add_argument('--fresh', type=int, metavar='ID',
                            help='Mark project for fresh start')
    action_group.add_argument('--remove', type=int, metavar='ID',
                            help='Remove project from queue')
    action_group.add_argument('--cleanup-stale', action='store_true',
                            help='Clean stale registries')
    
    # Display options
    display_group = parser.add_argument_group('display options')
    display_group.add_argument('--compact', action='store_true',
                              help='Compact output (one line per project)')
    display_group.add_argument('--no-summary', action='store_true',
                              help='Hide queue summary')
    display_group.add_argument('--no-usage', action='store_true',
                              help='Hide usage instructions')
    
    return parser.parse_args()


def check_conflicts(projects: List[tuple], active_sessions: List[str]) -> List[Dict[str, Any]]:
    """Check for various types of conflicts in the queue"""
    conflicts = []
    
    # Check for projects with duplicate sessions
    session_projects = {}
    for proj in projects:
        project_id = proj[0]
        spec_path = proj[1]
        status = proj[2]
        main_session = proj[4]
        session_name = proj[5]
        
        session_to_check = session_name or main_session
        if session_to_check and status in ('processing', 'PROCESSING'):
            if session_to_check in session_projects:
                conflicts.append({
                    'type': 'duplicate_session',
                    'message': f"Projects {session_projects[session_to_check]} and {project_id} both using session: {session_to_check}"
                })
            else:
                session_projects[session_to_check] = project_id
    
    # Check for processing projects with missing sessions
    for proj in projects:
        project_id = proj[0]
        spec_path = proj[1]
        status = proj[2]
        main_session = proj[4]
        session_name = proj[5]
        
        if status in ('processing', 'PROCESSING'):
            session_to_check = session_name or main_session
            if session_to_check and session_to_check not in active_sessions:
                project_name = Path(spec_path).stem
                conflicts.append({
                    'type': 'missing_session',
                    'message': f"Project {project_id} ({project_name}) is PROCESSING but session missing: {session_to_check}"
                })
    
    # Check for orphaned sessions
    for session in active_sessions:
        if ('impl' in session or 'orchestrator' in session) and not any(
            (proj[4] == session or proj[5] == session) for proj in projects
        ):
            if session not in ['orchestrator']:  # Skip known system sessions
                conflicts.append({
                    'type': 'orphaned_session',
                    'message': f"Session {session} exists but not tracked in queue"
                })
    
    # Check for projects in same spec that might conflict
    spec_projects = {}
    for proj in projects:
        project_id = proj[0]
        spec_path = proj[1]
        status = proj[2]
        
        if status in ('processing', 'PROCESSING', 'queued'):
            spec_name = Path(spec_path).name
            if spec_name in spec_projects:
                other_id = spec_projects[spec_name]
                conflicts.append({
                    'type': 'duplicate_spec',
                    'message': f"Projects {other_id} and {project_id} use same spec: {spec_name}"
                })
            else:
                spec_projects[spec_name] = project_id
    
    # Find conflicts where multiple projects might be trying to use the same session
    for proj in projects:
        project_id = proj[0]
        spec_path = proj[1]
        status = proj[2]
        main_session = proj[4]
        
        # Check if any active session might interfere
        spec_name = Path(spec_path).stem.lower()
        for session in active_sessions:
            session_lower = session.lower()
            # Look for potential matches based on spec name
            if spec_name in session_lower or session_lower in spec_name:
                # Check if this session belongs to a different project
                if not any((p[0] == project_id and (p[4] == session or p[5] == session)) for p in projects):
                    # Only flag if not already tracked
                    if status in ('queued', 'processing') and session not in [p[4] for p in projects] + [p[5] for p in projects]:
                        conflicts.append({
                            'type': 'potential_conflict',
                            'message': f"Project {project_id} ({spec_name}) may conflict with active session: {session}"
                        })
                        break
    
    return conflicts


def reconcile_missing_sessions(cursor, conn, projects, active_sessions):
    """Reconcile projects in PROCESSING state with missing tmux sessions"""
    reconciled = []
    
    if os.getenv('DISABLE_RECONCILIATION', 'false').lower() == 'true':
        return reconciled
    
    for proj in projects:
        proj_id = proj[0]
        spec_path = proj[1]
        status = proj[2]
        main_session = proj[4]
        session_name = proj[5]
        
        if status in ('PROCESSING', 'processing'):
            session_to_check = session_name or main_session
            if session_to_check and session_to_check not in active_sessions:
                try:
                    result = subprocess.run(['tmux', 'has-session', '-t', session_to_check], 
                                          capture_output=True, text=True)
                    if result.returncode != 0:
                        print(f"⚠️  Detected missing session for project ID {proj_id}: {Path(spec_path).name}")
                        print(f"    Session checked: {session_to_check}")
                        
                        cursor.execute(
                            "UPDATE project_queue SET status = 'FAILED', completed_at = ?, error_message = 'Session disappeared - auto-recovered' WHERE id = ?",
                            (datetime.now().timestamp(), proj_id)
                        )
                        reconciled.append(proj_id)
                    else:
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
    
    if os.getenv('DISABLE_RECONCILIATION', 'false').lower() == 'true':
        return reconciled
    
    for session in active_sessions:
        if 'impl' in session or 'spec' in session:
            session_tracked = any(
                (proj[4] == session or proj[5] == session) for proj in projects
            )
            
            if not session_tracked and session not in ['orchestrator']:
                print(f"⚠️  Found orphaned session: {session}")
                reconciled.append(session)
    
    return reconciled


def filter_projects(projects: List[tuple], args: argparse.Namespace) -> List[tuple]:
    """Filter projects based on command line arguments"""
    filtered = projects
    
    # If --all is specified, return everything (with optional limit)
    if args.all:
        if args.number:
            return filtered[:args.number]
        return filtered
    
    # Apply status filters
    status_filters = []
    
    if args.processing:
        status_filters.append('processing')
    if args.completed:
        status_filters.append('completed')
    if args.failed:
        status_filters.append('failed')
    if args.queued:
        status_filters.append('queued')
    if args.cancelled:
        status_filters.append('cancelled')
    if args.superseded:
        status_filters.append('superseded')
    if args.archived:
        status_filters.append('archived')
    
    # Custom status filter
    if args.status:
        status_filters.append(args.status.lower())
    
    # If specific filters are provided, use them
    if status_filters:
        filtered = [p for p in projects if p[2].lower() in status_filters]
    
    # Filter by merge status if requested
    if args.merged and len(projects[0]) >= 14:
        filtered = [p for p in filtered if len(p) >= 14 and p[12] == 'merged']
    
    # Default behavior: show processing + last 3 completed
    if not any([args.all, args.processing, args.completed, args.failed, 
                args.queued, args.cancelled, args.superseded, args.archived,
                args.status, args.merged]):
        processing = [p for p in projects if p[2].lower() in ['processing']]
        completed = [p for p in projects if p[2].lower() == 'completed']
        # Sort completed by completed_at (index 8) descending - handle various timestamp formats
        def get_timestamp(x):
            if not x[8]:
                return 0
            try:
                # Try to convert to float (unix timestamp)
                return float(x[8])
            except (ValueError, TypeError):
                # If it's a string timestamp, try to parse it
                try:
                    from datetime import datetime
                    return datetime.fromisoformat(x[8].replace('T', ' ')).timestamp()
                except:
                    return 0
        completed.sort(key=get_timestamp, reverse=True)
        filtered = processing + completed[:3]
    
    # Apply number limit if specified
    if args.number:
        filtered = filtered[:args.number]
    
    return filtered


def display_project_compact(proj: tuple, active_sessions: List[str]) -> None:
    """Display project in compact format (one line)"""
    project_id = proj[0]
    spec_path = proj[1]
    status = proj[2]
    main_session = proj[4] if len(proj) > 4 else None
    error_message = proj[9] if len(proj) > 9 else None
    
    project_name = Path(spec_path).stem.replace('_', ' ').title()
    
    status_emoji = {
        'queued': '⏳',
        'processing': '🔄', 
        'completed': '✅',
        'failed': '❌',
        'cancelled': '🚫',
        'superseded': '♻️',
        'archived': '📦'
    }.get(status.lower(), '❓')
    
    session_status = ""
    if main_session:
        if main_session in active_sessions:
            session_status = " [🟢]"
        elif status.lower() in ['processing']:
            session_status = " [🔴]"
    
    error_suffix = f" - {error_message[:50]}..." if error_message else ""
    
    print(f"{status_emoji} [{project_id:3d}] {status.upper():12s} {project_name[:40]:40s}{session_status}{error_suffix}")


def display_project_detailed(proj: tuple, active_sessions: List[str]) -> None:
    """Display project in detailed format (multiple lines)"""
    # Handle both old and new schema
    if len(proj) >= 14:
        project_id, spec_path, status, orch_session, main_session, session_name, \
        enqueued_at, started_at, completed_at, error_message, fresh_start, priority, \
        merged_status, merged_at = proj
    else:
        project_id, spec_path, status, orch_session, main_session, session_name, \
        enqueued_at, started_at, completed_at, error_message, fresh_start, priority = proj
        merged_status = None
        merged_at = None
    
    project_name = Path(spec_path).stem.replace('_', ' ').title()
    
    status_emoji = {
        'queued': '⏳',
        'processing': '🔄', 
        'completed': '✅',
        'failed': '❌',
        'cancelled': '🚫',
        'superseded': '♻️',
        'archived': '📦'
    }.get(status.lower(), '❓')
    
    fresh_indicator = ' 🆕' if fresh_start else ''
    priority_indicator = f' (P{priority})' if priority != 0 else ''
    
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
        if status.lower() in ("completed", "failed") and merged_status == "merged":
            session_status = "✅ COMPLETED"
        else:
            session_status = "🟢 ACTIVE" if main_session in active_sessions else "🔴 DEAD"
        print(f"     Session: {main_session} ({session_status})")
    
    if error_message:
        print(f"     Error: {error_message[:100]}...")
    
    print()


def main():
    """Main function with improved filtering and display options"""
    args = parse_arguments()
    
    # Handle action commands first
    if args.reset or args.fresh or args.remove or args.cleanup_stale:
        # These are handled by the existing code
        # Import the original functions or delegate to scheduler
        if args.reset:
            print(f"🔄 Delegating reset of project {args.reset} to scheduler...")
            import subprocess
            scheduler_path = Path(__file__).parent / 'scheduler.py'
            env = os.environ.copy()
            env['PATH'] = '/usr/bin:/bin:' + env.get('PATH', '')
            result = subprocess.run([
                '/usr/bin/python3', str(scheduler_path), '--delegated-reset', str(args.reset)
            ], capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                print(f"✅ Project {args.reset} reset successfully via scheduler")
                if result.stdout.strip():
                    print(f"   {result.stdout.strip()}")
            else:
                print(f"❌ Failed to reset project {args.reset}")
                if result.stderr.strip():
                    print(f"   Error: {result.stderr.strip()}")
            return
        
        if args.fresh:
            print(f"🆕 Marking project {args.fresh} for fresh start...")
            db_path = Path(__file__).parent / 'task_queue.db'
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE project_queue SET fresh_start = 1 WHERE id = ?", (args.fresh,))
            conn.commit()
            conn.close()
            print(f"✅ Project {args.fresh} marked for fresh start")
            return
        
        if args.remove:
            print(f"🗑️  Removing project {args.remove} from queue...")
            import subprocess
            scheduler_path = Path(__file__).parent / 'scheduler.py'
            result = subprocess.run([
                'python3', str(scheduler_path), '--remove-project', str(args.remove)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Project {args.remove} removed successfully")
            else:
                print(f"❌ Failed to remove project {args.remove}")
                if result.stderr:
                    print(f"   Error: {result.stderr}")
            return
        
        if args.cleanup_stale:
            print("🧹 Cleaning up stale registries...")
            import subprocess
            result = subprocess.run([
                'python3', Path(__file__).parent / 'cleanup_stale_registries.py'
            ], capture_output=True, text=True)
            print(result.stdout if result.stdout else "✅ Cleanup complete")
            return
    
    # Connect to database
    db_path = Path(__file__).parent / 'task_queue.db'
    if not db_path.exists():
        print("❌ Database not found. Run scheduler.py first to create it.")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get active tmux sessions
    active_sessions = get_active_tmux_sessions()
    
    # Handle --active flag
    if args.active:
        print("🔄 ACTIVE TMUX SESSIONS:")
        for session in active_sessions:
            print(f"  • {session}")
        return
    
    # Fetch all projects
    cursor.execute("""
        SELECT id, spec_path, status, orchestrator_session, main_session, session_name,
               enqueued_at, started_at, completed_at, error_message, fresh_start, priority,
               merged_status, merged_at
        FROM project_queue 
        ORDER BY 
            CASE 
                WHEN status = 'processing' THEN 1
                WHEN status = 'queued' THEN 2
                WHEN status = 'completed' THEN 3
                ELSE 4
            END,
            CASE
                WHEN completed_at IS NOT NULL THEN completed_at
                WHEN started_at IS NOT NULL THEN started_at
                ELSE enqueued_at
            END DESC
    """)
    projects = cursor.fetchall()
    
    # Reconcile if needed
    if not os.getenv('DISABLE_RECONCILIATION', 'false').lower() == 'true':
        reconcile_orphaned_sessions(cursor, conn, projects, active_sessions)
        reconcile_missing_sessions(cursor, conn, projects, active_sessions)
        # Re-fetch after reconciliation
        cursor.execute("""
            SELECT id, spec_path, status, orchestrator_session, main_session, session_name,
                   enqueued_at, started_at, completed_at, error_message, fresh_start, priority,
                   merged_status, merged_at
            FROM project_queue 
            ORDER BY 
                CASE 
                    WHEN status = 'processing' THEN 1
                    WHEN status = 'queued' THEN 2
                    WHEN status = 'completed' THEN 3
                    ELSE 4
                END,
                CASE
                    WHEN completed_at IS NOT NULL THEN completed_at
                    WHEN started_at IS NOT NULL THEN started_at
                    ELSE enqueued_at
                END DESC
        """)
        projects = cursor.fetchall()
    
    # Check for conflicts
    conflicts = check_conflicts(projects, active_sessions)
    
    # Handle --conflicts flag
    if args.conflicts:
        if conflicts:
            print("⚠️  CONFLICTS DETECTED:")
            for conflict in conflicts:
                print(f"  • {conflict['message']}")
        else:
            print("✅ No conflicts detected")
        return
    
    # Filter projects based on arguments
    filtered_projects = filter_projects(projects, args)
    
    # Display header
    print("=" * 80)
    print("📋 TMUX ORCHESTRATOR QUEUE STATUS")
    print("=" * 80)
    
    # Display conflicts if any
    if conflicts and not args.no_summary:
        print(f"\n⚠️  {len(conflicts)} CONFLICT(S) DETECTED:")
        for conflict in conflicts[:3]:  # Show first 3 conflicts
            print(f"  🚨 {conflict['message']}")
        if len(conflicts) > 3:
            print(f"  ... and {len(conflicts) - 3} more conflicts")
        print()
    
    # Display summary unless disabled
    if not args.no_summary:
        print(f"📊 QUEUE SUMMARY:")
        status_counts = {}
        for proj in projects:
            status = proj[2]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            print(f"  • {status.upper()}: {count}")
        
        print(f"\n🔄 ACTIVE SESSIONS: {len(active_sessions)}")
        
        # Show what's being displayed
        if not args.all and not any([args.processing, args.completed, args.failed, 
                                     args.queued, args.cancelled, args.superseded, 
                                     args.archived, args.status, args.merged]):
            print(f"\n📌 Showing: Processing projects + Last 3 completed (use --all for everything)")
        elif args.number:
            filter_desc = []
            if args.processing: filter_desc.append("processing")
            if args.completed: filter_desc.append("completed")
            if args.failed: filter_desc.append("failed")
            if args.queued: filter_desc.append("queued")
            if args.status: filter_desc.append(args.status)
            
            if filter_desc:
                print(f"\n📌 Showing: Last {args.number} {'/'.join(filter_desc)} projects")
            else:
                print(f"\n📌 Showing: Last {args.number} projects")
    
    # Display projects
    if filtered_projects:
        print(f"\n📋 PROJECTS ({len(filtered_projects)} shown):")
        print("-" * 80)
        
        for proj in filtered_projects:
            if args.compact:
                display_project_compact(proj, active_sessions)
            else:
                display_project_detailed(proj, active_sessions)
    else:
        print("\n📭 No projects match the specified filters")
    
    print("-" * 80)
    
    # Display usage unless disabled
    if not args.no_usage:
        print("💡 QUICK USAGE:")
        print("  qs              # Show processing + recent completed")
        print("  qs --all        # Show everything") 
        print("  qs --failed     # Show failed projects")
        print("  qs -n 10        # Show last 10 projects")
        print("  qs --help       # Full options list")
    
    conn.close()


if __name__ == '__main__':
    main()
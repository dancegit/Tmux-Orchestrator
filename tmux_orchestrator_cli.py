#!/usr/bin/env python3
"""
Command-line interface for the modularized Tmux Orchestrator system.

This CLI provides access to both the new modular functionality and
maintains backward compatibility with the original the modular orchestrator system.
"""

import argparse
import sys
from pathlib import Path

# Add tmux_orchestrator package to path
sys.path.insert(0, str(Path(__file__).parent))

from tmux_orchestrator.main import (
    main as orchestrator_main,
    create_orchestrator,
    restart_claude_with_oauth_management,
    check_oauth_conflicts
)


def find_git_root(start_path):
    """Find the nearest parent directory containing a .git folder"""
    from pathlib import Path
    current = Path(start_path).resolve()
    max_depth = 10  # Prevent infinite traversal
    depth = 0
    while current != current.parent and depth < max_depth:
        if (current / '.git').exists():
            return str(current)
        current = current.parent
        depth += 1
    return None

def cmd_run_orchestrator(args):
    """Add project to queue instead of running directly (QUEUE-ONLY ENFORCEMENT)."""
    print("🚀 Tmux Orchestrator (Queue-Only v2.1)...")
    
    # ENFORCE QUEUE-ONLY BEHAVIOR - NO DIRECT EXECUTION ALLOWED
    print("📋 QUEUE-ONLY MODE: All projects must be processed through the batch queue")
    print("🚫 Direct orchestration execution is disabled to prevent concurrent violations")
    
    # Auto-detect project from spec file if not provided
    if hasattr(args, 'spec') and args.spec and (not hasattr(args, 'project') or not args.project):
        from pathlib import Path
        spec_path = Path(args.spec).resolve()
        if spec_path.exists():
            # Try to find git root from spec location
            git_root = find_git_root(spec_path.parent)
            if git_root:
                args.project = git_root
                print(f"✅ Auto-detected project root: {git_root}")
            else:
                print("⚠️  No git repository found from spec location")
                # Use spec's parent directory as fallback
                args.project = str(spec_path.parent)
                print(f"📁 Using spec directory as project: {args.project}")
    
    # Handle batch mode - automatically detect JSON batch files
    if hasattr(args, 'spec') and args.spec:
        # Check if spec is a JSON file (for batch processing)
        import json
        import os
        if args.spec.endswith('.json') and os.path.exists(args.spec):
            try:
                with open(args.spec, 'r') as f:
                    batch_data = json.load(f)
                    # If it's a batch file, process it differently
                    if isinstance(batch_data, dict) and 'projects' in batch_data:
                        print(f"📦 Detected batch file with {len(batch_data['projects'])} projects")
                        # This would normally trigger batch processing
                        # For now, we'll just note it was detected
                        args.batch = True
            except (json.JSONDecodeError, IOError):
                pass  # Not a valid JSON batch file, treat as regular spec
    
    # Pass command line arguments to the modular main
    import sys
    sys.argv = ['tmux_orchestrator']
    
    # Add all arguments if provided
    if hasattr(args, 'project') and args.project:
        sys.argv.extend(['--project', args.project])
    if hasattr(args, 'spec') and args.spec:
        sys.argv.extend(['--spec', args.spec])
    if hasattr(args, 'resume') and args.resume:
        sys.argv.append('--resume')
    if hasattr(args, 'status_only') and args.status_only:
        sys.argv.append('--status-only')
    if hasattr(args, 'rebrief_all') and args.rebrief_all:
        sys.argv.append('--rebrief-all')
    if hasattr(args, 'roles') and args.roles:
        sys.argv.extend(['--roles', args.roles])
    if hasattr(args, 'add_roles') and args.add_roles:
        sys.argv.extend(['--add-roles', args.add_roles])
    if hasattr(args, 'team_type') and args.team_type:
        sys.argv.extend(['--team-type', args.team_type])
    if hasattr(args, 'plan') and args.plan:
        sys.argv.extend(['--plan', args.plan])
    if hasattr(args, 'size') and args.size:
        sys.argv.extend(['--size', args.size])
    if hasattr(args, 'git_mode') and args.git_mode:
        sys.argv.extend(['--git-mode', args.git_mode])
    if hasattr(args, 'debug') and args.debug:
        sys.argv.append('--debug')
    if hasattr(args, 'dry_run') and args.dry_run:
        sys.argv.append('--dry-run')
    if hasattr(args, 'new_project') and args.new_project:
        sys.argv.append('--new-project')
    
    # Add legacy arguments for scheduler compatibility
    if hasattr(args, 'project_id') and args.project_id:
        # Store project ID in environment for completion callback
        import os
        os.environ['SCHEDULER_PROJECT_ID'] = str(args.project_id)
        print(f"📋 Running project ID: {args.project_id}")
    
    # ALWAYS enable batch mode since we force it
    if hasattr(args, 'batch') and args.batch:
        # Enable non-interactive mode
        import os
        os.environ['BATCH_MODE'] = '1'
        os.environ['CLAUDE_SKIP_ANALYSIS'] = '1'  # Skip Claude analysis in batch mode
        os.environ['AUTO_CONFIRM'] = '1'  # Auto-confirm all prompts
        print("🤖 Running in batch mode (non-interactive)")
        
        # In batch mode, daemon is implied (no need for separate flag)
        os.environ['DAEMON_MODE'] = '1'
        print("📦 Batch mode enabled - running unattended with auto-defaults")
    elif hasattr(args, 'daemon') and args.daemon:
        # Enable daemon mode with auto-defaults (when not in batch)
        os.environ['DAEMON_MODE'] = '1'
        print("👻 Running in daemon mode (unattended)")
        
    # QUEUE-ONLY ENFORCEMENT: Replace direct execution with queue addition
    print("\n🚫 DIRECT EXECUTION DISABLED")
    print("📋 Adding project to queue for daemon processing...")
    
    # Validate required arguments
    if not hasattr(args, 'spec') or not args.spec:
        print("❌ Error: Specification file is required")
        print("   Use --spec /path/to/spec.md")
        return 1
    
    if not hasattr(args, 'project') or not args.project:
        print("❌ Error: Project directory is required")
        print("   Use --project /path/to/project or ensure spec is detectable")
        return 1
    
    try:
        # Import queue addition functionality
        import sqlite3
        import time
        from pathlib import Path
        
        # Validate paths
        spec_path = Path(args.spec).resolve()
        project_path = Path(args.project).resolve()
        
        if not spec_path.exists():
            print(f"❌ Spec file not found: {spec_path}")
            return 1
            
        print(f"📋 Adding to queue:")
        print(f"   Spec: {spec_path}")
        print(f"   Project: {project_path}")
        
        # Add project to queue using the existing queue system
        conn = sqlite3.connect('task_queue.db')
        cursor = conn.cursor()
        
        # Check for duplicate active projects (enforce unique constraint)
        cursor.execute('''
            SELECT COUNT(*) FROM project_queue 
            WHERE spec_path = ? AND status IN ('queued', 'processing')
        ''', (str(spec_path),))
        
        if cursor.fetchone()[0] > 0:
            print(f"⚠️  Project already queued or processing: {spec_path}")
            print("   Use './qs' to check queue status")
            conn.close()
            return 1
        
        # Add to queue
        cursor.execute('''
            INSERT INTO project_queue (spec_path, project_path, status, enqueued_at)
            VALUES (?, ?, 'queued', ?)
        ''', (str(spec_path), str(project_path), time.time()))
        
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Project added to queue with ID: {project_id}")
        print(f"🔄 Queue daemon will process this project automatically")
        print(f"📊 Use './qs' to monitor progress")
        print(f"\n💡 Queue-only mode enforces max_concurrent=1 for system stability")
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to add project to queue: {e}")
        return 1


def cmd_check_oauth(args):
    """Check OAuth port conflicts."""
    print("🔍 Checking OAuth port conflicts...")
    status = check_oauth_conflicts()
    
    print(f"OAuth Port Status:")
    print(f"  Port: {status['port']}")
    print(f"  Available: {'Yes' if status['is_free'] else 'No'}")
    
    if status['conflicts_detected']:
        print(f"  Conflicts: {len(status['conflicts_detected'])}")
        for conflict in status['conflicts_detected']:
            print(f"    - {conflict}")
    
    if status['recommendations']:
        print(f"  Recommendations:")
        for rec in status['recommendations']:
            print(f"    - {rec}")
    
    return status['is_free']


def cmd_restart_claude(args):
    """Restart Claude in a specific tmux window with OAuth management."""
    print(f"🔄 Restarting Claude in {args.session}:{args.window}")
    
    success = restart_claude_with_oauth_management(
        session_name=args.session,
        window_idx=args.window,
        window_name=args.name or f"Claude-{args.window}",
        worktree_path=args.worktree or f"/tmp/worktree-{args.window}"
    )
    
    if success:
        print("✅ Claude restart completed successfully")
    else:
        print("❌ Claude restart failed")
    
    return success


def cmd_test_modular_system(args):
    """Test the modular system components."""
    print("🧪 Testing modular system...")
    
    # Import and run the test
    from test_modular_system import main as test_main
    return test_main()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Modular Tmux Orchestrator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run the full orchestrator (current functionality)
  %(prog)s run
  
  # Check for OAuth port conflicts
  %(prog)s check-oauth
  
  # Restart Claude with OAuth management
  %(prog)s restart-claude mysession 1 --name Developer --worktree /path/to/worktree
  
  # Test the modular system
  %(prog)s test
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run orchestrator command - QUEUE-ONLY MODE (v2.1)  
    run_parser = subparsers.add_parser('run', help='Add project to processing queue (queue-only mode)')
    run_parser.add_argument('--project', '-p', type=str, help='Path to the project directory')
    run_parser.add_argument('--spec', '-s', type=str, help='Path to the specification file')
    run_parser.add_argument('--resume', action='store_true', help='Resume an existing orchestration')
    run_parser.add_argument('--status-only', action='store_true', help='Check status without making changes')
    run_parser.add_argument('--rebrief-all', action='store_true', help='Re-brief all agents when resuming')
    run_parser.add_argument('--roles', type=str, help='Comma-separated list of roles to deploy')
    run_parser.add_argument('--add-roles', type=str, help='Add additional roles to existing orchestration')
    run_parser.add_argument('--team-type', type=str, choices=['web_application', 'system_deployment', 'infrastructure_as_code', 'data_pipeline'], help='Predefined team template')
    run_parser.add_argument('--plan', type=str, choices=['pro', 'max5', 'max20', 'console'], default='max5', help='Subscription plan')
    run_parser.add_argument('--size', type=str, choices=['small', 'medium', 'large'], default='medium', help='Team size')
    run_parser.add_argument('--git-mode', type=str, choices=['local', 'github'], default='local', help='Git workflow mode')
    run_parser.add_argument('--debug', action='store_true', help='Enable debug output')
    run_parser.add_argument('--dry-run', action='store_true', help='Preview actions without executing')
    
    # Legacy the modular orchestrator arguments for backward compatibility with scheduler
    run_parser.add_argument('--project-id', type=int, help='Project ID for scheduler callbacks')
    run_parser.add_argument('--batch', action='store_true', help='Enable batch mode (non-interactive)')
    run_parser.add_argument('--daemon', action='store_true', help='Run in daemon mode (unattended with auto-defaults)')
    run_parser.add_argument('--new-project', action='store_true', help='Create new project directory parallel to Tmux-Orchestrator')
    
    run_parser.set_defaults(func=cmd_run_orchestrator)
    
    # Check OAuth command
    oauth_parser = subparsers.add_parser('check-oauth', help='Check OAuth port conflicts')
    oauth_parser.set_defaults(func=cmd_check_oauth)
    
    # Restart Claude command
    restart_parser = subparsers.add_parser('restart-claude', help='Restart Claude with OAuth management')
    restart_parser.add_argument('session', help='Tmux session name')
    restart_parser.add_argument('window', type=int, help='Window index')
    restart_parser.add_argument('--name', help='Window name (default: Claude-{window})')
    restart_parser.add_argument('--worktree', help='Worktree path (default: /tmp/worktree-{window})')
    restart_parser.set_defaults(func=cmd_restart_claude)
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test the modular system')
    test_parser.set_defaults(func=cmd_test_modular_system)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return False
    
    # Run the selected command
    try:
        return args.func(args)
    except Exception as e:
        print(f"❌ Command failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
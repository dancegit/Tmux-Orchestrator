#!/usr/bin/env python3
"""
Manual cleanup script for completed projects that have lingering tmux sessions.

This script identifies completed projects with active tmux sessions and offers
graceful cleanup options.
"""

import sys
import sqlite3
import subprocess
import logging
from typing import List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_completed_projects_with_sessions() -> List[Tuple[int, str, str]]:
    """
    Find completed projects that still have active tmux sessions.
    
    Returns:
        List of (project_id, session_name, project_path) tuples
    """
    completed_projects = []
    
    try:
        # Get completed projects from database
        with sqlite3.connect('task_queue.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, status, session_name FROM project_queue WHERE status = 'completed'")
            projects = cursor.fetchall()
            
            for project_id, status, session_name in projects:
                if session_name:
                    # Check if tmux session still exists
                    result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:  # Session exists
                        completed_projects.append((project_id, session_name, status))
                        
    except Exception as e:
        logger.error(f"Error checking completed projects: {e}")
        
    return completed_projects

def cleanup_session(session_name: str, dry_run: bool = False) -> bool:
    """
    Gracefully terminate a tmux session.
    
    Args:
        session_name: Name of tmux session to terminate
        dry_run: If True, only show what would be done
        
    Returns:
        True if successful (or dry run), False otherwise
    """
    try:
        if dry_run:
            logger.info(f"[DRY RUN] Would terminate tmux session: {session_name}")
            return True
            
        result = subprocess.run(['tmux', 'kill-session', '-t', session_name], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✓ Successfully terminated tmux session: {session_name}")
            return True
        else:
            logger.error(f"✗ Failed to terminate session {session_name}: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error terminating session {session_name}: {e}")
        return False

def main():
    """Main cleanup function."""
    import argparse
    parser = argparse.ArgumentParser(description='Clean up completed projects with lingering tmux sessions')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be cleaned up without doing it')
    parser.add_argument('--project-id', type=int, help='Clean up specific project ID only')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompts')
    args = parser.parse_args()
    
    logger.info("🔍 Scanning for completed projects with active tmux sessions...")
    
    completed_projects = get_completed_projects_with_sessions()
    
    if not completed_projects:
        logger.info("✓ No completed projects with lingering sessions found")
        return
        
    logger.info(f"Found {len(completed_projects)} completed projects with active sessions:")
    
    for project_id, session_name, status in completed_projects:
        logger.info(f"  Project {project_id}: {session_name} (status: {status})")
    
    # Filter by specific project if requested
    if args.project_id:
        completed_projects = [(pid, sname, status) for pid, sname, status in completed_projects 
                             if pid == args.project_id]
        if not completed_projects:
            logger.error(f"Project {args.project_id} not found in completed projects with sessions")
            return
    
    # Confirm cleanup unless forced
    if not args.force and not args.dry_run:
        response = input(f"\nClean up {len(completed_projects)} sessions? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            logger.info("Cleanup cancelled")
            return
    
    # Perform cleanup
    success_count = 0
    for project_id, session_name, status in completed_projects:
        logger.info(f"🧹 Cleaning up Project {project_id} session: {session_name}")
        if cleanup_session(session_name, dry_run=args.dry_run):
            success_count += 1
    
    if args.dry_run:
        logger.info(f"[DRY RUN] Would clean up {success_count}/{len(completed_projects)} sessions")
    else:
        logger.info(f"✓ Successfully cleaned up {success_count}/{len(completed_projects)} sessions")
        
        if success_count < len(completed_projects):
            logger.warning(f"⚠️  {len(completed_projects) - success_count} sessions failed to clean up")

if __name__ == "__main__":
    main()
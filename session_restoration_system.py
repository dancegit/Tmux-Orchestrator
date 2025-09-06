#!/usr/bin/env python3
"""
Session Restoration System for Tmux Orchestrator

Automatically restores processing projects that lost their tmux sessions
(e.g., after server restart, crashes, etc.)
"""

import logging
import sqlite3
import subprocess
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SessionRestorer:
    """Restores lost tmux sessions for processing projects"""
    
    def __init__(self, tmux_orchestrator_path: Path = None):
        self.tmux_orchestrator_path = tmux_orchestrator_path or Path(__file__).parent
        
    def get_lost_sessions(self) -> List[Dict[str, Any]]:
        """Find processing projects without active tmux sessions"""
        lost_sessions = []
        
        try:
            # Get all active tmux sessions
            result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'], 
                                  capture_output=True, text=True)
            active_sessions = set(result.stdout.strip().split('\n')) if result.returncode == 0 else set()
            
            # Get processing projects from database
            db_path = self.tmux_orchestrator_path / 'task_queue.db'
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, spec_path, project_path, 
                           COALESCE(session_name, orchestrator_session, main_session) as session_name,
                           started_at, auto_orchestrate_args
                    FROM project_queue 
                    WHERE status = 'processing'
                    AND started_at IS NOT NULL
                """)
                
                for row in cursor.fetchall():
                    project = dict(row)
                    session_name = project['session_name']
                    
                    # Check if project has a session but it's not active
                    if session_name and session_name not in active_sessions:
                        # Verify session really doesn't exist (not just tmux output issue)
                        session_check = subprocess.run(
                            ['tmux', 'has-session', '-t', session_name],
                            capture_output=True, text=True
                        )
                        
                        if session_check.returncode != 0:  # Session doesn't exist
                            logger.info(f"Found lost session: Project {project['id']} - session '{session_name}' missing")
                            lost_sessions.append(project)
                    
                    # Also check for projects with NULL session names (orphaned)
                    elif not session_name:
                        # Check if this project was supposed to have a session (has started_at)
                        if project['started_at']:
                            logger.info(f"Found orphaned project: {project['id']} - no session name recorded")
                            lost_sessions.append(project)
                        
        except Exception as e:
            logger.error(f"Error finding lost sessions: {e}")
            
        return lost_sessions
    
    def restore_session(self, project: Dict[str, Any]) -> bool:
        """Restore a lost session for a project"""
        project_id = project['id']
        spec_path = project['spec_path']
        project_path = project['project_path']
        auto_orchestrate_args = project.get('auto_orchestrate_args', '')
        
        logger.info(f"Restoring session for project {project_id}")
        
        try:
            # Determine restoration method based on project type
            if spec_path and Path(spec_path).exists():
                # Use tmux_orchestrator_cli.py --resume if possible
                success = self._restore_via_cli_resume(project)
                if success:
                    return True
                    
            # Fallback: Try to reconstruct session from available data
            success = self._restore_via_reconstruction(project)
            return success
            
        except Exception as e:
            logger.error(f"Error restoring session for project {project_id}: {e}")
            return False
    
    def _restore_via_cli_resume(self, project: Dict[str, Any]) -> bool:
        """Try to restore using the CLI --resume functionality"""
        project_id = project['id']
        project_path = project['project_path']
        spec_path = project['spec_path']
        
        if not project_path or not Path(project_path).exists():
            logger.warning(f"Project {project_id}: No valid project path for CLI resume")
            return False
            
        try:
            # Build CLI command
            cli_cmd = [
                'python3', 
                str(self.tmux_orchestrator_path / 'tmux_orchestrator_cli.py'),
                'run',
                '--project', project_path,
                '--resume',
                '--rebrief-all'  # Force re-briefing since session was lost
            ]
            
            if spec_path and Path(spec_path).exists():
                cli_cmd.extend(['--spec', spec_path])
                
            # Add project ID for database correlation
            cli_cmd.extend(['--project-id', str(project_id)])
            
            logger.info(f"Executing: {' '.join(cli_cmd)}")
            
            # Execute restoration
            result = subprocess.run(
                cli_cmd,
                capture_output=True,
                text=True,
                cwd=str(self.tmux_orchestrator_path),
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Successfully restored session for project {project_id} via CLI")
                
                # Update database with new session info if available
                self._update_restored_session_info(project_id, result.stdout)
                return True
            else:
                logger.warning(f"CLI resume failed for project {project_id}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"CLI resume timed out for project {project_id}")
            return False
        except Exception as e:
            logger.error(f"CLI resume error for project {project_id}: {e}")
            return False
    
    def _restore_via_reconstruction(self, project: Dict[str, Any]) -> bool:
        """Fallback: Try to reconstruct the session manually"""
        project_id = project['id']
        project_path = project['project_path']
        
        logger.info(f"Attempting manual reconstruction for project {project_id}")
        
        try:
            # Generate a new session name
            session_name = f"restored-{project_id}-{int(datetime.now().timestamp())}"
            
            # Create basic tmux session
            subprocess.run([
                'tmux', 'new-session', '-d', '-s', session_name,
                '-c', project_path or '/tmp'
            ], check=True)
            
            # Create orchestrator window
            subprocess.run([
                'tmux', 'rename-window', '-t', f'{session_name}:0', 'Orchestrator'
            ])
            
            # Start Claude in orchestrator window
            subprocess.run([
                'tmux', 'send-keys', '-t', f'{session_name}:0', 'claude', 'Enter'
            ])
            
            # Wait a moment for Claude to start
            subprocess.run(['sleep', '5'])
            
            # Send basic briefing
            briefing = f"""You are the Orchestrator for project {project_id} (RESTORED SESSION).

This session was automatically restored after being lost (server restart, crash, etc.).

Key Information:
- Project ID: {project_id}
- Project Path: {project_path}
- Status: PROCESSING (was in progress before session loss)

Your Tasks:
1. Analyze the current project state
2. Determine what work was already completed
3. Continue or restart implementation as needed
4. Coordinate with other agents (if restored)

IMPORTANT: This is a restored session - check for existing work before starting new implementation."""

            subprocess.run([
                'tmux', 'send-keys', '-t', f'{session_name}:0', briefing, 'Enter'
            ])
            
            # Update database with new session name
            db_path = self.tmux_orchestrator_path / 'task_queue.db'
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("""
                    UPDATE project_queue 
                    SET session_name = ?, orchestrator_session = ?, 
                        error_message = 'Session restored automatically'
                    WHERE id = ?
                """, (session_name, session_name, project_id))
                conn.commit()
                
            logger.info(f"✅ Successfully reconstructed session '{session_name}' for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reconstruct session for project {project_id}: {e}")
            return False
    
    def _update_restored_session_info(self, project_id: int, cli_output: str):
        """Update database with session info from CLI output"""
        try:
            # Extract session name from CLI output if possible
            lines = cli_output.split('\n')
            session_name = None
            
            for line in lines:
                if 'session:' in line.lower() or 'created session' in line.lower():
                    # Extract session name (implementation depends on CLI output format)
                    # This is a simple extraction - may need refinement
                    words = line.split()
                    for i, word in enumerate(words):
                        if 'session' in word.lower() and i + 1 < len(words):
                            potential_name = words[i + 1].strip(':')
                            if potential_name and not potential_name.startswith('-'):
                                session_name = potential_name
                                break
                                
            if session_name:
                db_path = self.tmux_orchestrator_path / 'task_queue.db'
                with sqlite3.connect(str(db_path)) as conn:
                    conn.execute("""
                        UPDATE project_queue 
                        SET session_name = ?, orchestrator_session = ?, 
                            error_message = 'Session restored via CLI'
                        WHERE id = ?
                    """, (session_name, session_name, project_id))
                    conn.commit()
                    
                logger.info(f"Updated project {project_id} with restored session: {session_name}")
                
        except Exception as e:
            logger.debug(f"Could not extract session info for project {project_id}: {e}")
    
    def restore_all_lost_sessions(self) -> int:
        """Restore all lost sessions and return count of successful restorations"""
        lost_sessions = self.get_lost_sessions()
        
        if not lost_sessions:
            logger.info("No lost sessions found - all processing projects have active sessions")
            return 0
            
        logger.info(f"Found {len(lost_sessions)} lost sessions to restore")
        
        restored_count = 0
        for project in lost_sessions:
            if self.restore_session(project):
                restored_count += 1
            else:
                # Mark as failed if restoration fails multiple times
                self._mark_restoration_failed(project)
                
        logger.info(f"✅ Restored {restored_count}/{len(lost_sessions)} sessions")
        return restored_count
    
    def _mark_restoration_failed(self, project: Dict[str, Any]):
        """Mark a project as failed if session restoration repeatedly fails"""
        project_id = project['id']
        
        try:
            db_path = self.tmux_orchestrator_path / 'task_queue.db'
            with sqlite3.connect(str(db_path)) as conn:
                # Check if this is a repeated failure
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT error_message FROM project_queue WHERE id = ?", 
                    (project_id,)
                )
                row = cursor.fetchone()
                
                current_error = row[0] if row else ""
                restoration_attempts = current_error.count("restoration failed")
                
                if restoration_attempts >= 2:  # Third failure
                    # Mark as failed
                    conn.execute("""
                        UPDATE project_queue 
                        SET status = 'failed', 
                            completed_at = ?,
                            error_message = 'Session restoration failed repeatedly - marked as failed'
                        WHERE id = ?
                    """, (datetime.now().isoformat(), project_id))
                    
                    logger.warning(f"⚠️  Project {project_id} marked as failed after repeated restoration failures")
                else:
                    # Update error message
                    new_error = f"{current_error}; Session restoration failed (attempt {restoration_attempts + 1})"
                    conn.execute(
                        "UPDATE project_queue SET error_message = ? WHERE id = ?",
                        (new_error, project_id)
                    )
                    
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error updating restoration failure for project {project_id}: {e}")


def main():
    """CLI interface for session restoration"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Restore lost tmux sessions for processing projects")
    parser.add_argument('--check-only', action='store_true', 
                       help='Only check for lost sessions, do not restore')
    parser.add_argument('--project-id', type=int, 
                       help='Restore specific project by ID')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be restored without doing it')
    
    args = parser.parse_args()
    
    restorer = SessionRestorer()
    
    if args.project_id:
        # Restore specific project
        # Implementation for single project restoration
        logger.info(f"Restoring specific project {args.project_id}")
        # ... implementation
        
    elif args.check_only:
        # Just check and report
        lost_sessions = restorer.get_lost_sessions()
        if lost_sessions:
            print(f"Found {len(lost_sessions)} lost sessions:")
            for project in lost_sessions:
                session_name = project.get('session_name', 'NULL')
                print(f"  - Project {project['id']}: session '{session_name}'")
        else:
            print("No lost sessions found")
            
    elif args.dry_run:
        # Show what would be restored
        lost_sessions = restorer.get_lost_sessions()
        print(f"Would restore {len(lost_sessions)} sessions:")
        for project in lost_sessions:
            print(f"  - Project {project['id']}: {project.get('spec_path', 'No spec')}")
            
    else:
        # Restore all lost sessions
        restored_count = restorer.restore_all_lost_sessions()
        sys.exit(0 if restored_count > 0 else 1)


if __name__ == "__main__":
    main()
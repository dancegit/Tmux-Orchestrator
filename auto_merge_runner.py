#!/usr/bin/env python3
"""
Auto Merge Runner - Automatically merges COMPLETED projects
Called by systemd timer every 5 minutes to merge pending projects.
"""

import sys
import sqlite3
import subprocess
import logging
from pathlib import Path
from datetime import datetime
import time
import os

# Setup logging
LOG_DIR = Path(__file__).parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'auto_merge.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class AutoMergeRunner:
    def __init__(self):
        self.db_path = Path(__file__).parent / 'task_queue.db'
        self.merge_script = Path(__file__).parent / 'merge_integration.py'
        self.max_merges_per_run = 5  # Limit to prevent overload
        self.lock_file = Path(__file__).parent / '.auto_merge.lock'
        
    def acquire_lock(self):
        """Acquire lock to prevent concurrent runs"""
        if self.lock_file.exists():
            # Check if lock is stale (older than 10 minutes)
            lock_age = time.time() - self.lock_file.stat().st_mtime
            if lock_age > 600:
                logger.warning(f"Removing stale lock file (age: {lock_age:.0f}s)")
                self.lock_file.unlink()
            else:
                logger.info("Another merge process is running, exiting")
                return False
        
        self.lock_file.write_text(str(os.getpid()))
        return True
    
    def release_lock(self):
        """Release the lock file"""
        if self.lock_file.exists():
            self.lock_file.unlink()
    
    def get_pending_merges(self):
        """Get list of projects pending merge"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, spec_path, project_path, orchestrator_session, main_session
            FROM project_queue 
            WHERE status = 'completed' 
                AND (merged_status = 'pending_merge' OR merged_status IS NULL)
            ORDER BY completed_at ASC
            LIMIT ?
        """, (self.max_merges_per_run,))
        
        projects = cursor.fetchall()
        conn.close()
        return projects
    
    def extract_commit_hash_from_session(self, session_name):
        """Extract commit hash from session name if available"""
        # NOTE: Session names have random IDs at the end, not git commit hashes
        # We should NOT try to extract commit hash from session names
        # Instead, we'll use project names for merging
        return None
    
    def merge_project(self, project_id, spec_path, project_path, orchestrator_session, main_session):
        """Attempt to merge a single project"""
        project_name = Path(spec_path).stem if spec_path else "unknown"
        logger.info(f"Attempting to merge project {project_id}: {project_name}")
        
        # Always use project name for merging
        # The merge_integration.py script will find the correct worktree and commit
        cmd = ['python3', str(self.merge_script)]
        cmd.extend(['--project', project_name, '--force'])
        logger.info(f"Using project name: {project_name}")
        
        try:
            # Run merge command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            success = result.returncode == 0
            
            # Update database
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            if success:
                cursor.execute("""
                    UPDATE project_queue 
                    SET merged_status = 'merged', 
                        merged_at = ?
                    WHERE id = ?
                """, (datetime.now().timestamp(), project_id))
                logger.info(f"✅ Successfully merged project {project_id}: {project_name}")
                
                # Push the merge and tags to remote
                self.push_merge_to_remote(project_path)
            else:
                error_msg = result.stderr[:500] if result.stderr else "Unknown error"
                cursor.execute("""
                    UPDATE project_queue 
                    SET merged_status = 'merge_failed',
                        error_message = ?
                    WHERE id = ?
                """, (f"Merge failed: {error_msg}", project_id))
                logger.error(f"❌ Failed to merge project {project_id}: {error_msg}")
            
            conn.commit()
            conn.close()
            return success
            
        except subprocess.TimeoutExpired:
            logger.error(f"Merge timeout for project {project_id}")
            self.update_status(project_id, 'merge_failed', 'Merge timeout')
            return False
        except Exception as e:
            logger.error(f"Exception merging project {project_id}: {e}")
            self.update_status(project_id, 'merge_failed', str(e))
            return False
    
    def push_merge_to_remote(self, project_path):
        """Push the merge commits and tags to remote repository"""
        try:
            # Determine the actual project directory from project_path
            # The merge_integration.py merges to the main project, not worktree
            if project_path and Path(project_path).exists():
                target_dir = Path(project_path)
            else:
                # Try to extract from spec path
                logger.warning(f"Project path {project_path} not found, skipping push")
                return
            
            # Push current branch
            push_cmd = ['git', 'push', 'origin', 'HEAD']
            result = subprocess.run(push_cmd, cwd=str(target_dir), 
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                logger.info(f"Pushed merge commits to remote for {target_dir.name}")
            else:
                logger.warning(f"Failed to push commits: {result.stderr[:200]}")
            
            # Push tags (integration-* tags created by merge_integration.py)
            push_tags_cmd = ['git', 'push', 'origin', '--tags']
            result = subprocess.run(push_tags_cmd, cwd=str(target_dir), 
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                logger.info(f"Pushed integration tags to remote for {target_dir.name}")
            else:
                logger.warning(f"Failed to push tags: {result.stderr[:200]}")
                
        except subprocess.TimeoutExpired:
            logger.warning("Git push timeout - continuing anyway")
        except Exception as e:
            logger.warning(f"Error pushing to remote: {e}")
    
    def update_status(self, project_id, status, error_msg=None):
        """Update project merge status in database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        if error_msg:
            cursor.execute("""
                UPDATE project_queue 
                SET merged_status = ?, error_message = ?
                WHERE id = ?
            """, (status, error_msg, project_id))
        else:
            cursor.execute("""
                UPDATE project_queue 
                SET merged_status = ?
                WHERE id = ?
            """, (status, project_id))
        
        conn.commit()
        conn.close()
    
    def run(self):
        """Main execution method"""
        logger.info("=== Auto Merge Runner Started ===")
        
        # Acquire lock
        if not self.acquire_lock():
            return 1
        
        try:
            # Get pending projects
            projects = self.get_pending_merges()
            
            if not projects:
                logger.info("No projects pending merge")
                return 0
            
            logger.info(f"Found {len(projects)} projects to merge")
            
            # Process each project
            success_count = 0
            fail_count = 0
            
            for project in projects:
                project_id, spec_path, project_path, orchestrator_session, main_session = project
                
                if self.merge_project(project_id, spec_path, project_path, 
                                    orchestrator_session, main_session):
                    success_count += 1
                else:
                    fail_count += 1
                
                # Small delay between merges to prevent overload
                time.sleep(2)
            
            # Summary
            logger.info(f"=== Merge Summary: {success_count} succeeded, {fail_count} failed ===")
            
            # Send notification if failures
            if fail_count > 0:
                self.send_failure_notification(fail_count)
            
            return 0
            
        except Exception as e:
            logger.error(f"Fatal error in auto merge runner: {e}")
            return 1
        finally:
            self.release_lock()
    
    def send_failure_notification(self, fail_count):
        """Send notification about merge failures"""
        # This could integrate with email/Slack notifications
        # For now, just log prominently
        logger.warning(f"⚠️  {fail_count} projects failed to merge - manual intervention may be needed")
        
        # Create a notification file for monitoring
        notification_file = LOG_DIR / 'merge_failures.txt'
        notification_file.write_text(
            f"{datetime.now().isoformat()}: {fail_count} merge failures\n"
        )

def main():
    """Main entry point"""
    runner = AutoMergeRunner()
    return runner.run()

if __name__ == '__main__':
    sys.exit(main())
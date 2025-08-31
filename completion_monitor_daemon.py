#!/usr/bin/env python3
"""
Completion Monitor Daemon for Tmux Orchestrator

Continuously monitors all PROCESSING projects for completion.
Automatically updates project status and triggers notifications.
"""

import time
import logging
import sqlite3
import json
import signal
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import argparse

from completion_manager import CompletionManager
from session_state import SessionStateManager
from scheduler import TmuxOrchestratorScheduler
from completion_detector import CompletionDetector, create_completion_marker
from agent_health_monitor import AgentHealthMonitor, AgentHealthDatabase
from scheduler_lock_manager import SchedulerLockManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('completion_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CompletionMonitorDaemon:
    """Daemon that monitors all PROCESSING projects for completion"""
    
    def __init__(self, poll_interval: int = 300, tmux_orchestrator_path: Path = None):
        """
        Initialize the completion monitor daemon.
        
        Args:
            poll_interval: How often to check for completions (seconds)
            tmux_orchestrator_path: Path to Tmux-Orchestrator directory
        """
        self.poll_interval = poll_interval
        self.running = True
        self.tmux_orchestrator_path = tmux_orchestrator_path or Path(__file__).parent
        
        # Initialize managers
        self.session_state_manager = SessionStateManager(self.tmux_orchestrator_path)
        self.completion_manager = CompletionManager(self.session_state_manager)
        self.scheduler = TmuxOrchestratorScheduler()  # For database operations
        self.completion_detector = CompletionDetector(self.tmux_orchestrator_path)
        
        # Initialize health monitoring
        self.health_monitor = AgentHealthMonitor()
        self.health_database = AgentHealthDatabase(str(self.tmux_orchestrator_path / 'task_queue.db'))
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"Completion Monitor Daemon initialized with {poll_interval}s poll interval")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def get_processing_projects(self) -> List[Dict[str, Any]]:
        """Get all projects that are currently PROCESSING, RECOVERED, or FAILED (for completion verification)"""
        db_path = self.tmux_orchestrator_path / 'task_queue.db'
        
        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, 
                           COALESCE(session_name, orchestrator_session, main_session) as project_name,
                           COALESCE(session_name, orchestrator_session, main_session) as session_name, 
                           spec_path as spec_file, status, started_at
                    FROM project_queue 
                    WHERE status IN ('processing', 'recovered', 'failed')
                    ORDER BY started_at ASC
                """)
                
                projects = []
                for row in cursor.fetchall():
                    project = {
                        'id': row['id'],
                        'project_name': row['project_name'],
                        'session_name': row['session_name'],
                        'spec_file': row['spec_file'],
                        'status': row['status'],
                        'started_at': row['started_at']
                    }
                    
                    # Auto-transition RECOVERED to PROCESSING if agents are active
                    if row['status'] == 'recovered' and self.is_agent_active(row['id'], row['session_name']):
                        logger.info(f"Auto-transitioning project {row['id']} from RECOVERED to PROCESSING (agents detected)")
                        self.update_project_status(row['id'], 'processing')
                        project['status'] = 'processing'
                    
                    # Auto-transition FAILED to PROCESSING if agents are still active (wrongly failed projects)
                    elif row['status'] == 'failed' and self.is_agent_active(row['id'], row['session_name']):
                        logger.info(f"Auto-transitioning project {row['id']} from FAILED to PROCESSING (active agents detected, possible wrongly failed project)")
                        self.update_project_status(row['id'], 'processing')
                        project['status'] = 'processing'
                    
                    projects.append(project)
                
                return projects
                
        except Exception as e:
            logger.error(f"Failed to get processing projects: {e}")
            return []
    
    def get_recent_failed_projects(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get recently failed projects that might actually be completed"""
        db_path = self.tmux_orchestrator_path / 'task_queue.db'
        
        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, 
                           COALESCE(session_name, orchestrator_session, main_session) as project_name,
                           COALESCE(session_name, orchestrator_session, main_session) as session_name, 
                           spec_path as spec_file, status, started_at, completed_at, error_message
                    FROM project_queue 
                    WHERE status = 'failed' 
                    AND completed_at > datetime('now', '-24 hours')  -- Only recent failures
                    ORDER BY completed_at DESC
                    LIMIT ?
                """, (limit,))
                
                projects = []
                for row in cursor.fetchall():
                    projects.append({
                        'id': row['id'],
                        'project_name': row['project_name'],
                        'session_name': row['session_name'],
                        'spec_file': row['spec_file'],
                        'status': row['status'],
                        'started_at': row['started_at'],
                        'completed_at': row['completed_at'],
                        'error_message': row['error_message']
                    })
                
                return projects
                
        except Exception as e:
            logger.error(f"Failed to get recent failed projects: {e}")
            return []
    
    def check_session_exists(self, session_name: str) -> bool:
        """Check if a tmux session exists and is active"""
        import subprocess
        try:
            result = subprocess.run(
                ['tmux', 'has-session', '-t', session_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Failed to check session {session_name}: {e}")
            return False
    
    def is_agent_active(self, project_id: int, session_name: str) -> bool:
        """Check if agents are active for a project (for auto-transitioning RECOVERED/FAILED projects)"""
        try:
            # Method 1: Check if tmux session exists and has recent activity
            if self.check_session_exists(session_name):
                # Check for recent session activity via tmux
                result = subprocess.run(
                    ['tmux', 'display-message', '-p', '-t', session_name, '#{session_activity}'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    last_active = int(result.stdout.strip())
                    idle_time = time.time() - last_active
                    if idle_time < 600:  # Active in last 10 minutes
                        logger.debug(f"Project {project_id}: Session active (idle {idle_time:.0f}s)")
                        return True
            
            # Method 2: Check for COMPLETED marker file (agents trying to complete)
            # Look for project worktrees pattern (project-tmux-worktrees)
            import glob
            possible_paths = [
                f"/home/clauderun/*{session_name.replace('-impl-', '*')}*/COMPLETED",
                f"/home/clauderun/*/*{session_name}*/orchestrator/COMPLETED",
                f"/tmp/{session_name}*/COMPLETED"
            ]
            for pattern in possible_paths:
                if glob.glob(pattern):
                    logger.debug(f"Project {project_id}: Found COMPLETED marker")
                    return True
            
            logger.debug(f"Project {project_id}: No agent activity detected")
            return False
            
        except Exception as e:
            logger.warning(f"Failed to check agent activity for project {project_id}: {e}")
            return False
    
    def check_project_completion(self, project: Dict[str, Any]) -> str:
        """
        Check if a project is completed, failed, or still processing.
        Uses multiple detection methods for reliability.
        
        Returns: 'completed', 'failed', 'processing'
        """
        session_name = project['session_name']
        project_id = project['id']
        
        logger.debug(f"Checking completion for project {project_id}: {session_name}")
        
        # First check if session still exists
        session_exists = self.check_session_exists(session_name)
        if not session_exists:
            logger.warning(f"Session {session_name} not found for project {project_id} - checking for completion signals before marking failed")
            
            # Get project path for enhanced detection even without session
            project_path = None
            try:
                conn = sqlite3.connect(str(self.tmux_orchestrator_path / 'task_queue.db'))
                cursor = conn.cursor()
                cursor.execute("SELECT project_path FROM project_queue WHERE id = ?", (project_id,))
                row = cursor.fetchone()
                if row:
                    project_path = row[0]
                conn.close()
            except Exception as e:
                logger.debug(f"Could not get project path for offline analysis: {e}")
            
            # Enhanced project info for detector
            offline_enhanced_project = {
                **project,
                'project_path': project_path
            }
            
            # Hybrid check: Verify if other signals indicate completion despite missing session
            status, reason = self.completion_detector.detect_completion(offline_enhanced_project)
            if status == 'completed':
                logger.info(f"Session missing but completion detected: {reason} - marking as completed")
                # Create marker to prevent re-processing
                create_completion_marker(session_name, project_id, reason)
                return 'completed'
            else:
                logger.info(f"Session {session_name} no longer exists and no completion signals found - marking as failed")
                return 'failed'
        
        try:
            # Get project path from database for enhanced detection
            db_path = self.tmux_orchestrator_path / 'task_queue.db'
            project_path = None
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT project_path FROM project_queue WHERE id = ?", (project_id,))
                row = cursor.fetchone()
                if row:
                    project_path = row[0]
            
            # Enhanced project info for detector
            enhanced_project = {
                **project,
                'project_path': project_path
            }
            
            # Use enhanced completion detector
            status, reason = self.completion_detector.detect_completion(enhanced_project)
            
            if status == 'completed':
                logger.info(f"Project {project_id} detected as complete: {reason}")
                # Create completion marker for future reference
                create_completion_marker(session_name, project_id, reason)
                return 'completed'
            elif status == 'failed':
                logger.info(f"Project {project_id} detected as failed: {reason}")
                return 'failed'
            else:
                logger.debug(f"Project {project_id} still processing: {reason}")
                
                # Fallback to old method if needed (but with improved logic)
                try:
                    result = subprocess.run([
                        'python3', 
                        str(self.tmux_orchestrator_path / 'check_project_completion.py'),
                        str(project_id)
                    ], capture_output=True, text=True, timeout=120, cwd=str(self.tmux_orchestrator_path))
                    
                    if result.returncode == 0 and "Project appears complete!" in result.stdout:
                        logger.info(f"Project {project_id} detected as complete by fallback method")
                        create_completion_marker(session_name, project_id, "Detected by check_project_completion.py")
                        return 'completed'
                except:
                    pass
                
                return 'processing'
                
        except Exception as e:
            logger.error(f"Error checking completion for project {project_id}: {e}")
            return 'processing'  # Continue monitoring on errors
    
    def update_project_status(self, project_id: int, new_status: str, completion_time: str = None):
        """Update project status in the database"""
        db_path = self.tmux_orchestrator_path / 'task_queue.db'
        
        try:
            with sqlite3.connect(str(db_path)) as conn:
                if completion_time:
                    conn.execute("""
                        UPDATE project_queue 
                        SET status = ?, completed_at = ?
                        WHERE id = ?
                    """, (new_status, completion_time, project_id))
                else:
                    conn.execute("""
                        UPDATE project_queue 
                        SET status = ?
                        WHERE id = ?
                    """, (new_status, project_id))
                
                conn.commit()
                logger.info(f"Updated project {project_id} status to {new_status}")
                
        except Exception as e:
            logger.error(f"Failed to update project {project_id} status: {e}")
    
    def process_completed_project(self, project: Dict[str, Any]):
        """Handle a project that has been detected as completed"""
        project_id = project['id']
        session_name = project['session_name']
        completion_time = datetime.now().isoformat()
        
        logger.info(f"Processing completion for project {project_id}: {project['project_name']}")
        
        # Update database status
        self.update_project_status(project_id, 'completed', completion_time)
        
        # Send notification (if configured)
        try:
            if hasattr(self.completion_manager, 'notifier') and self.completion_manager.notifier:
                # Use the completion manager's built-in notification method
                if hasattr(self.completion_manager.notifier, 'send_notification'):
                    success = self.completion_manager.notifier.send_notification(
                        f"Project Completed: {project['project_name']}",
                        f"Session {session_name} completed successfully at {completion_time}"
                    )
                    if success:
                        logger.info(f"Completion notification sent for project {project_id}")
                    else:
                        logger.warning(f"Failed to send completion notification for project {project_id}")
                else:
                    logger.info(f"Notification system not fully configured for project {project_id}")
        except Exception as e:
            logger.error(f"Error sending notification for project {project_id}: {e}")
        
        logger.info(f"✅ Project {project_id} marked as completed")
    
    def process_failed_project(self, project: Dict[str, Any]):
        """Handle a project that has failed"""
        project_id = project['id']
        session_name = project['session_name']
        completion_time = datetime.now().isoformat()
        
        logger.info(f"Processing failure for project {project_id}: {project['project_name']}")
        
        # Update database status
        self.update_project_status(project_id, 'failed', completion_time)
        
        # Send failure notification (if configured)
        try:
            if hasattr(self.completion_manager, 'notifier') and self.completion_manager.notifier:
                success = self.completion_manager.notifier.send_completion_notification(
                    project['project_name'],
                    session_name,
                    'failed'
                )
                if success:
                    logger.info(f"Failure notification sent for project {project_id}")
        except Exception as e:
            logger.error(f"Error sending failure notification for project {project_id}: {e}")
        
        logger.warning(f"❌ Project {project_id} marked as failed")
    
    def recover_wrongly_failed_project(self, project: Dict[str, Any]):
        """Recover a project that was wrongly marked as failed but is actually complete"""
        project_id = project['id']
        session_name = project['session_name']
        
        logger.info(f"🔄 Recovering wrongly failed project {project_id}: {project['project_name']}")
        
        # Update database status to completed (preserve original completion timestamp if recent)
        from datetime import datetime, timedelta
        completion_time = datetime.now().isoformat()
        
        # If failed recently (< 30 minutes ago), assume it was wrongly failed and use current time
        try:
            if project.get('completed_at'):
                failed_time = datetime.fromisoformat(project['completed_at'])
                if datetime.now() - failed_time < timedelta(minutes=30):
                    completion_time = project['completed_at']  # Keep original failure time as completion time
        except:
            pass  # Use current time if parsing fails
            
        self.update_project_status(project_id, 'completed', completion_time)
        
        # Update error message to indicate recovery
        try:
            db_path = self.tmux_orchestrator_path / 'task_queue.db'
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("""
                    UPDATE project_queue 
                    SET error_message = ?
                    WHERE id = ?
                """, (f"Recovered: Project incorrectly marked failed but found to be complete via completion detection", project_id))
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not update recovery message for project {project_id}: {e}")
        
        # Send recovery notification (if configured)
        try:
            if hasattr(self.completion_manager, 'notifier') and self.completion_manager.notifier:
                success = self.completion_manager.notifier.send_completion_notification(
                    project['project_name'],
                    session_name,
                    'completed_recovery'
                )
                if success:
                    logger.info(f"Recovery notification sent for project {project_id}")
        except Exception as e:
            logger.error(f"Error sending recovery notification for project {project_id}: {e}")
        
        logger.info(f"✅ Project {project_id} recovered from failed to completed")
    
    def failed_project_recovery_cycle(self):
        """Check recent failed projects to see if any are actually completed"""
        try:
            logger.debug("Starting failed project recovery cycle...")
            
            failed_projects = self.get_recent_failed_projects(3)
            if not failed_projects:
                logger.debug("No recent failed projects to check")
                return
            
            logger.info(f"Checking {len(failed_projects)} recent failed projects for potential recovery")
            
            recovered_count = 0
            
            for project in failed_projects:
                try:
                    project_id = project['id']
                    
                    # Skip if no session name (can't check completion)
                    if not project['session_name']:
                        logger.debug(f"Project {project_id}: No session name, skipping recovery check")
                        continue
                    
                    # Enhanced project info for detector
                    db_path = self.tmux_orchestrator_path / 'task_queue.db'
                    project_path = None
                    with sqlite3.connect(str(db_path)) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT project_path FROM project_queue WHERE id = ?", (project_id,))
                        row = cursor.fetchone()
                        if row:
                            project_path = row[0]
                    
                    enhanced_project = {
                        **project,
                        'project_path': project_path
                    }
                    
                    # Use completion detector to check if actually completed
                    status, reason = self.completion_detector.detect_completion(enhanced_project)
                    
                    if status == 'completed':
                        logger.info(f"🔄 Project {project_id} was wrongly failed - actually completed: {reason}")
                        self.recover_wrongly_failed_project(project)
                        recovered_count += 1
                    else:
                        logger.debug(f"Project {project_id} confirmed failed: {reason}")
                        
                except Exception as e:
                    logger.error(f"Error checking failed project {project.get('id', 'unknown')}: {e}")
            
            if recovered_count > 0:
                logger.info(f"✅ Recovered {recovered_count} wrongly failed project(s)")
            else:
                logger.debug("No wrongly failed projects found - all failures appear legitimate")
                
        except Exception as e:
            logger.error(f"Error during failed project recovery cycle: {e}")
    
    def monitoring_cycle(self):
        """Run one monitoring cycle - check all processing projects"""
        logger.debug("Starting monitoring cycle...")
        
        processing_projects = self.get_processing_projects()
        if not processing_projects:
            logger.debug("No processing projects to monitor")
            return
        
        logger.info(f"Monitoring {len(processing_projects)} processing projects")
        
        for project in processing_projects:
            try:
                status = self.check_project_completion(project)
                
                if status == 'completed':
                    self.process_completed_project(project)
                elif status == 'failed':
                    self.process_failed_project(project)
                # If 'processing', continue monitoring in next cycle
                
            except Exception as e:
                logger.error(f"Error processing project {project['id']}: {e}")
        
        # Perform agent health monitoring
        self.health_monitoring_cycle()
        
        # Verify cleanup for recent completed projects
        self.cleanup_verification_cycle()
        
        # Check for wrongly failed projects that might actually be completed
        self.failed_project_recovery_cycle()
        
        logger.debug("Monitoring cycle completed")
    
    def get_recent_completed_projects(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get the most recently completed projects for cleanup verification"""
        db_path = self.tmux_orchestrator_path / 'task_queue.db'
        
        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, project_path, orchestrator_session, main_session, session_name, 
                           status, completed_at
                    FROM project_queue 
                    WHERE status = 'completed' 
                    ORDER BY completed_at DESC 
                    LIMIT ?
                """, (limit,))
                
                projects = []
                for row in cursor.fetchall():
                    projects.append({
                        'id': row['id'],
                        'project_path': row['project_path'],
                        'orchestrator_session': row['orchestrator_session'],
                        'main_session': row['main_session'], 
                        'session_name': row['session_name'],
                        'status': row['status'],
                        'completed_at': row['completed_at']
                    })
                
                return projects
                
        except Exception as e:
            logger.error(f"Failed to get recent completed projects: {e}")
            return []

    def verify_project_cleanup(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify that a completed project has been properly cleaned up.
        Checks for lingering sessions and registry directories.
        
        Returns: Dictionary with cleanup status and issues found
        """
        project_id = project['id']
        issues = []
        
        # Check all possible session names
        session_names = []
        if project['orchestrator_session']:
            session_names.append(project['orchestrator_session'])
        if project['main_session'] and project['main_session'] not in session_names:
            session_names.append(project['main_session'])
        if project['session_name'] and project['session_name'] not in session_names:
            session_names.append(project['session_name'])
        
        # Check for lingering tmux sessions
        lingering_sessions = []
        for session_name in session_names:
            if session_name and self.check_session_exists(session_name):
                lingering_sessions.append(session_name)
                issues.append(f"Session {session_name} still exists")
        
        # Check for registry directory
        registry_path = None
        lingering_registry = False
        if project['project_path']:
            # Registry is typically in project-tmux-worktrees/registry/
            project_path = Path(project['project_path'])
            possible_registry = project_path.parent / f"{project_path.name}-tmux-worktrees" / "registry"
            if possible_registry.exists():
                registry_path = str(possible_registry)
                lingering_registry = True
                issues.append(f"Registry directory still exists: {registry_path}")
        
        cleanup_status = {
            'project_id': project_id,
            'completed_at': project['completed_at'],
            'session_names_checked': session_names,
            'lingering_sessions': lingering_sessions,
            'registry_path': registry_path,
            'lingering_registry': lingering_registry,
            'issues': issues,
            'needs_cleanup': len(issues) > 0
        }
        
        return cleanup_status

    def cleanup_verification_cycle(self):
        """Verify cleanup for the last 3 completed projects"""
        try:
            logger.debug("Starting cleanup verification cycle...")
            
            recent_completed = self.get_recent_completed_projects(3)
            if not recent_completed:
                logger.debug("No recent completed projects to verify")
                return
            
            logger.info(f"Verifying cleanup for {len(recent_completed)} recent completed projects")
            
            cleanup_issues = []
            
            for project in recent_completed:
                cleanup_status = self.verify_project_cleanup(project)
                
                if cleanup_status['needs_cleanup']:
                    cleanup_issues.append(cleanup_status)
                    logger.warning(f"🧹 Project {project['id']} cleanup issues: {', '.join(cleanup_status['issues'])}")
                else:
                    logger.debug(f"✅ Project {project['id']} properly cleaned up")
            
            if cleanup_issues:
                logger.warning(f"Found {len(cleanup_issues)} projects with cleanup issues")
                
                # Log detailed cleanup issues for manual intervention
                for issue in cleanup_issues:
                    logger.warning(f"Project {issue['project_id']} needs manual cleanup:")
                    for problem in issue['issues']:
                        logger.warning(f"  - {problem}")
                    
                    # Auto-cleanup if safe to do so
                    if issue['lingering_sessions']:
                        logger.info(f"Attempting to auto-cleanup lingering sessions for project {issue['project_id']}")
                        for session_name in issue['lingering_sessions']:
                            try:
                                subprocess.run(['tmux', 'kill-session', '-t', session_name], 
                                             capture_output=True, timeout=10)
                                logger.info(f"Killed lingering session: {session_name}")
                            except Exception as e:
                                logger.error(f"Failed to kill session {session_name}: {e}")
            else:
                logger.debug("All recent completed projects properly cleaned up")
                
        except Exception as e:
            logger.error(f"Error during cleanup verification cycle: {e}")

    def health_monitoring_cycle(self):
        """Check health of all active agent sessions"""
        try:
            processing_projects = self.get_processing_projects()
            
            for project in processing_projects:
                session_name = project.get('main_session')
                if not session_name:
                    continue
                    
                # Check if session exists
                try:
                    result = subprocess.run([
                        'tmux', 'has-session', '-t', session_name
                    ], capture_output=True, timeout=5)
                    
                    if result.returncode != 0:
                        logger.debug(f"Session {session_name} not found, skipping health check")
                        continue
                        
                except Exception as e:
                    logger.debug(f"Failed to check session {session_name}: {e}")
                    continue
                
                # Perform health check
                health_status = self.health_monitor.check_agent_health(session_name)
                
                if health_status:
                    # Record health check in database
                    self.health_database.record_health_check(session_name, health_status)
                    
                    # Check for stuck agents that need recovery
                    stuck_agents = [
                        (name, status) for name, status in health_status.items() 
                        if status.get('needs_recovery', False)
                    ]
                    
                    if stuck_agents:
                        logger.warning(f"Found {len(stuck_agents)} stuck agents in session {session_name}")
                        
                        for agent_name, agent_status in stuck_agents:
                            window_idx = agent_status.get('window_index')
                            if window_idx is not None:
                                logger.info(f"Attempting recovery for stuck agent {agent_name} in {session_name}:{window_idx}")
                                
                                success = self.health_monitor.auto_recover_stuck_agent(session_name, window_idx)
                                self.health_database.record_recovery_attempt(session_name, agent_name, success)
                                
                                if success:
                                    logger.info(f"Successfully recovered {agent_name}")
                                else:
                                    logger.error(f"Failed to recover {agent_name} - manual intervention may be required")
                    else:
                        logger.debug(f"All agents healthy in session {session_name}")
                        
        except Exception as e:
            logger.error(f"Error during health monitoring cycle: {e}")
    
    def run(self):
        """Main daemon loop"""
        logger.info("🔍 Completion Monitor Daemon started")
        logger.info(f"Monitoring for project completions every {self.poll_interval} seconds")
        
        while self.running:
            try:
                self.monitoring_cycle()
                
                # Wait for next cycle or shutdown signal
                for _ in range(self.poll_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(10)  # Brief pause before retrying
        
        logger.info("🛑 Completion Monitor Daemon stopped")

def main():
    parser = argparse.ArgumentParser(description='Tmux Orchestrator Completion Monitor Daemon')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--poll-interval', type=int, default=300, 
                       help='Poll interval in seconds (default: 300)')
    parser.add_argument('--test', action='store_true', help='Run one monitoring cycle and exit')
    
    args = parser.parse_args()
    
    # SINGLETON PROTECTION: Prevent multiple completion monitor instances
    lock_manager = SchedulerLockManager(mode="completion")
    
    try:
        logger.info("Acquiring completion monitor lock...")
        if not lock_manager.acquire_lock():
            logger.error("Another completion monitor daemon is already running!")
            logger.error("Check with: systemctl status tmux-orchestrator-completion")
            logger.error("Or kill duplicate processes: ps aux | grep completion_monitor")
            sys.exit(1)
        
        logger.info("✅ Completion monitor lock acquired successfully")
        
        # Create and run the daemon
        daemon = CompletionMonitorDaemon(poll_interval=args.poll_interval)
        
        if args.test:
            logger.info("Running test monitoring cycle...")
            daemon.monitoring_cycle()
            logger.info("Test completed")
        else:
            daemon.run()
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Completion monitor daemon error: {e}")
        raise
    finally:
        # Always release the lock
        try:
            lock_manager.release_lock()
            logger.info("Completion monitor lock released")
        except Exception as e:
            logger.warning(f"Error releasing completion monitor lock: {e}")

if __name__ == '__main__':
    main()
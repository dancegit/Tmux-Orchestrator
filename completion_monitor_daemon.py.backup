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
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import argparse

from completion_manager import CompletionManager
from session_state import SessionStateManager
from scheduler import TmuxOrchestratorScheduler

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
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"Completion Monitor Daemon initialized with {poll_interval}s poll interval")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def get_processing_projects(self) -> List[Dict[str, Any]]:
        """Get all projects that are currently PROCESSING"""
        db_path = self.tmux_orchestrator_path / 'task_queue.db'
        
        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, orchestrator_session as project_name, orchestrator_session as session_name, 
                           spec_path as spec_file, status, started_at
                    FROM project_queue 
                    WHERE status = 'processing'
                    ORDER BY started_at ASC
                """)
                
                projects = []
                for row in cursor.fetchall():
                    projects.append({
                        'id': row['id'],
                        'project_name': row['project_name'],
                        'session_name': row['session_name'],
                        'spec_file': row['spec_file'],
                        'status': row['status'],
                        'started_at': row['started_at']
                    })
                
                return projects
                
        except Exception as e:
            logger.error(f"Failed to get processing projects: {e}")
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
    
    def check_project_completion(self, project: Dict[str, Any]) -> str:
        """
        Check if a project is completed, failed, or still processing.
        
        Returns: 'completed', 'failed', 'processing'
        """
        session_name = project['session_name']
        project_id = project['id']
        
        logger.debug(f"Checking completion for project {project_id}: {session_name}")
        
        # First check if session still exists
        if not self.check_session_exists(session_name):
            logger.info(f"Session {session_name} no longer exists - marking as failed")
            return 'failed'
        
        try:
            # Use the external completion check script for consistency
            import subprocess
            
            logger.debug(f"Running completion check for project {project_id}")
            result = subprocess.run([
                'python3', 
                str(self.tmux_orchestrator_path / 'check_project_completion.py'),
                str(project_id)
            ], capture_output=True, text=True, timeout=120, cwd=str(self.tmux_orchestrator_path))
            
            logger.debug(f"Completion check result for project {project_id}: returncode={result.returncode}")
            
            if result.returncode == 0:
                # Parse the output to determine completion status
                output = result.stdout
                logger.debug(f"Completion check output: {output}")
                
                if "Project appears complete!" in output:
                    logger.info(f"Project {project_id} detected as complete")
                    return 'completed'
                elif "Project appears failed" in output or "ERROR" in output:
                    logger.info(f"Project {project_id} detected as failed")
                    return 'failed'
                else:
                    logger.debug(f"Project {project_id} still processing")
                    return 'processing'
            else:
                logger.warning(f"Completion check failed for project {project_id}: {result.stderr}")
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
        
        logger.debug("Monitoring cycle completed")
    
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
    
    # Create and run the daemon
    daemon = CompletionMonitorDaemon(poll_interval=args.poll_interval)
    
    if args.test:
        logger.info("Running test monitoring cycle...")
        daemon.monitoring_cycle()
        logger.info("Test completed")
    else:
        daemon.run()

if __name__ == '__main__':
    main()
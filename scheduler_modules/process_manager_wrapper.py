#!/usr/bin/env python3
"""
Process manager wrapper module extracted from scheduler.py
Wraps the existing ProcessManager with scheduler-specific functionality.
"""

import logging
import time
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessManagerWrapper:
    """Wrapper for ProcessManager with scheduler-specific enhancements."""
    
    def __init__(self, process_manager, db_connection, config):
        self.process_manager = process_manager
        self.conn = db_connection
        self.config = config
        self.active_processes = {}
        
    def track_project_process(self, project_id: int, pid: int, spec_path: str):
        """
        Track a process associated with a project.
        
        Args:
            project_id: Database ID of the project
            pid: Process ID to track
            spec_path: Path to the project specification
        """
        try:
            # Track in ProcessManager
            self.process_manager.track_process(
                pid=pid,
                name=f"project_{project_id}",
                metadata={
                    'project_id': project_id,
                    'spec_path': spec_path,
                    'started_at': time.time()
                }
            )
            
            # Track locally
            self.active_processes[project_id] = {
                'pid': pid,
                'spec_path': spec_path,
                'started_at': time.time()
            }
            
            # Update database
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE project_queue
                SET process_pid = ?
                WHERE id = ?
            """, (pid, project_id))
            self.conn.commit()
            
            logger.info(f"Tracking process {pid} for project {project_id}")
            
        except Exception as e:
            logger.error(f"Error tracking process for project {project_id}: {e}")
            
    def check_project_timeout(self, project_id: int) -> bool:
        """
        Check if a project has exceeded its timeout.
        
        Args:
            project_id: ID of project to check
            
        Returns:
            True if project has timed out, False otherwise
        """
        try:
            # Check with ProcessManager
            process_info = self.active_processes.get(project_id)
            if not process_info:
                return False
                
            pid = process_info['pid']
            started_at = process_info['started_at']
            
            # Check if process is still alive
            if not self.process_manager.is_process_alive(pid):
                logger.info(f"Process {pid} for project {project_id} is no longer alive")
                return True
                
            # Check runtime
            elapsed = time.time() - started_at
            max_runtime = self.config.MAX_AUTO_ORCHESTRATE_RUNTIME_SEC
            
            if elapsed > max_runtime:
                logger.warning(f"Project {project_id} exceeded timeout: {elapsed/3600:.1f} hours")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking timeout for project {project_id}: {e}")
            return False
            
    def terminate_project_process(self, project_id: int, reason: str = "Timeout"):
        """
        Terminate a project's process.
        
        Args:
            project_id: ID of project to terminate
            reason: Reason for termination
        """
        try:
            process_info = self.active_processes.get(project_id)
            if not process_info:
                logger.debug(f"No process info for project {project_id}")
                return
                
            pid = process_info['pid']
            
            # Terminate via ProcessManager
            success = self.process_manager.terminate_process(pid, grace_period=10)
            
            if success:
                logger.info(f"Terminated process {pid} for project {project_id}: {reason}")
            else:
                logger.warning(f"Failed to terminate process {pid} for project {project_id}")
                
            # Clean up tracking
            del self.active_processes[project_id]
            
            # Update database
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE project_queue
                SET process_pid = NULL,
                    notes = 'Process terminated: ' || ?
                WHERE id = ?
            """, (reason, project_id))
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error terminating process for project {project_id}: {e}")
            
    def cleanup_dead_processes(self):
        """Clean up tracking for dead processes."""
        try:
            dead_projects = []
            
            for project_id, process_info in self.active_processes.items():
                pid = process_info['pid']
                
                if not self.process_manager.is_process_alive(pid):
                    dead_projects.append(project_id)
                    logger.debug(f"Process {pid} for project {project_id} is dead")
                    
            # Clean up dead processes
            for project_id in dead_projects:
                del self.active_processes[project_id]
                
                # Update database
                cursor = self.conn.cursor()
                cursor.execute("""
                    UPDATE project_queue
                    SET process_pid = NULL
                    WHERE id = ? AND process_pid IS NOT NULL
                """, (project_id,))
                
            if dead_projects:
                self.conn.commit()
                logger.info(f"Cleaned up {len(dead_projects)} dead process(es)")
                
        except Exception as e:
            logger.error(f"Error cleaning up dead processes: {e}")
            
    def get_process_info(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        Get process information for a project.
        
        Args:
            project_id: ID of project
            
        Returns:
            Process information dictionary or None
        """
        return self.active_processes.get(project_id)
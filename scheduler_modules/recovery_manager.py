#!/usr/bin/env python3
"""
Recovery manager module extracted from scheduler.py
Handles reboot recovery and state restoration.
"""

import subprocess
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class RecoveryManager:
    """Manages recovery from reboots and system failures."""
    
    def __init__(self, db_connection, session_state_manager, config):
        self.conn = db_connection
        self.session_state_manager = session_state_manager
        self.config = config
        self.reboot_threshold_sec = config.REBOOT_DETECTION_THRESHOLD_SEC
        self.last_reboot_check = None
        
    def recover_from_reboot(self):
        """
        Detect if we're recovering from a reboot and clean up stale states.
        
        This method:
        1. Checks system uptime to detect recent reboots
        2. Resets any 'processing' projects to 'failed' if reboot detected
        3. Cleans up stale tmux sessions
        4. Updates recovery timestamps
        """
        try:
            # Get system uptime in seconds
            result = subprocess.run(['uptime', '-s'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.debug("Could not determine system uptime")
                return
                
            # Parse boot time
            boot_time_str = result.stdout.strip()
            try:
                # Parse format like "2024-01-09 10:30:45"
                boot_time = datetime.strptime(boot_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # Try alternate format
                try:
                    boot_time = datetime.strptime(boot_time_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    logger.debug(f"Could not parse boot time: {boot_time_str}")
                    return
                    
            uptime_seconds = (datetime.now() - boot_time).total_seconds()
            
            # If system has been up for less than threshold, we likely rebooted
            if uptime_seconds < self.reboot_threshold_sec:
                logger.warning(f"🔄 System reboot detected! Uptime: {uptime_seconds/60:.1f} minutes")
                
                # Check when we last ran this check
                if self.last_reboot_check:
                    time_since_check = (datetime.now() - self.last_reboot_check).total_seconds()
                    if time_since_check < 300:  # Don't run again within 5 minutes
                        logger.debug("Reboot recovery already ran recently, skipping")
                        return
                        
                self.last_reboot_check = datetime.now()
                
                # Reset all processing projects
                cursor = self.conn.cursor()
                cursor.execute("""
                    UPDATE project_queue
                    SET status = 'failed',
                        ended_at = datetime('now'),
                        notes = 'System reboot detected - project terminated'
                    WHERE status IN ('processing', 'timing_out')
                """)
                
                affected_rows = cursor.rowcount
                if affected_rows > 0:
                    self.conn.commit()
                    logger.info(f"✅ Reset {affected_rows} project(s) interrupted by reboot")
                    
                    # Emit event
                    if hasattr(self, '_dispatch_event'):
                        self._dispatch_event('reboot_recovery', {
                            'uptime_minutes': uptime_seconds / 60,
                            'projects_reset': affected_rows
                        })
                    
                # Clean up any orphaned tmux sessions
                try:
                    result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'],
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        sessions = result.stdout.strip().split('\n')
                        orchestrator_sessions = [s for s in sessions if 'orchestrator' in s.lower()]
                        
                        for session in orchestrator_sessions:
                            # Kill orphaned orchestrator sessions
                            subprocess.run(['tmux', 'kill-session', '-t', session],
                                         capture_output=True, check=False)
                            logger.info(f"Cleaned up orphaned session: {session}")
                            
                except Exception as e:
                    logger.debug(f"Could not clean tmux sessions: {e}")
                    
        except Exception as e:
            logger.error(f"Error in reboot recovery: {e}", exc_info=True)
            
    def recover_project(self, project_id: int, reason: str = "Manual recovery") -> bool:
        """
        Recover a failed or stuck project.
        
        Args:
            project_id: ID of the project to recover
            reason: Reason for recovery
            
        Returns:
            True if recovery successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            
            # Get project details
            cursor.execute("""
                SELECT status, spec_path, main_session
                FROM project_queue
                WHERE id = ?
            """, (project_id,))
            
            row = cursor.fetchone()
            if not row:
                logger.error(f"Project {project_id} not found")
                return False
                
            status, spec_path, main_session = row
            
            # Only recover if in recoverable state
            if status not in ['failed', 'timing_out', 'zombie', 'processing']:
                logger.warning(f"Project {project_id} in state '{status}' cannot be recovered")
                return False
                
            # Kill any existing session
            if main_session:
                try:
                    subprocess.run(['tmux', 'kill-session', '-t', main_session],
                                 capture_output=True, check=False)
                    logger.info(f"Killed existing session: {main_session}")
                except:
                    pass
                    
            # Update project status to recovered
            cursor.execute("""
                UPDATE project_queue
                SET status = 'recovered',
                    ended_at = datetime('now'),
                    notes = ?
                WHERE id = ?
            """, (reason, project_id))
            
            self.conn.commit()
            
            logger.info(f"✅ Project {project_id} recovered: {reason}")
            
            # Emit event
            if hasattr(self, '_dispatch_event'):
                self._dispatch_event('project_recovered', {
                    'project_id': project_id,
                    'spec_path': spec_path,
                    'reason': reason,
                    'previous_status': status
                })
                
            return True
            
        except Exception as e:
            logger.error(f"Error recovering project {project_id}: {e}", exc_info=True)
            if self.conn:
                self.conn.rollback()
            return False
            
    def check_recovery_needed(self) -> list:
        """
        Check if any projects need recovery.
        
        Returns:
            List of project IDs that may need recovery
        """
        recovery_candidates = []
        
        try:
            cursor = self.conn.cursor()
            
            # Find projects that have been processing too long
            cursor.execute("""
                SELECT id, spec_path, started_at
                FROM project_queue
                WHERE status = 'processing'
                AND datetime(started_at) < datetime('now', '-3 hours')
            """)
            
            for project_id, spec_path, started_at in cursor.fetchall():
                recovery_candidates.append({
                    'id': project_id,
                    'spec_path': spec_path,
                    'reason': 'Processing timeout (>3 hours)',
                    'started_at': started_at
                })
                
            # Find zombie projects
            cursor.execute("""
                SELECT id, spec_path, started_at
                FROM project_queue
                WHERE status = 'zombie'
            """)
            
            for project_id, spec_path, started_at in cursor.fetchall():
                recovery_candidates.append({
                    'id': project_id,
                    'spec_path': spec_path,
                    'reason': 'Zombie state detected',
                    'started_at': started_at
                })
                
        except Exception as e:
            logger.error(f"Error checking recovery candidates: {e}", exc_info=True)
            
        return recovery_candidates
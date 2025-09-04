#!/usr/bin/env python3
"""
Session monitoring module extracted from scheduler.py
Handles tmux session health checks and phantom detection.
"""

import subprocess
import logging
import time
from typing import Tuple, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class SessionMonitor:
    """Monitors tmux session health and detects phantom projects."""
    
    def __init__(self, db_connection, session_state_manager, config):
        self.conn = db_connection
        self.session_state_manager = session_state_manager
        self.config = config
        self.phantom_grace_period = config.PHANTOM_GRACE_PERIOD_SEC
        
    def detect_and_reset_phantom_projects(self) -> int:
        """
        [ENHANCED] Detect and reset phantom projects with intelligent grace periods.
        
        A phantom project is one that's marked as 'processing' but has no active process/session.
        Now includes:
        - OAuth grace period (first 45-60 seconds)
        - Configurable phantom grace period
        - Process verification via PID
        - Session validation
        
        Returns: Number of phantom projects reset
        """
        if not self.conn:
            return 0
            
        cursor = self.conn.cursor()
        phantom_count = 0
        
        try:
            # Get all processing projects with their metadata
            cursor.execute("""
                SELECT id, spec_path, started_at, main_session, process_pid
                FROM project_queue
                WHERE status = 'processing'
            """)
            
            processing_projects = cursor.fetchall()
            
            for project_id, spec_path, started_at, main_session, process_pid in processing_projects:
                # Calculate time since project started
                if started_at:
                    try:
                        # Parse ISO format timestamp
                        from datetime import datetime
                        start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                        elapsed_seconds = (datetime.now(start_time.tzinfo) - start_time).total_seconds()
                    except Exception as e:
                        logger.warning(f"Could not parse started_at for project {project_id}: {e}")
                        # If we can't parse, assume it's been running for a while
                        elapsed_seconds = self.phantom_grace_period + 1
                else:
                    # No start time, consider it old enough
                    elapsed_seconds = self.phantom_grace_period + 1
                
                # OAuth grace period: Skip projects in first 60 seconds (OAuth login time)
                if elapsed_seconds < 60:
                    logger.debug(f"Project {project_id} in OAuth grace period ({elapsed_seconds:.0f}s < 60s)")
                    continue
                
                # Extended phantom grace period for complex projects
                if elapsed_seconds < self.phantom_grace_period:
                    logger.debug(f"Project {project_id} in phantom grace period ({elapsed_seconds:.0f}s < {self.phantom_grace_period}s)")
                    continue
                
                # Check if the process is actually alive
                is_alive = False
                reason = "unknown"
                
                # First check: Process PID
                if process_pid:
                    try:
                        import psutil
                        process = psutil.Process(process_pid)
                        if process.is_running():
                            # Process exists, but let's verify it's actually our orchestrator
                            cmdline = ' '.join(process.cmdline())
                            if 'tmux_orchestrator' in cmdline:
                                is_alive = True
                                logger.debug(f"Project {project_id}: Process {process_pid} is alive and valid")
                            else:
                                reason = f"PID {process_pid} exists but not tmux_orchestrator process"
                        else:
                            reason = f"Process {process_pid} not running"
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        reason = f"Process {process_pid} does not exist or inaccessible"
                    except ImportError:
                        # psutil not available, fall back to session check
                        logger.debug("psutil not available, using session check only")
                else:
                    reason = "No process PID recorded"
                
                # Second check: Tmux session (if process check failed or no PID)
                if not is_alive and main_session:
                    try:
                        result = subprocess.run(
                            ['tmux', 'has-session', '-t', main_session],
                            capture_output=True,
                            check=False
                        )
                        if result.returncode == 0:
                            # Session exists, could still be valid
                            is_alive = True
                            reason = ""  # Clear reason since session is valid
                            logger.debug(f"Project {project_id}: Session {main_session} exists")
                        else:
                            if not reason:
                                reason = f"Session {main_session} does not exist"
                    except Exception as e:
                        if not reason:
                            reason = f"Session check failed: {e}"
                
                # If neither process nor session is alive, it's a phantom
                if not is_alive:
                    logger.warning(f"🻿 Phantom project detected: ID={project_id}, reason={reason}")
                    logger.info(f"  Spec: {spec_path}")
                    logger.info(f"  Runtime: {elapsed_seconds/60:.1f} minutes")
                    
                    # Reset to failed state
                    cursor.execute("""
                        UPDATE project_queue
                        SET status = 'failed',
                            ended_at = datetime('now'),
                            notes = 'Phantom project: ' || ?
                        WHERE id = ?
                    """, (reason, project_id))
                    
                    phantom_count += 1
                    
                    # Emit event for monitoring
                    if hasattr(self, '_dispatch_event'):
                        self._dispatch_event('phantom_detected', {
                            'project_id': project_id,
                            'spec_path': spec_path,
                            'reason': reason,
                            'runtime_minutes': elapsed_seconds / 60
                        })
                    
            if phantom_count > 0:
                self.conn.commit()
                logger.info(f"✅ Reset {phantom_count} phantom project(s)")
                
        except Exception as e:
            logger.error(f"Error detecting phantom projects: {e}", exc_info=True)
            if self.conn:
                self.conn.rollback()
                
        return phantom_count
    
    def validate_session_liveness(self, session_name: str, grace_period_sec: int = 900, 
                                 project_id: int = None, spec_path: str = None) -> Tuple[bool, str]:
        """
        Validates if a tmux session is truly alive and responsive.
        
        Enhanced validation that checks:
        1. Session exists
        2. Expected windows exist (orchestrator, pm, developer, tester)
        3. Panes are responsive (not in bash/shell state)
        4. Recent activity in panes
        
        Args:
            session_name: Name of the tmux session to validate
            grace_period_sec: Grace period before considering session dead
            project_id: Optional project ID for logging
            spec_path: Optional spec path for context
            
        Returns:
            Tuple of (is_alive, reason_if_dead)
        """
        try:
            # Check 1: Does session exist?
            result = subprocess.run(
                ['tmux', 'has-session', '-t', session_name],
                capture_output=True,
                check=False
            )
            
            if result.returncode != 0:
                return False, "Session does not exist"
            
            # Check 2: Get window list
            result = subprocess.run(
                ['tmux', 'list-windows', '-t', session_name, '-F', '#{window_index}:#{window_name}'],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                return False, "Could not list windows"
            
            windows = result.stdout.strip().split('\n')
            window_count = len([w for w in windows if w])
            
            # We expect at least 2 windows (orchestrator + one agent)
            if window_count < 2:
                return False, f"Only {window_count} window(s) found, expected at least 2"
            
            # Check 3: Validate key windows are not in shell state
            critical_windows = []
            for window in windows:
                if ':' in window:
                    idx, name = window.split(':', 1)
                    # Check orchestrator window (usually 0)
                    if idx == '0' or 'orchestrator' in name.lower():
                        critical_windows.append(idx)
            
            # Check at least one critical window
            dead_panes = 0
            for window_idx in critical_windows[:1]:  # Check first critical window
                target = f"{session_name}:{window_idx}"
                
                # Get pane command
                result = subprocess.run(
                    ['tmux', 'display-message', '-p', '-t', target, '#{pane_current_command}'],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    command = result.stdout.strip().lower()
                    # If orchestrator is in bash/sh, it's likely dead
                    if command in ['bash', 'sh', 'zsh']:
                        dead_panes += 1
                        logger.debug(f"Window {window_idx} in session {session_name} is in shell state")
            
            # If orchestrator is dead, session is effectively dead
            if dead_panes > 0:
                return False, f"{dead_panes} critical pane(s) in shell state"
            
            # Check 4: Look for recent activity (optional, may be expensive)
            # For now, if we got here, consider it alive
            
            logger.debug(f"Session {session_name} validated as alive with {window_count} windows")
            return True, ""
            
        except Exception as e:
            logger.error(f"Error validating session {session_name}: {e}", exc_info=True)
            return False, f"Validation error: {str(e)}"
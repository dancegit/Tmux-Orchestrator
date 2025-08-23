#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Enhanced Tmux Orchestrator Scheduler - Implements all Grok recommendations
Provides robust phantom detection, session validation, and completion tracking
"""

import time
import threading
import sqlite3
import os
import sys
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Tuple
import psutil  # For process scanning

# NEW: Imports for inter-process locking
import json
import socket
from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_UN
import atexit

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))
from session_state import SessionStateManager, SessionState
from email_notifier import get_email_notifier

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TmuxOrchestratorScheduler:
    def __init__(self, db_path='task_queue.db', tmux_orchestrator_path=None):
        self.db_path = db_path
        self.tmux_orchestrator_path = tmux_orchestrator_path or Path(__file__).parent
        self.session_state_manager = SessionStateManager(self.tmux_orchestrator_path)
        self.event_subscribers: Dict[str, List[Callable]] = {}  # Event hook system
        
        # Configuration from environment
        self.poll_interval = int(os.getenv('POLL_INTERVAL_SEC', '60'))
        self.max_concurrent = int(os.getenv('MAX_CONCURRENT_PROJECTS', '1'))
        self.stuck_timeout_hours = int(os.getenv('STUCK_TIMEOUT_HOURS', '4'))
        
        # Lock configuration for inter-process safety
        self.lock_path = Path('locks/project_queue.lock')
        self.lock_fd = None
        
        # State cache for optimization
        self.state_cache: Dict[str, SessionState] = {}
        
        # Setup database
        self.conn = sqlite3.connect(db_path, timeout=30.0)
        self.setup_database()
        
        # Queue processing state
        self.queue_lock = threading.Lock()  # Thread safety within this process
        self.stop_event = threading.Event()
        self.email_notifier = get_email_notifier()
        
        # NEW: Acquire inter-process lock
        self._acquire_process_lock()
        
        # Register exit handler to clean up lock
        atexit.register(self._release_process_lock)
        
        # Clean stale registry entries on startup
        self.session_state_manager.cleanup_stale_registries()
        
        # Auto-subscribe default completion handler
        self.subscribe('task_complete', self._handle_task_completion)
        self.subscribe('project_complete', self._on_project_complete)
        
        # Add authorization event types (for future use)
        self.event_subscribers.setdefault('authorization_request', [])
        self.event_subscribers.setdefault('authorization_response', [])
        
        # CRITICAL: Run phantom detection on startup
        logger.info("Running initial phantom project detection...")
        self.detect_and_reset_phantom_projects()
        
        # Start batch monitoring thread if enabled
        self._monitoring_enabled = os.getenv('ENABLE_BATCH_MONITORING', 'true').lower() == 'true'
        self._stop_monitoring = threading.Event()
        if self._monitoring_enabled:
            self.retry_thread = threading.Thread(target=self._monitor_batches, daemon=True)
            self.retry_thread.start()
            logger.info("Enhanced batch monitoring thread started")
        
        # NEW: Start heartbeat thread to keep lock fresh
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_thread, daemon=True)
        self.heartbeat_thread.start()
        logger.info("Lock heartbeat thread started")
    
    # NEW: Inter-process lock acquisition
    def _acquire_process_lock(self):
        try:
            # Create lock directory if it doesn't exist
            self.lock_path.parent.mkdir(exist_ok=True)
            
            # Create/open lock file
            self.lock_fd = open(self.lock_path, 'w')
            
            # Try to acquire exclusive lock (non-blocking)
            flock(self.lock_fd, LOCK_EX | LOCK_NB)
            
            # Write process info
            lock_info = {
                'pid': os.getpid(),
                'timestamp': datetime.now().isoformat(),
                'hostname': socket.gethostname()
            }
            self.lock_fd.write(json.dumps(lock_info))
            self.lock_fd.flush()
            
            logger.info(f"Successfully acquired process lock (PID: {os.getpid()})")
            
        except IOError:
            # Lock is held by another process
            logger.error("Another scheduler instance is already running!")
            logger.error(f"Check lock file: {self.lock_path}")
            
            # Try to read lock info
            try:
                with open(self.lock_path, 'r') as f:
                    lock_info = json.loads(f.read())
                    logger.error(f"Lock held by PID {lock_info['pid']} since {lock_info['timestamp']}")
            except:
                pass
                
            # Exit to prevent multiple schedulers
            sys.exit(1)
    
    def _release_process_lock(self):
        """Release the inter-process lock"""
        if self.lock_fd:
            try:
                flock(self.lock_fd, LOCK_UN)
                self.lock_fd.close()
                self.lock_path.unlink(missing_ok=True)
                logger.info("Released process lock")
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")
    
    def _heartbeat_thread(self):
        """Update lock file periodically to show we're alive"""
        while not self._stop_monitoring.is_set():
            if self.lock_fd:
                try:
                    lock_info = {
                        'pid': os.getpid(),
                        'timestamp': datetime.now().isoformat(),
                        'hostname': socket.gethostname()
                    }
                    self.lock_fd.seek(0)
                    self.lock_fd.truncate()
                    self.lock_fd.write(json.dumps(lock_info))
                    self.lock_fd.flush()
                except Exception as e:
                    logger.error(f"Error updating lock heartbeat: {e}")
            
            # Sleep for 30 seconds between heartbeats
            self._stop_monitoring.wait(30)
    
    def setup_database(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()
        
        # Main task queue table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scheduled_time REAL NOT NULL,
                note TEXT NOT NULL,
                target_window TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at REAL DEFAULT (strftime('%s', 'now')),
                executed_at REAL,
                session_name TEXT,
                agent_role TEXT
            )
        ''')
        
        # Add index for performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scheduled_time 
            ON task_queue(scheduled_time)
        ''')
        
        # Add index on status for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_status 
            ON task_queue(status)
        ''')
        
        # Project queue table for auto_orchestrate integration
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spec_path TEXT NOT NULL,
                project_name TEXT,
                status TEXT DEFAULT 'queued',
                queued_at REAL DEFAULT (strftime('%s', 'now')),
                started_at REAL,
                completed_at REAL,
                error_message TEXT,
                batch_id TEXT,
                session_name TEXT,
                orchestrator_session TEXT,
                main_session TEXT
            )
        ''')
        
        # Add index on project status
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_project_status 
            ON project_queue(status)
        ''')
        
        # Add index on batch_id for batch operations
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_batch_id 
            ON project_queue(batch_id)
        ''')
        
        self.conn.commit()
    
    def get_cached_state(self, project_name: str) -> Optional[SessionState]:
        """Get cached session state with TTL"""
        if project_name not in self.state_cache:
            self.state_cache[project_name] = self.session_state_manager.load_session_state(project_name)
        elif self.state_cache[project_name]:
            # Check if cache is stale (5 minutes)
            try:
                updated_at = datetime.fromisoformat(self.state_cache[project_name].updated_at)
                if (datetime.now() - updated_at).total_seconds() > 300:
                    self.state_cache[project_name] = self.session_state_manager.load_session_state(project_name)
            except:
                self.state_cache[project_name] = self.session_state_manager.load_session_state(project_name)
        
        return self.state_cache.get(project_name)
    
    def validate_session_liveness(self, session_name: str, grace_period_sec: int = 120) -> Tuple[bool, str]:
        """Validate tmux session liveness with multiple checks.
        
        Args:
            session_name: Tmux session name to check.
            grace_period_sec: Allow recent sessions to pass even if not fully active (e.g., during startup).
        
        Returns:
            (is_live, reason): True if live, else False with failure reason.
        """
        now = int(time.time())
        
        # Check existence
        try:
            result = subprocess.run(['tmux', 'has-session', '-t', session_name], capture_output=True)
            if result.returncode != 0:
                return False, "Session does not exist"
        except Exception as e:
            return False, f"Session existence check failed: {e}"
        
        # Check for dead panes
        try:
            panes = subprocess.run(
                ['tmux', 'list-panes', '-t', session_name, '-F', '#{pane_dead}'],
                capture_output=True, text=True
            )
            if panes.returncode != 0:
                return False, "Failed to list panes"
            
            if '1' in panes.stdout.strip().split('\n'):
                return False, "Session has dead panes"
            
            # Check activity (last activity time)
            activity = subprocess.run(
                ['tmux', 'display-message', '-t', session_name, '-p', '#{session_activity}'],
                capture_output=True, text=True
            )
            if activity.returncode == 0 and activity.stdout.strip():
                try:
                    last_active = int(activity.stdout.strip())
                    if now - last_active > 1800:  # 30min idle threshold
                        return False, "Session inactive for over 30 minutes"
                except:
                    # If we can't parse activity, check start time
                    pass
            
            # Check session creation time for grace period
            created = subprocess.run(
                ['tmux', 'display-message', '-t', session_name, '-p', '#{session_created}'],
                capture_output=True, text=True
            )
            if created.returncode == 0 and created.stdout.strip():
                try:
                    created_time = int(created.stdout.strip())
                    if now - created_time < grace_period_sec:
                        return True, "Session is new and within grace period"
                except:
                    pass
        except Exception as e:
            return False, f"Liveness check failed: {e}"
        
        # Check for active processes in panes
        processes = subprocess.run(
            ['tmux', 'list-panes', '-t', session_name, '-F', '#{pane_pid}'],
            capture_output=True, text=True
        )
        if processes.returncode != 0 or not processes.stdout.strip():
            return False, "No active processes in panes"
        
        return True, "Session is live"
    
    def detect_and_reset_phantom_projects(self) -> int:
        """Detect and reset phantom projects in 'processing' state with no active tmux or auto_orchestrate.py process."""
        reset_count = 0
        
        with self.queue_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, project_name, orchestrator_session, main_session, started_at
                FROM project_queue 
                WHERE status = 'processing'
            """)
            
            for row in cursor.fetchall():
                project_id, project_name, orch_session, main_session, started_at = row
                
                # Skip if project just started (2 minute grace period)
                if started_at and time.time() - float(started_at) < 120:
                    logger.debug(f"Project {project_id} is within grace period, skipping")
                    continue
                
                state = self.get_cached_state(project_name) if project_name else None
                
                # Check 1: No state file - definitely phantom
                if not state and project_name:
                    self._reset_phantom_project(cursor, project_id, project_name, reason="No session state found")
                    reset_count += 1
                    continue
                
                # Check 2: Session validation
                session_to_check = orch_session or main_session or (state.session_name if state else None)
                if session_to_check:
                    is_live, reason = self.validate_session_liveness(session_to_check)
                    if not is_live:
                        self._reset_phantom_project(cursor, project_id, project_name or "unknown", reason=reason)
                        reset_count += 1
                        continue
                
                # Check 3: Running auto_orchestrate.py process
                is_running = False
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            cmdline = proc.info['cmdline']
                            if cmdline and any('auto_orchestrate.py' in arg for arg in cmdline):
                                # Check if this process is for our project
                                if project_name and any(project_name in arg for arg in cmdline):
                                    is_running = True
                                    break
                                # Also check by project ID
                                if any(f'--project-id {project_id}' in ' '.join(cmdline) for arg in cmdline):
                                    is_running = True
                                    break
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                except Exception as e:
                    logger.error(f"Error checking processes: {e}")
                
                if not is_running and started_at and time.time() - float(started_at) > 300:  # 5 minutes
                    self._reset_phantom_project(cursor, project_id, project_name or "unknown", 
                                              reason="No running auto_orchestrate.py process after 5 minutes")
                    reset_count += 1
                    continue
            
            self.conn.commit()
        
        if reset_count > 0:
            logger.warning(f"Reset {reset_count} phantom PROCESSING projects")
        else:
            logger.debug("No phantom projects detected")
        
        return reset_count
    
    def _reset_phantom_project(self, cursor, project_id: int, project_name: str, reason: str):
        """Helper to reset a phantom project and update state."""
        error_msg = f"Phantom project detected: {reason}"
        cursor.execute("""
            UPDATE project_queue 
            SET status = 'failed', 
                error_message = ?,
                completed_at = strftime('%s', 'now')
            WHERE id = ?
        """, (error_msg, project_id))
        logger.warning(f"Reset phantom project {project_id} ({project_name}): {reason}")
        
        # Update session state if exists
        state = self.get_cached_state(project_name) if project_name else None
        if state:
            state.completion_status = 'failed'
            state.failure_reason = reason
            self.session_state_manager.save_session_state(state)
        
        # Dispatch event for notifications
        self._dispatch_event('project_complete', {
            'project_id': project_id, 
            'status': 'failed', 
            'reason': reason,
            'project_name': project_name
        })
    
    def detect_completed_projects(self):
        """Sync completion status from SessionState to project_queue."""
        with self.queue_lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, project_name FROM project_queue WHERE status = 'processing'")
            
            for row in cursor.fetchall():
                project_id, project_name = row
                if not project_name:
                    continue
                    
                state = self.get_cached_state(project_name)
                if not state:
                    continue
                
                if state.completion_status in ['completed', 'failed']:
                    status = state.completion_status
                    error_msg = state.failure_reason if status == 'failed' else None
                    cursor.execute("""
                        UPDATE project_queue 
                        SET status = ?, 
                            error_message = ?,
                            completed_at = strftime('%s', 'now')
                        WHERE id = ?
                    """, (status, error_msg, project_id))
                    logger.info(f"Synced completion for project {project_id} ({project_name}) to {status}")
                    self._dispatch_event('project_complete', {
                        'project_id': project_id, 
                        'status': status,
                        'project_name': project_name
                    })
            
            self.conn.commit()
    
    def check_stuck_projects(self):
        """Enhanced stuck project detection with configurable timeout and liveness checks"""
        timeout_seconds = self.stuck_timeout_hours * 3600
        
        with self.queue_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, project_name, started_at, orchestrator_session, main_session
                FROM project_queue 
                WHERE status = 'processing'
            """)
            
            now = int(time.time())
            for row in cursor.fetchall():
                project_id, project_name, started_at, orch_session, main_session = row
                is_stuck = False
                reason = None
                
                # Time-based timeout
                if started_at and now - int(started_at) > timeout_seconds:
                    is_stuck = True
                    reason = f'Timeout after {self.stuck_timeout_hours} hours in processing'
                
                # Liveness check even if not timed out
                elif project_name:
                    state = self.get_cached_state(project_name)
                    session_name = orch_session or main_session or (state.session_name if state else None)
                    
                    if session_name:
                        is_live, liveness_reason = self.validate_session_liveness(session_name)
                        if not is_live:
                            is_stuck = True
                            reason = liveness_reason
                
                if is_stuck:
                    cursor.execute("""
                        UPDATE project_queue 
                        SET status = 'failed', 
                            error_message = ?,
                            completed_at = strftime('%s', 'now')
                        WHERE id = ?
                    """, (f'Auto-reset: {reason}', project_id))
                    
                    if project_name:
                        state = self.get_cached_state(project_name)
                        if state:
                            state.completion_status = 'failed'
                            state.failure_reason = reason
                            self.session_state_manager.save_session_state(state)
                    
                    logger.warning(f"Reset stuck project {project_id}: {reason}")
                    self._dispatch_event('project_complete', {
                        'project_id': project_id,
                        'status': 'failed',
                        'reason': reason,
                        'project_name': project_name
                    })
            
            self.conn.commit()
    
    def _monitor_batches(self):
        """Enhanced background thread with all monitoring functions"""
        logger.info("Starting enhanced batch monitoring loop")
        
        # Use adaptive polling - faster when projects are active
        while not self._stop_monitoring.is_set():
            try:
                # Check for active projects
                cursor = self.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM project_queue WHERE status = 'processing'")
                active_count = cursor.fetchone()[0]
                
                # Adaptive polling interval
                poll_interval = 10 if active_count > 0 else self.poll_interval
                
                # Run all monitoring functions
                self.check_stuck_projects()
                self.detect_and_reset_phantom_projects()
                self.detect_completed_projects()
                
                # Original batch monitoring
                cursor.execute("""
                    SELECT DISTINCT batch_id 
                    FROM project_queue 
                    WHERE batch_id IS NOT NULL 
                    AND status IN ('queued', 'processing')
                """)
                
                incomplete_batches = [row[0] for row in cursor.fetchall()]
                for batch_id in incomplete_batches:
                    if self._is_batch_complete(batch_id):
                        logger.info(f"Detected completion of batch {batch_id}")
                        self._handle_batch_completion(batch_id)
                
            except Exception as e:
                logger.error(f"Error in enhanced batch monitoring: {e}", exc_info=True)
            
            # Wait for next cycle
            self._stop_monitoring.wait(poll_interval)
        
        logger.info("Enhanced batch monitoring stopped")
    
    def _dispatch_event(self, event: str, data: Dict[str, Any]):
        """Dispatch an event to all subscribers"""
        for callback in self.event_subscribers.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in event callback {callback.__name__}: {e}")
    
    def subscribe(self, event: str, callback: Callable):
        """Subscribe a callback to an event"""
        self.event_subscribers.setdefault(event, []).append(callback)
        logger.info(f"Subscribed {callback.__name__} to event '{event}'")
    
    def _handle_task_completion(self, event_data: Dict):
        """Handle task completion events"""
        # Existing task completion logic
        pass
    
    def _on_project_complete(self, event_data: Dict):
        """Handle project completion events"""
        batch_id = event_data.get('batch_id')
        if batch_id:
            logger.debug(f"Project completion event for batch {batch_id}")
            # Trigger immediate check instead of waiting for monitoring cycle
            threading.Thread(
                target=self.check_batch_completion, 
                args=(batch_id,),
                daemon=True
            ).start()
    
    def _is_batch_complete(self, batch_id: str) -> bool:
        """Check if all projects in a batch are complete"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM project_queue 
            WHERE batch_id = ? AND status IN ('queued', 'processing')
        """, (batch_id,))
        return cursor.fetchone()[0] == 0
    
    def _handle_batch_completion(self, batch_id: str):
        """Handle batch completion - send notifications, etc."""
        logger.info(f"Batch {batch_id} completed")
        # Add batch completion logic here
    
    def check_batch_completion(self, batch_id: str):
        """Check and handle batch completion"""
        if self._is_batch_complete(batch_id):
            self._handle_batch_completion(batch_id)
    
    def mark_project_complete(self, project_id: int, success: bool = True, error_message: str = None):
        """Mark a project as complete"""
        with self.queue_lock:
            cursor = self.conn.cursor()
            status = 'completed' if success else 'failed'
            cursor.execute("""
                UPDATE project_queue 
                SET status = ?, error_message = ?, completed_at = strftime('%s', 'now')
                WHERE id = ?
            """, (status, error_message, project_id))
            self.conn.commit()
            logger.info(f"Marked project {project_id} as {status}")
    
    def stop_monitoring(self):
        """Stop all monitoring threads"""
        if hasattr(self, '_stop_monitoring'):
            self._stop_monitoring.set()
            logger.info("Monitoring stop requested")
    
    def __del__(self):
        """Cleanup on deletion"""
        self.stop_monitoring()
        self._release_process_lock()


if __name__ == "__main__":
    # Test the enhanced scheduler
    scheduler = TmuxOrchestratorScheduler()
    logger.info("Enhanced scheduler initialized successfully")
    
    # Run specific recovery for Project 58 if needed
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--reset-project-58":
        logger.info("Running Project 58 recovery...")
        scheduler.mark_project_complete(58, success=False, 
                                       error_message="Manual reset: No active session/process after 7+ hours")
        logger.info("Project 58 reset complete")
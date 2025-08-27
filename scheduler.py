#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psutil",
#     "python-dotenv",
# ]
# ///
"""
Tmux Orchestrator Scheduler - Replaces at command with reliable Python-based scheduling
Provides persistent task queue, credit exhaustion detection, and missed task recovery
"""

# Set UV_NO_WORKSPACE environment variable for all subprocess calls
import os
os.environ['UV_NO_WORKSPACE'] = '1'

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
import signal
from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_UN
import atexit

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))
from session_state import SessionStateManager, SessionState
from scheduler_lock_manager import SchedulerLockManager
from email_notifier import get_email_notifier
from process_manager import ProcessManager  # NEW: Import ProcessManager for subprocess tracking
from state_synchronizer import StateSynchronizer  # NEW: Import for proactive null session repair
from project_lock import ProjectLock  # NEW: Import for cross-project interference prevention
from tmux_session_manager import TmuxSessionManager  # Required for safe tmux operations

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

class DependencyChecker:
    """Ensures critical dependencies are available at runtime with auto-installation."""
    
    @staticmethod
    def verify_psutil():
        """Verify psutil is available, auto-install if missing."""
        try:
            import psutil
            logger.info(f"✓ psutil verified: version {psutil.__version__}")
            return True
        except ImportError:
            logger.warning("⚠️  psutil missing - attempting auto-install")
            try:
                # Use uv to install psutil
                result = subprocess.run(['uv', 'pip', 'install', 'psutil>=5.9.0'], 
                                      check=True, capture_output=True, text=True)
                logger.info(f"✓ psutil installation output: {result.stdout}")
                
                # Verify installation worked
                import psutil
                logger.info(f"✓ psutil installed successfully: version {psutil.__version__}")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to install psutil via uv: {e}")
                logger.error(f"Command output: {e.stdout}")
                logger.error(f"Command error: {e.stderr}")
                return False
            except ImportError as e:
                logger.error(f"❌ psutil still unavailable after installation attempt: {e}")
                return False
            except Exception as e:
                logger.error(f"❌ Unexpected error during psutil installation: {e}")
                return False
    
    @staticmethod
    def verify_all_dependencies():
        """Verify all critical dependencies are available."""
        dependencies_ok = True
        
        if not DependencyChecker.verify_psutil():
            dependencies_ok = False
            
        return dependencies_ok

class TmuxOrchestratorScheduler:
    def __init__(self, db_path='task_queue.db', tmux_orchestrator_path=None, read_only=False):
        self.db_path = db_path
        self.tmux_orchestrator_path = tmux_orchestrator_path or Path(__file__).parent
        self.session_state_manager = SessionStateManager(self.tmux_orchestrator_path)
        self.event_subscribers: Dict[str, List[Callable]] = {}  # Event hook system
        self.read_only = read_only  # Flag to indicate read-only operations
        
        # Verify critical dependencies before proceeding
        if not DependencyChecker.verify_all_dependencies():
            raise RuntimeError("Critical dependencies unavailable - cannot proceed with scheduler initialization")
        
        # Add lock for thread-safe queue operations (FIX: Prevent concurrent project starts)
        self.queue_lock = threading.Lock()
        
        # ENHANCED: Use robust lock manager to prevent duplicate schedulers
        # Only acquire lock for write operations (daemon mode)
        self.lock_manager = SchedulerLockManager(lock_dir="locks", timeout=30)
        if not read_only and not self.lock_manager.acquire_lock():
            logger.error("❌ Another scheduler is already running. Exiting to prevent duplicates.")
            sys.exit(1)
        
        # Add configurable poll interval
        self.poll_interval = int(os.getenv('POLL_INTERVAL_SEC', 60))
        
        # Add configurable concurrency limit (default 1 for sequential processing)
        self.max_concurrent = int(os.getenv('MAX_CONCURRENT_PROJECTS', 1))
        
        # NEW: For re-entrance protection to prevent notification loops
        self.processing_events = set()
        self._event_lock = threading.Lock()
        
        # Initialize TmuxSessionManager for session management
        self.tmux_manager = TmuxSessionManager()
        
        # NEW: Initialize ProcessManager for subprocess tracking and timeout enforcement
        if not read_only:
            self.process_manager = ProcessManager(
                max_runtime=int(os.getenv('MAX_AUTO_ORCHESTRATE_RUNTIME_SEC', 1800)),  # Default 30 minutes for Claude analysis
                monitor_interval=int(os.getenv('PROCESS_MONITOR_INTERVAL_SEC', 30))   # Check every 30 seconds
            )
            logger.info(f"ProcessManager initialized with {self.process_manager.max_runtime}s timeout")
        else:
            self.process_manager = None
        
        # Configure phantom detection grace period for long-running Claude analysis
        self.phantom_grace_period = int(os.getenv('PHANTOM_GRACE_PERIOD_SEC', 900))  # Default 15 minutes instead of 2
        
        # NEW: State synchronization configuration
        self.state_sync_interval = int(os.getenv('STATE_SYNC_INTERVAL_SEC', 300))  # 5 minutes default
        self.last_state_sync = 0
        logger.info(f"State synchronization configured with {self.state_sync_interval}s interval")
        
        # NEW: Orphaned session reconciliation configuration
        self.orphaned_reconcile_interval = int(os.getenv('ORPHANED_RECONCILE_INTERVAL_SEC', 600))  # 10 minutes default
        self.last_orphaned_reconcile = 0
        logger.info(f"Orphaned session reconciliation configured with {self.orphaned_reconcile_interval}s interval")
        
        self.setup_database()
        
        # Clean stale registry entries on startup (only for write operations)
        if not read_only:
            self.session_state_manager.cleanup_stale_registries()
            
            # NEW: Reboot recovery - handle projects that were processing before shutdown
            self._recover_from_reboot()
            
            # Auto-subscribe default completion handler
            self.subscribe('task_complete', self._handle_task_completion)
            self.subscribe('project_complete', self._on_project_complete)
            
            # Add authorization event types (for future use)
            self.event_subscribers.setdefault('authorization_request', [])
            self.event_subscribers.setdefault('authorization_response', [])
            
            # CRITICAL: Run phantom detection on startup to clean up stuck projects
            logger.info("Running initial phantom project detection...")
            self.detect_and_reset_phantom_projects()
        
        # NEW: Register lock release on exit (only if not read-only)
        if not read_only:
            atexit.register(self.lock_manager.release_lock)
        
        # NEW: Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Start batch monitoring thread if enabled (only for write operations)
        self._monitoring_enabled = os.getenv('ENABLE_BATCH_MONITORING', 'true').lower() == 'true'
        self._stop_monitoring = threading.Event()
        if self._monitoring_enabled and not read_only:
            self.retry_thread = threading.Thread(target=self._monitor_batches, daemon=True)
            self.retry_thread.start()
            logger.info("Batch monitoring thread started")
        
        # NEW: Start heartbeat thread to keep lock fresh (only for write operations)
        if not read_only:
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_thread, daemon=True)
            self.heartbeat_thread.start()
            logger.info("Lock heartbeat thread started")
    
    # NEW: Inter-process lock acquisition
    def _acquire_process_lock(self):
        try:
            # Create lock directory if it doesn't exist
            self.lock_path.parent.mkdir(exist_ok=True)
            
            # Create/open lock file
            self.lock_fd = open(self.lock_path, 'w+')
            
            # Try to acquire exclusive non-blocking lock
            try:
                flock(self.lock_fd, LOCK_EX | LOCK_NB)
            except IOError:
                # Lock is held - check for staleness
                self.lock_fd.seek(0)
                try:
                    lock_content = self.lock_fd.read()
                    if lock_content:
                        lock_data = json.loads(lock_content)
                        pid = lock_data.get('pid')
                        timestamp = datetime.fromisoformat(lock_data.get('timestamp', '1970-01-01'))
                        
                        # Check if lock is stale (older than 1 hour)
                        if (datetime.now() - timestamp).total_seconds() > 3600:
                            logger.warning(f"Lock is stale (created at {timestamp}), attempting to release")
                            self.lock_fd.seek(0)
                            self.lock_fd.truncate()
                            flock(self.lock_fd, LOCK_EX | LOCK_NB)
                        # Check if process is dead
                        elif pid and pid != os.getpid():
                            try:
                                os.kill(pid, 0)  # Check if process exists
                            except OSError:
                                logger.warning(f"Lock holder process {pid} is dead, releasing lock")
                                self.lock_fd.seek(0)
                                self.lock_fd.truncate()
                                flock(self.lock_fd, LOCK_EX | LOCK_NB)
                            else:
                                raise RuntimeError(f"Scheduler already running (PID: {pid})")
                        else:
                            raise RuntimeError("Scheduler already running")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Invalid lock file content: {e}, attempting to acquire")
                    self.lock_fd.seek(0)
                    self.lock_fd.truncate()
                    flock(self.lock_fd, LOCK_EX | LOCK_NB)
            
            # Write our lock data
            self.lock_fd.seek(0)
            self.lock_fd.truncate()
            lock_data = {
                'pid': os.getpid(),
                'timestamp': datetime.now().isoformat(),
                'hostname': socket.gethostname()
            }
            self.lock_fd.write(json.dumps(lock_data) + '\n')
            self.lock_fd.flush()
            logger.info(f"Acquired process lock: {lock_data}")
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            if self.lock_fd:
                self.lock_fd.close()
                self.lock_fd = None
            raise RuntimeError(f"Could not acquire scheduler lock: {e}")
    
    # NEW: Release inter-process lock
    def _release_process_lock(self):
        if self.lock_fd and not self.lock_fd.closed:
            flock(self.lock_fd, LOCK_UN)
            self.lock_fd.close()
            self.lock_fd = None
            logger.info("Released process lock")
    
    # NEW: Heartbeat thread to keep lock fresh
    def _heartbeat_thread(self):
        """Update lock file timestamp every 30 seconds to indicate we're alive"""
        last_health_check = 0
        health_check_interval = 300  # 5 minutes
        
        while not self._stop_monitoring.is_set():
            try:
                # Get lock_fd from lock_manager
                lock_fd = None
                if hasattr(self, 'lock_manager') and self.lock_manager:
                    lock_fd = getattr(self.lock_manager, 'lock_fd', None)
                
                # NEW: Guard and reacquire if lock_fd is missing or closed
                if not lock_fd or (hasattr(lock_fd, 'closed') and lock_fd.closed):
                    logger.warning("lock_fd missing or closed - attempting to reacquire")
                    # Try to reacquire through the lock manager
                    if hasattr(self, 'lock_manager') and self.lock_manager:
                        if self.lock_manager.acquire_lock():
                            # The lock manager should have set self.lock_manager.lock_fd if successful
                            logger.info("Successfully reacquired lock through lock manager")
                            lock_fd = getattr(self.lock_manager, 'lock_fd', None)
                        else:
                            logger.error("Failed to reacquire lock - shutting down heartbeat")
                            break  # Exit thread if reacquire fails
                    else:
                        logger.error("No lock_manager available for reacquisition")
                        break
                
                # Original code (with added flush check) - use lock_fd from lock_manager
                if lock_fd and not lock_fd.closed:
                    lock_fd.seek(0)
                    lock_data = {
                        'pid': os.getpid(),
                        'timestamp': datetime.now().isoformat(),
                        'hostname': socket.gethostname()
                    }
                    lock_fd.truncate()
                    lock_fd.write(json.dumps(lock_data) + '\n')
                    lock_fd.flush()
                    os.fsync(lock_fd.fileno())  # NEW: Ensure write is synced to disk
                    logger.debug(f"Updated lock heartbeat: {lock_data['timestamp']}")
            except Exception as e:
                logger.error(f"Error updating lock heartbeat: {e}")
                # NEW: On error, attempt reacquire on next iteration
            
            # Perform health check every 5 minutes
            current_time = time.time()
            if current_time - last_health_check > health_check_interval:
                last_health_check = current_time
                if not self._check_dependencies():
                    logger.error("Dependency health check failed - critical dependencies missing")
                    self._dispatch_event('dependency_failure', {
                        'timestamp': current_time,
                        'severity': 'critical'
                    })
            
            # Sleep for 30 seconds
            self._stop_monitoring.wait(30)
    
    def _check_dependencies(self):
        """Check all required system dependencies"""
        required_commands = ['bc', 'tmux', 'git', 'python3']
        missing = []
        
        for cmd in required_commands:
            try:
                result = subprocess.run(['which', cmd], capture_output=True, text=True)
                if result.returncode != 0:
                    missing.append(cmd)
                    logger.error(f"Missing required dependency: {cmd}")
            except Exception as e:
                logger.error(f"Error checking command {cmd}: {e}")
                missing.append(cmd)
        
        # Check tmux server is running
        if 'tmux' not in missing:
            try:
                result = subprocess.run(['tmux', 'list-sessions'], capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning("tmux server not running")
            except:
                pass
        
        if missing:
            logger.error(f"Missing dependencies: {', '.join(missing)}")
            logger.error("To install missing dependencies:")
            if 'bc' in missing:
                logger.error("  sudo apt-get install bc  # or brew install bc on macOS")
            if 'tmux' in missing:
                logger.error("  sudo apt-get install tmux  # or brew install tmux on macOS")
            return False
        
        return True
    
    def check_stuck_projects(self):
        """Enhanced stuck project detection with configurable timeout and liveness checks"""
        stuck_timeout_hours = int(os.getenv('STUCK_TIMEOUT_HOURS', '4'))
        timeout_seconds = stuck_timeout_hours * 3600
        
        with self.queue_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, project_path, started_at, orchestrator_session, main_session, spec_path, session_name
                FROM project_queue 
                WHERE status = 'processing'
            """)
            
            now = int(time.time())
            for row in cursor.fetchall():
                project_id, project_path, started_at, orch_session, main_session, spec_path, session_name = row
                is_stuck = False
                reason = None
                
                # Derive project name from spec path (for state manager)
                project_name = None
                if spec_path:
                    project_name = Path(spec_path).stem.lower().replace('_', '-')
                
                # Time-based timeout - Handle both timestamp and datetime string formats
                if started_at:
                    if isinstance(started_at, str):
                        # Convert datetime string to timestamp
                        try:
                            from datetime import datetime
                            dt = datetime.strptime(started_at, '%Y-%m-%d %H:%M:%S')
                            started_timestamp = dt.timestamp()
                        except ValueError:
                            # Try to parse as float if it's a string representation of a number
                            try:
                                started_timestamp = float(started_at)
                            except ValueError:
                                logger.error(f"Invalid started_at format for project {project_id}: {started_at}")
                                started_timestamp = 0
                    else:
                        started_timestamp = float(started_at)
                        
                    if started_timestamp and now - started_timestamp > timeout_seconds:
                        is_stuck = True
                        reason = f'Timeout after {stuck_timeout_hours} hours in processing'
                
                # Liveness check even if not timed out - USE session_name column directly
                elif session_name:
                    # Use the session_name from database directly instead of trying to derive it
                    is_live, liveness_reason = self.validate_session_liveness(session_name, project_id=project_id, spec_path=spec_path)
                    if not is_live:
                        is_stuck = True
                        reason = liveness_reason
                # Fallback: if no session_name, try orchestrator_session or main_session, or pattern matching
                elif orch_session:
                    is_live, liveness_reason = self.validate_session_liveness(orch_session, project_id=project_id, spec_path=spec_path)
                    if not is_live:
                        is_stuck = True
                        reason = liveness_reason
                elif main_session:
                    is_live, liveness_reason = self.validate_session_liveness(main_session, project_id=project_id, spec_path=spec_path)
                    if not is_live:
                        is_stuck = True
                        reason = liveness_reason
                else:
                    # No session names in database - use pattern matching fallback
                    is_live, liveness_reason = self.validate_session_liveness(None, project_id=project_id, spec_path=spec_path)
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
                        state = self.session_state_manager.load_session_state(project_name)
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
    
    def reset_project_to_queued(self, project_id: int, _internal_call: bool = False) -> bool:
        """Reset a project to queued status regardless of current status"""
        if _internal_call:
            # Already have lock, don't acquire again
            cursor = self.conn.cursor()
        else:
            # External call, acquire both queue lock and project lock
            project_lock = ProjectLock()
            if not project_lock.acquire(project_id):
                logger.error(f"Failed to acquire project lock for reset of project {project_id}")
                return False
            
            try:
                with self.queue_lock:
                    cursor = self.conn.cursor()
                    cursor.execute("""
                        SELECT id FROM project_queue WHERE id = ?
                    """, (project_id,))
                    row = cursor.fetchone()
                    if not row:
                        logger.error(f"Project {project_id} not found")
                        return False
                    
                    cursor.execute("""
                        UPDATE project_queue 
                        SET status = 'queued', started_at = NULL, completed_at = NULL, 
                            error_message = NULL, orchestrator_session = NULL, main_session = NULL
                        WHERE id = ?
                    """, (project_id,))
                    self.conn.commit()
                    logger.info(f"Project {project_id} reset to queued status")
                    return True
            finally:
                project_lock.release()
        
        # Internal call path
        cursor.execute("""
            SELECT id FROM project_queue WHERE id = ?
        """, (project_id,))
        row = cursor.fetchone()
        if not row:
            logger.error(f"Project {project_id} not found")
            return False
        
        cursor.execute("""
            UPDATE project_queue 
            SET status = 'queued', started_at = NULL, completed_at = NULL, 
                error_message = NULL, orchestrator_session = NULL, main_session = NULL
            WHERE id = ?
        """, (project_id,))
        self.conn.commit()
        logger.info(f"Project {project_id} reset to queued status")
        return True

    def check_and_reset_specific_project(self, project_id: int, force: bool = False) -> bool:
        """Check if a specific project is stuck and optionally reset it"""
        # Acquire project lock to prevent interference during reset operations
        project_lock = ProjectLock()
        if not project_lock.acquire(project_id):
            logger.error(f"Failed to acquire project lock for check/reset of project {project_id}")
            return False
        
        try:
            with self.queue_lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    SELECT status, started_at, orchestrator_session, main_session, session_name
                    FROM project_queue 
                    WHERE id = ?
                """, (project_id,))
                row = cursor.fetchone()
                if not row:
                    logger.error(f"Project {project_id} not found")
                    return False
                
                status, started_at, orch_session, main_session, session_name = row
                
                # If force is specified, always reset regardless of status
                if force:
                    return self.reset_project_to_queued(project_id, _internal_call=True)
                
                if status != 'processing':
                    logger.info(f"Project {project_id} is {status}, not processing")
                    return False
                
                is_stuck = False
                if started_at and time.time() - float(started_at) > 7200:  # 2 hours (reduced from 4)
                    is_stuck = True
                    logger.info(f"Project {project_id} has been running for {(time.time() - float(started_at))/3600:.1f} hours")
                elif session_name and not self._session_exists(session_name):  # Check tmux using session_name
                    is_stuck = True
                    logger.info(f"Project {project_id} session '{session_name}' no longer exists")
                elif not session_name and orch_session and not self._session_exists(orch_session):  # Fallback to orchestrator_session
                    is_stuck = True
                    logger.info(f"Project {project_id} orchestrator session '{orch_session}' no longer exists")
                
                if is_stuck:
                    self.mark_project_complete(project_id, success=False, error_message='Manual reset: Project appeared stuck or orphaned')
                    logger.warning(f"Reset project {project_id} to failed")
                    return True
                logger.info(f"Project {project_id} appears to be running normally")
                return False
        finally:
            project_lock.release()
    
    def detect_and_reset_phantom_projects(self) -> int:
        """
        CRITICAL: Detect and reset phantom PROCESSING projects that have no tmux sessions.
        Enhanced version with process scanning using psutil.
        
        Returns: Number of phantom projects reset
        """
        reset_count = 0
        
        with self.queue_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, project_path, orchestrator_session, main_session, started_at, spec_path
                FROM project_queue 
                WHERE status = 'processing'
            """)
            
            for row in cursor.fetchall():
                project_id, project_path, orch_session, main_session, started_at, spec_path = row
                
                # Derive project name from spec path
                project_name = None
                if spec_path:
                    project_name = Path(spec_path).stem.lower().replace('_', '-')
                
                # Skip if project just started (configurable grace period for Claude analysis)
                grace_period = self.phantom_grace_period  # Use configurable value
                
                # Handle both timestamp and datetime string formats
                if started_at:
                    if isinstance(started_at, str):
                        # Convert datetime string to timestamp
                        try:
                            from datetime import datetime
                            dt = datetime.strptime(started_at, '%Y-%m-%d %H:%M:%S')
                            started_timestamp = dt.timestamp()
                        except ValueError:
                            # Try to parse as float if it's a string representation of a number
                            try:
                                started_timestamp = float(started_at)
                            except ValueError:
                                logger.error(f"Invalid started_at format for project {project_id}: {started_at}")
                                started_timestamp = 0
                    else:
                        started_timestamp = float(started_at)
                    elapsed = time.time() - started_timestamp
                else:
                    elapsed = 0
                
                if started_at and elapsed < grace_period:
                    logger.debug(f"Project {project_id} is within grace period ({grace_period}s), skipping (elapsed: {elapsed:.0f}s)")
                    continue
                
                # Check 1: No session name set (auto_orchestrate.py failed before session creation)
                if not orch_session and not main_session:
                    # NEW: Check if process is still alive via ProcessManager before flagging
                    if self.process_manager.is_alive(project_id):
                        logger.debug(f"Project {project_id} has no session but process is alive ({elapsed:.0f}s elapsed) - skipping phantom reset")
                        continue
                    
                    # ENHANCED: Before marking as phantom, check if any session exists via pattern matching
                    logger.info(f"No session name recorded for project {project_id}, checking for active sessions via pattern matching...")
                    pattern_is_live, pattern_reason = self.validate_session_liveness(None, project_id=project_id, spec_path=spec_path)
                    if pattern_is_live:
                        logger.info(f"Found active session for project {project_id} via pattern matching - not a phantom")
                        
                        # Try to update the database with the discovered session name
                        self._attempt_session_name_recovery(cursor, project_id, spec_path)
                        continue
                    
                    if started_at and elapsed > grace_period:
                        self._reset_phantom_project(cursor, project_id, project_name or "unknown", 
                                                  reason=f"No session created after {grace_period}s (elapsed: {elapsed:.0f}s)")
                        reset_count += 1
                        logger.warning(f"Phantom reset for {project_id}: No session after {elapsed:.0f}s, no active process")
                        continue
                
                # Check 2: Session validation (with pattern matching fallback if no session name)
                session_to_check = orch_session or main_session
                if session_to_check:
                    is_live, reason = self.validate_session_liveness(session_to_check, project_id=project_id, spec_path=spec_path)
                    if not is_live:
                        self._reset_phantom_project(cursor, project_id, project_name or "unknown", reason=reason)
                        reset_count += 1
                        continue
                else:
                    # No session names recorded - try pattern matching fallback
                    is_live, reason = self.validate_session_liveness(None, project_id=project_id, spec_path=spec_path)
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
                
                # Handle both timestamp and datetime string formats for started_at
                if not is_running and started_at:
                    if isinstance(started_at, str):
                        # Convert datetime string to timestamp
                        try:
                            from datetime import datetime
                            dt = datetime.strptime(started_at, '%Y-%m-%d %H:%M:%S')
                            started_timestamp = dt.timestamp()
                        except ValueError:
                            # Try to parse as float if it's a string representation of a number
                            try:
                                started_timestamp = float(started_at)
                            except ValueError:
                                logger.error(f"Invalid started_at format for project {project_id}: {started_at}")
                                started_timestamp = 0
                    else:
                        started_timestamp = float(started_at)
                        
                    if started_timestamp and time.time() - started_timestamp > 300:  # 5 minutes
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
    
    def remove_project_from_queue(self, project_id: int) -> bool:
        """Remove a project from the queue (for completed/failed projects)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM project_queue WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        if not row:
            logger.error(f"Project {project_id} not found")
            return False
        
        status = row[0]
        if status == 'processing':
            logger.warning(f"Cannot remove project {project_id} - still processing")
            return False
        
        cursor.execute("DELETE FROM project_queue WHERE id = ?", (project_id,))
        self.conn.commit()
        logger.info(f"Removed project {project_id} from queue (was {status})")
        return cursor.rowcount > 0
    
    def _session_exists(self, session_name: str) -> bool:
        """Check if a tmux session exists"""
        try:
            result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _find_lingering_sessions(self, active_sessions: List[str]) -> List[str]:
        """Find sessions that belong to completed/failed projects but are still active"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT main_session FROM project_queue 
            WHERE status IN ('completed', 'failed') AND main_session IS NOT NULL
        """)
        completed_sessions = [row[0] for row in cursor.fetchall()]
        
        return [sess for sess in active_sessions if sess in completed_sessions]
    
    def _is_session_ready(self, session_name: str, window_index: int) -> bool:
        """Validate if session exists and is running Claude (not bash)."""
        # Check existence
        if not self._session_exists(session_name):
            logger.warning(f"Session {session_name} does not exist")
            return False
        
        # Check pane command (should not be bash/sh)
        target = f"{session_name}:{window_index}"
        try:
            result = subprocess.run(
                ['tmux', 'display-message', '-p', '-t', target, '#{pane_current_command}'],
                capture_output=True, text=True, check=True
            )
            command = result.stdout.strip().lower()
            if 'bash' in command or 'sh' in command:
                logger.warning(f"Target {target} is running {command}, not Claude")
                return False
            
            # Check if pane is active (has recent activity, to detect dead Claude)
            activity_result = subprocess.run(
                ['tmux', 'display-message', '-p', '-t', target, '#{pane_dead} #{pane_active}'],
                capture_output=True, text=True, check=True
            )
            activity = activity_result.stdout.strip().split()
            if len(activity) >= 2 and (activity[0] == '1' or activity[1] == '0'):  # Dead or inactive
                logger.warning(f"Target {target} is dead or inactive")
                return False
            
            # Note: Claude might show as 'python' or other process names
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check pane command for {target}: {e}")
            return False
    
    def get_active_tmux_sessions(self):
        """Helper to get active tmux sessions (for sequential processing check)."""
        try:
            result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'], 
                                    capture_output=True, text=True)
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            return []
        except Exception as e:
            logger.error(f"Failed to get tmux sessions: {e}")
            return []
    
    def get_next_project_atomic(self) -> Optional[Dict[str, Any]]:
        """Atomically dequeue the next project if none are processing. FIXES SEQUENTIAL PROCESSING."""
        with self.queue_lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute("BEGIN")  # Explicit transaction
                
                # NEW: Pre-dequeue cleanup - check for and clean lingering sessions
                active_sessions = self.tmux_manager.get_active_sessions()
                lingering_sessions = self._find_lingering_sessions(active_sessions)
                if lingering_sessions:
                    logger.warning(f"Found {len(lingering_sessions)} lingering sessions: {lingering_sessions}")
                    for sess in lingering_sessions:
                        if self.tmux_manager.kill_session(sess):
                            logger.info(f"Cleaned up lingering session {sess}")
                        else:
                            logger.error(f"Failed to clean up {sess} - queue may remain blocked")
                            # Optional: Abort dequeue if cleanup fails
                            # self.conn.rollback()
                            # return None
                
                # Step 1: Check if we're at the concurrency limit
                cursor.execute("SELECT COUNT(*) FROM project_queue WHERE status = 'processing'")
                active_count = cursor.fetchone()[0]
                if active_count >= self.max_concurrent:
                    logger.debug(f"Skipping dequeue: {active_count} project(s) processing (limit: {self.max_concurrent})")
                    self.conn.rollback()
                    return None

                # Step 2: Select the next highest-priority queued project
                cursor.execute("""
                    SELECT id, spec_path, project_path, batch_id, retry_count
                    FROM project_queue 
                    WHERE status = 'queued' 
                    ORDER BY priority DESC, enqueued_at ASC 
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if not row:
                    logger.debug("No queued projects available - queue is empty")
                    self.conn.rollback()
                    return None

                # Step 3: Atomically update to 'processing' (within transaction)
                project_id = row[0]
                cursor.execute("""
                    UPDATE project_queue 
                    SET status = 'processing', started_at = strftime('%s', 'now') 
                    WHERE id = ?
                """, (project_id,))
                
                self.conn.commit()  # Commit if successful
                logger.info(f"Dequeued project {project_id}")
                
                # Return project data
                return {
                    'id': row[0],
                    'spec_path': row[1], 
                    'project_path': row[2],
                    'batch_id': row[3],
                    'retry_count': row[4]
                }
            except sqlite3.OperationalError as e:
                self.conn.rollback()
                if "locked" in str(e).lower():
                    logger.warning("DB locked during dequeue; will retry later")
                    time.sleep(1)  # Simple backoff
                    return None  # Caller can retry
                raise
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Transaction failed in atomic dequeue: {e}")
                raise
    
    def mark_project_complete(self, project_id: int, success: bool = True, error_message: str = None):
        """Mark a project as completed or failed. Called by orchestration agents when work finishes."""
        try:
            cursor = self.conn.cursor()
            
            # NEW: Guard to prevent re-marking and repeated events/loops
            cursor.execute("SELECT status, main_session FROM project_queue WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if row and row[0] in ('completed', 'failed'):
                logger.debug(f"Project {project_id} already marked as {row[0]}, skipping DB update")
                # But still dispatch event for manual updates (see below)
                updated = False
            else:
                status = 'completed' if success else 'failed'
                with self.conn:  # Transaction for atomic update
                    cursor.execute("""
                        UPDATE project_queue 
                        SET status = ?, completed_at = strftime('%s', 'now'), error_message = ? 
                        WHERE id = ?
                    """, (status, error_message, project_id))
                logger.info(f"Project {project_id} marked as {status}")
                updated = True
            
            # NEW: Immediate session cleanup
            # Get session name from DB or derive from spec
            session_name = None
            if row and row[1]:  # main_session from DB
                session_name = row[1]
            else:
                # Try to get from spec_path
                cursor.execute("SELECT spec_path FROM project_queue WHERE id = ?", (project_id,))
                spec_row = cursor.fetchone()
                if spec_row and spec_row[0]:
                    project_name = Path(spec_row[0]).stem.lower().replace('_', '-')
                    # Load session state to get session_name
                    state = self.session_state_manager.load_session_state(project_name)
                    if state and state.session_name:
                        session_name = state.session_name
            
            # Kill the session if found
            if session_name:
                if self.tmux_manager.kill_session(session_name):
                    logger.info(f"Successfully killed session {session_name} for completed project {project_id}")
                    # Optional: Clean up registry immediately
                    self.session_state_manager.cleanup_stale_registries()
                else:
                    logger.warning(f"Failed to kill session {session_name} - manual cleanup needed")
            else:
                logger.warning(f"No session found for project {project_id} - skipping cleanup")
            
            # NEW: Always trigger event (even for manual re-marks), but guard against loops
            event_key = f"complete_{project_id}_{success}"
            with self._event_lock:
                if event_key not in self.processing_events:
                    self.processing_events.add(event_key)
                    try:
                        # Dispatch project completion event
                        self._dispatch_event('project_complete', {
                            'project_id': project_id,
                            'status': 'completed' if success else 'failed',
                            'error_message': error_message,
                            'manual_update': not updated
                        })
                        logger.info(f"Dispatched project_complete event for {project_id} (manual: {not updated})")
                        
                        # Also trigger task completion for monitoring (if session available)
                        if session_name:
                            self.complete_task(f"project_{project_id}", session_name, "orchestrator", 
                                             f"Project marked as {'completed' if success else 'failed'}")
                        else:
                            logger.debug(f"Skipping task completion trigger for project {project_id} - no session name")
                    finally:
                        # Remove from processing set after a delay
                        threading.Timer(1.0, lambda: self.processing_events.discard(event_key)).start()
                else:
                    logger.debug(f"Skipped duplicate event for {project_id}")
                    
        except sqlite3.Error as e:
            logger.error(f"Failed to update completion status for project {project_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error marking project {project_id} complete: {e}")
    
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
        state = self.session_state_manager.load_session_state(project_name) if project_name else None
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
    
    def _attempt_session_name_recovery(self, cursor, project_id: int, spec_path: str) -> bool:
        """
        Attempt to discover and record the session name for a project using pattern matching.
        
        Args:
            cursor: Database cursor
            project_id: Project ID 
            spec_path: Project spec path for pattern matching
        
        Returns:
            True if session name was recovered and updated, False otherwise
        """
        try:
            # Use the existing pattern matching logic to find the session
            now = int(time.time())
            grace_period_sec = 900  # 15 minutes
            
            # Call the pattern matching scan
            is_live, reason = self._scan_active_sessions_for_project(project_id, spec_path, now, grace_period_sec)
            
            if not is_live:
                logger.info(f"No active session found via pattern matching for project {project_id}: {reason}")
                return False
            
            # Extract session name from the reason message
            # The reason format is: "Found active session 'session_name' via pattern matching"
            if "Found active session" in reason and "via pattern matching" in reason:
                # Extract session name from between single quotes
                import re
                match = re.search(r"'([^']+)'", reason)
                if match:
                    discovered_session_name = match.group(1)
                    
                    # Update the database with the discovered session name
                    cursor.execute("""
                        UPDATE project_queue 
                        SET session_name = ? 
                        WHERE id = ?
                    """, (discovered_session_name, project_id))
                    
                    logger.info(f"Successfully recovered session name '{discovered_session_name}' for project {project_id}")
                    return True
                else:
                    logger.warning(f"Could not extract session name from reason: {reason}")
                    return False
            else:
                logger.warning(f"Unexpected reason format for session recovery: {reason}")
                return False
                
        except Exception as e:
            logger.error(f"Error during session name recovery for project {project_id}: {e}")
            return False
    
    def validate_session_liveness(self, session_name: str, grace_period_sec: int = 900, project_id: int = None, spec_path: str = None) -> Tuple[bool, str]:
        """Validate tmux session liveness with multiple checks and pattern matching fallback.
        
        Args:
            session_name: Tmux session name to check. If None, uses pattern matching.
            grace_period_sec: Allow recent sessions to pass even if not fully active (e.g., during startup).
            project_id: Project ID for pattern matching fallback (optional).
            spec_path: Spec path for pattern matching fallback (optional).
        
        Returns:
            (is_live, reason): True if live, else False with failure reason.
        """
        now = int(time.time())
        
        # Primary check: If we have a session name, use it directly
        if session_name and session_name.strip():
            return self._check_session_directly(session_name, now, grace_period_sec)
        
        # Fallback: Pattern matching scan for sessions when session_name is missing
        logger.info(f"Session name missing for project {project_id}, attempting pattern matching scan...")
        return self._scan_active_sessions_for_project(project_id, spec_path, now, grace_period_sec)
    
    def _check_session_directly(self, session_name: str, now: int, grace_period_sec: int) -> Tuple[bool, str]:
        """Direct session validation for known session names"""
        # Check existence
        try:
            result = subprocess.run(['tmux', 'has-session', '-t', session_name], capture_output=True)
            if result.returncode != 0:
                return False, f"Session '{session_name}' does not exist"
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
                    idle_time = now - last_active
                    # More lenient idle threshold - some sessions may be idle but still valid
                    # e.g., completed work but waiting for manual review
                    if idle_time > 7200:  # 2 hour idle threshold instead of 30min
                        return False, f"Session inactive for {idle_time//60} minutes"
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
                        return True, f"Session '{session_name}' is new and within grace period"
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
        
        return True, f"Session '{session_name}' is live"
    
    def _scan_active_sessions_for_project(self, project_id: int, spec_path: str, now: int, grace_period_sec: int) -> Tuple[bool, str]:
        """Scan all active tmux sessions looking for ones that might belong to this project"""
        try:
            # Get all active sessions
            result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}:#{session_created}'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return False, "Failed to list tmux sessions"
            
            project_keywords = []
            if spec_path:
                # Extract keywords from spec path for pattern matching
                path_parts = spec_path.lower().split('/')
                for part in path_parts:
                    # Look for relevant parts
                    if any(term in part for term in ['elliott', 'wave', 'options', 'reporting', 'backtesting']):
                        project_keywords.extend(part.split('_'))
                        project_keywords.extend(part.split('-'))
                
                # Add specific keywords based on spec name patterns
                spec_name = os.path.basename(spec_path).lower()
                if 'reporting' in spec_name:
                    project_keywords.extend(['elliott', 'wave', 'options', 'report', 'reporting', 'generation'])
                elif 'backtesting' in spec_name:
                    project_keywords.extend(['elliott', 'wave', 'backtesting', 'implementation'])
                elif 'elliott' in spec_name:
                    project_keywords.extend(['elliott', 'wave'])
            
            # Look for sessions matching project patterns
            candidate_sessions = []
            for line in result.stdout.strip().split('\n'):
                if ':' not in line:
                    continue
                    
                session_name, created_str = line.split(':', 1)
                
                # More flexible matching - check if session looks like our project sessions
                is_project_session = False
                
                # Direct impl pattern match
                if '-impl-' in session_name:
                    is_project_session = True
                
                # Keyword-based match (more flexible)
                if project_keywords and any(keyword in session_name.lower() 
                                          for keyword in project_keywords if keyword and len(keyword) > 2):
                    is_project_session = True
                
                # Elliott Wave specific patterns
                if 'elliott' in session_name.lower() and any(term in session_name.lower() 
                                                           for term in ['wave', 'options', 'report', 'backtesting']):
                    is_project_session = True
                
                if not is_project_session:
                    continue
                
                # Check if session is recent enough to be relevant
                # Be more lenient - projects can run for many hours legitimately
                try:
                    created_time = int(created_str)
                    session_age = now - created_time
                    # Only skip sessions older than 8 hours (projects can legitimately run long)
                    if session_age > 28800:  # 8 hours instead of 2 hours
                        continue
                except:
                    continue
                
                candidate_sessions.append((session_name, created_time))
            
            if not candidate_sessions:
                return False, f"No candidate sessions found for project {project_id} (keywords: {project_keywords})"
            
            # Check the most recent candidate session
            candidate_sessions.sort(key=lambda x: x[1], reverse=True)  # Sort by creation time, newest first
            best_match, _ = candidate_sessions[0]
            
            logger.info(f"Found candidate session '{best_match}' for project {project_id}")
            
            # Validate the candidate session
            is_live, reason = self._check_session_directly(best_match, now, grace_period_sec)
            
            if is_live:
                # Update database with discovered session name
                try:
                    with self.conn:
                        cursor = self.conn.cursor()
                        cursor.execute("UPDATE project_queue SET session_name = ? WHERE id = ?", 
                                     (best_match, project_id))
                        logger.info(f"Updated project {project_id} with discovered session name: {best_match}")
                except Exception as e:
                    logger.error(f"Failed to update discovered session name: {e}")
                
                return True, f"Found active session '{best_match}' via pattern matching"
            else:
                return False, f"Candidate session '{best_match}' failed validation: {reason}"
                
        except Exception as e:
            return False, f"Pattern matching scan failed: {e}"
    
    def _recover_from_reboot(self):
        """Recover from system reboot by checking status of projects that were processing"""
        logger.info("🔄 Starting reboot recovery check...")
        
        try:
            with self.queue_lock:
                cursor = self.conn.cursor()
                
                # Find all projects that were marked as processing
                cursor.execute("""
                    SELECT id, spec_path, project_path, session_name, started_at
                    FROM project_queue 
                    WHERE status IN ('processing', 'credit_paused')
                    ORDER BY id
                """)
                
                processing_projects = cursor.fetchall()
                
                if not processing_projects:
                    logger.info("No projects found in processing state - clean startup")
                    return
                
                logger.info(f"Found {len(processing_projects)} projects in processing/credit_paused state")
                
                # Initialize state synchronizer for null session name repairs
                synchronizer = StateSynchronizer(self.db_path, "registry")
                
                for project_id, spec_path, project_path, session_name, started_at in processing_projects:
                    logger.info(f"Checking project {project_id} (session: {session_name})")
                    
                    # NEW: Proactive repair for null session names
                    if not session_name:
                        logger.warning(f"Null session_name detected for project {project_id} - attempting repair")
                        max_attempts = 3
                        repaired = False
                        
                        for attempt in range(max_attempts):
                            logger.info(f"Repair attempt {attempt+1}/{max_attempts} for project {project_id}")
                            
                            try:
                                if synchronizer.repair_missing_session_name(project_id):
                                    # Refresh session_name after repair
                                    cursor.execute("SELECT session_name FROM project_queue WHERE id = ?", (project_id,))
                                    result = cursor.fetchone()
                                    if result and result[0]:
                                        session_name = result[0]
                                        logger.info(f"✅ Repaired null session for project {project_id}: {session_name}")
                                        repaired = True
                                        break
                                    else:
                                        logger.warning(f"Repair returned success but session_name still null for project {project_id}")
                                else:
                                    logger.warning(f"Repair failed for project {project_id} on attempt {attempt+1}")
                            except Exception as e:
                                logger.error(f"Error during repair attempt {attempt+1} for project {project_id}: {e}")
                            
                            if attempt < max_attempts - 1:  # Don't sleep after last attempt
                                time.sleep(1)  # Backoff between attempts
                        
                        if not repaired and not session_name:
                            # Mark as failed if unrepairable after all attempts
                            logger.error(f"❌ Failed to repair null session for project {project_id} after {max_attempts} attempts")
                            cursor.execute("""
                                UPDATE project_queue 
                                SET status = 'failed', 
                                    error_message = 'Unrecoverable null session name after reboot - repair failed',
                                    completed_at = strftime('%s', 'now')
                                WHERE id = ?
                            """, (project_id,))
                            logger.error(f"Marked project {project_id} as failed due to unrecoverable null session name")
                            continue  # Skip further processing for this project
                    
                    # Check if the tmux session still exists
                    session_exists = False
                    if session_name:
                        try:
                            result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                                                  capture_output=True)
                            session_exists = result.returncode == 0
                        except Exception as e:
                            logger.error(f"Error checking session {session_name}: {e}")
                    
                    # Also try pattern matching if session_name is missing
                    if not session_exists and spec_path:
                        is_live, reason = self.validate_session_liveness(
                            None, 
                            project_id=project_id, 
                            spec_path=spec_path
                        )
                        session_exists = is_live
                        if is_live:
                            logger.info(f"Found active session for project {project_id} via pattern matching")
                    
                    if session_exists:
                        # Session still exists - project may still be running
                        logger.info(f"✅ Project {project_id} session still active - keeping as processing")
                        
                        # Check if it was credit_paused and might need to be resumed
                        cursor.execute("SELECT status FROM project_queue WHERE id = ?", (project_id,))
                        status = cursor.fetchone()[0]
                        
                        if status == 'credit_paused':
                            # Check if credits might be available now
                            logger.info(f"Project {project_id} was credit_paused - will be checked by credit monitor")
                    else:
                        # Session doesn't exist - likely terminated during reboot
                        logger.warning(f"❌ Project {project_id} session not found after reboot")
                        
                        # Check if there's completion information in SessionState
                        project_name = None
                        if spec_path:
                            project_name = Path(spec_path).stem.lower().replace('_', '-')
                        
                        completion_detected = False
                        if project_name:
                            state = self.session_state_manager.load_session_state(project_name)
                            if state and state.completion_status in ['completed', 'failed']:
                                # Project actually completed before reboot
                                logger.info(f"Project {project_id} found {state.completion_status} in SessionState")
                                cursor.execute("""
                                    UPDATE project_queue 
                                    SET status = ?, 
                                        completed_at = strftime('%s', 'now'),
                                        error_message = ?
                                    WHERE id = ?
                                """, (state.completion_status, state.failure_reason, project_id))
                                completion_detected = True
                        
                        if not completion_detected:
                            # Mark as failed due to reboot
                            cursor.execute("""
                                UPDATE project_queue 
                                SET status = 'failed', 
                                    completed_at = strftime('%s', 'now'),
                                    error_message = 'Project terminated during system reboot/shutdown'
                                WHERE id = ?
                            """, (project_id,))
                            logger.info(f"Marked project {project_id} as failed due to reboot")
                
                self.conn.commit()
                logger.info("✅ Reboot recovery completed")
                
        except Exception as e:
            logger.error(f"Error during reboot recovery: {e}", exc_info=True)
    
    def _dispatch_event(self, event: str, data: Dict[str, Any]):
        """Dispatch an event to all subscribers"""
        for callback in self.event_subscribers.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in event callback {callback.__name__}: {e}")
    
    def process_signal_files(self) -> int:
        """Process signal files for reset operations"""
        processed = 0
        signal_dir = Path('signals')
        if not signal_dir.exists():
            return 0
        
        for signal_file in signal_dir.glob('reset_project_*.signal'):
            try:
                with open(signal_file, 'r') as f:
                    import json
                    signal_data = json.loads(f.read())
                
                project_id = signal_data['project_id']
                logger.info(f"Processing reset signal for project {project_id}")
                
                # Process the reset
                success = self.reset_project_to_queued(project_id)
                if success:
                    logger.info(f"Successfully reset project {project_id} via signal")
                    processed += 1
                else:
                    logger.error(f"Failed to reset project {project_id} via signal")
                
                # Remove processed signal file
                signal_file.unlink()
                
            except Exception as e:
                logger.error(f"Error processing signal file {signal_file}: {e}")
                # Remove corrupted signal file
                try:
                    signal_file.unlink()
                except:
                    pass
        
        return processed

    def detect_completed_projects(self):
        """Sync completion status from SessionState to project_queue."""
        with self.queue_lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, project_path, spec_path FROM project_queue WHERE status = 'processing'")
            
            for row in cursor.fetchall():
                project_id, project_path, spec_path = row
                
                # Derive project name from spec path
                project_name = None
                if spec_path:
                    project_name = Path(spec_path).stem.lower().replace('_', '-')
                
                if not project_name:
                    continue
                    
                state = self.session_state_manager.load_session_state(project_name)
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
        
    def setup_database(self):
        """Initialize SQLite database for persistent task storage"""
        self.conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Enable WAL mode for better concurrency (multiple readers, single writer)
        cursor.execute("PRAGMA journal_mode=WAL;")
        journal_mode = cursor.fetchone()[0]
        if journal_mode != 'wal':
            raise RuntimeError(f"Failed to enable WAL mode: current mode is {journal_mode}")
        
        cursor.execute("PRAGMA busy_timeout=10000;")  # 10 second timeout for locks
        cursor.execute("PRAGMA synchronous=NORMAL;")  # Better performance with WAL
        
        # Log for debugging
        logger.info(f"Database initialized in {journal_mode} mode with busy_timeout=10000")
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                window_index INTEGER NOT NULL,
                next_run REAL NOT NULL,
                interval_minutes INTEGER NOT NULL,
                note TEXT,
                last_run REAL,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3
            )
        ''')
        # New table for project queue
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS project_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spec_path TEXT NOT NULL,
                project_path TEXT,  -- Can be null if auto-detected
                status TEXT DEFAULT 'queued',  -- queued, processing, completed, failed, retried, permanently_failed, credit_paused
                enqueued_at REAL DEFAULT (strftime('%s', 'now')),
                started_at REAL,
                completed_at REAL,
                priority INTEGER DEFAULT 0,  -- Higher = sooner
                error_message TEXT,
                batch_id TEXT,  -- Groups related projects for batch processing
                retry_count INTEGER DEFAULT 0,  -- Number of retry attempts
                enhanced_spec_path TEXT,  -- Path to research-enhanced spec for retries
                orchestrator_session TEXT,  -- Session running auto_orchestrate.py
                main_session TEXT  -- Main project session created by orchestration
            )
        ''')
        
        # Create unique index to prevent duplicate active projects
        try:
            self.conn.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_project 
                ON project_queue(spec_path, project_path) 
                WHERE status IN ('queued', 'processing')
            ''')
        except sqlite3.OperationalError as e:
            logger.debug(f"Index already exists or not supported: {e}")
        
        # Add batch retry system columns to existing table
        try:
            self.conn.execute('ALTER TABLE project_queue ADD COLUMN batch_id TEXT;')
            self.conn.execute('ALTER TABLE project_queue ADD COLUMN retry_count INTEGER DEFAULT 0;')
            self.conn.execute('ALTER TABLE project_queue ADD COLUMN enhanced_spec_path TEXT;')
            self.conn.execute('ALTER TABLE project_queue ADD COLUMN orchestrator_session TEXT;')
            self.conn.execute('ALTER TABLE project_queue ADD COLUMN main_session TEXT;')
        except sqlite3.OperationalError:
            pass  # Columns already exist
        
        # Add indexes for performance
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_project_queue_status ON project_queue(status);')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_project_queue_priority ON project_queue(priority, enqueued_at);')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_project_queue_batch ON project_queue(batch_id);')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_project_queue_retry ON project_queue(retry_count);')
        self.conn.commit()
        logger.info("Database initialized")
        
    def enqueue_task(self, session_name, agent_role, window_index, interval_minutes, note="", task_type="standard"):
        """Add a task to the scheduler queue with idempotent behavior to prevent loops"""
        import hashlib
        
        # Create composite key for deduplication
        note_hash = hashlib.md5(note.encode()).hexdigest()[:8]
        task_key = f"{session_name}:{agent_role}:{task_type}:{note_hash}"
        
        # Check for recent duplicates (within 10 minutes)
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, next_run FROM tasks 
            WHERE session_name = ? AND agent_role = ? AND window_index = ? 
            AND note LIKE ? AND next_run > ? AND next_run < ?
            ORDER BY next_run DESC LIMIT 1
        """, (session_name, agent_role, window_index, f"%{note[:20]}%", 
              time.time() - 600, time.time() + 3600))  # Check past 10min to future 1hr
        
        existing = cursor.fetchone()
        if existing:
            logger.warning(f"Duplicate task detected (loop prevention): {task_key}")
            logger.warning(f"Existing task ID: {existing[0]}, scheduled for: {datetime.fromtimestamp(existing[1])}")
            return existing[0]  # Return existing task ID instead of creating duplicate
        
        # Calculate next run time
        next_run = time.time() + (interval_minutes * 60)
        
        # Insert the new task
        try:
            cursor.execute("""
                INSERT INTO tasks (session_name, agent_role, window_index, next_run, interval_minutes, note)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_name, agent_role, window_index, next_run, interval_minutes, note))
            self.conn.commit()
            task_id = cursor.lastrowid
            logger.info(f"Enqueued task {task_id} for {session_name}:{window_index} ({agent_role}) - {note}")
            
            # Dispatch event for new task
            if hasattr(self, '_dispatch_event'):
                self._dispatch_event('task_added', {
                    'task_id': task_id,
                    'session': session_name,
                    'role': agent_role,
                    'scheduled_time': next_run
                })
            
            return task_id
        except Exception as e:
            logger.error(f"Failed to add task: {e}")
            self.conn.rollback()
            return None
        
    def get_agent_credit_status(self, project_name, agent_role):
        """Check if agent is credit exhausted from session state"""
        try:
            state = self.session_state_manager.load_session_state(project_name)
            if state and agent_role in state.agents:
                agent = state.agents[agent_role]
                return {
                    'exhausted': agent.is_exhausted,
                    'reset_time': agent.credit_reset_time,
                    'alive': agent.is_alive
                }
        except Exception as e:
            logger.error(f"Error checking credit status: {e}")
        return {'exhausted': False, 'reset_time': None, 'alive': True}
    
    def subscribe(self, event: str, callback: Callable):
        """Subscribe a callback to an event"""
        self.event_subscribers.setdefault(event, []).append(callback)
        logger.info(f"Subscribed {callback.__name__} to event '{event}'")
    
    def complete_task(self, task_id: int, session_name: str, agent_role: str, completion_message: str = ""):
        """Mark task as complete and trigger completion hooks with re-entrance protection"""
        # NEW: Re-entrance guard to prevent notification loops
        task_key = f"{task_id}_{session_name}_{agent_role}"
        with self._event_lock:
            if task_key in self.processing_events:
                logger.warning(f"Skipping recursive/re-entrant event for task {task_key} to prevent notification loop")
                return
            self.processing_events.add(task_key)
            
            try:
                now = time.time()
                self.conn.execute("UPDATE tasks SET last_run = ? WHERE id = ?", (now, task_id))
                self.conn.commit()
                
                # Extract project name from session name
                project_name = session_name.split('-impl')[0].replace('-', ' ').title()
                
                # Update session state
                state = self.session_state_manager.load_session_state(project_name)
                if state and agent_role.lower() in state.agents:
                    agent = state.agents[agent_role.lower()]
                    agent.last_check_in_time = datetime.now().isoformat()
                    self.session_state_manager.save_session_state(state)
                    logger.info(f"Updated session state for {agent_role}")
                
                # Trigger event subscribers
                for callback in self.event_subscribers.get('task_complete', []):
                    try:
                        callback(task_id, session_name, agent_role, completion_message)
                    except Exception as e:
                        logger.error(f"Error in event callback {callback.__name__}: {e}")
            finally:
                self.processing_events.remove(task_key)
    
    def _handle_task_completion(self, task_id: int, session_name: str, agent_role: str, completion_message: str):
        """Default handler: Force agent to report to Orchestrator via tmux injection"""
        try:
            # CRITICAL FIX: Prevent orchestrator tasks from creating more orchestrator tasks (infinite loop)
            if agent_role.lower() == 'orchestrator':
                logger.debug(f"Skipping completion report for orchestrator task {task_id} to prevent infinite loop")
                return
                
            # Find agent's window from state
            project_name = session_name.split('-impl')[0].replace('-', ' ').title()
            state = self.session_state_manager.load_session_state(project_name)
            
            if not state or agent_role.lower() not in state.agents:
                logger.warning(f"Cannot find agent {agent_role} in state")
                return
                
            window_index = state.agents[agent_role.lower()].window_index
            
            # FIX: Construct fresh report message (no appending to prevent accumulation)
            if not completion_message or "Agent orchestrator completed:" in completion_message:
                # Use fresh message if empty or if it already contains accumulated text
                fresh_completion_message = f"Task {task_id} completed successfully"
            else:
                fresh_completion_message = completion_message
            
            report_prompt = f"IMPORTANT: Report to Orchestrator (window 0) - {fresh_completion_message}"
            
            # Inject into agent's tmux window to prompt Claude to report
            cmd = ['tmux', 'send-keys', '-t', f'{session_name}:{window_index}', report_prompt, 'C-m']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Injected completion report prompt to {session_name}:{window_index} ({agent_role})")
                
                # FIX: Also schedule an immediate check-in for Orchestrator with FRESH note (no accumulation)
                orchestrator_note = f"Agent {agent_role} completed: {fresh_completion_message}"
                self.enqueue_task(session_name, 'orchestrator', 0, 0, orchestrator_note)
            else:
                logger.error(f"Failed to inject completion message: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error in completion handler: {e}")
    
    def trigger_event(self, event_name: str, data: Dict[str, Any]):
        """Trigger an event with data for all subscribers with rate limiting and deduplication"""
        import hashlib
        
        # Rate limiting - enforce minimum interval between events
        current_time = time.time()
        if hasattr(self, '_last_event_time'):
            time_since_last = current_time - self._last_event_time
            if time_since_last < 0.5:  # 500ms minimum between events
                time.sleep(0.5 - time_since_last)
                current_time = time.time()
        self._last_event_time = current_time
        
        # Deduplication - skip duplicate events
        event_hash = hashlib.md5(f"{event_name}:{json.dumps(data, sort_keys=True)}".encode()).hexdigest()
        if not hasattr(self, '_event_history'):
            self._event_history = collections.deque(maxlen=100)
        
        if event_hash in self._event_history:
            logger.warning(f"Skipping duplicate event: {event_name} - {data}")
            return
            
        self._event_history.append(event_hash)
        
        # Trigger subscribers
        for subscriber in self.event_subscribers.get(event_name, []):
            try:
                subscriber(data)
            except Exception as e:
                logger.error(f"Error in event subscriber for {event_name}: {e}")
        
    def run_task(self, task_id, session_name, agent_role, window_index, note):
        """Execute a scheduled task with verification"""
        try:
            import shlex
            
            # NEW: Validate session before sending
            if not self._is_session_ready(session_name, window_index):
                logger.warning(f"Skipping task {task_id}: Session {session_name}:{window_index} not ready")
                return False  # Will trigger retry logic
            
            # Extract project name from session name (format: project-impl-uuid)
            project_name = session_name.split('-impl')[0]
            
            # Check credit status
            credit_status = self.get_agent_credit_status(project_name, agent_role)
            
            if credit_status['exhausted']:
                logger.warning(f"Agent {agent_role} is credit exhausted, deferring task")
                # Exponential backoff: double the interval
                cursor = self.conn.cursor()
                cursor.execute("""
                    UPDATE tasks 
                    SET interval_minutes = interval_minutes * 2,
                        next_run = ?,
                        note = ?
                    WHERE id = ?
                """, (time.time() + 3600, f"{note} (credit backoff)", task_id))
                self.conn.commit()
                return False
                
            if not credit_status['alive']:
                logger.warning(f"Agent {agent_role} appears dead, attempting restart")
                # Could implement agent restart logic here
                
            # Build the command to send to the agent
            if note:
                message = f"SCHEDULED CHECK-IN: {note}"
            else:
                message = "SCHEDULED CHECK-IN: Time for your regular status update"
            
            # Target window for tmux commands
            target_window = f"{session_name}:{window_index}"
            
            # Capture before state
            cmd_capture_before = f"tmux capture-pane -t {target_window} -p | tail -20"
            result_before = subprocess.run(cmd_capture_before, shell=True, capture_output=True, text=True)
            before_content = result_before.stdout if result_before.returncode == 0 else ""
            
            # Send message using send-claude-message.sh script if available
            send_script = self.tmux_orchestrator_path / "send-claude-message.sh"
            if send_script.exists():
                cmd = [str(send_script), target_window, message]
                result_send = subprocess.run(cmd, capture_output=True, text=True)
            else:
                # Fallback to direct tmux send-keys
                # First send the message
                cmd_msg = ['tmux', 'send-keys', '-t', target_window, message]
                result_msg = subprocess.run(cmd_msg, capture_output=True, text=True)
                # Then send Enter key (C-m)
                cmd_enter = ['tmux', 'send-keys', '-t', target_window, 'C-m']
                result_enter = subprocess.run(cmd_enter, capture_output=True, text=True)
                # Combine results
                result_send = result_msg
                if result_msg.returncode != 0 or result_enter.returncode != 0:
                    result_send.returncode = 1
                    result_send.stderr = (result_msg.stderr or '') + (result_enter.stderr or '')
            
            if result_send.returncode != 0:
                logger.error(f"Failed to send message to {target_window}: {result_send.stderr}")
                return False
            
            # Wait and verify
            time.sleep(3)
            
            cmd_capture_after = f"tmux capture-pane -t {target_window} -p | tail -20"
            result_after = subprocess.run(cmd_capture_after, shell=True, capture_output=True, text=True)
            after_content = result_after.stdout if result_after.returncode == 0 else ""
            
            # Check if content changed
            if before_content == after_content:
                logger.warning(f"WARNING: No response detected from {target_window} - message may not have been received")
                return False
            
            logger.info(f"✓ Message verified as delivered to {target_window} for task {task_id}")
            # Trigger completion event with the note as completion message
            self.complete_task(task_id, session_name, agent_role, note)
            return True
                
        except Exception as e:
            logger.error(f"Error running task {task_id}: {e}")
            return False
            
    def check_and_run_tasks(self):
        """Check for due tasks and run them"""
        now = time.time()
        cursor = self.conn.cursor()
        
        # Get all tasks that are due
        cursor.execute("""
            SELECT id, session_name, agent_role, window_index, next_run, 
                   interval_minutes, note, last_run, retry_count
            FROM tasks 
            WHERE next_run <= ?
            ORDER BY next_run
        """, (now,))
        
        for row in cursor.fetchall():
            task_id, session_name, agent_role, window_index, next_run, \
            interval_minutes, note, last_run, retry_count = row
            
            # NEW: Check retry cap before attempting
            max_retries = int(os.getenv('MAX_TASK_RETRIES', 5))  # Configurable via env var
            if retry_count >= max_retries:
                logger.error(f"Task {task_id} exceeded max retries ({retry_count}/{max_retries}) - disabling permanently")
                self.conn.execute("""
                    UPDATE tasks 
                    SET next_run = ?, retry_count = -1  -- Negative indicates permanent failure
                    WHERE id = ?
                """, (time.time() + 31536000, task_id))  # 1 year in future
                continue  # Skip this task
            
            # Check if task was missed (overdue by more than 2x interval)
            if last_run and (now - last_run) > (interval_minutes * 60 * 2):
                logger.warning(f"Task {task_id} was missed, recovering...")
                
            # Run the task
            success = self.run_task(task_id, session_name, agent_role, window_index, note)
            
            if success:
                # Skip rescheduling if interval_minutes == 0 (one-time task)
                if interval_minutes == 0:
                    logger.info(f"Task {task_id} has interval_minutes=0; not rescheduling (one-time task)")
                    # NEW: Delete completed one-time tasks instead of deferring
                    self.remove_task(task_id)
                    logger.info(f"Task {task_id} completed and removed (one-time task)")
                else:
                    # Reschedule for next interval
                    next_run = now + (interval_minutes * 60)
                    self.conn.execute("""
                        UPDATE tasks 
                        SET next_run = ?, retry_count = 0 
                        WHERE id = ?
                    """, (next_run, task_id))
            else:
                # Increment retry count
                self.conn.execute("""
                    UPDATE tasks 
                    SET retry_count = retry_count + 1,
                        next_run = ?
                    WHERE id = ?
                """, (now + 300, task_id))  # Retry in 5 minutes
                
        self.conn.commit()
        
    def remove_task(self, task_id):
        """Remove a task from the queue"""
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
        logger.info(f"Removed task {task_id}")
        
    def list_tasks(self):
        """List all scheduled tasks"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, session_name, agent_role, window_index, 
                   datetime(next_run, 'unixepoch', 'localtime') as next_run_time,
                   interval_minutes, note
            FROM tasks
            ORDER BY next_run
        """)
        return cursor.fetchall()
        
    def cleanup_old_tasks(self, days=7):
        """Remove tasks older than specified days with no session"""
        cutoff = time.time() - (days * 24 * 3600)
        self.conn.execute("""
            DELETE FROM tasks 
            WHERE created_at < ? AND last_run IS NULL
        """, (cutoff,))
        self.conn.commit()
        
    def enqueue_project(self, spec_path: str, project_path: Optional[str] = None, priority: int = 0):
        """Enqueue a project for batch processing"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO project_queue (spec_path, project_path, priority)
            VALUES (?, ?, ?)
        """, (spec_path, project_path, priority))
        self.conn.commit()
        task_id = cursor.lastrowid
        logger.info(f"Enqueued project {task_id} with spec {spec_path}")
        return task_id

    def get_next_project(self) -> Optional[Dict[str, Any]]:
        """Get the next queued project, ordered by priority and enqueue time"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM project_queue
            WHERE status = 'queued'
            ORDER BY priority DESC, enqueued_at ASC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return dict(zip([col[0] for col in cursor.description], row))
        return None

    def update_project_status(self, project_id: int, status: str, error_message: Optional[str] = None):
        """Update the status of a queued project"""
        now = time.time()
        cursor = self.conn.cursor()
        if status == 'processing':
            cursor.execute("UPDATE project_queue SET status = ?, started_at = ? WHERE id = ?", (status, now, project_id))
        elif status in ('completed', 'failed'):
            cursor.execute("UPDATE project_queue SET status = ?, completed_at = ?, error_message = ? WHERE id = ?", (status, now, error_message, project_id))
        else:
            cursor.execute("UPDATE project_queue SET status = ? WHERE id = ?", (status, project_id))
        self.conn.commit()
        logger.info(f"Updated project {project_id} to status: {status}")
    
    def has_active_orchestrations(self):
        """Check if there are any active orchestrations"""
        try:
            from concurrent_orchestration import ConcurrentOrchestrationManager
            logger.debug(f"Using tmux_orchestrator_path: {self.tmux_orchestrator_path}")
            logger.debug(f"Path type: {type(self.tmux_orchestrator_path)}")
            logger.debug(f"Path exists: {self.tmux_orchestrator_path.exists()}")
            
            manager = ConcurrentOrchestrationManager(self.tmux_orchestrator_path)
            all_orchestrations = manager.list_active_orchestrations()
            logger.debug(f"All orchestrations found: {len(all_orchestrations)}")
            
            for i, orch in enumerate(all_orchestrations):
                logger.debug(f"Orchestration {i}: {orch}")
            
            # First check JSON-based active orchestrations
            json_based_active = sum(1 for orch in all_orchestrations if orch.get('active'))
            
            # If no JSON-based active orchestrations, check tmux sessions as fallback
            if json_based_active == 0:
                logger.info(f"No JSON-based active orchestrations found, checking tmux sessions")
                try:
                    tmux_result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name} #{session_activity}'],
                                               capture_output=True, text=True)
                    if tmux_result.returncode == 0:
                        live_sessions = {}
                        for line in tmux_result.stdout.strip().split('\n'):
                            if ' ' in line:
                                parts = line.split(' ', 1)
                                name = parts[0].strip()
                                try:
                                    live_sessions[name] = int(parts[1].strip())
                                except (ValueError, IndexError):
                                    continue
                        
                        logger.debug(f"Found {len(live_sessions)} tmux sessions: {list(live_sessions.keys())}")
                        
                        # Cross-reference: If registry has entry and tmux session exists with recent activity (<6 hours old)
                        now = int(time.time())
                        matches_found = 0
                        for orch in all_orchestrations:
                            session_name = orch.get('session_name')
                            if session_name in live_sessions:
                                last_active = live_sessions[session_name]
                                age_seconds = now - last_active
                                logger.debug(f"Checking session {session_name}: age={age_seconds}s, threshold=21600s")
                                if age_seconds < 21600:  # 6 hour threshold
                                    orch['active'] = True  # Force active
                                    matches_found += 1
                                    logger.info(f"Marked {session_name} as active via tmux fallback (last activity: {age_seconds}s ago)")
                                else:
                                    logger.debug(f"Session {session_name} too old: {age_seconds}s > 21600s")
                        
                        if matches_found == 0:
                            logger.warning(f"No matches found between {len(all_orchestrations)} orchestrations and {len(live_sessions)} tmux sessions")
                
                except Exception as e:
                    logger.warning(f"tmux fallback failed: {e}")
            
            # Re-count after potential tmux fallback updates
            active_count = sum(1 for orch in all_orchestrations if orch.get('active'))
            logger.info(f"Found {active_count} active orchestrations out of {len(all_orchestrations)} total")
            
            if active_count == 0:
                logger.info(f"No active orchestrations found (checked {len(all_orchestrations)} total)")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking active orchestrations: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Conservative approach: assume active if we can't check
            return True
    
    def run_queue_daemon(self, poll_interval: int = 60, send_batch_summary: bool = True):
        """Daemon loop to process the project queue one at a time"""
        logger.info("Starting project queue daemon")
        # Import here to avoid circular dependency
        from concurrent_orchestration import FileLock
        
        # Initialize email notifier
        email_notifier = get_email_notifier()
        
        # Track batch processing stats
        batch_start_time = time.time()
        completed_projects = []
        failed_projects = []
        
        while True:
            try:
                # NEW: Proactive cleanup of lingering sessions from completed projects
                active_sessions = self.tmux_manager.get_active_sessions()
                lingering_sessions = self._find_lingering_sessions(active_sessions)
                if lingering_sessions:
                    logger.warning(f"Daemon cleanup: Found {len(lingering_sessions)} lingering sessions")
                    for sess in lingering_sessions:
                        if self.tmux_manager.kill_session(sess):
                            logger.info(f"Daemon cleaned up {sess}")
                
                # Check for stuck projects and auto-reset them
                # NOTE: Process already holds lock via _acquire_process_lock(), no additional FileLock needed
                self.check_stuck_projects()
                
                # CRITICAL: Check for phantom PROCESSING projects and reset them
                phantom_count = self.detect_and_reset_phantom_projects()
                if phantom_count > 0:
                    logger.warning(f"Detected and reset {phantom_count} phantom projects")
                
                # CRITICAL: Check for active orchestrations before processing ANY queued project
                logger.debug("Checking for active orchestrations before processing queue...")
                active_check = self.has_active_orchestrations()
                logger.info(f"Active orchestration check result: {active_check}")
                if active_check:
                    logger.info("Active orchestrations detected - waiting before processing queue...")
                    time.sleep(poll_interval)  # Wait before retrying
                    continue
                
                # FIXED: Use atomic dequeue to ensure only one project processes at a time
                next_project = self.get_next_project_atomic()
                if next_project:
                    project_start_time = time.time()
                    # Project is already marked as 'processing' by atomic method
                    
                    # Extract project name from spec path
                    spec_path = Path(next_project['spec_path'])
                    project_name = spec_path.stem
                    
                    try:
                        # Prepare project_path arg ('auto' if None)
                        proj_arg = next_project['project_path'] or 'auto'
                        
                        # NEW: Enhanced default resume mode - always attempt auto-resume first
                        logger.info(f"Checking for existing orchestration to resume for {project_name}")
                        should_resume = self._attempt_auto_resume(proj_arg, next_project['spec_path'])
                        
                        if should_resume:
                            logger.info(f"✅ Default resume mode: Found existing healthy orchestration for {project_name} - will resume")
                        else:
                            if proj_arg != 'auto':
                                logger.info(f"No existing/healthy orchestration found for {project_name} - will create new")
                            else:
                                logger.info(f"Auto-detect mode for {project_name} - will create new orchestration")
                        
                        # Override resume decision only if fresh_start is explicitly requested
                        if next_project.get('fresh_start', False):
                            should_resume = False
                            logger.info(f"Fresh start requested for {project_name} - overriding resume mode")
                        
                        # Build command - FIXED: Call auto_orchestrate.py directly to avoid nested uv execution
                        # The script has shebang #!/usr/bin/env -S uv run --quiet --script
                        cmd = [
                            str(self.tmux_orchestrator_path / 'auto_orchestrate.py'),
                            '--spec', next_project['spec_path'],
                            '--project', proj_arg,
                            '--project-id', str(next_project['id']),  # FIXED: Pass project ID for completion callback
                            '--batch',  # Enable non-interactive mode (now works with --project-id fix)
                            '--daemon',  # Force unattended mode with auto-defaults
                        ]
                        
                        # Add resume flag only if we determined we should resume
                        if should_resume:
                            cmd.append('--resume')
                            logger.info(f"Adding --resume flag for existing project {project_name}")
                        
                        # Add --overwrite flag if this is a fresh start request (only for new projects)
                        if next_project.get('fresh_start', False) and not should_resume:
                            cmd.append('--overwrite')
                            logger.info(f"Adding --overwrite flag for fresh start project {project_name}")
                        # NEW: Use ProcessManager for non-blocking subprocess execution with timeout enforcement
                        logger.info(f"Starting auto_orchestrate.py for project {next_project['id']}: {' '.join(cmd)}")
                        
                        # Create logs directory if needed
                        logs_dir = self.tmux_orchestrator_path / 'logs' / 'auto_orchestrate'
                        logs_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Create log file for this project
                        log_file = logs_dir / f"project_{next_project['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                        
                        # Use Popen for non-blocking execution with output capture
                        with open(log_file, 'w') as log_handle:
                            log_handle.write(f"=== auto_orchestrate.py output for Project {next_project['id']} ===\n")
                            log_handle.write(f"Command: {' '.join(cmd)}\n")
                            log_handle.write(f"Started at: {datetime.now()}\n")
                            log_handle.write("=" * 80 + "\n\n")
                            log_handle.flush()
                            
                            process = subprocess.Popen(
                                cmd, 
                                stdout=log_handle, 
                                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                                text=True,
                                cwd=str(self.tmux_orchestrator_path)
                            )
                        
                        logger.info(f"auto_orchestrate.py output for project {next_project['id']} will be logged to: {log_file}")
                        
                        # Register process with ProcessManager for monitoring
                        cmd_str = ' '.join(cmd[-4:])  # Last 4 args for logging
                        self.process_manager.register(
                            project_id=next_project['id'],
                            pid=process.pid,
                            cmd=f"auto_orchestrate.py {cmd_str}"
                        )
                        
                        logger.info(f"Registered process {process.pid} for project {next_project['id']} with ProcessManager")
                        
                        # Wait for completion with periodic heartbeat
                        start_time = time.time()
                        
                        while True:
                            # Check if process completed
                            poll_result = process.poll()
                            if poll_result is not None:
                                # Process completed
                                logger.info(f"auto_orchestrate.py completed for project {next_project['id']} with exit code {poll_result}")
                                
                                # Log file has captured all output
                                if poll_result != 0:
                                    logger.error(f"auto_orchestrate.py failed for project {next_project['id']}. Check log file: {log_file}")
                                    # Read last 200 lines from log for error context
                                    try:
                                        with open(log_file, 'r') as f:
                                            lines = f.readlines()
                                            last_lines = ''.join(lines[-200:])
                                            logger.debug(f"Last 200 lines of output:\n{last_lines}")
                                    except:
                                        pass
                                    raise subprocess.CalledProcessError(poll_result, cmd, output=str(log_file))
                                    
                                break
                            
                            # Check if ProcessManager killed the process (timeout)
                            if not self.process_manager.is_alive(next_project['id']):
                                logger.error(f"ProcessManager terminated process for project {next_project['id']} (likely timeout)")
                                try:
                                    process.terminate()
                                    process.wait(timeout=5)
                                except:
                                    process.kill()
                                raise subprocess.TimeoutExpired(cmd, self.process_manager.max_runtime)
                            
                            # Update heartbeat and sleep
                            self.process_manager.update_heartbeat(next_project['id'])
                            time.sleep(5)  # Check every 5 seconds
                        
                        # Create result object similar to subprocess.run
                        class ProcessResult:
                            def __init__(self, returncode, stdout="", stderr=""):
                                self.returncode = returncode
                                self.stdout = stdout
                                self.stderr = stderr
                        
                        result = ProcessResult(poll_result)
                        if result.stderr:
                            logger.warning(f"STDERR: {result.stderr[:500]}")
                        
                        # CRITICAL: Validate that auto_orchestrate.py actually created a tmux session
                        # Wait up to 30 seconds for session creation, then verify
                        session_validated = False
                        for attempt in range(6):  # 6 attempts, 5 seconds each = 30 seconds total
                            time.sleep(5)
                            
                            # Check if any new tmux sessions were created with project-related names
                            try:
                                session_check = subprocess.run(['tmux', 'list-sessions'], 
                                                             capture_output=True, text=True)
                                if session_check.returncode == 0:
                                    sessions = session_check.stdout
                                    # Look for sessions containing the project name or spec keywords
                                    project_keywords = [project_name.lower(), 'tmux-orchestrator', 'impl']
                                    if any(keyword in sessions.lower() for keyword in project_keywords):
                                        session_validated = True
                                        logger.info(f"Session validation SUCCESS for project {next_project['id']}")
                                        break
                            except Exception as e:
                                logger.warning(f"Session validation error: {e}")
                        
                        if not session_validated:
                            # Session creation failed - mark project as failed immediately
                            error_msg = "auto_orchestrate.py completed but no tmux session was created"
                            self.update_project_status(next_project['id'], 'failed', error_msg)
                            logger.error(f"SESSION VALIDATION FAILED for project {next_project['id']}: {error_msg}")
                            failed_projects.append(f"{project_name} (ID: {next_project['id']}) - Session Creation Failed")
                            continue
                        
                        # FIXED: Keep project in 'processing' until actual orchestration work completes
                        # Project remains 'processing' - will be marked 'completed' by orchestration agents
                        logger.info(f"Started project {next_project['id']} - orchestration setup and session validation completed")
                        
                        # Track started (not completed yet)
                        completed_projects.append(f"{project_name} (ID: {next_project['id']}) - Setup Complete")
                        
                        # Send individual project completion email
                        # Note: auto_orchestrate.py already sends its own email, 
                        # but we can send an additional batch notification here
                        duration = int(time.time() - project_start_time)
                        
                    except subprocess.CalledProcessError as e:
                        error_msg = f"Subprocess failed: {e.stderr}"
                        self.update_project_status(next_project['id'], 'failed', error_msg)
                        logger.error(error_msg)
                        
                        # Track failure
                        failed_projects.append(f"{project_name} (ID: {next_project['id']})")
                        
                        # Send failure email
                        try:
                            email_notifier.send_project_completion_email(
                                project_name=project_name,
                                spec_path=next_project['spec_path'],
                                status='failed',
                                error_message=error_msg,
                                batch_mode=True
                            )
                        except Exception as email_err:
                            logger.debug(f"Failed to send failure email: {email_err}")
                            
                    except Exception as e:
                        self.update_project_status(next_project['id'], 'failed', str(e))
                        logger.error(f"Failed project {next_project['id']}: {e}")
                        
                        # Track failure
                        failed_projects.append(f"{project_name} (ID: {next_project['id']})")
                        
                        # Send failure email
                        try:
                            email_notifier.send_project_completion_email(
                                project_name=project_name,
                                spec_path=next_project['spec_path'],
                                status='failed',
                                error_message=str(e),
                                batch_mode=True
                            )
                        except Exception as email_err:
                            logger.debug(f"Failed to send failure email: {email_err}")
                else:
                    # No more projects in queue
                    if send_batch_summary and (completed_projects or failed_projects):
                        # Send batch summary email
                        try:
                            total_duration = int(time.time() - batch_start_time)
                            email_notifier.send_batch_summary_email(
                                completed_projects=completed_projects,
                                failed_projects=failed_projects,
                                total_duration_seconds=total_duration
                            )
                            # Reset batch tracking
                            completed_projects = []
                            failed_projects = []
                            batch_start_time = time.time()
                        except Exception as e:
                            logger.debug(f"Failed to send batch summary email: {e}")
                            
            except Exception as e:
                logger.error(f"Daemon error: {e}")
            
            time.sleep(poll_interval)  # Poll interval
        
    def run(self):
        """Main scheduler loop"""
        logger.info("Starting Tmux Orchestrator Scheduler")
        
        # Track last cleanup time
        last_cleanup = time.time()
        cleanup_interval = 24 * 3600  # 24 hours
        
        while True:
            try:
                # Check if it's time for cleanup
                now = time.time()
                if now - last_cleanup > cleanup_interval:
                    self.cleanup_old_tasks()
                    last_cleanup = now
                
                # Check and run due tasks
                self.check_and_run_tasks()
                
                # Sleep for a short interval
                time.sleep(30)  # Check every 30 seconds
                
            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user")
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)  # Wait a minute before retrying
                
        self.conn.close()

    # ========== BATCH RETRY SYSTEM METHODS ==========
    
    def enqueue_project(self, spec_path: str, project_path: str = None, batch_id: str = None, retry_count: int = 0):
        """Add a project to the queue for batch processing with idempotency checks"""
        import traceback
        cursor = self.conn.cursor()
        
        # Log caller information for debugging
        stack = traceback.extract_stack()
        caller_info = stack[-2] if len(stack) >= 2 else None
        if caller_info:
            logger.debug(f"enqueue_project called from {caller_info.filename}:{caller_info.lineno} in {caller_info.name}")
        
        # Check if project already exists in active states
        cursor.execute("""
            SELECT id, status, batch_id 
            FROM project_queue 
            WHERE spec_path = ? 
            AND (project_path = ? OR (project_path IS NULL AND ? IS NULL))
            AND status IN ('queued', 'processing')
            ORDER BY enqueued_at DESC
            LIMIT 1
        """, (spec_path, project_path, project_path))
        
        existing = cursor.fetchone()
        if existing:
            project_id, status, existing_batch = existing
            logger.warning(f"Duplicate enqueue prevented: ID={project_id}, spec={spec_path}, status={status}, batch={existing_batch}")
            if caller_info:
                logger.warning(f"  Called from: {caller_info.filename}:{caller_info.lineno}")
            
            # Don't create duplicate - return existing ID
            return project_id
            
        # If not duplicate, proceed with insertion
        cursor.execute("""
            INSERT INTO project_queue (spec_path, project_path, batch_id, retry_count)
            VALUES (?, ?, ?, ?)
        """, (spec_path, project_path, batch_id, retry_count))
        self.conn.commit()
        project_id = cursor.lastrowid
        logger.info(f"Enqueued project {project_id}: {spec_path} (batch: {batch_id}, retry: {retry_count})")
        return project_id

    def update_project_status(self, project_id: int, status: str, error_message: str = None):
        """Update project status in queue"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE project_queue 
            SET status = ?, error_message = ?, completed_at = strftime('%s', 'now')
            WHERE id = ?
        """, (status, error_message, project_id))
        self.conn.commit()
        logger.info(f"Updated project {project_id} status to {status}")
        
    def get_next_project(self):
        """Get next queued project"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, spec_path, project_path, batch_id, retry_count 
            FROM project_queue 
            WHERE status = 'queued' 
            ORDER BY priority DESC, enqueued_at ASC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'spec_path': row[1], 
                'project_path': row[2],
                'batch_id': row[3],
                'retry_count': row[4]
            }
        return None
        
    def publish_event(self, event_name: str, data: Dict[str, Any]):
        """Publish an event to all subscribers"""
        self.trigger_event(event_name, data)
        
    def check_batch_completion(self, batch_id: str):
        """Check if a batch is complete and trigger retry logic if needed"""
        if not batch_id:
            return
            
        if self._is_batch_complete(batch_id):
            self._handle_batch_completion(batch_id)
            
    def _is_batch_complete(self, batch_id: str) -> bool:
        """Check if all projects in batch are completed or failed"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM project_queue 
            WHERE batch_id = ? AND status IN ('queued', 'processing')
        """, (batch_id,))
        return cursor.fetchone()[0] == 0
        
    def _handle_batch_completion(self, batch_id: str):
        """Handle completed batch - check for failures and potentially retry"""
        failed_projects = self._get_failed_projects(batch_id)
        
        if not failed_projects:
            logger.info(f"Batch {batch_id} completed successfully with no failures")
            return
            
        # Check if any failures are eligible for retry
        retryable = [p for p in failed_projects if p['retry_count'] < 3]
        
        if not retryable:
            logger.info(f"Batch {batch_id} failures exceed max retry count - escalating")
            self._escalate_batch_failures(batch_id, failed_projects)
            return
            
        logger.info(f"Batch {batch_id} completed with {len(failed_projects)} failures, {len(retryable)} retryable")
        
        # Run research agent if enabled
        if os.getenv('ENABLE_RESEARCH_AGENT', 'true').lower() == 'true':
            enhanced_projects = self._run_research_agent(retryable)
        else:
            enhanced_projects = retryable
            
        # Create new batch for retries
        retry_count = max(p['retry_count'] for p in retryable) + 1
        new_batch_id = f"{batch_id}-retry{retry_count}"
        
        for project in enhanced_projects:
            spec_path = project.get('enhanced_spec_path', project['spec_path'])
            self.enqueue_project(
                spec_path=spec_path,
                project_path=project['project_path'], 
                batch_id=new_batch_id,
                retry_count=project['retry_count'] + 1
            )
            
        # Mark original failures as retried
        self.conn.execute("""
            UPDATE project_queue SET status = 'retried' 
            WHERE batch_id = ? AND status = 'failed'
        """, (batch_id,))
        self.conn.commit()
        
        logger.info(f"Created retry batch {new_batch_id} with {len(enhanced_projects)} projects")
        
    def _get_failed_projects(self, batch_id: str) -> List[Dict]:
        """Get all failed projects in a batch"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, spec_path, project_path, retry_count, error_message
            FROM project_queue 
            WHERE batch_id = ? AND status = 'failed'
        """, (batch_id,))
        
        projects = []
        for row in cursor.fetchall():
            projects.append({
                'id': row[0],
                'spec_path': row[1],
                'project_path': row[2], 
                'retry_count': row[3],
                'error_message': row[4]
            })
        return projects
        
    def _run_research_agent(self, failed_projects: List[Dict]) -> List[Dict]:
        """Run research agent to analyze failures and enhance specs"""
        try:
            # Import here to avoid circular imports
            import json
            import uuid
            
            # Create research session data
            research_data = {
                'failed_projects': failed_projects,
                'session_id': str(uuid.uuid4()),
                'timestamp': datetime.now().isoformat()
            }
            
            # Call auto_orchestrate.py in research mode
            cmd = [
                'uv', 'run', '--quiet', '--script',
                str(self.tmux_orchestrator_path / 'auto_orchestrate.py'),
                '--research', json.dumps(research_data)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # Parse enhanced project data from stdout
                enhanced_data = json.loads(result.stdout)
                logger.info("Research agent completed successfully")
                return enhanced_data.get('enhanced_projects', failed_projects)
            else:
                logger.error(f"Research agent failed: {result.stderr}")
                return failed_projects
                
        except Exception as e:
            logger.error(f"Error running research agent: {e}")
            return failed_projects
            
    def _escalate_batch_failures(self, batch_id: str, failed_projects: List[Dict]):
        """Escalate batch failures that exceed retry limits"""
        try:
            # Mark as permanently failed
            self.conn.execute("""
                UPDATE project_queue SET status = 'permanently_failed'
                WHERE batch_id = ? AND status = 'failed'
            """, (batch_id,))
            self.conn.commit()
            
            # Send notification email
            email_notifier = get_email_notifier()
            failure_summary = '\n'.join([
                f"- {p['spec_path']}: {p['error_message']}" 
                for p in failed_projects
            ])
            
            email_notifier.send_email(
                subject=f"Batch {batch_id} - Failures Exceed Retry Limits",
                body=f"""
Batch {batch_id} has {len(failed_projects)} projects that failed after maximum retries.

Failed Projects:
{failure_summary}

These projects require manual review and intervention.
                """.strip(),
                is_html=False
            )
            
            logger.info(f"Escalated {len(failed_projects)} permanently failed projects from batch {batch_id}")
            
        except Exception as e:
            logger.error(f"Error escalating batch failures: {e}")
            
    def check_credits(self) -> bool:
        """Check if sufficient credits available for research operations"""
        # This is a placeholder - implement based on your credit system
        # Return True for now to not block operations
        return True
        
    def _run_state_sync(self):
        """Run proactive state synchronization between SQLite, JSON states, and tmux sessions"""
        try:
            logger.debug("Running state synchronization check...")
            synchronizer = StateSynchronizer(self.db_path, "registry")
            mismatches = synchronizer.detect_mismatches()
            
            if mismatches:
                logger.warning(f"Detected {len(mismatches)} state mismatches")
                
                # Log details of each mismatch for debugging
                for mismatch in mismatches:
                    logger.warning(f"State mismatch - {mismatch.type}: {mismatch.description}")
                
                # Attempt auto-repair
                results = synchronizer.auto_repair_mismatches(mismatches)
                logger.info(f"State sync repair results: repaired={results['repaired']}, failed={results['failed']}")
                
                # Escalate critical unresolved issues via email
                if results['failed'] > 0:
                    critical_failed = [m for m in mismatches if m.severity == 'critical']
                    if critical_failed:
                        try:
                            notifier = get_email_notifier()
                            report = synchronizer.generate_report(critical_failed)
                            notifier.send_email(
                                subject="Critical State Synchronization Alert - Tmux Orchestrator",
                                body=f"Critical state mismatches detected and could not be automatically repaired:\n\n{report}"
                            )
                            logger.warning("Sent email alert for critical state synchronization failures")
                        except Exception as email_error:
                            logger.error(f"Failed to send state sync alert email: {email_error}")
            else:
                logger.debug("No state mismatches detected - system synchronized")
                
        except Exception as e:
            logger.error(f"State synchronization check failed: {e}", exc_info=True)
    
    def _reconcile_orphaned_sessions(self):
        """Reconcile orphaned tmux sessions that exist but aren't tracked in SQLite/JSON"""
        try:
            logger.debug("Running orphaned session reconciliation...")
            
            # Get all active tmux sessions
            active_sessions = set()
            try:
                result = subprocess.run(
                    ['tmux', 'list-sessions', '-F', '#{session_name}'],
                    capture_output=True, text=True, check=False
                )
                if result.returncode == 0:
                    active_sessions = set(line.strip() for line in result.stdout.strip().split('\n') if line.strip())
                else:
                    logger.debug("No tmux sessions found or tmux not running")
                    return
            except Exception as e:
                logger.warning(f"Failed to get active tmux sessions: {e}")
                return
            
            if not active_sessions:
                logger.debug("No active tmux sessions found")
                return
            
            # Get known sessions from database
            known_sessions = set()
            with self.queue_lock:
                cursor = self.conn.cursor()
                cursor.execute("SELECT session_name FROM project_queue WHERE session_name IS NOT NULL")
                known_sessions.update(row[0] for row in cursor.fetchall())
            
            # Get known sessions from JSON states
            try:
                synchronizer = StateSynchronizer(self.db_path, "registry")
                json_states = synchronizer.get_json_session_states()
                known_sessions.update(state.get('session_name') for state in json_states if state.get('session_name'))
            except Exception as e:
                logger.warning(f"Failed to get JSON session states: {e}")
            
            # Find orphaned sessions (exist in tmux but not tracked)
            orphaned = active_sessions - known_sessions
            
            if not orphaned:
                logger.debug("No orphaned sessions detected")
                return
            
            logger.info(f"Found {len(orphaned)} potentially orphaned sessions: {', '.join(sorted(orphaned))}")
            
            for session_name in orphaned:
                try:
                    # Check if session is recent (grace period to avoid killing new sessions)
                    session_age = self._get_session_age(session_name)
                    grace_period = int(os.getenv('ORPHANED_SESSION_GRACE_PERIOD_SEC', 3600))  # 1 hour default
                    
                    if session_age < grace_period:
                        logger.debug(f"Session '{session_name}' is only {session_age}s old, within grace period")
                        continue
                    
                    # Check if this might be a system session we should preserve
                    if self._is_system_session(session_name):
                        logger.debug(f"Session '{session_name}' appears to be a system session, preserving")
                        continue
                    
                    logger.warning(f"Terminating orphaned session: '{session_name}' (age: {session_age}s)")
                    
                    # Kill the orphaned session
                    result = subprocess.run(
                        ['tmux', 'kill-session', '-t', session_name],
                        capture_output=True, text=True, check=False
                    )
                    
                    if result.returncode == 0:
                        logger.info(f"✅ Successfully terminated orphaned session: '{session_name}'")
                    else:
                        logger.warning(f"Failed to terminate orphaned session '{session_name}': {result.stderr}")
                        
                except Exception as e:
                    logger.error(f"Error processing orphaned session '{session_name}': {e}")
                    
        except Exception as e:
            logger.error(f"Orphaned session reconciliation failed: {e}", exc_info=True)
    
    def _get_session_age(self, session_name: str) -> int:
        """Get the age of a tmux session in seconds"""
        try:
            # Get session creation time using tmux format
            result = subprocess.run(
                ['tmux', 'display-message', '-t', session_name, '-p', '#{session_created}'],
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                session_created = int(result.stdout.strip())
                return int(time.time()) - session_created
        except Exception as e:
            logger.debug(f"Could not determine age for session '{session_name}': {e}")
        
        # Default to old age if we can't determine (err on the side of terminating)
        return 7200  # 2 hours
    
    def _is_system_session(self, session_name: str) -> bool:
        """Check if a session appears to be a system/user session that should be preserved"""
        # Preserve numeric sessions (like "0", "1", "2") as they're likely user sessions
        if session_name.isdigit():
            return True
            
        # Preserve common system session patterns
        preserve_patterns = [
            'main', 'default', 'work', 'dev', 'prod', 'staging',
            'tmux-orc', 'orchestrator', 'scheduler',  # Our own system sessions
            'claude', 'vim', 'editor', 'shell'  # Common user tool sessions
        ]
        
        # Check if session name matches any preserve pattern
        session_lower = session_name.lower()
        for pattern in preserve_patterns:
            if pattern in session_lower:
                return True
                
        return False
    
    def _attempt_auto_resume(self, project_path: str, spec_path: str) -> bool:
        """
        Attempt to auto-resume an existing orchestration for a project.
        
        Args:
            project_path: Path to the project directory  
            spec_path: Path to the specification file
            
        Returns:
            True if existing session found and resume should be attempted, False otherwise
        """
        try:
            # Extract project name from spec path for session state lookup
            spec_file = Path(spec_path)
            project_name = spec_file.stem.lower().replace('_', '-')
            
            logger.debug(f"Checking for existing orchestration: project_name={project_name}")
            
            # Check if there's an existing session state
            state = self.session_state_manager.load_session_state(project_name)
            if not state or not state.session_name:
                logger.debug(f"No existing session state found for {project_name}")
                return False
            
            # Verify the tmux session still exists
            try:
                result = subprocess.run(
                    ['tmux', 'has-session', '-t', state.session_name],
                    capture_output=True, check=False
                )
                session_exists = result.returncode == 0
                
                if session_exists:
                    logger.info(f"Found existing tmux session '{state.session_name}' for {project_name}")
                    
                    # Additional validation: Check if session is healthy/active
                    if self._is_session_healthy(state.session_name):
                        logger.info(f"Session '{state.session_name}' appears healthy - will attempt resume")
                        return True
                    else:
                        logger.warning(f"Session '{state.session_name}' exists but appears unhealthy - will start new")
                        return False
                else:
                    logger.debug(f"Session '{state.session_name}' no longer exists for {project_name}")
                    return False
                    
            except Exception as e:
                logger.warning(f"Error checking tmux session for {project_name}: {e}")
                return False
                
        except Exception as e:
            logger.warning(f"Error during auto-resume check for {project_path}: {e}")
            return False
    
    def _is_session_healthy(self, session_name: str) -> bool:
        """
        Check if a tmux session appears to be healthy/active.
        
        Args:
            session_name: Name of tmux session to check
            
        Returns:
            True if session appears healthy, False otherwise
        """
        try:
            # Check if session has any windows
            result = subprocess.run(
                ['tmux', 'list-windows', '-t', session_name, '-F', '#{window_name}'],
                capture_output=True, text=True, check=False
            )
            
            if result.returncode != 0:
                return False
                
            windows = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            
            # Session should have at least one window
            if not windows:
                logger.debug(f"Session '{session_name}' has no windows")
                return False
            
            # Check if any windows have active processes (not just shell)
            active_windows = 0
            for window in windows:
                try:
                    # Get pane count and process info
                    result = subprocess.run(
                        ['tmux', 'list-panes', '-t', f"{session_name}:{window}", '-F', '#{pane_current_command}'],
                        capture_output=True, text=True, check=False
                    )
                    if result.returncode == 0:
                        commands = result.stdout.strip().split('\n')
                        # Count panes with active processes (not just shell)
                        for cmd in commands:
                            if cmd.strip() and cmd.strip() not in ['bash', 'zsh', 'sh', 'fish']:
                                active_windows += 1
                                break
                except Exception:
                    continue
            
            # Consider healthy if at least one window has active processes
            is_healthy = active_windows > 0
            logger.debug(f"Session '{session_name}' health check: {active_windows} active windows, healthy={is_healthy}")
            return is_healthy
            
        except Exception as e:
            logger.debug(f"Error checking session health for '{session_name}': {e}")
            return False
    
    def _monitor_batches(self):
        """Enhanced background thread with all monitoring functions"""
        logger.info("Starting enhanced batch monitoring loop")
        
        while not self._stop_monitoring.is_set():
            try:
                # Check for active projects
                cursor = self.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM project_queue WHERE status = 'processing'")
                active_count = cursor.fetchone()[0]
                
                # Adaptive polling interval - faster when projects are active
                poll_interval = 10 if active_count > 0 else int(os.getenv('POLL_INTERVAL_SEC', '60'))
                
                # Run all monitoring functions
                logger.debug("Running monitoring cycle...")
                self.process_signal_files()
                self.check_stuck_projects()
                self.detect_and_reset_phantom_projects()
                self.detect_completed_projects()
                
                # NEW: Proactive state synchronization (every 5 minutes by default)
                now = time.time()
                if now - self.last_state_sync > self.state_sync_interval:
                    logger.debug("Running periodic state synchronization...")
                    self._run_state_sync()
                    self.last_state_sync = now
                
                # NEW: Orphaned session reconciliation (every 10 minutes by default)
                if now - self.last_orphaned_reconcile > self.orphaned_reconcile_interval:
                    logger.debug("Running orphaned session reconciliation...")
                    self._reconcile_orphaned_sessions()
                    self.last_orphaned_reconcile = now
                
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
            
            # Wait for next cycle with adaptive polling
            self._stop_monitoring.wait(poll_interval)
        
        logger.info("Enhanced batch monitoring stopped")
        
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
            
    def update_session_name(self, project_id: int, session_name: str):
        """Update the tmux session name for a project in the queue"""
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE project_queue SET session_name = ? WHERE id = ?", (session_name, project_id))
            logger.info(f"Updated session_name for project {project_id} to {session_name}")
    
    def stop_monitoring(self):
        """Stop the batch monitoring thread"""
        if hasattr(self, '_stop_monitoring'):
            self._stop_monitoring.set()
            logger.info("Batch monitoring stop requested")
    
    def shutdown(self):
        """Clean shutdown of scheduler and all managed processes"""
        logger.info("Scheduler shutdown initiated...")
        
        # Stop monitoring threads
        self.stop_monitoring()
        
        # Shutdown ProcessManager (kills all tracked processes)
        if hasattr(self, 'process_manager'):
            self.process_manager.shutdown()
        
        # Release process lock (only if not read-only)
        if not self.read_only:
            self.lock_manager.release_lock()
        
        # Close database connection
        if hasattr(self, 'conn'):
            self.conn.close()
        
        logger.info("Scheduler shutdown complete")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown()
        sys.exit(0)

# CLI interface for managing tasks
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Tmux Orchestrator Scheduler')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--add', nargs=5, metavar=('SESSION', 'ROLE', 'WINDOW', 'INTERVAL', 'NOTE'),
                       help='Add a scheduled task')
    parser.add_argument('--list', action='store_true', help='List all tasks')
    parser.add_argument('--remove', type=int, metavar='ID', help='Remove a task')
    
    # Project queue management
    parser.add_argument('--queue-daemon', action='store_true', help='Start project queue daemon')
    parser.add_argument('--queue-add', nargs=2, metavar=('SPEC', 'PROJECT'), help='Add project to queue')
    parser.add_argument('--queue-list', action='store_true', help='List queued projects')
    parser.add_argument('--queue-status', type=int, metavar='ID', help='Get status of project')
    
    args = parser.parse_args()
    
    # Determine if this is a read-only operation
    read_only = args.list or args.queue_list or (args.queue_status is not None)
    
    scheduler = TmuxOrchestratorScheduler(read_only=read_only)
    
    if args.daemon:
        scheduler.run()
    elif args.add:
        session, role, window, interval, note = args.add
        task_id = scheduler.enqueue_task(session, role, int(window), int(interval), note)
        print(f"Task {task_id} added successfully")
    elif args.list:
        tasks = scheduler.list_tasks()
        if tasks:
            print("ID | Session | Role | Window | Next Run | Interval | Note")
            print("-" * 70)
            for task in tasks:
                print(" | ".join(map(str, task)))
        else:
            print("No scheduled tasks")
    elif args.remove:
        scheduler.remove_task(args.remove)
        print(f"Task {args.remove} removed")
    elif args.queue_daemon:
        print("Starting project queue daemon...")
        scheduler.run_queue_daemon()
    elif args.queue_add:
        spec_path, project_path = args.queue_add
        project_id = scheduler.enqueue_project(spec_path, project_path if project_path != 'auto' else None)
        print(f"Project {project_id} added to queue")
    elif args.queue_list:
        cursor = scheduler.conn.cursor()
        cursor.execute("SELECT * FROM project_queue ORDER BY priority DESC, enqueued_at ASC")
        projects = cursor.fetchall()
        if projects:
            print("ID | Spec | Project | Status | Priority | Enqueued At | Error")
            print("-" * 80)
            for proj in projects:
                print(" | ".join(str(p) if p is not None else "-" for p in proj))
        else:
            print("No queued projects")
    elif args.queue_status:
        cursor = scheduler.conn.cursor()
        cursor.execute("SELECT * FROM project_queue WHERE id = ?", (args.queue_status,))
        project = cursor.fetchone()
        if project:
            columns = [col[0] for col in cursor.description]
            for col, val in zip(columns, project):
                print(f"{col}: {val}")
        else:
            print(f"Project {args.queue_status} not found")
    else:
        parser.print_help()

if __name__ == '__main__':
    # Check for special commands first
    if len(sys.argv) > 1:
        if sys.argv[1] == '--reset-project' and len(sys.argv) > 2:
            try:
                project_id = int(sys.argv[2])
                scheduler = TmuxOrchestratorScheduler()
                force = '--force' in sys.argv
                reset = scheduler.check_and_reset_specific_project(project_id, force=force)
                if reset:
                    print(f"✅ Project {project_id} has been reset")
                else:
                    print(f"ℹ️ Project {project_id} was not reset (use --force to override)")
                sys.exit(0)
            except ValueError:
                print("❌ Invalid project ID")
                sys.exit(1)
        elif sys.argv[1] == '--check-project' and len(sys.argv) > 2:
            try:
                project_id = int(sys.argv[2])
                scheduler = TmuxOrchestratorScheduler()
                scheduler.check_and_reset_specific_project(project_id, force=False)
                sys.exit(0)
            except ValueError:
                print("❌ Invalid project ID")
                sys.exit(1)
        elif sys.argv[1] == '--delegated-reset' and len(sys.argv) > 2:
            # Non-blocking reset via signal file (works even when daemon is active)
            try:
                project_id = int(sys.argv[2])
                signal_dir = Path('signals')
                signal_dir.mkdir(exist_ok=True)
                
                signal_file = signal_dir / f'reset_project_{project_id}.signal'
                with open(signal_file, 'w') as f:
                    f.write(f'{{"project_id": {project_id}, "timestamp": "{datetime.now().isoformat()}", "force": true}}')
                
                print(f"✅ Reset signal created for project {project_id}")
                print(f"   Signal file: {signal_file}")
                print(f"   The daemon will process this reset within 60 seconds")
                sys.exit(0)
            except ValueError:
                print("❌ Invalid project ID")
                sys.exit(1)
        elif sys.argv[1] == '--remove-project' and len(sys.argv) > 2:
            try:
                project_id = int(sys.argv[2])
                scheduler = TmuxOrchestratorScheduler()
                removed = scheduler.remove_project_from_queue(project_id)
                if removed:
                    print(f"✅ Project {project_id} has been removed from queue")
                else:
                    print(f"❌ Project {project_id} not found or could not be removed")
                sys.exit(0)
            except ValueError:
                print("❌ Invalid project ID")
                sys.exit(1)
    
    main()
#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Tmux Orchestrator Scheduler - Replaces at command with reliable Python-based scheduling
Provides persistent task queue, credit exhaustion detection, and missed task recovery
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
from typing import Dict, Any, Optional, List, Callable

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
        
        # Add lock for thread-safe queue operations (FIX: Prevent concurrent project starts)
        self.queue_lock = threading.Lock()
        
        # NEW: Inter-process lock file
        self.lock_path = Path('locks/project_queue.lock')
        self.lock_fd = None
        self._acquire_process_lock()  # NEW: Acquire early to prevent multiple instances
        
        # Add configurable poll interval
        self.poll_interval = int(os.getenv('POLL_INTERVAL_SEC', 60))
        
        # Add configurable concurrency limit (default 1 for sequential processing)
        self.max_concurrent = int(os.getenv('MAX_CONCURRENT_PROJECTS', 1))
        
        # NEW: For re-entrance protection to prevent notification loops
        self.processing_events = set()
        self._event_lock = threading.Lock()
        
        self.setup_database()
        
        # Clean stale registry entries on startup
        self.session_state_manager.cleanup_stale_registries()
        
        # Auto-subscribe default completion handler
        self.subscribe('task_complete', self._handle_task_completion)
        self.subscribe('project_complete', self._on_project_complete)
        
        # Add authorization event types (for future use)
        self.event_subscribers.setdefault('authorization_request', [])
        self.event_subscribers.setdefault('authorization_response', [])
        
        # NEW: Register lock release on exit
        atexit.register(self._release_process_lock)
        
        # Start batch monitoring thread if enabled
        self._monitoring_enabled = os.getenv('ENABLE_BATCH_MONITORING', 'true').lower() == 'true'
        self._stop_monitoring = threading.Event()
        if self._monitoring_enabled:
            self.retry_thread = threading.Thread(target=self._monitor_batches, daemon=True)
            self.retry_thread.start()
            logger.info("Batch monitoring thread started")
        
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
        if self.lock_fd:
            flock(self.lock_fd, LOCK_UN)
            self.lock_fd.close()
            logger.info("Released process lock")
    
    # NEW: Heartbeat thread to keep lock fresh
    def _heartbeat_thread(self):
        """Update lock file timestamp every 30 seconds to indicate we're alive"""
        while not self._stop_monitoring.is_set():
            try:
                if self.lock_fd and not self.lock_fd.closed:
                    self.lock_fd.seek(0)
                    lock_data = {
                        'pid': os.getpid(),
                        'timestamp': datetime.now().isoformat(),
                        'hostname': socket.gethostname()
                    }
                    self.lock_fd.truncate()
                    self.lock_fd.write(json.dumps(lock_data) + '\n')
                    self.lock_fd.flush()
                    logger.debug(f"Updated lock heartbeat: {lock_data['timestamp']}")
            except Exception as e:
                logger.error(f"Error updating lock heartbeat: {e}")
            
            # Sleep for 30 seconds
            self._stop_monitoring.wait(30)
    
    def check_stuck_projects(self):
        """Auto-reset projects stuck in processing >4 hours"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE project_queue 
            SET status = 'failed', 
                error_message = 'Auto-reset: Timeout after 4 hours in processing',
                completed_at = strftime('%s', 'now')
            WHERE status = 'processing' 
            AND strftime('%s', 'now') - started_at > 14400
        """)
        affected = cursor.rowcount
        self.conn.commit()
        if affected > 0:
            logger.warning(f"Auto-reset {affected} stuck projects to 'failed'")
    
    def check_and_reset_specific_project(self, project_id: int, force: bool = False) -> bool:
        """Check if a specific project is stuck and optionally reset it"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT status, started_at, orchestrator_session, main_session
            FROM project_queue 
            WHERE id = ?
        """, (project_id,))
        row = cursor.fetchone()
        if not row:
            logger.error(f"Project {project_id} not found")
            return False
        
        status, started_at, orch_session, main_session = row
        if status != 'processing':
            logger.info(f"Project {project_id} is {status}, not processing")
            return False
        
        is_stuck = False
        if started_at and time.time() - float(started_at) > 7200:  # 2 hours (reduced from 4)
            is_stuck = True
            logger.info(f"Project {project_id} has been running for {(time.time() - float(started_at))/3600:.1f} hours")
        elif orch_session and not self._session_exists(orch_session):  # Check tmux
            is_stuck = True
            logger.info(f"Project {project_id} orchestrator session '{orch_session}' no longer exists")
        
        if is_stuck or force:
            self.mark_project_complete(project_id, success=False, error_message='Manual reset: Project appeared stuck or orphaned')
            logger.warning(f"Reset project {project_id} to failed")
            return True
        logger.info(f"Project {project_id} appears to be running normally")
        return False
    
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
            cursor.execute("SELECT status FROM project_queue WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if row and row[0] in ('completed', 'failed'):
                logger.debug(f"Project {project_id} already marked as {row[0]}, skipping to prevent notification loop")
                return  # Exit early without updating or triggering event
            
            status = 'completed' if success else 'failed'
            with self.conn:  # Transaction for atomic update
                cursor.execute("""
                    UPDATE project_queue 
                    SET status = ?, completed_at = strftime('%s', 'now'), error_message = ? 
                    WHERE id = ?
                """, (status, error_message, project_id))
            logger.info(f"Project {project_id} marked as {status}")
            
            # Trigger project completion event for monitoring
            self.complete_task(f"project_{project_id}", {
                'project_id': project_id, 
                'status': status, 
                'error_message': error_message
            })
        except sqlite3.Error as e:
            logger.error(f"Failed to update completion status for project {project_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error marking project {project_id} complete: {e}")
        
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
        
    def enqueue_task(self, session_name, agent_role, window_index, interval_minutes, note=""):
        """Add a task to the scheduler queue"""
        next_run = time.time() + (interval_minutes * 60)
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (session_name, agent_role, window_index, next_run, interval_minutes, note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_name, agent_role, window_index, next_run, interval_minutes, note))
        self.conn.commit()
        task_id = cursor.lastrowid
        logger.info(f"Enqueued task {task_id} for {session_name}:{window_index} ({agent_role})")
        return task_id
        
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
                cmd_send = f"tmux send-keys -t {target_window} {shlex.quote(message)} Enter"
                result_send = subprocess.run(cmd_send, shell=True, capture_output=True, text=True)
            
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
            
            # Check if task was missed (overdue by more than 2x interval)
            if last_run and (now - last_run) > (interval_minutes * 60 * 2):
                logger.warning(f"Task {task_id} was missed, recovering...")
                
            # Run the task
            success = self.run_task(task_id, session_name, agent_role, window_index, note)
            
            if success:
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
    
    def has_active_orchestrations(self) -> bool:
        """Check if any orchestrations are currently active"""
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
            
            active_orchestrations = [orch for orch in all_orchestrations if orch.get('active')]
            logger.debug(f"Active orchestrations: {len(active_orchestrations)}")
            
            if active_orchestrations:
                logger.info(f"Found {len(active_orchestrations)} active orchestration(s): {[o['session_name'] for o in active_orchestrations]}")
                return True
            else:
                logger.info(f"No active orchestrations found (checked {len(all_orchestrations)} total)")
                return False
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
                with FileLock(str(self.tmux_orchestrator_path / 'locks' / 'project_queue.lock'), timeout=30):
                    # Check for stuck projects and auto-reset them
                    self.check_stuck_projects()
                    
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
                            
                            # CRITICAL: Determine if this should be resume vs create new
                            should_resume = False
                            if proj_arg != 'auto':
                                # Specific project path provided - check if orchestration exists
                                try:
                                    state = self.session_state_manager.load_session_state(project_name)
                                    should_resume = state is not None and state.session_name
                                    if should_resume:
                                        logger.info(f"Found existing orchestration for {project_name} - will resume")
                                    else:
                                        logger.info(f"No existing orchestration for {project_name} - will create new")
                                except Exception as e:
                                    logger.warning(f"Could not check session state for {project_name}: {e}")
                                    should_resume = False
                            else:
                                # Auto-detect mode - never resume, always create new
                                logger.info(f"Auto-detect mode for {project_name} - will create new orchestration")
                                should_resume = False
                            
                            # Build command
                            cmd = [
                                'uv', 'run', '--quiet', '--script',
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
                            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                            # FIXED: Keep project in 'processing' until actual orchestration work completes
                            # Project remains 'processing' - will be marked 'completed' by orchestration agents
                            logger.info(f"Started project {next_project['id']} - orchestration setup completed, project remains in processing")
                            
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
        
    def _monitor_batches(self):
        """Background thread to monitor batch completion"""
        logger.info("Starting batch monitoring loop")
        
        while not self._stop_monitoring.wait(300):  # Check every 5 minutes
            try:
                # Get all distinct batch_ids with incomplete projects
                cursor = self.conn.cursor()
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
                logger.error(f"Error in batch monitoring: {e}")
                
        logger.info("Batch monitoring stopped")
        
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
    
    scheduler = TmuxOrchestratorScheduler()
    
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
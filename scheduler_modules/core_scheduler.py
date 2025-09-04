#!/usr/bin/env python3
"""
Core scheduler module that coordinates all other modules.
This is the central orchestrator for the modular scheduler system.
"""

import sqlite3
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# Import Phase 1 modules
from .config import SchedulerConfig
from .dependency_checker import DependencyChecker
from . import utils

# Import Phase 2 modules
from .session_monitor import SessionMonitor
from .recovery_manager import RecoveryManager
from .batch_processor import BatchProcessor
from .process_manager_wrapper import ProcessManagerWrapper
from .state_synchronizer_wrapper import StateSynchronizerWrapper

logger = logging.getLogger(__name__)


class CoreScheduler:
    """
    Central scheduler that coordinates all modular components.
    Uses dependency injection for flexibility and testability.
    """
    
    def __init__(self, 
                 db_path: str = 'task_queue.db',
                 tmux_orchestrator_path: Optional[Path] = None,
                 session_state_manager=None,
                 process_manager=None,
                 state_synchronizer=None,
                 lock_manager=None,
                 config: Optional[SchedulerConfig] = None):
        """
        Initialize the core scheduler with injected dependencies.
        
        Args:
            db_path: Path to SQLite database
            tmux_orchestrator_path: Path to Tmux-Orchestrator directory
            session_state_manager: SessionStateManager instance
            process_manager: ProcessManager instance
            state_synchronizer: StateSynchronizer instance
            lock_manager: SchedulerLockManager instance
            config: SchedulerConfig instance
        """
        # Configuration
        self.config = config or SchedulerConfig
        self.db_path = db_path
        self.tmux_orchestrator_path = tmux_orchestrator_path or Path(__file__).parent.parent
        
        # Verify dependencies
        if not DependencyChecker.verify_all_dependencies():
            raise RuntimeError("Critical dependencies unavailable")
            
        # Core components (injected)
        self.session_state_manager = session_state_manager
        self.lock_manager = lock_manager
        
        # Database connection
        self.conn = None
        self._init_database()
        
        # Phase 2: Initialize monitoring modules
        self.session_monitor = SessionMonitor(
            self.conn, 
            self.session_state_manager,
            self.config
        )
        
        self.recovery_manager = RecoveryManager(
            self.conn,
            self.session_state_manager,
            self.config
        )
        
        self.batch_processor = BatchProcessor(self)
        
        if process_manager:
            self.process_manager_wrapper = ProcessManagerWrapper(
                process_manager,
                self.conn,
                self.config
            )
        else:
            self.process_manager_wrapper = None
            
        if state_synchronizer:
            self.state_synchronizer_wrapper = StateSynchronizerWrapper(
                state_synchronizer,
                self.conn,
                self.session_state_manager,
                self.config
            )
        else:
            self.state_synchronizer_wrapper = None
            
        # Threading control
        self.stop_event = threading.Event()
        self.daemon_thread = None
        
        # Monitoring intervals
        self.last_phantom_check = 0
        self.last_state_sync = 0
        self.last_orphan_check = 0
        
    def _init_database(self):
        """Initialize database connection and schema."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
            
            # Create tables if needed
            self._ensure_schema()
            
            logger.info(f"Database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
            
    def _ensure_schema(self):
        """Ensure database schema exists."""
        # This would normally be in a separate schema module
        # For now, just check if table exists
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='project_queue'
        """)
        
        if not cursor.fetchone():
            logger.warning("project_queue table not found - scheduler may not work properly")
            
    def start_daemon(self):
        """Start the scheduler daemon."""
        if self.daemon_thread and self.daemon_thread.is_alive():
            logger.warning("Daemon already running")
            return
            
        self.stop_event.clear()
        self.daemon_thread = threading.Thread(target=self._daemon_loop, daemon=True)
        self.daemon_thread.start()
        
        logger.info("Scheduler daemon started")
        
    def stop_daemon(self):
        """Stop the scheduler daemon."""
        self.stop_event.set()
        
        if self.daemon_thread:
            self.daemon_thread.join(timeout=5)
            
        logger.info("Scheduler daemon stopped")
        
    def _daemon_loop(self):
        """Main daemon loop that coordinates all monitoring activities."""
        logger.info("Entering daemon loop")
        
        # Initial recovery check
        self.recovery_manager.recover_from_reboot()
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                # Phantom detection (every phantom_grace_period)
                if current_time - self.last_phantom_check > self.config.PHANTOM_GRACE_PERIOD_SEC:
                    self.session_monitor.detect_and_reset_phantom_projects()
                    self.last_phantom_check = current_time
                    
                # State synchronization
                if self.state_synchronizer_wrapper and \
                   current_time - self.last_state_sync > self.config.STATE_SYNC_INTERVAL_SEC:
                    self.state_synchronizer_wrapper.sync_project_states()
                    self.state_synchronizer_wrapper.repair_null_sessions()
                    self.last_state_sync = current_time
                    
                # Batch monitoring
                self.batch_processor.monitor_batches()
                
                # Process cleanup
                if self.process_manager_wrapper:
                    self.process_manager_wrapper.cleanup_dead_processes()
                    
                # Orphaned session reconciliation
                if current_time - self.last_orphan_check > self.config.ORPHANED_RECONCILE_INTERVAL_SEC:
                    self._reconcile_orphaned_sessions()
                    self.last_orphan_check = current_time
                    
                # Sleep for monitoring interval
                time.sleep(self.config.PROCESS_MONITOR_INTERVAL_SEC)
                
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}", exc_info=True)
                time.sleep(5)  # Brief pause before retrying
                
        logger.info("Exiting daemon loop")
        
    def _reconcile_orphaned_sessions(self):
        """Reconcile orphaned tmux sessions."""
        try:
            import subprocess
            
            # Get all tmux sessions
            result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'],
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                return
                
            sessions = result.stdout.strip().split('\n')
            orchestrator_sessions = [s for s in sessions if 'orchestrator' in s.lower()]
            
            # Get active project sessions from database
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT main_session FROM project_queue
                WHERE status IN ('processing', 'queued') AND main_session IS NOT NULL
            """)
            
            active_sessions = {row[0] for row in cursor.fetchall()}
            
            # Find orphaned sessions
            for session in orchestrator_sessions:
                if session not in active_sessions:
                    # Check session age
                    age = utils.get_session_age(session)
                    
                    # Only kill old orphaned sessions (>1 hour)
                    if age > 3600:
                        logger.warning(f"Killing orphaned session: {session} (age: {age/3600:.1f} hours)")
                        subprocess.run(['tmux', 'kill-session', '-t', session],
                                     capture_output=True, check=False)
                        
        except Exception as e:
            logger.error(f"Error reconciling orphaned sessions: {e}", exc_info=True)
            
    def get_status(self) -> Dict[str, Any]:
        """
        Get current scheduler status.
        
        Returns:
            Dictionary containing status information
        """
        status = {
            'daemon_running': self.daemon_thread and self.daemon_thread.is_alive(),
            'database_connected': self.conn is not None,
            'batch_active': self.batch_processor.is_batch_active(),
            'batch_metrics': self.batch_processor.get_batch_statistics()
        }
        
        # Add validation results if available
        if self.state_synchronizer_wrapper:
            status['state_validation'] = self.state_synchronizer_wrapper.validate_state_consistency()
            
        return status
        
    def cleanup(self):
        """Clean up resources."""
        self.stop_daemon()
        
        if self.conn:
            self.conn.close()
            
        logger.info("Scheduler cleanup complete")
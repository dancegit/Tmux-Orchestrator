#!/usr/bin/env python3
"""
Process Manager for Tmux Orchestrator

Tracks and manages auto_orchestrate.py subprocesses to prevent orphan processes
and enforce timeouts. Provides centralized PID registry with monitoring and cleanup.
"""

import os
import psutil
import threading
import time
import logging
from collections import defaultdict
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class ProcessManager:
    """Manages subprocess PIDs for orchestration projects."""
    
    def __init__(self, max_runtime: int = 1800, monitor_interval: int = 30):
        """
        Initialize ProcessManager.
        
        Args:
            max_runtime: Maximum runtime in seconds before force-killing (default: 30 min)
            monitor_interval: How often to check processes in seconds (default: 30s)
        """
        self.active_processes = defaultdict(dict)  # project_id -> process info
        self.max_runtime = int(os.getenv('MAX_PROCESS_RUNTIME_SEC', max_runtime))
        self.monitor_interval = monitor_interval
        self._stop = False
        self._lock = threading.Lock()  # Thread-safe access to active_processes
        
        # Start background monitor thread
        self.monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self.monitor_thread.start()
        logger.info(f"ProcessManager started with {max_runtime}s timeout, {monitor_interval}s monitoring")

    def register(self, project_id: int, pid: int, cmd: Optional[str] = None):
        """
        Register a new process for a project.
        
        Args:
            project_id: Project ID from database
            pid: Process ID to track
            cmd: Optional command line for logging
        """
        with self._lock:
            self.active_processes[project_id] = {
                'pid': pid,
                'start_time': time.time(),
                'last_heartbeat': time.time(),
                'cmd': cmd or 'auto_orchestrate.py'
            }
        logger.info(f"Registered process {pid} for project {project_id} (cmd: {cmd})")

    def is_alive(self, project_id: int) -> bool:
        """
        Check if the process is still running.
        
        Args:
            project_id: Project ID to check
            
        Returns:
            True if process exists and is running, False otherwise
        """
        with self._lock:
            info = self.active_processes.get(project_id)
            if not info:
                return False
                
        try:
            p = psutil.Process(info['pid'])
            # Check if running and not a zombie
            return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def kill(self, project_id: int, force: bool = False, reason: str = "Manual termination") -> bool:
        """
        Kill the process gracefully (SIGTERM) or forcefully (SIGKILL).
        
        Args:
            project_id: Project ID to kill
            force: If True, use SIGKILL; if False, use SIGTERM with graceful wait
            reason: Reason for killing (for logging)
            
        Returns:
            True if successfully killed, False if process not found or error
        """
        with self._lock:
            info = self.active_processes.get(project_id)
            if not info:
                logger.warning(f"Cannot kill project {project_id}: not found in registry")
                return False
                
        try:
            p = psutil.Process(info['pid'])
            logger.warning(f"Killing process {info['pid']} for project {project_id} (force={force}) - {reason}")
            
            if force:
                p.kill()  # SIGKILL
            else:
                p.terminate()  # SIGTERM
                try:
                    p.wait(timeout=10)  # Wait up to 10s for graceful exit
                except psutil.TimeoutExpired:
                    logger.warning(f"Process {info['pid']} didn't terminate gracefully, force killing")
                    p.kill()
                    
            with self._lock:
                del self.active_processes[project_id]
            return True
            
        except psutil.NoSuchProcess:
            logger.info(f"Process {info['pid']} for project {project_id} already dead")
            with self._lock:
                del self.active_processes[project_id]
            return False
        except Exception as e:
            logger.error(f"Unexpected error killing process for project {project_id}: {e}")
            return False

    def update_heartbeat(self, project_id: int):
        """
        Update heartbeat for a process (can be called by child processes).
        
        Args:
            project_id: Project ID to update heartbeat for
        """
        with self._lock:
            if project_id in self.active_processes:
                self.active_processes[project_id]['last_heartbeat'] = time.time()

    def get_active_count(self) -> int:
        """Get count of currently tracked processes."""
        with self._lock:
            return len(self.active_processes)

    def get_process_info(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        Get process information for debugging.
        
        Args:
            project_id: Project ID to get info for
            
        Returns:
            Dict with process info or None if not found
        """
        with self._lock:
            info = self.active_processes.get(project_id)
            if not info:
                return None
            
            # Add runtime calculation
            runtime = time.time() - info['start_time']
            return {
                **info,
                'runtime_seconds': runtime,
                'is_alive': self.is_alive(project_id)
            }

    def get_all_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get info for all tracked processes (for debugging/monitoring)."""
        with self._lock:
            result = {}
            for project_id, info in self.active_processes.items():
                runtime = time.time() - info['start_time']
                result[project_id] = {
                    **info,
                    'runtime_seconds': runtime,
                    'is_alive': self.is_alive(project_id)
                }
            return result

    def _monitor(self):
        """Background monitor to detect and clean up dead/timeout processes."""
        logger.info(f"ProcessManager monitor thread started (checking every {self.monitor_interval}s)")
        
        while not self._stop:
            to_remove = []
            current_time = time.time()
            
            with self._lock:
                process_items = list(self.active_processes.items())
            
            for project_id, info in process_items:
                pid = info['pid']
                start_time = info['start_time']
                runtime = current_time - start_time
                
                # Check if process is still alive
                if not self.is_alive(project_id):
                    logger.warning(f"Detected dead process {pid} for project {project_id} (runtime: {runtime:.1f}s)")
                    to_remove.append(project_id)
                    continue
                
                # Check for timeout
                if runtime > self.max_runtime:
                    logger.warning(f"Process {pid} for project {project_id} exceeded timeout ({runtime:.1f}s > {self.max_runtime}s)")
                    if self.kill(project_id, force=True, reason=f"Timeout after {runtime:.1f}s"):
                        to_remove.append(project_id)
                
            # Clean up removed processes
            with self._lock:
                for project_id in to_remove:
                    if project_id in self.active_processes:
                        del self.active_processes[project_id]
            
            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} processes: {to_remove}")
            
            time.sleep(self.monitor_interval)
        
        logger.info("ProcessManager monitor thread stopped")

    def shutdown(self):
        """Shutdown ProcessManager and kill all tracked processes."""
        logger.info("ProcessManager shutting down...")
        self._stop = True
        
        # Kill all tracked processes
        with self._lock:
            project_ids = list(self.active_processes.keys())
        
        for project_id in project_ids:
            self.kill(project_id, force=True, reason="ProcessManager shutdown")
        
        # Wait for monitor thread to finish
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
            
        logger.info(f"ProcessManager shutdown complete (terminated {len(project_ids)} processes)")

    def __del__(self):
        """Ensure cleanup on garbage collection."""
        if not self._stop:
            self.shutdown()
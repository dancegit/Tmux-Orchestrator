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
        
        # Heartbeat extension settings
        self.heartbeat_timeout = int(os.getenv('HEARTBEAT_TIMEOUT_SEC', 600))  # 10min default
        self.max_extensions = int(os.getenv('MAX_TIMEOUT_EXTENSIONS', 3))  # Max 3 extensions
        self.extension_duration = int(os.getenv('EXTENSION_DURATION_SEC', 900))  # 15min per extension
        
        # Start background monitor thread
        self.monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self.monitor_thread.start()
        logger.info(f"ProcessManager started with {max_runtime}s timeout, {monitor_interval}s monitoring, heartbeat extensions enabled")

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
                'cmd': cmd or 'auto_orchestrate.py',
                'timeout_extensions': 0,  # Track number of extensions granted
                'extended_timeout': self.max_runtime  # Current effective timeout
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

    def extend_timeout(self, project_id: int, reason: str = "Long-running operation") -> bool:
        """
        Extend timeout for a process based on recent heartbeat activity.
        
        Args:
            project_id: Project ID to extend timeout for
            reason: Reason for extension (for logging)
            
        Returns:
            True if timeout was extended, False if extension denied
        """
        with self._lock:
            info = self.active_processes.get(project_id)
            if not info:
                logger.warning(f"Cannot extend timeout for project {project_id}: not found in registry")
                return False
            
            # Check if we've exceeded maximum extensions
            if info['timeout_extensions'] >= self.max_extensions:
                logger.warning(f"Cannot extend timeout for project {project_id}: max extensions ({self.max_extensions}) reached")
                return False
            
            # Check if heartbeat is recent enough to justify extension
            current_time = time.time()
            heartbeat_age = current_time - info['last_heartbeat']
            
            if heartbeat_age > self.heartbeat_timeout:
                logger.warning(f"Cannot extend timeout for project {project_id}: stale heartbeat ({heartbeat_age:.1f}s > {self.heartbeat_timeout}s)")
                return False
            
            # Grant extension
            info['timeout_extensions'] += 1
            info['extended_timeout'] += self.extension_duration
            
            logger.info(f"Extended timeout for project {project_id} by {self.extension_duration}s (extension #{info['timeout_extensions']}/{self.max_extensions}) - {reason}")
            return True

    def get_effective_timeout(self, project_id: int) -> int:
        """Get the current effective timeout for a process (including extensions)."""
        with self._lock:
            info = self.active_processes.get(project_id)
            if not info:
                return self.max_runtime
            return info.get('extended_timeout', self.max_runtime)

    def heartbeat_with_extension(self, project_id: int, operation_name: str = "Long operation") -> dict:
        """
        Update heartbeat and potentially extend timeout if nearing expiration.
        
        This is a convenience method for long-running operations to call periodically.
        It updates the heartbeat and automatically requests timeout extension if needed.
        
        Args:
            project_id: Project ID to heartbeat
            operation_name: Name of the operation (for logging)
            
        Returns:
            dict with status information:
            {
                'heartbeat_updated': bool,
                'extension_granted': bool,
                'timeout_remaining': int,
                'extensions_used': int,
                'max_extensions': int
            }
        """
        result = {
            'heartbeat_updated': False,
            'extension_granted': False,
            'timeout_remaining': 0,
            'extensions_used': 0,
            'max_extensions': self.max_extensions
        }
        
        # Update heartbeat first
        self.update_heartbeat(project_id)
        result['heartbeat_updated'] = True
        
        # Check if we need extension
        with self._lock:
            info = self.active_processes.get(project_id)
            if not info:
                return result
                
            current_time = time.time()
            runtime = current_time - info['start_time']
            effective_timeout = info.get('extended_timeout', self.max_runtime)
            remaining = max(0, effective_timeout - runtime)
            extensions_used = info.get('timeout_extensions', 0)
            
            result['timeout_remaining'] = int(remaining)
            result['extensions_used'] = extensions_used
            
            # Auto-extend if we're within 5 minutes of timeout and haven't maxed out extensions
            if (remaining < 300 and  # Less than 5 minutes remaining
                extensions_used < self.max_extensions):
                if self.extend_timeout(project_id, f"Auto-extension during {operation_name}"):
                    result['extension_granted'] = True
                    result['timeout_remaining'] = int(remaining + self.extension_duration)
        
        return result

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
            current_time = time.time()
            runtime = current_time - info['start_time']
            heartbeat_age = current_time - info['last_heartbeat']
            effective_timeout = info.get('extended_timeout', self.max_runtime)
            
            return {
                **info,
                'runtime_seconds': runtime,
                'heartbeat_age_seconds': heartbeat_age,
                'effective_timeout_seconds': effective_timeout,
                'timeout_remaining_seconds': max(0, effective_timeout - runtime),
                'is_alive': self.is_alive(project_id)
            }

    def get_all_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get info for all tracked processes (for debugging/monitoring)."""
        with self._lock:
            result = {}
            current_time = time.time()
            for project_id, info in self.active_processes.items():
                runtime = current_time - info['start_time']
                heartbeat_age = current_time - info['last_heartbeat']
                effective_timeout = info.get('extended_timeout', self.max_runtime)
                
                result[project_id] = {
                    **info,
                    'runtime_seconds': runtime,
                    'heartbeat_age_seconds': heartbeat_age,
                    'effective_timeout_seconds': effective_timeout,
                    'timeout_remaining_seconds': max(0, effective_timeout - runtime),
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
                
                # Check for timeout using extended timeout
                effective_timeout = info.get('extended_timeout', self.max_runtime)
                heartbeat_age = current_time - info['last_heartbeat']
                
                if runtime > effective_timeout:
                    # Check if we can auto-extend based on recent heartbeat
                    if (heartbeat_age <= self.heartbeat_timeout and 
                        info.get('timeout_extensions', 0) < self.max_extensions):
                        # Auto-extend timeout
                        with self._lock:
                            if project_id in self.active_processes:  # Double-check still exists
                                self.active_processes[project_id]['timeout_extensions'] += 1
                                self.active_processes[project_id]['extended_timeout'] += self.extension_duration
                                extensions = self.active_processes[project_id]['timeout_extensions']
                                logger.info(f"Auto-extended timeout for project {project_id} by {self.extension_duration}s due to recent heartbeat (extension #{extensions}/{self.max_extensions})")
                    else:
                        # No more extensions available or stale heartbeat
                        logger.warning(f"Process {pid} for project {project_id} exceeded timeout ({runtime:.1f}s > {effective_timeout}s, heartbeat age: {heartbeat_age:.1f}s)")
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
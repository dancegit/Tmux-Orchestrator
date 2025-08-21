#!/usr/bin/env python3
"""
ProjectLock - File-based locking mechanism for project operations

Prevents cross-project interference during resets and critical operations
in multi-project environments by providing exclusive access through file locks.
"""

import os
import fcntl
import time
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ProjectLock:
    """
    File-based project locking mechanism using fcntl for cross-process synchronization.
    
    Prevents race conditions and interference during critical project operations
    like resets, session termination, and state modifications.
    """
    
    def __init__(self, lock_dir: str = 'locks', timeout: int = 30):
        """
        Initialize ProjectLock.
        
        Args:
            lock_dir: Directory to store lock files (default: 'locks')
            timeout: Maximum seconds to wait for lock acquisition (default: 30)
        """
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(exist_ok=True)
        self.timeout = timeout
        self._fd = None
        self.project_id = None
        self.lock_file = None

    def acquire(self, project_id: int) -> bool:
        """
        Acquire exclusive lock for a project.
        
        Args:
            project_id: Project ID to lock
            
        Returns:
            True if lock acquired successfully, False if timeout occurred
        """
        self.project_id = project_id
        self.lock_file = self.lock_dir / f'project_{project_id}.lock'
        
        try:
            # Open lock file for writing (creates if doesn't exist)
            self._fd = open(self.lock_file, 'w')
            
            # Write process info for debugging
            self._fd.write(f"PID: {os.getpid()}\nTIME: {time.time()}\n")
            self._fd.flush()
            
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                try:
                    # Try to acquire exclusive non-blocking lock
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    logger.debug(f"✅ Acquired project lock for project {project_id}")
                    return True
                except IOError:
                    # Lock is held by another process, wait and retry
                    time.sleep(0.5)
            
            # Timeout occurred
            logger.warning(f"⏰ Timeout acquiring project lock for project {project_id} after {self.timeout}s")
            self._cleanup_failed_acquire()
            return False
            
        except Exception as e:
            logger.error(f"❌ Error acquiring project lock for project {project_id}: {e}")
            self._cleanup_failed_acquire()
            return False

    def release(self):
        """Release the acquired lock."""
        if self._fd:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                self._fd.close()
                logger.debug(f"🔓 Released project lock for project {self.project_id}")
                
                # Clean up lock file
                if self.lock_file and self.lock_file.exists():
                    try:
                        self.lock_file.unlink()
                    except OSError:
                        # Lock file may be in use by another process, that's OK
                        pass
                        
            except Exception as e:
                logger.warning(f"Error releasing project lock for project {self.project_id}: {e}")
            finally:
                self._fd = None
                self.project_id = None
                self.lock_file = None

    def _cleanup_failed_acquire(self):
        """Clean up after failed lock acquisition."""
        if self._fd:
            try:
                self._fd.close()
            except:
                pass
            self._fd = None
        self.project_id = None
        self.lock_file = None

    def __enter__(self):
        """Context manager entry - lock must be acquired externally."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release the lock."""
        self.release()

    def is_locked(self, project_id: int) -> bool:
        """
        Check if a project is currently locked (non-blocking check).
        
        Args:
            project_id: Project ID to check
            
        Returns:
            True if project is locked, False otherwise
        """
        lock_file = self.lock_dir / f'project_{project_id}.lock'
        if not lock_file.exists():
            return False
            
        try:
            with open(lock_file, 'r') as test_fd:
                # Try to acquire non-blocking lock
                fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(test_fd, fcntl.LOCK_UN)
                return False  # Lock was available
        except IOError:
            return True  # Lock is held
        except Exception:
            return False  # Assume not locked if we can't determine

    def cleanup_stale_locks(self, max_age_hours: int = 24):
        """
        Clean up stale lock files older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours before a lock is considered stale
        """
        if not self.lock_dir.exists():
            return
            
        max_age_seconds = max_age_hours * 3600
        current_time = time.time()
        cleaned = 0
        
        for lock_file in self.lock_dir.glob('project_*.lock'):
            try:
                # Check if lock file is old
                age = current_time - lock_file.stat().st_mtime
                if age > max_age_seconds:
                    # Try to remove stale lock
                    try:
                        with open(lock_file, 'r') as test_fd:
                            fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            # Lock is available, safe to remove
                            lock_file.unlink()
                            cleaned += 1
                            logger.debug(f"Cleaned stale lock file: {lock_file}")
                    except IOError:
                        # Lock is still held, leave it alone
                        pass
            except Exception as e:
                logger.warning(f"Error checking stale lock {lock_file}: {e}")
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} stale project lock files")


def with_project_lock(lock_dir: str = 'locks', timeout: int = 30):
    """
    Decorator to automatically acquire and release project locks for methods.
    
    The decorated method must accept project_id as its first argument after self.
    
    Args:
        lock_dir: Directory for lock files
        timeout: Lock acquisition timeout
        
    Example:
        @with_project_lock()
        def reset_project(self, project_id: int):
            # This method will run with project_id locked
            pass
    """
    def decorator(func):
        def wrapper(self, project_id: int, *args, **kwargs):
            lock = ProjectLock(lock_dir, timeout)
            if lock.acquire(project_id):
                try:
                    return func(self, project_id, *args, **kwargs)
                finally:
                    lock.release()
            else:
                logger.error(f"Failed to acquire project lock for {func.__name__} on project {project_id}")
                return False
        return wrapper
    return decorator


# Convenience function for simple locking
def acquire_project_lock(project_id: int, timeout: int = 30) -> ProjectLock:
    """
    Acquire a project lock with specified timeout.
    
    Args:
        project_id: Project ID to lock
        timeout: Maximum seconds to wait
        
    Returns:
        ProjectLock object if successful, None if failed
        
    Example:
        lock = acquire_project_lock(123)
        if lock:
            try:
                # Do critical operations
                pass
            finally:
                lock.release()
    """
    lock = ProjectLock(timeout=timeout)
    if lock.acquire(project_id):
        return lock
    return None
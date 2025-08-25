#!/usr/bin/env python3
"""
Enhanced Scheduler Lock Manager
Prevents duplicate scheduler processes with robust detection and prevention mechanisms.
"""
import os
import sys
import json
import time
import socket
import psutil
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_UN
import logging

logger = logging.getLogger(__name__)

class SchedulerLockManager:
    """Robust scheduler process lock manager with enhanced duplicate detection"""
    
    def __init__(self, lock_dir: str = "locks", timeout: int = 30):
        self.lock_dir = Path(lock_dir)
        self.lock_file = self.lock_dir / "scheduler.lock"
        self.process_file = self.lock_dir / "scheduler_process.info"
        self.timeout = timeout
        self.lock_fd = None
        self.process_signature = self._generate_process_signature()
        
        # Create lock directory
        self.lock_dir.mkdir(exist_ok=True)
    
    def _generate_process_signature(self) -> str:
        """Generate unique signature for this scheduler process"""
        # Combine script path, command line args, and working directory
        script_path = os.path.abspath(sys.argv[0])
        cmd_args = ' '.join(sys.argv[1:])
        cwd = os.getcwd()
        signature_data = f"{script_path}|{cmd_args}|{cwd}|{os.getpid()}"
        return hashlib.md5(signature_data.encode()).hexdigest()[:16]
    
    def _is_scheduler_process(self, pid: int) -> tuple[bool, str]:
        """Enhanced process validation - checks if PID is actually a scheduler"""
        try:
            process = psutil.Process(pid)
            
            # Check if process exists and is running
            if not process.is_running():
                return False, f"Process {pid} is not running"
            
            # Check command line - must contain 'scheduler.py'
            try:
                cmdline = ' '.join(process.cmdline())
                if 'scheduler.py' not in cmdline:
                    return False, f"Process {pid} is not a scheduler: {cmdline}"
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                return False, f"Cannot access process {pid} command line"
            
            # Check working directory (if accessible)
            try:
                process_cwd = process.cwd()
                current_cwd = os.getcwd()
                if process_cwd != current_cwd:
                    logger.warning(f"Process {pid} running from different directory: {process_cwd} vs {current_cwd}")
                    # Don't fail on different directories - could be legitimate
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            # Check process age - very new processes might be startup races
            create_time = datetime.fromtimestamp(process.create_time())
            age = datetime.now() - create_time
            if age < timedelta(seconds=5):
                logger.warning(f"Process {pid} is very new ({age.total_seconds():.1f}s) - potential race condition")
                return True, f"Process {pid} is a recent scheduler"
            
            return True, f"Process {pid} is a valid scheduler"
            
        except psutil.NoSuchProcess:
            return False, f"Process {pid} no longer exists"
        except Exception as e:
            logger.error(f"Error checking process {pid}: {e}")
            return False, f"Error checking process {pid}: {e}"
    
    def _find_existing_schedulers(self) -> list[dict]:
        """Find all running scheduler processes on the system"""
        schedulers = []
        
        for process in psutil.process_iter(['pid', 'cmdline', 'create_time', 'cwd']):
            try:
                cmdline = ' '.join(process.info['cmdline'] or [])
                if 'scheduler.py' in cmdline and '--daemon' in cmdline:
                    is_valid, reason = self._is_scheduler_process(process.pid)
                    schedulers.append({
                        'pid': process.pid,
                        'cmdline': cmdline,
                        'cwd': process.info.get('cwd', 'unknown'),
                        'create_time': datetime.fromtimestamp(process.info['create_time']),
                        'valid': is_valid,
                        'reason': reason
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
                continue
        
        return schedulers
    
    def _cleanup_stale_locks(self) -> bool:
        """Clean up locks from dead or invalid processes"""
        cleaned = False
        
        # Clean up main lock file
        if self.lock_file.exists():
            try:
                with open(self.lock_file, 'r') as f:
                    lock_data = json.load(f)
                
                pid = lock_data.get('pid')
                timestamp = lock_data.get('timestamp')
                
                # Check process validity
                is_valid, reason = self._is_scheduler_process(pid) if pid else (False, "No PID in lock")
                
                if not is_valid:
                    logger.info(f"Removing stale lock: {reason}")
                    self.lock_file.unlink()
                    cleaned = True
                elif timestamp:
                    # Check timestamp staleness
                    lock_time = datetime.fromisoformat(timestamp)
                    age = datetime.now() - lock_time
                    if age > timedelta(hours=2):  # Locks older than 2 hours are stale
                        logger.warning(f"Removing old lock from {lock_time} (process {pid} may be hung)")
                        self.lock_file.unlink()
                        cleaned = True
            except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
                logger.warning(f"Invalid lock file: {e} - removing")
                try:
                    self.lock_file.unlink()
                    cleaned = True
                except FileNotFoundError:
                    pass
        
        # Clean up process info file
        if self.process_file.exists():
            try:
                with open(self.process_file, 'r') as f:
                    process_data = json.load(f)
                
                pid = process_data.get('pid')
                is_valid, reason = self._is_scheduler_process(pid) if pid else (False, "No PID in process file")
                
                if not is_valid:
                    logger.info(f"Removing stale process file: {reason}")
                    self.process_file.unlink()
                    cleaned = True
            except (json.JSONDecodeError, FileNotFoundError, KeyError):
                try:
                    self.process_file.unlink()
                    cleaned = True
                except FileNotFoundError:
                    pass
        
        return cleaned
    
    def acquire_lock(self) -> bool:
        """
        Acquire exclusive scheduler lock with enhanced duplicate detection
        Returns True if lock acquired successfully, False otherwise
        """
        try:
            # Step 1: Find all existing scheduler processes
            existing_schedulers = self._find_existing_schedulers()
            valid_schedulers = [s for s in existing_schedulers if s['valid']]
            
            if valid_schedulers:
                logger.error("Found existing scheduler processes:")
                for scheduler in valid_schedulers:
                    logger.error(f"  PID {scheduler['pid']}: {scheduler['cmdline']}")
                    logger.error(f"    CWD: {scheduler['cwd']}")
                    logger.error(f"    Started: {scheduler['create_time']}")
                return False
            
            # Step 2: Clean up any stale locks
            self._cleanup_stale_locks()
            
            # Step 3: Atomic lock acquisition with file locking
            try:
                self.lock_fd = open(self.lock_file, 'w+')
                flock(self.lock_fd, LOCK_EX | LOCK_NB)
                
                # Double-check no other process started after our check
                time.sleep(0.1)  # Brief pause to catch race conditions
                current_schedulers = self._find_existing_schedulers()
                current_valid = [s for s in current_schedulers if s['valid'] and s['pid'] != os.getpid()]
                
                if current_valid:
                    logger.error(f"Race condition detected: {len(current_valid)} scheduler(s) started during lock acquisition")
                    for scheduler in current_valid:
                        logger.error(f"  Conflicting PID {scheduler['pid']}: {scheduler['cmdline']}")
                    self._release_lock()
                    return False
                
                # Write lock data
                lock_data = {
                    'pid': os.getpid(),
                    'timestamp': datetime.now().isoformat(),
                    'hostname': socket.gethostname(),
                    'signature': self.process_signature,
                    'cmdline': ' '.join(sys.argv),
                    'cwd': os.getcwd()
                }
                
                self.lock_fd.seek(0)
                self.lock_fd.truncate()
                json.dump(lock_data, self.lock_fd, indent=2)
                self.lock_fd.flush()
                os.fsync(self.lock_fd.fileno())  # Force write to disk
                
                # Write process info file for additional validation
                with open(self.process_file, 'w') as f:
                    json.dump(lock_data, f, indent=2)
                
                logger.info(f"✅ Scheduler lock acquired successfully (PID: {os.getpid()})")
                return True
                
            except IOError as e:
                if "Resource temporarily unavailable" in str(e):
                    logger.error("Scheduler lock is held by another process")
                else:
                    logger.error(f"Failed to acquire scheduler lock: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error in lock acquisition: {e}")
            self._release_lock()
            return False
    
    def _release_lock(self):
        """Release the scheduler lock"""
        try:
            if self.lock_fd:
                flock(self.lock_fd, LOCK_UN)
                self.lock_fd.close()
                self.lock_fd = None
            
            # Remove lock files
            for file_path in [self.lock_file, self.process_file]:
                try:
                    file_path.unlink()
                except FileNotFoundError:
                    pass
            
            logger.info("Scheduler lock released")
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
    
    def release_lock(self):
        """Public interface to release lock"""
        self._release_lock()
    
    def __enter__(self):
        if not self.acquire_lock():
            raise RuntimeError("Could not acquire scheduler lock - another scheduler is running")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._release_lock()
    
    def get_status(self) -> dict:
        """Get current lock status and system scheduler information"""
        status = {
            'lock_file_exists': self.lock_file.exists(),
            'process_file_exists': self.process_file.exists(),
            'current_pid': os.getpid(),
            'existing_schedulers': self._find_existing_schedulers()
        }
        
        if self.lock_file.exists():
            try:
                with open(self.lock_file, 'r') as f:
                    status['lock_data'] = json.load(f)
            except Exception as e:
                status['lock_error'] = str(e)
        
        return status

def check_scheduler_processes():
    """Utility function to check for duplicate scheduler processes"""
    manager = SchedulerLockManager()
    status = manager.get_status()
    
    print("🔍 Scheduler Process Analysis")
    print("=" * 50)
    
    schedulers = status['existing_schedulers']
    if not schedulers:
        print("✅ No scheduler processes found")
        return
    
    print(f"Found {len(schedulers)} scheduler process(es):")
    for i, scheduler in enumerate(schedulers, 1):
        print(f"\n{i}. PID {scheduler['pid']}")
        print(f"   Command: {scheduler['cmdline']}")
        print(f"   Directory: {scheduler['cwd']}")
        print(f"   Started: {scheduler['create_time']}")
        print(f"   Status: {'✅ VALID' if scheduler['valid'] else '❌ INVALID'}")
        print(f"   Reason: {scheduler['reason']}")
    
    valid_count = sum(1 for s in schedulers if s['valid'])
    if valid_count > 1:
        print(f"\n⚠️  WARNING: {valid_count} valid scheduler processes detected!")
        print("This indicates a duplicate process issue.")
    elif valid_count == 1:
        print(f"\n✅ Single valid scheduler process detected (normal)")
    else:
        print(f"\n❌ No valid scheduler processes (all processes are invalid)")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        check_scheduler_processes()
    else:
        print("Usage: python3 scheduler_lock_manager.py --check")
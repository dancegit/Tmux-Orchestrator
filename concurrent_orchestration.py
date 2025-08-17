#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Concurrent orchestration support for Tmux Orchestrator
Provides file-based locking and UUID-namespaced sessions to prevent conflicts
"""

import os
import time
import uuid
import fcntl
import subprocess
import json
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FileLock:
    """Simple file-based lock implementation using fcntl"""
    
    def __init__(self, lock_file_path, timeout=30):
        self.lock_file_path = lock_file_path
        self.timeout = timeout
        self.lock_file = None
        self.acquired = False
        
    def __enter__(self):
        self.acquire()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        
    def acquire(self):
        """Acquire the lock with timeout"""
        start_time = time.time()
        
        # Create lock directory if it doesn't exist
        lock_dir = os.path.dirname(self.lock_file_path)
        os.makedirs(lock_dir, exist_ok=True)
        
        while True:
            try:
                # Try to create and lock the file
                self.lock_file = open(self.lock_file_path, 'w')
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Write PID and timestamp for debugging
                lock_info = {
                    'pid': os.getpid(),
                    'timestamp': datetime.now().isoformat(),
                    'hostname': os.uname().nodename
                }
                self.lock_file.write(json.dumps(lock_info))
                self.lock_file.flush()
                
                self.acquired = True
                logger.info(f"Acquired lock: {self.lock_file_path}")
                return
                
            except (IOError, OSError) as e:
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                    
                # Check timeout
                if time.time() - start_time > self.timeout:
                    raise TimeoutError(f"Could not acquire lock {self.lock_file_path} within {self.timeout}s")
                    
                # Check if lock is stale
                if self._is_lock_stale():
                    logger.warning(f"Removing stale lock: {self.lock_file_path}")
                    try:
                        os.remove(self.lock_file_path)
                    except OSError:
                        pass
                        
                time.sleep(0.5)
                
    def release(self):
        """Release the lock"""
        if self.lock_file and self.acquired:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                os.remove(self.lock_file_path)
                logger.info(f"Released lock: {self.lock_file_path}")
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")
            finally:
                self.lock_file = None
                self.acquired = False
                
    def _is_lock_stale(self, max_age_seconds=300):
        """Check if lock file is stale (older than max_age_seconds)"""
        try:
            if os.path.exists(self.lock_file_path):
                # Check file age
                file_age = time.time() - os.path.getmtime(self.lock_file_path)
                if file_age > max_age_seconds:
                    # Try to read lock info
                    try:
                        with open(self.lock_file_path, 'r') as f:
                            lock_info = json.loads(f.read())
                            pid = lock_info.get('pid')
                            
                            # Check if process is still alive
                            if pid and not self._is_process_alive(pid):
                                return True
                    except:
                        # If we can't read the lock file, consider it stale
                        return True
                        
        except OSError:
            pass
            
        return False
        
    def _is_process_alive(self, pid):
        """Check if a process with given PID is alive"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class ConcurrentOrchestrationManager:
    """Manages concurrent orchestrations with proper isolation"""
    
    def __init__(self, tmux_orchestrator_path):
        self.tmux_orchestrator_path = Path(tmux_orchestrator_path)
        self.lock_dir = self.tmux_orchestrator_path / 'locks'
        self.lock_dir.mkdir(exist_ok=True)
        
    def get_unique_session_name(self, project_name, check_tmux=True):
        """Generate a unique session name with UUID suffix"""
        base_name = self.sanitize_name(project_name)
        unique_id = str(uuid.uuid4())[:8]
        session_name = f"{base_name}-impl-{unique_id}"
        
        if check_tmux:
            # Verify it doesn't exist in tmux
            result = subprocess.run(
                ['tmux', 'has-session', '-t', session_name],
                capture_output=True
            )
            if result.returncode == 0:
                # Session exists, try again
                return self.get_unique_session_name(project_name, check_tmux)
                
        return session_name
        
    def get_unique_registry_dir(self, project_name, session_id=None):
        """Get unique registry directory for the project"""
        base_name = self.sanitize_name(project_name)
        if session_id:
            registry_dir = self.tmux_orchestrator_path / 'registry' / 'projects' / f"{base_name}-{session_id}"
        else:
            # Extract UUID from session name if available
            registry_dir = self.tmux_orchestrator_path / 'registry' / 'projects' / base_name
            
        return registry_dir
        
    def sanitize_name(self, name):
        """Sanitize project name for filesystem and tmux compatibility"""
        import re
        # Replace spaces and special characters with hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '-', name.lower())
        # Remove multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        return sanitized
        
    def acquire_project_lock(self, project_name, timeout=30):
        """Acquire a lock for the project"""
        lock_file = self.lock_dir / f"{self.sanitize_name(project_name)}.lock"
        return FileLock(str(lock_file), timeout)
        
    def start_orchestration(self, project_name, timeout=30):
        """Start a new orchestration with proper locking and isolation"""
        lock = self.acquire_project_lock(project_name, timeout)
        
        try:
            with lock:
                # Generate unique identifiers
                session_name = self.get_unique_session_name(project_name)
                session_id = session_name.split('-')[-1]  # Extract UUID part
                registry_dir = self.get_unique_registry_dir(project_name, session_id)
                
                # Create registry directory
                registry_dir.mkdir(parents=True, exist_ok=True)
                
                # Store orchestration metadata
                metadata = {
                    'project_name': project_name,
                    'session_name': session_name,
                    'session_id': session_id,
                    'registry_dir': str(registry_dir),
                    'created_at': datetime.now().isoformat(),
                    'pid': os.getpid()
                }
                
                metadata_file = registry_dir / 'orchestration_metadata.json'
                metadata_file.write_text(json.dumps(metadata, indent=2))
                
                logger.info(f"Started orchestration: {session_name} in {registry_dir}")
                return session_name, registry_dir
                
        except TimeoutError:
            raise Exception(f"Could not acquire lock for project {project_name} within {timeout}s. Another orchestration may be starting.")
            
    def list_active_orchestrations(self):
        """List all active orchestrations across projects"""
        orchestrations = []
        projects_dir = self.tmux_orchestrator_path / 'registry' / 'projects'
        
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    metadata_file = project_dir / 'orchestration_metadata.json'
                    state_file = project_dir / 'session_state.json'
                    
                    if metadata_file.exists():
                        try:
                            metadata = json.loads(metadata_file.read_text())
                            
                            # Check if session is still active
                            session_name = metadata.get('session_name')
                            if session_name:
                                result = subprocess.run(
                                    ['tmux', 'has-session', '-t', session_name],
                                    capture_output=True
                                )
                                metadata['active'] = result.returncode == 0
                            else:
                                metadata['active'] = False
                                
                            # Add session state info if available
                            if state_file.exists():
                                try:
                                    state = json.loads(state_file.read_text())
                                    metadata['agents'] = len(state.get('agents', {}))
                                    metadata['last_updated'] = state.get('updated_at')
                                except:
                                    pass
                                    
                            orchestrations.append(metadata)
                            
                        except Exception as e:
                            logger.error(f"Error reading metadata from {project_dir}: {e}")
                            
        return orchestrations
        
    def cleanup_stale_orchestrations(self, max_age_hours=24):
        """Clean up orchestrations older than max_age_hours with no active session"""
        cleaned = 0
        projects_dir = self.tmux_orchestrator_path / 'registry' / 'projects'
        
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    metadata_file = project_dir / 'orchestration_metadata.json'
                    
                    if metadata_file.exists():
                        try:
                            metadata = json.loads(metadata_file.read_text())
                            created_at = datetime.fromisoformat(metadata['created_at'])
                            age_hours = (datetime.now() - created_at).total_seconds() / 3600
                            
                            if age_hours > max_age_hours:
                                # Check if session is active
                                session_name = metadata.get('session_name')
                                if session_name:
                                    result = subprocess.run(
                                        ['tmux', 'has-session', '-t', session_name],
                                        capture_output=True
                                    )
                                    if result.returncode != 0:
                                        # Session not active, safe to clean
                                        logger.info(f"Cleaning stale orchestration: {project_dir}")
                                        import shutil
                                        shutil.rmtree(project_dir)
                                        cleaned += 1
                                        
                        except Exception as e:
                            logger.error(f"Error processing {project_dir}: {e}")
                            
        return cleaned


# CLI interface for testing
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Concurrent Orchestration Manager')
    parser.add_argument('--list', action='store_true', help='List active orchestrations')
    parser.add_argument('--cleanup', action='store_true', help='Clean up stale orchestrations')
    parser.add_argument('--start', metavar='PROJECT', help='Start a new orchestration')
    
    args = parser.parse_args()
    
    manager = ConcurrentOrchestrationManager(Path(__file__).parent)
    
    if args.list:
        orchestrations = manager.list_active_orchestrations()
        if orchestrations:
            print("Active Orchestrations:")
            print("-" * 80)
            for orch in orchestrations:
                status = "ACTIVE" if orch.get('active') else "INACTIVE"
                print(f"Project: {orch['project_name']} | Session: {orch['session_name']} | Status: {status}")
                print(f"  Created: {orch['created_at']} | Agents: {orch.get('agents', 'N/A')}")
                print(f"  Registry: {orch['registry_dir']}")
                print()
        else:
            print("No orchestrations found")
            
    elif args.cleanup:
        cleaned = manager.cleanup_stale_orchestrations()
        print(f"Cleaned up {cleaned} stale orchestrations")
        
    elif args.start:
        try:
            session_name, registry_dir = manager.start_orchestration(args.start)
            print(f"Started orchestration: {session_name}")
            print(f"Registry directory: {registry_dir}")
        except Exception as e:
            print(f"Error: {e}")
            
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
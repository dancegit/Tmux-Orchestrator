#!/usr/bin/env python3
"""
Systemd cleanup script for graceful scheduler shutdown
"""

import os
import sys
import signal
import time
import logging
import subprocess
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

LOCK_DIR = Path(__file__).parent / 'locks'
PID_FILE = LOCK_DIR / 'scheduler.pid'
LOCK_FILE = LOCK_DIR / 'project_queue.lock'

def read_pid():
    """Read the scheduler PID from file"""
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except (ValueError, IOError):
            return None
    return None

def is_process_running(pid):
    """Check if a process is running"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def cleanup_scheduler():
    """Perform graceful cleanup of scheduler"""
    logger.info("Starting scheduler cleanup...")
    
    # 1. Find scheduler process
    pid = read_pid()
    if not pid:
        logger.info("No PID file found - checking for running processes")
        # Try to find scheduler process
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'scheduler.py.*--daemon'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout:
                pid = int(result.stdout.strip().split('\n')[0])
                logger.info(f"Found scheduler process: {pid}")
        except Exception as e:
            logger.error(f"Failed to find scheduler process: {e}")
    
    # 2. Send graceful shutdown signal
    if pid and is_process_running(pid):
        logger.info(f"Sending SIGTERM to scheduler process {pid}")
        try:
            os.kill(pid, signal.SIGTERM)
            
            # Wait for graceful shutdown (up to 30 seconds)
            for i in range(30):
                if not is_process_running(pid):
                    logger.info(f"Scheduler process {pid} terminated gracefully")
                    break
                time.sleep(1)
            else:
                # Force kill if still running
                logger.warning(f"Scheduler process {pid} did not terminate, sending SIGKILL")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
                
        except OSError as e:
            logger.error(f"Failed to terminate scheduler process: {e}")
    
    # 3. Clean up lock files
    if LOCK_FILE.exists():
        logger.info(f"Removing lock file: {LOCK_FILE}")
        try:
            LOCK_FILE.unlink()
        except Exception as e:
            logger.error(f"Failed to remove lock file: {e}")
    
    if PID_FILE.exists():
        logger.info(f"Removing PID file: {PID_FILE}")
        try:
            PID_FILE.unlink()
        except Exception as e:
            logger.error(f"Failed to remove PID file: {e}")
    
    # 4. Clean up stale session data
    try:
        from session_state import SessionStateManager
        session_manager = SessionStateManager()
        session_manager.cleanup_stale_registries(age_threshold=3600)  # 1 hour
        logger.info("Cleaned up stale session registries")
    except Exception as e:
        logger.error(f"Failed to clean up session registries: {e}")
    
    # 5. Close any open database connections
    try:
        # Remove any stale database journal files
        db_files = [
            'task_queue.db-journal',
            'task_queue.db-wal',
            'task_queue.db-shm'
        ]
        for db_file in db_files:
            db_path = Path(__file__).parent / db_file
            if db_path.exists():
                logger.info(f"Removing database file: {db_path}")
                db_path.unlink()
    except Exception as e:
        logger.error(f"Failed to clean up database files: {e}")
    
    logger.info("Scheduler cleanup completed")

def create_systemd_service():
    """Create systemd service file for scheduler"""
    service_content = """[Unit]
Description=Tmux Orchestrator Scheduler
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={working_dir}
ExecStart={python} {scheduler_path} --daemon
ExecStop={python} {cleanup_script}
Restart=on-failure
RestartSec=10
StandardOutput=append:{log_dir}/scheduler.log
StandardError=append:{log_dir}/scheduler.log

# Graceful shutdown
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
""".format(
        user=os.environ.get('USER', 'root'),
        working_dir=Path(__file__).parent,
        python=sys.executable,
        scheduler_path=Path(__file__).parent / 'scheduler.py',
        cleanup_script=Path(__file__),
        log_dir=Path(__file__).parent / 'logs'
    )
    
    service_path = Path('/etc/systemd/system/tmux-orchestrator-scheduler.service')
    
    print("Systemd service configuration:")
    print("=" * 60)
    print(service_content)
    print("=" * 60)
    print(f"\nTo install this service:")
    print(f"1. Save the above content to: {service_path}")
    print(f"2. Run: sudo systemctl daemon-reload")
    print(f"3. Run: sudo systemctl enable tmux-orchestrator-scheduler")
    print(f"4. Run: sudo systemctl start tmux-orchestrator-scheduler")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--create-service':
        create_systemd_service()
    else:
        cleanup_scheduler()
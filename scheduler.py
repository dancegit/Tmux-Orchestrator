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
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))
from session_state import SessionStateManager, SessionState
from email_notifier import get_email_notifier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
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
        self.setup_database()
        
    def setup_database(self):
        """Initialize SQLite database for persistent task storage"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
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
                status TEXT DEFAULT 'queued',  -- queued, processing, completed, failed
                enqueued_at REAL DEFAULT (strftime('%s', 'now')),
                started_at REAL,
                completed_at REAL,
                priority INTEGER DEFAULT 0,  -- Higher = sooner
                error_message TEXT
            )
        ''')
        # Add indexes for performance
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_project_queue_status ON project_queue(status);')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_project_queue_priority ON project_queue(priority, enqueued_at);')
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
        
    def run_task(self, task_id, session_name, agent_role, window_index, note):
        """Execute a scheduled task"""
        try:
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
                
            # Use the send-claude-message.sh script if available
            send_script = self.tmux_orchestrator_path / "send-claude-message.sh"
            if send_script.exists():
                cmd = [str(send_script), f"{session_name}:{window_index}", message]
            else:
                # Fallback to direct tmux send-keys
                cmd = ['tmux', 'send-keys', '-t', f'{session_name}:{window_index}', message, 'Enter']
                
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Successfully executed task {task_id} for {agent_role}")
                # Update last_run time
                self.conn.execute("UPDATE tasks SET last_run = ? WHERE id = ?", 
                                (time.time(), task_id))
                self.conn.commit()
                return True
            else:
                logger.error(f"Failed to execute task {task_id}: {result.stderr}")
                return False
                
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
                    next_project = self.get_next_project()
                    if next_project:
                        project_start_time = time.time()
                        self.update_project_status(next_project['id'], 'processing')
                        
                        # Extract project name from spec path
                        spec_path = Path(next_project['spec_path'])
                        project_name = spec_path.stem
                        
                        try:
                            # Prepare project_path arg ('auto' if None)
                            proj_arg = next_project['project_path'] or 'auto'
                            
                            # Run auto_orchestrate.py as subprocess for the project
                            cmd = [
                                'uv', 'run', '--quiet', '--script',
                                str(self.tmux_orchestrator_path / 'auto_orchestrate.py'),
                                '--spec', next_project['spec_path'],
                                '--project', proj_arg
                            ]
                            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                            self.update_project_status(next_project['id'], 'completed')
                            logger.info(f"Completed project {next_project['id']}")
                            
                            # Track completion
                            completed_projects.append(f"{project_name} (ID: {next_project['id']})")
                            
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
    main()
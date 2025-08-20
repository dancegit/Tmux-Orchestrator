#!/usr/bin/env python3
"""
Heartbeat Monitor for Tmux Orchestrator
Detects and recovers from stuck projects (processing but no tmux session)
"""

import sqlite3
import subprocess
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HeartbeatMonitor:
    def __init__(self, db_path='task_queue.db', poll_interval=60, max_stuck_time=300):
        self.db_path = Path(db_path)
        self.poll_interval = poll_interval
        self.max_stuck_time = max_stuck_time  # seconds
        self.stop_event = threading.Event()
        
    def get_active_tmux_sessions(self) -> List[str]:
        """Get list of active tmux session names"""
        try:
            result = subprocess.run(
                ['tmux', 'list-sessions', '-F', '#{session_name}'], 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            return []
        except Exception as e:
            logger.error(f"Failed to get tmux sessions: {e}")
            return []
    
    def check_stuck_projects(self) -> List[Dict]:
        """Find projects marked as processing but without tmux sessions"""
        stuck_projects = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all processing projects
            cursor.execute("""
                SELECT id, spec_path, project_path, session_name,
                       CAST((julianday('now') - julianday(datetime(started_at, 'unixepoch'))) * 86400 AS INTEGER) as stuck_seconds
                FROM project_queue 
                WHERE status = 'processing'
            """)
            
            active_sessions = self.get_active_tmux_sessions()
            
            for row in cursor.fetchall():
                project_id, spec_path, project_path, session_name, stuck_seconds = row
                
                # Check if session exists
                session_exists = False
                if session_name:
                    session_exists = session_name in active_sessions
                else:
                    # No session name recorded - definitely stuck
                    session_exists = False
                
                if not session_exists and (stuck_seconds is None or stuck_seconds > self.max_stuck_time):
                    stuck_projects.append({
                        'id': project_id,
                        'spec_path': spec_path,
                        'project_path': project_path,
                        'session_name': session_name,
                        'stuck_seconds': stuck_seconds or 0
                    })
                    logger.warning(f"Stuck project detected: ID={project_id}, spec={spec_path}, stuck for {stuck_seconds}s")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Error checking stuck projects: {e}")
            
        return stuck_projects
    
    def fix_stuck_project(self, project: Dict) -> bool:
        """Mark stuck project as failed so it can be retried"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Update to failed status with error message
            cursor.execute("""
                UPDATE project_queue 
                SET status = 'failed', 
                    error_message = 'Heartbeat monitor: No tmux session found after ' || ? || ' seconds',
                    completed_at = strftime('%s', 'now')
                WHERE id = ?
            """, (project['stuck_seconds'], project['id']))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Fixed stuck project {project['id']} - marked as failed for retry")
            return True
            
        except Exception as e:
            logger.error(f"Failed to fix stuck project {project['id']}: {e}")
            return False
    
    def run_once(self):
        """Run one heartbeat check cycle"""
        logger.debug("Running heartbeat check...")
        
        stuck_projects = self.check_stuck_projects()
        
        if stuck_projects:
            logger.info(f"Found {len(stuck_projects)} stuck project(s)")
            
            for project in stuck_projects:
                if self.fix_stuck_project(project):
                    logger.info(f"Successfully recovered project {project['id']}")
                else:
                    logger.error(f"Failed to recover project {project['id']}")
        else:
            logger.debug("No stuck projects found")
    
    def run(self):
        """Run continuous heartbeat monitoring"""
        logger.info(f"Starting heartbeat monitor (interval={self.poll_interval}s, max_stuck={self.max_stuck_time}s)")
        
        while not self.stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")
            
            # Wait for next poll or stop signal
            self.stop_event.wait(self.poll_interval)
        
        logger.info("Heartbeat monitor stopped")
    
    def stop(self):
        """Stop the monitoring thread"""
        self.stop_event.set()

def main():
    """Run heartbeat monitor as standalone process"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Heartbeat monitor for Tmux Orchestrator')
    parser.add_argument('--interval', type=int, default=60, help='Poll interval in seconds')
    parser.add_argument('--max-stuck', type=int, default=300, help='Max seconds before marking as stuck')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    
    args = parser.parse_args()
    
    monitor = HeartbeatMonitor(
        poll_interval=args.interval,
        max_stuck_time=args.max_stuck
    )
    
    if args.once:
        monitor.run_once()
    else:
        try:
            monitor.run()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            monitor.stop()

if __name__ == '__main__':
    main()
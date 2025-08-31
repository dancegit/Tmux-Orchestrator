#!/usr/bin/env python3
"""
Project Health Monitor - Continuous monitoring and automatic recovery for orchestrated projects
Runs every 30 minutes to detect and fix issues with projects in the queue
"""

import sqlite3
import subprocess
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('project_health_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProjectHealthMonitor:
    def __init__(self):
        self.db_path = Path('task_queue.db')
        self.orchestrator_path = Path(__file__).parent
        
    def get_failed_projects(self) -> List[Dict]:
        """Get all failed projects from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, session_name, status, error_message, spec_path, completed_at
            FROM project_queue 
            WHERE status = 'failed'
            ORDER BY id DESC
        ''')
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        conn.close()
        return results
    
    def get_processing_projects(self) -> List[Dict]:
        """Get all processing projects to check for false positives"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, session_name, status, started_at, spec_path
            FROM project_queue 
            WHERE status = 'processing'
            ORDER BY id DESC
        ''')
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        conn.close()
        return results
    
    def check_tmux_session_exists(self, session_name: str) -> bool:
        """Check if a tmux session exists"""
        if not session_name:
            return False
            
        try:
            result = subprocess.run(
                ['tmux', 'has-session', '-t', session_name],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def check_for_stuck_processes(self, session_name: str) -> Dict:
        """Check if a session has stuck agents or other issues"""
        if not session_name:
            return {'stuck': False, 'reason': 'No session name'}
            
        try:
            # Check agent health
            from agent_health_monitor import AgentHealthMonitor
            health_monitor = AgentHealthMonitor()
            health_status = health_monitor.check_agent_health(session_name)
            
            if health_status:
                stuck_agents = [
                    name for name, status in health_status.items()
                    if status.get('is_stuck', False) and status.get('stuck_duration', 0) > 1800
                ]
                
                active_agents = [
                    name for name, status in health_status.items()
                    if status.get('has_claude', False) and not status.get('is_stuck', False)
                ]
                
                if stuck_agents and not active_agents:
                    return {
                        'stuck': True,
                        'reason': f"All agents stuck: {', '.join(stuck_agents)}",
                        'agents': stuck_agents
                    }
                elif stuck_agents:
                    return {
                        'stuck': False,
                        'reason': f"Some agents stuck but others active",
                        'stuck_agents': stuck_agents,
                        'active_agents': active_agents
                    }
            
            return {'stuck': False, 'reason': 'No stuck agents detected'}
            
        except Exception as e:
            logger.error(f"Error checking stuck processes: {e}")
            return {'stuck': False, 'reason': f'Check failed: {e}'}
    
    def analyze_failure(self, project: Dict) -> Dict:
        """Analyze why a project failed and determine recovery strategy"""
        error_msg = project.get('error_message', '')
        session_name = project.get('session_name', '')
        
        analysis = {
            'project_id': project['id'],
            'session_name': session_name,
            'error': error_msg,
            'recovery_strategy': 'reset',
            'confidence': 0.5
        }
        
        # Check if session exists
        session_exists = self.check_tmux_session_exists(session_name)
        
        if 'no tmux session was created' in error_msg.lower() and not session_exists:
            analysis['recovery_strategy'] = 'reset'
            analysis['confidence'] = 0.9
            analysis['reason'] = 'Session creation failed, needs reset'
            
        elif 'subprocess failed' in error_msg.lower():
            analysis['recovery_strategy'] = 'reset'
            analysis['confidence'] = 0.8
            analysis['reason'] = 'Subprocess failure, needs reset'
            
        elif session_exists:
            # Session exists but marked as failed - could be false positive
            stuck_check = self.check_for_stuck_processes(session_name)
            
            if stuck_check['stuck']:
                analysis['recovery_strategy'] = 'restart_agents'
                analysis['confidence'] = 0.7
                analysis['reason'] = stuck_check['reason']
            else:
                # Likely false positive
                analysis['recovery_strategy'] = 'update_status'
                analysis['confidence'] = 0.8
                analysis['reason'] = 'Session active but marked failed - false positive'
        
        return analysis
    
    def reset_project(self, project_id: int) -> bool:
        """Reset a failed project"""
        try:
            logger.info(f"Resetting project {project_id}...")
            result = subprocess.run(
                ['python3', 'queue_status.py', '--reset', str(project_id)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully reset project {project_id}")
                return True
            else:
                logger.error(f"Failed to reset project {project_id}: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error resetting project {project_id}: {e}")
            return False
    
    def update_project_status(self, project_id: int, new_status: str, reason: str = None) -> bool:
        """Update a project's status in the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if new_status == 'processing':
                cursor.execute('''
                    UPDATE project_queue 
                    SET status = ?,
                        error_message = NULL,
                        completed_at = NULL
                    WHERE id = ?
                ''', (new_status, project_id))
            else:
                cursor.execute('''
                    UPDATE project_queue 
                    SET status = ?,
                        error_message = ?
                    WHERE id = ?
                ''', (new_status, reason, project_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated project {project_id} status to {new_status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating project {project_id} status: {e}")
            return False
    
    def check_false_positives(self) -> List[Dict]:
        """Check processing projects for false positive failures"""
        processing = self.get_processing_projects()
        false_positives = []
        
        for project in processing:
            if project.get('started_at'):
                # Check if it's been processing for too long (>4 hours)
                started = datetime.fromtimestamp(project['started_at'])
                if datetime.now() - started > timedelta(hours=4):
                    session_exists = self.check_tmux_session_exists(project['session_name'])
                    
                    if not session_exists:
                        false_positives.append({
                            'project': project,
                            'issue': 'Long running but no session',
                            'action': 'mark_failed'
                        })
                    else:
                        stuck_check = self.check_for_stuck_processes(project['session_name'])
                        if stuck_check['stuck']:
                            false_positives.append({
                                'project': project,
                                'issue': stuck_check['reason'],
                                'action': 'restart_or_fail'
                            })
        
        return false_positives
    
    def monitor_cycle(self):
        """Main monitoring cycle"""
        logger.info("=" * 60)
        logger.info("Starting health monitoring cycle")
        
        # Check failed projects
        failed = self.get_failed_projects()
        logger.info(f"Found {len(failed)} failed projects")
        
        for project in failed:
            logger.info(f"\nAnalyzing failed project {project['id']}: {project.get('session_name', 'no session')}")
            
            analysis = self.analyze_failure(project)
            logger.info(f"  Strategy: {analysis['recovery_strategy']} (confidence: {analysis['confidence']:.1f})")
            logger.info(f"  Reason: {analysis['reason']}")
            
            # Apply recovery strategy
            if analysis['confidence'] >= 0.7:
                if analysis['recovery_strategy'] == 'reset':
                    if self.reset_project(project['id']):
                        logger.info(f"  ✅ Reset project {project['id']}")
                    else:
                        logger.error(f"  ❌ Failed to reset project {project['id']}")
                        
                elif analysis['recovery_strategy'] == 'update_status':
                    if self.update_project_status(project['id'], 'processing', 
                                                   f"False positive corrected: {analysis['reason']}"):
                        logger.info(f"  ✅ Updated project {project['id']} to processing")
                    else:
                        logger.error(f"  ❌ Failed to update project {project['id']}")
            else:
                logger.info(f"  ⚠️  Low confidence ({analysis['confidence']:.1f}), skipping automatic action")
        
        # Check for false positives in processing projects
        false_positives = self.check_false_positives()
        if false_positives:
            logger.info(f"\nFound {len(false_positives)} potential false positives")
            
            for fp in false_positives:
                project = fp['project']
                logger.info(f"  Project {project['id']}: {fp['issue']}")
                
                if fp['action'] == 'mark_failed':
                    self.update_project_status(project['id'], 'failed', fp['issue'])
        
        logger.info("\nMonitoring cycle complete")
        logger.info("=" * 60)
    
    def run_continuous(self, interval_minutes: int = 30):
        """Run continuous monitoring"""
        logger.info(f"Starting continuous monitoring (interval: {interval_minutes} minutes)")
        
        while True:
            try:
                self.monitor_cycle()
                
                # Wait for next cycle
                logger.info(f"Waiting {interval_minutes} minutes until next check...")
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                logger.info("Waiting 5 minutes before retry...")
                time.sleep(300)

def main():
    monitor = ProjectHealthMonitor()
    
    if '--once' in sys.argv:
        # Run once for testing
        monitor.monitor_cycle()
    else:
        # Run continuously
        monitor.run_continuous(interval_minutes=30)

if __name__ == '__main__':
    main()
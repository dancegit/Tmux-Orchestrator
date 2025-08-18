#!/usr/bin/env python3
"""
Self-check-in monitoring system for Tmux Orchestrator.
Monitors scheduled check-ins and intervenes when projects are stuck.
"""

import subprocess
import sqlite3
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json

from session_state import SessionStateManager, SessionState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CheckinMonitor:
    """Monitors agent check-ins and detects stuck projects"""
    
    def __init__(self, tmux_orchestrator_path: Path):
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.state_manager = SessionStateManager(tmux_orchestrator_path)
        self.scheduler_db = self.tmux_orchestrator_path / 'task_queue.db'
        
        # Thresholds for intervention
        self.stuck_threshold_hours = 2  # Project considered stuck after 2 hours
        self.checkin_warning_minutes = 45  # Warning if no check-in scheduled within 45 min
        
        # Emergency check-in strategy
        self.emergency_strategy = 'hybrid'  # 'one-time', 'recurring', 'hybrid'
        self.emergency_intervals = [0, 30, 60]  # Minutes: immediate, then 30min, then 60min
        self.max_emergencies = 3  # Max number of emergency attempts
        self.recovery_signals_required = 1  # Min signals needed to confirm recovery (reduced for faster backing off)
        self.emergency_tracker = {}  # Track per-session emergency count and last sent time
        
    def get_active_sessions(self) -> List[str]:
        """Get list of active tmux sessions"""
        try:
            result = subprocess.run(
                ['tmux', 'list-sessions', '-F', '#{session_name}'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return [s.strip() for s in result.stdout.strip().split('\n') if s.strip()]
            return []
        except:
            return []
    
    def get_scheduled_checkins(self, session_name: str) -> List[Dict]:
        """Get all scheduled check-ins for a session"""
        if not self.scheduler_db.exists():
            return []
        
        try:
            conn = sqlite3.connect(str(self.scheduler_db))
            cursor = conn.cursor()
            
            # Get all tasks for this session
            cursor.execute("""
                SELECT id, agent_role, window_index, next_run, interval_minutes, note
                FROM tasks
                WHERE session_name = ?
                ORDER BY next_run
            """, (session_name,))
            
            tasks = []
            for row in cursor.fetchall():
                # Handle timestamp format - could be epoch or ISO format
                try:
                    if isinstance(row[3], (int, float)):
                        next_run = datetime.fromtimestamp(row[3])
                    else:
                        next_run = datetime.fromisoformat(row[3])
                except:
                    next_run = datetime.now()
                
                tasks.append({
                    'id': row[0],
                    'role': row[1],
                    'window': row[2],
                    'next_run': next_run,
                    'interval': row[4],
                    'note': row[5]
                })
            
            conn.close()
            return tasks
        except Exception as e:
            logger.error(f"Error reading scheduler database: {e}")
            return []
    
    def get_last_activity(self, session_name: str, window: int) -> Optional[datetime]:
        """Get last activity time for a window"""
        try:
            # Capture the last line and check for activity
            result = subprocess.run([
                'tmux', 'capture-pane', '-t', f'{session_name}:{window}', 
                '-p', '-S', '-1'
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                # For now, assume current time if there's output
                # In practice, you'd parse timestamps from the output
                return datetime.now()
            return None
        except:
            return None
    
    def check_project_health(self, session_name: str, state: SessionState) -> Dict:
        """Check overall health of a project"""
        health = {
            'session_name': session_name,
            'status': 'healthy',
            'issues': [],
            'recommendations': []
        }
        
        # Check 1: Are there scheduled check-ins?
        checkins = self.get_scheduled_checkins(session_name)
        if not checkins:
            health['status'] = 'critical'
            health['issues'].append("No scheduled check-ins found")
            health['recommendations'].append("Schedule emergency check-ins for all agents")
        else:
            # Check 2: Are check-ins happening soon enough?
            next_checkin = min(checkins, key=lambda x: x['next_run'])
            time_to_next = (next_checkin['next_run'] - datetime.now()).total_seconds() / 60
            
            if time_to_next > self.checkin_warning_minutes:
                health['status'] = 'warning'
                health['issues'].append(f"Next check-in not for {time_to_next:.0f} minutes")
                health['recommendations'].append("Schedule more frequent check-ins")
        
        # Check 3: How long has the project been running?
        if hasattr(state, 'created_at'):
            created = datetime.fromisoformat(state.created_at.replace('Z', '+00:00'))
            hours_running = (datetime.now() - created).total_seconds() / 3600
            
            if hours_running > self.stuck_threshold_hours:
                # Check if there's been recent activity
                orchestrator_active = self.get_last_activity(session_name, 0)
                if not orchestrator_active or (datetime.now() - orchestrator_active).total_seconds() > 3600:
                    health['status'] = 'critical'
                    health['issues'].append(f"Project running for {hours_running:.1f} hours with no recent activity")
                    health['recommendations'].append("Perform emergency intervention")
        
        # Check 4: Are agents responsive?
        for role, agent in state.agents.items():
            if hasattr(agent, 'is_alive') and not agent.is_alive:
                health['status'] = 'warning' if health['status'] == 'healthy' else health['status']
                health['issues'].append(f"{role} agent is not alive")
                health['recommendations'].append(f"Restart {role} agent")
        
        # Check for recovery if emergency was previously sent
        if session_name in self.emergency_tracker:
            recovery_signals = self.detect_recovery_signals(session_name)
            if len(recovery_signals) >= self.recovery_signals_required:
                health['status'] = 'recovered'
                health['recovery_signals'] = recovery_signals
                self.handle_recovery(session_name)
            else:
                health['recovery_signals'] = recovery_signals
        
        return health
    
    def schedule_emergency_checkin(self, session_name: str, window: int, role: str, interval: int = None):
        """Schedule an emergency check-in with dynamic interval"""
        if interval is None:
            # Get the appropriate interval based on emergency level
            level = self.emergency_tracker.get(session_name, {}).get('count', 0)
            interval = self.emergency_intervals[min(level, len(self.emergency_intervals) - 1)]
        
        logger.info(f"Scheduling emergency check-in for {session_name}:{window} ({role}) in {interval} minutes")
        
        # Use the schedule_with_note.sh script
        cmd = [
            str(self.tmux_orchestrator_path / 'schedule_with_note.sh'),
            str(interval),
            f"EMERGENCY CHECK-IN (Level {self.emergency_tracker.get(session_name, {}).get('count', 0) + 1}): Project may be stuck. Please report status immediately.",
            f"{session_name}:{window}"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Emergency check-in scheduled successfully")
            else:
                logger.error(f"Failed to schedule emergency check-in: {result.stderr}")
        except Exception as e:
            logger.error(f"Error scheduling emergency check-in: {e}")
    
    def force_immediate_checkin(self, session_name: str, window: int, role: str):
        """Force an immediate check-in using intelligent briefing system"""
        logger.warning(f"Forcing immediate intelligent briefing for {session_name}:{window} ({role})")
        
        # Use intelligent briefing system for meaningful, context-rich messages
        try:
            briefing_script = self.tmux_orchestrator_path / 'intelligent_briefing.py'
            if briefing_script.exists():
                result = subprocess.run([
                    'python3',
                    str(briefing_script),
                    session_name,
                    role,
                    str(window)
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"Intelligent briefing sent to {role}")
                else:
                    logger.error(f"Failed to send intelligent briefing: {result.stderr}")
                    # Fallback to basic message
                    self._send_basic_emergency_message(session_name, window, role)
            else:
                logger.warning("Intelligent briefing system not available, using basic message")
                self._send_basic_emergency_message(session_name, window, role)
                
        except Exception as e:
            logger.error(f"Error with intelligent briefing: {e}")
            self._send_basic_emergency_message(session_name, window, role)
    
    def _send_basic_emergency_message(self, session_name: str, window: int, role: str):
        """Fallback basic emergency message"""
        message = f"""URGENT: Emergency status check required!

Project monitoring detected issues - need immediate response.
1. What are you currently working on?
2. Are you blocked on anything? 
3. What's your next step?

If you're the Orchestrator: cd {self.tmux_orchestrator_path} && python3 claude_control.py status detailed"""
        
        send_script = self.tmux_orchestrator_path / 'send-claude-message.sh'
        if send_script.exists():
            try:
                result = subprocess.run([
                    str(send_script),
                    f"{session_name}:{window}",
                    message
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"Basic emergency message sent to {role}")
                else:
                    logger.error(f"Failed to send basic message: {result.stderr}")
            except Exception as e:
                logger.error(f"Error sending basic message: {e}")
    
    def detect_recovery_signals(self, session_name: str) -> List[str]:
        """Detect signals that indicate project has recovered"""
        signals = []
        
        try:
            # Signal 1: Recent scheduled check-ins (non-emergency)
            checkins = self.get_scheduled_checkins(session_name)
            normal_checkins = [c for c in checkins if 'EMERGENCY' not in c.get('note', '')]
            if normal_checkins:
                next_checkin = min(normal_checkins, key=lambda x: x['next_run'])
                time_to_next = (next_checkin['next_run'] - datetime.now()).total_seconds() / 60
                if time_to_next < self.checkin_warning_minutes:
                    signals.append('scheduled_checkins')
            
            # Signal 2: Recent activity in ANY agent window (not just orchestrator)
            try:
                # Check orchestrator and a few key agent windows for activity
                for window in [0, 1, 5]:  # orchestrator, PM, developer
                    result = subprocess.run([
                        'tmux', 'capture-pane', '-t', f'{session_name}:{window}', 
                        '-p', '-S', '-10'
                    ], capture_output=True, text=True)
                    
                    if result.returncode == 0 and result.stdout.strip():
                        # Look for signs of recent AI activity
                        output = result.stdout.lower()
                        activity_indicators = [
                            'human:', 'assistant:', '●', '✅', '🚨', 
                            'analyzing', 'implementing', 'checking', 'working on',
                            'i will', 'i\'ll', 'let me', 'starting', 'completed'
                        ]
                        if any(indicator in output for indicator in activity_indicators):
                            signals.append('recent_activity')
                            break
            except:
                pass
            
            # Signal 3: No emergency tasks currently scheduled
            emergency_checkins = [c for c in checkins if 'EMERGENCY' in c.get('note', '')]
            if not emergency_checkins:
                signals.append('no_emergency_tasks')
            
            # Signal 4: Project might be completed (check for completion indicators)
            try:
                result = subprocess.run([
                    'tmux', 'capture-pane', '-t', f'{session_name}:0', 
                    '-p', '-S', '-20'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    output = result.stdout.lower()
                    completion_indicators = [
                        'project is complete', 'already complete', 'finished',
                        'all done', 'completed successfully', 'project done'
                    ]
                    if any(indicator in output for indicator in completion_indicators):
                        signals.append('project_completed')
            except:
                pass
            
        except Exception as e:
            logger.error(f"Error detecting recovery signals for {session_name}: {e}")
        
        return signals
    
    def handle_recovery(self, session_name: str):
        """Handle recovery - cancel emergencies and clean up tracking"""
        logger.info(f"Project {session_name} has recovered! Cancelling emergency interventions.")
        
        # Remove from emergency tracker
        if session_name in self.emergency_tracker:
            del self.emergency_tracker[session_name]
        
        # TODO: Cancel pending emergency tasks in scheduler (would need scheduler.py enhancement)
        # For now, we rely on the fact that new check-ins indicate recovery
    
    def handle_stuck_project(self, session_name: str, state: SessionState, health: Dict):
        """Handle stuck project with intelligent escalation"""
        if health['status'] not in ['warning', 'critical']:
            return
        
        # Initialize tracking if needed
        if session_name not in self.emergency_tracker:
            self.emergency_tracker[session_name] = {
                'count': 0,
                'last_sent': None,
                'first_detected': datetime.now().isoformat()
            }
        
        tracker = self.emergency_tracker[session_name]
        
        # Check if we've exceeded max emergencies
        if tracker['count'] >= self.max_emergencies:
            logger.warning(f"Project {session_name} unresponsive after {self.max_emergencies} emergency attempts")
            # TODO: Escalate to email notification or mark as failed
            return
        
        # Determine if it's time for next emergency level
        level = tracker['count']
        interval = self.emergency_intervals[min(level, len(self.emergency_intervals) - 1)]
        
        # For immediate (level 0), send right away
        # For others, check if enough time has passed since last emergency
        should_send = False
        if level == 0:
            should_send = True
        elif tracker['last_sent']:
            last_sent = datetime.fromisoformat(tracker['last_sent'])
            minutes_since = (datetime.now() - last_sent).total_seconds() / 60
            # Send next level if it's been long enough
            if minutes_since >= self.emergency_intervals[level - 1]:
                should_send = True
        
        if should_send:
            logger.warning(f"Initiating emergency level {level + 1} for {session_name}")
            
            if level == 0:
                # First intervention: immediate wake-up message
                self.force_immediate_checkin(session_name, 0, 'orchestrator')
            else:
                # Subsequent interventions: schedule future check-ins
                self.schedule_emergency_checkin(session_name, 0, 'orchestrator', interval)
            
            # Update tracking
            tracker['count'] += 1
            tracker['last_sent'] = datetime.now().isoformat()
    
    def monitor_all_projects(self):
        """Monitor all active projects and intervene as needed"""
        logger.info("Starting project health check...")
        
        active_sessions = self.get_active_sessions()
        
        # Filter for orchestrator sessions
        orchestrator_sessions = [s for s in active_sessions if 'impl' in s and s != 'tmux-orchestrator-server']
        
        interventions_needed = []
        
        for session in orchestrator_sessions:
            # Extract project name from session name
            parts = session.split('-impl-')
            if len(parts) > 0:
                project_name = parts[0].replace('-', ' ').title()
                
                # Load session state
                state = self.state_manager.load_session_state(project_name)
                if not state:
                    logger.warning(f"No state found for {session}")
                    continue
                
                # Check if project is already completed
                if hasattr(state, 'completion_status') and state.completion_status in ['completed', 'failed']:
                    logger.info(f"Skipping {session} - already {state.completion_status}")
                    continue
                
                # Check project health
                health = self.check_project_health(session, state)
                
                logger.info(f"\nProject: {project_name}")
                logger.info(f"Session: {session}")
                logger.info(f"Status: {health['status']}")
                
                if health['issues']:
                    logger.warning(f"Issues: {health['issues']}")
                    logger.info(f"Recommendations: {health['recommendations']}")
                
                # Handle stuck projects intelligently
                if health['status'] in ['warning', 'critical']:
                    self.handle_stuck_project(session, state, health)
                    if health['status'] == 'critical':
                        interventions_needed.append(session)
        
        return len(interventions_needed)
    
    def run_continuous_monitoring(self, interval_minutes: int = 30):
        """Run continuous monitoring"""
        logger.info(f"Starting continuous check-in monitoring (interval: {interval_minutes} minutes)")
        
        while True:
            try:
                interventions = self.monitor_all_projects()
                if interventions > 0:
                    logger.info(f"Performed {interventions} interventions")
                else:
                    logger.info("All projects healthy")
                
                # Sleep until next check
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Brief pause before retry

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor Tmux Orchestrator check-ins')
    parser.add_argument('--once', action='store_true', help='Run once instead of continuous monitoring')
    parser.add_argument('--interval', type=int, default=30, help='Monitoring interval in minutes (default: 30)')
    parser.add_argument('--force-checkin', nargs=2, metavar=('SESSION', 'WINDOW'), 
                       help='Force immediate check-in for specific window')
    
    args = parser.parse_args()
    
    tmux_orchestrator_path = Path(__file__).parent
    monitor = CheckinMonitor(tmux_orchestrator_path)
    
    if args.force_checkin:
        session, window = args.force_checkin
        monitor.force_immediate_checkin(session, int(window), 'manual')
    elif args.once:
        monitor.monitor_all_projects()
    else:
        monitor.run_continuous_monitoring(args.interval)

if __name__ == '__main__':
    main()
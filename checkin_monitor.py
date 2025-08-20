#!/usr/bin/env python3
"""
Self-check-in monitoring system for Tmux Orchestrator.
Monitors scheduled check-ins and intervenes when projects are stuck.
"""

import subprocess
import sqlite3
import time
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import json

from session_state import SessionStateManager, SessionState
from cycle_detection import CycleDetector
from git_coordinator import GitCoordinator

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
        self.cycle_detector = CycleDetector(tmux_orchestrator_path)
        self.git_coordinator = GitCoordinator(tmux_orchestrator_path)  # Initialize git coordinator
        self.scheduler_db = self.tmux_orchestrator_path / 'task_queue.db'
        
        # Thresholds for intervention
        self.stuck_threshold_hours = float(os.getenv('STUCK_THRESHOLD_HOURS', '0.5'))  # Project considered stuck after 30 minutes (was 2 hours)
        self.checkin_warning_minutes = 45  # Warning if no check-in scheduled within 45 min
        
        # Emergency check-in strategy
        self.emergency_strategy = 'hybrid'  # 'one-time', 'recurring', 'hybrid'
        self.emergency_intervals = [0, 5, 15]  # Minutes: immediate, then 5min, then 15min (optimized for 2-min monitoring)
        self.max_emergencies = 3  # Max number of emergency attempts
        self.recovery_signals_required = 1  # Min signals needed to confirm recovery (reduced for faster backing off)
        self.emergency_tracker = {}  # Track per-session emergency count and last sent time
        
        # Idle detection and nudging (optimized for 2-minute monitoring)  
        self.idle_threshold_minutes = float(os.getenv('IDLE_THRESHOLD_MINUTES', '3'))  # No activity in this time = idle (was 5 minutes)
        self.nudge_cooldown_minutes = 6  # Min time between nudges (allows nudge every 3 monitoring cycles)
        self.nudge_tracker = {}  # {session_name: last_nudge_time isoformat}
        
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
    
    def _is_session_alive(self, session_name: str) -> bool:
        """Check if the tmux session exists and is active."""
        active_sessions = self.get_active_sessions()
        if session_name not in active_sessions:
            logger.warning(f"Session {session_name} is dead - skipping monitoring and escalating to failure")
            # Extract project name from session name
            parts = session_name.split('-impl-')
            if len(parts) > 0:
                project_name = parts[0].replace('-', ' ').title()
                state = self.state_manager.load_session_state(project_name)
                if state and state.completion_status not in ['completed', 'failed']:
                    # Escalate to failure handler to clean up state
                    try:
                        from project_failure_handler import ProjectFailureHandler
                        handler = ProjectFailureHandler(self.tmux_orchestrator_path)
                        handler.handle_timeout_failure(project_name, state)
                        logger.info(f"Escalated dead session {session_name} to failure handler")
                    except Exception as e:
                        logger.error(f"Failed to escalate dead session to failure handler: {e}")
            return False
        return True
    
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
        """Get last activity time for a window (enhanced to return actual timestamp if possible)"""
        try:
            # Capture last 10 lines for better detection
            result = subprocess.run([
                'tmux', 'capture-pane', '-t', f'{session_name}:{window}', 
                '-p', '-S', '-10'
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.lower()
                activity_indicators = [
                    'human:', 'assistant:', '●', '✅', '🚨', 
                    'analyzing', 'implementing', 'checking', 'working on',
                    'i will', 'i\'ll', 'let me', 'starting', 'completed',
                    'bash(', 'edit(', 'read(', 'write(', 'grep(',
                    'scheduled check-in:', 'status update:'
                ]
                if any(indicator in output for indicator in activity_indicators):
                    return datetime.now()  # Recent activity detected
            return None  # No activity
        except:
            return None
    
    def is_team_idle(self, session_name: str, state: SessionState) -> bool:
        """Check if ALL agents in the team are idle (no recent activity)"""
        if not state or not state.agents:
            return False
        
        now = datetime.now()
        active_agents = 0
        idle_agents = []
        
        for role, agent in state.agents.items():
            window = agent.window_index if hasattr(agent, 'window_index') else None
            if window is None:
                continue  # Skip if no window
                
            last_active = self.get_last_activity(session_name, window)
            if last_active and (now - last_active).total_seconds() / 60 < self.idle_threshold_minutes:
                active_agents += 1
            else:
                idle_agents.append(f"{role} (window {window})")
        
        # Log idle status
        if active_agents == 0 and len(state.agents) > 0:
            logger.info(f"All agents idle in {session_name}: {', '.join(idle_agents)}")
            return True
        
        return False
    
    def nudge_idle_project(self, session_name: str, health: Dict):
        """Reschedule the earliest check-in to ASAP if team is idle"""
        now = datetime.now()
        
        # Check cooldown
        if session_name in self.nudge_tracker:
            last_nudge = datetime.fromisoformat(self.nudge_tracker[session_name])
            if (now - last_nudge).total_seconds() / 60 < self.nudge_cooldown_minutes:
                logger.debug(f"Skipping nudge for {session_name} - cooldown active")
                return  # Too soon
        
        # Get scheduled check-ins (non-emergency)
        checkins = [c for c in self.get_scheduled_checkins(session_name) 
                    if 'EMERGENCY' not in c.get('note', '') and 'IDLE NUDGE' not in c.get('note', '')]
        if not checkins:
            # No check-ins: Fall back to emergency
            logger.warning(f"Idle project {session_name}: No check-ins, scheduling emergency nudge")
            self.schedule_emergency_checkin(session_name, 0, 'orchestrator', 1)
            self.nudge_tracker[session_name] = now.isoformat()
            return
        
        # Find earliest
        earliest = min(checkins, key=lambda x: x['next_run'])
        time_to_earliest = (earliest['next_run'] - now).total_seconds() / 60
        
        if time_to_earliest < 5:  # Already soon, no need to nudge
            logger.debug(f"Next check-in for {session_name} already in {time_to_earliest:.1f} minutes")
            return
        
        # Reschedule to 1 minute from now
        new_next_run = now + timedelta(minutes=1)
        try:
            conn = sqlite3.connect(str(self.scheduler_db))
            cursor = conn.cursor()
            
            # Update with IDLE NUDGE note
            new_note = f"IDLE NUDGE: Team appears idle, please check in ASAP (was: {earliest['note'] or 'Regular check-in'})"
            cursor.execute("""
                UPDATE tasks 
                SET next_run = ?, note = ?
                WHERE id = ?
            """, (new_next_run.timestamp(), new_note, earliest['id']))
            conn.commit()
            conn.close()
            
            self.nudge_tracker[session_name] = now.isoformat()
            logger.warning(f"Idle project {session_name}: Nudged task {earliest['id']} ({earliest['role']}) to run in 1 minute")
            health['issues'].append("Team appears idle - nudged next check-in")
            health['recommendations'].append("Monitor for response after nudge")
        except Exception as e:
            logger.error(f"Failed to nudge {session_name}: {e}")
    
    def check_project_health(self, session_name: str, state: SessionState) -> Dict:
        """Check overall health of a project"""
        # Skip monitoring failed sessions to prevent resource waste and repeated timeout triggers
        if state and hasattr(state, 'completion_status') and state.completion_status == "failed":
            return {
                'session_name': session_name,
                'status': 'failed',
                'issues': [f"Session already marked as failed ({state.failure_reason or 'unknown reason'}) - skipping monitoring"],
                'recommendations': ["No action needed - session should be cleaned up"],
                'skip_monitoring': True
            }
        
        health = {
            'session_name': session_name,
            'status': 'healthy',
            'issues': [],
            'recommendations': []
        }
        
        # NEW: Check for coordination conflicts first
        project_name = session_name.split('-impl-')[0].replace('-', ' ').title()
        conflicts = self.state_manager.get_status_conflicts(project_name)
        if conflicts:
            health['status'] = 'critical'
            
            # Attempt automatic resolution
            resolutions = self.state_manager.resolve_conflicts_automatically(project_name)
            
            for i, conflict in enumerate(conflicts):
                health['issues'].append(f"CONFLICT: {conflict['description']}")
                
                # Add resolution info if available
                if i < len(resolutions) and resolutions[i]:
                    resolution = resolutions[i]
                    health['recommendations'].append(f"AUTO-RESOLVED: {resolution['message']}")
                    
                    # Notify affected agents
                    for agent in resolution.get('agents_notified', []):
                        self._send_conflict_resolution_notice(session_name, state, agent, resolution)
                        
                    logger.info(f"Auto-resolved {conflict['type']}: {resolution['action']}")
                else:
                    health['recommendations'].append(conflict['suggested_action'])
                    
            # Try git sync to resolve deployment conflicts
            if self.git_coordinator.resolve_deployment_conflict(state):
                health['recommendations'].append("Attempted git sync to resolve deployment conflict")
                self.state_manager.save_session_state(state)  # Save updated agent states
            
            return health  # Skip other checks - conflict is highest priority
        
        # NEW: Git-aware health check - detect and resolve divergences
        try:
            if self.git_coordinator.detect_divergence(state):
                health['status'] = 'warning'
                health['issues'].append("Git worktrees have divergent commits - potential sync issue")
                
                # Attempt automatic sync from sysadmin/devops to developer/tester
                sync_results = self.git_coordinator.sync_all_agents(
                    state, 
                    source_role='sysadmin',  # Prioritize SysAdmin for deployments
                    target_roles=['developer', 'tester']  # Target affected roles
                )
                
                if any(sync_results.values()):
                    successful_syncs = [role for role, success in sync_results.items() if success]
                    health['recommendations'].append(f"Auto-synced divergent branches: {', '.join(successful_syncs)}")
                    self.state_manager.save_session_state(state)  # Save updated commit hashes
                    logger.info(f"Auto-synced git divergence in {session_name}")
                else:
                    health['status'] = 'critical'
                    health['recommendations'].append("Manual git sync required - check git logs for conflicts")
        except Exception as e:
            logger.warning(f"Git health check failed for {session_name}: {e}")
            health['issues'].append(f"Git health check error: {str(e)}")
        
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
        
        # Check for idle team before recovery check
        if health['status'] != 'critical' and self.is_team_idle(session_name, state):
            health['status'] = 'warning' if health['status'] == 'healthy' else health['status']
            health['issues'].append("All team members appear idle (no recent activity)")
            self.nudge_idle_project(session_name, health)
        
        # Check for recovery if emergency was previously sent
        if session_name in self.emergency_tracker:
            recovery_signals = self.detect_recovery_signals(session_name)
            if len(recovery_signals) >= self.recovery_signals_required:
                health['status'] = 'recovered'
                health['recovery_signals'] = recovery_signals
                self.handle_recovery(session_name)
            else:
                health['recovery_signals'] = recovery_signals
        
        # NEW: Check for project timeout (4 hours)
        if state and state.created_at and state.completion_status == "pending":
            created = datetime.fromisoformat(state.created_at.replace('Z', '+00:00'))
            duration = datetime.now() - created
            hours_running = duration.total_seconds() / 3600
            
            if hours_running > 6:
                # Check if there are pending batch specs
                if self._has_pending_batch_specs():
                    health['status'] = 'critical'
                    health['issues'].append(f"Project timed out after {hours_running:.1f} hours with pending batch specs")
                    
                    # Trigger failure handler
                    try:
                        from project_failure_handler import ProjectFailureHandler
                        handler = ProjectFailureHandler(self.tmux_orchestrator_path)
                        if handler.handle_timeout_failure(state.project_name, state):
                            health['recommendations'].append("Timeout failure handling completed - project terminated")
                            # Mark project as handled to prevent further monitoring
                            health['handled'] = True
                        else:
                            health['recommendations'].append("Timeout failure handling failed - manual intervention required")
                    except Exception as e:
                        logger.error(f"Failed to handle timeout for {session_name}: {e}")
                        health['recommendations'].append(f"Timeout handler error: {str(e)}")
                        
                else:
                    health['status'] = 'warning' if health['status'] == 'healthy' else health['status']
                    health['issues'].append(f"Project running {hours_running:.1f} hours but no pending batch specs - continuing monitoring")
        
        return health
    
    def schedule_emergency_checkin(self, session_name: str, window: int, role: str, interval: int = None):
        """Schedule an emergency check-in with dynamic interval and cycle detection"""
        if interval is None:
            # Get the appropriate interval based on emergency level
            level = self.emergency_tracker.get(session_name, {}).get('count', 0)
            interval = self.emergency_intervals[min(level, len(self.emergency_intervals) - 1)]
        
        # Record scheduling event for cycle detection
        note = f"EMERGENCY CHECK-IN (Level {self.emergency_tracker.get(session_name, {}).get('count', 0) + 1}): Project may be stuck. Please report status immediately."
        cycle_detected = self.cycle_detector.record_scheduling_event(
            session_name=session_name,
            agent_role=role,
            window=window,
            event_type='emergency_scheduled',
            interval_minutes=interval,
            note=note,
            triggered_by='stuck_project_detection'
        )
        
        # If cycle detected, attempt to break it
        if cycle_detected:
            logger.warning(f"Cycle detected while scheduling emergency for {session_name}: {cycle_detected}")
            cycle_break_result = self.cycle_detector.prevent_cycle(session_name, cycle_detected)
            if cycle_break_result['success']:
                logger.info(f"Successfully broke cycle: {cycle_break_result['message']}")
                # Don't schedule emergency if cycle was broken - let the cycle breaking take effect
                return
            else:
                logger.error(f"Failed to break cycle: {cycle_break_result}")
        
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
        
        # Check if session is still alive before sending emergency messages
        if not self._is_session_alive(session_name):
            logger.info(f"Session {session_name} is dead - skipping emergency handling")
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
        
        # Safeguard for too many sessions
        if len(orchestrator_sessions) > 20:
            logger.warning(f"Too many sessions ({len(orchestrator_sessions)}), consider increasing monitoring interval to avoid overload")
        
        interventions_needed = []
        
        for session in orchestrator_sessions:
            # Check if session is alive before processing
            if not self._is_session_alive(session):
                continue
            
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
                
                # Skip further processing if marked for skipping
                if health.get('skip_monitoring'):
                    logger.debug(f"Skipping monitoring for {session} - {health['issues'][0]}")
                    continue
                
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
                
                # Check for authorization timeouts
                self.check_authorization_timeouts(session, state)
        
        return len(interventions_needed)
    
    def _has_pending_batch_specs(self) -> bool:
        """Check if there are pending specs in the batch queue using scheduler"""
        try:
            from scheduler import TmuxOrchestratorScheduler
            scheduler = TmuxOrchestratorScheduler()
            
            # Count queued projects in the scheduler database
            cursor = scheduler.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM project_queue WHERE status = 'queued'")
            count = cursor.fetchone()[0]
            return count > 0
            
        except Exception as e:
            logger.warning(f"Could not check batch queue: {e}")
            return False  # Fail-safe: assume no queue to avoid false timeouts
    
    def check_authorization_timeouts(self, session_name: str, state: SessionState):
        """Check for agents waiting on authorizations that have timed out"""
        now = datetime.now()
        
        for role, agent in state.agents.items():
            if agent.waiting_for and isinstance(agent.waiting_for, dict):
                try:
                    since = datetime.fromisoformat(agent.waiting_for.get('since', ''))
                    timeout_minutes = agent.waiting_for.get('timeout_minutes', 30)
                    
                    if (now - since).total_seconds() / 60 > timeout_minutes:
                        # Timeout exceeded - escalate to Orchestrator
                        target_role = agent.waiting_for.get('role', 'unknown')
                        request_id = agent.waiting_for.get('request_id', 'unknown')
                        request = agent.waiting_for.get('request', 'unspecified request')
                        
                        escalation_msg = f"AUTHORIZATION TIMEOUT: {role} has been waiting for {target_role} authorization for over {timeout_minutes} minutes. Request ID: {request_id}. Request: {request}"
                        
                        # Send escalation to Orchestrator
                        send_script = self.tmux_orchestrator_path / "send-claude-message.sh"
                        if send_script.exists():
                            subprocess.run([
                                str(send_script),
                                f"{session_name}:0",
                                escalation_msg
                            ], capture_output=True)
                        
                        logger.warning(f"Escalated authorization timeout for {role} waiting on {target_role}")
                        
                        # Clear the waiting_for to prevent repeated escalations
                        agent.waiting_for['escalated'] = True
                        self.state_manager.save_session_state(state)
                        
                except Exception as e:
                    logger.error(f"Error checking authorization timeout for {role}: {e}")
    
    def _send_conflict_resolution_notice(self, session_name: str, state: SessionState, agent_role: str, resolution: Dict[str, Any]):
        """Send conflict resolution notice to specific agent"""
        if agent_role not in state.agents:
            logger.warning(f"Agent {agent_role} not found in session {session_name}")
            return
            
        agent = state.agents[agent_role]
        window = agent.window_index
        
        message = f"""🔧 CONFLICT RESOLUTION NOTICE:

{resolution['message']}

Resolution Type: {resolution.get('type', 'Unknown')}
Action Taken: {resolution.get('action', 'Unknown')}

Next Steps:
{chr(10).join(f'• {step}' for step in resolution.get('next_steps', []))}

This conflict has been automatically resolved. Please acknowledge and proceed accordingly."""
        
        send_script = self.tmux_orchestrator_path / 'send-claude-message.sh'
        if send_script.exists():
            try:
                result = subprocess.run([
                    str(send_script),
                    f"{session_name}:{window}",
                    message
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"Sent conflict resolution notice to {agent_role}")
                else:
                    logger.error(f"Failed to send conflict resolution notice: {result.stderr}")
            except Exception as e:
                logger.error(f"Error sending conflict resolution notice: {e}")
    
    def run_continuous_monitoring(self, interval_minutes: int = 2):
        """Run continuous monitoring"""
        logger.info(f"Starting continuous check-in monitoring (interval: {interval_minutes} minutes)")
        
        while True:
            try:
                interventions = self.monitor_all_projects()
                if interventions > 0:
                    logger.info(f"Performed {interventions} interventions")
                else:
                    logger.debug("All projects healthy")  # Reduced to DEBUG to minimize log noise
                
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
    parser.add_argument('--interval', type=int, default=2, help='Monitoring interval in minutes (default: 2)')
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
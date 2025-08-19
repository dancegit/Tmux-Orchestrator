#!/usr/bin/env python3
"""
Project failure handler for timeout and failure management in Tmux Orchestrator.
Handles project timeouts, cleanup, reporting, and batch queue progression.
"""

import subprocess
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from session_state import SessionStateManager, SessionState
from email_notifier import get_email_notifier
from enhanced_notifications import EnhancedNotificationSystem, Priority, NotificationType
from cycle_detection import CycleDetector

logger = logging.getLogger(__name__)

class ProjectFailureHandler:
    """Handles project failures including timeout, cleanup, reporting, and queue progression"""
    
    def __init__(self, tmux_orchestrator_path: Path):
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.state_manager = SessionStateManager(tmux_orchestrator_path)
        self.email_notifier = get_email_notifier()
        self.notification_system = EnhancedNotificationSystem(tmux_orchestrator_path)
        self.cycle_detector = CycleDetector(tmux_orchestrator_path)
        
        # Add scheduler reference for task cleanup
        from scheduler import TmuxOrchestratorScheduler
        self.scheduler = TmuxOrchestratorScheduler()
        
        # Ensure logs directory exists
        (tmux_orchestrator_path / 'registry' / 'logs').mkdir(parents=True, exist_ok=True)
    
    def handle_timeout_failure(self, project_name: str, state: SessionState) -> bool:
        """
        Handle project timeout failure with complete cleanup and progression.
        
        Returns True if handling succeeded, False if errors occurred.
        """
        try:
            logger.warning(f"Handling timeout failure for project: {project_name}")
            
            # Calculate duration for reporting
            created = datetime.fromisoformat(state.created_at)
            duration = datetime.now() - created
            hours_running = duration.total_seconds() / 3600
            
            # Step 1: Send internal alert before cleanup
            self._send_internal_alert(state, hours_running)
            
            # Step 2: Generate failure report (before cleanup to capture window states)
            report_path = self._generate_failure_report(project_name, state, hours_running)
            
            # Step 3: Mark as failed in state
            self._mark_as_failed(state, hours_running)
            
            # Step 4: Update project queue status for batch retry system
            self._update_queue_status(state, 'failed', f"Timeout after {hours_running:.1f} hours")
            
            # Step 5: Remove all scheduled check-ins for the session
            self._remove_scheduled_tasks(state.session_name)
            
            # Step 6: Send email notification
            self._send_failure_email(state, hours_running, report_path)
            
            # Step 7: Cleanup tmux session safely with verification
            if not self._cleanup_tmux(state.session_name):
                logger.error("Cleanup failed - aborting queue progression")
                return False
            
            # Step 8: Check for batch completion and trigger intelligent retry
            batch_id = getattr(state, 'batch_id', None)
            if batch_id:
                self.scheduler.check_batch_completion(batch_id)
            
            # Step 9: Update batch queue and trigger next spec (legacy path)
            self._progress_batch_queue(project_name)
            
            logger.info(f"Successfully handled timeout failure for {project_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling timeout failure for {project_name}: {e}")
            try:
                # Emergency notification if handler fails
                self.notification_system.send_emergency_alert(
                    session_name=state.session_name if state else project_name,
                    alert_type="HANDLER_FAILURE",
                    details=f"Timeout handler failed: {str(e)}"
                )
            except:
                pass  # Don't let notification failure crash the handler
            return False
    
    def _send_internal_alert(self, state: SessionState, hours_running: float):
        """Send internal alert to orchestrator before cleanup"""
        try:
            self.notification_system.send_emergency_alert(
                session_name=state.session_name,
                alert_type="PROJECT_TIMEOUT",
                details=f"Project {state.project_name} timed out after {hours_running:.1f} hours with pending batch specs. Initiating failure handling.",
                affected_agents=[agent_role for agent_role in state.agents.keys()]
            )
            logger.info(f"Sent internal timeout alert for {state.project_name}")
        except Exception as e:
            logger.error(f"Failed to send internal alert: {e}")
    
    def _remove_scheduled_tasks(self, session_name: str):
        """Remove all scheduled check-ins for the failed session"""
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.scheduler.db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE session_name = ?", (session_name,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            logger.info(f"Removed {deleted} scheduled tasks for {session_name}")
        except Exception as e:
            logger.error(f"Failed to remove tasks for {session_name}: {e}")
    
    def _mark_as_failed(self, state: SessionState, hours_running: float):
        """Mark project as failed and log to historical failure log"""
        try:
            # Update session state
            state.completion_status = "failed"
            state.completion_time = datetime.now().isoformat()
            state.failure_reason = "timeout_after_4_hours_with_pending_specs"
            self.state_manager.save_session_state(state)
            
            # Log to separate historical failure log
            failure_log = self.tmux_orchestrator_path / 'registry' / 'logs' / 'failures.jsonl'
            failure_entry = {
                "timestamp": state.completion_time,
                "project_name": state.project_name,
                "session_name": state.session_name,
                "failure_reason": state.failure_reason,
                "duration_hours": round(hours_running, 2),
                "spec_path": state.spec_path,
                "agent_count": len(state.agents),
                "created_at": state.created_at
            }
            
            with open(failure_log, 'a') as f:
                f.write(json.dumps(failure_entry) + '\\n')
            
            logger.info(f"Marked {state.project_name} as failed and logged to failure history")
            
        except Exception as e:
            logger.error(f"Failed to mark project as failed: {e}")
            raise
    
    def _generate_failure_report(self, project_name: str, state: SessionState, hours_running: float) -> Path:
        """Generate detailed failure report with window captures and analysis"""
        try:
            # Create report in project root if available, otherwise in registry
            if state.project_path and Path(state.project_path).exists():
                report_dir = Path(state.project_path)
            else:
                report_dir = self.tmux_orchestrator_path / 'registry' / 'projects' / project_name.lower().replace(' ', '-')
                report_dir.mkdir(parents=True, exist_ok=True)
            
            report_path = report_dir / f"failure_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            
            with open(report_path, 'w') as f:
                f.write("# Project Failure Report\\n\\n")
                f.write(f"**Project**: {project_name}\\n")
                f.write(f"**Session**: {state.session_name}\\n")
                f.write(f"**Failure Reason**: Timeout after 4 hours with pending batch specs\\n")
                f.write(f"**Duration**: {hours_running:.1f} hours\\n")
                f.write(f"**Start Time**: {state.created_at}\\n")
                f.write(f"**End Time**: {datetime.now().isoformat()}\\n")
                f.write(f"**Spec Path**: {state.spec_path or 'Unknown'}\\n\\n")
                
                # Agent status summary
                f.write("## Agent Status Summary\\n\\n")
                for role, agent in state.agents.items():
                    f.write(f"- **{role}** (Window {agent.window_index}): ")
                    f.write(f"{'Alive' if agent.is_alive else 'Dead'}")
                    if agent.is_exhausted:
                        f.write(", Exhausted")
                    if agent.current_branch:
                        f.write(f", Branch: {agent.current_branch}")
                    f.write("\\n")
                
                # Status reports and conflicts
                if state.status_reports:
                    f.write("\\n## Final Status Reports\\n\\n")
                    for role, report in state.status_reports.items():
                        f.write(f"- **{role}**: {report.get('topic', 'Unknown')} - {report.get('status', 'Unknown')}\\n")
                        if report.get('details'):
                            f.write(f"  - Details: {report['details']}\\n")
                
                # Cycle detection statistics
                try:
                    cycle_stats = self.cycle_detector.get_cycle_statistics()
                    if cycle_stats.get('total_events_24h', 0) > 0:
                        f.write("\\n## Cycle Detection Analysis\\n\\n")
                        f.write(f"- Total events in last 24h: {cycle_stats.get('total_events_24h', 0)}\\n")
                        f.write(f"- Event types: {cycle_stats.get('events_by_type', {})}\\n")
                except Exception as e:
                    logger.warning(f"Could not get cycle statistics: {e}")
                
                # Window captures from key agents
                f.write("\\n## Recent Window Captures\\n\\n")
                self._capture_agent_windows(f, state)
                
                # Recommendations
                f.write("\\n## Recommendations\\n\\n")
                f.write("- Review agent logs above for stuck patterns\\n")
                f.write("- Check for resource exhaustion or dependency issues\\n")
                f.write("- Consider adjusting team configuration or project scope\\n")
                if any(agent.is_exhausted for agent in state.agents.values()):
                    f.write("- **Credit exhaustion detected** - monitor usage limits\\n")
                
                f.write("\\n---\\n")
                f.write("*Report generated automatically by Tmux Orchestrator failure handler*\\n")
            
            logger.info(f"Generated failure report: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Failed to generate failure report: {e}")
            # Create minimal report
            try:
                minimal_path = self.tmux_orchestrator_path / 'registry' / 'logs' / f"failure_{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(minimal_path, 'w') as f:
                    f.write(f"Project {project_name} failed due to timeout after {hours_running:.1f} hours\\n")
                    f.write(f"Report generation failed: {str(e)}\\n")
                return minimal_path
            except:
                return Path("failure_report_unavailable")
    
    def _capture_agent_windows(self, file_handle, state: SessionState):
        """Capture recent output from key agent windows"""
        key_roles = ['orchestrator', 'project_manager', 'developer', 'tester']
        
        for role in key_roles:
            if role in state.agents:
                agent = state.agents[role]
                try:
                    # Capture last 100 lines from the window
                    result = subprocess.run([
                        'tmux', 'capture-pane', '-t', f'{state.session_name}:{agent.window_index}',
                        '-p', '-S', '-100'
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0 and result.stdout.strip():
                        file_handle.write(f"### {role.title()} (Window {agent.window_index})\\n\\n")
                        file_handle.write("```\\n")
                        file_handle.write(result.stdout.strip())
                        file_handle.write("\\n```\\n\\n")
                    else:
                        file_handle.write(f"### {role.title()} (Window {agent.window_index})\\n\\n")
                        file_handle.write("*No recent output captured*\\n\\n")
                        
                except Exception as e:
                    logger.warning(f"Could not capture window for {role}: {e}")
                    file_handle.write(f"### {role.title()} (Window {agent.window_index})\\n\\n")
                    file_handle.write(f"*Capture failed: {str(e)}*\\n\\n")
    
    def _send_failure_email(self, state: SessionState, hours_running: float, report_path: Path):
        """Send failure notification email"""
        try:
            # Get pending queue count for context
            pending_count = self._get_pending_queue_count()
            
            self.email_notifier.send_project_completion_email(
                project_name=state.project_name,
                spec_path=state.spec_path or state.implementation_spec_path,
                status='failed',
                error_message=f"Project timed out after {hours_running:.1f} hours with {pending_count} pending batch specs in queue.",
                session_name=state.session_name,
                duration_seconds=int((datetime.now() - datetime.fromisoformat(state.created_at)).total_seconds()),
                batch_mode=True,
                additional_info={
                    "Timeout Duration": f"{hours_running:.1f} hours",
                    "Pending Queue Items": pending_count,
                    "Failure Report": str(report_path),
                    "Agent Count": len(state.agents),
                    "Exhausted Agents": sum(1 for agent in state.agents.values() if agent.is_exhausted)
                }
            )
            logger.info(f"Sent failure email for {state.project_name}")
            
        except Exception as e:
            logger.error(f"Failed to send failure email: {e}")
    
    def _cleanup_tmux(self, session_name: str) -> bool:
        """Safely cleanup tmux session and all its windows with verification and retry"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Check if session exists
                result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                                      capture_output=True)
                if result.returncode != 0:
                    logger.info(f"Session {session_name} not found - already cleaned up")
                    return True
                
                # Get window list for logging
                result = subprocess.run([
                    'tmux', 'list-windows', '-t', session_name, '-F', '#{window_index}:#{window_name}'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    windows = result.stdout.strip().split('\\n')
                    logger.info(f"Cleaning up session {session_name} with windows: {windows} (attempt {attempt + 1})")
                    
                    # Kill individual windows first (safer)
                    for window_info in windows:
                        if window_info and ':' in window_info:
                            window_index = window_info.split(':')[0]
                            try:
                                subprocess.run(['tmux', 'kill-window', '-t', f"{session_name}:{window_index}"], 
                                             capture_output=True, timeout=5)
                            except subprocess.TimeoutExpired:
                                logger.warning(f"Timeout killing window {window_index}")
                
                # Kill the entire session
                result = subprocess.run(['tmux', 'kill-session', '-t', session_name], 
                                      capture_output=True, timeout=10)
                if result.returncode == 0:
                    logger.info(f"Session kill command succeeded for {session_name}")
                else:
                    logger.warning(f"Session kill failed: {result.stderr}")
                
                # Verify session is gone
                import time
                time.sleep(1)  # Brief delay to let tmux process the kill
                result = subprocess.run(['tmux', 'has-session', '-t', session_name], capture_output=True)
                if result.returncode != 0:
                    logger.info(f"Verified cleanup of {session_name}")
                    return True
                else:
                    logger.warning(f"Session {session_name} still exists (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Brief delay before retry
                    
            except Exception as e:
                logger.error(f"Cleanup attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        logger.error(f"Failed to clean up {session_name} after {max_retries} attempts")
        return False
    
    def _progress_batch_queue(self, failed_project_name: str):
        """Update batch queue status and trigger next spec if available using existing scheduler"""
        try:
            from scheduler import TmuxOrchestratorScheduler
            scheduler = TmuxOrchestratorScheduler()
            
            # Check if there are failures in the current batch that should defer to intelligent retry
            # This coordination prevents conflicts between old and new retry systems
            state = None
            try:
                state = self.state_manager.load_session_state(failed_project_name)
                batch_id = getattr(state, 'batch_id', None)
                
                if batch_id and self._batch_has_failures(batch_id):
                    logger.info(f"Deferring progression for batch {batch_id} to intelligent retry system")
                    return  # Let the new batch retry system handle this
            except Exception:
                pass  # Continue with legacy progression if state unavailable
            
            # Get next queued project
            next_project = scheduler.get_next_project()
            
            if next_project:
                logger.info(f"Next batch project ready: ID {next_project['id']} - {next_project['spec_path']}")
                
                # Mark as processing
                scheduler.update_project_status(next_project['id'], 'processing')
                
                # Trigger next orchestration
                self._trigger_next_orchestration(next_project)
                
            else:
                logger.info("No pending projects in batch queue - batch processing complete")
                
        except Exception as e:
            logger.error(f"Failed to progress batch queue: {e}")
    
    def _trigger_next_orchestration(self, queue_item: Dict[str, Any]):
        """Trigger orchestration for the next queued spec in a persistent tmux session"""
        try:
            spec_path = queue_item.get('spec_path')
            project_path = queue_item.get('project_path')
            project_id = queue_item.get('id')
            
            if not spec_path or not Path(spec_path).exists():
                logger.error(f"Next spec not found: {spec_path}")
                self._update_project_status_with_error(project_id, 'failed', 'Spec file not found')
                return
            
            # Derive project name for logging/session naming
            project_name = Path(spec_path).stem.lower().replace(' ', '-').replace('_', '-')
            logger.info(f"Triggering persistent orchestration for project ID {project_id} ({project_name}): {spec_path}")
            
            # Ensure tmux server is running before creating sessions
            if not self._ensure_tmux_server_running():
                error_msg = "Failed to ensure tmux server is running"
                logger.error(error_msg)
                self._update_project_status_with_error(project_id, 'failed', error_msg)
                return
            
            # Create a dedicated tmux session for this orchestration process
            orchestrator_session = f"orchestrator-{project_id}"
            
            # Kill any existing session with this name (cleanup)
            subprocess.run(['tmux', 'kill-session', '-t', orchestrator_session], capture_output=True)
            
            # Create new detached session
            create_result = subprocess.run(
                ['tmux', 'new-session', '-d', '-s', orchestrator_session, '-n', 'main', '-c', str(self.tmux_orchestrator_path)],
                capture_output=True, text=True
            )
            if create_result.returncode != 0:
                error_msg = f"Failed to create tmux session {orchestrator_session}: {create_result.stderr}"
                logger.error(error_msg)
                self._update_project_status_with_error(project_id, 'failed', error_msg)
                self._send_orchestration_alert(orchestrator_session, "ORCHESTRATION_LAUNCH_FAILURE", error_msg)
                return
            
            # Build the command to run auto_orchestrate.py
            cmd_parts = [
                './auto_orchestrate.py',  # Use relative path since we're in the tmux orchestrator directory
                '--spec', spec_path
            ]
            if project_path:
                cmd_parts.extend(['--project', project_path])
            
            # Send the command to the tmux session (with error handling)
            full_cmd = ' '.join(cmd_parts) + '; echo "=== Orchestration completed or failed ==="; echo "Session will remain for debugging - kill manually if needed"; sleep infinity'
            send_result = subprocess.run(
                ['tmux', 'send-keys', '-t', f'{orchestrator_session}:0', full_cmd, 'C-m'],
                capture_output=True, text=True
            )
            if send_result.returncode != 0:
                error_msg = f"Failed to send command to {orchestrator_session}: {send_result.stderr}"
                logger.error(error_msg)
                subprocess.run(['tmux', 'kill-session', '-t', orchestrator_session], capture_output=True)
                self._update_project_status_with_error(project_id, 'failed', error_msg)
                self._send_orchestration_alert(orchestrator_session, "ORCHESTRATION_LAUNCH_FAILURE", error_msg)
                return
            
            # Verify startup: Check that auto_orchestrate.py is running and making progress
            import time
            initial_verification_timeout = 30  # Wait for auto_orchestrate.py to start
            start_time = time.time()
            
            logger.info(f"Verifying auto_orchestrate.py started in session {orchestrator_session}...")
            
            # First, verify the orchestrator session is running and has auto_orchestrate.py
            orchestrator_running = False
            while time.time() - start_time < initial_verification_timeout:
                # Check if the orchestrator session still exists
                check_result = subprocess.run(['tmux', 'has-session', '-t', orchestrator_session], capture_output=True)
                if check_result.returncode != 0:
                    error_msg = f"Orchestrator session {orchestrator_session} died during startup"
                    logger.error(error_msg)
                    self._update_project_status_with_error(project_id, 'failed', error_msg)
                    return
                
                # Check if auto_orchestrate.py is running
                capture_result = subprocess.run(
                    ['tmux', 'capture-pane', '-t', f'{orchestrator_session}:0', '-p'],
                    capture_output=True, text=True
                )
                if capture_result.returncode == 0 and capture_result.stdout.strip():
                    output = capture_result.stdout
                    if "Auto-Orchestrate" in output or "Analyzing specification" in output or "Step 1:" in output:
                        orchestrator_running = True
                        logger.info(f"✅ Verified: auto_orchestrate.py is running in {orchestrator_session}")
                        break
                
                time.sleep(2)
            
            if not orchestrator_running:
                error_msg = f"auto_orchestrate.py failed to start properly in {orchestrator_session}"
                logger.error(error_msg)
                # Capture final output for debugging
                capture_result = subprocess.run(
                    ['tmux', 'capture-pane', '-t', f'{orchestrator_session}:0', '-p'],
                    capture_output=True, text=True
                )
                if capture_result.returncode == 0:
                    logger.error(f"Final session output: {capture_result.stdout}")
                
                subprocess.run(['tmux', 'kill-session', '-t', orchestrator_session], capture_output=True)
                self._update_project_status_with_error(project_id, 'failed', error_msg)
                self._send_orchestration_alert(orchestrator_session, "ORCHESTRATION_STARTUP_FAILURE", error_msg)
                return
            
            # Store orchestrator session for tracking (don't wait for main session - it takes too long)
            logger.info(f"✅ Orchestration process started successfully for project ID {project_id}")
            logger.info(f"   Orchestrator session: {orchestrator_session}")
            logger.info(f"   Note: Main project session will be created after specification analysis (may take 5-15 minutes)")
            
            self._update_orchestrator_tracking(project_id, orchestrator_session, "pending")
            
            # Log success - the process will continue in the background
            logger.info(f"Project {project_id} is now running in persistent tmux session {orchestrator_session}")
            logger.info(f"To monitor progress: tmux attach -t {orchestrator_session}")
            
        except Exception as e:
            logger.error(f"Failed to trigger next orchestration: {e}")
            if project_id:
                self._update_project_status_with_error(project_id, 'failed', str(e))
                self._send_orchestration_alert(f"orchestrator-{project_id}", "ORCHESTRATION_LAUNCH_FAILURE", str(e))
    
    def _update_project_status_with_error(self, project_id: int, status: str, error_message: str):
        """Update project status in database with error message"""
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.scheduler.db_path))
            conn.execute(
                "UPDATE project_queue SET status = ?, error_message = ? WHERE id = ?", 
                (status, error_message, project_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"Updated project {project_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update project status: {e}")
    
    def _update_orchestrator_tracking(self, project_id: int, orchestrator_session: str, main_session: str):
        """Store orchestrator session info for tracking"""
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.scheduler.db_path))
            # First, check if orchestrator_session column exists, if not add it
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(project_queue)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'orchestrator_session' not in columns:
                cursor.execute("ALTER TABLE project_queue ADD COLUMN orchestrator_session TEXT")
            if 'main_session' not in columns:
                cursor.execute("ALTER TABLE project_queue ADD COLUMN main_session TEXT")
            
            cursor.execute(
                "UPDATE project_queue SET orchestrator_session = ?, main_session = ? WHERE id = ?", 
                (orchestrator_session, main_session, project_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"Stored session tracking for project {project_id}")
        except Exception as e:
            logger.warning(f"Failed to update orchestrator tracking: {e}")
    
    def _ensure_tmux_server_running(self) -> bool:
        """Ensure tmux server is running, start it if necessary"""
        try:
            # Check if tmux server is running by trying to list sessions
            result = subprocess.run(['tmux', 'list-sessions'], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Server is running
                logger.info("✓ Tmux server is already running")
                return True
            elif "no server running" in result.stderr.lower():
                # Server is not running, start it
                logger.info("Tmux server not running, starting it...")
                
                # Check if our background session already exists
                check_result = subprocess.run([
                    'tmux', 'has-session', '-t', 'tmux-orchestrator-server'
                ], capture_output=True)
                
                if check_result.returncode != 0:
                    # Create a persistent background session to keep server running
                    start_result = subprocess.run([
                        'tmux', 'new-session', '-d', '-s', 'tmux-orchestrator-server', 
                        '-n', 'server', 'echo "Tmux Orchestrator Server - Keep this session running"; sleep infinity'
                    ], capture_output=True, text=True)
                    
                    if start_result.returncode == 0:
                        logger.info("✓ Started tmux server with background session")
                        return True
                    else:
                        logger.error(f"Failed to start tmux server: {start_result.stderr}")
                        return False
                else:
                    logger.info("✓ Tmux background session already exists")
                    return True
            else:
                logger.error(f"Unexpected tmux error: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.error("tmux command not found - tmux is not installed")
            return False
        except Exception as e:
            logger.error(f"Error checking tmux server: {e}")
            return False
    
    def _send_orchestration_alert(self, session_name: str, alert_type: str, details: str):
        """Send alert about orchestration issues"""
        try:
            self.notification_system.send_emergency_alert(
                session_name=session_name,
                alert_type=alert_type,
                details=details
            )
        except Exception as e:
            logger.warning(f"Failed to send orchestration alert: {e}")
    
    def _get_pending_queue_count(self) -> int:
        """Get count of pending items in batch queue using scheduler"""
        try:
            from scheduler import TmuxOrchestratorScheduler
            scheduler = TmuxOrchestratorScheduler()
            
            # Count queued projects in the scheduler database
            cursor = scheduler.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM project_queue WHERE status = 'queued'")
            count = cursor.fetchone()[0]
            return count
            
        except Exception as e:
            logger.warning(f"Could not get pending queue count: {e}")
            return 0
    
    def has_pending_batch_specs(self) -> bool:
        """Check if there are pending specs in the batch queue"""
        return self._get_pending_queue_count() > 0
    
    def _update_queue_status(self, state: SessionState, status: str, error_message: str = None):
        """Update project_queue with failure details for batch retry system"""
        try:
            cursor = self.scheduler.conn.cursor()
            # Try to match by spec_path or project_path
            spec_path = getattr(state, 'spec_path', None) or getattr(state, 'implementation_spec_path', None)
            project_path = getattr(state, 'project_path', None)
            
            if spec_path:
                cursor.execute("""
                    UPDATE project_queue
                    SET status = ?, error_message = ?, completed_at = strftime('%s', 'now')
                    WHERE spec_path = ? OR project_path = ?
                """, (status, error_message, spec_path, project_path))
                
                if cursor.rowcount > 0:
                    self.scheduler.conn.commit()
                    logger.info(f"Updated queue status for {state.project_name} to {status}")
                else:
                    logger.debug(f"No matching project found in queue for {state.project_name}")
            else:
                logger.warning(f"Cannot update queue status - no spec_path found for {state.project_name}")
                
        except Exception as e:
            logger.error(f"Failed to update queue status: {e}")
    
    def _batch_has_failures(self, batch_id: str) -> bool:
        """Check if batch has any failed projects"""
        if not batch_id:
            return False
            
        try:
            cursor = self.scheduler.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM project_queue WHERE batch_id=? AND status='failed'", (batch_id,))
            return cursor.fetchone()[0] > 0
        except Exception as e:
            logger.error(f"Error checking batch failures: {e}")
            return False
#!/usr/bin/env python3
"""
Project completion detection and notification manager for Tmux Orchestrator.
Monitors for completion signals and triggers email notifications.
"""

import subprocess
import time
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json

from session_state import SessionStateManager, SessionState
from email_notifier import get_email_notifier

logger = logging.getLogger(__name__)

class CompletionManager:
    """Manages project completion detection and notifications"""
    
    def __init__(self, 
                 state_mgr: SessionStateManager, 
                 notifier=None,
                 poll_interval: int = 300,  # 5 minutes default
                 timeout_multiplier: float = 2.0):  # Fail if exceeded by 2x estimated time
        self.state_mgr = state_mgr
        self.notifier = notifier or get_email_notifier()
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.poll_interval = poll_interval
        self.timeout_multiplier = timeout_multiplier
        self.monitoring_futures = {}  # Track active monitoring tasks

    def is_complete(self, 
                    state: SessionState, 
                    spec: Any,  # ImplementationSpec type
                    worktree_paths: Dict[str, Path]) -> Optional[str]:
        """
        Check if project is complete or failed.
        Returns 'completed', 'failed', or None.
        """
        try:
            # Check failure conditions first
            failure_status = self._check_failure_conditions(state, spec)
            if failure_status:
                logger.info(f"Failure detected: {failure_status}")
                return 'failed'
            
            # Get orchestrator worktree path
            orch_worktree = worktree_paths.get('orchestrator')
            if not orch_worktree:
                logger.warning("No orchestrator worktree found")
                return None
            
            # CRITICAL: Check if enough time has passed (minimum 10 minutes of work)
            if hasattr(state, 'created_at'):
                from datetime import datetime
                try:
                    created_dt = datetime.fromisoformat(state.created_at.replace('Z', '+00:00'))
                    elapsed = (datetime.now(created_dt.tzinfo) - created_dt).total_seconds()
                    if elapsed < 600:  # 10 minutes minimum
                        logger.debug(f"Project started only {elapsed:.0f}s ago - too early to mark complete")
                        return None
                except:
                    pass
            
            # Check for actual implementation files (code-agnostic)
            has_implementation = False
            developer_worktree = worktree_paths.get('developer')
            if developer_worktree:
                # Check common implementation directories
                implementation_dirs = ['src', 'lib', 'app', 'components', 'modules', 'packages', 'public', 'dist']
                code_extensions = [
                    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
                    '.go', '.rs', '.rb', '.php', '.cs', '.swift', '.kt', '.scala',
                    '.r', '.m', '.mm', '.vue', '.svelte', '.dart', '.lua', '.ex', '.exs',
                    '.html', '.css', '.scss', '.sass', '.sql', '.sh', '.bash', '.zsh'
                ]
                
                total_files = 0
                for dir_name in implementation_dirs:
                    dir_path = developer_worktree / dir_name
                    if dir_path.exists():
                        for ext in code_extensions:
                            code_files = list(dir_path.rglob(f'*{ext}'))
                            total_files += len(code_files)
                
                # Also check root for code files
                for ext in code_extensions:
                    root_files = list(developer_worktree.glob(f'*{ext}'))
                    total_files += len(root_files)
                
                has_implementation = total_files >= 3  # Require at least 3 files
                logger.debug(f"Found {total_files} code files in project")
            
            # Check completion criteria
            marker_exists = self._check_marker_file(orch_worktree)
            git_merged = self._check_git_merged(state, spec, orch_worktree)
            phases_complete = self._check_phases_complete(state, spec)
            
            logger.debug(f"Completion checks - Marker: {marker_exists}, Git merged: {git_merged}, Phases: {phases_complete}, Implementation: {has_implementation}")
            
            # Require actual implementation in addition to marker/phases
            if marker_exists and has_implementation and (git_merged or phases_complete):
                logger.info("All completion criteria met including actual implementation")
                return 'completed'
            elif marker_exists and not has_implementation:
                logger.warning("Marker exists but no implementation found - not marking as complete")
            
            return None
        except Exception as e:
            logger.error(f"Error checking completion: {e}")
            return None

    def monitor(self, 
                session_name: str, 
                project_name: str,
                spec: Any,
                worktree_paths: Dict[str, Path],
                spec_path: str,
                batch_mode: bool = False):
        """
        Start background monitoring for completion.
        """
        def _monitor_loop():
            logger.info(f"Starting completion monitoring for {session_name}")
            consecutive_failures = 0
            
            while True:
                try:
                    # Load latest state
                    state = self.state_mgr.load_session_state(project_name)
                    if not state:
                        logger.error(f"Could not load state for {project_name}")
                        consecutive_failures += 1
                        if consecutive_failures > 3:
                            logger.error("Too many failures loading state, stopping monitor")
                            break
                        time.sleep(self.poll_interval)
                        continue
                    
                    # Skip if already completed/failed
                    if hasattr(state, 'completion_status') and state.completion_status in ['completed', 'failed']:
                        logger.info(f"Session already {state.completion_status}, stopping monitor")
                        break
                    
                    # Check completion
                    status = self.is_complete(state, spec, worktree_paths)
                    
                    if status:
                        # Calculate duration
                        start_time = getattr(state, 'created_at', None)
                        if start_time:
                            # Convert ISO string to timestamp
                            from datetime import datetime
                            dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                            duration = int(time.time() - dt.timestamp())
                        else:
                            duration = 0
                        
                        # Prepare additional info
                        additional_info = {
                            'Session Name': session_name,
                            'Project Type': getattr(spec, 'project_type', 'unknown'),
                            'Team Size': len(getattr(state, 'agents', {})),
                            'Git Branch': getattr(state, 'parent_branch', 'unknown')
                        }
                        
                        # Read completion message if marker exists
                        orch_worktree = worktree_paths.get('orchestrator')
                        if orch_worktree:
                            marker_file = orch_worktree / 'COMPLETED'
                            if marker_file.exists():
                                try:
                                    completion_msg = marker_file.read_text()
                                    additional_info['Completion Note'] = completion_msg.strip()
                                except:
                                    pass
                        
                        # Send notification
                        logger.info(f"Sending {status} notification for {project_name}")
                        success = self.notifier.send_project_completion_email(
                            project_name=project_name,
                            spec_path=spec_path,
                            status=status,
                            duration_seconds=duration,
                            session_name=session_name,
                            batch_mode=batch_mode,
                            additional_info=additional_info
                        )
                        
                        if success:
                            logger.info(f"Notification sent successfully for {project_name}")
                        else:
                            logger.error(f"Failed to send notification for {project_name}")
                        
                        # Update state
                        if hasattr(state, 'completion_status'):
                            state.completion_status = status
                            state.completion_time = datetime.now().isoformat()
                            self.state_mgr.save_session_state(state)
                        
                        # Update database status via scheduler
                        self._update_database_status(session_name, status)
                        
                        break  # Stop monitoring
                    
                    consecutive_failures = 0  # Reset on success
                    
                except Exception as e:
                    logger.error(f"Error in monitor loop: {e}")
                    consecutive_failures += 1
                    if consecutive_failures > 5:
                        logger.error("Too many consecutive failures, stopping monitor")
                        break
                
                time.sleep(self.poll_interval)
            
            logger.info(f"Completion monitoring stopped for {session_name}")
        
        # Submit to executor
        future = self.executor.submit(_monitor_loop)
        self.monitoring_futures[session_name] = future
        logger.info(f"Started completion monitoring for {session_name} in background")

    def stop_monitoring(self, session_name: str):
        """Stop monitoring for a specific session"""
        if session_name in self.monitoring_futures:
            self.monitoring_futures[session_name].cancel()
            del self.monitoring_futures[session_name]
            logger.info(f"Stopped monitoring for {session_name}")

    # Helper Methods
    
    def _check_marker_file(self, worktree_path: Path) -> bool:
        """Check for COMPLETED marker file in Orchestrator's worktree"""
        marker = worktree_path / 'COMPLETED'
        exists = marker.exists()
        if exists:
            logger.info(f"Found completion marker at {marker}")
        return exists

    def _check_git_merged(self, state: SessionState, spec: Any, worktree_path: Path) -> bool:
        """Check if the feature branch is merged to parent branch"""
        try:
            # Skip if no git workflow info
            if not hasattr(spec, 'git_workflow'):
                return False
            
            git_workflow = spec.git_workflow
            if not git_workflow or not hasattr(git_workflow, 'parent_branch'):
                return False
            
            # Fetch latest
            result = subprocess.run(
                ['git', 'fetch', 'origin'], 
                cwd=str(worktree_path), 
                capture_output=True, 
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.warning(f"Git fetch failed: {result.stderr}")
                return False
            
            # Check if branch is merged
            parent = git_workflow.parent_branch
            branch = getattr(git_workflow, 'branch_name', None)
            
            if not branch:
                return False
            
            # Check merged branches
            merge_check = subprocess.run(
                ['git', 'branch', '-r', '--merged', f'origin/{parent}'],
                cwd=str(worktree_path), 
                capture_output=True, 
                text=True,
                timeout=10
            )
            
            if merge_check.returncode == 0:
                merged = f'origin/{branch}' in merge_check.stdout
                if merged:
                    logger.info(f"Branch {branch} is merged to {parent}")
                return merged
                
            return False
            
        except subprocess.TimeoutExpired:
            logger.warning("Git command timed out")
            return False
        except Exception as e:
            logger.error(f"Git merge check failed: {e}")
            return False

    def _check_phases_complete(self, state: SessionState, spec: Any) -> bool:
        """Check if all phases are marked complete"""
        try:
            # Check if we have phase tracking
            if not hasattr(state, 'phases_completed'):
                return False
            
            if not hasattr(spec, 'implementation_plan'):
                return False
            
            plan = spec.implementation_plan
            if not hasattr(plan, 'phases'):
                return False
            
            # Get all phase names
            all_phases = {phase.name for phase in plan.phases}
            completed = set(state.phases_completed)
            
            all_complete = all_phases.issubset(completed)
            if all_complete:
                logger.info("All implementation phases marked complete")
            
            return all_complete
            
        except Exception as e:
            logger.error(f"Phase check failed: {e}")
            return False

    def _check_failure_conditions(self, state: SessionState, spec: Any) -> Optional[str]:
        """Check for failure conditions like timeouts"""
        try:
            # Check timeout
            if hasattr(spec, 'implementation_plan') and hasattr(spec.implementation_plan, 'total_estimated_hours'):
                estimated_seconds = spec.implementation_plan.total_estimated_hours * 3600
                
                # Get start time
                start_time = getattr(state, 'created_at', None)
                if start_time:
                    from datetime import datetime
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    elapsed = time.time() - dt.timestamp()
                    
                    if elapsed > estimated_seconds * self.timeout_multiplier:
                        logger.warning(f"Project exceeded timeout: {elapsed}s > {estimated_seconds * self.timeout_multiplier}s")
                        return f"Timeout exceeded ({elapsed/3600:.1f}h > {estimated_seconds * self.timeout_multiplier / 3600:.1f}h)"
            
            # Check for failure marker
            for role, agent in state.agents.items():
                if hasattr(agent, 'worktree_path'):
                    failure_marker = Path(agent.worktree_path) / 'FAILED'
                    if failure_marker.exists():
                        logger.warning(f"Found failure marker in {role}'s worktree")
                        return f"Failure marker found in {role}'s worktree"
            
            return None
            
        except Exception as e:
            logger.error(f"Failure check error: {e}")
            return None

    def _update_database_status(self, session_name: str, status: str):
        """Update project status in the database via scheduler."""
        try:
            # Import scheduler here to avoid circular imports
            from scheduler import TmuxOrchestratorScheduler
            
            # Find project ID by session name
            scheduler = TmuxOrchestratorScheduler()
            
            # Query project_queue to find the project ID by session name
            cursor = scheduler.conn.cursor()
            cursor.execute("""
                SELECT id FROM project_queue 
                WHERE session_name = ? OR orchestrator_session = ? OR main_session = ?
            """, (session_name, session_name, session_name))
            
            row = cursor.fetchone()
            if row:
                project_id = row[0]
                logger.info(f"Found project ID {project_id} for session {session_name}")
                
                # Update the project status
                scheduler.update_project_status(project_id, status)
                logger.info(f"Updated database status for project {project_id} to {status}")
            else:
                logger.warning(f"Could not find project ID for session {session_name}")
                
        except Exception as e:
            logger.error(f"Failed to update database status: {e}")
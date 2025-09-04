#!/usr/bin/env python3
"""
State synchronizer wrapper module extracted from scheduler.py
Wraps the existing StateSynchronizer with scheduler-specific functionality.
"""

import logging
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class StateSynchronizerWrapper:
    """Wrapper for StateSynchronizer with scheduler-specific enhancements."""
    
    def __init__(self, state_synchronizer, db_connection, session_state_manager, config):
        self.state_synchronizer = state_synchronizer
        self.conn = db_connection
        self.session_state_manager = session_state_manager
        self.config = config
        self.last_sync_time = None
        self.sync_interval = config.STATE_SYNC_INTERVAL_SEC
        
    def sync_project_states(self):
        """
        Synchronize project states between database and session states.
        
        This ensures consistency between:
        - SQLite project_queue table
        - SessionState JSON files
        - Tmux session actual states
        """
        try:
            current_time = time.time()
            
            # Check if enough time has passed since last sync
            if self.last_sync_time and (current_time - self.last_sync_time) < self.sync_interval:
                return
                
            self.last_sync_time = current_time
            
            logger.debug("Starting state synchronization...")
            
            # Get all active projects from database
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, spec_path, main_session, status
                FROM project_queue
                WHERE status IN ('processing', 'queued')
            """)
            
            db_projects = {}
            for project_id, spec_path, main_session, status in cursor.fetchall():
                db_projects[project_id] = {
                    'spec_path': spec_path,
                    'main_session': main_session,
                    'status': status
                }
                
            # Get all session states
            session_states = self._get_all_session_states()
            
            # Sync database to session states
            for project_id, project_info in db_projects.items():
                if project_info['main_session']:
                    session_name = project_info['main_session'].split('-')[0] if '-' in project_info['main_session'] else project_info['main_session']
                    
                    # Check if session state exists
                    state = self.session_state_manager.load_session_state(session_name)
                    
                    if not state:
                        # Create missing session state
                        logger.info(f"Creating missing session state for {session_name}")
                        state = self.session_state_manager.create_session_state(
                            session_name=project_info['main_session'],
                            project_path=Path(project_info['spec_path']).parent if project_info['spec_path'] else None
                        )
                        
                    # Update state if needed
                    if state and project_info['status'] == 'processing':
                        if not state.is_active:
                            state.is_active = True
                            self.session_state_manager.save_session_state(state)
                            
            # Check for orphaned session states (no corresponding DB entry)
            for session_name in session_states:
                found = False
                for project_info in db_projects.values():
                    if project_info['main_session'] and session_name in project_info['main_session']:
                        found = True
                        break
                        
                if not found:
                    state = self.session_state_manager.load_session_state(session_name)
                    if state and state.is_active:
                        logger.warning(f"Orphaned active session state: {session_name}")
                        # Mark as inactive
                        state.is_active = False
                        self.session_state_manager.save_session_state(state)
                        
            logger.debug("State synchronization complete")
            
        except Exception as e:
            logger.error(f"Error synchronizing states: {e}", exc_info=True)
            
    def repair_null_sessions(self):
        """
        Repair projects with null main_session by finding their tmux sessions.
        
        This can happen when:
        - Database updates fail partially
        - Sessions are created but not recorded
        - Recovery from crashes
        """
        try:
            cursor = self.conn.cursor()
            
            # Find projects with null sessions
            cursor.execute("""
                SELECT id, spec_path
                FROM project_queue
                WHERE status = 'processing' AND main_session IS NULL
            """)
            
            null_sessions = cursor.fetchall()
            
            if not null_sessions:
                return
                
            logger.info(f"Found {len(null_sessions)} project(s) with null sessions")
            
            # Use StateSynchronizer to repair
            for project_id, spec_path in null_sessions:
                repaired = self.state_synchronizer.repair_null_session(project_id, spec_path)
                
                if repaired:
                    logger.info(f"✅ Repaired null session for project {project_id}")
                else:
                    logger.warning(f"Could not repair session for project {project_id}")
                    
        except Exception as e:
            logger.error(f"Error repairing null sessions: {e}", exc_info=True)
            
    def _get_all_session_states(self) -> List[str]:
        """
        Get list of all session state names.
        
        Returns:
            List of session names that have state files
        """
        try:
            registry_path = Path(self.session_state_manager.registry_path)
            session_files = registry_path.glob("session_*.json")
            
            session_names = []
            for file_path in session_files:
                # Extract session name from filename
                name = file_path.stem.replace("session_", "")
                session_names.append(name)
                
            return session_names
            
        except Exception as e:
            logger.error(f"Error getting session states: {e}")
            return []
            
    def validate_state_consistency(self) -> Dict[str, Any]:
        """
        Validate consistency between different state stores.
        
        Returns:
            Dictionary with validation results
        """
        results = {
            'consistent': True,
            'issues': []
        }
        
        try:
            # Check database vs session states
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM project_queue
                WHERE status = 'processing'
            """)
            
            db_processing = cursor.fetchone()[0]
            
            # Count active session states
            session_states = self._get_all_session_states()
            active_states = 0
            
            for session_name in session_states:
                state = self.session_state_manager.load_session_state(session_name)
                if state and state.is_active:
                    active_states += 1
                    
            # Check for mismatches
            if db_processing != active_states:
                results['consistent'] = False
                results['issues'].append(
                    f"Mismatch: {db_processing} processing in DB, {active_states} active session states"
                )
                
            # Check for tmux session mismatches
            import subprocess
            result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'],
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                tmux_sessions = result.stdout.strip().split('\n')
                orchestrator_sessions = [s for s in tmux_sessions if 'orchestrator' in s.lower()]
                
                if len(orchestrator_sessions) != active_states:
                    results['consistent'] = False
                    results['issues'].append(
                        f"Mismatch: {len(orchestrator_sessions)} tmux sessions, {active_states} active states"
                    )
                    
        except Exception as e:
            results['consistent'] = False
            results['issues'].append(f"Validation error: {str(e)}")
            
        return results
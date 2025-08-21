#!/usr/bin/env python3
"""
State Synchronizer - Synchronizes SQLite queue and JSON session states

This module prevents state mismatches that can cause phantom PROCESSING projects
or orphaned tmux sessions by maintaining consistency between:
1. SQLite project_queue table (authoritative for project status)
2. JSON session_state files (authoritative for tmux session details)

Key Functions:
- Detect and repair session_name corruption in database
- Cleanup orphaned JSON session states 
- Reconcile tmux sessions with database entries
- Proactive state validation and repair
"""

import sqlite3
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class StateMismatch:
    """Represents a detected state mismatch between systems"""
    type: str  # 'missing_session_name', 'orphaned_json', 'dead_tmux_session', 'session_name_mismatch'
    project_id: int
    description: str
    severity: str  # 'critical', 'warning', 'info'
    recommended_action: str
    details: Dict = None

class StateSynchronizer:
    """Synchronizes state between SQLite queue and JSON session states"""
    
    def __init__(self, db_path: str = "task_queue.db", registry_dir: str = "registry"):
        self.db_path = Path(db_path)
        self.registry_dir = Path(registry_dir)
        self.projects_dir = self.registry_dir / "projects"
        
        # Ensure directories exist
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        
    def get_database_projects(self) -> List[Dict]:
        """Get all projects from SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, spec_path, project_path, status, session_name,
                       enqueued_at, started_at, completed_at, error_message
                FROM project_queue 
                ORDER BY id
            """)
            
            projects = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return projects
            
        except Exception as e:
            logger.error(f"Failed to get database projects: {e}")
            return []
    
    def get_json_session_states(self) -> List[Dict]:
        """Get all JSON session state files"""
        session_states = []
        
        try:
            for project_dir in self.projects_dir.iterdir():
                if not project_dir.is_dir():
                    continue
                    
                state_file = project_dir / "session_state.json"
                if not state_file.exists():
                    continue
                    
                try:
                    with open(state_file, 'r') as f:
                        state_data = json.load(f)
                        state_data['_file_path'] = str(state_file)
                        state_data['_project_dir'] = str(project_dir)
                        session_states.append(state_data)
                        
                except Exception as e:
                    logger.warning(f"Failed to read {state_file}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to scan session states: {e}")
            
        return session_states
    
    def get_active_tmux_sessions(self) -> Set[str]:
        """Get list of active tmux session names"""
        try:
            result = subprocess.run(
                ['tmux', 'list-sessions', '-F', '#{session_name}'],
                capture_output=True, text=True, check=False
            )
            
            if result.returncode == 0:
                return set(line.strip() for line in result.stdout.strip().split('\n') if line.strip())
            else:
                logger.warning("No tmux sessions found or tmux not running")
                return set()
                
        except Exception as e:
            logger.error(f"Failed to get tmux sessions: {e}")
            return set()
    
    def detect_mismatches(self) -> List[StateMismatch]:
        """Detect state mismatches between systems"""
        mismatches = []
        
        # Get current state from all systems
        db_projects = self.get_database_projects()
        json_states = self.get_json_session_states()
        active_sessions = self.get_active_tmux_sessions()
        
        logger.info(f"State analysis: {len(db_projects)} DB projects, {len(json_states)} JSON states, {len(active_sessions)} tmux sessions")
        
        # Create lookup maps
        db_by_session_name = {p['session_name']: p for p in db_projects if p['session_name']}
        json_by_session_name = {s.get('session_name'): s for s in json_states if s.get('session_name')}
        
        # 1. Check for missing/null session_name in database
        for project in db_projects:
            if project['status'] == 'PROCESSING' and not project['session_name']:
                mismatches.append(StateMismatch(
                    type='missing_session_name',
                    project_id=project['id'],
                    description=f"Project {project['id']} is PROCESSING but has null session_name",
                    severity='critical',
                    recommended_action='repair_session_name_from_json_or_reset_to_queued',
                    details={'project': project}
                ))
        
        # 2. Check for orphaned JSON session states
        for json_state in json_states:
            session_name = json_state.get('session_name')
            if not session_name:
                continue
                
            # Check if corresponding DB project exists
            db_project = db_by_session_name.get(session_name)
            if not db_project:
                mismatches.append(StateMismatch(
                    type='orphaned_json',
                    project_id=0,  # No DB project
                    description=f"JSON session state exists for '{session_name}' but no corresponding DB project",
                    severity='warning',
                    recommended_action='cleanup_orphaned_json_state',
                    details={'json_state': json_state}
                ))
            elif db_project['status'] not in ['PROCESSING']:
                mismatches.append(StateMismatch(
                    type='stale_json_state',
                    project_id=db_project['id'],
                    description=f"JSON session state exists for '{session_name}' but DB project is {db_project['status']}",
                    severity='info',
                    recommended_action='cleanup_stale_json_state',
                    details={'json_state': json_state, 'project': db_project}
                ))
        
        # 3. Check for dead tmux sessions referenced in database
        for project in db_projects:
            if project['status'] == 'PROCESSING' and project['session_name']:
                if project['session_name'] not in active_sessions:
                    mismatches.append(StateMismatch(
                        type='dead_tmux_session',
                        project_id=project['id'],
                        description=f"Project {project['id']} references dead tmux session '{project['session_name']}'",
                        severity='critical',
                        recommended_action='reset_project_to_failed_or_queued',
                        details={'project': project}
                    ))
        
        # 4. Check for session name mismatches between DB and JSON
        for session_name, db_project in db_by_session_name.items():
            json_state = json_by_session_name.get(session_name)
            if json_state:
                # Check if project paths match (basic consistency check)
                db_path = db_project.get('project_path', '').rstrip('/')
                json_path = json_state.get('project_path', '').rstrip('/')
                
                if db_path and json_path and db_path != json_path:
                    mismatches.append(StateMismatch(
                        type='session_name_mismatch',
                        project_id=db_project['id'],
                        description=f"Session '{session_name}' has mismatched project paths: DB='{db_path}' vs JSON='{json_path}'",
                        severity='warning',
                        recommended_action='verify_session_consistency',
                        details={'project': db_project, 'json_state': json_state}
                    ))
        
        return mismatches
    
    def repair_missing_session_name(self, project_id: int) -> bool:
        """Attempt to repair missing session_name from JSON state"""
        try:
            # Find corresponding JSON state by project path
            db_projects = self.get_database_projects()
            project = next((p for p in db_projects if p['id'] == project_id), None)
            
            if not project:
                logger.error(f"Project {project_id} not found in database")
                return False
                
            project_path = project.get('project_path', '').rstrip('/')
            if not project_path:
                logger.error(f"Project {project_id} has no project_path")
                return False
            
            # Search JSON states for matching project path
            json_states = self.get_json_session_states()
            matching_state = None
            
            for state in json_states:
                state_path = state.get('project_path', '').rstrip('/')
                if state_path == project_path:
                    matching_state = state
                    break
            
            if not matching_state:
                logger.warning(f"No JSON state found for project {project_id} path '{project_path}'")
                return False
                
            session_name = matching_state.get('session_name')
            if not session_name:
                logger.warning(f"JSON state for project {project_id} has no session_name")
                return False
            
            # Update database with recovered session_name
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE project_queue 
                SET session_name = ? 
                WHERE id = ?
            """, (session_name, project_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Repaired session_name for project {project_id}: '{session_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to repair session_name for project {project_id}: {e}")
            return False
    
    def cleanup_orphaned_json_state(self, json_state: Dict) -> bool:
        """Remove orphaned JSON session state file"""
        try:
            file_path = Path(json_state['_file_path'])
            project_dir = Path(json_state['_project_dir'])
            
            # Remove the session state file
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Removed orphaned JSON state: {file_path}")
            
            # Remove project directory if it's empty
            if project_dir.exists() and project_dir.is_dir():
                try:
                    project_dir.rmdir()  # Only removes if empty
                    logger.info(f"Removed empty project directory: {project_dir}")
                except OSError:
                    # Directory not empty, leave it
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned JSON state: {e}")
            return False
    
    def reset_project_to_failed(self, project_id: int, reason: str = "dead_tmux_session") -> bool:
        """Reset a project to FAILED status due to dead session"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE project_queue 
                SET status = 'FAILED', 
                    completed_at = ?,
                    error_message = ?
                WHERE id = ?
            """, (datetime.now().timestamp(), f"State sync: {reason}", project_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Reset project {project_id} to FAILED due to {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset project {project_id}: {e}")
            return False
    
    def auto_repair_mismatches(self, mismatches: List[StateMismatch], dry_run: bool = False) -> Dict[str, int]:
        """Automatically repair detected mismatches"""
        results = {
            'repaired': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for mismatch in mismatches:
            if dry_run:
                logger.info(f"DRY RUN: Would repair {mismatch.type} for project {mismatch.project_id}")
                results['skipped'] += 1
                continue
            
            success = False
            
            if mismatch.type == 'missing_session_name':
                success = self.repair_missing_session_name(mismatch.project_id)
                
            elif mismatch.type == 'orphaned_json':
                success = self.cleanup_orphaned_json_state(mismatch.details['json_state'])
                
            elif mismatch.type == 'stale_json_state':
                success = self.cleanup_orphaned_json_state(mismatch.details['json_state'])
                
            elif mismatch.type == 'dead_tmux_session':
                success = self.reset_project_to_failed(mismatch.project_id, "dead_tmux_session")
            
            if success:
                results['repaired'] += 1
                logger.info(f"Repaired {mismatch.type} for project {mismatch.project_id}")
            else:
                results['failed'] += 1
                logger.error(f"Failed to repair {mismatch.type} for project {mismatch.project_id}")
        
        return results
    
    def generate_report(self, mismatches: List[StateMismatch]) -> str:
        """Generate human-readable state synchronization report"""
        if not mismatches:
            return "✅ State Synchronization Report: All systems in sync, no mismatches detected."
        
        report = []
        report.append(f"🔍 State Synchronization Report - {len(mismatches)} mismatches detected")
        report.append("=" * 70)
        
        # Group by severity
        critical = [m for m in mismatches if m.severity == 'critical']
        warnings = [m for m in mismatches if m.severity == 'warning']
        info = [m for m in mismatches if m.severity == 'info']
        
        if critical:
            report.append(f"\n🚨 CRITICAL ISSUES ({len(critical)}):")
            for mismatch in critical:
                report.append(f"  • Project {mismatch.project_id}: {mismatch.description}")
                report.append(f"    Action: {mismatch.recommended_action}")
        
        if warnings:
            report.append(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for mismatch in warnings:
                report.append(f"  • Project {mismatch.project_id}: {mismatch.description}")
                report.append(f"    Action: {mismatch.recommended_action}")
        
        if info:
            report.append(f"\n📋 INFO ({len(info)}):")
            for mismatch in info:
                report.append(f"  • Project {mismatch.project_id}: {mismatch.description}")
                report.append(f"    Action: {mismatch.recommended_action}")
        
        return "\n".join(report)

def main():
    """CLI interface for state synchronization"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Synchronize SQLite queue and JSON session states')
    parser.add_argument('--detect', action='store_true', help='Detect mismatches only')
    parser.add_argument('--repair', action='store_true', help='Auto-repair detected mismatches')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be repaired without making changes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')
    
    synchronizer = StateSynchronizer()
    
    # Detect mismatches
    mismatches = synchronizer.detect_mismatches()
    
    # Generate and print report
    report = synchronizer.generate_report(mismatches)
    print(report)
    
    if args.repair and mismatches:
        print(f"\n🔧 Auto-repairing {len(mismatches)} mismatches...")
        results = synchronizer.auto_repair_mismatches(mismatches, dry_run=args.dry_run)
        
        print(f"\nRepair Results:")
        print(f"  Repaired: {results['repaired']}")
        print(f"  Failed: {results['failed']}")
        print(f"  Skipped: {results['skipped']}")
        
        if results['repaired'] > 0:
            print("\n✅ State synchronization completed successfully!")
        elif results['failed'] > 0:
            print("\n❌ Some repairs failed. Check logs for details.")

if __name__ == "__main__":
    main()
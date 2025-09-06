#!/usr/bin/env python3
"""
CIIS Project Fixer for Tmux Orchestrator

Fixes missing project_path and incorrect session_name for CIIS batch projects.
This ensures the completion monitor can properly detect when CIIS projects are done.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class CIISProjectFixer:
    """Fixes CIIS project metadata in the queue database"""
    
    def __init__(self, db_path: str = "/home/clauderun/Tmux-Orchestrator/task_queue.db"):
        self.db_path = db_path
        self.signalmatrix_base = Path("/home/clauderun/signalmatrix/signalmatrix_org")
    
    def fix_ciis_project(self, project_id: int) -> bool:
        """
        Fix a CIIS project's missing metadata.
        
        Args:
            project_id: The project ID to fix
            
        Returns:
            True if fixed successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get project details
            cursor.execute("""
                SELECT spec_path, project_path, session_name, main_session
                FROM project_queue
                WHERE id = ?
            """, (project_id,))
            
            result = cursor.fetchone()
            if not result:
                logger.error(f"Project {project_id} not found")
                return False
            
            spec_path, project_path, session_name, main_session = result
            
            # Check if it's a CIIS project
            if not spec_path or '.ciis/batch_specs' not in spec_path:
                logger.info(f"Project {project_id} is not a CIIS project")
                return False
            
            # Parse CIIS spec to get slice information
            project_path_fixed, session_name_fixed = self._get_ciis_metadata(spec_path)
            
            if not project_path_fixed:
                logger.warning(f"Could not determine project path for {spec_path}")
                return False
            
            # Update the database
            updates = []
            params = []
            
            if not project_path:
                updates.append("project_path = ?")
                params.append(str(project_path_fixed))
                logger.info(f"Setting project_path to {project_path_fixed}")
            
            # Fix session name if it's a restored session
            if session_name and session_name.startswith("restored-"):
                # Try to find the actual session
                actual_session = self._find_actual_session(project_id)
                if actual_session:
                    updates.append("session_name = ?")
                    params.append(actual_session)
                    logger.info(f"Updating session_name from {session_name} to {actual_session}")
            elif not session_name and session_name_fixed:
                updates.append("session_name = ?")
                params.append(session_name_fixed)
                logger.info(f"Setting session_name to {session_name_fixed}")
            
            if updates:
                params.append(project_id)
                cursor.execute(f"""
                    UPDATE project_queue
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, params)
                conn.commit()
                logger.info(f"✅ Fixed project {project_id}")
                return True
            else:
                logger.info(f"Project {project_id} already has correct metadata")
                return True
                
        except Exception as e:
            logger.error(f"Error fixing project {project_id}: {e}")
            return False
        finally:
            conn.close()
    
    def _get_ciis_metadata(self, spec_path: str) -> Tuple[Optional[Path], Optional[str]]:
        """
        Extract project path and session name from CIIS spec.
        
        Returns:
            Tuple of (project_path, session_name)
        """
        try:
            spec_file = Path(spec_path)
            if not spec_file.exists():
                return None, None
            
            with open(spec_file) as f:
                spec_data = json.load(f)
            
            # Extract slice information
            slices = []
            if 'slice_ids' in spec_data:
                slices = spec_data['slice_ids']
            elif 'target_slices' in spec_data:
                slices = spec_data['target_slices']
            elif 'slices' in spec_data:
                slices = spec_data['slices']
            
            # Get primary slice for project path
            if slices:
                primary_slice = slices[0] if isinstance(slices, list) else slices
                project_path = self.signalmatrix_base / f"signalmatrix-slice-{primary_slice}"
                
                if project_path.exists() and (project_path / '.git').exists():
                    # Generate session name from spec file name
                    spec_name = spec_file.stem
                    # Convert batch_prop-20250905165836-1_20250905_165836 to batch-prop-202509051-xxxxx
                    if spec_name.startswith("batch_"):
                        parts = spec_name.split('_')
                        if len(parts) >= 3:
                            batch_type = parts[0].replace('_', '-')
                            batch_id = parts[1].split('-')[1] if '-' in parts[1] else parts[1]
                            session_name = f"{batch_type}-{batch_id[:9]}"
                        else:
                            session_name = spec_name.replace('_', '-')[:20]
                    else:
                        session_name = spec_name.replace('_', '-')[:20]
                    
                    return project_path, session_name
            
            return None, None
            
        except Exception as e:
            logger.error(f"Error parsing CIIS spec {spec_path}: {e}")
            return None, None
    
    def _find_actual_session(self, project_id: int) -> Optional[str]:
        """
        Try to find the actual tmux session for a project.
        
        Returns:
            Session name if found
        """
        import subprocess
        
        try:
            # Get list of active tmux sessions
            result = subprocess.run(
                ['tmux', 'list-sessions', '-F', '#{session_name}'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                sessions = result.stdout.strip().split('\n')
                
                # Look for sessions that might match this project
                # Pattern: batch-prop-YYYYMMDD or similar
                for session in sessions:
                    if 'batch' in session and 'prop' in session:
                        # This is likely our session
                        return session
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding session for project {project_id}: {e}")
            return None
    
    def fix_all_ciis_projects(self) -> int:
        """
        Fix all CIIS projects with missing metadata.
        
        Returns:
            Number of projects fixed
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Find all CIIS projects with missing metadata
            cursor.execute("""
                SELECT id
                FROM project_queue
                WHERE spec_path LIKE '%.ciis/batch_specs%'
                AND (project_path IS NULL OR project_path = '' 
                     OR session_name LIKE 'restored-%')
                AND status IN ('processing', 'queued')
            """)
            
            projects = cursor.fetchall()
            fixed_count = 0
            
            for (project_id,) in projects:
                if self.fix_ciis_project(project_id):
                    fixed_count += 1
            
            logger.info(f"Fixed {fixed_count} out of {len(projects)} CIIS projects")
            return fixed_count
            
        finally:
            conn.close()


if __name__ == "__main__":
    import sys
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description='Fix CIIS project metadata')
    parser.add_argument('project_id', nargs='?', type=int,
                       help='Specific project ID to fix (optional)')
    parser.add_argument('--all', action='store_true',
                       help='Fix all CIIS projects with missing metadata')
    
    args = parser.parse_args()
    
    fixer = CIISProjectFixer()
    
    if args.all:
        fixed = fixer.fix_all_ciis_projects()
        print(f"✅ Fixed {fixed} CIIS projects")
    elif args.project_id:
        if fixer.fix_ciis_project(args.project_id):
            print(f"✅ Fixed project {args.project_id}")
        else:
            print(f"❌ Failed to fix project {args.project_id}")
            sys.exit(1)
    else:
        parser.print_help()
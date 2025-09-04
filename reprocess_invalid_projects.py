#!/usr/bin/env python3
"""
Re-processing workflow for projects with invalid or incomplete implementations.
This script identifies projects marked as complete but failing spec validation,
and re-queues them for proper implementation.
"""

import sys
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from tmux_orchestrator.core.validation import ProjectValidator
from scheduler import SchedulerDaemon

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/reprocess.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ProjectReprocessor:
    """Handles re-processing of invalid or incomplete projects."""
    
    def __init__(self, db_path: str = "task_queue.db"):
        """Initialize reprocessor with database connection."""
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.validator = ProjectValidator()
        self.scheduler = SchedulerDaemon()
    
    def find_invalid_projects(self, validate_all: bool = False) -> List[Dict[str, Any]]:
        """
        Find projects that need re-processing.
        
        Args:
            validate_all: If True, validate all completed projects.
                         If False, only check those with low/missing validation scores.
        
        Returns:
            List of projects needing re-processing
        """
        cursor = self.conn.cursor()
        
        if validate_all:
            # Get all completed projects
            cursor.execute("""
                SELECT id, spec_path, project_path, validation_score, 
                       completed_at, main_session, spec_version
                FROM project_queue 
                WHERE status IN ('completed', 'merged')
                ORDER BY completed_at DESC
            """)
        else:
            # Get projects with low or missing validation scores
            cursor.execute("""
                SELECT id, spec_path, project_path, validation_score, 
                       completed_at, main_session, spec_version
                FROM project_queue 
                WHERE status IN ('completed', 'merged')
                  AND (validation_score < 70 OR validation_score IS NULL)
                ORDER BY completed_at DESC
            """)
        
        projects = []
        for row in cursor.fetchall():
            projects.append({
                'id': row['id'],
                'spec_path': row['spec_path'],
                'project_path': row['project_path'],
                'validation_score': row['validation_score'],
                'completed_at': row['completed_at'],
                'main_session': row['main_session'],
                'spec_version': row['spec_version']
            })
        
        logger.info(f"Found {len(projects)} projects to check")
        return projects
    
    def validate_project(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a project against its spec.
        
        Args:
            project: Project information from database
        
        Returns:
            Validation results
        """
        project_path = project.get('project_path')
        if not project_path:
            # Try to derive from spec path
            spec_path = Path(project.get('spec_path', ''))
            if spec_path.exists():
                project_path = spec_path.parent
            else:
                logger.error(f"Cannot find project path for ID {project['id']}")
                return {'passed': False, 'score': 0, 'error': 'No project path'}
        
        project_path = Path(project_path)
        if not project_path.exists():
            logger.warning(f"Project path does not exist: {project_path}")
            return {'passed': False, 'score': 0, 'error': 'Project path not found'}
        
        logger.info(f"Validating project {project['id']}: {project_path}")
        
        # Get comprehensive validation report
        report = self.validator.get_validation_report(project_path)
        
        # Extract key metrics
        result = {
            'passed': report.get('passed', False),
            'basic_checks': report.get('basic_checks', {}),
            'spec_validation': report.get('spec_validation', {})
        }
        
        # Calculate overall score
        if result['spec_validation']:
            result['score'] = result['spec_validation'].get('overall_score', 0)
        else:
            # Basic validation only
            basic_passed = sum(1 for v in result['basic_checks'].values() if v)
            result['score'] = (basic_passed / 4) * 100 if result['basic_checks'] else 0
        
        return result
    
    def update_validation_scores(self, project_id: int, validation: Dict[str, Any]):
        """
        Update validation scores in database.
        
        Args:
            project_id: Project ID
            validation: Validation results
        """
        cursor = self.conn.cursor()
        
        score = validation.get('score', 0)
        details = {
            'basic_checks': validation.get('basic_checks', {}),
            'spec_validation': validation.get('spec_validation', {}),
            'timestamp': datetime.now().isoformat()
        }
        
        # Extract spec requirements if available
        spec_requirements = None
        if validation.get('spec_validation'):
            spec_validation = validation['spec_validation']
            if 'code_details' in spec_validation:
                # Build a summary of requirements
                code_details = spec_validation['code_details']
                spec_requirements = {
                    'api_endpoints': code_details.get('api_endpoints', {}),
                    'user_stories': code_details.get('user_stories', {}),
                    'acceptance_criteria': code_details.get('acceptance_criteria', {})
                }
        
        cursor.execute("""
            UPDATE project_queue 
            SET validation_score = ?, 
                validation_details = ?,
                spec_requirements = ?
            WHERE id = ?
        """, (score, json.dumps(details), json.dumps(spec_requirements) if spec_requirements else None, project_id))
        
        self.conn.commit()
        logger.info(f"Updated validation score for project {project_id}: {score:.1f}%")
    
    def requeue_project(self, project: Dict[str, Any], reason: str = "validation_failed"):
        """
        Re-queue a project for re-processing.
        
        Args:
            project: Project information
            reason: Reason for re-queueing
        """
        project_id = project['id']
        
        logger.info(f"Re-queueing project {project_id} - Reason: {reason}")
        
        # Use scheduler's reset method if available
        if hasattr(self.scheduler, 'reset_project_to_queued'):
            success = self.scheduler.reset_project_to_queued(project_id)
            if success:
                logger.info(f"Successfully re-queued project {project_id}")
            else:
                logger.error(f"Failed to re-queue project {project_id}")
        else:
            # Manual reset
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE project_queue 
                SET status = 'queued',
                    error_message = ?,
                    retry_count = retry_count + 1,
                    validation_score = NULL,
                    validation_details = NULL
                WHERE id = ?
            """, (f"Re-queued: {reason}", project_id))
            self.conn.commit()
            logger.info(f"Manually re-queued project {project_id}")
    
    def process_invalid_projects(self, project_ids: Optional[List[int]] = None,
                                validate_all: bool = False,
                                dry_run: bool = False) -> Dict[str, Any]:
        """
        Main processing method to validate and re-queue invalid projects.
        
        Args:
            project_ids: Specific project IDs to process (e.g., [83, 84])
            validate_all: Validate all completed projects
            dry_run: If True, only report what would be done
        
        Returns:
            Summary of processing results
        """
        logger.info("=" * 60)
        logger.info("Starting project re-processing workflow")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        logger.info("=" * 60)
        
        # Get projects to process
        if project_ids:
            # Specific projects requested
            cursor = self.conn.cursor()
            projects = []
            for pid in project_ids:
                cursor.execute("""
                    SELECT id, spec_path, project_path, validation_score, 
                           completed_at, main_session, spec_version
                    FROM project_queue 
                    WHERE id = ?
                """, (pid,))
                row = cursor.fetchone()
                if row:
                    projects.append({
                        'id': row[0],
                        'spec_path': row[1],
                        'project_path': row[2],
                        'validation_score': row[3],
                        'completed_at': row[4],
                        'main_session': row[5],
                        'spec_version': row[6]
                    })
                else:
                    logger.warning(f"Project {pid} not found")
        else:
            # Find invalid projects automatically
            projects = self.find_invalid_projects(validate_all)
        
        # Process each project
        results = {
            'total': len(projects),
            'validated': 0,
            'passed': 0,
            'failed': 0,
            'requeued': 0,
            'errors': 0,
            'details': []
        }
        
        for project in projects:
            logger.info(f"\nProcessing project {project['id']}: {project['spec_path']}")
            
            try:
                # Validate project
                validation = self.validate_project(project)
                results['validated'] += 1
                
                # Update scores in database (even in dry run)
                self.update_validation_scores(project['id'], validation)
                
                if validation['passed']:
                    results['passed'] += 1
                    logger.info(f"✓ Project {project['id']} passed validation (score: {validation['score']:.1f}%)")
                else:
                    results['failed'] += 1
                    logger.warning(f"✗ Project {project['id']} failed validation (score: {validation['score']:.1f}%)")
                    
                    # Re-queue if not in dry run mode
                    if not dry_run:
                        self.requeue_project(project, f"validation_score={validation['score']:.1f}")
                        results['requeued'] += 1
                    else:
                        logger.info(f"[DRY RUN] Would re-queue project {project['id']}")
                
                # Store details
                results['details'].append({
                    'id': project['id'],
                    'spec_path': project['spec_path'],
                    'score': validation['score'],
                    'passed': validation['passed'],
                    'issues': validation.get('spec_validation', {}).get('issues', []) if validation.get('spec_validation') else []
                })
                
            except Exception as e:
                logger.error(f"Error processing project {project['id']}: {e}")
                results['errors'] += 1
                results['details'].append({
                    'id': project['id'],
                    'error': str(e)
                })
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("RE-PROCESSING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total projects checked: {results['total']}")
        logger.info(f"Successfully validated: {results['validated']}")
        logger.info(f"Passed validation: {results['passed']}")
        logger.info(f"Failed validation: {results['failed']}")
        if not dry_run:
            logger.info(f"Re-queued for processing: {results['requeued']}")
        else:
            logger.info(f"Would re-queue: {results['failed']}")
        logger.info(f"Errors encountered: {results['errors']}")
        
        # Show failed projects
        if results['failed'] > 0:
            logger.info("\nFailed Projects:")
            for detail in results['details']:
                if detail.get('passed') is False:
                    logger.info(f"  - ID {detail['id']}: {detail['spec_path']} (score: {detail.get('score', 0):.1f}%)")
                    if detail.get('issues'):
                        for issue in detail['issues'][:3]:
                            logger.info(f"    • {issue}")
        
        return results


def main():
    """Main entry point for the reprocessor script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Re-process invalid or incomplete projects')
    parser.add_argument('--project-ids', nargs='+', type=int,
                       help='Specific project IDs to process (e.g., 83 84)')
    parser.add_argument('--validate-all', action='store_true',
                       help='Validate all completed projects, not just those with low scores')
    parser.add_argument('--dry-run', action='store_true',
                       help='Only report what would be done, don\'t actually re-queue')
    parser.add_argument('--db', default='task_queue.db',
                       help='Path to database file')
    
    args = parser.parse_args()
    
    try:
        reprocessor = ProjectReprocessor(args.db)
        results = reprocessor.process_invalid_projects(
            project_ids=args.project_ids,
            validate_all=args.validate_all,
            dry_run=args.dry_run
        )
        
        # Exit with error code if failures found
        if results['failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()
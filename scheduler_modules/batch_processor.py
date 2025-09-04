#!/usr/bin/env python3
"""
Batch processor module extracted from scheduler.py
Handles batch monitoring and processing logic.
"""

import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Handles batch processing and monitoring."""
    
    def __init__(self, scheduler_instance):
        self.scheduler = scheduler_instance
        self.monitoring_enabled = True
        self.last_batch_check = None
        self.batch_start_time = None
        self.batch_metrics = {
            'total_projects': 0,
            'completed': 0,
            'failed': 0,
            'processing': 0,
            'queued': 0
        }
        
    def monitor_batches(self):
        """
        Monitor batch processing and report progress.
        Tracks metrics and sends periodic summaries.
        """
        if not self.monitoring_enabled:
            return
            
        try:
            current_time = time.time()
            
            # Check every 60 seconds
            if self.last_batch_check and (current_time - self.last_batch_check) < 60:
                return
                
            self.last_batch_check = current_time
            
            # Get current batch status
            cursor = self.scheduler.conn.cursor()
            
            # Count projects by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM project_queue
                WHERE datetime(enqueued_at, 'unixepoch') > datetime('now', '-24 hours')
                GROUP BY status
            """)
            
            status_counts = {}
            for status, count in cursor.fetchall():
                status_counts[status] = count
                
            # Update metrics
            self.batch_metrics['queued'] = status_counts.get('queued', 0)
            self.batch_metrics['processing'] = status_counts.get('processing', 0)
            self.batch_metrics['completed'] = status_counts.get('completed', 0)
            self.batch_metrics['failed'] = status_counts.get('failed', 0)
            self.batch_metrics['total_projects'] = sum(status_counts.values())
            
            # Log if we have active batch
            if self.batch_metrics['total_projects'] > 0:
                logger.info(f"📊 Batch Status: "
                          f"Queued={self.batch_metrics['queued']}, "
                          f"Processing={self.batch_metrics['processing']}, "
                          f"Completed={self.batch_metrics['completed']}, "
                          f"Failed={self.batch_metrics['failed']}")
                
                # Calculate completion rate
                if self.batch_metrics['completed'] + self.batch_metrics['failed'] > 0:
                    total_finished = self.batch_metrics['completed'] + self.batch_metrics['failed']
                    success_rate = (self.batch_metrics['completed'] / total_finished) * 100
                    logger.info(f"Success rate: {success_rate:.1f}%")
                    
                # Check for stuck batches
                if self.batch_metrics['processing'] > 0:
                    cursor.execute("""
                        SELECT id, spec_path, 
                               (julianday('now') - julianday(started_at)) * 24 as hours_running
                        FROM project_queue
                        WHERE status = 'processing'
                        ORDER BY started_at
                        LIMIT 1
                    """)
                    
                    row = cursor.fetchone()
                    if row:
                        project_id, spec_path, hours_running = row
                        if hours_running and hours_running > 2:
                            logger.warning(f"⚠️  Long-running project: ID={project_id}, "
                                         f"Runtime={hours_running:.1f} hours, Spec={spec_path}")
                            
                # Send summary if batch is complete
                if (self.batch_metrics['queued'] == 0 and 
                    self.batch_metrics['processing'] == 0 and
                    self.batch_metrics['total_projects'] > 0):
                    
                    self._send_batch_summary()
                    
        except Exception as e:
            logger.error(f"Error monitoring batches: {e}", exc_info=True)
            
    def _send_batch_summary(self):
        """Send batch completion summary."""
        try:
            summary = f"""
📊 Batch Processing Complete
============================
Total Projects: {self.batch_metrics['total_projects']}
Completed: {self.batch_metrics['completed']}
Failed: {self.batch_metrics['failed']}
Success Rate: {(self.batch_metrics['completed'] / max(1, self.batch_metrics['total_projects'])) * 100:.1f}%
"""
            
            logger.info(summary)
            
            # Emit event for notifications
            if hasattr(self.scheduler, '_dispatch_event'):
                self.scheduler._dispatch_event('batch_complete', self.batch_metrics)
                
            # Reset metrics for next batch
            self.batch_metrics = {
                'total_projects': 0,
                'completed': 0,
                'failed': 0,
                'processing': 0,
                'queued': 0
            }
            
        except Exception as e:
            logger.error(f"Error sending batch summary: {e}", exc_info=True)
            
    def check_batch_timeout(self, project_id: int) -> bool:
        """
        Check if a project in a batch has timed out.
        
        Args:
            project_id: ID of project to check
            
        Returns:
            True if project has timed out, False otherwise
        """
        try:
            cursor = self.scheduler.conn.cursor()
            
            cursor.execute("""
                SELECT started_at, spec_path
                FROM project_queue
                WHERE id = ? AND status = 'processing'
            """, (project_id,))
            
            row = cursor.fetchone()
            if not row:
                return False
                
            started_at, spec_path = row
            
            if started_at:
                # Parse timestamp and check timeout
                try:
                    start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    elapsed = (datetime.now(start_time.tzinfo) - start_time).total_seconds()
                    
                    # Default 3 hour timeout for batch projects
                    timeout_seconds = 10800
                    
                    if elapsed > timeout_seconds:
                        logger.warning(f"Batch project timeout: ID={project_id}, "
                                     f"Runtime={elapsed/3600:.1f} hours, Spec={spec_path}")
                        return True
                        
                except Exception as e:
                    logger.debug(f"Could not check timeout for project {project_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error checking batch timeout: {e}", exc_info=True)
            
        return False
        
    def get_batch_statistics(self) -> Dict[str, Any]:
        """
        Get current batch processing statistics.
        
        Returns:
            Dictionary containing batch metrics
        """
        return self.batch_metrics.copy()
        
    def is_batch_active(self) -> bool:
        """
        Check if a batch is currently being processed.
        
        Returns:
            True if batch is active, False otherwise
        """
        return (self.batch_metrics['queued'] > 0 or 
                self.batch_metrics['processing'] > 0)
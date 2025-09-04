#!/usr/bin/env python3
"""
Queue manager module extracted from scheduler.py
Handles SQLite queue operations and state machine.
"""

import sqlite3
import logging
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ProjectState(Enum):
    """State machine for project lifecycle management"""
    QUEUED = 'queued'          # Initial state
    PROCESSING = 'processing'   # Active
    TIMING_OUT = 'timing_out'   # Pre-kill grace period
    ZOMBIE = 'zombie'           # Detected hang (PID alive, session dead)
    FAILED = 'failed'           # Terminal failure
    COMPLETED = 'completed'     # Terminal success
    RECOVERED = 'recovered'     # Manually recovered from failed/stuck
    
    @classmethod
    def valid_transitions(cls):
        """Define valid state transitions"""
        return {
            cls.QUEUED: [cls.PROCESSING],
            cls.PROCESSING: [cls.TIMING_OUT, cls.ZOMBIE, cls.FAILED, cls.COMPLETED, cls.RECOVERED],
            cls.TIMING_OUT: [cls.FAILED, cls.COMPLETED, cls.RECOVERED],
            cls.ZOMBIE: [cls.FAILED, cls.RECOVERED],
            cls.FAILED: [cls.RECOVERED],
            cls.COMPLETED: [],
            cls.RECOVERED: [cls.PROCESSING, cls.COMPLETED, cls.FAILED]
        }


class QueueManager:
    """Manages the project queue and state transitions."""
    
    def __init__(self, db_connection, config, lock_manager=None):
        self.conn = db_connection
        self.config = config
        self.lock_manager = lock_manager
        self.queue_lock = threading.Lock()
        
    def enqueue_project(self, spec_path: str, project_path: str, priority: int = 5,
                        metadata: Optional[Dict] = None) -> Optional[int]:
        """
        Add a project to the queue.
        
        Args:
            spec_path: Path to specification file
            project_path: Path to project directory
            priority: Priority level (1=highest, 10=lowest)
            metadata: Optional metadata dictionary
            
        Returns:
            Project ID if successful, None otherwise
        """
        try:
            with self.queue_lock:
                cursor = self.conn.cursor()
                
                # Check for duplicates
                cursor.execute("""
                    SELECT id, status FROM project_queue 
                    WHERE spec_path = ? AND status IN ('queued', 'processing')
                """, (spec_path,))
                
                existing = cursor.fetchone()
                if existing:
                    logger.warning(f"Project already in queue: {spec_path} (ID: {existing[0]}, Status: {existing[1]})")
                    return None
                
                # Insert new project
                cursor.execute("""
                    INSERT INTO project_queue 
                    (spec_path, project_path, status, priority, enqueued_at)
                    VALUES (?, ?, 'queued', ?, ?)
                """, (spec_path, project_path, priority, time.time()))
                
                project_id = cursor.lastrowid
                self.conn.commit()
                
                logger.info(f"✅ Enqueued project {project_id}: {spec_path}")
                
                # Store metadata if provided
                if metadata:
                    self._store_metadata(project_id, metadata)
                
                return project_id
                
        except Exception as e:
            logger.error(f"Error enqueueing project: {e}")
            if self.conn:
                self.conn.rollback()
            return None
            
    def get_next_project_atomic(self) -> Optional[Tuple[int, str, str]]:
        """
        Atomically get and mark the next project for processing with database-level locking.
        Uses BEGIN IMMEDIATE for shared lock to prevent races across modes.
        
        Returns:
            Tuple of (project_id, spec_path, project_path) or None
        """
        try:
            with self.queue_lock:
                cursor = self.conn.cursor()
                
                # ENHANCED: Use database transaction with IMMEDIATE mode for cross-process locking
                # This ensures atomicity even if multiple scheduler instances (queue/checkin) run concurrently
                cursor.execute("BEGIN IMMEDIATE")  # Critical: reserves DB for writing, prevents races
                
                try:
                    # Get highest priority queued project
                    cursor.execute("""
                        SELECT id, spec_path, project_path
                        FROM project_queue
                        WHERE status = 'queued'
                        ORDER BY priority ASC, enqueued_at ASC
                        LIMIT 1
                    """)
                    
                    row = cursor.fetchone()
                    if not row:
                        self.conn.rollback()  # Release lock on no project
                        return None
                    
                    project_id, spec_path, project_path = row
                    
                    # Atomically update to processing
                    cursor.execute("""
                        UPDATE project_queue
                        SET status = 'processing',
                            started_at = datetime('now'),
                            processing_started_at = ?
                        WHERE id = ? AND status = 'queued'
                    """, (time.time(), project_id))
                    
                    if cursor.rowcount == 0:
                        # Someone else grabbed it first
                        self.conn.rollback()
                        return None
                    
                    self.conn.commit()  # Commit and release lock atomically
                    
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower():
                        logger.warning("Database locked during dequeue; will retry later")
                        self.conn.rollback()
                        return None
                    raise
                except Exception:
                    self.conn.rollback()
                    raise
                
                logger.info(f"🎯 Dequeued project {project_id} for processing: {spec_path}")
                return project_id, spec_path, project_path
                
        except Exception as e:
            logger.error(f"Error getting next project: {e}")
            if self.conn:
                self.conn.rollback()
            return None
            
    def update_project_status(self, project_id: int, status: str, 
                            notes: Optional[str] = None,
                            session_name: Optional[str] = None,
                            process_pid: Optional[int] = None) -> bool:
        """
        Update project status with optional metadata.
        
        Args:
            project_id: Project ID to update
            status: New status
            notes: Optional notes
            session_name: Optional tmux session name
            process_pid: Optional process PID
            
        Returns:
            True if update successful
        """
        try:
            with self.queue_lock:
                cursor = self.conn.cursor()
                
                # Build update query
                updates = ["status = ?"]
                params = [status]
                
                if notes:
                    updates.append("notes = ?")
                    params.append(notes)
                    
                if session_name:
                    updates.append("main_session = ?")
                    params.append(session_name)
                    
                if process_pid:
                    updates.append("process_pid = ?")
                    params.append(process_pid)
                    
                # Add completion timestamp if terminal state
                if status in ['completed', 'failed']:
                    updates.append("ended_at = datetime('now')")
                    
                params.append(project_id)
                
                query = f"UPDATE project_queue SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"No project found with ID {project_id}")
                    return False
                    
                self.conn.commit()
                logger.info(f"Updated project {project_id} status to {status}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating project status: {e}")
            if self.conn:
                self.conn.rollback()
            return False
            
    def get_project_status(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current status and metadata for a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            Dictionary with project information or None
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, spec_path, project_path, status, priority,
                       enqueued_at, started_at, completed_at, error_message,
                       main_session, process_pid, enqueued_at
                FROM project_queue
                WHERE id = ?
            """, (project_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            return {
                'id': row[0],
                'spec_path': row[1],
                'project_path': row[2],
                'status': row[3],
                'priority': row[4],
                'enqueued_at': row[5],
                'started_at': row[6],
                'completed_at': row[7],
                'error_message': row[8],
                'main_session': row[9],
                'process_pid': row[10]
            }
            
        except Exception as e:
            logger.error(f"Error getting project status: {e}")
            return None
            
    def get_queue_status(self) -> Dict[str, int]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with counts by status
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM project_queue
                GROUP BY status
            """)
            
            status_counts = {}
            for status, count in cursor.fetchall():
                status_counts[status] = count
                
            return status_counts
            
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {}
            
    def get_active_projects(self) -> List[Dict[str, Any]]:
        """
        Get all active (processing) projects.
        
        Returns:
            List of project dictionaries
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, spec_path, project_path, main_session, process_pid, started_at
                FROM project_queue
                WHERE status = 'processing'
                ORDER BY started_at ASC
            """)
            
            projects = []
            for row in cursor.fetchall():
                projects.append({
                    'id': row[0],
                    'spec_path': row[1],
                    'project_path': row[2],
                    'main_session': row[3],
                    'process_pid': row[4],
                    'started_at': row[5]
                })
                
            return projects
            
        except Exception as e:
            logger.error(f"Error getting active projects: {e}")
            return []
            
    def cleanup_old_projects(self, days: int = 7) -> int:
        """
        Remove completed/failed projects older than specified days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of projects removed
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                DELETE FROM project_queue
                WHERE status IN ('completed', 'failed')
                AND datetime(ended_at) < datetime('now', ? || ' days')
            """, (-days,))
            
            deleted = cursor.rowcount
            if deleted > 0:
                self.conn.commit()
                logger.info(f"Cleaned up {deleted} old project(s)")
                
            return deleted
            
        except Exception as e:
            logger.error(f"Error cleaning up old projects: {e}")
            return 0
            
    def _store_metadata(self, project_id: int, metadata: Dict[str, Any]):
        """Store additional metadata for a project."""
        try:
            # Could store in a separate metadata table or as JSON
            # For now, store key items in notes field
            notes = []
            for key, value in metadata.items():
                notes.append(f"{key}: {value}")
                
            if notes:
                cursor = self.conn.cursor()
                cursor.execute("""
                    UPDATE project_queue
                    SET notes = ?
                    WHERE id = ?
                """, ("; ".join(notes), project_id))
                self.conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing metadata: {e}")
            
    def validate_state_transition(self, project_id: int, new_state: ProjectState) -> bool:
        """
        Validate if a state transition is allowed.
        
        Args:
            project_id: Project ID
            new_state: Proposed new state
            
        Returns:
            True if transition is valid
        """
        try:
            current_status = self.get_project_status(project_id)
            if not current_status:
                return False
                
            current_state = ProjectState(current_status['status'])
            valid_transitions = ProjectState.valid_transitions()
            
            if new_state in valid_transitions.get(current_state, []):
                return True
            else:
                logger.warning(f"Invalid state transition for project {project_id}: "
                             f"{current_state.value} -> {new_state.value}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating state transition: {e}")
            return False
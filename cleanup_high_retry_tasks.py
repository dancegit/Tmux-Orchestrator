#!/usr/bin/env python3
"""
Cleanup script to fix high-retry tasks causing message flooding.
This purges tasks with excessive retry counts and disables problematic one-time tasks.
"""

import sqlite3
import logging
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_high_retry_tasks(db_path='task_queue.db', retry_threshold=10):
    """Clean up tasks with high retry counts to stop flooding."""
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # First, let's see what we're dealing with
        cursor.execute("""
            SELECT COUNT(*) as count, MAX(retry_count) as max_retry 
            FROM tasks 
            WHERE retry_count >= ?
        """, (retry_threshold,))
        result = cursor.fetchone()
        high_retry_count = result[0] if result else 0
        max_retry = result[1] if result else 0
        
        logger.info(f"Found {high_retry_count} tasks with retry_count >= {retry_threshold} (max: {max_retry})")
        
        # Show sample of problematic tasks
        cursor.execute("""
            SELECT id, session_name, agent_role, interval_minutes, retry_count, note
            FROM tasks 
            WHERE retry_count >= ?
            ORDER BY retry_count DESC
            LIMIT 10
        """, (retry_threshold,))
        
        logger.info("Sample of high-retry tasks:")
        for row in cursor.fetchall():
            logger.info(f"  Task {row[0]}: session={row[1]}, role={row[2]}, interval={row[3]}, retries={row[4]}, note={row[5][:50]}...")
        
        # Purge high-retry tasks
        cursor.execute("""
            DELETE FROM tasks 
            WHERE retry_count >= ?
        """, (retry_threshold,))
        deleted_high = cursor.rowcount
        logger.info(f"Deleted {deleted_high} tasks with retry_count >= {retry_threshold}")
        
        # Disable one-time tasks with any retries (set far-future next_run)
        cursor.execute("""
            UPDATE tasks 
            SET next_run = strftime('%s', 'now') + 31536000,  -- 1 year
                retry_count = -1  -- Mark as disabled
            WHERE interval_minutes = 0 AND retry_count > 0
        """)
        disabled_one_time = cursor.rowcount
        logger.info(f"Disabled {disabled_one_time} one-time tasks with retries")
        
        # Also clean up any tasks that are scheduled but have interval_minutes=0 and note contains "completed"
        cursor.execute("""
            UPDATE tasks 
            SET next_run = strftime('%s', 'now') + 31536000,  -- 1 year
                retry_count = -1  -- Mark as disabled
            WHERE interval_minutes = 0 
            AND note LIKE '%completed%'
            AND next_run < strftime('%s', 'now') + 86400  -- Due within 24 hours
        """)
        disabled_completed = cursor.rowcount
        logger.info(f"Disabled {disabled_completed} completed one-time tasks")
        
        conn.commit()
        logger.info("Database cleanup completed successfully")
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        conn.rollback()
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()
    
    return True

if __name__ == '__main__':
    # Get database path from environment or use default
    db_path = os.getenv('TASK_DB_PATH', '/home/clauderun/Tmux-Orchestrator/task_queue.db')
    
    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        sys.exit(1)
    
    # Backup database first
    backup_path = f"{db_path}.backup_{os.getpid()}"
    logger.info(f"Creating backup at {backup_path}")
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        sys.exit(1)
    
    # Run cleanup with threshold of 10 retries
    success = cleanup_high_retry_tasks(db_path, retry_threshold=10)
    
    if success:
        logger.info("Cleanup completed successfully!")
        logger.info(f"Backup saved at: {backup_path}")
    else:
        logger.error("Cleanup failed - restoring from backup")
        try:
            shutil.copy2(backup_path, db_path)
            logger.info("Database restored from backup")
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
        sys.exit(1)
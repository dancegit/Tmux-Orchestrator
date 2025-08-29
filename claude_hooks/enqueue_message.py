#!/usr/bin/env python3
"""
Message enqueueing module for hooks-based message queue.
Provides functions to add messages to the database queue with proper sequencing.
"""

import sqlite3
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

# Configuration
DB_PATH = os.environ.get('QUEUE_DB_PATH', '/home/clauderun/Tmux-Orchestrator/task_queue.db')
TIMEOUT = 10.0  # SQLite busy timeout

def ensure_database_exists():
    """Ensure the database and tables exist."""
    db_path = Path(DB_PATH)
    if not db_path.exists():
        logger.error(f"Database not found at {DB_PATH}")
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    
    # Check if tables exist
    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='message_queue';")
        if not cursor.fetchone():
            logger.error("message_queue table not found - run migration script first")
            raise RuntimeError("message_queue table not found - run migrate_queue_db.py first")
    finally:
        conn.close()

def get_next_sequence_number(cursor) -> int:
    """Get the next sequence number atomically."""
    cursor.execute("""
    UPDATE sequence_generator 
    SET current_value = current_value + 1 
    WHERE name = 'message_sequence';
    """)
    
    cursor.execute("SELECT current_value FROM sequence_generator WHERE name = 'message_sequence';")
    result = cursor.fetchone()
    
    if not result:
        # Initialize if not exists
        cursor.execute("""
        INSERT INTO sequence_generator (name, current_value) 
        VALUES ('message_sequence', 1);
        """)
        return 1
    
    return result[0]

def enqueue_message(
    agent_id: str,
    message: str,
    priority: int = 0,
    project_name: Optional[str] = None,
    dependency_id: Optional[int] = None,
    fifo_scope: str = 'agent'
) -> int:
    """
    Enqueue a message to the database queue.
    
    Args:
        agent_id: Target agent in session:window format
        message: The message content
        priority: Message priority (0-100, higher = more urgent)
        project_name: Optional project name for project-level FIFO
        dependency_id: Optional ID of message that must complete first
        fifo_scope: FIFO ordering scope ('agent', 'project', 'global')
    
    Returns:
        The message ID of the enqueued message
    """
    ensure_database_exists()
    
    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    cursor = conn.cursor()
    
    try:
        with conn:
            # Get next sequence number
            sequence_number = get_next_sequence_number(cursor)
            
            # Extract project name from agent_id if not provided
            if not project_name and '-session:' in agent_id:
                session_name = agent_id.split(':')[0]
                project_name = session_name.replace('-session', '')
            
            # Insert message
            cursor.execute("""
            INSERT INTO message_queue 
            (agent_id, message, priority, sequence_number, project_name, 
             dependency_id, fifo_scope, status, enqueued_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP);
            """, (agent_id, message, priority, sequence_number, project_name, 
                  dependency_id, fifo_scope))
            
            message_id = cursor.lastrowid
            logger.info(f"Enqueued message {message_id} for agent {agent_id} with priority {priority}")
            
            return message_id
            
    except sqlite3.Error as e:
        logger.error(f"Failed to enqueue message: {e}")
        raise
    finally:
        conn.close()

def enqueue_batch(messages: list[Dict[str, Any]]) -> list[int]:
    """
    Enqueue multiple messages in a single transaction.
    
    Args:
        messages: List of message dictionaries with keys:
                 - agent_id (required)
                 - message (required)  
                 - priority (optional, default 0)
                 - project_name (optional)
                 - dependency_id (optional)
                 - fifo_scope (optional, default 'agent')
    
    Returns:
        List of message IDs for the enqueued messages
    """
    ensure_database_exists()
    
    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    cursor = conn.cursor()
    
    message_ids = []
    
    try:
        with conn:
            for msg in messages:
                # Validate required fields
                if 'agent_id' not in msg or 'message' not in msg:
                    raise ValueError("Each message must have 'agent_id' and 'message' fields")
                
                # Get next sequence number
                sequence_number = get_next_sequence_number(cursor)
                
                # Extract project name if needed
                project_name = msg.get('project_name')
                if not project_name and '-session:' in msg['agent_id']:
                    session_name = msg['agent_id'].split(':')[0]
                    project_name = session_name.replace('-session', '')
                
                # Insert message
                cursor.execute("""
                INSERT INTO message_queue 
                (agent_id, message, priority, sequence_number, project_name, 
                 dependency_id, fifo_scope, status, enqueued_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP);
                """, (
                    msg['agent_id'],
                    msg['message'],
                    msg.get('priority', 0),
                    sequence_number,
                    project_name,
                    msg.get('dependency_id'),
                    msg.get('fifo_scope', 'agent')
                ))
                
                message_ids.append(cursor.lastrowid)
            
            logger.info(f"Enqueued {len(messages)} messages in batch")
            return message_ids
            
    except sqlite3.Error as e:
        logger.error(f"Failed to enqueue batch: {e}")
        raise
    finally:
        conn.close()

def enqueue_with_dependency_chain(
    agent_id: str,
    messages: list[str],
    priority: int = 0,
    project_name: Optional[str] = None
) -> list[int]:
    """
    Enqueue multiple messages where each depends on the previous one.
    
    Args:
        agent_id: Target agent
        messages: List of message contents in order
        priority: Priority for all messages
        project_name: Optional project name
    
    Returns:
        List of message IDs in order
    """
    message_ids = []
    dependency_id = None
    
    for msg in messages:
        msg_id = enqueue_message(
            agent_id=agent_id,
            message=msg,
            priority=priority,
            project_name=project_name,
            dependency_id=dependency_id
        )
        message_ids.append(msg_id)
        dependency_id = msg_id  # Next message depends on this one
    
    return message_ids

def clear_agent_queue(agent_id: str) -> int:
    """
    Clear all pending messages for an agent.
    
    Args:
        agent_id: The agent whose queue to clear
        
    Returns:
        Number of messages cleared
    """
    ensure_database_exists()
    
    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    cursor = conn.cursor()
    
    try:
        with conn:
            cursor.execute("""
            DELETE FROM message_queue 
            WHERE agent_id = ? AND status = 'pending';
            """, (agent_id,))
            
            cleared_count = cursor.rowcount
            logger.info(f"Cleared {cleared_count} pending messages for agent {agent_id}")
            return cleared_count
            
    except sqlite3.Error as e:
        logger.error(f"Failed to clear queue: {e}")
        raise
    finally:
        conn.close()

def get_queue_status(agent_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get queue status information.
    
    Args:
        agent_id: Optional agent to get status for (None for global status)
        
    Returns:
        Dictionary with queue statistics
    """
    ensure_database_exists()
    
    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        if agent_id:
            # Agent-specific status
            cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'pulled' THEN 1 ELSE 0 END) as pulled,
                SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
                MIN(CASE WHEN status = 'pending' THEN priority END) as min_priority,
                MAX(CASE WHEN status = 'pending' THEN priority END) as max_priority
            FROM message_queue
            WHERE agent_id = ?;
            """, (agent_id,))
        else:
            # Global status
            cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'pulled' THEN 1 ELSE 0 END) as pulled,
                SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
                COUNT(DISTINCT agent_id) as active_agents
            FROM message_queue;
            """)
        
        result = cursor.fetchone()
        return dict(result) if result else {}
        
    finally:
        conn.close()

# CLI interface for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enqueue messages to the hooks-based queue")
    parser.add_argument("agent_id", help="Target agent ID (session:window format)")
    parser.add_argument("message", help="Message to enqueue")
    parser.add_argument("--priority", type=int, default=0, help="Message priority (0-100)")
    parser.add_argument("--project", help="Project name")
    parser.add_argument("--dependency", type=int, help="Message ID this depends on")
    parser.add_argument("--scope", choices=['agent', 'project', 'global'], default='agent',
                       help="FIFO scope")
    
    args = parser.parse_args()
    
    try:
        msg_id = enqueue_message(
            agent_id=args.agent_id,
            message=args.message,
            priority=args.priority,
            project_name=args.project,
            dependency_id=args.dependency,
            fifo_scope=args.scope
        )
        print(f"Enqueued message with ID: {msg_id}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
#!/usr/bin/env python3
"""
Message queue checker for hooks-based agent messaging system.
Pulls next message from queue based on agent ID (session:window format).
"""

import argparse
import sqlite3
import sys
import subprocess
import json
import logging
import os
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
DB_PATH = os.environ.get('QUEUE_DB_PATH', '/home/clauderun/Tmux-Orchestrator/task_queue.db')
TIMEOUT = 10.0  # SQLite busy timeout

def get_current_tmux_context():
    """Get current tmux session:window context."""
    try:
        session_name = subprocess.getoutput("tmux display-message -p '#{session_name}'").strip()
        window_index = subprocess.getoutput("tmux display-message -p '#{window_index}'").strip()
        return f"{session_name}:{window_index}"
    except Exception as e:
        logger.error(f"Failed to get tmux context: {e}")
        return None

def validate_agent_id(agent_id: str):
    """Validate that agent_id matches current tmux context."""
    current = get_current_tmux_context()
    if not current:
        raise ValueError("Could not determine current tmux context")
    
    if current != agent_id:
        raise ValueError(f"Agent ID mismatch: Expected {agent_id}, but current context is {current}")
    
    return True

def mark_previous_as_delivered(cursor, agent_id: str):
    """Implicit ACK: Mark the last pulled message as delivered."""
    cursor.execute("""
    UPDATE message_queue 
    SET status = 'delivered', delivered_at = CURRENT_TIMESTAMP
    WHERE agent_id = ? AND status = 'pulled' 
    ORDER BY pulled_at DESC LIMIT 1;
    """, (agent_id,))
    
    if cursor.rowcount > 0:
        logger.info(f"Marked previous message as delivered for {agent_id}")

def get_next_message(cursor, agent_id: str, scope: str = 'agent'):
    """Get next pending message respecting dependencies, priority, and FIFO."""
    
    if scope == 'agent':
        # Per-agent FIFO (default)
        query = """
        SELECT * FROM message_queue 
        WHERE agent_id = ? AND status = 'pending'
          AND (dependency_id IS NULL OR dependency_id IN (
            SELECT id FROM message_queue WHERE status = 'delivered'
          ))
        ORDER BY priority DESC, sequence_number ASC
        LIMIT 1;
        """
        params = (agent_id,)
        
    elif scope == 'project':
        # Project-level FIFO - get project from agent_id
        cursor.execute("SELECT project_name FROM agents WHERE agent_id = ?;", (agent_id,))
        result = cursor.fetchone()
        project_name = result[0] if result else None
        
        if not project_name:
            logger.warning(f"No project found for agent {agent_id}, falling back to agent scope")
            return get_next_message(cursor, agent_id, 'agent')
        
        query = """
        SELECT * FROM message_queue 
        WHERE project_name = ? AND status = 'pending'
          AND (dependency_id IS NULL OR dependency_id IN (
            SELECT id FROM message_queue WHERE status = 'delivered'
          ))
        ORDER BY priority DESC, sequence_number ASC
        LIMIT 1;
        """
        params = (project_name,)
        
    else:  # global scope
        query = """
        SELECT * FROM message_queue 
        WHERE status = 'pending'
          AND (dependency_id IS NULL OR dependency_id IN (
            SELECT id FROM message_queue WHERE status = 'delivered'
          ))
        ORDER BY priority DESC, sequence_number ASC
        LIMIT 1;
        """
        params = ()

    cursor.execute(query, params)
    return cursor.fetchone()

def update_agent_status(cursor, agent_id: str, status: str):
    """Update agent status in the agents table."""
    # Ensure agent record exists
    cursor.execute("INSERT OR IGNORE INTO agents (agent_id, status) VALUES (?, ?);", (agent_id, status))
    
    # Update status
    cursor.execute("""
    UPDATE agents 
    SET status = ?, 
        ready_since = CASE WHEN ? = 'ready' THEN CURRENT_TIMESTAMP ELSE ready_since END,
        last_heartbeat = CURRENT_TIMESTAMP
    WHERE agent_id = ?;
    """, (status, status, agent_id))

def main():
    parser = argparse.ArgumentParser(description="Check and pull from message queue.")
    parser.add_argument('--agent', required=True, 
                       help="Agent ID as session:window (e.g., project-session:2)")
    parser.add_argument('--bootstrap', action='store_true', 
                       help="Bootstrap mode for session initialization")
    parser.add_argument('--check-idle', action='store_true', 
                       help="Check queue in idle mode and set ready flag")
    parser.add_argument('--scope', default='agent', 
                       choices=['agent', 'project', 'global'], 
                       help="FIFO scope for message selection")
    parser.add_argument('--no-validation', action='store_true',
                       help="Skip agent ID validation (for testing)")
    args = parser.parse_args()

    # Validate agent_id against current tmux context
    if not args.no_validation:
        try:
            validate_agent_id(args.agent)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

    # Check if database exists
    if not Path(DB_PATH).exists():
        logger.error(f"Database not found at {DB_PATH}")
        print(json.dumps({"status": "error", "message": "Database not found"}))
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    conn.row_factory = sqlite3.Row  # Dict-like rows
    cursor = conn.cursor()

    try:
        # Transaction for atomicity
        with conn:
            # Implicit ACK for previous message (except in bootstrap)
            if not args.bootstrap:
                mark_previous_as_delivered(cursor, args.agent)

            # Get next message
            message_row = get_next_message(cursor, args.agent, args.scope)
            
            if not message_row:
                # No messages available
                if args.bootstrap:
                    logger.info("Bootstrap: No initial message, setting ready flag.")
                    update_agent_status(cursor, args.agent, 'ready')
                elif args.check_idle:
                    logger.info("Idle check: Queue empty, enabling direct delivery.")
                    update_agent_status(cursor, args.agent, 'ready')
                else:
                    logger.info("No pending messages.")
                    update_agent_status(cursor, args.agent, 'active')
                
                print(json.dumps({"status": "empty", "agent_id": args.agent}))
                return

            # Mark message as pulled
            cursor.execute("""
            UPDATE message_queue 
            SET status = 'pulled', pulled_at = CURRENT_TIMESTAMP 
            WHERE id = ?;
            """, (message_row['id'],))

            # Update agent status to active (processing message)
            update_agent_status(cursor, args.agent, 'active')

            # Output JSON for hook injection
            output = {
                "status": "pulled",
                "message": message_row['message'],
                "priority": message_row['priority'],
                "sequence_number": message_row['sequence_number'],
                "message_id": message_row['id'],
                "agent_id": args.agent,
                "scope": args.scope
            }
            
            logger.info(f"Pulled message {message_row['id']} for agent {args.agent}")
            print(json.dumps(output))

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
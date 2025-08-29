#!/usr/bin/env python3
"""
Cleanup script for SessionEnd hook.
Handles agent cleanup when a session ends, including message requeuing.
"""

import argparse
import sqlite3
import sys
import logging
import os
from datetime import datetime
from pathlib import Path

# Configure logging
log_dir = Path(__file__).parent.parent / 'logs' / 'hooks'
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"cleanup_agent_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DB_PATH = os.environ.get('QUEUE_DB_PATH', '/home/clauderun/Tmux-Orchestrator/task_queue.db')
TIMEOUT = 10.0

def cleanup_agent(agent_id: str, reason: str = "session_end"):
    """
    Handle agent cleanup on session end.
    
    Args:
        agent_id: Agent identifier (session:window)
        reason: Cleanup reason (session_end, error, manual, etc.)
    """
    logger.info(f"Starting cleanup for agent {agent_id}, reason: {reason}")
    
    if not Path(DB_PATH).exists():
        logger.error(f"Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    cursor = conn.cursor()
    
    try:
        with conn:
            # 1. Requeue undelivered messages (pulled but not delivered)
            cursor.execute("""
            UPDATE message_queue 
            SET status = 'pending', pulled_at = NULL 
            WHERE agent_id = ? AND status = 'pulled';
            """, (agent_id,))
            requeued_count = cursor.rowcount
            
            if requeued_count > 0:
                logger.info(f"Requeued {requeued_count} undelivered messages for {agent_id}")
            
            # 2. Update agent status
            cursor.execute("""
            UPDATE agents 
            SET status = 'offline', 
                last_heartbeat = CURRENT_TIMESTAMP,
                ready_since = NULL,
                direct_delivery_pipe = NULL
            WHERE agent_id = ?;
            """, (agent_id,))
            
            # 3. Log session end event
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                reason TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            );
            """)
            
            # Get some stats for the session
            cursor.execute("""
            SELECT 
                COUNT(*) as total_messages,
                SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                MIN(enqueued_at) as first_message,
                MAX(delivered_at) as last_delivery
            FROM message_queue
            WHERE agent_id = ?;
            """, (agent_id,))
            
            stats = cursor.fetchone()
            details = {
                'total_messages': stats[0],
                'delivered': stats[1],
                'pending': stats[2],
                'session_duration': None
            }
            
            if stats[3] and stats[4]:
                # Calculate approximate session duration
                try:
                    start = datetime.fromisoformat(stats[3].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(stats[4].replace('Z', '+00:00'))
                    duration = (end - start).total_seconds() / 60  # minutes
                    details['session_duration'] = f"{duration:.1f} minutes"
                except Exception as e:
                    logger.warning(f"Could not calculate session duration: {e}")
            
            cursor.execute("""
            INSERT INTO session_events (agent_id, event_type, reason, details)
            VALUES (?, 'session_end', ?, ?);
            """, (agent_id, reason, str(details)))
            
            logger.info(f"Agent {agent_id} cleanup completed. Stats: {details}")
            
            # 4. Check for any high-priority messages that need attention
            cursor.execute("""
            SELECT COUNT(*) FROM message_queue 
            WHERE agent_id = ? AND status = 'pending' AND priority >= 50;
            """, (agent_id,))
            high_priority_count = cursor.fetchone()[0]
            
            if high_priority_count > 0:
                logger.warning(f"Agent {agent_id} has {high_priority_count} high-priority messages pending!")
                # Could trigger an alert or reassignment here
            
    except sqlite3.Error as e:
        logger.error(f"Database error during cleanup: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during cleanup: {e}", exc_info=True)
        raise
    finally:
        conn.close()

def get_agent_session_info(agent_id: str):
    """Get information about an agent's session for debugging."""
    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get agent info
        cursor.execute("SELECT * FROM agents WHERE agent_id = ?;", (agent_id,))
        agent_info = cursor.fetchone()
        
        # Get message stats
        cursor.execute("""
        SELECT 
            status, 
            COUNT(*) as count,
            MIN(priority) as min_priority,
            MAX(priority) as max_priority
        FROM message_queue
        WHERE agent_id = ?
        GROUP BY status;
        """, (agent_id,))
        
        message_stats = cursor.fetchall()
        
        return {
            'agent': dict(agent_info) if agent_info else None,
            'messages': [dict(row) for row in message_stats]
        }
        
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Clean up agent resources on session end")
    parser.add_argument("--agent", required=True, 
                       help="Agent ID as session:window (e.g., project-session:2)")
    parser.add_argument("--reason", default="session_end",
                       choices=['session_end', 'error', 'timeout', 'manual', 'credits_exhausted'],
                       help="Reason for cleanup")
    parser.add_argument("--info", action="store_true",
                       help="Just show agent info without cleanup")
    
    args = parser.parse_args()
    
    try:
        if args.info:
            info = get_agent_session_info(args.agent)
            import json
            print(json.dumps(info, indent=2))
        else:
            cleanup_agent(args.agent, args.reason)
            print(f"Successfully cleaned up agent {args.agent}")
            
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
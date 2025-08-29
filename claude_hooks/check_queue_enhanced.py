#!/usr/bin/env python3
"""
Enhanced message queue checker for hooks-based agent messaging system.
Supports rebriefing, context restoration, and error recovery.
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
log_dir = Path(__file__).parent.parent / 'logs' / 'hooks'
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"check_queue_{datetime.now().strftime('%Y%m%d')}.log"

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
TIMEOUT = 10.0  # SQLite busy timeout
REBRIEF_THRESHOLD = 3600  # Rebrief if no activity for 1 hour

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
        logger.warning("Could not determine current tmux context - skipping validation")
        return True  # Allow hook to proceed
    
    if current != agent_id:
        logger.warning(f"Agent ID mismatch: Expected {agent_id}, but current context is {current}")
        # Don't raise error - just log warning
    
    return True

def get_agent_info(cursor, agent_id: str):
    """Get agent information including last activity."""
    cursor.execute("""
    SELECT project_name, status, last_heartbeat, ready_since, last_sequence_delivered 
    FROM agents WHERE agent_id = ?;
    """, (agent_id,))
    return cursor.fetchone()

def needs_rebriefing(cursor, agent_id: str) -> bool:
    """Check if agent needs rebriefing based on inactivity."""
    agent_info = get_agent_info(cursor, agent_id)
    if not agent_info:
        return False
    
    last_heartbeat = agent_info['last_heartbeat']
    if not last_heartbeat:
        return True
    
    # Parse timestamp and check age
    try:
        last_time = datetime.fromisoformat(last_heartbeat.replace('Z', '+00:00'))
        age_seconds = (datetime.utcnow() - last_time.replace(tzinfo=None)).total_seconds()
        return age_seconds > REBRIEF_THRESHOLD
    except Exception as e:
        logger.error(f"Error checking rebrief threshold: {e}")
        return False

def create_rebrief_message(cursor, agent_id: str) -> str:
    """Generate a contextual rebriefing message."""
    # Extract role from agent_id (assuming format session:window)
    session_name, window_index = agent_id.split(':')
    
    # Get agent info
    agent_info = get_agent_info(cursor, agent_id)
    project_name = agent_info['project_name'] if agent_info else 'current project'
    
    # Get recent completed work (last 5 delivered messages)
    cursor.execute("""
    SELECT message, delivered_at 
    FROM message_queue 
    WHERE agent_id = ? AND status = 'delivered' 
    ORDER BY delivered_at DESC LIMIT 5;
    """, (agent_id,))
    recent_work = cursor.fetchall()
    
    rebrief_msg = f"""🔄 **Context Restoration & Rebriefing**

Welcome back! You are agent {agent_id} working on {project_name}.

**Recent Activity Summary:**
"""
    
    if recent_work:
        for work in recent_work:
            delivered = datetime.fromisoformat(work['delivered_at'].replace('Z', '+00:00'))
            time_ago = (datetime.utcnow() - delivered.replace(tzinfo=None)).total_seconds() / 60
            rebrief_msg += f"\n- {int(time_ago)}m ago: {work['message'][:50]}..."
    else:
        rebrief_msg += "\n- No recent completed tasks found"
    
    rebrief_msg += f"""

**Quick Status Check:**
1. Run `git status` to see uncommitted changes
2. Run `git log --oneline -5` to see recent commits  
3. Check for any pending tasks or blockers
4. Continue with your assigned responsibilities

Please provide a brief status update on your current work."""
    
    return rebrief_msg

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
    
    # First check if rebriefing is needed
    if needs_rebriefing(cursor, agent_id):
        logger.info(f"Agent {agent_id} needs rebriefing due to inactivity")
        # Create and return a rebrief message
        rebrief_msg = create_rebrief_message(cursor, agent_id)
        
        # Insert rebrief message with high priority
        cursor.execute("""
        UPDATE sequence_generator 
        SET current_value = current_value + 1 
        WHERE name = 'message_sequence';
        """)
        cursor.execute("SELECT current_value FROM sequence_generator WHERE name = 'message_sequence';")
        seq_num = cursor.fetchone()[0]
        
        cursor.execute("""
        INSERT INTO message_queue 
        (agent_id, message, priority, sequence_number, status)
        VALUES (?, ?, 95, ?, 'pending');
        """, (agent_id, rebrief_msg, seq_num))
    
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
        project_name = result['project_name'] if result else None
        
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
    # Parse project name from session name
    session_name = agent_id.split(':')[0]
    project_name = session_name.replace('-session', '') if '-session' in session_name else session_name
    
    # Ensure agent record exists
    cursor.execute("""
    INSERT OR IGNORE INTO agents (agent_id, project_name, status) 
    VALUES (?, ?, ?);
    """, (agent_id, project_name, status))
    
    # Update status
    cursor.execute("""
    UPDATE agents 
    SET status = ?, 
        ready_since = CASE WHEN ? = 'ready' THEN CURRENT_TIMESTAMP ELSE ready_since END,
        last_heartbeat = CURRENT_TIMESTAMP
    WHERE agent_id = ?;
    """, (status, status, agent_id))

def handle_compact_trigger(agent_id: str):
    """Handle PostCompact event by queueing a rebriefing message."""
    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        with conn:
            # Get agent info for context
            agent_info = get_agent_info(cursor, agent_id)
            project_name = agent_info['project_name'] if agent_info else 'current project'
            
            # Get recent completed work for context
            cursor.execute("""
            SELECT message, delivered_at 
            FROM message_queue 
            WHERE agent_id = ? AND status = 'delivered' 
            ORDER BY delivered_at DESC LIMIT 3;
            """, (agent_id,))
            recent_work = cursor.fetchall()
            
            # Queue a high-priority context restoration message
            compact_msg = f"""🔄 **Context Restoration After Compaction**

Your conversation history has been compacted to maintain performance. Here's your context restoration:

**You are:** Agent {agent_id} working on {project_name}

**Recent Completed Tasks:**"""
            
            if recent_work:
                for work in recent_work:
                    delivered = datetime.fromisoformat(work['delivered_at'].replace('Z', '+00:00'))
                    time_ago = (datetime.utcnow() - delivered.replace(tzinfo=None)).total_seconds() / 60
                    compact_msg += f"\n- {int(time_ago)}m ago: {work['message'][:50]}..."
            else:
                compact_msg += "\n- No recent tasks found"
            
            compact_msg += f"""

**Quick Status Check:**
- Run `pwd` to confirm your working directory
- Run `git status` to check for uncommitted changes  
- Run `git log --oneline -5` to see recent commits
- Review your role's responsibilities if needed

Please continue with your current work. If you were in the middle of implementing something, complete it."""
            
            # Get sequence number
            cursor.execute("""
            UPDATE sequence_generator 
            SET current_value = current_value + 1 
            WHERE name = 'message_sequence';
            """)
            cursor.execute("SELECT current_value FROM sequence_generator WHERE name = 'message_sequence';")
            seq_num = cursor.fetchone()[0]
            
            # Insert with very high priority
            cursor.execute("""
            INSERT INTO message_queue 
            (agent_id, message, priority, sequence_number, status)
            VALUES (?, ?, 99, ?, 'pending');
            """, (agent_id, compact_msg, seq_num))
            
            logger.info(f"Queued context restoration message for {agent_id} after compaction")
            
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Enhanced message queue checker with rebriefing support.")
    parser.add_argument('--agent', required=True, 
                       help="Agent ID as session:window (e.g., project-session:2)")
    parser.add_argument('--bootstrap', action='store_true', 
                       help="Bootstrap mode for session initialization")
    parser.add_argument('--check-idle', action='store_true', 
                       help="Check queue in idle mode and set ready flag")
    parser.add_argument('--rebrief', action='store_true',
                       help="Handle PostCompact event for rebriefing")
    parser.add_argument('--scope', default='agent', 
                       choices=['agent', 'project', 'global'], 
                       help="FIFO scope for message selection")
    parser.add_argument('--no-validation', action='store_true',
                       help="Skip agent ID validation (for testing)")
    args = parser.parse_args()

    logger.info(f"Hook triggered for agent {args.agent} - bootstrap:{args.bootstrap}, idle:{args.check_idle}, rebrief:{args.rebrief}")

    # Handle PostCompact rebriefing specially
    if args.rebrief:
        handle_compact_trigger(args.agent)
        print(json.dumps({"status": "rebrief_queued", "agent_id": args.agent}))
        return

    # Validate agent_id against current tmux context
    if not args.no_validation:
        validate_agent_id(args.agent)

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

            # Output for hook injection - just the message content
            print(message_row['message'])
            
            # Log the pull for debugging
            logger.info(f"Pulled message {message_row['id']} (priority={message_row['priority']}, seq={message_row['sequence_number']}) for agent {args.agent}")

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
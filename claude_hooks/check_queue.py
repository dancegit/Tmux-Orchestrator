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
from tmux_message_sender import TmuxMessageSender
from git_policy_enforcer import GitPolicyEnforcer

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

def check_git_policy_compliance(cursor, agent_id: str) -> dict:
    """Check git workflow policy compliance after tool use"""
    try:
        # Determine worktree path from agent_id
        worktree_path = Path.cwd()  # Assumes hook runs in worktree directory
        
        # Extract agent role from agent_id (session:window format)
        session_name = agent_id.split(':')[0]
        # Try to extract role from session name patterns
        if 'orchestrator' in session_name:
            agent_role = 'orchestrator'
        elif 'developer' in session_name or 'dev' in session_name:
            agent_role = 'developer'
        elif 'tester' in session_name or 'test' in session_name:
            agent_role = 'tester'
        elif 'project-manager' in session_name or 'pm' in session_name:
            agent_role = 'project-manager'
        else:
            agent_role = 'agent'  # Default fallback
        
        # Initialize enforcer and check policies
        enforcer = GitPolicyEnforcer(str(worktree_path), agent_role)
        policy_result = enforcer.check_all_policies()
        
        # Process violations and queue messages for high-priority ones
        for violation in policy_result['violations']:
            if violation['severity'] in ['critical', 'high']:
                # Queue high-priority policy violation message
                cursor.execute("""
                UPDATE sequence_generator 
                SET current_value = current_value + 1 
                WHERE name = 'message_sequence';
                """)
                cursor.execute("SELECT current_value FROM sequence_generator WHERE name = 'message_sequence';")
                seq_num = cursor.fetchone()[0]
                
                priority = 80 if violation['severity'] == 'critical' else 70
                
                cursor.execute("""
                INSERT INTO message_queue 
                (agent_id, message, priority, sequence_number, status)
                VALUES (?, ?, ?, ?, 'pending');
                """, (agent_id, violation['message'], priority, seq_num))
                
                logger.info(f"Queued {violation['severity']} git policy violation message for {agent_id}: {violation['type']}")
                
                # Handle auto-fix if available and enabled
                if violation.get('auto_fix_available') and violation['type'] == 'commit_interval':
                    if enforcer.perform_auto_commit("policy enforcement"):
                        logger.info(f"Auto-committed for {agent_id} due to commit interval violation")
        
        return policy_result
        
    except Exception as e:
        logger.error(f"Error checking git policy compliance for {agent_id}: {e}")
        return {'violations': [], 'compliant': True, 'error': str(e)}

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

def is_mcp_approval_mode(agent_id: str) -> bool:
    """Check if Claude is currently in MCP approval mode by examining tmux pane content."""
    try:
        session_name, window_index = agent_id.split(':')
        
        # Get pane content from the specified tmux session:window
        cmd = f"tmux capture-pane -t {session_name}:{window_index} -p"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
        
        if result.returncode != 0:
            logger.warning(f"Could not capture pane content for {agent_id}: {result.stderr}")
            return False
        
        pane_content = result.stdout.lower()
        
        # Check for MCP approval prompts
        mcp_indicators = [
            "approve these servers",
            "mcp servers",
            "model context protocol",
            "server approval",
            "dangerous permissions",
            "to approve, type 'yes'",
            "approve the following servers"
        ]
        
        for indicator in mcp_indicators:
            if indicator in pane_content:
                logger.info(f"MCP approval mode detected for {agent_id}: found '{indicator}'")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking MCP approval mode for {agent_id}: {e}")
        return False

def handle_bootstrap_startup(agent_id: str):
    """Handle agent startup with delayed message delivery."""
    logger.info(f"Handling bootstrap startup for {agent_id}")
    
    # Create a delayed delivery mechanism for bootstrap messages
    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        with conn:
            # Check if there are pending messages for this agent
            cursor.execute("""
            SELECT COUNT(*) as count FROM message_queue 
            WHERE agent_id = ? AND status = 'pending'
            """, (agent_id,))
            pending_count = cursor.fetchone()['count']
            
            if pending_count > 0:
                logger.info(f"Found {pending_count} pending messages for {agent_id} - will attempt delivery after startup delay")
                
                # Mark agent as starting up
                update_agent_status(cursor, agent_id, 'starting')
                
                # Schedule a delayed check (this could be done via a background process or cron)
                # For now, we'll use a simple approach - mark for delayed delivery
                cursor.execute("""
                INSERT OR REPLACE INTO agent_startup_queue (agent_id, startup_time, retry_count)
                VALUES (?, CURRENT_TIMESTAMP, 0)
                """, (agent_id,))
                
                logger.info(f"Scheduled delayed message delivery for {agent_id}")
            else:
                # No pending messages, just mark as ready
                update_agent_status(cursor, agent_id, 'ready')
                
    finally:
        conn.close()

def handle_bootstrap_startup(agent_id: str):
    """Handle bootstrap mode by checking for pending messages and scheduling delivery."""
    conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        with conn:
            # Check if there are pending messages
            cursor.execute("""
            SELECT COUNT(*) as count FROM message_queue 
            WHERE agent_id = ? AND status = 'pending'
            """, (agent_id,))
            
            msg_count = cursor.fetchone()['count']
            
            if msg_count > 0:
                # Schedule agent for delayed delivery
                cursor.execute("""
                INSERT OR REPLACE INTO agent_startup_queue 
                (agent_id, startup_time, retry_count, completed)
                VALUES (?, CURRENT_TIMESTAMP, 0, FALSE)
                """, (agent_id,))
                
                logger.info(f"Agent {agent_id} has {msg_count} pending messages, scheduled for delayed delivery")
                return True
            else:
                logger.info(f"Agent {agent_id} has no pending messages at bootstrap")
                return False
                
    except Exception as e:
        logger.error(f"Error in bootstrap handling: {e}")
        return False
    finally:
        conn.close()

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

    # Check if Claude is in MCP approval mode (avoid interference)
    if is_mcp_approval_mode(args.agent):
        logger.info(f"Skipping hook execution - agent {args.agent} is in MCP approval mode")
        print(json.dumps({"status": "skipped_mcp_approval", "agent_id": args.agent}))
        return

    # Handle PostCompact rebriefing specially
    if args.rebrief:
        handle_compact_trigger(args.agent)
        print(json.dumps({"status": "rebrief_queued", "agent_id": args.agent}))
        return
    
    # Handle bootstrap mode specially
    if args.bootstrap:
        handle_bootstrap_startup(args.agent)
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
            # Check git policy compliance (except during bootstrap and MCP approval)
            if not args.bootstrap and not args.rebrief:
                policy_result = check_git_policy_compliance(cursor, args.agent)
                logger.info(f"Git policy check for {args.agent}: {len(policy_result['violations'])} violations found")

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

            # Send message via tmux send-keys instead of stdout
            sender = TmuxMessageSender(args.agent)
            
            # For bootstrap mode, don't wait (Claude might not be ready yet)
            wait_for_ready = not args.bootstrap
            
            if sender.send_message_via_tmux(message_row['message'], wait_for_ready=wait_for_ready):
                logger.info(f"Successfully delivered message {message_row['id']} via tmux send-keys")
                
                # Output status for hook system
                print(json.dumps({
                    "status": "delivered", 
                    "agent_id": args.agent,
                    "message_id": message_row['id'],
                    "delivery_method": "tmux_send_keys"
                }))
            else:
                logger.error(f"Failed to deliver message {message_row['id']} via tmux send-keys")
                
                # Mark message as pending again for retry
                cursor.execute("""
                UPDATE message_queue 
                SET status = 'pending', pulled_at = NULL 
                WHERE id = ?;
                """, (message_row['id'],))
                
                print(json.dumps({
                    "status": "delivery_failed", 
                    "agent_id": args.agent,
                    "message_id": message_row['id']
                }))
            
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
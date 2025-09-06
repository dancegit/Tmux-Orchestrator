#!/usr/bin/env python3
"""
TmuxMessenger with hooks-based queue support.
This module provides messaging functionality using the hooks-based pull model by default.
The legacy push mode is available as a fallback when explicitly disabled.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Add the claude_hooks directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'claude_hooks'))
from enqueue_message import enqueue_message, enqueue_batch, get_queue_status

# Import MCP utilities for centralized cleaning and detection
from mcp_utils import (
    clean_mcp_wrappers, 
    detect_mcp_usage, 
    validate_message_for_queue,
    log_mcp_violation,
    add_enter_key_safety
)

logger = logging.getLogger(__name__)

class TmuxMessengerHooks:
    """Tmux messaging system using hooks-based queue by default."""
    
    def __init__(self, orchestrator_path: Path, use_hooks: bool = True):
        self.orchestrator_path = orchestrator_path
        self.send_script = orchestrator_path / 'send-claude-message.sh'
        
        # Always use hooks by default
        self.use_hooks = use_hooks
        
        logger.info(f"TmuxMessenger initialized with hooks={'enabled' if self.use_hooks else 'disabled'}")
        
    def send_message(self, target: str, message: str, priority: int = 0, 
                    project_name: Optional[str] = None) -> bool:
        """
        Send a message to an agent using hooks-based queue.
        
        Args:
            target: Agent ID in session:window format
            message: Message content
            priority: Message priority (0-100) for queue mode
            project_name: Optional project name for queue mode
            
        Returns:
            True if message was sent/queued successfully
        """
        if self.use_hooks:
            return self._send_via_queue(target, message, priority, project_name)
        else:
            # Fallback to direct send only if explicitly disabled
            return self._send_direct(target, message)
    
    def _send_via_queue(self, target: str, message: str, priority: int = 0,
                       project_name: Optional[str] = None) -> bool:
        """Send message via hooks-based queue with MCP detection."""
        try:
            # Validate and clean message using centralized MCP utilities
            is_valid, clean_message, rejection_reason = validate_message_for_queue(message, target)
            
            if not is_valid:
                if rejection_reason.startswith("MCP contamination"):
                    # Log MCP violation for monitoring
                    log_mcp_violation(target, message, "Queue enqueue blocked")
                    logger.error(f"MCP usage detected in message to {target}. Message rejected.")
                    # Send warning to agent
                    warning_msg = "WARNING: MCP tmux commands detected. Use scm or send-monitored-message.sh instead."
                    enqueue_message(agent_id=target, message=warning_msg, priority=90)
                    return False
                else:
                    logger.warning(f"Message rejected for {target}: {rejection_reason}")
                    return True  # Empty message is not an error
            
            # Add Enter key safety for execution
            clean_message = add_enter_key_safety(clean_message)
            
            # Enqueue the message
            msg_id = enqueue_message(
                agent_id=target,
                message=clean_message,
                priority=priority,
                project_name=project_name
            )
            
            logger.info(f"Enqueued message {msg_id} to {target} with priority {priority}")
            
            # For high-priority messages, check if agent is ready for direct delivery
            if priority >= 80:
                self._attempt_direct_delivery(target)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to enqueue message: {e}")
            # Fallback to direct send if queueing fails
            logger.info("Falling back to direct send")
            return self._send_direct(target, message)
    
    def _send_direct(self, target: str, message: str) -> bool:
        """Send message directly using existing push-based method with MCP blocking."""
        # Validate and clean message using centralized utilities
        is_valid, clean_message, rejection_reason = validate_message_for_queue(message, target)
        
        if not is_valid:
            if "MCP" in rejection_reason:
                log_mcp_violation(target, message, "Direct send blocked")
                logger.error(f"MCP detected in direct send to {target} - aborting")
                return False
            logger.warning(f"Message rejected for {target}: {rejection_reason}")
            return True
        
        # Use enhanced send script
        try:
            result = subprocess.run([
                str(self.send_script),
                target,
                clean_message
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"Direct message sent to {target}")
                return True
            else:
                logger.error(f"Failed to send to {target}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Message send timeout to {target}")
            return False
        except Exception as e:
            logger.error(f"Exception sending to {target}: {e}")
            return False
    
    def _attempt_direct_delivery(self, agent_id: str):
        """Check if agent is ready and attempt direct delivery of high-priority message."""
        try:
            import sqlite3
            db_path = os.environ.get('QUEUE_DB_PATH', '/home/clauderun/Tmux-Orchestrator/task_queue.db')
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if agent is ready
            cursor.execute("""
            SELECT status, direct_delivery_pipe 
            FROM agents 
            WHERE agent_id = ? AND status = 'ready';
            """, (agent_id,))
            
            result = cursor.fetchone()
            if result:
                logger.info(f"Agent {agent_id} is ready, triggering immediate queue check")
                # Send a signal to trigger queue check
                # This could be done via a named pipe or by sending a special tmux key
                subprocess.run([
                    'tmux', 'send-keys', '-t', agent_id, 'C-l'  # Ctrl-L to trigger refresh
                ], capture_output=True)
            
            conn.close()
            
        except Exception as e:
            logger.warning(f"Could not check agent ready status: {e}")
    
    def send_batch(self, messages: list[Dict[str, Any]]) -> bool:
        """
        Send multiple messages efficiently.
        
        Args:
            messages: List of message dictionaries with keys:
                     - agent_id (required)
                     - message (required)
                     - priority (optional)
                     - project_name (optional)
                     
        Returns:
            True if all messages were sent/queued successfully
        """
        if self.use_hooks:
            try:
                # Validate and clean all messages using centralized utilities
                valid_messages = []
                for msg in messages:
                    is_valid, cleaned, reason = validate_message_for_queue(msg['message'], msg['agent_id'])
                    if is_valid:
                        msg['message'] = add_enter_key_safety(cleaned)
                        valid_messages.append(msg)
                    elif "MCP" in reason:
                        log_mcp_violation(msg['agent_id'], msg['message'], "Batch send blocked")
                        logger.error(f"MCP detected in batch message to {msg['agent_id']}")
                
                messages = valid_messages
                
                if not messages:
                    logger.warning("All messages were empty after cleaning")
                    return True
                
                # Enqueue as batch
                msg_ids = enqueue_batch(messages)
                logger.info(f"Enqueued {len(msg_ids)} messages in batch")
                return True
                
            except Exception as e:
                logger.error(f"Failed to enqueue batch: {e}")
                return False
        else:
            # Send individually using direct method
            success = True
            for msg in messages:
                if not self._send_direct(msg['agent_id'], msg['message']):
                    success = False
            return success
    
    def send_command(self, target: str, command: str, priority: int = 0) -> bool:
        """Send a command with 'Please run:' prefix."""
        return self.send_message(target, f"Please run: {command}", priority)
    
    def send_briefing(self, target: str, briefing: str) -> bool:
        """Send a role briefing with high priority."""
        return self.send_message(target, briefing, priority=50)
    
    def get_queue_stats(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Get queue statistics."""
        if self.use_hooks:
            return get_queue_status(agent_id)
        else:
            return {"mode": "push", "queue_enabled": False, "note": "Hooks disabled - using legacy push mode"}
    
    def clean_message_from_mcp_wrappers(self, message: str) -> str:
        """Legacy wrapper for backward compatibility. Uses centralized MCP utilities."""
        return clean_mcp_wrappers(message)

# Create a backward-compatible class that can be imported as TmuxMessenger
class TmuxMessenger(TmuxMessengerHooks):
    """Backward-compatible alias for TmuxMessengerHooks."""
    pass

if __name__ == "__main__":
    # Test the messenger
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python tmux_messenger_hooks.py <agent_id> <message> [--no-hooks]")
        sys.exit(1)
    
    # Hooks are enabled by default, use --no-hooks to disable
    use_hooks = '--no-hooks' not in sys.argv
    messenger = TmuxMessenger(Path.cwd(), use_hooks=use_hooks)
    
    success = messenger.send_message(sys.argv[1], sys.argv[2])
    print(f"Message {'sent' if success else 'failed'} (mode={'hooks' if use_hooks else 'push'})")
    
    if use_hooks:
        stats = messenger.get_queue_stats(sys.argv[1])
        print(f"Queue stats: {stats}")
#!/usr/bin/env python3
"""
Smart message delivery system for Claude instances in tmux sessions.
Uses tmux send-keys to deliver messages directly to Claude instead of stdout.
"""

import subprocess
import time
import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class TmuxMessageSender:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.session_name, self.window_index = agent_id.split(':')
        
    def is_claude_ready(self, timeout: int = 30) -> bool:
        """Check if Claude is ready to receive messages (not bash, not MCP approval)."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Capture current pane content
                cmd = f"tmux capture-pane -t {self.agent_id} -p"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                
                if result.returncode != 0:
                    logger.warning(f"Failed to capture pane for {self.agent_id}: {result.stderr}")
                    return False
                
                content = result.stdout.lower()
                
                # Check for MCP approval mode (wait for this to complete)
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
                    if indicator in content:
                        logger.info(f"MCP approval detected for {self.agent_id}, waiting...")
                        time.sleep(2)
                        continue
                
                # Check for bash indicators (not ready)
                bash_indicators = [
                    "$",
                    "clauderun@",
                    "bash:",
                    "command not found",
                    "# ", 
                    "[1]",  # Job indicator
                    "exit"
                ]
                
                lines = content.split('\n')
                last_few_lines = '\n'.join(lines[-5:])  # Check last few lines
                
                # If we see bash indicators in recent lines, Claude is not ready
                bash_detected = any(indicator in last_few_lines for indicator in bash_indicators)
                
                # Check for Claude ready indicators
                claude_indicators = [
                    "assistant:",
                    "claude:",
                    "how can i help",
                    "how may i assist", 
                    "> ",  # Claude prompt
                    "i'm claude",
                    "```"  # Code blocks indicate Claude is responding
                ]
                
                claude_detected = any(indicator in content for indicator in claude_indicators)
                
                if claude_detected and not bash_detected:
                    logger.info(f"Claude is ready for {self.agent_id}")
                    return True
                
                if bash_detected:
                    logger.debug(f"Bash mode detected for {self.agent_id}, waiting for Claude...")
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error checking Claude readiness for {self.agent_id}: {e}")
                time.sleep(1)
        
        logger.warning(f"Timeout waiting for Claude readiness on {self.agent_id}")
        return False
    
    def send_message_via_tmux(self, message: str, wait_for_ready: bool = True) -> bool:
        """Send message to Claude using tmux send-keys."""
        try:
            # Check if session exists
            check_cmd = f"tmux has-session -t {self.session_name}"
            result = subprocess.run(check_cmd, shell=True, capture_output=True)
            if result.returncode != 0:
                logger.error(f"Tmux session {self.session_name} does not exist")
                return False
            
            # Wait for Claude to be ready if requested
            if wait_for_ready and not self.is_claude_ready():
                logger.warning(f"Claude not ready for {self.agent_id}, message not sent")
                return False
            
            # Clear any existing input
            clear_cmd = f"tmux send-keys -t {self.agent_id} C-u"
            subprocess.run(clear_cmd, shell=True, capture_output=True)
            
            # Send message using literal mode (-l) to preserve formatting
            send_cmd = f"tmux send-keys -t {self.agent_id} -l {repr(message)}"
            result = subprocess.run(send_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to send message to {self.agent_id}: {result.stderr}")
                return False
            
            # Send Enter to submit the message
            enter_cmd = f"tmux send-keys -t {self.agent_id} Enter"
            result = subprocess.run(enter_cmd, shell=True, capture_output=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to send Enter to {self.agent_id}: {result.stderr}")
                return False
            
            logger.info(f"Successfully sent message to {self.agent_id} via tmux")
            return True
            
        except Exception as e:
            logger.error(f"Error sending message to {self.agent_id}: {e}")
            return False
    
    def get_pane_status(self) -> dict:
        """Get detailed status of the tmux pane."""
        try:
            # Capture pane content
            cmd = f"tmux capture-pane -t {self.agent_id} -p"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                return {"error": f"Failed to capture pane: {result.stderr}"}
            
            content = result.stdout
            lines = content.split('\n')
            last_line = lines[-1] if lines else ""
            
            # Analyze content
            is_mcp = any(indicator in content.lower() for indicator in [
                "approve these servers", "mcp servers", "server approval"
            ])
            
            is_bash = any(indicator in last_line for indicator in [
                "$", "clauderun@", "#"
            ])
            
            is_claude = any(indicator in content.lower() for indicator in [
                "assistant:", "claude:", "how can i help"
            ])
            
            return {
                "last_line": last_line,
                "is_mcp_approval": is_mcp,
                "is_bash_mode": is_bash,
                "is_claude_ready": is_claude and not is_bash,
                "content_length": len(content),
                "line_count": len(lines)
            }
            
        except Exception as e:
            return {"error": str(e)}
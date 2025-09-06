#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Utilities Module

Centralizes MCP pattern detection and cleaning to prevent tmux command execution issues.
This module addresses the MCP Enter key issue where agents bypass proper messaging scripts.
"""

import re
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)

# Pre-compiled MCP patterns for performance
MCP_PATTERNS = [
    # Common MCP wrappers
    re.compile(r'^echo\s+[\'"]TMUX_MCP_START[\'"];\s*'),
    re.compile(r';\s*echo\s+[\'"]TMUX_MCP_DONE_\$\?[\'"]$'),
    re.compile(r'echo\s+[\'"]TMUX_MCP_START[\'"];\s*'),
    re.compile(r';\s*echo\s+[\'"]TMUX_MCP_DONE_\$\?[\'"]'),
    
    # Alternative wrapper patterns  
    re.compile(r'echo\s+TMUX_MCP_START;\s*'),
    re.compile(r';\s*echo\s+TMUX_MCP_DONE_\$\?'),
    re.compile(r'echo\s+[\'"]MCP_EXECUTE_START[\'"];\s*'),
    re.compile(r';\s*echo\s+[\'"]MCP_EXECUTE_END_\$\?[\'"]'),
    
    # Shell execution wrappers
    re.compile(r'bash\s+-c\s+[\'"]echo\s+[\'"]?TMUX_MCP_START[\'"]?;\s*'),
    re.compile(r';\s*echo\s+[\'"]?TMUX_MCP_DONE_\$\?[\'"]?[\'"]'),
    
    # Command substitution patterns
    re.compile(r'\$\(\s*echo\s+[\'"]TMUX_MCP_START[\'"];\s*'),
    re.compile(r';\s*echo\s+[\'"]TMUX_MCP_DONE_\$\?[\'"]?\s*\)'),
    
    # Inline wrapper remnants
    re.compile(r'TMUX_MCP_START\s*;?\s*'),
    re.compile(r';\s*TMUX_MCP_DONE_\$\?\s*'),
]

# MCP detection patterns (not compiled for flexibility)
MCP_DETECTION_KEYWORDS = [
    'TMUX_MCP_START',
    'TMUX_MCP_DONE',
    'MCP_EXECUTE_START',
    'MCP_EXECUTE_END',
    '-Orchestrator; echo "TMUX_MCP',  # Common pattern from stuck messages
]

def detect_mcp_usage(message: str) -> Tuple[bool, List[str]]:
    """
    Detect if a message contains MCP patterns.
    
    Args:
        message: The message to check
        
    Returns:
        Tuple of (has_mcp, detected_patterns)
    """
    detected = []
    for keyword in MCP_DETECTION_KEYWORDS:
        if keyword in message:
            detected.append(keyword)
    
    return len(detected) > 0, detected

def clean_mcp_wrappers(message: str, max_iterations: int = 3) -> str:
    """
    Remove MCP wrapper patterns from a message.
    
    Args:
        message: The message to clean
        max_iterations: Maximum cleaning iterations to prevent infinite loops
        
    Returns:
        Cleaned message without MCP wrappers
    """
    original = message
    
    # Apply patterns iteratively
    for _ in range(max_iterations):
        before = message
        for pattern in MCP_PATTERNS:
            message = pattern.sub('', message)
        if message == before:
            break
    
    # Clean up artifacts
    message = re.sub(r';\s*;', ';', message)  # Double semicolons
    message = re.sub(r'^\s*;\s*', '', message)  # Leading semicolon
    message = re.sub(r'\s*;\s*$', '', message)  # Trailing semicolon
    message = re.sub(r'\s+', ' ', message)  # Multiple spaces
    message = message.strip()
    
    if len(original) > len(message) + 20:
        logger.debug(f"Cleaned MCP wrappers: {len(original)} → {len(message)} chars")
    
    return message

def validate_message_for_queue(message: str, agent_id: str) -> Tuple[bool, str, str]:
    """
    Validate a message before enqueueing, checking for MCP contamination.
    
    Args:
        message: The message to validate
        agent_id: Target agent ID for logging
        
    Returns:
        Tuple of (is_valid, cleaned_message, rejection_reason)
    """
    # First clean the message
    cleaned = clean_mcp_wrappers(message)
    
    # Check if message is empty after cleaning
    if not cleaned:
        return False, "", "Message was empty after cleaning MCP wrappers"
    
    # Detect remaining MCP patterns
    has_mcp, patterns = detect_mcp_usage(cleaned)
    if has_mcp:
        logger.warning(f"MCP patterns detected in message to {agent_id}: {patterns}")
        # Attempt deeper cleaning
        cleaned = clean_mcp_wrappers(cleaned, max_iterations=5)
        
        # Re-check after aggressive cleaning
        has_mcp, patterns = detect_mcp_usage(cleaned)
        if has_mcp:
            return False, cleaned, f"MCP contamination persists after cleaning: {patterns}"
    
    return True, cleaned, ""

def add_enter_key_safety(message: str) -> str:
    """
    Ensure message will execute by adding Enter key marker if missing.
    This is a safety mechanism for messages that might lack proper termination.
    
    Args:
        message: The message to check
        
    Returns:
        Message with Enter key safety marker
    """
    # Don't add if message already has certain patterns
    if message.endswith('C-m') or message.endswith('Enter'):
        return message
    
    # Add safety marker that the send script can interpret
    return f"{message}__ENSURE_ENTER__"

def log_mcp_violation(agent_id: str, message: str, context: str = ""):
    """
    Log MCP usage violations for monitoring and enforcement.
    
    Args:
        agent_id: The agent that used MCP
        message: The violating message
        context: Additional context about the violation
    """
    import json
    from datetime import datetime
    from pathlib import Path
    
    log_dir = Path("/home/clauderun/Tmux-Orchestrator/registry/logs/mcp_violations")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    violation = {
        "timestamp": datetime.now().isoformat(),
        "agent_id": agent_id,
        "message": message[:500],  # Truncate for logging
        "context": context,
        "detected_patterns": detect_mcp_usage(message)[1]
    }
    
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with open(log_file, 'a') as f:
        f.write(json.dumps(violation) + '\n')
    
    logger.warning(f"MCP violation logged for {agent_id}: {violation['detected_patterns']}")

# CLI interface for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python mcp_utils.py <message>")
        print("Tests MCP detection and cleaning on a message")
        sys.exit(1)
    
    test_message = ' '.join(sys.argv[1:])
    print(f"Original: {test_message}")
    
    has_mcp, patterns = detect_mcp_usage(test_message)
    if has_mcp:
        print(f"MCP detected: {patterns}")
    
    cleaned = clean_mcp_wrappers(test_message)
    print(f"Cleaned: {cleaned}")
    
    is_valid, final_msg, reason = validate_message_for_queue(test_message, "test-agent")
    print(f"Valid for queue: {is_valid}")
    if not is_valid:
        print(f"Rejection reason: {reason}")
    print(f"Final message: {final_msg}")
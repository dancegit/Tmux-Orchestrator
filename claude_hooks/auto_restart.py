#!/usr/bin/env python3
"""
Auto-restart script for error detection and recovery.
Handles automatic agent restart when recoverable errors occur.
"""

import subprocess
import json
import sys
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Configure logging
log_dir = Path(__file__).parent.parent / 'logs' / 'hooks'
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"auto_restart_{datetime.now().strftime('%Y%m%d')}.log"

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
ORCHESTRATOR_PATH = Path(__file__).parent.parent
AUTO_ORCHESTRATE_SCRIPT = ORCHESTRATOR_PATH / 'auto_orchestrate.py'
MAX_RESTART_ATTEMPTS = 3
RESTART_COOLDOWN = 300  # 5 minutes between restart attempts

# Restart history tracking
RESTART_HISTORY_FILE = log_dir / 'restart_history.json'

def load_restart_history() -> Dict[str, Any]:
    """Load restart history from file."""
    if RESTART_HISTORY_FILE.exists():
        try:
            with open(RESTART_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load restart history: {e}")
    return {}

def save_restart_history(history: Dict[str, Any]):
    """Save restart history to file."""
    try:
        with open(RESTART_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save restart history: {e}")

def should_restart(error_info: Dict[str, Any]) -> bool:
    """
    Determine if agent should be restarted based on error type.
    
    Args:
        error_info: Dictionary containing error details
        
    Returns:
        True if restart should be attempted
    """
    error_msg = error_info.get('message', '').lower()
    error_type = error_info.get('type', '').lower()
    
    # Recoverable error patterns
    recoverable_patterns = [
        # Tmux/session errors
        "tmux server exited",
        "lost connection",
        "session not found",
        "pane dead",
        "no such window",
        "can't find session",
        
        # Network/connection errors
        "connection reset",
        "connection refused",
        "timeout",
        "broken pipe",
        
        # Claude-specific errors
        "context window exceeded",
        "rate limit",
        "api error",
        
        # Process errors
        "process died",
        "killed",
        "terminated unexpectedly"
    ]
    
    # Non-recoverable patterns
    non_recoverable_patterns = [
        "credits exhausted",
        "subscription expired",
        "authentication failed",
        "permission denied",
        "disk full",
        "out of memory"
    ]
    
    # Check for non-recoverable errors first
    for pattern in non_recoverable_patterns:
        if pattern in error_msg:
            logger.info(f"Non-recoverable error detected: {pattern}")
            return False
    
    # Check for recoverable errors
    for pattern in recoverable_patterns:
        if pattern in error_msg:
            logger.info(f"Recoverable error detected: {pattern}")
            return True
    
    # Default: don't restart for unknown errors
    logger.warning(f"Unknown error type: {error_msg}")
    return False

def check_restart_limits(agent_id: str) -> bool:
    """
    Check if agent has exceeded restart limits.
    
    Args:
        agent_id: Agent identifier
        
    Returns:
        True if restart is allowed
    """
    history = load_restart_history()
    agent_history = history.get(agent_id, {})
    
    # Check attempt count
    attempts = agent_history.get('attempts', 0)
    if attempts >= MAX_RESTART_ATTEMPTS:
        last_attempt = agent_history.get('last_attempt')
        if last_attempt:
            # Check if cooldown period has passed
            last_time = datetime.fromisoformat(last_attempt)
            elapsed = (datetime.utcnow() - last_time).total_seconds()
            if elapsed < RESTART_COOLDOWN:
                logger.warning(f"Agent {agent_id} exceeded restart limit. Cooldown: {RESTART_COOLDOWN - elapsed:.0f}s")
                return False
            else:
                # Reset attempts after cooldown
                agent_history['attempts'] = 0
    
    return True

def update_restart_history(agent_id: str, success: bool):
    """Update restart history for an agent."""
    history = load_restart_history()
    
    if agent_id not in history:
        history[agent_id] = {'attempts': 0, 'successes': 0, 'failures': 0}
    
    agent_history = history[agent_id]
    agent_history['attempts'] += 1
    agent_history['last_attempt'] = datetime.utcnow().isoformat()
    
    if success:
        agent_history['successes'] += 1
        # Reset attempts on success
        agent_history['attempts'] = 0
    else:
        agent_history['failures'] += 1
    
    history[agent_id] = agent_history
    save_restart_history(history)

def get_project_path_for_agent(agent_id: str) -> Path:
    """Determine project path from agent ID."""
    # Extract session name
    session_name = agent_id.split(':')[0]
    
    # Remove -session suffix to get project name
    project_name = session_name.replace('-session', '')
    
    # Try to find project path
    # First check if we're already in a project worktree
    current_path = Path.cwd()
    if 'tmux-worktrees' in str(current_path):
        # Navigate up to find main project
        project_root = current_path
        while project_root.parent != project_root:
            if (project_root.parent / '.git').exists():
                return project_root.parent
            project_root = project_root.parent
    
    # Otherwise, try common locations
    possible_paths = [
        Path.home() / project_name,
        Path.home() / 'projects' / project_name,
        Path.cwd().parent / project_name
    ]
    
    for path in possible_paths:
        if path.exists() and (path / '.git').exists():
            return path
    
    # Fallback to current directory
    logger.warning(f"Could not determine project path for {agent_id}, using current directory")
    return Path.cwd()

def restart_agent(agent_id: str, error_info: Dict[str, Any]) -> bool:
    """
    Restart a failed agent using auto_orchestrate.py.
    
    Args:
        agent_id: Agent identifier (session:window)
        error_info: Error details
        
    Returns:
        True if restart was successful
    """
    logger.info(f"Attempting to restart agent {agent_id}")
    
    # Extract window index from agent_id
    try:
        session_name, window_index = agent_id.split(':')
        window_index = int(window_index)
    except ValueError:
        logger.error(f"Invalid agent_id format: {agent_id}")
        return False
    
    # Get project path
    project_path = get_project_path_for_agent(agent_id)
    
    # Prepare restart command
    cmd = [
        'python3',
        str(AUTO_ORCHESTRATE_SCRIPT),
        '--project', str(project_path),
        '--resume',
        '--rebrief-agent', str(window_index)
    ]
    
    try:
        logger.info(f"Running restart command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # 1 minute timeout
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully restarted agent {agent_id}")
            
            # Queue a message explaining the restart
            from enqueue_message import enqueue_message
            restart_msg = f"""🔄 **Automatic Restart**

You were automatically restarted due to an error:
- Error: {error_info.get('message', 'Unknown error')}
- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please check your workspace and continue with your tasks:
1. Run `pwd` to verify your location
2. Run `git status` to check uncommitted work
3. Review any error logs if needed
4. Continue with your assigned responsibilities"""
            
            enqueue_message(agent_id, restart_msg, priority=90)
            
            return True
        else:
            logger.error(f"Restart command failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Restart command timed out")
        return False
    except Exception as e:
        logger.error(f"Restart failed with exception: {e}", exc_info=True)
        return False

def main():
    """Main entry point for hook execution."""
    # Read error info from stdin (piped from hook)
    try:
        error_json = sys.stdin.read()
        error_info = json.loads(error_json)
    except Exception as e:
        logger.error(f"Failed to parse error info: {e}")
        sys.exit(1)
    
    agent_id = error_info.get('agent_id')
    if not agent_id:
        logger.error("No agent_id in error info")
        sys.exit(1)
    
    logger.info(f"Processing error for agent {agent_id}: {error_info.get('message', 'Unknown')}")
    
    # Check if restart is appropriate
    if not should_restart(error_info):
        logger.info("Error is non-recoverable, skipping restart")
        sys.exit(0)
    
    # Check restart limits
    if not check_restart_limits(agent_id):
        logger.warning("Agent exceeded restart limits")
        sys.exit(0)
    
    # Attempt restart
    success = restart_agent(agent_id, error_info)
    update_restart_history(agent_id, success)
    
    if not success:
        # Log failure for monitoring
        from cleanup_agent import cleanup_agent
        cleanup_agent(agent_id, reason='restart_failed')
        sys.exit(1)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
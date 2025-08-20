#!/usr/bin/env python3
"""
Subprocess wrapper with retry logic and better error handling
"""

import subprocess
import time
import logging
from typing import Optional, Union, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class SubprocessError(Exception):
    """Custom exception for subprocess failures"""
    pass

def run_with_retry(
    cmd: Union[str, List[str]], 
    max_retries: int = 3,
    retry_delay: float = 1.0,
    timeout: Optional[float] = None,
    check: bool = True,
    shell: bool = False,
    cwd: Optional[Union[str, Path]] = None,
    **kwargs
) -> subprocess.CompletedProcess:
    """
    Run a subprocess command with automatic retry on failure.
    
    Args:
        cmd: Command to run (string or list)
        max_retries: Maximum number of retry attempts (default 3)
        retry_delay: Delay between retries in seconds (default 1.0)
        timeout: Command timeout in seconds (optional)
        check: Whether to raise exception on non-zero exit (default True)
        shell: Whether to run through shell (default False)
        cwd: Working directory for command
        **kwargs: Additional arguments passed to subprocess.run
        
    Returns:
        subprocess.CompletedProcess object
        
    Raises:
        SubprocessError: If command fails after all retries
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Log the attempt
            if attempt > 0:
                logger.info(f"Retry attempt {attempt + 1}/{max_retries} for command: {cmd}")
            
            # Run the command
            result = subprocess.run(
                cmd,
                shell=shell,
                cwd=cwd,
                timeout=timeout,
                check=False,  # We'll check manually
                capture_output=True,
                text=True,
                **kwargs
            )
            
            # Check for success
            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, cmd, result.stdout, result.stderr
                )
            
            # Success - return result
            return result
            
        except subprocess.TimeoutExpired as e:
            last_error = e
            logger.warning(f"Command timed out after {timeout}s: {cmd}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
                
        except subprocess.CalledProcessError as e:
            last_error = e
            logger.warning(f"Command failed with exit code {e.returncode}: {cmd}")
            logger.debug(f"stdout: {e.stdout}")
            logger.debug(f"stderr: {e.stderr}")
            
            # Don't retry for certain exit codes
            if e.returncode in [127, 126]:  # Command not found, permission denied
                break
                
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
                
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error running command: {cmd} - {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
    
    # All retries failed
    raise SubprocessError(f"Command failed after {max_retries} attempts: {cmd}") from last_error

def safe_check_output(
    cmd: Union[str, List[str]],
    default: str = "",
    **kwargs
) -> str:
    """
    Safely get command output with fallback on failure.
    
    Args:
        cmd: Command to run
        default: Default value to return on failure
        **kwargs: Arguments passed to run_with_retry
        
    Returns:
        Command output or default value
    """
    try:
        result = run_with_retry(cmd, check=True, **kwargs)
        return result.stdout.strip()
    except SubprocessError:
        logger.warning(f"Failed to get output for: {cmd}, using default: {default}")
        return default

def tmux_safe_run(
    tmux_cmd: List[str],
    max_retries: int = 3,
    retry_delay: float = 0.5
) -> subprocess.CompletedProcess:
    """
    Specialized wrapper for tmux commands with common error handling.
    
    Args:
        tmux_cmd: Tmux command parts (without 'tmux' prefix)
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries
        
    Returns:
        subprocess.CompletedProcess object
    """
    full_cmd = ['tmux'] + tmux_cmd
    
    try:
        return run_with_retry(
            full_cmd,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=5.0  # tmux commands should be fast
        )
    except SubprocessError as e:
        # Special handling for common tmux errors
        if "no server running" in str(e):
            logger.error("No tmux server running - cannot execute command")
        elif "session not found" in str(e):
            logger.error("Tmux session not found")
        elif "window not found" in str(e):
            logger.error("Tmux window not found")
        raise

def git_safe_run(
    git_cmd: List[str],
    cwd: Optional[Union[str, Path]] = None,
    max_retries: int = 3
) -> subprocess.CompletedProcess:
    """
    Specialized wrapper for git commands with common error handling.
    
    Args:
        git_cmd: Git command parts (without 'git' prefix)
        cwd: Working directory for git command
        max_retries: Maximum retry attempts
        
    Returns:
        subprocess.CompletedProcess object
    """
    full_cmd = ['git'] + git_cmd
    
    try:
        return run_with_retry(
            full_cmd,
            cwd=cwd,
            max_retries=max_retries,
            retry_delay=2.0,  # Git operations may need more time
            timeout=30.0  # Git operations can be slow
        )
    except SubprocessError as e:
        # Special handling for common git errors
        if "not a git repository" in str(e):
            logger.error(f"Not a git repository: {cwd}")
        elif "Could not resolve host" in str(e):
            logger.error("Network error - cannot reach git remote")
        raise

# Convenience functions for common patterns
def check_command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH"""
    try:
        run_with_retry(['which', cmd], max_retries=1)
        return True
    except SubprocessError:
        return False

def get_process_info(pattern: str) -> List[Dict[str, Any]]:
    """Get process information matching a pattern"""
    try:
        result = run_with_retry(
            ['pgrep', '-f', '-a', pattern],
            check=False,  # pgrep returns 1 if no matches
            max_retries=1
        )
        
        processes = []
        if result.returncode == 0 and result.stdout:
            for line in result.stdout.strip().split('\n'):
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    processes.append({
                        'pid': int(parts[0]),
                        'cmd': parts[1]
                    })
        return processes
        
    except SubprocessError:
        return []

if __name__ == "__main__":
    # Test the wrapper
    logging.basicConfig(level=logging.DEBUG)
    
    # Test successful command
    print("Testing successful command...")
    result = run_with_retry(['echo', 'Hello, World!'])
    print(f"Output: {result.stdout}")
    
    # Test command with retries
    print("\nTesting command that might fail...")
    try:
        result = run_with_retry(['false'], max_retries=2, retry_delay=0.5)
    except SubprocessError as e:
        print(f"Expected failure: {e}")
    
    # Test tmux wrapper
    print("\nTesting tmux wrapper...")
    try:
        result = tmux_safe_run(['list-sessions'])
        print(f"Tmux sessions: {result.stdout}")
    except SubprocessError as e:
        print(f"Tmux error: {e}")
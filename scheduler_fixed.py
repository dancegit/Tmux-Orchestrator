#!/usr/bin/env python3
"""
Temporary wrapper to ensure the scheduler uses direct execution for auto_orchestrate.py
This bypasses any caching issues with the systemd service.
"""
import sys
import os

# Add the Tmux-Orchestrator directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and monkey-patch the scheduler module before it creates subprocesses
import scheduler

# Find the process_next_project method and patch it
original_process_next_project = scheduler.QueueDaemon.process_next_project

def patched_process_next_project(self):
    """Patched version that ensures direct execution"""
    # Store original subprocess.run
    import subprocess
    original_run = subprocess.run
    
    def patched_run(cmd, *args, **kwargs):
        # If this is calling auto_orchestrate.py with nested uv, fix it
        if len(cmd) >= 5 and cmd[0] == 'uv' and cmd[1] == 'run' and 'auto_orchestrate.py' in str(cmd[4]):
            print(f"FIXING nested UV execution: {cmd}")
            # Remove the uv run --quiet --script prefix
            cmd = cmd[4:]  # Skip 'uv', 'run', '--quiet', '--script'
            print(f"Fixed to direct execution: {cmd}")
        return original_run(cmd, *args, **kwargs)
    
    # Temporarily patch subprocess.run
    subprocess.run = patched_run
    try:
        return original_process_next_project(self)
    finally:
        # Restore original
        subprocess.run = original_run

# Apply the patch
scheduler.QueueDaemon.process_next_project = patched_process_next_project

# Now run the scheduler with the original arguments
if __name__ == "__main__":
    scheduler.main()
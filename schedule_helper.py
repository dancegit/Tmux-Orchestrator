#!/usr/bin/env python3
"""
Helper for dynamic scheduling decisions
"""

import subprocess
import sys

def schedule_next_check(reason="", minutes=None):
    """
    Schedule next check based on current situation
    
    Guidelines:
    - 2 minutes: Quick tasks, idle agents, need frequent monitoring
    - 3 minutes: Standard tasks in progress
    - 4 minutes: Complex tasks, research, building features
    - 5 minutes: Long running processes, waiting for results
    """
    
    if minutes is None:
        # Default to 3 minutes
        minutes = 3
    
    # Ensure within bounds
    minutes = max(2, min(5, minutes))
    
    print(f"\n{'='*50}")
    print(f"Scheduling Next Check: {minutes} minutes")
    if reason:
        print(f"Reason: {reason}")
    print(f"{'='*50}\n")
    
    # Execute the dynamic schedule script
    cmd = ["/Users/jasonedward/Coding/Tmux orchestrator/dynamic_schedule.sh", str(minutes)]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    # Can be called from command line
    if len(sys.argv) > 1:
        if len(sys.argv) > 2:
            schedule_next_check(reason=sys.argv[2], minutes=int(sys.argv[1]))
        else:
            schedule_next_check(minutes=int(sys.argv[1]))
    else:
        schedule_next_check()
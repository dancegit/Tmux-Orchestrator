#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Reset credit status for agents that have been manually recovered"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

# Set UV_NO_WORKSPACE environment variable for all subprocess calls
os.environ['UV_NO_WORKSPACE'] = '1'

def kill_stale_resume_processes():
    """Kill any resume processes scheduled for tomorrow"""
    try:
        # Find all sleep processes waiting for ~75000+ seconds (tomorrow)
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'sleep 75' in line and 'resume_signalmatrix' in line:
                parts = line.split()
                if len(parts) > 1:
                    pid = parts[1]
                    print(f"Killing stale resume process: PID {pid}")
                    subprocess.run(['kill', pid])
    except Exception as e:
        print(f"Error killing processes: {e}")

def reset_agent_status(agent: str):
    """Reset a specific agent to active status"""
    schedule_path = Path.home() / '.claude' / 'credit_schedule.json'
    
    if not schedule_path.exists():
        print(f"No credit schedule found at {schedule_path}")
        return
    
    with open(schedule_path, 'r') as f:
        schedule = json.load(f)
    
    if agent in schedule.get('agents', {}):
        old_status = schedule['agents'][agent].get('status', 'unknown')
        schedule['agents'][agent]['status'] = 'active'
        schedule['agents'][agent]['last_checked'] = datetime.now().isoformat()
        
        # Remove exhaustion-related fields
        for field in ['exhausted_at', 'scheduled_resume']:
            if field in schedule['agents'][agent]:
                del schedule['agents'][agent][field]
        
        print(f"Reset {agent}: {old_status} -> active")
        
        # Remove any resume script for this agent
        resume_script = Path.home() / '.claude' / f'resume_{agent.replace(':', '_')}.sh'
        if resume_script.exists():
            resume_script.unlink()
            print(f"Removed resume script: {resume_script}")
    
    # Save updated schedule
    with open(schedule_path, 'w') as f:
        json.dump(schedule, f, indent=2)

def main():
    """Reset all exhausted agents to active status"""
    print("Resetting credit status for manually recovered agents...")
    
    # Kill stale resume processes first
    kill_stale_resume_processes()
    
    # Read current schedule
    schedule_path = Path.home() / '.claude' / 'credit_schedule.json'
    if not schedule_path.exists():
        print("No credit schedule found")
        return
    
    with open(schedule_path, 'r') as f:
        schedule = json.load(f)
    
    # Find all exhausted agents
    exhausted_agents = []
    for agent, status in schedule.get('agents', {}).items():
        if status.get('status') == 'exhausted':
            exhausted_agents.append(agent)
    
    if not exhausted_agents:
        print("No exhausted agents found")
        return
    
    print(f"\nFound {len(exhausted_agents)} exhausted agents:")
    for agent in exhausted_agents:
        print(f"  - {agent}")
    
    print("\nResetting all to active status...")
    for agent in exhausted_agents:
        reset_agent_status(agent)
    
    print("\nDone! The credit monitor will re-check their actual status on the next cycle.")
    print("If they're truly exhausted, it will detect that and reschedule appropriately.")

if __name__ == "__main__":
    main()
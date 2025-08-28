#!/usr/bin/env python3
"""
Fix for agents using incorrect session names when reporting to orchestrator.

This script:
1. Detects the current tmux session name
2. Sends a message to agents with the correct session name
3. Ensures future communications use the full session name
"""

import subprocess
import sys
import re

def get_current_session():
    """Get the current tmux session name."""
    try:
        result = subprocess.run(
            ['tmux', 'display-message', '-p', '#{session_name}'],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def get_session_agents(session_name):
    """Get all agent windows in the session."""
    try:
        result = subprocess.run(
            ['tmux', 'list-windows', '-t', session_name, '-F', '#{window_index}:#{window_name}'],
            capture_output=True, text=True, check=True
        )
        agents = []
        for line in result.stdout.strip().split('\n'):
            if line:
                idx, name = line.split(':', 1)
                agents.append((int(idx), name))
        return agents
    except subprocess.CalledProcessError:
        return []

def send_session_correction(session_name, window_idx, agent_name):
    """Send a correction message to an agent about the correct session name."""
    message = f"""📍 **Session Name Update**

Important: When reporting to the Orchestrator, use the full session name:
`{session_name}:0`

Do NOT use shortened forms like "integrated-deployment:0".

Your current session: {session_name}
Your window: {window_idx} ({agent_name})
Orchestrator location: {session_name}:0

Please acknowledge this update and use the correct session name for all future communications."""
    
    target = f"{session_name}:{window_idx}"
    
    # Send using the send-claude-message.sh script if available
    send_script = "/home/clauderun/Tmux-Orchestrator/send-claude-message.sh"
    try:
        subprocess.run([send_script, target, message], check=True)
        print(f"✅ Sent correction to {agent_name} at window {window_idx}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to direct tmux send
        subprocess.run(['tmux', 'send-keys', '-t', target, message, 'Enter'])
        print(f"✅ Sent correction to {agent_name} at window {window_idx} (direct)")

def main():
    # Get the target session from command line or current session
    if len(sys.argv) > 1:
        session_name = sys.argv[1]
    else:
        session_name = get_current_session()
    
    if not session_name:
        print("❌ Could not determine session name. Please provide it as an argument.")
        sys.exit(1)
    
    print(f"🔍 Checking session: {session_name}")
    
    # Check if it's the problematic session
    if "integrated-multi-component-deployment-testing" in session_name:
        print("✅ Found integrated deployment session")
        
        # Get all agents
        agents = get_session_agents(session_name)
        print(f"📊 Found {len(agents)} agents")
        
        # Send correction to non-orchestrator agents
        for idx, name in agents:
            if idx > 0:  # Skip orchestrator at window 0
                send_session_correction(session_name, idx, name)
        
        print("\n✅ Session name corrections sent to all agents")
        print(f"📝 Agents should now use: {session_name}:0 for orchestrator communication")
    else:
        print(f"ℹ️  Session '{session_name}' doesn't appear to need correction")

if __name__ == "__main__":
    main()
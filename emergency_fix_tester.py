#!/usr/bin/env python3
"""
Emergency fix for the Tester agent trying to use wrong session name
"""

import subprocess
import sys

def send_direct_message(target, message):
    """Send message directly via tmux send-keys"""
    try:
        # Clear any current input
        subprocess.run(['tmux', 'send-keys', '-t', target, 'C-u'], check=True)
        # Send the message
        subprocess.run(['tmux', 'send-keys', '-t', target, message, 'Enter'], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to send to {target}: {e}")
        return False

def main():
    session_name = "integrated-multi-component-deployment-testing-impl-e117e2b5"
    tester_window = 3
    
    # Send correction to tester
    correction = f"""🚨 URGENT CORRECTION:

The session name is: {session_name}
To report to the Orchestrator, use: {session_name}:0

NOT "integrated-deployment:0" - use the full session name!

Please retry your report using the correct session name."""
    
    target = f"{session_name}:{tester_window}"
    
    print(f"Sending emergency correction to Tester at {target}")
    if send_direct_message(target, correction):
        print("✅ Emergency correction sent successfully")
    else:
        print("❌ Failed to send emergency correction")

if __name__ == "__main__":
    main()
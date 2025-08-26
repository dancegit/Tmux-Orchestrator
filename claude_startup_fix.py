#!/usr/bin/env python3
"""
Fix for Claude startup to handle MCP configuration acceptance.
This script ensures Claude agents start properly by:
1. Starting Claude to accept any MCP configurations
2. Waiting for prompts and sending 'y' to accept
3. Exiting Claude
4. Restarting with --dangerously-skip-permissions
"""

import subprocess
import time
import sys

def start_claude_with_mcp_handling(session_window):
    """
    Start Claude with proper MCP configuration handling.
    
    Args:
        session_window: tmux target in format "session:window"
    """
    print(f"Starting Claude setup for {session_window}")
    
    # Step 1: Start Claude normally
    cmd = f"tmux send-keys -t {session_window} 'claude' Enter"
    subprocess.run(cmd, shell=True)
    time.sleep(3)
    
    # Step 2: Check for MCP configuration prompts
    capture_cmd = f"tmux capture-pane -t {session_window} -p"
    output = subprocess.check_output(capture_cmd, shell=True).decode()
    
    if "Accept this configuration" in output or ".mcp.json" in output:
        print(f"  Found MCP configuration prompt in {session_window}")
        # Send 'y' to accept
        accept_cmd = f"tmux send-keys -t {session_window} 'y' Enter"
        subprocess.run(accept_cmd, shell=True)
        time.sleep(2)
        
        # Exit Claude
        exit_cmd = f"tmux send-keys -t {session_window} '/exit' Enter"
        subprocess.run(exit_cmd, shell=True)
        time.sleep(2)
    else:
        # No MCP prompt, exit Claude anyway
        exit_cmd = f"tmux send-keys -t {session_window} '/exit' Enter"
        subprocess.run(exit_cmd, shell=True)
        time.sleep(2)
    
    # Step 3: Start Claude with --dangerously-skip-permissions
    final_cmd = f"tmux send-keys -t {session_window} 'claude --dangerously-skip-permissions' Enter"
    subprocess.run(final_cmd, shell=True)
    print(f"  Started Claude with permissions bypass in {session_window}")

def fix_all_agents_in_session(session_name):
    """
    Fix Claude startup for all agents in a session.
    """
    # Get all windows in the session
    list_cmd = f"tmux list-windows -t {session_name} -F '#{{window_index}}:#{{window_name}}'"
    windows_output = subprocess.check_output(list_cmd, shell=True).decode().strip()
    
    for window_info in windows_output.split('\n'):
        window_idx, window_name = window_info.split(':', 1)
        print(f"\nProcessing window {window_idx} ({window_name})")
        
        # Check if Claude is already running properly
        capture_cmd = f"tmux capture-pane -t {session_name}:{window_idx} -p"
        output = subprocess.check_output(capture_cmd, shell=True).decode()
        
        if "Bypassing Permissions" in output or "for shortcuts" in output:
            print(f"  Claude already running properly in window {window_idx}")
            continue
            
        # Fix Claude startup
        start_claude_with_mcp_handling(f"{session_name}:{window_idx}")
        time.sleep(5)  # Give Claude time to start

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 claude_startup_fix.py <session-name>")
        print("Example: python3 claude_startup_fix.py elliott-wave-mvp-impl-123")
        sys.exit(1)
    
    session_name = sys.argv[1]
    fix_all_agents_in_session(session_name)
    print("\nClaude startup fix completed!")
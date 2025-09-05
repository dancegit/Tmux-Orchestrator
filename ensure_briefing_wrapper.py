#!/usr/bin/env python3
"""
Wrapper to ensure briefing happens for tmux sessions.
This should be called AFTER tmux_orchestrator_cli.py creates a session.
"""

import subprocess
import sys
import time
from pathlib import Path
import json

def get_session_windows(session_name):
    """Get list of windows in a tmux session."""
    try:
        result = subprocess.run(
            ['tmux', 'list-windows', '-t', session_name, '-F', '#{window_index}:#{window_name}'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            windows = []
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    idx, name = line.split(':', 1)
                    windows.append((int(idx), name))
            return windows
    except:
        pass
    return []

def check_if_briefed(session_name, window_idx):
    """Check if a window has been briefed (has content beyond prompt)."""
    try:
        result = subprocess.run(
            ['tmux', 'capture-pane', '-t', f"{session_name}:{window_idx}", '-p'],
            capture_output=True, text=True
        )
        content = result.stdout.strip()
        # Check for signs of briefing
        if any(keyword in content for keyword in ['ROLE ACTIVATION', 'You are the', 'Your role is', 'coordinate', 'implement']):
            return True
        # Check if it's just an empty Claude prompt
        if 'Welcome to Claude' in content and len(content.split('\n')) < 20:
            return False
    except:
        pass
    return False

def send_briefing(session_name, window_idx, role_name, spec_path):
    """Send briefing to a specific window."""
    
    # Define role-specific briefings
    briefings = {
        'Orchestrator': f"""You are the Orchestrator for implementing the spec at {spec_path}.

Your role is to:
1. Read and analyze the specification
2. Create an implementation plan
3. Coordinate with other agents to implement the solution
4. Ensure all tests pass and the implementation is complete

Start by reading the spec file and creating a detailed implementation plan. Then coordinate with the Project Manager to break it down into tasks.""",
        
        'Project-Manager': f"""You are the Project Manager for implementing the spec at {spec_path}.

Your role is to:
1. Work with the Orchestrator to understand the implementation plan
2. Break down the work into specific, actionable tasks
3. Assign tasks to the Developer and track progress
4. Ensure quality standards and deadlines are met

Wait for the Orchestrator to provide the implementation plan, then create a task breakdown.""",
        
        'Developer': f"""You are the Developer for implementing the spec at {spec_path}.

Your role is to:
1. Implement the code according to the tasks assigned by the Project Manager
2. Follow best practices and maintain code quality
3. Write clean, maintainable, and well-documented code
4. Collaborate with the Tester to ensure testability

Wait for specific tasks from the Project Manager, then implement them following the project's coding standards.""",
        
        'Tester': f"""You are the Tester for the spec at {spec_path}.

Your role is to:
1. Write comprehensive test cases based on the specification
2. Create unit tests, integration tests, and end-to-end tests as needed
3. Validate that the implementation meets all requirements
4. Report any bugs or issues to the Developer

Wait for the Developer to provide implementations, then create thorough tests to validate them.""",
        
        'TestRunner': f"""You are the Test Runner for the spec at {spec_path}.

Your role is to:
1. Execute all tests created by the Tester
2. Generate test reports and coverage metrics
3. Verify that all tests pass successfully
4. Report results back to the team

Wait for the Tester to create tests, then run them and report the results."""
    }
    
    # Get briefing for role
    briefing = briefings.get(role_name, briefings.get('Developer'))  # Default to Developer
    
    # Use send-claude-message.sh if available
    send_script = Path('/home/clauderun/Tmux-Orchestrator/send-claude-message.sh')
    target = f"{session_name}:{window_idx}"
    
    if send_script.exists():
        result = subprocess.run(
            [str(send_script), target, briefing],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    else:
        # Fallback to direct tmux send-keys
        subprocess.run(['tmux', 'send-keys', '-t', target, briefing, 'Enter'])
        return True

def ensure_session_briefed(session_name, spec_path):
    """Ensure all agents in a session are briefed."""
    
    print(f"Ensuring briefing for session: {session_name}")
    
    # Get windows
    windows = get_session_windows(session_name)
    if not windows:
        print(f"No windows found in session {session_name}")
        return False
    
    briefed_count = 0
    for window_idx, window_name in windows:
        # Check if already briefed
        if check_if_briefed(session_name, window_idx):
            print(f"  Window {window_idx} ({window_name}): Already briefed ✓")
            briefed_count += 1
        else:
            # Send briefing
            print(f"  Window {window_idx} ({window_name}): Sending briefing...")
            if send_briefing(session_name, window_idx, window_name, spec_path):
                print(f"  Window {window_idx} ({window_name}): Briefed ✓")
                briefed_count += 1
                time.sleep(2)  # Pause between briefings
            else:
                print(f"  Window {window_idx} ({window_name}): Briefing failed ✗")
    
    print(f"Briefed {briefed_count}/{len(windows)} agents")
    return briefed_count == len(windows)

def main():
    """Main entry point."""
    
    if len(sys.argv) < 3:
        print("Usage: ensure_briefing_wrapper.py <session_name> <spec_path>")
        sys.exit(1)
    
    session_name = sys.argv[1]
    spec_path = sys.argv[2]
    
    # Wait a moment for session to stabilize
    time.sleep(3)
    
    # Ensure briefing
    success = ensure_session_briefed(session_name, spec_path)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
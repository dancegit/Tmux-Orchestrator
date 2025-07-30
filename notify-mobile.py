#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "requests",
#     "psutil",
# ]
# ///

"""
Mobile notification script for Tmux Orchestrator agents.
Sends status updates to the mobile monitoring app.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import subprocess

import requests
import psutil

def get_current_session_info():
    """Get current tmux session and window info."""
    try:
        session = os.environ.get('TMUX_PANE', '').split('.')[0] if 'TMUX_PANE' in os.environ else None
        if session:
            result = subprocess.run(['tmux', 'display-message', '-p', '#{session_name}:#{window_index}'], 
                                  capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else None
    except:
        pass
    return None

def get_git_status():
    """Get current git branch and recent commits."""
    try:
        # Get current branch
        branch_result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                     capture_output=True, text=True, cwd='.')
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
        
        # Get last commit
        commit_result = subprocess.run(['git', 'log', '-1', '--oneline'], 
                                     capture_output=True, text=True, cwd='.')
        last_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "No commits"
        
        # Check for uncommitted changes
        status_result = subprocess.run(['git', 'status', '--porcelain'], 
                                     capture_output=True, text=True, cwd='.')
        has_changes = bool(status_result.stdout.strip()) if status_result.returncode == 0 else False
        
        return {
            "branch": branch,
            "last_commit": last_commit,
            "has_uncommitted_changes": has_changes
        }
    except:
        return {"branch": "unknown", "last_commit": "Error getting git status", "has_uncommitted_changes": False}

def send_notification(status_type, message, details=None, priority="normal"):
    """Send notification to mobile app via local API."""
    session_info = get_current_session_info()
    git_info = get_git_status()
    
    notification = {
        "timestamp": datetime.now().isoformat(),
        "agent": {
            "session": session_info,
            "role": os.environ.get('AGENT_ROLE', 'unknown'),
            "pid": os.getpid()
        },
        "status_type": status_type,
        "message": message,
        "details": details or {},
        "git": git_info,
        "priority": priority,
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
        }
    }
    
    try:
        # Send to local API endpoint (mobile app connects via SSH tunnel)
        response = requests.post('http://localhost:8089/api/notifications', 
                               json=notification, timeout=5)
        if response.status_code == 200:
            print(f"✓ Mobile notification sent: {status_type}")
        else:
            print(f"✗ Mobile notification failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        # Mobile app not connected, save to queue
        queue_dir = Path("~/.tmux-orchestrator/mobile-queue").expanduser()
        queue_dir.mkdir(parents=True, exist_ok=True)
        
        queue_file = queue_dir / f"notification_{int(time.time())}.json"
        with open(queue_file, 'w') as f:
            json.dump(notification, f, indent=2)
        print(f"📱 Mobile notification queued: {queue_file}")
    except Exception as e:
        print(f"✗ Mobile notification error: {e}")

def main():
    """Main CLI interface for mobile notifications."""
    if len(sys.argv) < 3:
        print("Usage: notify-mobile.py <status_type> <message> [details_json] [priority]")
        print("\nStatus types: progress, completed, error, blocked, checkin, git_commit")
        print("Priority: low, normal, high, urgent")
        print("\nExamples:")
        print('  notify-mobile.py progress "Implementing authentication endpoints"')
        print('  notify-mobile.py completed "User login feature finished" \'{"tests_passed": true}\' high')
        print('  notify-mobile.py error "Database connection failed" \'{"error_code": 500}\'')
        print('  notify-mobile.py git_commit "Added JWT token validation"')
        sys.exit(1)
    
    status_type = sys.argv[1]
    message = sys.argv[2]
    details = json.loads(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else {}
    priority = sys.argv[4] if len(sys.argv) > 4 else "normal"
    
    send_notification(status_type, message, details, priority)

if __name__ == "__main__":
    main()
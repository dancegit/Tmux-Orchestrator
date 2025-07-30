# Tmux Orchestrator Mobile Monitor - Android App Specification

## Project Overview
Create an Android application that provides secure remote monitoring and voice control for Tmux Orchestrator projects, enabling users to track AI agent progress and issue voice commands from their mobile device.

## Core Features

### 1. Secure SSH Connection
- **SSH Keypair Generation**: Generate unique Ed25519 keypair in-app on first run
- **Key Management**: Store private key securely in Android Keystore
- **Public Key Export**: Display/export public key for manual server configuration
- **Server Configuration**: User configures server details in app settings
- **Connection Management**: Persistent SSH tunnel with auto-reconnect
- **Port Forwarding**: Secure tunnel for API endpoints (e.g., localhost:8089)

### 2. Real-time Project Monitoring
- **Dashboard View**: 
  - Active projects list
  - Current agent statuses (Active/Idle/Exhausted)
  - Work in progress for each agent
  - Next scheduled check-in times
  - Recent commits and git activity
- **Push Notifications**:
  - Project completion
  - Agent errors/blockers
  - Credit exhaustion warnings
  - Scheduled check-in reminders
- **Detail Views**:
  - Individual agent conversation logs
  - Git commit history
  - Error logs and violations

### 3. Voice Integration (ElevenLabs)
- **API Key Configuration**: User enters ElevenLabs API key in app settings
- **Text-to-Speech**:
  - Read status updates aloud
  - Voice notifications for important events
  - Configurable voice selection from available ElevenLabs voices
- **Voice-to-Text**:
  - Voice commands to orchestrator
  - Natural language processing for common tasks
  - Command confirmation before execution
- **Voice Commands**:
  - "What's the status of [project]?"
  - "Tell the developer to focus on [task]"
  - "Schedule a check-in for [time]"
  - "Create a new project for [specification]"

### 4. Build System
- **Local APK Generation**:
  ```bash
  ./build-android-monitor.sh
  ```
- **Build Process**:
  1. Build generic APK with no embedded secrets
  2. Sign APK with debug certificate
  3. Output: `tmux-monitor-[timestamp].apk`

### 5. App Configuration (First Run)
- **Initial Setup Screen**:
  - Server configuration (hostname/IP, SSH port)
  - SSH key generation and public key export
  - ElevenLabs API key entry
  - Voice settings (voice selection, language)
  - Connection testing
- **Configuration Storage**:
  - Encrypted preferences using Android Keystore
  - SSH private key stored in Android Keystore
  - All sensitive data encrypted at rest

## Technical Architecture

### Android App Components
- **Language**: Kotlin
- **Min SDK**: 26 (Android 8.0)
- **Architecture**: MVVM with Jetpack Compose
- **Dependencies**:
  - JSch or Apache MINA SSHD (SSH client)
  - Retrofit (API calls)
  - WorkManager (background updates)
  - ElevenLabs SDK
  - Room (local data caching)

### Server-side Components
- **API Service**: FastAPI endpoint on Tmux-Orchestrator server
- **WebSocket Server**: Real-time status updates
- **Authentication**: SSH key-based auth only
- **Data Format**: JSON over SSH tunnel

### Communication Protocol
```
Android App <--> SSH Tunnel <--> API Service <--> Tmux Sessions
     |                                 |
     v                                 v
 User Config                   claude_control.py
(Server, Keys)                monitoring scripts
```

## Agent Notification System

Agents use the `notify-mobile.py` script to send status updates to the mobile app:

```python
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
```

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
1. Android project setup with Kotlin
2. Initial setup wizard UI (server config, SSH key generation)
3. SSH client integration and keypair management
4. Settings screen for configuration management
5. Build script for generic APK generation
6. Server-side API endpoint setup

### Phase 2: Monitoring Features (Week 2)
1. Real-time status polling
2. Push notification system
3. Agent detail views
4. Git activity tracking
5. Error and violation monitoring
6. Agent notification script integration

### Phase 3: Voice Integration (Week 3)
1. ElevenLabs API integration with user-provided API key
2. Voice configuration UI (API key entry, voice selection)
3. Text-to-speech for status updates
4. Voice command recognition
5. Natural language command parsing
6. Voice notification system

### Phase 4: Polish & Testing (Week 4)
1. UI/UX improvements
2. Offline mode with data caching
3. Background service optimization
4. Security hardening
5. Documentation and deployment

## Agent Integration Examples

Agents can use the notification script in their workflows:

```bash
# Progress updates
notify-mobile.py progress "Starting database migration"
notify-mobile.py progress "50% complete on authentication module" '{"completion": 50}'

# Task completion
notify-mobile.py completed "Authentication endpoints finished" '{"tests_passed": true, "coverage": 95}'

# Error reporting
notify-mobile.py error "Build failed" '{"error": "Missing dependency: requests", "file": "requirements.txt"}'

# Git activities
notify-mobile.py git_commit "Added user registration API"

# Check-in notifications
notify-mobile.py checkin "Scheduled check-in complete" '{"next_checkin": "2024-01-15T14:30:00"}'

# Blocker alerts
notify-mobile.py blocked "Waiting for API documentation" '{"blocking_issue": "External API docs not available"}' urgent
```

## Security Considerations
- Private keys never leave the device (stored in Android Keystore)
- All communication through encrypted SSH tunnel
- ElevenLabs API key encrypted in app preferences (Android Keystore)
- No secrets embedded in APK at build time
- Unique keypair generated per app installation
- Optional biometric authentication for app access
- Agent notifications secured via localhost-only API
- User responsible for keeping API keys secure
- Public key export for manual server configuration

## Success Criteria
- ✓ Secure connection established within 3 seconds
- ✓ Real-time updates with <1 second latency
- ✓ Voice commands processed accurately 95%+ of the time
- ✓ Battery-efficient background monitoring
- ✓ Works on Android 8.0+ devices
- ✓ APK size under 25MB
- ✓ Agent notifications delivered within 2 seconds

## Future Enhancements
- iOS version
- Multi-server support
- Custom notification rules
- Voice conversation transcripts
- Integration with Claude API for direct agent interaction
- Notification queuing and retry mechanism
- Agent performance analytics dashboard

## File Structure
```
mobile-monitor/
├── android-app/
│   ├── app/src/main/
│   ├── build.gradle
│   └── ...
├── server-api/
│   ├── api_server.py
│   ├── websocket_server.py
│   └── requirements.txt
├── scripts/
│   ├── notify-mobile.py
│   └── build-android-monitor.sh
└── docs/
    └── API.md
```

This specification provides a comprehensive mobile monitoring and control solution for Tmux Orchestrator, enabling users to stay connected with their AI development teams from anywhere, with agents actively reporting their progress through the notification system.
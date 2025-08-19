#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Install Tmux Orchestrator Queue Daemon as systemd service
"""

import os
import sys
import subprocess
from pathlib import Path

def create_systemd_service():
    """Create systemd service file for queue daemon"""
    
    # Get current user and paths
    user = os.getenv('USER')
    home = Path.home()
    orchestrator_path = Path(__file__).parent
    
    service_content = f"""[Unit]
Description=Tmux Orchestrator Queue Daemon
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=5
User={user}
WorkingDirectory={orchestrator_path}
ExecStart=/usr/bin/python3 {orchestrator_path}/scheduler.py --queue-daemon
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=HOME={home}

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tmux-orchestrator-queue

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={orchestrator_path}
ReadWritePaths={home}

[Install]
WantedBy=multi-user.target
"""
    
    service_file = f"/etc/systemd/system/tmux-orchestrator-queue.service"
    
    print(f"Creating systemd service file: {service_file}")
    
    # Write service file (requires sudo)
    try:
        subprocess.run(['sudo', 'tee', service_file], 
                      input=service_content.encode(), 
                      check=True, capture_output=True)
        print("✅ Service file created")
        
        # Reload systemd
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        print("✅ Systemd reloaded")
        
        # Enable service
        subprocess.run(['sudo', 'systemctl', 'enable', 'tmux-orchestrator-queue'], check=True)
        print("✅ Service enabled")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating service: {e}")
        return False

def install_auto_start_script():
    """Create script to auto-start queue daemon when auto_orchestrate runs"""
    
    script_content = """#!/bin/bash
# Auto-start queue daemon if not running

SERVICE_NAME="tmux-orchestrator-queue"

# Check if service is running
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "🚀 Starting queue daemon service..."
    sudo systemctl start "$SERVICE_NAME"
    
    # Wait a moment for startup
    sleep 2
    
    # Check if it started successfully
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "✅ Queue daemon started successfully"
    else
        echo "❌ Failed to start queue daemon"
        echo "📋 Service status:"
        systemctl status "$SERVICE_NAME" --no-pager -l
    fi
else
    echo "✅ Queue daemon already running"
fi
"""
    
    script_path = Path(__file__).parent / "ensure_queue_daemon.sh"
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_path, 0o755)
    print(f"✅ Auto-start script created: {script_path}")
    
    return script_path

def main():
    print("🔧 Installing Tmux Orchestrator Queue Daemon")
    print("=" * 50)
    
    # Stop any running manual queue daemon first
    try:
        result = subprocess.run(['pkill', '-f', 'scheduler.py.*queue-daemon'], 
                               capture_output=True)
        if result.returncode == 0:
            print("🛑 Stopped manual queue daemon process")
    except:
        pass
    
    # Create systemd service
    if create_systemd_service():
        print("\n🎯 Systemd service installed successfully!")
        
        # Create auto-start script
        script_path = install_auto_start_script()
        
        print(f"\n📋 USAGE:")
        print(f"  Start:   sudo systemctl start tmux-orchestrator-queue")
        print(f"  Stop:    sudo systemctl stop tmux-orchestrator-queue") 
        print(f"  Status:  systemctl status tmux-orchestrator-queue")
        print(f"  Logs:    journalctl -u tmux-orchestrator-queue -f")
        print(f"  Auto:    {script_path}")
        
        # Ask to start now
        if len(sys.argv) > 1 and sys.argv[1] == '--start':
            print(f"\n🚀 Starting service now...")
            try:
                subprocess.run(['sudo', 'systemctl', 'start', 'tmux-orchestrator-queue'], check=True)
                print("✅ Service started!")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to start service: {e}")
        else:
            print(f"\n💡 To start the service now: sudo systemctl start tmux-orchestrator-queue")
            
    else:
        print("❌ Failed to install systemd service")
        sys.exit(1)

if __name__ == '__main__':
    main()
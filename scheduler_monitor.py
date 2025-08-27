#!/usr/bin/env python3
"""
Scheduler Process Monitor and Management Tool
Provides comprehensive monitoring, cleanup, and management of scheduler processes.
"""

import sys
import os
import time
import argparse
import logging
from pathlib import Path
from scheduler_lock_manager import SchedulerLockManager, check_scheduler_processes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cmd_status():
    """Show detailed scheduler status for dual-service architecture"""
    print("🔍 Scheduler Process Status (Dual-Service Architecture)")
    print("=" * 60)
    
    # Check both service modes
    services = [
        {"name": "Check-in Scheduler", "mode": "checkin"},
        {"name": "Queue Processor", "mode": "queue"}
    ]
    
    total_valid = 0
    
    for service in services:
        print(f"\n📋 {service['name']} (mode: {service['mode']})")
        print("-" * 40)
        
        lock_manager = SchedulerLockManager(mode=service['mode'])
        status = lock_manager.get_status()
        
        print(f"Lock file exists: {status['lock_file_exists']}")
        print(f"Process file exists: {status['process_file_exists']}")
        
        if 'lock_data' in status:
            lock_data = status['lock_data']
            print(f"Lock holder PID: {lock_data.get('pid', 'unknown')}")
            print(f"Lock timestamp: {lock_data.get('timestamp', 'unknown')}")
            print(f"Lock hostname: {lock_data.get('hostname', 'unknown')}")
        
        schedulers = status['existing_schedulers']
        
        if not schedulers:
            print("  ❌ No processes running for this service")
        else:
            for scheduler in schedulers:
                status_icon = "✅" if scheduler['valid'] else "❌"
                print(f"  {status_icon} PID {scheduler['pid']}")
                print(f"     Command: {scheduler['cmdline']}")
                print(f"     Directory: {scheduler['cwd']}")
                print(f"     Started: {scheduler['create_time']}")
                print(f"     Status: {scheduler['reason']}")
                if scheduler['valid']:
                    total_valid += 1
    
    # Check systemd services
    print(f"\n🔧 Systemd Service Status")
    print("-" * 40)
    try:
        import subprocess
        checkin_status = subprocess.run(['systemctl', 'is-active', 'tmux-orchestrator-checkin'], 
                                       capture_output=True, text=True)
        queue_status = subprocess.run(['systemctl', 'is-active', 'tmux-orchestrator-queue'], 
                                     capture_output=True, text=True)
        
        checkin_active = checkin_status.returncode == 0
        queue_active = queue_status.returncode == 0
        
        print(f"  tmux-orchestrator-checkin: {'✅ active' if checkin_active else '❌ inactive'}")
        print(f"  tmux-orchestrator-queue: {'✅ active' if queue_active else '❌ inactive'}")
        
    except Exception as e:
        print(f"  ⚠️  Could not check systemd status: {e}")
    
    print(f"\n📊 Summary: {total_valid} valid scheduler process(es) running")
    
    # Updated validation for dual services
    if total_valid == 0:
        print("❌ No scheduler services running")
        return 1
    elif total_valid == 2:
        print("✅ Both scheduler services running (optimal)")
        return 0
    else:
        print(f"⚠️  WARNING: Only {total_valid}/2 scheduler services running")
        return 1

def cmd_cleanup():
    """Clean up stale locks and dead processes"""
    print("🧹 Scheduler Cleanup")
    print("=" * 50)
    
    lock_manager = SchedulerLockManager()
    
    # Cleanup stale locks
    print("Cleaning up stale locks...")
    cleaned = lock_manager._cleanup_stale_locks()
    
    if cleaned:
        print("✅ Cleaned up stale locks")
    else:
        print("✅ No stale locks found")
    
    # Show current status
    print("\nPost-cleanup status:")
    return cmd_status()

def cmd_stop_all():
    """Stop all scheduler processes"""
    print("🛑 Stopping All Schedulers")
    print("=" * 50)
    
    lock_manager = SchedulerLockManager()
    status = lock_manager.get_status()
    
    schedulers = status['existing_schedulers']
    valid_schedulers = [s for s in schedulers if s['valid']]
    
    if not valid_schedulers:
        print("✅ No scheduler processes to stop")
        return 0
    
    print(f"Found {len(valid_schedulers)} scheduler(s) to stop:")
    
    stopped = 0
    for scheduler in valid_schedulers:
        pid = scheduler['pid']
        print(f"  Stopping PID {pid}... ", end="")
        
        try:
            os.kill(pid, 15)  # SIGTERM
            print("✅ SIGTERM sent")
            stopped += 1
        except OSError as e:
            print(f"❌ Failed: {e}")
    
    if stopped > 0:
        print(f"\n⏳ Waiting 5 seconds for graceful shutdown...")
        time.sleep(5)
        
        # Check if any are still running
        status = lock_manager.get_status()
        remaining = [s for s in status['existing_schedulers'] if s['valid']]
        
        if remaining:
            print(f"⚠️  {len(remaining)} process(es) still running, sending SIGKILL...")
            for scheduler in remaining:
                pid = scheduler['pid']
                try:
                    os.kill(pid, 9)  # SIGKILL
                    print(f"  Killed PID {pid}")
                except OSError:
                    print(f"  PID {pid} already gone")
        
        # Final cleanup
        lock_manager._cleanup_stale_locks()
        print("✅ All schedulers stopped and locks cleaned up")
    
    return 0

def cmd_restart():
    """Restart scheduler safely"""
    print("🔄 Restarting Scheduler")
    print("=" * 50)
    
    # Stop all existing
    print("Step 1: Stopping existing schedulers...")
    cmd_stop_all()
    
    # Wait a moment
    time.sleep(2)
    
    # Start new one
    print("\nStep 2: Starting new scheduler...")
    os.system("python3 start_scheduler_safe.py --daemon")
    
    # Verify startup
    time.sleep(3)
    print("\nStep 3: Verifying startup...")
    return cmd_status()

def cmd_monitor():
    """Continuous monitoring mode"""
    print("👁️  Scheduler Monitor (Ctrl+C to stop)")
    print("=" * 50)
    
    try:
        while True:
            os.system('clear')
            print(f"Scheduler Monitor - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 50)
            
            cmd_status()
            
            print("\n" + "="*50)
            print("Refreshing in 10 seconds... (Ctrl+C to stop)")
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n👋 Monitor stopped")
        return 0

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Scheduler Process Monitor and Management Tool",
        epilog="Examples:\n"
               "  %(prog)s status     - Show scheduler status\n"
               "  %(prog)s cleanup    - Clean up stale locks\n"
               "  %(prog)s stop-all   - Stop all schedulers\n"
               "  %(prog)s restart    - Restart scheduler safely\n"
               "  %(prog)s monitor    - Continuous monitoring",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('command', 
                       choices=['status', 'cleanup', 'stop-all', 'restart', 'monitor'],
                       help='Command to execute')
    
    args = parser.parse_args()
    
    if args.command == 'status':
        return cmd_status()
    elif args.command == 'cleanup':
        return cmd_cleanup()
    elif args.command == 'stop-all':
        return cmd_stop_all()
    elif args.command == 'restart':
        return cmd_restart()
    elif args.command == 'monitor':
        return cmd_monitor()
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
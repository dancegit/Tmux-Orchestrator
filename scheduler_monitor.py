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
    """Show detailed scheduler status"""
    print("🔍 Scheduler Process Status")
    print("=" * 50)
    
    lock_manager = SchedulerLockManager()
    status = lock_manager.get_status()
    
    print(f"Current PID: {status['current_pid']}")
    print(f"Lock file exists: {status['lock_file_exists']}")
    print(f"Process file exists: {status['process_file_exists']}")
    
    if 'lock_data' in status:
        lock_data = status['lock_data']
        print(f"Lock holder PID: {lock_data.get('pid', 'unknown')}")
        print(f"Lock timestamp: {lock_data.get('timestamp', 'unknown')}")
        print(f"Lock hostname: {lock_data.get('hostname', 'unknown')}")
    
    schedulers = status['existing_schedulers']
    print(f"\nFound {len(schedulers)} scheduler process(es):")
    
    if not schedulers:
        print("  ✅ No scheduler processes detected")
        return 0
    
    for i, scheduler in enumerate(schedulers, 1):
        status_icon = "✅" if scheduler['valid'] else "❌"
        print(f"\n  {i}. {status_icon} PID {scheduler['pid']}")
        print(f"     Command: {scheduler['cmdline']}")
        print(f"     Directory: {scheduler['cwd']}")
        print(f"     Started: {scheduler['create_time']}")
        print(f"     Status: {scheduler['reason']}")
    
    valid_count = sum(1 for s in schedulers if s['valid'])
    if valid_count == 0:
        print("\n✅ No valid schedulers running")
        return 0
    elif valid_count == 1:
        print("\n✅ Single scheduler running (normal)")
        return 0
    else:
        print(f"\n⚠️  WARNING: {valid_count} schedulers running (DUPLICATE DETECTED!)")
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
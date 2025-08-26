#!/usr/bin/env python3
"""
Safe Scheduler Startup Script
Prevents duplicate scheduler processes with enhanced detection and safety checks.
"""

import sys
import os
import logging
from pathlib import Path
from scheduler_lock_manager import SchedulerLockManager, check_scheduler_processes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main startup with comprehensive duplicate prevention"""
    
    print("🔒 Tmux Orchestrator Safe Scheduler Startup")
    print("=" * 50)
    
    # Step 1: Check for existing scheduler processes
    print("Step 1: Checking for existing scheduler processes...")
    lock_manager = SchedulerLockManager()
    status = lock_manager.get_status()
    
    existing_schedulers = status['existing_schedulers']
    valid_schedulers = [s for s in existing_schedulers if s['valid']]
    
    if valid_schedulers:
        print(f"❌ Found {len(valid_schedulers)} existing scheduler process(es):")
        for scheduler in valid_schedulers:
            print(f"   PID {scheduler['pid']}: {scheduler['cmdline']}")
            print(f"   Directory: {scheduler['cwd']}")
            print(f"   Started: {scheduler['create_time']}")
        
        print("\n🛑 STOPPING: Will not start duplicate scheduler!")
        print("Use 'python3 scheduler_lock_manager.py --check' to investigate.")
        return 1
    
    print("✅ No existing schedulers found")
    
    # Step 2: Attempt lock acquisition
    print("\nStep 2: Acquiring scheduler lock...")
    if not lock_manager.acquire_lock():
        print("❌ Failed to acquire scheduler lock")
        print("Another scheduler may have started during our check.")
        return 1
    
    print("✅ Scheduler lock acquired successfully")
    
    # Step 3: Start the scheduler
    print("\nStep 3: Starting scheduler daemon...")
    try:
        # Import and start scheduler
        sys.path.append(str(Path(__file__).parent))
        from scheduler import TmuxOrchestratorScheduler
        
        # Create scheduler instance
        scheduler = TmuxOrchestratorScheduler()
        
        # Release our lock since TmuxScheduler will acquire its own
        lock_manager.release_lock()
        
        # Run in daemon mode
        if '--daemon' in sys.argv:
            print("🚀 Starting in daemon mode...")
            scheduler.run_queue_daemon()
        else:
            print("🚀 Starting in interactive mode...")
            scheduler.run()
            
    except KeyboardInterrupt:
        print("\n⏹️  Scheduler stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Failed to start scheduler: {e}")
        logger.exception("Scheduler startup failed")
        return 1
    finally:
        # Ensure lock is released
        try:
            lock_manager.release_lock()
        except:
            pass
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
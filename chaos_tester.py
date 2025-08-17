#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Chaos Testing Framework for Tmux Orchestrator
Simulates failures and tests system resilience
"""

import os
import sys
import random
import time
import json
import subprocess
import signal
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Callable
import argparse
import logging
import shutil

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChaosEvent:
    """Represents a chaos event that can be triggered"""
    def __init__(self, name: str, description: str, action: Callable, 
                 severity: str = 'medium', probability: float = 0.5):
        self.name = name
        self.description = description
        self.action = action
        self.severity = severity
        self.probability = probability
        self.triggered_count = 0
        self.last_triggered = None
    
    def trigger(self) -> bool:
        """Trigger the chaos event"""
        try:
            logger.info(f"Triggering chaos event: {self.name}")
            self.action()
            self.triggered_count += 1
            self.last_triggered = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Failed to trigger {self.name}: {e}")
            return False


class ChaosTester:
    def __init__(self, orchestrator_path: Path = None, dry_run: bool = False):
        self.orchestrator_path = orchestrator_path or Path.cwd()
        self.dry_run = dry_run
        self.events: List[ChaosEvent] = []
        self.results = {
            'start_time': datetime.now().isoformat(),
            'events_triggered': [],
            'recovery_times': {},
            'failures': []
        }
        
        # Initialize chaos events
        self._setup_chaos_events()
    
    def _setup_chaos_events(self):
        """Setup all chaos events"""
        # Tmux-related chaos
        self.events.append(ChaosEvent(
            'kill_random_window',
            'Kill a random tmux window',
            self._kill_random_tmux_window,
            severity='high',
            probability=0.3
        ))
        
        self.events.append(ChaosEvent(
            'detach_session',
            'Detach from tmux session',
            self._detach_tmux_session,
            severity='low',
            probability=0.7
        ))
        
        # Process chaos
        self.events.append(ChaosEvent(
            'high_cpu_load',
            'Create high CPU load',
            self._create_cpu_load,
            severity='medium',
            probability=0.4
        ))
        
        self.events.append(ChaosEvent(
            'memory_pressure',
            'Create memory pressure',
            self._create_memory_pressure,
            severity='high',
            probability=0.3
        ))
        
        # File system chaos
        self.events.append(ChaosEvent(
            'fill_disk_space',
            'Fill up disk space temporarily',
            self._fill_disk_space,
            severity='high',
            probability=0.2
        ))
        
        self.events.append(ChaosEvent(
            'corrupt_git_worktree',
            'Corrupt a git worktree',
            self._corrupt_git_worktree,
            severity='high',
            probability=0.2
        ))
        
        # Scheduler chaos
        self.events.append(ChaosEvent(
            'kill_scheduler',
            'Kill the scheduler process',
            self._kill_scheduler,
            severity='medium',
            probability=0.5
        ))
        
        self.events.append(ChaosEvent(
            'corrupt_task_queue',
            'Corrupt the task queue database',
            self._corrupt_task_queue,
            severity='high',
            probability=0.3
        ))
        
        # Network chaos (simulated)
        self.events.append(ChaosEvent(
            'slow_git_operations',
            'Make git operations slow',
            self._slow_git_operations,
            severity='medium',
            probability=0.4
        ))
    
    def _kill_random_tmux_window(self):
        """Kill a random tmux window"""
        if self.dry_run:
            logger.info("[DRY RUN] Would kill random tmux window")
            return
        
        # Get list of windows
        result = subprocess.run(
            ['tmux', 'list-windows', '-F', '#{session_name}:#{window_index}'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout:
            windows = result.stdout.strip().split('\n')
            # Filter out orchestrator windows to avoid killing ourselves
            windows = [w for w in windows if 'orchestrator' not in w.lower()]
            
            if windows:
                target = random.choice(windows)
                logger.info(f"Killing tmux window: {target}")
                subprocess.run(['tmux', 'kill-window', '-t', target])
    
    def _detach_tmux_session(self):
        """Detach from a tmux session"""
        if self.dry_run:
            logger.info("[DRY RUN] Would detach tmux session")
            return
        
        # This simulates an accidental detach
        result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            sessions = result.stdout.strip().split('\n')
            if sessions:
                target = random.choice(sessions)
                logger.info(f"Detaching session: {target}")
                subprocess.run(['tmux', 'detach-client', '-s', target])
    
    def _create_cpu_load(self):
        """Create temporary CPU load"""
        if self.dry_run:
            logger.info("[DRY RUN] Would create CPU load")
            return
        
        logger.info("Creating CPU load for 10 seconds")
        
        def cpu_burn():
            end_time = time.time() + 10
            while time.time() < end_time:
                _ = sum(i*i for i in range(1000))
        
        # Start CPU burn in background threads
        threads = []
        for _ in range(os.cpu_count() or 4):
            t = threading.Thread(target=cpu_burn)
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Don't wait for threads to complete
    
    def _create_memory_pressure(self):
        """Create temporary memory pressure"""
        if self.dry_run:
            logger.info("[DRY RUN] Would create memory pressure")
            return
        
        logger.info("Creating memory pressure")
        
        # Allocate 500MB of memory temporarily
        data = []
        try:
            for _ in range(50):
                data.append('x' * (10 * 1024 * 1024))  # 10MB chunks
            
            # Hold for 5 seconds
            time.sleep(5)
        except MemoryError:
            logger.warning("Memory allocation failed - system protected itself")
        finally:
            data.clear()
    
    def _fill_disk_space(self):
        """Temporarily fill disk space"""
        if self.dry_run:
            logger.info("[DRY RUN] Would fill disk space")
            return
        
        temp_file = self.orchestrator_path / '.chaos_disk_fill'
        logger.info("Creating large temporary file")
        
        try:
            # Write 100MB file
            with open(temp_file, 'wb') as f:
                for _ in range(100):
                    f.write(b'0' * (1024 * 1024))
            
            # Keep for 10 seconds
            time.sleep(10)
        finally:
            if temp_file.exists():
                temp_file.unlink()
    
    def _corrupt_git_worktree(self):
        """Simulate git worktree corruption"""
        if self.dry_run:
            logger.info("[DRY RUN] Would corrupt git worktree")
            return
        
        # Find a worktree
        worktrees_path = self.orchestrator_path / 'registry' / 'projects'
        if not worktrees_path.exists():
            return
        
        worktrees = list(worktrees_path.glob('*/worktrees/*/.git'))
        if not worktrees:
            return
        
        target = random.choice(worktrees)
        logger.info(f"Corrupting git config in: {target.parent}")
        
        # Backup original
        backup = target.parent / '.git.chaos_backup'
        if target.exists():
            target.rename(backup)
            
            # Create corrupted version
            target.write_text("corrupted by chaos testing")
            
            # Restore after 30 seconds
            def restore():
                time.sleep(30)
                if backup.exists():
                    target.unlink()
                    backup.rename(target)
                    logger.info(f"Restored git config in: {target.parent}")
            
            threading.Thread(target=restore, daemon=True).start()
    
    def _kill_scheduler(self):
        """Kill the scheduler process"""
        if self.dry_run:
            logger.info("[DRY RUN] Would kill scheduler")
            return
        
        # Find scheduler process
        import psutil
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'scheduler.py' in ' '.join(cmdline):
                    logger.info(f"Killing scheduler process: {proc.info['pid']}")
                    proc.kill()
                    break
            except:
                pass
    
    def _corrupt_task_queue(self):
        """Corrupt the task queue database"""
        if self.dry_run:
            logger.info("[DRY RUN] Would corrupt task queue")
            return
        
        db_path = self.orchestrator_path / 'task_queue.db'
        if not db_path.exists():
            return
        
        logger.info("Corrupting task queue database")
        
        # Backup original
        backup = db_path.with_suffix('.db.chaos_backup')
        shutil.copy2(db_path, backup)
        
        # Corrupt by truncating
        with open(db_path, 'r+b') as f:
            size = f.seek(0, 2)
            if size > 1000:
                f.seek(size // 2)
                f.truncate()
        
        # Restore after 60 seconds
        def restore():
            time.sleep(60)
            if backup.exists():
                shutil.copy2(backup, db_path)
                backup.unlink()
                logger.info("Restored task queue database")
        
        threading.Thread(target=restore, daemon=True).start()
    
    def _slow_git_operations(self):
        """Make git operations artificially slow"""
        if self.dry_run:
            logger.info("[DRY RUN] Would slow git operations")
            return
        
        # This would require network traffic control which is complex
        # For now, just log the intent
        logger.info("Simulating slow git operations (not implemented)")
    
    def run_chaos_test(self, duration_minutes: int = 30, 
                      event_interval: Tuple[int, int] = (30, 120)) -> Dict[str, Any]:
        """Run chaos test for specified duration"""
        logger.info(f"Starting chaos test for {duration_minutes} minutes")
        logger.info(f"Event interval: {event_interval[0]}-{event_interval[1]} seconds")
        
        if self.dry_run:
            logger.info("Running in DRY RUN mode - no actual chaos will be triggered")
        
        end_time = time.time() + (duration_minutes * 60)
        
        while time.time() < end_time:
            # Wait for next event
            wait_time = random.randint(*event_interval)
            logger.info(f"Waiting {wait_time} seconds until next event...")
            time.sleep(wait_time)
            
            if time.time() >= end_time:
                break
            
            # Select and trigger an event
            eligible_events = [e for e in self.events if random.random() < e.probability]
            
            if eligible_events:
                event = random.choice(eligible_events)
                
                # Record pre-event state
                pre_state = self._capture_system_state()
                
                # Trigger event
                success = event.trigger()
                
                if success:
                    self.results['events_triggered'].append({
                        'name': event.name,
                        'timestamp': datetime.now().isoformat(),
                        'severity': event.severity
                    })
                    
                    # Monitor recovery
                    recovery_time = self._monitor_recovery(event.name, pre_state)
                    if recovery_time:
                        self.results['recovery_times'][event.name] = recovery_time
                else:
                    self.results['failures'].append({
                        'event': event.name,
                        'timestamp': datetime.now().isoformat()
                    })
        
        self.results['end_time'] = datetime.now().isoformat()
        return self.results
    
    def _capture_system_state(self) -> Dict[str, Any]:
        """Capture current system state"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'tmux_sessions': [],
            'processes': []
        }
        
        # Capture tmux state
        result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            state['tmux_sessions'] = result.stdout.strip().split('\n')
        
        # Capture process count
        import psutil
        state['process_count'] = len(psutil.pids())
        
        return state
    
    def _monitor_recovery(self, event_name: str, pre_state: Dict[str, Any], 
                         timeout: int = 300) -> Optional[float]:
        """Monitor system recovery after chaos event"""
        start_time = time.time()
        logger.info(f"Monitoring recovery from {event_name}")
        
        while time.time() - start_time < timeout:
            current_state = self._capture_system_state()
            
            # Check if system has recovered
            # This is simplified - real recovery detection would be more complex
            if len(current_state['tmux_sessions']) >= len(pre_state['tmux_sessions']):
                recovery_time = time.time() - start_time
                logger.info(f"System recovered from {event_name} in {recovery_time:.1f} seconds")
                return recovery_time
            
            time.sleep(5)
        
        logger.warning(f"System did not recover from {event_name} within timeout")
        return None
    
    def generate_report(self) -> str:
        """Generate chaos test report"""
        lines = []
        lines.append("Chaos Test Report")
        lines.append("=" * 60)
        lines.append(f"Start: {self.results['start_time']}")
        lines.append(f"End: {self.results.get('end_time', 'In progress')}")
        lines.append("")
        
        # Events summary
        lines.append(f"Events Triggered: {len(self.results['events_triggered'])}")
        
        # Group by severity
        by_severity = {}
        for event in self.results['events_triggered']:
            sev = event['severity']
            by_severity[sev] = by_severity.get(sev, 0) + 1
        
        for sev in ['low', 'medium', 'high']:
            if sev in by_severity:
                lines.append(f"  {sev.capitalize()}: {by_severity[sev]}")
        
        lines.append("")
        
        # Recovery times
        if self.results['recovery_times']:
            lines.append("Recovery Times:")
            for event, time_sec in self.results['recovery_times'].items():
                lines.append(f"  {event}: {time_sec:.1f}s")
            
            avg_recovery = sum(self.results['recovery_times'].values()) / len(self.results['recovery_times'])
            lines.append(f"\nAverage Recovery: {avg_recovery:.1f}s")
        
        # Failures
        if self.results['failures']:
            lines.append("\nFailed Events:")
            for failure in self.results['failures']:
                lines.append(f"  {failure['event']} at {failure['timestamp']}")
        
        # Event details
        lines.append("\nEvent Timeline:")
        for event in self.results['events_triggered'][-10:]:  # Last 10 events
            lines.append(f"  {event['timestamp']}: {event['name']} ({event['severity']})")
        
        return "\n".join(lines)


def main():
    """CLI interface for chaos testing"""
    parser = argparse.ArgumentParser(description='Chaos testing for Tmux Orchestrator')
    parser.add_argument('--duration', type=int, default=30, 
                       help='Test duration in minutes')
    parser.add_argument('--min-interval', type=int, default=30,
                       help='Minimum seconds between events')
    parser.add_argument('--max-interval', type=int, default=120,
                       help='Maximum seconds between events')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simulate chaos without actually triggering events')
    parser.add_argument('--severity', choices=['low', 'medium', 'high', 'all'],
                       default='all', help='Limit chaos events by severity')
    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON')
    
    args = parser.parse_args()
    
    # Safety check
    if not args.dry_run:
        print("\n⚠️  WARNING: Chaos testing will disrupt running orchestrations!")
        print("This may kill processes, corrupt files, and cause data loss.")
        response = input("\nAre you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Chaos test cancelled.")
            return
    
    tester = ChaosTester(dry_run=args.dry_run)
    
    # Filter events by severity if requested
    if args.severity != 'all':
        tester.events = [e for e in tester.events if e.severity == args.severity]
    
    # Run chaos test
    try:
        results = tester.run_chaos_test(
            duration_minutes=args.duration,
            event_interval=(args.min_interval, args.max_interval)
        )
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print("\n" + tester.generate_report())
            
    except KeyboardInterrupt:
        logger.info("Chaos test interrupted by user")
        if not args.json:
            print("\n" + tester.generate_report())


if __name__ == "__main__":
    main()
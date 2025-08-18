#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psutil",
# ]
# ///
"""
Load Testing for Tmux Orchestrator
Tests system capacity for concurrent orchestrations
"""

import os
import sys
import time
import json
import subprocess
import threading
import queue
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import argparse
import psutil
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OrchestrationLoad:
    """Represents a single orchestration load"""
    def __init__(self, project_id: int, project_path: Path, spec_path: Path):
        self.project_id = project_id
        self.project_path = project_path
        self.spec_path = spec_path
        self.session_name = f"load-test-{project_id}"
        self.start_time = None
        self.end_time = None
        self.status = 'pending'
        self.metrics = {}
        self.error = None


class LoadTester:
    def __init__(self, orchestrator_path: Path = None):
        self.orchestrator_path = orchestrator_path or Path.cwd()
        self.test_projects_dir = self.orchestrator_path / 'load_test_projects'
        self.loads: List[OrchestrationLoad] = []
        self.results = {
            'start_time': None,
            'end_time': None,
            'max_concurrent': 0,
            'successful_orchestrations': 0,
            'failed_orchestrations': 0,
            'resource_metrics': [],
            'performance_metrics': {}
        }
        self.resource_monitor_thread = None
        self.stop_monitoring = threading.Event()
        
    def setup_test_environment(self):
        """Setup test environment"""
        # Create test projects directory
        if self.test_projects_dir.exists():
            shutil.rmtree(self.test_projects_dir)
        self.test_projects_dir.mkdir(parents=True)
        
        logger.info(f"Created test environment at {self.test_projects_dir}")
    
    def create_test_project(self, project_id: int, project_type: str = 'web_app') -> Tuple[Path, Path]:
        """Create a test project for load testing"""
        project_dir = self.test_projects_dir / f"project_{project_id}"
        project_dir.mkdir()
        
        # Initialize git
        subprocess.run(['git', 'init'], cwd=project_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], 
                      cwd=project_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Load Test'], 
                      cwd=project_dir, capture_output=True)
        
        # Create project files based on type
        if project_type == 'web_app':
            (project_dir / 'package.json').write_text(json.dumps({
                'name': f'load-test-{project_id}',
                'version': '1.0.0',
                'scripts': {
                    'dev': 'node server.js',
                    'test': 'jest'
                }
            }))
            (project_dir / 'server.js').write_text('console.log("Load test server");')
            (project_dir / 'README.md').write_text(f'# Load Test Project {project_id}')
            
        elif project_type == 'system_deployment':
            (project_dir / 'deployment_spec.md').write_text(f'# Deployment {project_id}')
            (project_dir / 'app.service').write_text('[Unit]\nDescription=Load Test')
            (project_dir / 'ansible').mkdir()
            
        # Commit files
        subprocess.run(['git', 'add', '.'], cwd=project_dir, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], 
                      cwd=project_dir, capture_output=True)
        
        # Create spec file
        spec_file = project_dir / 'spec.md'
        spec_file.write_text(f"""
# Load Test Project {project_id}

## Overview
Automated load test project

## Requirements
- Feature A
- Feature B
- Feature C

## Success Criteria
- All tests pass
- Performance acceptable
- No crashes
""")
        
        return project_dir, spec_file
    
    def start_resource_monitoring(self):
        """Start monitoring system resources"""
        self.stop_monitoring.clear()
        
        def monitor():
            while not self.stop_monitoring.is_set():
                metrics = {
                    'timestamp': datetime.now().isoformat(),
                    'cpu_percent': psutil.cpu_percent(interval=1),
                    'memory_percent': psutil.virtual_memory().percent,
                    'memory_available_gb': psutil.virtual_memory().available / (1024**3),
                    'swap_percent': psutil.swap_memory().percent,
                    'disk_usage_percent': psutil.disk_usage('/').percent,
                    'process_count': len(psutil.pids()),
                    'tmux_session_count': self._count_tmux_sessions()
                }
                
                self.results['resource_metrics'].append(metrics)
                time.sleep(5)  # Monitor every 5 seconds
        
        self.resource_monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.resource_monitor_thread.start()
    
    def stop_resource_monitoring(self):
        """Stop resource monitoring"""
        self.stop_monitoring.set()
        if self.resource_monitor_thread:
            self.resource_monitor_thread.join(timeout=10)
    
    def _count_tmux_sessions(self) -> int:
        """Count active tmux sessions"""
        try:
            result = subprocess.run(['tmux', 'list-sessions'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return len(result.stdout.strip().split('\n'))
        except:
            pass
        return 0
    
    def launch_orchestration(self, load: OrchestrationLoad) -> bool:
        """Launch a single orchestration"""
        try:
            load.start_time = datetime.now()
            load.status = 'launching'
            
            # Run auto_orchestrate.py
            cmd = [
                str(self.orchestrator_path / 'auto_orchestrate.py'),
                '--project', str(load.project_path),
                '--spec', str(load.spec_path),
                '--force',
                '--plan', 'pro',  # Use minimal team size
                '--size', 'small'
            ]
            
            logger.info(f"Launching orchestration {load.project_id}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                load.status = 'running'
                logger.info(f"Successfully launched orchestration {load.project_id}")
                return True
            else:
                load.status = 'failed'
                load.error = result.stderr
                logger.error(f"Failed to launch orchestration {load.project_id}: {result.stderr}")
                return False
                
        except Exception as e:
            load.status = 'failed'
            load.error = str(e)
            logger.error(f"Exception launching orchestration {load.project_id}: {e}")
            return False
    
    def verify_orchestration(self, load: OrchestrationLoad) -> bool:
        """Verify an orchestration is running properly"""
        try:
            # Check if tmux session exists
            result = subprocess.run(
                ['tmux', 'has-session', '-t', f"{load.project_path.name}-impl"],
                capture_output=True
            )
            
            if result.returncode == 0:
                # Check if windows exist
                result = subprocess.run(
                    ['tmux', 'list-windows', '-t', f"{load.project_path.name}-impl"],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    window_count = len(result.stdout.strip().split('\n'))
                    load.metrics['window_count'] = window_count
                    return window_count >= 3  # At least orchestrator, dev, tester
                    
        except Exception as e:
            logger.error(f"Error verifying orchestration {load.project_id}: {e}")
            
        return False
    
    def cleanup_orchestration(self, load: OrchestrationLoad):
        """Clean up an orchestration"""
        try:
            # Kill tmux session
            session_name = f"{load.project_path.name}-impl"
            subprocess.run(['tmux', 'kill-session', '-t', session_name], 
                         capture_output=True)
            
            load.end_time = datetime.now()
            load.status = 'completed'
            
            # Calculate duration
            if load.start_time:
                duration = (load.end_time - load.start_time).total_seconds()
                load.metrics['duration_seconds'] = duration
                
        except Exception as e:
            logger.error(f"Error cleaning up orchestration {load.project_id}: {e}")
    
    def run_concurrent_test(self, num_orchestrations: int, 
                          launch_interval: float = 5.0,
                          hold_duration: int = 300) -> Dict[str, Any]:
        """Run concurrent orchestration test"""
        logger.info(f"Starting load test with {num_orchestrations} orchestrations")
        logger.info(f"Launch interval: {launch_interval}s, Hold duration: {hold_duration}s")
        
        self.results['start_time'] = datetime.now().isoformat()
        
        # Setup test environment
        self.setup_test_environment()
        
        # Start resource monitoring
        self.start_resource_monitoring()
        
        # Create test projects
        logger.info("Creating test projects...")
        for i in range(num_orchestrations):
            project_type = 'web_app' if i % 2 == 0 else 'system_deployment'
            project_dir, spec_file = self.create_test_project(i, project_type)
            load = OrchestrationLoad(i, project_dir, spec_file)
            self.loads.append(load)
        
        # Launch orchestrations with interval
        logger.info("Launching orchestrations...")
        launch_start = time.time()
        concurrent_count = 0
        
        for load in self.loads:
            if self.launch_orchestration(load):
                self.results['successful_orchestrations'] += 1
                concurrent_count += 1
                self.results['max_concurrent'] = max(self.results['max_concurrent'], 
                                                   concurrent_count)
            else:
                self.results['failed_orchestrations'] += 1
            
            # Wait before next launch
            if load != self.loads[-1]:  # Not the last one
                time.sleep(launch_interval)
        
        launch_duration = time.time() - launch_start
        self.results['performance_metrics']['launch_duration'] = launch_duration
        self.results['performance_metrics']['avg_launch_time'] = launch_duration / num_orchestrations
        
        # Verify all orchestrations
        logger.info("Verifying orchestrations...")
        verified_count = 0
        for load in self.loads:
            if load.status == 'running' and self.verify_orchestration(load):
                verified_count += 1
        
        self.results['performance_metrics']['verified_count'] = verified_count
        logger.info(f"Verified {verified_count}/{num_orchestrations} orchestrations")
        
        # Hold for specified duration
        logger.info(f"Holding for {hold_duration} seconds...")
        time.sleep(hold_duration)
        
        # Measure peak resource usage
        if self.results['resource_metrics']:
            peak_cpu = max(m['cpu_percent'] for m in self.results['resource_metrics'])
            peak_memory = max(m['memory_percent'] for m in self.results['resource_metrics'])
            self.results['performance_metrics']['peak_cpu_percent'] = peak_cpu
            self.results['performance_metrics']['peak_memory_percent'] = peak_memory
        
        # Cleanup orchestrations
        logger.info("Cleaning up orchestrations...")
        cleanup_start = time.time()
        
        for load in self.loads:
            self.cleanup_orchestration(load)
        
        cleanup_duration = time.time() - cleanup_start
        self.results['performance_metrics']['cleanup_duration'] = cleanup_duration
        
        # Stop resource monitoring
        self.stop_resource_monitoring()
        
        # Cleanup test environment
        if self.test_projects_dir.exists():
            shutil.rmtree(self.test_projects_dir)
        
        self.results['end_time'] = datetime.now().isoformat()
        
        return self.results
    
    def run_ramp_test(self, max_orchestrations: int = 20,
                     ramp_duration: int = 600,
                     hold_duration: int = 300) -> Dict[str, Any]:
        """Run ramp-up load test"""
        logger.info(f"Starting ramp test to {max_orchestrations} orchestrations")
        
        self.results['start_time'] = datetime.now().isoformat()
        self.results['test_type'] = 'ramp'
        
        # Setup and start monitoring
        self.setup_test_environment()
        self.start_resource_monitoring()
        
        # Calculate launch interval
        launch_interval = ramp_duration / max_orchestrations
        
        # Run concurrent test with calculated interval
        return self.run_concurrent_test(
            max_orchestrations, 
            launch_interval=launch_interval,
            hold_duration=hold_duration
        )
    
    def generate_report(self) -> str:
        """Generate load test report"""
        lines = []
        lines.append("Load Test Report")
        lines.append("=" * 60)
        lines.append(f"Start: {self.results['start_time']}")
        lines.append(f"End: {self.results.get('end_time', 'In progress')}")
        lines.append("")
        
        # Summary
        lines.append("Summary:")
        lines.append(f"  Total orchestrations: {len(self.loads)}")
        lines.append(f"  Successful launches: {self.results['successful_orchestrations']}")
        lines.append(f"  Failed launches: {self.results['failed_orchestrations']}")
        lines.append(f"  Max concurrent: {self.results['max_concurrent']}")
        
        if 'performance_metrics' in self.results:
            perf = self.results['performance_metrics']
            lines.append("")
            lines.append("Performance Metrics:")
            
            if 'launch_duration' in perf:
                lines.append(f"  Total launch time: {perf['launch_duration']:.1f}s")
                lines.append(f"  Avg launch time: {perf['avg_launch_time']:.1f}s per orchestration")
            
            if 'verified_count' in perf:
                lines.append(f"  Verified running: {perf['verified_count']}")
            
            if 'cleanup_duration' in perf:
                lines.append(f"  Cleanup time: {perf['cleanup_duration']:.1f}s")
            
            if 'peak_cpu_percent' in perf:
                lines.append(f"  Peak CPU: {perf['peak_cpu_percent']:.1f}%")
                lines.append(f"  Peak Memory: {perf['peak_memory_percent']:.1f}%")
        
        # Resource usage over time
        if self.results['resource_metrics']:
            lines.append("")
            lines.append("Resource Usage Timeline (last 10 samples):")
            
            for metric in self.results['resource_metrics'][-10:]:
                lines.append(f"  {metric['timestamp']}: "
                           f"CPU={metric['cpu_percent']:.1f}%, "
                           f"Mem={metric['memory_percent']:.1f}%, "
                           f"Sessions={metric['tmux_session_count']}")
        
        # Failed orchestrations
        failed_loads = [l for l in self.loads if l.status == 'failed']
        if failed_loads:
            lines.append("")
            lines.append("Failed Orchestrations:")
            for load in failed_loads[:5]:  # First 5
                lines.append(f"  Project {load.project_id}: {load.error}")
        
        # Recommendations
        lines.append("")
        lines.append("Recommendations:")
        
        if self.results.get('performance_metrics', {}).get('peak_cpu_percent', 0) > 80:
            lines.append("  ⚠️  High CPU usage detected - consider reducing concurrent orchestrations")
        
        if self.results.get('performance_metrics', {}).get('peak_memory_percent', 0) > 85:
            lines.append("  ⚠️  High memory usage detected - system may be at capacity")
        
        if self.results['failed_orchestrations'] > 0:
            failure_rate = self.results['failed_orchestrations'] / len(self.loads) * 100
            lines.append(f"  ⚠️  {failure_rate:.1f}% failure rate - investigate causes")
        
        success_rate = self.results['successful_orchestrations'] / len(self.loads) * 100
        lines.append(f"\n✅ Overall success rate: {success_rate:.1f}%")
        lines.append(f"✅ System handled up to {self.results['max_concurrent']} concurrent orchestrations")
        
        return "\n".join(lines)


def main():
    """CLI interface for load testing"""
    parser = argparse.ArgumentParser(description='Load testing for Tmux Orchestrator')
    
    subparsers = parser.add_subparsers(dest='mode', help='Test mode')
    
    # Concurrent test
    concurrent = subparsers.add_parser('concurrent', help='Run concurrent orchestrations')
    concurrent.add_argument('--count', type=int, default=5, 
                          help='Number of orchestrations')
    concurrent.add_argument('--interval', type=float, default=5.0,
                          help='Seconds between launches')
    concurrent.add_argument('--hold', type=int, default=300,
                          help='Seconds to hold orchestrations')
    
    # Ramp test
    ramp = subparsers.add_parser('ramp', help='Ramp up orchestrations gradually')
    ramp.add_argument('--max', type=int, default=10,
                     help='Maximum orchestrations')
    ramp.add_argument('--duration', type=int, default=600,
                     help='Ramp duration in seconds')
    ramp.add_argument('--hold', type=int, default=300,
                     help='Seconds to hold at peak')
    
    parser.add_argument('--json', action='store_true', help='Output JSON format')
    
    args = parser.parse_args()
    
    if not args.mode:
        parser.print_help()
        return
    
    # Safety warning
    print("\n⚠️  WARNING: Load testing will create multiple orchestrations!")
    print("This will consume significant system resources.")
    response = input("\nContinue? (yes/no): ")
    if response.lower() != 'yes':
        print("Load test cancelled.")
        return
    
    tester = LoadTester()
    
    try:
        if args.mode == 'concurrent':
            results = tester.run_concurrent_test(
                num_orchestrations=args.count,
                launch_interval=args.interval,
                hold_duration=args.hold
            )
        elif args.mode == 'ramp':
            results = tester.run_ramp_test(
                max_orchestrations=args.max,
                ramp_duration=args.duration,
                hold_duration=args.hold
            )
        
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print("\n" + tester.generate_report())
            
    except KeyboardInterrupt:
        logger.info("Load test interrupted by user")
        tester.stop_resource_monitoring()
        
        # Cleanup any running sessions
        for load in tester.loads:
            if load.status == 'running':
                tester.cleanup_orchestration(load)
        
        if not args.json:
            print("\n" + tester.generate_report())


if __name__ == "__main__":
    main()
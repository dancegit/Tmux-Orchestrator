#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psutil",
# ]
# ///
"""
Performance Tuning Module for Tmux Orchestrator
Analyzes and optimizes system performance for orchestration operations
"""

import os
import sys
import time
import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timedelta

# Set UV_NO_WORKSPACE environment variable for all subprocess calls
os.environ['UV_NO_WORKSPACE'] = '1'
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


class PerformanceTuner:
    def __init__(self, orchestrator_path: Path = None):
        self.orchestrator_path = orchestrator_path or Path.cwd()
        self.metrics = {}
        self.recommendations = []
        
    def measure_system_resources(self) -> Dict[str, Any]:
        """Measure current system resource usage"""
        metrics = {
            'cpu': {
                'count': psutil.cpu_count(),
                'percent': psutil.cpu_percent(interval=1),
                'load_avg': os.getloadavg(),
                'per_cpu': psutil.cpu_percent(interval=1, percpu=True)
            },
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent,
                'swap_percent': psutil.swap_memory().percent
            },
            'disk': {
                'usage': psutil.disk_usage('/').percent,
                'io_counters': psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {}
            },
            'processes': {
                'total': len(psutil.pids()),
                'tmux_sessions': self.count_tmux_sessions(),
                'python_processes': len([p for p in psutil.process_iter(['name']) if 'python' in p.info['name']])
            }
        }
        
        return metrics
    
    def count_tmux_sessions(self) -> int:
        """Count active tmux sessions"""
        try:
            result = subprocess.run(
                ['tmux', 'list-sessions'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return len(result.stdout.strip().split('\n'))
        except:
            pass
        return 0
    
    def benchmark_operations(self) -> Dict[str, float]:
        """Benchmark key orchestrator operations"""
        benchmarks = {}
        
        # Benchmark tmux operations
        start = time.time()
        for _ in range(10):
            subprocess.run(['tmux', 'list-sessions'], capture_output=True)
        benchmarks['tmux_list_sessions'] = (time.time() - start) / 10
        
        # Benchmark git operations
        if (self.orchestrator_path / '.git').exists():
            start = time.time()
            subprocess.run(['git', 'status'], cwd=self.orchestrator_path, capture_output=True)
            benchmarks['git_status'] = time.time() - start
            
            start = time.time()
            subprocess.run(['git', 'log', '--oneline', '-10'], cwd=self.orchestrator_path, capture_output=True)
            benchmarks['git_log'] = time.time() - start
        
        # Benchmark file operations
        test_file = self.orchestrator_path / '.perf_test'
        start = time.time()
        for i in range(100):
            test_file.write_text(f"test {i}")
        benchmarks['file_write_100'] = time.time() - start
        test_file.unlink()
        
        # Benchmark SQLite operations (for scheduler)
        import sqlite3
        db_path = ':memory:'
        start = time.time()
        conn = sqlite3.connect(db_path)
        conn.execute('CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)')
        for i in range(1000):
            conn.execute('INSERT INTO test (data) VALUES (?)', (f'data{i}',))
        conn.commit()
        conn.close()
        benchmarks['sqlite_insert_1000'] = time.time() - start
        
        return benchmarks
    
    def analyze_git_performance(self) -> Dict[str, Any]:
        """Analyze git repository performance"""
        git_metrics = {}
        
        # Check for large files
        try:
            result = subprocess.run(
                ['git', 'ls-files', '-z'],
                cwd=self.orchestrator_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                files = result.stdout.strip().split('\0')
                git_metrics['total_files'] = len(files)
                
                # Find large files
                large_files = []
                for file in files[:1000]:  # Limit to prevent hanging
                    if file:
                        file_path = self.orchestrator_path / file
                        if file_path.exists():
                            size = file_path.stat().st_size
                            if size > 1024 * 1024:  # > 1MB
                                large_files.append((file, size))
                
                git_metrics['large_files'] = sorted(large_files, key=lambda x: x[1], reverse=True)[:10]
        except:
            pass
        
        # Check worktree count
        try:
            result = subprocess.run(
                ['git', 'worktree', 'list'],
                cwd=self.orchestrator_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                git_metrics['worktree_count'] = len(result.stdout.strip().split('\n'))
        except:
            pass
        
        return git_metrics
    
    def generate_recommendations(self, metrics: Dict[str, Any], benchmarks: Dict[str, float]) -> List[Dict[str, str]]:
        """Generate performance recommendations based on metrics"""
        recommendations = []
        
        # CPU recommendations
        if metrics['cpu']['percent'] > 80:
            recommendations.append({
                'category': 'CPU',
                'severity': 'high',
                'issue': f"High CPU usage: {metrics['cpu']['percent']:.1f}%",
                'recommendation': "Consider reducing concurrent agent count or adding CPU resources"
            })
        
        # Memory recommendations
        if metrics['memory']['percent'] > 85:
            recommendations.append({
                'category': 'Memory',
                'severity': 'high',
                'issue': f"High memory usage: {metrics['memory']['percent']:.1f}%",
                'recommendation': "Reduce agent count or increase system memory"
            })
        
        if metrics['memory']['swap_percent'] > 20:
            recommendations.append({
                'category': 'Memory',
                'severity': 'medium',
                'issue': f"Swap usage: {metrics['memory']['swap_percent']:.1f}%",
                'recommendation': "System is swapping - performance will be degraded"
            })
        
        # Disk recommendations
        if metrics['disk']['usage'] > 90:
            recommendations.append({
                'category': 'Disk',
                'severity': 'high',
                'issue': f"Low disk space: {metrics['disk']['usage']:.1f}% used",
                'recommendation': "Clean up old logs and worktrees"
            })
        
        # Process recommendations
        if metrics['processes']['tmux_sessions'] > 10:
            recommendations.append({
                'category': 'Processes',
                'severity': 'medium',
                'issue': f"Many tmux sessions: {metrics['processes']['tmux_sessions']}",
                'recommendation': "Consider cleaning up old orchestration sessions"
            })
        
        # Benchmark-based recommendations
        if benchmarks.get('tmux_list_sessions', 0) > 0.1:
            recommendations.append({
                'category': 'Performance',
                'severity': 'low',
                'issue': f"Slow tmux operations: {benchmarks['tmux_list_sessions']*1000:.1f}ms",
                'recommendation': "Tmux operations are slow - check system load"
            })
        
        if benchmarks.get('git_status', 0) > 0.5:
            recommendations.append({
                'category': 'Git',
                'severity': 'medium',
                'issue': f"Slow git status: {benchmarks['git_status']:.2f}s",
                'recommendation': "Consider git gc or reducing repository size"
            })
        
        return recommendations
    
    def optimize_scheduler_database(self) -> Dict[str, Any]:
        """Optimize scheduler SQLite database"""
        results = {}
        db_path = self.orchestrator_path / 'task_queue.db'
        
        if db_path.exists():
            import sqlite3
            
            conn = sqlite3.connect(str(db_path))
            
            # Get database stats
            cursor = conn.execute("SELECT COUNT(*) FROM tasks")
            task_count = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE executed = 0 AND scheduled_time < ?", 
                                (datetime.now().isoformat(),))
            overdue_count = cursor.fetchone()[0]
            
            results['task_count'] = task_count
            results['overdue_count'] = overdue_count
            
            # Clean old executed tasks
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor = conn.execute("DELETE FROM tasks WHERE executed = 1 AND scheduled_time < ?", (week_ago,))
            results['cleaned_tasks'] = cursor.rowcount
            
            # Vacuum database
            conn.execute("VACUUM")
            
            # Analyze for query optimization
            conn.execute("ANALYZE")
            
            conn.commit()
            conn.close()
            
            results['status'] = 'optimized'
        else:
            results['status'] = 'no_database'
        
        return results
    
    def clean_old_logs(self, days: int = 7) -> Dict[str, int]:
        """Clean old log files"""
        cleaned = {
            'log_files': 0,
            'registry_files': 0,
            'total_size': 0
        }
        
        # Clean old logs
        log_patterns = [
            'sync_coordinator.log*',
            'scheduler.log*',
            'logs/*.log'
        ]
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for pattern in log_patterns:
            for log_file in self.orchestrator_path.glob(pattern):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    size = log_file.stat().st_size
                    log_file.unlink()
                    cleaned['log_files'] += 1
                    cleaned['total_size'] += size
        
        # Clean old registry files
        registry_path = self.orchestrator_path / 'registry'
        if registry_path.exists():
            for session_file in registry_path.glob('**/*session*.json'):
                if session_file.stat().st_mtime < cutoff_date.timestamp():
                    size = session_file.stat().st_size
                    session_file.unlink()
                    cleaned['registry_files'] += 1
                    cleaned['total_size'] += size
        
        return cleaned
    
    def tune_system(self, clean_logs: bool = False, optimize_db: bool = True) -> Dict[str, Any]:
        """Run full system performance tuning"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'metrics': {},
            'benchmarks': {},
            'recommendations': [],
            'optimizations': {}
        }
        
        # Measure system resources
        logger.info("Measuring system resources...")
        results['metrics'] = self.measure_system_resources()
        
        # Run benchmarks
        logger.info("Running performance benchmarks...")
        results['benchmarks'] = self.benchmark_operations()
        
        # Analyze git performance
        logger.info("Analyzing git performance...")
        results['metrics']['git'] = self.analyze_git_performance()
        
        # Generate recommendations
        results['recommendations'] = self.generate_recommendations(
            results['metrics'], 
            results['benchmarks']
        )
        
        # Perform optimizations
        if optimize_db:
            logger.info("Optimizing scheduler database...")
            results['optimizations']['database'] = self.optimize_scheduler_database()
        
        if clean_logs:
            logger.info("Cleaning old logs...")
            results['optimizations']['logs'] = self.clean_old_logs()
        
        return results
    
    def format_report(self, results: Dict[str, Any]) -> str:
        """Format performance report for display"""
        lines = []
        lines.append("Tmux Orchestrator Performance Report")
        lines.append("=" * 60)
        lines.append(f"Generated: {results['timestamp']}")
        lines.append("")
        
        # System metrics
        lines.append("System Resources:")
        lines.append(f"  CPU: {results['metrics']['cpu']['percent']:.1f}% (Load: {results['metrics']['cpu']['load_avg']})")
        lines.append(f"  Memory: {results['metrics']['memory']['percent']:.1f}% used ({results['metrics']['memory']['available'] / (1024**3):.1f}GB available)")
        lines.append(f"  Disk: {results['metrics']['disk']['usage']:.1f}% used")
        lines.append(f"  Processes: {results['metrics']['processes']['total']} total, {results['metrics']['processes']['tmux_sessions']} tmux sessions")
        lines.append("")
        
        # Benchmarks
        lines.append("Performance Benchmarks:")
        for op, time_sec in results['benchmarks'].items():
            lines.append(f"  {op}: {time_sec*1000:.1f}ms")
        lines.append("")
        
        # Git metrics
        if 'git' in results['metrics']:
            git = results['metrics']['git']
            lines.append("Git Repository:")
            lines.append(f"  Total files: {git.get('total_files', 'unknown')}")
            lines.append(f"  Worktrees: {git.get('worktree_count', 'unknown')}")
            if git.get('large_files'):
                lines.append("  Large files:")
                for file, size in git['large_files'][:5]:
                    lines.append(f"    {file}: {size / (1024*1024):.1f}MB")
            lines.append("")
        
        # Recommendations
        if results['recommendations']:
            lines.append("Recommendations:")
            for rec in sorted(results['recommendations'], key=lambda x: {'high': 0, 'medium': 1, 'low': 2}[x['severity']]):
                lines.append(f"  [{rec['severity'].upper()}] {rec['category']}: {rec['issue']}")
                lines.append(f"    → {rec['recommendation']}")
            lines.append("")
        else:
            lines.append("✅ No performance issues detected")
            lines.append("")
        
        # Optimizations performed
        if results['optimizations']:
            lines.append("Optimizations Performed:")
            if 'database' in results['optimizations']:
                db = results['optimizations']['database']
                if db.get('status') == 'optimized':
                    lines.append(f"  Database: Cleaned {db.get('cleaned_tasks', 0)} old tasks")
            if 'logs' in results['optimizations']:
                logs = results['optimizations']['logs']
                lines.append(f"  Logs: Removed {logs['log_files']} files ({logs['total_size'] / (1024*1024):.1f}MB)")
        
        return "\n".join(lines)


def main():
    """CLI interface for performance tuning"""
    parser = argparse.ArgumentParser(description='Performance tuning for Tmux Orchestrator')
    parser.add_argument('--clean-logs', action='store_true', help='Clean old log files')
    parser.add_argument('--no-optimize-db', action='store_true', help='Skip database optimization')
    parser.add_argument('--json', action='store_true', help='Output JSON format')
    parser.add_argument('--watch', action='store_true', help='Continuous monitoring mode')
    parser.add_argument('--interval', type=int, default=60, help='Watch interval in seconds')
    
    args = parser.parse_args()
    
    tuner = PerformanceTuner()
    
    if args.watch:
        try:
            while True:
                os.system('clear')
                results = tuner.tune_system(
                    clean_logs=False,  # Don't clean in watch mode
                    optimize_db=False  # Don't optimize in watch mode
                )
                
                if args.json:
                    print(json.dumps(results, indent=2))
                else:
                    print(tuner.format_report(results))
                
                print(f"\nRefreshing in {args.interval} seconds... (Ctrl+C to exit)")
                time.sleep(args.interval)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
    else:
        # Single run
        results = tuner.tune_system(
            clean_logs=args.clean_logs,
            optimize_db=not args.no_optimize_db
        )
        
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print(tuner.format_report(results))


if __name__ == "__main__":
    main()
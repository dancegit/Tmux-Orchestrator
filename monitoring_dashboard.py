#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "flask",
#     "psutil",
#     "pyyaml",
# ]
# ///
"""
Monitoring Dashboard for Tmux Orchestrator
Real-time web dashboard for monitoring orchestration metrics
"""

import os
import sys
import json
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import argparse
import psutil
import yaml
from flask import Flask, render_template_string, jsonify
import threading
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# HTML template for the dashboard
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Tmux Orchestrator Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .card h2 {
            margin-top: 0;
            color: #444;
            font-size: 18px;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .metric:last-child {
            border-bottom: none;
        }
        .metric-label {
            color: #666;
        }
        .metric-value {
            font-weight: 600;
            color: #333;
        }
        .status-active {
            color: #28a745;
        }
        .status-failed {
            color: #dc3545;
        }
        .status-warning {
            color: #ffc107;
        }
        .status-exhausted {
            color: #6c757d;
        }
        .progress-bar {
            background: #e0e0e0;
            border-radius: 4px;
            height: 8px;
            overflow: hidden;
            margin-top: 4px;
        }
        .progress-fill {
            height: 100%;
            transition: width 0.3s ease;
        }
        .progress-cpu { background: #2196F3; }
        .progress-memory { background: #4CAF50; }
        .progress-disk { background: #FF9800; }
        .progress-danger { background: #f44336; }
        .orchestration-item {
            padding: 12px;
            margin: 8px 0;
            background: #f8f9fa;
            border-radius: 4px;
            border-left: 4px solid #007bff;
        }
        .orchestration-failed {
            border-left-color: #dc3545;
        }
        .orchestration-title {
            font-weight: 600;
            margin-bottom: 4px;
        }
        .orchestration-details {
            font-size: 14px;
            color: #666;
        }
        .agent-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        .agent-box {
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
            text-align: center;
            border: 2px solid #dee2e6;
        }
        .agent-active {
            border-color: #28a745;
            background: #d4edda;
        }
        .agent-exhausted {
            border-color: #dc3545;
            background: #f8d7da;
        }
        .refresh-info {
            text-align: center;
            color: #666;
            margin-top: 20px;
            font-size: 14px;
        }
        .error-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .error-item {
            padding: 8px;
            margin: 4px 0;
            background: #fff3cd;
            border-radius: 4px;
            font-size: 14px;
        }
        .timestamp {
            color: #999;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 Tmux Orchestrator Dashboard</h1>
        
        <div class="grid">
            <!-- System Resources -->
            <div class="card">
                <h2>System Resources</h2>
                <div class="metric">
                    <span class="metric-label">CPU Usage</span>
                    <span class="metric-value" id="cpu-percent">--%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill progress-cpu" id="cpu-bar" style="width: 0%"></div>
                </div>
                
                <div class="metric" style="margin-top: 10px;">
                    <span class="metric-label">Memory Usage</span>
                    <span class="metric-value" id="memory-percent">--%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill progress-memory" id="memory-bar" style="width: 0%"></div>
                </div>
                
                <div class="metric" style="margin-top: 10px;">
                    <span class="metric-label">Disk Usage</span>
                    <span class="metric-value" id="disk-percent">--%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill progress-disk" id="disk-bar" style="width: 0%"></div>
                </div>
                
                <div class="metric" style="margin-top: 15px;">
                    <span class="metric-label">Load Average</span>
                    <span class="metric-value" id="load-avg">0.0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Processes</span>
                    <span class="metric-value" id="process-count">0</span>
                </div>
            </div>
            
            <!-- Orchestration Status -->
            <div class="card">
                <h2>Active Orchestrations</h2>
                <div class="metric">
                    <span class="metric-label">Total Sessions</span>
                    <span class="metric-value" id="session-count">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Active Projects</span>
                    <span class="metric-value status-active" id="active-projects">0</span>
                </div>
                <div id="orchestration-list"></div>
            </div>
            
            <!-- Agent Health -->
            <div class="card">
                <h2>Agent Health</h2>
                <div class="metric">
                    <span class="metric-label">Total Agents</span>
                    <span class="metric-value" id="total-agents">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Active Agents</span>
                    <span class="metric-value status-active" id="active-agents">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Exhausted Credits</span>
                    <span class="metric-value status-exhausted" id="exhausted-agents">0</span>
                </div>
                <div class="agent-grid" id="agent-grid"></div>
            </div>
            
            <!-- Performance Metrics -->
            <div class="card">
                <h2>Performance Metrics</h2>
                <div class="metric">
                    <span class="metric-label">Tmux Response Time</span>
                    <span class="metric-value" id="tmux-latency">--ms</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Git Operations</span>
                    <span class="metric-value" id="git-latency">--ms</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Scheduler Queue</span>
                    <span class="metric-value" id="queue-size">0 tasks</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Uptime</span>
                    <span class="metric-value" id="uptime">--</span>
                </div>
            </div>
            
            <!-- Recent Errors -->
            <div class="card">
                <h2>Recent Issues</h2>
                <div class="error-list" id="error-list">
                    <div style="color: #666; text-align: center; padding: 20px;">
                        No issues detected
                    </div>
                </div>
            </div>
            
            <!-- Quick Stats -->
            <div class="card">
                <h2>Statistics</h2>
                <div class="metric">
                    <span class="metric-label">Total Commits Today</span>
                    <span class="metric-value" id="commits-today">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Tests Run</span>
                    <span class="metric-value" id="tests-run">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Credit Resets</span>
                    <span class="metric-value" id="credit-resets">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Worktrees Created</span>
                    <span class="metric-value" id="worktrees-count">0</span>
                </div>
            </div>
        </div>
        
        <div class="refresh-info">
            Auto-refreshing every 5 seconds | Last update: <span id="last-update">--</span>
        </div>
    </div>
    
    <script>
        async function updateDashboard() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                
                // Update system resources
                document.getElementById('cpu-percent').textContent = data.system.cpu_percent.toFixed(1) + '%';
                document.getElementById('cpu-bar').style.width = data.system.cpu_percent + '%';
                if (data.system.cpu_percent > 80) {
                    document.getElementById('cpu-bar').className = 'progress-fill progress-danger';
                }
                
                document.getElementById('memory-percent').textContent = data.system.memory_percent.toFixed(1) + '%';
                document.getElementById('memory-bar').style.width = data.system.memory_percent + '%';
                if (data.system.memory_percent > 85) {
                    document.getElementById('memory-bar').className = 'progress-fill progress-danger';
                }
                
                document.getElementById('disk-percent').textContent = data.system.disk_percent.toFixed(1) + '%';
                document.getElementById('disk-bar').style.width = data.system.disk_percent + '%';
                if (data.system.disk_percent > 90) {
                    document.getElementById('disk-bar').className = 'progress-fill progress-danger';
                }
                
                document.getElementById('load-avg').textContent = data.system.load_avg.join(', ');
                document.getElementById('process-count').textContent = data.system.process_count;
                
                // Update orchestrations
                document.getElementById('session-count').textContent = data.orchestrations.total_sessions;
                document.getElementById('active-projects').textContent = data.orchestrations.active_projects.length;
                
                const orchList = document.getElementById('orchestration-list');
                orchList.innerHTML = '';
                data.orchestrations.active_projects.forEach(project => {
                    const item = document.createElement('div');
                    item.className = 'orchestration-item';
                    item.innerHTML = `
                        <div class="orchestration-title">${project.name}</div>
                        <div class="orchestration-details">
                            ${project.windows} windows • ${project.duration}
                        </div>
                    `;
                    orchList.appendChild(item);
                });
                
                // Update agent health
                document.getElementById('total-agents').textContent = data.agents.total;
                document.getElementById('active-agents').textContent = data.agents.active;
                document.getElementById('exhausted-agents').textContent = data.agents.exhausted;
                
                const agentGrid = document.getElementById('agent-grid');
                agentGrid.innerHTML = '';
                data.agents.details.forEach(agent => {
                    const box = document.createElement('div');
                    box.className = 'agent-box ' + (agent.status === 'active' ? 'agent-active' : 
                                                    agent.status === 'exhausted' ? 'agent-exhausted' : '');
                    box.innerHTML = `
                        <div style="font-weight: 600;">${agent.role}</div>
                        <div style="font-size: 12px; margin-top: 4px;">${agent.session}</div>
                    `;
                    agentGrid.appendChild(box);
                });
                
                // Update performance metrics
                document.getElementById('tmux-latency').textContent = data.performance.tmux_latency.toFixed(1) + 'ms';
                document.getElementById('git-latency').textContent = data.performance.git_latency.toFixed(1) + 'ms';
                document.getElementById('queue-size').textContent = data.performance.queue_size + ' tasks';
                document.getElementById('uptime').textContent = data.performance.uptime;
                
                // Update statistics
                document.getElementById('commits-today').textContent = data.statistics.commits_today;
                document.getElementById('tests-run').textContent = data.statistics.tests_run;
                document.getElementById('credit-resets').textContent = data.statistics.credit_resets;
                document.getElementById('worktrees-count').textContent = data.statistics.worktrees_count;
                
                // Update recent issues
                const errorList = document.getElementById('error-list');
                if (data.recent_issues.length > 0) {
                    errorList.innerHTML = '';
                    data.recent_issues.forEach(issue => {
                        const item = document.createElement('div');
                        item.className = 'error-item';
                        item.innerHTML = `
                            <div>${issue.message}</div>
                            <div class="timestamp">${issue.timestamp}</div>
                        `;
                        errorList.appendChild(item);
                    });
                } else {
                    errorList.innerHTML = '<div style="color: #666; text-align: center; padding: 20px;">No issues detected</div>';
                }
                
                // Update timestamp
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                
            } catch (error) {
                console.error('Failed to update dashboard:', error);
            }
        }
        
        // Update immediately and then every 5 seconds
        updateDashboard();
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
"""


class MetricsCollector:
    """Collects metrics for the dashboard"""
    
    def __init__(self, orchestrator_path: Path = None):
        self.orchestrator_path = orchestrator_path or Path.cwd()
        
    def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system resource metrics"""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_avg': os.getloadavg(),
            'process_count': len(psutil.pids()),
            'memory_available_gb': psutil.virtual_memory().available / (1024**3),
            'swap_percent': psutil.swap_memory().percent
        }
    
    def collect_orchestration_metrics(self) -> Dict[str, Any]:
        """Collect orchestration-related metrics"""
        metrics = {
            'total_sessions': 0,
            'active_projects': [],
            'window_counts': {}
        }
        
        try:
            # Get tmux sessions
            result = subprocess.run(
                ['tmux', 'list-sessions', '-F', '#{session_name}:#{session_created}'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout:
                sessions = result.stdout.strip().split('\n')
                metrics['total_sessions'] = len(sessions)
                
                for session_info in sessions:
                    if ':' in session_info:
                        session_name, created = session_info.split(':', 1)
                        
                        # Get window count for session
                        window_result = subprocess.run(
                            ['tmux', 'list-windows', '-t', session_name],
                            capture_output=True,
                            text=True
                        )
                        
                        window_count = 0
                        if window_result.returncode == 0:
                            window_count = len(window_result.stdout.strip().split('\n'))
                        
                        # Calculate duration
                        try:
                            created_time = int(created)
                            duration = datetime.now() - datetime.fromtimestamp(created_time)
                            duration_str = f"{duration.days}d {duration.seconds//3600}h" if duration.days > 0 else f"{duration.seconds//3600}h {(duration.seconds%3600)//60}m"
                        except:
                            duration_str = "unknown"
                        
                        if '-impl' in session_name:
                            metrics['active_projects'].append({
                                'name': session_name.replace('-impl', ''),
                                'session': session_name,
                                'windows': window_count,
                                'duration': duration_str
                            })
                            
        except Exception as e:
            logger.error(f"Error collecting orchestration metrics: {e}")
            
        return metrics
    
    def collect_agent_metrics(self) -> Dict[str, Any]:
        """Collect agent health metrics"""
        metrics = {
            'total': 0,
            'active': 0,
            'exhausted': 0,
            'details': []
        }
        
        # Check credit schedule file
        credit_file = Path.home() / '.claude' / 'credit_schedule.json'
        exhausted_agents = set()
        
        if credit_file.exists():
            try:
                with open(credit_file) as f:
                    credit_data = json.load(f)
                    for session, info in credit_data.get('sessions', {}).items():
                        if info.get('exhausted'):
                            exhausted_agents.add(session)
            except:
                pass
        
        # Get all claude windows
        try:
            result = subprocess.run(
                ['tmux', 'list-windows', '-a', '-F', '#{session_name}:#{window_index}:#{window_name}'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout:
                windows = result.stdout.strip().split('\n')
                
                for window in windows:
                    if ':' in window:
                        parts = window.split(':', 2)
                        if len(parts) >= 3:
                            session, index, name = parts
                            window_id = f"{session}:{index}"
                            
                            # Determine role from window name
                            role = name.lower()
                            if 'orchestrator' in role:
                                role = 'orchestrator'
                            elif 'developer' in role:
                                role = 'developer'
                            elif 'tester' in role and 'runner' not in role:
                                role = 'tester'
                            elif 'testrunner' in role or 'test-runner' in role:
                                role = 'testrunner'
                            elif 'pm' in role or 'project' in role:
                                role = 'pm'
                            elif 'sysadmin' in role:
                                role = 'sysadmin'
                            elif 'devops' in role:
                                role = 'devops'
                            else:
                                continue  # Skip non-agent windows
                            
                            metrics['total'] += 1
                            
                            status = 'exhausted' if window_id in exhausted_agents else 'active'
                            if status == 'active':
                                metrics['active'] += 1
                            else:
                                metrics['exhausted'] += 1
                            
                            metrics['details'].append({
                                'role': role,
                                'session': window_id,
                                'status': status
                            })
                            
        except Exception as e:
            logger.error(f"Error collecting agent metrics: {e}")
            
        return metrics
    
    def collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect performance metrics"""
        metrics = {
            'tmux_latency': 0.0,
            'git_latency': 0.0,
            'queue_size': 0,
            'uptime': 'unknown'
        }
        
        # Measure tmux latency
        start = time.time()
        subprocess.run(['tmux', 'list-sessions'], capture_output=True)
        metrics['tmux_latency'] = (time.time() - start) * 1000
        
        # Measure git latency
        if (self.orchestrator_path / '.git').exists():
            start = time.time()
            subprocess.run(['git', 'status'], cwd=self.orchestrator_path, capture_output=True)
            metrics['git_latency'] = (time.time() - start) * 1000
        
        # Check scheduler queue
        db_path = self.orchestrator_path / 'task_queue.db'
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE executed = 0")
                metrics['queue_size'] = cursor.fetchone()[0]
                conn.close()
            except:
                pass
        
        # Calculate uptime (from boot time)
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            metrics['uptime'] = f"{uptime.days}d {uptime.seconds//3600}h"
        except:
            pass
        
        return metrics
    
    def collect_statistics(self) -> Dict[str, Any]:
        """Collect various statistics"""
        stats = {
            'commits_today': 0,
            'tests_run': 0,
            'credit_resets': 0,
            'worktrees_count': 0
        }
        
        # Count today's commits
        try:
            result = subprocess.run(
                ['git', 'log', '--since=midnight', '--oneline'],
                cwd=self.orchestrator_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout:
                stats['commits_today'] = len(result.stdout.strip().split('\n'))
        except:
            pass
        
        # Count worktrees
        registry_path = self.orchestrator_path / 'registry' / 'projects'
        if registry_path.exists():
            stats['worktrees_count'] = len(list(registry_path.glob('*/worktrees/*')))
        
        # Count credit resets from logs
        credit_log = self.orchestrator_path / 'credit_management' / 'credit_monitor.log'
        if credit_log.exists():
            try:
                today = datetime.now().date()
                with open(credit_log) as f:
                    for line in f:
                        if 'Credit reset detected' in line and str(today) in line:
                            stats['credit_resets'] += 1
            except:
                pass
        
        return stats
    
    def collect_recent_issues(self) -> List[Dict[str, str]]:
        """Collect recent issues and errors"""
        issues = []
        
        # Check various log files
        log_files = [
            'scheduler.log',
            'sync_coordinator.log',
            'credit_management/credit_monitor.log'
        ]
        
        for log_file in log_files:
            log_path = self.orchestrator_path / log_file
            if log_path.exists():
                try:
                    with open(log_path) as f:
                        lines = f.readlines()[-100:]  # Last 100 lines
                        
                    for line in lines:
                        if any(keyword in line.lower() for keyword in ['error', 'warning', 'failed', 'exception']):
                            # Extract timestamp and message
                            parts = line.strip().split(' - ', 3)
                            if len(parts) >= 4:
                                timestamp = parts[0]
                                message = parts[3]
                                
                                # Only include recent issues (last hour)
                                try:
                                    log_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S,%f')
                                    if datetime.now() - log_time < timedelta(hours=1):
                                        issues.append({
                                            'timestamp': log_time.strftime('%H:%M:%S'),
                                            'source': log_file,
                                            'message': message[:100]  # Truncate long messages
                                        })
                                except:
                                    pass
                                    
                except Exception as e:
                    logger.error(f"Error reading log {log_file}: {e}")
        
        # Sort by timestamp and return latest 10
        issues.sort(key=lambda x: x['timestamp'], reverse=True)
        return issues[:10]


# Global metrics collector
collector = None


@app.route('/')
def dashboard():
    """Serve the dashboard HTML"""
    return render_template_string(DASHBOARD_TEMPLATE)


@app.route('/api/metrics')
def get_metrics():
    """API endpoint for metrics data"""
    global collector
    
    data = {
        'system': collector.collect_system_metrics(),
        'orchestrations': collector.collect_orchestration_metrics(),
        'agents': collector.collect_agent_metrics(),
        'performance': collector.collect_performance_metrics(),
        'statistics': collector.collect_statistics(),
        'recent_issues': collector.collect_recent_issues()
    }
    
    return jsonify(data)


def main():
    """Run the monitoring dashboard"""
    parser = argparse.ArgumentParser(description='Monitoring dashboard for Tmux Orchestrator')
    parser.add_argument('--port', type=int, default=5000, help='Port to run dashboard on')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args = parser.parse_args()
    
    global collector
    collector = MetricsCollector()
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║       Tmux Orchestrator Monitoring Dashboard         ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Dashboard URL: http://{args.host}:{args.port:<5}              ║
║                                                      ║
║  Press Ctrl+C to stop the dashboard                  ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
    """)
    
    # Run Flask app
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
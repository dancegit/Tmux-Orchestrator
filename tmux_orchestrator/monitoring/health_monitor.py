"""
Health Monitor Module

Provides comprehensive system health monitoring, performance tracking,
and automated alerting for the Tmux Orchestrator system.
"""

import time
import psutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import json
from rich.console import Console

console = Console()


class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_average: List[float]
    process_count: int
    tmux_session_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class AgentHealth:
    """Agent health information."""
    role: str
    session_name: str
    window_index: int
    is_responsive: bool
    last_activity: Optional[float]
    credit_status: str
    error_count: int
    performance_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class HealthAlert:
    """Health monitoring alert."""
    id: str
    severity: HealthStatus
    component: str
    message: str
    timestamp: float
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class HealthMonitor:
    """
    Comprehensive health monitoring system.
    
    Features:
    - System resource monitoring (CPU, memory, disk)
    - Tmux session health tracking
    - Agent responsiveness monitoring
    - Claude credit status tracking
    - Automated alerting and notifications
    - Performance trend analysis
    """
    
    def __init__(self, tmux_orchestrator_path: Path):
        """
        Initialize health monitor.
        
        Args:
            tmux_orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.monitoring_dir = tmux_orchestrator_path / 'registry' / 'monitoring'
        self.monitoring_dir.mkdir(parents=True, exist_ok=True)
        
        # Alert thresholds
        self.thresholds = {
            'cpu_warning': 80.0,
            'cpu_critical': 95.0,
            'memory_warning': 85.0,
            'memory_critical': 95.0,
            'disk_warning': 85.0,
            'disk_critical': 95.0,
            'load_warning': 5.0,
            'load_critical': 10.0,
            'agent_unresponsive_minutes': 10
        }
        
        # Monitoring state
        self.metrics_history: List[SystemMetrics] = []
        self.agent_health: Dict[str, AgentHealth] = {}
        self.active_alerts: Dict[str, HealthAlert] = {}
        
        # Alert callbacks
        self.alert_callbacks: List[Callable] = []
        
        # Load existing data
        self._load_monitoring_data()
    
    def collect_system_metrics(self) -> SystemMetrics:
        """
        Collect current system performance metrics.
        
        Returns:
            SystemMetrics: Current system metrics
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            load_avg = list(psutil.getloadavg())
            process_count = len(psutil.pids())
            
            # Count tmux sessions
            try:
                result = subprocess.run(['tmux', 'list-sessions'], 
                                      capture_output=True, text=True)
                tmux_session_count = len([line for line in result.stdout.strip().split('\n') 
                                        if line.strip()]) if result.returncode == 0 else 0
            except Exception:
                tmux_session_count = 0
            
            metrics = SystemMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=disk.percent,
                load_average=load_avg,
                process_count=process_count,
                tmux_session_count=tmux_session_count
            )
            
            # Add to history
            self.metrics_history.append(metrics)
            
            # Keep only recent history (last 1000 entries)
            if len(self.metrics_history) > 1000:
                self.metrics_history = self.metrics_history[-1000:]
            
            # Check for alerts
            self._check_system_alerts(metrics)
            
            return metrics
            
        except Exception as e:
            console.print(f"[yellow]⚠️ Error collecting system metrics: {e}[/yellow]")
            return SystemMetrics(
                timestamp=time.time(),
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_percent=0.0,
                load_average=[0.0, 0.0, 0.0],
                process_count=0,
                tmux_session_count=0
            )
    
    def check_agent_health(self, session_name: str, agents: Dict[str, Any]) -> Dict[str, AgentHealth]:
        """
        Check health status of all agents in a session.
        
        Args:
            session_name: Tmux session name
            agents: Dictionary of agent configurations
            
        Returns:
            Dict mapping agent role to health status
        """
        health_results = {}
        
        for role, agent_config in agents.items():
            try:
                window_index = agent_config.get('window_index', 0)
                
                # Test agent responsiveness
                is_responsive = self._test_agent_responsiveness(session_name, window_index)
                
                # Check for recent activity
                last_activity = self._get_last_agent_activity(session_name, window_index)
                
                # Check credit status
                credit_status = self._check_agent_credits(session_name, window_index)
                
                # Calculate performance score
                performance_score = self._calculate_performance_score(session_name, role)
                
                agent_health = AgentHealth(
                    role=role,
                    session_name=session_name,
                    window_index=window_index,
                    is_responsive=is_responsive,
                    last_activity=last_activity,
                    credit_status=credit_status,
                    error_count=self._count_agent_errors(session_name, window_index),
                    performance_score=performance_score
                )
                
                health_results[role] = agent_health
                self.agent_health[f"{session_name}:{role}"] = agent_health
                
                # Check for agent alerts
                self._check_agent_alerts(agent_health)
                
            except Exception as e:
                console.print(f"[yellow]⚠️ Error checking {role} health: {e}[/yellow]")
                health_results[role] = AgentHealth(
                    role=role,
                    session_name=session_name,
                    window_index=0,
                    is_responsive=False,
                    last_activity=None,
                    credit_status="unknown",
                    error_count=0,
                    performance_score=0.0
                )
        
        return health_results
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive system health summary.
        
        Returns:
            Dict containing system health information
        """
        if not self.metrics_history:
            current_metrics = self.collect_system_metrics()
        else:
            current_metrics = self.metrics_history[-1]
        
        # Calculate health status
        overall_status = HealthStatus.HEALTHY
        
        if (current_metrics.cpu_percent > self.thresholds['cpu_critical'] or
            current_metrics.memory_percent > self.thresholds['memory_critical'] or
            current_metrics.disk_percent > self.thresholds['disk_critical']):
            overall_status = HealthStatus.CRITICAL
        elif (current_metrics.cpu_percent > self.thresholds['cpu_warning'] or
              current_metrics.memory_percent > self.thresholds['memory_warning'] or
              current_metrics.disk_percent > self.thresholds['disk_warning']):
            overall_status = HealthStatus.WARNING
        
        # Count agent statuses
        responsive_agents = len([ah for ah in self.agent_health.values() if ah.is_responsive])
        total_agents = len(self.agent_health)
        
        return {
            'overall_status': overall_status.value,
            'timestamp': current_metrics.timestamp,
            'system_metrics': current_metrics.to_dict(),
            'agent_summary': {
                'total_agents': total_agents,
                'responsive_agents': responsive_agents,
                'unresponsive_agents': total_agents - responsive_agents
            },
            'active_alerts': len([alert for alert in self.active_alerts.values() if not alert.resolved]),
            'tmux_sessions': current_metrics.tmux_session_count
        }
    
    def get_performance_trends(self, hours: int = 24) -> Dict[str, List[float]]:
        """
        Get performance trends over specified time period.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Dict containing trend data
        """
        cutoff_time = time.time() - (hours * 3600)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {
                'cpu_trend': [],
                'memory_trend': [],
                'disk_trend': [],
                'load_trend': []
            }
        
        return {
            'cpu_trend': [m.cpu_percent for m in recent_metrics],
            'memory_trend': [m.memory_percent for m in recent_metrics],
            'disk_trend': [m.disk_percent for m in recent_metrics],
            'load_trend': [m.load_average[0] for m in recent_metrics],
            'timestamps': [m.timestamp for m in recent_metrics]
        }
    
    def create_alert(self, 
                    component: str, 
                    message: str, 
                    severity: HealthStatus = HealthStatus.WARNING) -> str:
        """
        Create a health monitoring alert.
        
        Args:
            component: Component that triggered the alert
            message: Alert message
            severity: Alert severity level
            
        Returns:
            str: Alert ID
        """
        alert_id = f"{component}_{int(time.time())}"
        
        alert = HealthAlert(
            id=alert_id,
            severity=severity,
            component=component,
            message=message,
            timestamp=time.time(),
            resolved=False
        )
        
        self.active_alerts[alert_id] = alert
        
        # Trigger alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                console.print(f"[yellow]⚠️ Alert callback error: {e}[/yellow]")
        
        console.print(f"[red]🚨 ALERT [{severity.value.upper()}] {component}: {message}[/red]")
        return alert_id
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Mark an alert as resolved.
        
        Args:
            alert_id: Alert ID to resolve
            
        Returns:
            bool: True if alert was resolved
        """
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolved = True
            console.print(f"[green]✅ Resolved alert: {alert_id}[/green]")
            return True
        
        return False
    
    def register_alert_callback(self, callback: Callable) -> None:
        """
        Register a callback for alert notifications.
        
        Args:
            callback: Function to call when alerts are created
        """
        self.alert_callbacks.append(callback)
    
    def start_monitoring(self, interval_seconds: int = 60) -> None:
        """
        Start continuous monitoring (this would typically run in a separate thread).
        
        Args:
            interval_seconds: Monitoring interval in seconds
        """
        console.print(f"[blue]📊 Starting health monitoring (interval: {interval_seconds}s)[/blue]")
        # Note: In a real implementation, this would run in a background thread
        # For this modular system, monitoring will be triggered by orchestrator check-ins
    
    def _test_agent_responsiveness(self, session_name: str, window_index: int) -> bool:
        """Test if an agent is responsive."""
        try:
            # Send a simple test command and check for response
            test_marker = f"health_check_{int(time.time())}"
            
            # Send echo command
            subprocess.run([
                'tmux', 'send-keys', '-t', f'{session_name}:{window_index}', 
                f'echo {test_marker}', 'Enter'
            ], capture_output=True, timeout=5)
            
            time.sleep(1)
            
            # Capture output
            result = subprocess.run([
                'tmux', 'capture-pane', '-t', f'{session_name}:{window_index}', '-p'
            ], capture_output=True, text=True, timeout=5)
            
            return test_marker in result.stdout
            
        except Exception:
            return False
    
    def _get_last_agent_activity(self, session_name: str, window_index: int) -> Optional[float]:
        """Get timestamp of last agent activity."""
        try:
            # Check tmux window activity
            result = subprocess.run([
                'tmux', 'display-message', '-t', f'{session_name}:{window_index}',
                '-p', '#{window_activity}'
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            
        except Exception:
            pass
        
        return None
    
    def _check_agent_credits(self, session_name: str, window_index: int) -> str:
        """Check agent credit status."""
        try:
            # Capture recent output to look for credit warnings
            result = subprocess.run([
                'tmux', 'capture-pane', '-t', f'{session_name}:{window_index}', 
                '-S', '-50', '-p'
            ], capture_output=True, text=True)
            
            output = result.stdout.lower()
            
            if '/upgrade' in output or 'credits will reset' in output:
                return "exhausted"
            elif 'approaching usage limit' in output:
                return "low"
            else:
                return "available"
            
        except Exception:
            return "unknown"
    
    def _calculate_performance_score(self, session_name: str, role: str) -> float:
        """Calculate agent performance score (0-100)."""
        # This is a simplified implementation
        # In practice, this would analyze various performance metrics
        base_score = 80.0
        
        # Adjust based on responsiveness
        agent_key = f"{session_name}:{role}"
        if agent_key in self.agent_health:
            if not self.agent_health[agent_key].is_responsive:
                base_score -= 30.0
        
        return max(0.0, min(100.0, base_score))
    
    def _count_agent_errors(self, session_name: str, window_index: int) -> int:
        """Count recent errors in agent output."""
        try:
            result = subprocess.run([
                'tmux', 'capture-pane', '-t', f'{session_name}:{window_index}', 
                '-S', '-100', '-p'
            ], capture_output=True, text=True)
            
            output = result.stdout.lower()
            error_indicators = ['error:', 'exception:', 'failed:', 'traceback']
            
            error_count = 0
            for line in output.split('\n'):
                if any(indicator in line for indicator in error_indicators):
                    error_count += 1
            
            return error_count
            
        except Exception:
            return 0
    
    def _check_system_alerts(self, metrics: SystemMetrics) -> None:
        """Check system metrics against thresholds and create alerts."""
        # CPU alerts
        if metrics.cpu_percent > self.thresholds['cpu_critical']:
            self.create_alert('system_cpu', f'Critical CPU usage: {metrics.cpu_percent:.1f}%', 
                            HealthStatus.CRITICAL)
        elif metrics.cpu_percent > self.thresholds['cpu_warning']:
            self.create_alert('system_cpu', f'High CPU usage: {metrics.cpu_percent:.1f}%', 
                            HealthStatus.WARNING)
        
        # Memory alerts
        if metrics.memory_percent > self.thresholds['memory_critical']:
            self.create_alert('system_memory', f'Critical memory usage: {metrics.memory_percent:.1f}%', 
                            HealthStatus.CRITICAL)
        elif metrics.memory_percent > self.thresholds['memory_warning']:
            self.create_alert('system_memory', f'High memory usage: {metrics.memory_percent:.1f}%', 
                            HealthStatus.WARNING)
        
        # Disk alerts
        if metrics.disk_percent > self.thresholds['disk_critical']:
            self.create_alert('system_disk', f'Critical disk usage: {metrics.disk_percent:.1f}%', 
                            HealthStatus.CRITICAL)
        elif metrics.disk_percent > self.thresholds['disk_warning']:
            self.create_alert('system_disk', f'High disk usage: {metrics.disk_percent:.1f}%', 
                            HealthStatus.WARNING)
    
    def _check_agent_alerts(self, agent_health: AgentHealth) -> None:
        """Check agent health and create alerts if needed."""
        if not agent_health.is_responsive:
            self.create_alert(f'agent_{agent_health.role}', 
                            f'Agent {agent_health.role} is unresponsive', 
                            HealthStatus.CRITICAL)
        
        if agent_health.credit_status == "exhausted":
            self.create_alert(f'agent_{agent_health.role}_credits', 
                            f'Agent {agent_health.role} has exhausted credits', 
                            HealthStatus.WARNING)
        
        if agent_health.error_count > 5:
            self.create_alert(f'agent_{agent_health.role}_errors', 
                            f'Agent {agent_health.role} has {agent_health.error_count} recent errors', 
                            HealthStatus.WARNING)
    
    def _save_monitoring_data(self) -> None:
        """Persist monitoring data to disk."""
        try:
            # Save metrics history
            metrics_file = self.monitoring_dir / 'metrics_history.json'
            metrics_data = [m.to_dict() for m in self.metrics_history[-100:]]  # Keep recent 100
            metrics_file.write_text(json.dumps(metrics_data, indent=2))
            
            # Save agent health
            health_file = self.monitoring_dir / 'agent_health.json'
            health_data = {k: v.to_dict() for k, v in self.agent_health.items()}
            health_file.write_text(json.dumps(health_data, indent=2))
            
            # Save alerts
            alerts_file = self.monitoring_dir / 'active_alerts.json'
            alerts_data = {k: v.to_dict() for k, v in self.active_alerts.items()}
            alerts_file.write_text(json.dumps(alerts_data, indent=2))
            
        except Exception as e:
            console.print(f"[yellow]⚠️ Failed to save monitoring data: {e}[/yellow]")
    
    def _load_monitoring_data(self) -> None:
        """Load monitoring data from disk."""
        try:
            # Load metrics history
            metrics_file = self.monitoring_dir / 'metrics_history.json'
            if metrics_file.exists():
                metrics_data = json.loads(metrics_file.read_text())
                self.metrics_history = [
                    SystemMetrics(**data) for data in metrics_data
                ]
            
            # Load agent health
            health_file = self.monitoring_dir / 'agent_health.json'
            if health_file.exists():
                health_data = json.loads(health_file.read_text())
                self.agent_health = {
                    k: AgentHealth(**v) for k, v in health_data.items()
                }
            
            # Load alerts
            alerts_file = self.monitoring_dir / 'active_alerts.json'
            if alerts_file.exists():
                alerts_data = json.loads(alerts_file.read_text())
                self.active_alerts = {
                    k: HealthAlert(**v) for k, v in alerts_data.items()
                }
                
        except Exception as e:
            console.print(f"[yellow]⚠️ Failed to load monitoring data: {e}[/yellow]")
            # Initialize empty state
            self.metrics_history = []
            self.agent_health = {}
            self.active_alerts = {}
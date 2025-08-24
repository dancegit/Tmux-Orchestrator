#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Multi-Project Monitoring Tool for Tmux Orchestrator
Monitor multiple concurrent orchestrations from a single dashboard
"""

import os
import sys
import json
import subprocess
import time
import curses
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import argparse

# Set UV_NO_WORKSPACE environment variable for all subprocess calls
os.environ['UV_NO_WORKSPACE'] = '1'
import glob

# Import session state management
sys.path.append(str(Path(__file__).parent))
from session_state import SessionStateManager, SessionState, AgentState


class MultiProjectMonitor:
    def __init__(self, orchestrator_path: str = None):
        self.orchestrator_path = Path(orchestrator_path) if orchestrator_path else Path.cwd()
        self.registry_path = self.orchestrator_path / 'registry'
        self.session_manager = SessionStateManager(self.orchestrator_path)
        self.refresh_interval = 10  # seconds
        self.project_statuses: Dict[str, Dict] = {}
        
    def discover_active_projects(self) -> List[Tuple[str, Path]]:
        """Discover all active orchestration projects"""
        active_projects = []
        
        # Look for session state files
        session_files = glob.glob(str(self.registry_path / 'projects' / '*' / 'session_state.json'))
        
        for session_file in session_files:
            session_path = Path(session_file)
            project_name = session_path.parent.name
            
            # Check if session is actually active (tmux session exists)
            try:
                state = self.session_manager.load_session_state(project_name)
                if state and state.session_name:
                    # Verify tmux session exists
                    result = subprocess.run(
                        ['tmux', 'has-session', '-t', state.session_name],
                        capture_output=True
                    )
                    if result.returncode == 0:
                        active_projects.append((project_name, session_path.parent))
            except:
                pass
                
        return active_projects
    
    def get_tmux_session_info(self, session_name: str) -> Dict[str, Any]:
        """Get information about a tmux session"""
        info = {
            'exists': False,
            'windows': [],
            'attached': False,
            'created': None
        }
        
        try:
            # Check if session exists
            result = subprocess.run(
                ['tmux', 'has-session', '-t', session_name],
                capture_output=True
            )
            info['exists'] = result.returncode == 0
            
            if info['exists']:
                # Get window list
                result = subprocess.run(
                    ['tmux', 'list-windows', '-t', session_name, '-F', '#{window_index}:#{window_name}:#{window_active}'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            idx, name, active = line.split(':')
                            info['windows'].append({
                                'index': int(idx),
                                'name': name,
                                'active': active == '1'
                            })
                
                # Check if attached
                result = subprocess.run(
                    ['tmux', 'list-clients', '-t', session_name],
                    capture_output=True,
                    text=True
                )
                info['attached'] = bool(result.stdout.strip())
                
        except Exception as e:
            pass
            
        return info
    
    def get_agent_health(self, agent: AgentState) -> Dict[str, Any]:
        """Get health status of an agent"""
        health = {
            'status': 'unknown',
            'credit_exhausted': agent.is_exhausted,
            'last_checkin': agent.last_check_in_time,
            'time_since_checkin': None,
            'checkin_overdue': False
        }
        
        # Determine status
        if agent.is_exhausted:
            health['status'] = 'exhausted'
            if agent.credit_reset_time:
                health['reset_time'] = agent.credit_reset_time
        elif not agent.is_alive:
            health['status'] = 'dead'
        elif agent.is_alive:
            health['status'] = 'active'
        else:
            health['status'] = 'unknown'
        
        # Calculate time since last check-in
        if agent.last_check_in_time:
            try:
                last_checkin_dt = datetime.fromisoformat(agent.last_check_in_time.replace('Z', '+00:00'))
                delta = datetime.now(last_checkin_dt.tzinfo) - last_checkin_dt
                health['time_since_checkin'] = delta
                
                # Check if overdue (2x the check-in interval)
                # Note: check_in_interval is not a field in AgentState, would need to be passed separately
                # For now, assume a default 30 minute interval
                overdue_threshold = 60 * 60  # 60 minutes
                health['checkin_overdue'] = delta.total_seconds() > overdue_threshold
            except:
                pass
                
        return health
    
    def get_project_metrics(self, state: SessionState) -> Dict[str, Any]:
        """Calculate project metrics"""
        metrics = {
            'total_agents': len(state.agents),
            'active_agents': 0,
            'dead_agents': 0,
            'exhausted_agents': 0,
            'overdue_agents': 0,
            'completion_rate': 0.0,
            'health_score': 0.0
        }
        
        for agent in state.agents.values():
            health = self.get_agent_health(agent)
            
            if health['status'] == 'active':
                metrics['active_agents'] += 1
            elif health['status'] == 'dead':
                metrics['dead_agents'] += 1
            elif health['status'] == 'exhausted':
                metrics['exhausted_agents'] += 1
                
            if health['checkin_overdue']:
                metrics['overdue_agents'] += 1
        
        # Calculate completion rate (simplified - based on phase progress)
        if hasattr(state, 'phases_completed') and hasattr(state, 'total_phases'):
            if state.total_phases > 0:
                metrics['completion_rate'] = state.phases_completed / state.total_phases
        
        # Calculate health score
        if metrics['total_agents'] > 0:
            healthy_agents = metrics['active_agents']
            metrics['health_score'] = healthy_agents / metrics['total_agents']
        
        return metrics
    
    def update_project_statuses(self):
        """Update status for all active projects"""
        active_projects = self.discover_active_projects()
        
        # Remove projects that are no longer active
        current_projects = set(p[0] for p in active_projects)
        for project in list(self.project_statuses.keys()):
            if project not in current_projects:
                del self.project_statuses[project]
        
        # Update active projects
        for project_name, project_path in active_projects:
            try:
                # Load session state
                state = self.session_manager.load_session_state(project_name)
                if not state:
                    continue
                
                # Get tmux session info
                tmux_info = self.get_tmux_session_info(state.session_name)
                
                # Get project metrics
                metrics = self.get_project_metrics(state)
                
                # Get git branch info
                git_info = {'branch': 'unknown', 'uncommitted': False}
                try:
                    worktree_path = project_path / 'worktrees' / 'orchestrator'
                    if worktree_path.exists():
                        result = subprocess.run(
                            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                            cwd=worktree_path,
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0:
                            git_info['branch'] = result.stdout.strip()
                        
                        result = subprocess.run(
                            ['git', 'status', '--porcelain'],
                            cwd=worktree_path,
                            capture_output=True,
                            text=True
                        )
                        git_info['uncommitted'] = bool(result.stdout.strip())
                except:
                    pass
                
                self.project_statuses[project_name] = {
                    'session_state': state,
                    'tmux_info': tmux_info,
                    'metrics': metrics,
                    'git_info': git_info,
                    'last_updated': datetime.now()
                }
                
            except Exception as e:
                # Keep partial info if available
                if project_name not in self.project_statuses:
                    self.project_statuses[project_name] = {
                        'error': str(e),
                        'last_updated': datetime.now()
                    }
    
    def format_duration(self, td: Optional[timedelta]) -> str:
        """Format timedelta as human readable"""
        if not td:
            return "never"
            
        total_seconds = int(td.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h{minutes}m"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            return f"{days}d{hours}h"
    
    def draw_dashboard(self, stdscr):
        """Draw the multi-project dashboard"""
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(1)   # Non-blocking input
        
        # Color pairs
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Good
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Warning
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)     # Error
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)    # Info
        curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK) # Highlight
        
        last_update = time.time()
        selected_project = 0
        
        while True:
            # Update data periodically
            if time.time() - last_update > self.refresh_interval:
                self.update_project_statuses()
                last_update = time.time()
            
            # Clear screen
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            
            # Header
            header = "Tmux Orchestrator - Multi-Project Monitor"
            subheader = f"Active Projects: {len(self.project_statuses)} | Updated: {datetime.now().strftime('%H:%M:%S')}"
            stdscr.addstr(0, (width - len(header)) // 2, header, curses.A_BOLD)
            stdscr.addstr(1, (width - len(subheader)) // 2, subheader)
            
            # Project list
            y = 3
            project_list = sorted(self.project_statuses.items())
            
            for idx, (project_name, status) in enumerate(project_list):
                if y >= height - 10:  # Leave room for details
                    break
                
                # Highlight selected project
                attr = curses.A_REVERSE if idx == selected_project else 0
                
                # Get display info
                if 'error' in status:
                    status_text = "ERROR"
                    color = curses.color_pair(3)
                elif 'metrics' in status:
                    metrics = status['metrics']
                    if metrics['health_score'] >= 0.8:
                        status_text = "HEALTHY"
                        color = curses.color_pair(1)
                    elif metrics['health_score'] >= 0.5:
                        status_text = "WARNING"
                        color = curses.color_pair(2)
                    else:
                        status_text = "CRITICAL"
                        color = curses.color_pair(3)
                else:
                    status_text = "UNKNOWN"
                    color = 0
                
                # Project summary line
                summary = f"{project_name:<30} [{status_text:^10}]"
                if 'metrics' in status:
                    m = status['metrics']
                    summary += f" Agents: {m['active_agents']}/{m['total_agents']}"
                    summary += f" Completion: {m['completion_rate']*100:.0f}%"
                
                stdscr.addstr(y, 2, summary[:width-4], color | attr)
                y += 1
            
            # Separator
            y += 1
            if y < height - 8:
                stdscr.addstr(y, 0, "─" * width)
                y += 1
            
            # Detailed view of selected project
            if selected_project < len(project_list) and y < height - 6:
                project_name, status = project_list[selected_project]
                
                # Project name
                stdscr.addstr(y, 2, f"Project: {project_name}", curses.A_BOLD)
                y += 1
                
                if 'session_state' in status:
                    state = status['session_state']
                    
                    # Session info
                    tmux_status = "attached" if status['tmux_info']['attached'] else "detached"
                    stdscr.addstr(y, 4, f"Session: {state.session_name} ({tmux_status})")
                    y += 1
                    
                    # Git info
                    git_info = status['git_info']
                    git_status = " [uncommitted]" if git_info['uncommitted'] else ""
                    stdscr.addstr(y, 4, f"Branch: {git_info['branch']}{git_status}")
                    y += 1
                    
                    # Agent details
                    y += 1
                    stdscr.addstr(y, 4, "Agents:", curses.A_UNDERLINE)
                    y += 1
                    
                    for agent_name, agent in sorted(state.agents.items()):
                        if y >= height - 2:
                            break
                            
                        health = self.get_agent_health(agent)
                        
                        # Status icon and color
                        if health['status'] == 'active':
                            icon = "●"
                            color = curses.color_pair(1)
                        elif health['status'] == 'exhausted':
                            icon = "◐"
                            color = curses.color_pair(2)
                        else:
                            icon = "○"
                            color = curses.color_pair(3)
                        
                        # Agent line
                        agent_line = f"{icon} {agent.role:<20}"
                        if health['time_since_checkin']:
                            agent_line += f" Last seen: {self.format_duration(health['time_since_checkin'])}"
                        if health['checkin_overdue']:
                            agent_line += " [OVERDUE]"
                        
                        stdscr.addstr(y, 6, agent_line[:width-8], color)
                        y += 1
            
            # Footer
            footer = "↑↓ Navigate | Enter: Attach | r: Refresh | q: Quit"
            stdscr.addstr(height-1, (width - len(footer)) // 2, footer, curses.A_DIM)
            
            # Refresh display
            stdscr.refresh()
            
            # Handle input
            key = stdscr.getch()
            if key == ord('q'):
                break
            elif key == ord('r'):
                self.update_project_statuses()
                last_update = time.time()
            elif key == curses.KEY_UP and selected_project > 0:
                selected_project -= 1
            elif key == curses.KEY_DOWN and selected_project < len(project_list) - 1:
                selected_project += 1
            elif key == 10 and selected_project < len(project_list):  # Enter key
                # Attach to selected project's tmux session
                project_name, status = project_list[selected_project]
                if 'session_state' in status:
                    session_name = status['session_state'].session_name
                    subprocess.run(['tmux', 'attach-session', '-t', session_name])
                    # Refresh after returning
                    self.update_project_statuses()
                    last_update = time.time()
            
            # Small delay to prevent CPU spinning
            time.sleep(0.1)
    
    def run_dashboard(self):
        """Run the dashboard in curses mode"""
        # Initial data fetch
        self.update_project_statuses()
        
        if not self.project_statuses:
            print("No active orchestrations found.")
            print(f"Registry path: {self.registry_path}")
            return
        
        # Run curses interface
        curses.wrapper(self.draw_dashboard)
    
    def get_summary_report(self) -> str:
        """Get a text summary of all projects"""
        self.update_project_statuses()
        
        if not self.project_statuses:
            return "No active orchestrations found."
        
        lines = []
        lines.append("Tmux Orchestrator - Multi-Project Summary")
        lines.append("=" * 60)
        lines.append(f"Active Projects: {len(self.project_statuses)}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        for project_name, status in sorted(self.project_statuses.items()):
            lines.append(f"Project: {project_name}")
            lines.append("-" * 40)
            
            if 'error' in status:
                lines.append(f"  Error: {status['error']}")
            else:
                if 'session_state' in status:
                    state = status['session_state']
                    lines.append(f"  Session: {state.session_name}")
                    lines.append(f"  Started: {state.start_time}")
                
                if 'metrics' in status:
                    m = status['metrics']
                    lines.append(f"  Agents: {m['active_agents']} active, {m['dead_agents']} dead, {m['exhausted_agents']} exhausted")
                    lines.append(f"  Health Score: {m['health_score']*100:.0f}%")
                    lines.append(f"  Completion: {m['completion_rate']*100:.0f}%")
                
                if 'git_info' in status:
                    git = status['git_info']
                    uncommitted = " (uncommitted changes)" if git['uncommitted'] else ""
                    lines.append(f"  Branch: {git['branch']}{uncommitted}")
            
            lines.append("")
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Multi-Project Monitor for Tmux Orchestrator')
    parser.add_argument('--path', help='Path to Tmux Orchestrator directory', default='.')
    parser.add_argument('--summary', action='store_true', help='Print summary instead of interactive dashboard')
    parser.add_argument('--json', action='store_true', help='Output JSON format')
    
    args = parser.parse_args()
    
    monitor = MultiProjectMonitor(args.path)
    
    if args.summary:
        print(monitor.get_summary_report())
    elif args.json:
        monitor.update_project_statuses()
        output = {
            'timestamp': datetime.now().isoformat(),
            'projects': {}
        }
        
        for project_name, status in monitor.project_statuses.items():
            project_data = {
                'error': status.get('error'),
                'metrics': status.get('metrics'),
                'git_info': status.get('git_info')
            }
            
            if 'session_state' in status:
                state = status['session_state']
                project_data['session'] = {
                    'name': state.session_name,
                    'created_at': state.created_at,
                    'agents': {
                        name: {
                            'role': agent.role,
                            'is_alive': agent.is_alive,
                            'is_exhausted': agent.is_exhausted
                        }
                        for name, agent in state.agents.items()
                    }
                }
            
            output['projects'][project_name] = project_data
        
        print(json.dumps(output, indent=2))
    else:
        monitor.run_dashboard()


if __name__ == "__main__":
    main()
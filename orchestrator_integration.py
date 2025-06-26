#!/usr/bin/env python3
"""
Orchestrator Integration for Project Startup

Integrates project startup with the main orchestrator for monitoring and management.
"""

import os
import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from session_registry import SessionRegistry
from tmux_utils import TmuxOrchestrator
from project_startup import ProjectInfo, ProjectStartupAutomation
from github_integration import GitHubIntegration


class OrchestratorProjectManager:
    """Manages projects within the orchestrator ecosystem"""
    
    def __init__(self):
        self.registry = SessionRegistry()
        self.tmux = TmuxOrchestrator()
        self.startup = ProjectStartupAutomation()
        self.github = GitHubIntegration()
        self.monitoring_config_file = Path(__file__).parent / "registry" / "monitoring_config.json"
        self.monitoring_config = self._load_monitoring_config()
    
    def _load_monitoring_config(self) -> Dict:
        """Load monitoring configuration"""
        if self.monitoring_config_file.exists():
            with open(self.monitoring_config_file, 'r') as f:
                return json.load(f)
        return {
            "default_check_interval": 300,
            "error_detection": {
                "patterns": ["ERROR", "FATAL", "Exception", "Failed", "Error:"],
                "ignore_patterns": ["[32m", "[INFO]", "npm WARN"]
            },
            "success_detection": {
                "patterns": ["Server running", "Compiled successfully", "Ready on", "Listening on"]
            },
            "idle_detection": {
                "timeout_minutes": 30,
                "prompt_patterns": [">", "$", ">>>", "In [", "claude>"]
            }
        }
    
    def _save_monitoring_config(self):
        """Save monitoring configuration"""
        self.monitoring_config_file.parent.mkdir(exist_ok=True)
        with open(self.monitoring_config_file, 'w') as f:
            json.dump(self.monitoring_config, f, indent=2)
    
    def start_and_monitor_project(self, project_name: str, custom_briefing: str = None) -> Dict:
        """Start a project and set up monitoring"""
        result = {
            "success": False,
            "project_name": project_name,
            "session_name": None,
            "monitoring_enabled": False,
            "errors": []
        }
        
        # Start the project
        if not self.startup.start_project(project_name, custom_briefing):
            result["errors"].append("Failed to start project")
            return result
        
        # Get project info
        project = self.startup.discovery.find_project(project_name)
        if not project:
            result["errors"].append("Could not find project after startup")
            return result
        
        session_name = self.startup._get_session_name(project)
        result["session_name"] = session_name
        result["success"] = True
        
        # Set up monitoring
        try:
            self._setup_project_monitoring(session_name, project)
            result["monitoring_enabled"] = True
        except Exception as e:
            result["errors"].append(f"Monitoring setup failed: {str(e)}")
        
        # Initial health check
        time.sleep(5)  # Give everything time to start
        health = self.check_project_health(session_name)
        result["initial_health"] = health
        
        return result
    
    def _setup_project_monitoring(self, session_name: str, project: ProjectInfo):
        """Set up monitoring for a project session"""
        # Get project config
        project_config = self.startup.configs.get(project.name, {})
        monitoring_config = project_config.get('monitoring', {})
        
        # Merge with defaults
        check_interval = monitoring_config.get('check_interval', 
                                             self.monitoring_config['default_check_interval'])
        
        # Update registry with monitoring info
        self.registry.register_session(session_name, {
            'monitoring': {
                'enabled': True,
                'check_interval': check_interval,
                'last_check': datetime.now().isoformat(),
                'error_patterns': monitoring_config.get('error_patterns', 
                                                       self.monitoring_config['error_detection']['patterns']),
                'success_patterns': monitoring_config.get('success_patterns',
                                                        self.monitoring_config['success_detection']['patterns'])
            }
        })
    
    def check_project_health(self, session_name: str) -> Dict:
        """Check health of a project session"""
        health = {
            "session_exists": False,
            "windows_healthy": {},
            "errors_detected": [],
            "agent_status": "unknown",
            "server_status": "unknown",
            "last_activity": {}
        }
        
        # Check if session exists
        sessions = self.tmux.get_tmux_sessions()
        session = next((s for s in sessions if s.name == session_name), None)
        
        if not session:
            return health
        
        health["session_exists"] = True
        
        # Check each window
        for window in session.windows:
            window_health = self._check_window_health(session_name, window.window_index)
            health["windows_healthy"][window.window_name] = window_health
            
            # Special handling for known windows
            if window.window_name == "Claude-Agent":
                health["agent_status"] = self._determine_agent_status(window_health)
            elif window.window_name == "Dev-Server":
                health["server_status"] = self._determine_server_status(window_health)
        
        return health
    
    def _check_window_health(self, session_name: str, window_index: int) -> Dict:
        """Check health of a specific window"""
        # Capture recent output
        content = self.tmux.capture_window_content(session_name, window_index, num_lines=100)
        
        health = {
            "has_output": bool(content.strip()),
            "errors": [],
            "successes": [],
            "is_idle": False,
            "last_activity_time": None
        }
        
        if not content:
            return health
        
        lines = content.split('\n')
        
        # Check for errors
        error_patterns = self.monitoring_config['error_detection']['patterns']
        ignore_patterns = self.monitoring_config['error_detection']['ignore_patterns']
        
        for line in lines[-50:]:  # Check last 50 lines
            # Skip if line contains ignore patterns
            if any(ignore in line for ignore in ignore_patterns):
                continue
            
            for error_pattern in error_patterns:
                if error_pattern.lower() in line.lower():
                    health["errors"].append(line.strip())
                    break
        
        # Check for success patterns
        success_patterns = self.monitoring_config['success_detection']['patterns']
        for line in lines[-20:]:  # Check last 20 lines
            for success_pattern in success_patterns:
                if success_pattern.lower() in line.lower():
                    health["successes"].append(line.strip())
                    break
        
        # Check if idle
        if lines:
            last_line = lines[-1].strip()
            prompt_patterns = self.monitoring_config['idle_detection']['prompt_patterns']
            health["is_idle"] = any(last_line.endswith(pattern) for pattern in prompt_patterns)
        
        return health
    
    def _determine_agent_status(self, window_health: Dict) -> str:
        """Determine Claude agent status from window health"""
        if not window_health["has_output"]:
            return "not_started"
        elif window_health["errors"]:
            return "error"
        elif window_health["is_idle"]:
            return "idle"
        else:
            return "working"
    
    def _determine_server_status(self, window_health: Dict) -> str:
        """Determine dev server status from window health"""
        if not window_health["has_output"]:
            return "not_started"
        elif window_health["errors"]:
            return "error"
        elif window_health["successes"]:
            return "running"
        else:
            return "starting"
    
    def get_all_projects_status(self) -> Dict:
        """Get status of all project sessions"""
        all_sessions = self.tmux.get_tmux_sessions()
        project_sessions = []
        
        for session in all_sessions:
            session_info = self.registry.get_session_info(session.name)
            if session_info and session_info.get('auto_started'):
                # This is a project session
                health = self.check_project_health(session.name)
                project_sessions.append({
                    "session_name": session.name,
                    "project_info": session_info.get('project_info', {}),
                    "health": health,
                    "monitoring": session_info.get('monitoring', {})
                })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_projects": len(project_sessions),
            "projects": project_sessions
        }
    
    def suggest_agent_tasks(self, session_name: str) -> List[str]:
        """Suggest tasks for an idle agent based on project context"""
        suggestions = []
        
        # Get session info
        session_info = self.registry.get_session_info(session_name)
        if not session_info:
            return suggestions
        
        project_info = session_info.get('project_info', {})
        project_path = project_info.get('path')
        
        if not project_path:
            return suggestions
        
        # Check GitHub issues
        if self.github.gh_available:
            issues = self.github.get_issues(project_path, limit=5)
            if issues:
                prioritized = self.github.prioritize_issues(issues)
                if prioritized:
                    top_issue = prioritized[0]
                    suggestions.append(f"Work on issue #{top_issue['number']}: {top_issue['title']}")
        
        # Generic suggestions based on project type
        project_type = project_info.get('project_type')
        framework = project_info.get('framework')
        
        if project_type == 'nodejs':
            suggestions.extend([
                "Run 'npm audit' and fix any security vulnerabilities",
                "Review and update dependencies in package.json",
                "Add or improve unit tests"
            ])
        elif project_type == 'python':
            suggestions.extend([
                "Run 'pip list --outdated' and update dependencies",
                "Add type hints to functions missing them",
                "Improve test coverage"
            ])
        
        # Framework-specific suggestions
        if framework == 'nextjs':
            suggestions.extend([
                "Optimize page load performance",
                "Review and improve SEO meta tags",
                "Check for accessibility issues"
            ])
        elif framework == 'fastapi':
            suggestions.extend([
                "Add API documentation with examples",
                "Implement request validation",
                "Add performance monitoring endpoints"
            ])
        
        # General suggestions
        suggestions.extend([
            "Review code for potential refactoring opportunities",
            "Update or add documentation",
            "Look for and fix any TODO comments in the code"
        ])
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def send_task_to_agent(self, session_name: str, task: str) -> bool:
        """Send a task to a Claude agent"""
        try:
            # Send the task message
            self.tmux.send_keys_to_window(session_name, 0, task, confirm=False)
            time.sleep(1)  # Critical delay for Claude UI
            
            # Send Enter
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:0', 'Enter'])
            
            # Update registry
            self.registry.register_session(session_name, {
                'current_task': task,
                'task_assigned_at': datetime.now().isoformat()
            })
            
            return True
        except:
            return False
    
    def create_monitoring_report(self) -> str:
        """Create a comprehensive monitoring report"""
        status = self.get_all_projects_status()
        
        report_lines = [
            f"Project Monitoring Report - {status['timestamp']}",
            "=" * 60,
            f"\nTotal Active Projects: {status['total_projects']}\n"
        ]
        
        for project in status['projects']:
            session_name = project['session_name']
            project_info = project['project_info']
            health = project['health']
            
            report_lines.extend([
                f"\nProject: {project_info.get('name', session_name)}",
                "-" * 40,
                f"Session: {session_name}",
                f"Type: {project_info.get('project_type', 'unknown')}",
                f"Framework: {project_info.get('framework', 'none')}",
                f"Path: {project_info.get('path', 'unknown')}",
                "",
                "Health Status:",
                f"  Agent: {health['agent_status']}",
                f"  Server: {health['server_status']}",
                f"  Session Active: {health['session_exists']}"
            ])
            
            # Add error summary if any
            all_errors = []
            for window_name, window_health in health['windows_healthy'].items():
                if window_health['errors']:
                    all_errors.extend(window_health['errors'])
            
            if all_errors:
                report_lines.append("\nRecent Errors:")
                for error in all_errors[:3]:  # Show up to 3 errors
                    report_lines.append(f"  - {error}")
            
            # Add suggestions for idle agents
            if health['agent_status'] == 'idle':
                suggestions = self.suggest_agent_tasks(session_name)
                if suggestions:
                    report_lines.append("\nSuggested Tasks:")
                    for i, suggestion in enumerate(suggestions[:3], 1):
                        report_lines.append(f"  {i}. {suggestion}")
        
        return '\n'.join(report_lines)


if __name__ == "__main__":
    import sys
    
    manager = OrchestratorProjectManager()
    
    if len(sys.argv) < 2:
        print("Usage: python orchestrator_integration.py <command> [args]")
        print("\nCommands:")
        print("  start <project>     - Start and monitor a project")
        print("  status              - Show all projects status")
        print("  health <session>    - Check health of a session")
        print("  suggest <session>   - Get task suggestions for a session")
        print("  report              - Generate monitoring report")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "start":
        if len(sys.argv) < 3:
            print("Error: Project name required")
            sys.exit(1)
        
        project_name = sys.argv[2]
        result = manager.start_and_monitor_project(project_name)
        print(json.dumps(result, indent=2))
    
    elif command == "status":
        status = manager.get_all_projects_status()
        print(json.dumps(status, indent=2))
    
    elif command == "health":
        if len(sys.argv) < 3:
            print("Error: Session name required")
            sys.exit(1)
        
        session_name = sys.argv[2]
        health = manager.check_project_health(session_name)
        print(json.dumps(health, indent=2))
    
    elif command == "suggest":
        if len(sys.argv) < 3:
            print("Error: Session name required")
            sys.exit(1)
        
        session_name = sys.argv[2]
        suggestions = manager.suggest_agent_tasks(session_name)
        print("Task suggestions:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"{i}. {suggestion}")
    
    elif command == "report":
        report = manager.create_monitoring_report()
        print(report)
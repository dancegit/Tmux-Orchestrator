#!/usr/bin/env python3
"""
State Updater for Tmux Orchestrator
Subscribes to event bus and updates session state based on events
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict
from datetime import datetime

# Add imports
from event_bus import EventBus
from session_state import SessionStateManager

logger = logging.getLogger(__name__)

class StateUpdater:
    def __init__(self):
        self.manager = SessionStateManager(Path(__file__).parent)
        self.bus = EventBus()
        self.setup_subscriptions()
        
    def setup_subscriptions(self):
        """Subscribe to relevant event types"""
        self.bus.subscribe('violation', self.handle_violation)
        self.bus.subscribe('critical_violation', self.handle_critical_violation)
        self.bus.subscribe('git_violation', self.handle_git_violation)
        self.bus.subscribe('credit_exhausted', self.handle_credit_exhausted)
        self.bus.subscribe('task_completed', self.handle_task_completed)
        self.bus.subscribe('status_update', self.handle_status_update)
        logger.info("State updater subscribed to all event types")
        
    def handle_violation(self, event_type: str, data: Dict[str, Any]):
        """Handle compliance violations"""
        try:
            project_name = data.get('project_name', 'default')
            agent = data.get('sender', 'unknown')
            severity = data.get('severity', 'low')
            
            # Update session state with violation
            state = self.manager.load_session_state(project_name)
            if state:
                # Add to status reports
                if not hasattr(state, 'status_reports') or state.status_reports is None:
                    state.status_reports = {}
                    
                state.status_reports[agent] = {
                    'topic': 'compliance',
                    'status': 'VIOLATION',
                    'details': str(data.get('analysis', {})),
                    'timestamp': datetime.now().isoformat(),
                    'severity': severity
                }
                
                self.manager.save_session_state(state)
                logger.info(f"Updated session state for {project_name} with violation from {agent}")
                
            # For high severity, consider selective tmux notification
            if severity == 'high':
                self._send_critical_notification(data)
                
        except Exception as e:
            logger.error(f"Error handling violation: {e}")
            
    def handle_critical_violation(self, event_type: str, data: Dict[str, Any]):
        """Handle critical violations that need immediate attention"""
        self.handle_violation(event_type, data)  # Same as violation but always critical
        self._send_critical_notification(data)
        
    def handle_git_violation(self, event_type: str, data: Dict[str, Any]):
        """Handle git workflow violations"""
        try:
            project_name = data.get('project_name', 'default')
            agent = data.get('agent', 'unknown')
            
            state = self.manager.load_session_state(project_name)
            if state:
                if not hasattr(state, 'status_reports') or state.status_reports is None:
                    state.status_reports = {}
                    
                state.status_reports[agent] = {
                    'topic': 'git_compliance',
                    'status': 'VIOLATION',
                    'details': str(data.get('violations', [])),
                    'timestamp': datetime.now().isoformat()
                }
                
                self.manager.save_session_state(state)
                logger.info(f"Updated session state for {project_name} with git violation")
                
        except Exception as e:
            logger.error(f"Error handling git violation: {e}")
            
    def handle_credit_exhausted(self, event_type: str, data: Dict[str, Any]):
        """Handle credit exhaustion events"""
        try:
            agent_window = data.get('agent', '')
            reset_time = data.get('reset_time', '')
            
            # Extract project and role from window name
            parts = agent_window.split(':')
            if parts:
                session_name = parts[0]
                # Try to find matching project
                for project_dir in (Path(__file__).parent / 'registry' / 'projects').iterdir():
                    if project_dir.is_dir():
                        state = self.manager.load_session_state(project_dir.name)
                        if state and state.session_name == session_name:
                            # Update agent exhaustion status
                            for role, agent in state.agents.items():
                                if agent.window_index == int(parts[1]) if len(parts) > 1 else 0:
                                    agent.is_exhausted = True
                                    agent.credit_reset_time = reset_time
                                    self.manager.save_session_state(state)
                                    logger.info(f"Marked {role} as exhausted in {project_dir.name}")
                                    break
                                    
        except Exception as e:
            logger.error(f"Error handling credit exhaustion: {e}")
            
    def handle_task_completed(self, event_type: str, data: Dict[str, Any]):
        """Handle task completion events"""
        try:
            project_name = data.get('project_name', 'default')
            agent = data.get('agent', 'unknown')
            task = data.get('task', 'unknown')
            
            state = self.manager.load_session_state(project_name)
            if state:
                if not hasattr(state, 'status_reports') or state.status_reports is None:
                    state.status_reports = {}
                    
                state.status_reports[agent] = {
                    'topic': 'task_completion',
                    'status': 'COMPLETE',
                    'details': task,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.manager.save_session_state(state)
                logger.info(f"Updated session state for {project_name} with task completion")
                
        except Exception as e:
            logger.error(f"Error handling task completion: {e}")
            
    def handle_status_update(self, event_type: str, data: Dict[str, Any]):
        """Handle general status updates"""
        try:
            project_name = data.get('project_name', 'default')
            agent = data.get('agent', 'unknown')
            status = data.get('status', 'unknown')
            details = data.get('details', '')
            
            state = self.manager.load_session_state(project_name)
            if state:
                if not hasattr(state, 'status_reports') or state.status_reports is None:
                    state.status_reports = {}
                    
                state.status_reports[agent] = {
                    'topic': 'status_update',
                    'status': status,
                    'details': details,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.manager.save_session_state(state)
                logger.info(f"Updated session state for {project_name} with status update")
                
        except Exception as e:
            logger.error(f"Error handling status update: {e}")
            
    def _send_critical_notification(self, data: Dict[str, Any]):
        """Send critical notifications via tmux (selective, only for high priority)"""
        try:
            # Get orchestrator session from config
            import yaml
            with open('orchestrator_config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            target = config.get('general', {}).get('tmux_session', 'orchestrator:0') + ':0'
            
            # Build concise message
            sender = data.get('sender', 'unknown')
            severity = data.get('severity', 'high')
            violations = data.get('violations', [])
            
            msg = f"⚠️  CRITICAL: {sender} - {severity} severity violation"
            if violations:
                msg += f" ({len(violations)} rules violated)"
                
            # Use send-claude-message.sh for critical only
            send_script = Path(__file__).parent / 'send-claude-message.sh'
            if send_script.exists():
                subprocess.run([str(send_script), target, msg], capture_output=True)
                logger.info(f"Sent critical notification to {target}")
                
        except Exception as e:
            logger.error(f"Error sending critical notification: {e}")
            
    def run(self):
        """Run the state updater (blocking)"""
        logger.info("State updater running. Press Ctrl+C to stop.")
        try:
            # Keep running until interrupted
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down state updater...")
            self.bus.shutdown()

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/state_updater.log'),
            logging.StreamHandler()
        ]
    )
    
    # Ensure logs directory exists
    Path('logs').mkdir(exist_ok=True)
    
    # Run the updater
    updater = StateUpdater()
    updater.run()
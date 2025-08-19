#!/usr/bin/env python3
"""
Enhanced notification system for better coordination between agents and orchestrator.
Provides intelligent, context-aware messaging with priority levels and routing.
"""

import logging
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5

class NotificationType(Enum):
    STATUS_UPDATE = "status_update"
    CONFLICT_RESOLUTION = "conflict_resolution"
    EMERGENCY_ALERT = "emergency_alert"
    COORDINATION_REQUEST = "coordination_request"
    CYCLE_DETECTED = "cycle_detected"
    AUTHORIZATION_TIMEOUT = "authorization_timeout"
    PROJECT_COMPLETION = "project_completion"
    SYSTEM_HEALTH = "system_health"

@dataclass
class Notification:
    """Enhanced notification with context and routing"""
    id: str
    timestamp: datetime
    sender: str
    recipient: str
    notification_type: NotificationType
    priority: Priority
    subject: str
    message: str
    context: Dict[str, Any]
    requires_response: bool = False
    response_timeout_minutes: Optional[int] = None
    escalation_chain: Optional[List[str]] = None
    acknowledgment_required: bool = False

class EnhancedNotificationSystem:
    """Enhanced notification system with intelligent routing and context awareness"""
    
    def __init__(self, tmux_orchestrator_path: Path):
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.notification_log = tmux_orchestrator_path / 'registry' / 'logs' / 'notifications.jsonl'
        self.notification_log.parent.mkdir(parents=True, exist_ok=True)
        
        # Notification preferences and routing rules
        self.routing_rules = {
            NotificationType.EMERGENCY_ALERT: ['orchestrator'],
            NotificationType.CONFLICT_RESOLUTION: ['orchestrator', 'project_manager'],
            NotificationType.CYCLE_DETECTED: ['orchestrator'],
            NotificationType.AUTHORIZATION_TIMEOUT: ['orchestrator'],
            NotificationType.PROJECT_COMPLETION: ['orchestrator', 'project_manager'],
            NotificationType.SYSTEM_HEALTH: ['orchestrator']
        }
        
        # Priority-based message formatting
        self.priority_prefixes = {
            Priority.EMERGENCY: "🚨 EMERGENCY",
            Priority.CRITICAL: "🔥 CRITICAL",
            Priority.HIGH: "⚠️  HIGH PRIORITY",
            Priority.MEDIUM: "📋 MEDIUM",
            Priority.LOW: "ℹ️  INFO"
        }
        
        # Template library for common notification types
        self.message_templates = {
            NotificationType.CONFLICT_RESOLUTION: self._format_conflict_resolution,
            NotificationType.EMERGENCY_ALERT: self._format_emergency_alert,
            NotificationType.CYCLE_DETECTED: self._format_cycle_detection,
            NotificationType.AUTHORIZATION_TIMEOUT: self._format_authorization_timeout,
            NotificationType.PROJECT_COMPLETION: self._format_project_completion,
            NotificationType.SYSTEM_HEALTH: self._format_system_health
        }
    
    def send_notification(self, notification: Notification, session_name: str = None, 
                         window: int = None) -> bool:
        """Send an enhanced notification with intelligent routing"""
        try:
            # Log notification
            self._log_notification(notification)
            
            # Format message with context
            formatted_message = self._format_notification(notification)
            
            # Determine target window if not specified
            if not session_name or window is None:
                session_name, window = self._resolve_recipient_location(notification.recipient)
            
            # Send via tmux
            success = self._send_via_tmux(session_name, window, formatted_message)
            
            # Handle escalation if enabled
            if not success and notification.escalation_chain:
                return self._escalate_notification(notification)
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
    
    def send_conflict_resolution_notification(self, session_name: str, conflict_type: str, 
                                           resolution: Dict[str, Any], 
                                           affected_agents: List[str]) -> List[bool]:
        """Send conflict resolution notifications to affected agents"""
        results = []
        
        for agent in affected_agents:
            notification = Notification(
                id=f"conflict_{session_name}_{agent}_{datetime.now().timestamp()}",
                timestamp=datetime.now(),
                sender="coordination_system",
                recipient=agent,
                notification_type=NotificationType.CONFLICT_RESOLUTION,
                priority=Priority.HIGH,
                subject=f"Conflict Resolution: {conflict_type}",
                message="",  # Will be formatted by template
                context={
                    'conflict_type': conflict_type,
                    'resolution': resolution,
                    'session_name': session_name,
                    'other_agents': [a for a in affected_agents if a != agent]
                },
                acknowledgment_required=True
            )
            
            success = self.send_notification(notification, session_name)
            results.append(success)
        
        return results
    
    def send_cycle_detection_notification(self, session_name: str, cycle_info: Dict[str, Any],
                                        break_result: Dict[str, Any] = None) -> bool:
        """Send cycle detection notification to orchestrator"""
        notification = Notification(
            id=f"cycle_{session_name}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            sender="cycle_detector",
            recipient="orchestrator",
            notification_type=NotificationType.CYCLE_DETECTED,
            priority=Priority.CRITICAL,
            subject=f"Scheduling Cycle Detected: {cycle_info.get('type', 'Unknown')}",
            message="",  # Will be formatted by template
            context={
                'session_name': session_name,
                'cycle_info': cycle_info,
                'break_result': break_result
            },
            requires_response=True,
            response_timeout_minutes=10,
            escalation_chain=["project_manager"]
        )
        
        return self.send_notification(notification, session_name, 0)
    
    def send_emergency_alert(self, session_name: str, alert_type: str, details: str,
                           affected_agents: List[str] = None) -> bool:
        """Send emergency alert to orchestrator"""
        notification = Notification(
            id=f"emergency_{session_name}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            sender="monitoring_system",
            recipient="orchestrator", 
            notification_type=NotificationType.EMERGENCY_ALERT,
            priority=Priority.EMERGENCY,
            subject=f"Emergency: {alert_type}",
            message="",  # Will be formatted by template
            context={
                'session_name': session_name,
                'alert_type': alert_type,
                'details': details,
                'affected_agents': affected_agents or []
            },
            requires_response=True,
            response_timeout_minutes=5,
            acknowledgment_required=True
        )
        
        return self.send_notification(notification, session_name, 0)
    
    def send_coordination_request(self, session_name: str, requesting_agent: str,
                                target_agent: str, request_details: str,
                                priority: Priority = Priority.MEDIUM) -> bool:
        """Send coordination request between agents"""
        notification = Notification(
            id=f"coordination_{session_name}_{requesting_agent}_{target_agent}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            sender=requesting_agent,
            recipient=target_agent,
            notification_type=NotificationType.COORDINATION_REQUEST,
            priority=priority,
            subject=f"Coordination Request from {requesting_agent}",
            message=request_details,
            context={
                'session_name': session_name,
                'requesting_agent': requesting_agent,
                'request_details': request_details
            },
            requires_response=True,
            response_timeout_minutes=30,
            escalation_chain=["project_manager", "orchestrator"]
        )
        
        return self.send_notification(notification, session_name)
    
    def _format_notification(self, notification: Notification) -> str:
        """Format notification message using templates"""
        priority_prefix = self.priority_prefixes.get(notification.priority, "")
        timestamp = notification.timestamp.strftime("%H:%M:%S")
        
        # Use template if available
        if notification.notification_type in self.message_templates:
            template_func = self.message_templates[notification.notification_type]
            content = template_func(notification)
        else:
            content = notification.message
        
        header = f"{priority_prefix} - {notification.subject} [{timestamp}]"
        separator = "═" * min(len(header), 60)
        
        formatted_message = f"""{separator}
{header}
{separator}

{content}"""
        
        # Add response/acknowledgment requirements
        if notification.requires_response:
            timeout = notification.response_timeout_minutes or 30
            formatted_message += f"\n\n⏰ Response required within {timeout} minutes"
        
        if notification.acknowledgment_required:
            formatted_message += "\n\n✅ Please acknowledge receipt with 'ACK' or similar"
        
        return formatted_message
    
    def _format_conflict_resolution(self, notification: Notification) -> str:
        """Format conflict resolution notification"""
        context = notification.context
        resolution = context.get('resolution', {})
        conflict_type = context.get('conflict_type', 'Unknown')
        
        return f"""A {conflict_type} conflict has been automatically resolved:

🔧 Resolution: {resolution.get('message', 'Unknown resolution')}
📋 Action Taken: {resolution.get('action', 'Unknown action')}

Next Steps for {notification.recipient}:
{chr(10).join(f'• {step}' for step in resolution.get('next_steps', []))}

Other agents involved: {', '.join(context.get('other_agents', []))}

Please coordinate accordingly and confirm your status."""
    
    def _format_emergency_alert(self, notification: Notification) -> str:
        """Format emergency alert notification"""
        context = notification.context
        alert_type = context.get('alert_type', 'Unknown')
        details = context.get('details', 'No details provided')
        affected_agents = context.get('affected_agents', [])
        
        message = f"""EMERGENCY SITUATION DETECTED:

Alert Type: {alert_type}
Details: {details}
Session: {context.get('session_name', 'Unknown')}

"""
        
        if affected_agents:
            message += f"Affected Agents: {', '.join(affected_agents)}\n\n"
        
        message += """IMMEDIATE ACTION REQUIRED:
1. Assess the situation
2. Take corrective action
3. Report status immediately
4. Coordinate with affected agents if needed

This is an automated alert from the monitoring system."""
        
        return message
    
    def _format_cycle_detection(self, notification: Notification) -> str:
        """Format cycle detection notification"""
        context = notification.context
        cycle_info = context.get('cycle_info', {})
        break_result = context.get('break_result')
        
        message = f"""SCHEDULING CYCLE DETECTED:

Cycle Type: {cycle_info.get('type', 'Unknown')}
Description: {cycle_info.get('description', 'No description')}
Suggested Action: {cycle_info.get('suggested_action', 'Manual intervention required')}

"""
        
        if break_result:
            if break_result.get('success'):
                message += f"✅ AUTO-RESOLVED: {break_result.get('message', 'Cycle broken')}\n"
            else:
                message += f"❌ AUTO-RESOLUTION FAILED: {break_result.get('error', 'Unknown error')}\n"
                message += "MANUAL INTERVENTION REQUIRED\n"
        
        message += f"""
Session: {context.get('session_name', 'Unknown')}

Please verify the situation and take appropriate action."""
        
        return message
    
    def _format_authorization_timeout(self, notification: Notification) -> str:
        """Format authorization timeout notification"""
        context = notification.context
        return f"""AUTHORIZATION REQUEST TIMED OUT:

Agent: {context.get('waiting_agent', 'Unknown')}
Waiting For: {context.get('target_agent', 'Unknown')}
Request: {context.get('request_details', 'Unknown request')}
Wait Time: {context.get('wait_time_minutes', 'Unknown')} minutes

Please resolve this authorization bottleneck immediately."""
    
    def _format_project_completion(self, notification: Notification) -> str:
        """Format project completion notification"""
        context = notification.context
        return f"""PROJECT COMPLETION NOTIFICATION:

Project: {context.get('project_name', 'Unknown')}
Status: {context.get('completion_status', 'Unknown')}
Duration: {context.get('duration', 'Unknown')}
Tasks Completed: {context.get('tasks_completed', 'Unknown')}

Final report and cleanup actions may be required."""
    
    def _format_system_health(self, notification: Notification) -> str:
        """Format system health notification"""
        context = notification.context
        health_data = context.get('health_data', {})
        
        return f"""SYSTEM HEALTH UPDATE:

Overall Status: {health_data.get('status', 'Unknown')}
Active Projects: {health_data.get('active_projects', 'Unknown')}
Healthy Projects: {health_data.get('healthy_projects', 'Unknown')}
Issues Detected: {len(health_data.get('issues', []))}

Recent Issues:
{chr(10).join(f'• {issue}' for issue in health_data.get('issues', [])[:5])}"""
    
    def _resolve_recipient_location(self, recipient: str) -> tuple[str, int]:
        """Resolve recipient to session name and window"""
        # This would ideally query the session state to find the agent's location
        # For now, return defaults - this should be enhanced with actual agent lookup
        if recipient == "orchestrator":
            return "signalmatrix-event-delivery-architecture-impl-a9601f5d", 0
        else:
            # Would need to look up agent locations from session state
            return "signalmatrix-event-delivery-architecture-impl-a9601f5d", 1
    
    def _send_via_tmux(self, session_name: str, window: int, message: str) -> bool:
        """Send message via tmux to the specified window"""
        send_script = self.tmux_orchestrator_path / 'send-claude-message.sh'
        if not send_script.exists():
            logger.error("send-claude-message.sh script not found")
            return False
        
        try:
            result = subprocess.run([
                str(send_script),
                f"{session_name}:{window}",
                message
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Notification sent successfully to {session_name}:{window}")
                return True
            else:
                logger.error(f"Failed to send notification: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending notification via tmux: {e}")
            return False
    
    def _escalate_notification(self, notification: Notification) -> bool:
        """Escalate notification through escalation chain"""
        if not notification.escalation_chain:
            return False
        
        logger.info(f"Escalating notification {notification.id} through chain: {notification.escalation_chain}")
        
        for escalation_recipient in notification.escalation_chain:
            escalated_notification = Notification(
                id=f"escalated_{notification.id}",
                timestamp=datetime.now(),
                sender="notification_system",
                recipient=escalation_recipient,
                notification_type=notification.notification_type,
                priority=Priority.HIGH,  # Escalated notifications are high priority
                subject=f"ESCALATED: {notification.subject}",
                message=f"Original recipient ({notification.recipient}) did not respond.\n\n{notification.message}",
                context=notification.context,
                requires_response=True,
                response_timeout_minutes=15,  # Shorter timeout for escalated notifications
                acknowledgment_required=True
            )
            
            if self.send_notification(escalated_notification):
                return True
        
        return False
    
    def _log_notification(self, notification: Notification):
        """Log notification to file for auditing and analysis"""
        try:
            with open(self.notification_log, 'a') as f:
                log_entry = {
                    'id': notification.id,
                    'timestamp': notification.timestamp.isoformat(),
                    'sender': notification.sender,
                    'recipient': notification.recipient,
                    'type': notification.notification_type.value,
                    'priority': notification.priority.value,
                    'subject': notification.subject,
                    'requires_response': notification.requires_response,
                    'acknowledgment_required': notification.acknowledgment_required
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Error logging notification: {e}")
    
    def get_notification_statistics(self) -> Dict[str, Any]:
        """Get statistics about sent notifications"""
        stats = {
            'total_sent': 0,
            'by_type': {},
            'by_priority': {},
            'by_recipient': {},
            'requiring_response': 0,
            'requiring_acknowledgment': 0
        }
        
        try:
            if self.notification_log.exists():
                with open(self.notification_log, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                entry = json.loads(line.strip())
                                stats['total_sent'] += 1
                                
                                # Count by type
                                ntype = entry.get('type', 'unknown')
                                stats['by_type'][ntype] = stats['by_type'].get(ntype, 0) + 1
                                
                                # Count by priority
                                priority = entry.get('priority', 0)
                                stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1
                                
                                # Count by recipient
                                recipient = entry.get('recipient', 'unknown')
                                stats['by_recipient'][recipient] = stats['by_recipient'].get(recipient, 0) + 1
                                
                                # Count response/acknowledgment requirements
                                if entry.get('requires_response'):
                                    stats['requiring_response'] += 1
                                if entry.get('acknowledgment_required'):
                                    stats['requiring_acknowledgment'] += 1
                                    
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"Error calculating notification statistics: {e}")
        
        return stats
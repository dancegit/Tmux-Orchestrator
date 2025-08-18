#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///
"""
Email notification system for Tmux Orchestrator
Sends notifications when projects complete (batch or individual)
"""

import os
import smtplib
import logging
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class EmailNotifier:
    """Handles email notifications for project completion"""
    
    def __init__(self):
        """Initialize email notifier with settings from .env file"""
        # Load .env file from same directory as auto_orchestrate.py
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded email settings from {env_path}")
        else:
            logger.warning(f"No .env file found at {env_path}")
        
        # Get email settings from environment
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.sender_email = os.getenv('SENDER_EMAIL', self.smtp_username)
        self.recipient_email = os.getenv('RECIPIENT_EMAIL', self.smtp_username)
        self.use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        
        # Get optional subject prefix
        self.subject_prefix = os.getenv('EMAIL_SUBJECT_PREFIX', '').strip()
        if self.subject_prefix and not self.subject_prefix.endswith(' '):
            self.subject_prefix += ' '  # Add space if not present
        
        # Check if email is configured
        self.enabled = all([
            self.smtp_server,
            self.smtp_username,
            self.smtp_password,
            self.recipient_email
        ])
        
        if not self.enabled:
            logger.info("Email notifications disabled - missing configuration in .env file")
        else:
            logger.info(f"Email notifications enabled - will send to {self.recipient_email}")
    
    def send_project_completion_email(self, 
                                     project_name: str,
                                     spec_path: str,
                                     status: str = 'completed',
                                     error_message: Optional[str] = None,
                                     session_name: Optional[str] = None,
                                     duration_seconds: Optional[int] = None,
                                     batch_mode: bool = False,
                                     additional_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send email notification for project completion
        
        Args:
            project_name: Name of the project
            spec_path: Path to the specification file
            status: 'completed' or 'failed'
            error_message: Error message if failed
            session_name: Tmux session name
            duration_seconds: Time taken to complete
            batch_mode: Whether this was part of batch processing
            additional_info: Any additional information to include
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Email notifications disabled, skipping")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Set subject based on status
            if status == 'completed':
                subject = f"✅ Project Completed: {project_name}"
                status_emoji = "✅"
                status_text = "completed successfully"
            else:
                subject = f"❌ Project Failed: {project_name}"
                status_emoji = "❌"
                status_text = "failed"
            
            if batch_mode:
                subject = f"[Batch] {subject}"
            
            # Add configurable prefix if set
            if self.subject_prefix:
                subject = f"{self.subject_prefix}{subject}"
            
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Build email body
            body_lines = [
                f"Project Orchestration {status_text.title()}",
                "=" * 50,
                "",
                f"**Project**: {project_name}",
                f"**Status**: {status_emoji} {status_text}",
                f"**Specification**: {spec_path}",
            ]
            
            if session_name:
                body_lines.append(f"**Session**: {session_name}")
            
            if duration_seconds:
                hours = duration_seconds // 3600
                minutes = (duration_seconds % 3600) // 60
                seconds = duration_seconds % 60
                duration_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
                body_lines.append(f"**Duration**: {duration_str}")
            
            body_lines.extend([
                f"**Mode**: {'Batch Processing' if batch_mode else 'Individual'}",
                f"**Completed At**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                ""
            ])
            
            if error_message:
                body_lines.extend([
                    "**Error Details**:",
                    "-" * 30,
                    error_message,
                    ""
                ])
            
            if additional_info:
                body_lines.extend([
                    "**Additional Information**:",
                    "-" * 30
                ])
                for key, value in additional_info.items():
                    body_lines.append(f"  • {key}: {value}")
                body_lines.append("")
            
            # Add instructions for attaching to session
            if session_name and status == 'completed':
                body_lines.extend([
                    "**To attach to the running session**:",
                    f"```",
                    f"tmux attach -t {session_name}",
                    f"```",
                    ""
                ])
            
            # Add batch queue status if in batch mode
            if batch_mode:
                body_lines.extend([
                    "**Batch Processing Note**:",
                    "This project was processed as part of a batch queue.",
                    "The next project in queue (if any) will be processed automatically.",
                    ""
                ])
            
            body_lines.extend([
                "-" * 50,
                "Sent by Tmux Orchestrator Auto-Notification System"
            ])
            
            # Create plain text version
            text_body = "\n".join(body_lines)
            
            # Create HTML version (with better formatting)
            html_lines = [
                "<html><body>",
                f"<h2>Project Orchestration {status_text.title()}</h2>",
                "<table style='border-collapse: collapse;'>",
                f"<tr><td style='padding: 5px; font-weight: bold;'>Project:</td><td style='padding: 5px;'>{project_name}</td></tr>",
                f"<tr><td style='padding: 5px; font-weight: bold;'>Status:</td><td style='padding: 5px;'>{status_emoji} {status_text}</td></tr>",
                f"<tr><td style='padding: 5px; font-weight: bold;'>Specification:</td><td style='padding: 5px;'>{spec_path}</td></tr>",
            ]
            
            if session_name:
                html_lines.append(f"<tr><td style='padding: 5px; font-weight: bold;'>Session:</td><td style='padding: 5px;'>{session_name}</td></tr>")
            
            if duration_seconds:
                hours = duration_seconds // 3600
                minutes = (duration_seconds % 3600) // 60
                seconds = duration_seconds % 60
                duration_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
                html_lines.append(f"<tr><td style='padding: 5px; font-weight: bold;'>Duration:</td><td style='padding: 5px;'>{duration_str}</td></tr>")
            
            html_lines.extend([
                f"<tr><td style='padding: 5px; font-weight: bold;'>Mode:</td><td style='padding: 5px;'>{'Batch Processing' if batch_mode else 'Individual'}</td></tr>",
                f"<tr><td style='padding: 5px; font-weight: bold;'>Completed At:</td><td style='padding: 5px;'>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>",
                "</table>"
            ])
            
            if error_message:
                html_lines.extend([
                    "<h3>Error Details</h3>",
                    f"<pre style='background-color: #f0f0f0; padding: 10px;'>{error_message}</pre>"
                ])
            
            if additional_info:
                html_lines.append("<h3>Additional Information</h3><ul>")
                for key, value in additional_info.items():
                    html_lines.append(f"<li><strong>{key}:</strong> {value}</li>")
                html_lines.append("</ul>")
            
            if session_name and status == 'completed':
                html_lines.extend([
                    "<h3>To attach to the running session:</h3>",
                    f"<code style='background-color: #f0f0f0; padding: 5px;'>tmux attach -t {session_name}</code>"
                ])
            
            if batch_mode:
                html_lines.extend([
                    "<h3>Batch Processing Note</h3>",
                    "<p>This project was processed as part of a batch queue. ",
                    "The next project in queue (if any) will be processed automatically.</p>"
                ])
            
            html_lines.extend([
                "<hr>",
                "<p style='color: #666; font-size: 0.9em;'>Sent by Tmux Orchestrator Auto-Notification System</p>",
                "</body></html>"
            ])
            
            html_body = "\n".join(html_lines)
            
            # Attach parts
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent to {self.recipient_email} for project {project_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
    
    def send_batch_summary_email(self, 
                                completed_projects: list,
                                failed_projects: list,
                                total_duration_seconds: int) -> bool:
        """
        Send summary email for batch processing completion
        
        Args:
            completed_projects: List of successfully completed projects
            failed_projects: List of failed projects
            total_duration_seconds: Total time for batch processing
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            total_projects = len(completed_projects) + len(failed_projects)
            
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Set subject
            if failed_projects:
                subject = f"⚠️ Batch Processing Complete: {len(completed_projects)}/{total_projects} Succeeded"
            else:
                subject = f"✅ Batch Processing Complete: All {total_projects} Projects Succeeded"
            
            # Add configurable prefix if set
            if self.subject_prefix:
                subject = f"{self.subject_prefix}{subject}"
            
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Calculate duration
            hours = total_duration_seconds // 3600
            minutes = (total_duration_seconds % 3600) // 60
            seconds = total_duration_seconds % 60
            duration_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
            
            # Build email body
            body_lines = [
                "Batch Processing Summary",
                "=" * 50,
                "",
                f"**Total Projects**: {total_projects}",
                f"**Completed**: {len(completed_projects)} ✅",
                f"**Failed**: {len(failed_projects)} ❌",
                f"**Total Duration**: {duration_str}",
                f"**Completed At**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                ""
            ]
            
            if completed_projects:
                body_lines.extend([
                    "**Completed Projects**:",
                    "-" * 30
                ])
                for project in completed_projects:
                    body_lines.append(f"  ✅ {project}")
                body_lines.append("")
            
            if failed_projects:
                body_lines.extend([
                    "**Failed Projects**:",
                    "-" * 30
                ])
                for project in failed_projects:
                    body_lines.append(f"  ❌ {project}")
                body_lines.append("")
            
            body_lines.extend([
                "-" * 50,
                "Sent by Tmux Orchestrator Auto-Notification System"
            ])
            
            text_body = "\n".join(body_lines)
            
            # Create HTML version
            html_body = f"""
            <html><body>
            <h2>Batch Processing Summary</h2>
            <table style='border-collapse: collapse;'>
            <tr><td style='padding: 5px; font-weight: bold;'>Total Projects:</td><td style='padding: 5px;'>{total_projects}</td></tr>
            <tr><td style='padding: 5px; font-weight: bold;'>Completed:</td><td style='padding: 5px;'>{len(completed_projects)} ✅</td></tr>
            <tr><td style='padding: 5px; font-weight: bold;'>Failed:</td><td style='padding: 5px;'>{len(failed_projects)} ❌</td></tr>
            <tr><td style='padding: 5px; font-weight: bold;'>Total Duration:</td><td style='padding: 5px;'>{duration_str}</td></tr>
            <tr><td style='padding: 5px; font-weight: bold;'>Completed At:</td><td style='padding: 5px;'>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            </table>
            """
            
            if completed_projects:
                html_body += "<h3>Completed Projects</h3><ul>"
                for project in completed_projects:
                    html_body += f"<li>✅ {project}</li>"
                html_body += "</ul>"
            
            if failed_projects:
                html_body += "<h3>Failed Projects</h3><ul>"
                for project in failed_projects:
                    html_body += f"<li>❌ {project}</li>"
                html_body += "</ul>"
            
            html_body += """
            <hr>
            <p style='color: #666; font-size: 0.9em;'>Sent by Tmux Orchestrator Auto-Notification System</p>
            </body></html>
            """
            
            # Attach parts
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Batch summary email sent to {self.recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send batch summary email: {e}")
            return False


# Singleton instance
_email_notifier = None

def get_email_notifier() -> EmailNotifier:
    """Get or create the singleton email notifier instance"""
    global _email_notifier
    if _email_notifier is None:
        _email_notifier = EmailNotifier()
    return _email_notifier
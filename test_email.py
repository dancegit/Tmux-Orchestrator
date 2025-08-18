#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///
"""
Test email notification system for Tmux Orchestrator
"""

import sys
import time
from email_notifier import get_email_notifier

def test_email_notification():
    """Send a test email to verify configuration"""
    print("Testing Tmux Orchestrator Email Notification System...")
    print("-" * 50)
    
    # Get the email notifier instance
    notifier = get_email_notifier()
    
    # Check if email is configured
    if not notifier.enabled:
        print("❌ Email notifications are not configured!")
        print("\nTo configure email notifications:")
        print("1. Copy .env.example to .env")
        print("2. Edit .env with your email settings")
        print("3. For Gmail: Use an app-specific password")
        return False
    
    print(f"✅ Email configuration loaded")
    print(f"   SMTP Server: {notifier.smtp_server}:{notifier.smtp_port}")
    print(f"   Sender: {notifier.sender_email}")
    print(f"   Recipient: {notifier.recipient_email}")
    if notifier.subject_prefix:
        print(f"   Subject Prefix: '{notifier.subject_prefix}'")
    print()
    
    # Send test email for project completion
    print("Sending test project completion email...")
    success = notifier.send_project_completion_email(
        project_name="Test Project",
        spec_path="/path/to/test_spec.md",
        status="completed",
        session_name="test-session-123",
        duration_seconds=3665,  # 1 hour, 1 minute, 5 seconds
        batch_mode=False,
        additional_info={
            "Test Mode": "Email Configuration Test",
            "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "System": "Tmux Orchestrator v1.6.0"
        }
    )
    
    if success:
        print("✅ Test email sent successfully!")
        print(f"   Check your inbox at: {notifier.recipient_email}")
    else:
        print("❌ Failed to send test email")
        print("   Check the logs for error details")
        return False
    
    # Also test failure notification
    print("\nSending test failure notification...")
    success2 = notifier.send_project_completion_email(
        project_name="Test Failed Project",
        spec_path="/path/to/failed_spec.md",
        status="failed",
        error_message="This is a test error message to verify failure notifications are working correctly.\nError code: TEST_ERROR_123",
        session_name="test-failed-session",
        duration_seconds=1800,  # 30 minutes
        batch_mode=True
    )
    
    if success2:
        print("✅ Failure notification sent successfully!")
    else:
        print("❌ Failed to send failure notification")
    
    # Test batch summary email
    print("\nSending test batch summary email...")
    success3 = notifier.send_batch_summary_email(
        completed_projects=["Project A", "Project B", "Project C"],
        failed_projects=["Project D"],
        total_duration_seconds=7200  # 2 hours
    )
    
    if success3:
        print("✅ Batch summary email sent successfully!")
    else:
        print("❌ Failed to send batch summary email")
    
    print("\n" + "-" * 50)
    if success and success2 and success3:
        print("✅ All email tests passed!")
        print("\nEmail notifications are properly configured and working.")
        return True
    else:
        print("⚠️  Some email tests failed")
        print("Check your email configuration and try again.")
        return False

if __name__ == "__main__":
    # Enable logging to see detailed error messages
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    success = test_email_notification()
    sys.exit(0 if success else 1)
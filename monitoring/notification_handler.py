#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Advanced notification handler for compliance violations
Provides different notification levels and aggregation
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

class NotificationHandler:
    def __init__(self, orchestrator_session: str = "tmux-orc:0"):
        self.orchestrator_session = orchestrator_session
        self.script_dir = Path(__file__).parent
        self.registry_dir = self.script_dir.parent / "registry"
        self.notification_log = self.registry_dir / "logs" / "compliance" / "notifications.jsonl"
        self.notification_log.parent.mkdir(parents=True, exist_ok=True)
        
        # Track notifications to avoid spam
        self.recent_notifications = defaultdict(list)
        self.notification_threshold = 5  # Max notifications per rule per hour
        
    def send_violation_alert(self, violations: List[Dict[str, Any]], 
                           severity: str = "medium") -> bool:
        """Send violation alert to orchestrator"""
        
        # Check if we should send notification (rate limiting)
        if not self._should_notify(violations):
            return False
            
        # Format notification based on severity
        if severity == "critical":
            notification = self._format_critical_alert(violations)
        elif severity == "high":
            notification = self._format_high_alert(violations)
        else:
            notification = self._format_standard_alert(violations)
            
        # Send notification
        success = self._send_to_orchestrator(notification)
        
        # Log notification
        self._log_notification(violations, notification, success)
        
        return success
        
    def _should_notify(self, violations: List[Dict[str, Any]]) -> bool:
        """Check if we should send notification (rate limiting)"""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        for violation in violations:
            rule_id = violation.get('rule_id', 'unknown')
            
            # Clean old notifications
            self.recent_notifications[rule_id] = [
                t for t in self.recent_notifications[rule_id] 
                if t > hour_ago
            ]
            
            # Check threshold
            if len(self.recent_notifications[rule_id]) >= self.notification_threshold:
                return False
                
            # Add this notification
            self.recent_notifications[rule_id].append(now)
            
        return True
        
    def _format_critical_alert(self, violations: List[Dict[str, Any]]) -> str:
        """Format critical severity alert"""
        alert = "🚨 CRITICAL COMPLIANCE VIOLATION 🚨\\n\\n"
        
        for v in violations:
            alert += f"❌ {v['rule_description']}\\n"
            alert += f"   Severity: CRITICAL\\n"
            alert += f"   Details: {v['explanation']}\\n"
            alert += f"   Required Action: {v['correction']}\\n\\n"
            
        alert += "⚡ IMMEDIATE ACTION REQUIRED ⚡"
        return alert
        
    def _format_high_alert(self, violations: List[Dict[str, Any]]) -> str:
        """Format high severity alert"""
        alert = "⚠️  HIGH PRIORITY COMPLIANCE ALERT ⚠️\\n\\n"
        
        for v in violations[:3]:  # Limit to 3
            alert += f"• {v['rule_description']} ({v['severity']})\\n"
            
        if len(violations) > 3:
            alert += f"• ... and {len(violations) - 3} more violations\\n"
            
        alert += f"\\nAction: {violations[0].get('correction', 'Review compliance rules')}"
        return alert
        
    def _format_standard_alert(self, violations: List[Dict[str, Any]]) -> str:
        """Format standard severity alert"""
        alert = "📋 Compliance Notice\\n\\n"
        
        # Group by rule type
        by_category = defaultdict(list)
        for v in violations:
            category = v.get('rule_id', '').split('-')[0]
            by_category[category].append(v)
            
        for category, items in by_category.items():
            alert += f"{category.upper()}: {len(items)} violations\\n"
            
        alert += "\\nRun compliance report for details."
        return alert
        
    def _send_to_orchestrator(self, message: str) -> bool:
        """Send notification to orchestrator"""
        send_script = self.script_dir.parent / "send-claude-message.sh"
        
        if not send_script.exists():
            print(f"Warning: send-claude-message.sh not found")
            return False
            
        try:
            result = subprocess.run(
                [str(send_script), self.orchestrator_session, message],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Failed to send notification: {e}")
            return False
            
    def _log_notification(self, violations: List[Dict[str, Any]], 
                         notification: str, success: bool):
        """Log notification for audit trail"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "violations_count": len(violations),
            "rule_ids": [v.get('rule_id') for v in violations],
            "notification_sent": success,
            "notification_text": notification[:200]  # First 200 chars
        }
        
        with open(self.notification_log, 'a') as f:
            json.dump(log_entry, f)
            f.write('\n')
            
    def send_daily_summary(self):
        """Send daily compliance summary to orchestrator"""
        today = datetime.utcnow().date()
        violations_file = self.registry_dir / "logs" / "communications" / str(today) / "violations.jsonl"
        
        if not violations_file.exists():
            return
            
        # Count violations by type
        violation_counts = defaultdict(int)
        total_violations = 0
        
        with open(violations_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                    
                try:
                    entry = json.loads(line)
                    violations = entry.get('analysis', {}).get('violations', [])
                    total_violations += len(violations)
                    
                    for v in violations:
                        rule_id = v.get('rule_id', 'unknown')
                        violation_counts[rule_id] += 1
                except:
                    continue
                    
        if total_violations == 0:
            summary = "✅ Daily Compliance Report: No violations detected today!"
        else:
            summary = f"📊 Daily Compliance Report\\n\\n"
            summary += f"Total Violations: {total_violations}\\n\\n"
            
            # Top violations
            summary += "Top Rule Violations:\\n"
            for rule_id, count in sorted(violation_counts.items(), 
                                       key=lambda x: x[1], reverse=True)[:5]:
                summary += f"• {rule_id}: {count} violations\\n"
                
            summary += "\\nReview detailed logs for corrections."
            
        self._send_to_orchestrator(summary)
        
def main():
    """Test notification handler"""
    handler = NotificationHandler()
    
    # Test violation
    test_violations = [{
        "rule_id": "comm-001",
        "rule_description": "Developers must report to PM only",
        "severity": "high",
        "explanation": "Developer directly messaged Tester",
        "correction": "Route message through PM"
    }]
    
    success = handler.send_violation_alert(test_violations, severity="high")
    print(f"Test notification sent: {success}")

if __name__ == "__main__":
    main()
#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Continuous compliance monitoring service for Tmux Orchestrator
Watches communication logs and checks for rule violations
"""

import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Any, Set
import sys
import signal
import os

class ComplianceMonitor:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.registry_dir = self.script_dir.parent / "registry"
        self.logs_dir = self.registry_dir / "logs"
        self.processed_messages: Set[str] = set()
        self.running = True
        self.orchestrator_session = self._find_orchestrator_session()
        
    def _find_orchestrator_session(self) -> str:
        """Find the orchestrator's tmux session"""
        # Try common patterns
        patterns = ["orchestrator:0", "tmux-orc:0", "tmux-orchestrator:0"]
        
        # Check tmux sessions
        try:
            result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                sessions = result.stdout.strip().split('\n')
                for session in sessions:
                    if 'orchestrator' in session.lower() or 'orc' in session.lower():
                        return f"{session}:0"
        except:
            pass
            
        # Default fallback
        return "tmux-orc:0"
        
    def start(self):
        """Start the compliance monitoring service"""
        print(f"Starting compliance monitor...")
        print(f"Watching logs directory: {self.logs_dir}")
        print(f"Orchestrator session: {self.orchestrator_session}")
        print("Press Ctrl+C to stop")
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        while self.running:
            try:
                self._check_new_messages()
                time.sleep(5)  # Check every 5 seconds
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(10)
                
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print("\nShutting down compliance monitor...")
        self.running = False
        sys.exit(0)
        
    def _check_new_messages(self):
        """Check for new messages to analyze"""
        today = date.today().strftime("%Y-%m-%d")
        daily_log_dir = self.logs_dir / "communications" / today
        
        if not daily_log_dir.exists():
            return
            
        messages_file = daily_log_dir / "messages.jsonl"
        if not messages_file.exists():
            return
            
        # Check if there are new messages (trigger file)
        trigger_file = daily_log_dir / ".new_messages"
        if not trigger_file.exists():
            return
            
        # Remove trigger file
        trigger_file.unlink()
        
        # Process new messages
        self._process_message_log(messages_file)
        
    def _process_message_log(self, log_file: Path):
        """Process messages in the log file"""
        violations_file = log_file.parent / "violations.jsonl"
        
        with open(log_file, 'r') as f:
            for line_num, line in enumerate(f):
                if not line.strip():
                    continue
                    
                try:
                    message = json.loads(line)
                    message_id = f"{message['timestamp']}_{message['sender']['pane']}"
                    
                    # Skip if already processed
                    if message_id in self.processed_messages:
                        continue
                        
                    # Analyze message
                    analysis = self._analyze_message(message)
                    
                    # Mark as processed
                    self.processed_messages.add(message_id)
                    
                    # If violations found, log and notify
                    if not analysis.get('compliant', True):
                        self._handle_violation(message, analysis, violations_file)
                        
                except Exception as e:
                    print(f"Error processing line {line_num}: {e}")
                    
    def _analyze_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a message using the rule analyzer"""
        # Save message to temp file
        temp_file = self.script_dir / "temp_message.jsonl"
        with open(temp_file, 'w') as f:
            json.dump(message, f)
            f.write('\n')
            
        try:
            # Call rule analyzer
            result = subprocess.run(
                [str(self.script_dir / "rule_analyzer.py"), str(temp_file)],
                capture_output=True,
                text=True
            )
            
            # Read analysis result
            analysis_file = temp_file.parent / "compliance_analysis.jsonl"
            if analysis_file.exists():
                with open(analysis_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        analysis = json.loads(lines[-1])
                        analysis_file.unlink()  # Clean up
                        return analysis
                        
        except Exception as e:
            print(f"Error in analysis: {e}")
            
        finally:
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()
                
        # Return compliant if analysis fails
        return {"compliant": True, "error": "Analysis failed"}
        
    def _handle_violation(self, message: Dict[str, Any], analysis: Dict[str, Any], 
                         violations_file: Path):
        """Handle a compliance violation"""
        
        # Log violation
        violation_entry = {
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "message": message,
            "analysis": analysis,
            "notification_sent": False
        }
        
        with open(violations_file, 'a') as f:
            json.dump(violation_entry, f)
            f.write('\n')
            
        # Prepare notification for orchestrator
        self._notify_orchestrator(message, analysis)
        
        # Update violation entry
        violation_entry['notification_sent'] = True
        
    def _notify_orchestrator(self, message: Dict[str, Any], analysis: Dict[str, Any]):
        """Notify orchestrator of compliance violation"""
        
        # Build notification message
        violations = analysis.get('violations', [])
        if not violations:
            return
            
        # Create concise notification
        sender = message['sender']['pane']
        recipient = message['recipient']['pane']
        
        notification = f"⚠️  COMPLIANCE ALERT: {sender} → {recipient}\\n"
        
        for v in violations[:3]:  # Limit to first 3 violations
            notification += f"• {v['rule_description']} ({v['severity']})\\n"
            
        if len(violations) > 3:
            notification += f"• ... and {len(violations) - 3} more violations\\n"
            
        notification += f"\\nCorrection: {violations[0].get('correction', 'Follow hub-and-spoke model')}"
        
        # Send notification using send-claude-message.sh
        send_script = self.script_dir.parent / "send-claude-message.sh"
        if send_script.exists():
            try:
                subprocess.run(
                    [str(send_script), self.orchestrator_session, notification],
                    capture_output=True
                )
                print(f"Notified orchestrator about violation: {sender} → {recipient}")
            except Exception as e:
                print(f"Failed to notify orchestrator: {e}")
                
def main():
    """Run the compliance monitoring service"""
    
    # Check if already running
    pid_file = Path("/tmp/tmux_compliance_monitor.pid")
    if pid_file.exists():
        # Check if process is actually running
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            # Check if process exists
            os.kill(pid, 0)
            print("Compliance monitor is already running")
            sys.exit(0)
        except (ProcessLookupError, ValueError):
            # Process not running, remove stale pid file
            pid_file.unlink()
            
    # Write pid file
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
        
    try:
        monitor = ComplianceMonitor()
        monitor.start()
    finally:
        # Clean up pid file
        if pid_file.exists():
            pid_file.unlink()

if __name__ == "__main__":
    main()
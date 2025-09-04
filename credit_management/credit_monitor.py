#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Claude Code Credit Monitor
Monitors agent windows for credit exhaustion and manages pause/resume cycles
"""

import json
import subprocess
import re
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import logging

# Set UV_NO_WORKSPACE environment variable for all subprocess calls
os.environ['UV_NO_WORKSPACE'] = '1'
import sys

# Setup logging
log_dir = Path.home() / '.claude'
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'credit_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('credit_monitor')

class CreditMonitor:
    def __init__(self):
        self.data_dir = Path.home() / '.claude'
        self.data_dir.mkdir(exist_ok=True)
        self.schedule_file = self.data_dir / 'credit_schedule.json'
        self.load_schedule()
        
    def load_schedule(self):
        """Load or initialize credit schedule"""
        if self.schedule_file.exists():
            with open(self.schedule_file, 'r') as f:
                self.schedule = json.load(f)
        else:
            # Initialize with empty schedule
            self.schedule = {
                'last_known_reset': None,
                'next_reset_time': None,
                'fallback_cycle_hours': 5,
                'agents': {},
                'reset_history': []
            }
            self.save_schedule()
    
    def save_schedule(self):
        """Save credit schedule to disk"""
        with open(self.schedule_file, 'w') as f:
            json.dump(self.schedule, f, indent=2)
    
    def capture_pane_text(self, target: str, lines: int = 100) -> str:
        """Capture text from tmux pane"""
        try:
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', target, '-p', '-S', f'-{lines}'],
                capture_output=True,
                text=True
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception as e:
            logger.error(f"Failed to capture pane {target}: {e}")
            return ""
    
    def parse_reset_time_from_ui(self, pane_text: str) -> Optional[datetime]:
        """Parse reset time from Claude UI text"""
        # Look for patterns like "credits will reset at 11pm" or "credits will reset at 23:00"
        patterns = [
            r'credits will reset at (\d{1,2}):(\d{2})\s*(am|pm)?',
            r'credits will reset at (\d{1,2})(am|pm)',
            r'reset at (\d{1,2}):(\d{2})',
            r'reset at (\d{1,2})\s*(am|pm)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, pane_text, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) >= 2:
                        hour = int(groups[0])
                        minute = int(groups[1]) if groups[1] and groups[1].isdigit() else 0
                        
                        # Handle AM/PM
                        if len(groups) > 2 and groups[-1]:
                            am_pm = groups[-1].lower()
                            if am_pm == 'pm' and hour < 12:
                                hour += 12
                            elif am_pm == 'am' and hour == 12:
                                hour = 0
                    else:
                        # Just hour with am/pm
                        hour = int(groups[0])
                        minute = 0
                        if groups[1]:
                            am_pm = groups[1].lower()
                            if am_pm == 'pm' and hour < 12:
                                hour += 12
                            elif am_pm == 'am' and hour == 12:
                                hour = 0
                    
                    # Create datetime for today with parsed time
                    now = datetime.now()
                    reset_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    # If the time is in the past, assume it's tomorrow
                    if reset_time <= now:
                        reset_time += timedelta(days=1)
                    
                    logger.info(f"Parsed reset time from UI: {reset_time}")
                    return reset_time
                    
                except Exception as e:
                    logger.error(f"Failed to parse time from match: {match.group()}, error: {e}")
        
        return None
    
    def detect_credit_exhaustion(self, pane_text: str) -> Tuple[bool, Optional[str]]:
        """Detect if credits are exhausted or approaching limit"""
        exhaustion_indicators = [
            ('/upgrade', 'exhausted'),
            ('Approaching Opus usage limit', 'warning'),
            ('usage limit reached', 'exhausted'),
            ('out of credits', 'exhausted')
        ]
        
        for indicator, status in exhaustion_indicators:
            if indicator.lower() in pane_text.lower():
                return True, status
        
        return False, None
    
    def calculate_next_reset_fallback(self) -> datetime:
        """Calculate next reset time using 5-hour cycle as fallback"""
        if self.schedule.get('last_known_reset'):
            last_reset = datetime.fromisoformat(self.schedule['last_known_reset'])
            cycles_since = int((datetime.now() - last_reset).total_seconds() / 3600 / 5)
            next_reset = last_reset + timedelta(hours=5 * (cycles_since + 1))
            return next_reset
        else:
            # No known reset, assume next 5-hour boundary
            now = datetime.now()
            hour = now.hour
            next_boundary = ((hour // 5) + 1) * 5
            if next_boundary >= 24:
                next_boundary -= 24
                next_reset = (now + timedelta(days=1)).replace(hour=next_boundary, minute=0, second=0, microsecond=0)
            else:
                next_reset = now.replace(hour=next_boundary, minute=0, second=0, microsecond=0)
            return next_reset
    
    def update_fallback_schedule(self, actual_reset_time: datetime):
        """Update fallback schedule when we successfully parse a reset time"""
        logger.info(f"Updating fallback schedule with actual reset time: {actual_reset_time}")
        
        # Update the schedule
        self.schedule['last_known_reset'] = actual_reset_time.isoformat()
        self.schedule['next_reset_time'] = (actual_reset_time + timedelta(hours=5)).isoformat()
        
        # Add to history for pattern analysis
        self.schedule['reset_history'].append({
            'timestamp': datetime.now().isoformat(),
            'reset_time': actual_reset_time.isoformat()
        })
        
        # Keep only last 20 entries
        self.schedule['reset_history'] = self.schedule['reset_history'][-20:]
        
        self.save_schedule()
    
    def check_agent(self, session_window: str) -> Dict:
        """Check credit status for a specific agent"""
        pane_text = self.capture_pane_text(session_window)
        if not pane_text:
            return {'status': 'unknown', 'error': 'Could not capture pane'}
        
        # Check for exhaustion
        is_exhausted, exhaustion_status = self.detect_credit_exhaustion(pane_text)
        
        # Try to parse reset time from UI
        ui_reset_time = self.parse_reset_time_from_ui(pane_text)
        
        # Calculate next reset time
        if ui_reset_time:
            next_reset = ui_reset_time
            # Update our fallback schedule with this accurate info
            self.update_fallback_schedule(ui_reset_time)
        else:
            next_reset = self.calculate_next_reset_fallback()
        
        agent_status = {
            'status': exhaustion_status or 'active',
            'last_checked': datetime.now().isoformat(),
            'next_reset': next_reset.isoformat() if next_reset else None,
            'ui_reset_detected': ui_reset_time is not None
        }
        
        # Update agent record
        if session_window not in self.schedule['agents']:
            self.schedule['agents'][session_window] = {}
        
        self.schedule['agents'][session_window].update(agent_status)
        
        if is_exhausted and exhaustion_status == 'exhausted':
            self.schedule['agents'][session_window]['exhausted_at'] = datetime.now().isoformat()
            self.schedule['agents'][session_window]['scheduled_resume'] = next_reset.isoformat()
            # Also add to the returned status so schedule_resume can be called
            agent_status['scheduled_resume'] = next_reset.isoformat()
        
        return agent_status
    
    def get_active_agents(self) -> List[str]:
        """Get list of active tmux sessions with Claude agents"""
        try:
            # Get all tmux sessions
            result = subprocess.run(
                ['tmux', 'list-sessions', '-F', '#{session_name}'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return []
            
            sessions = result.stdout.strip().split('\n')
            agents = []
            
            # For each session, check windows for Claude
            for session in sessions:
                if not session:
                    continue
                    
                windows_result = subprocess.run(
                    ['tmux', 'list-windows', '-t', session, '-F', '#{window_index}:#{window_name}'],
                    capture_output=True,
                    text=True
                )
                
                if windows_result.returncode == 0:
                    for window in windows_result.stdout.strip().split('\n'):
                        if window:
                            idx, name = window.split(':', 1)
                            # Check if this window likely has Claude
                            target = f"{session}:{idx}"
                            pane_text = self.capture_pane_text(target, lines=20)
                            if 'claude' in pane_text.lower() or 'Human:' in pane_text:
                                agents.append(target)
            
            return agents
            
        except Exception as e:
            logger.error(f"Failed to get active agents: {e}")
            return []
    
    def monitor_all_agents(self):
        """Check all active agents for credit status"""
        # Skip if auto_orchestrate is running (setup in progress)
        try:
            result = subprocess.run(['pgrep', '-f', 'orchestration'], capture_output=True)
            if result.returncode == 0:
                logger.info("orchestration is running, skipping agent monitoring")
                return {}
        except:
            pass
            
        agents = self.get_active_agents()
        logger.info(f"Monitoring {len(agents)} active agents")
        
        statuses = {}
        for agent in agents:
            logger.info(f"Checking agent: {agent}")
            status = self.check_agent(agent)
            statuses[agent] = status
            
            # If exhausted, schedule resume
            if status['status'] == 'exhausted' and status.get('scheduled_resume'):
                self.schedule_resume(agent, status['scheduled_resume'])
        
        self.save_schedule()
        return statuses
    
    def schedule_resume(self, agent: str, resume_time: str):
        """Schedule agent resume at given time"""
        # Check if already scheduled
        if agent in self.schedule.get('agents', {}) and            self.schedule['agents'][agent].get('resume_scheduled'):
            logger.info(f"Resume already scheduled for {agent}, skipping duplicate")
            return
            
        resume_dt = datetime.fromisoformat(resume_time)
        
        # Add 2 minute buffer to ensure credits are available
        resume_dt += timedelta(minutes=2)
        
        # Get the orchestrator path
        orchestrator_path = Path(__file__).parent.parent.resolve()
        
        # Create resume script
        resume_script = self.data_dir / f'resume_{agent.replace(":", "_")}.sh'
        with open(resume_script, 'w') as f:
            f.write(f"""#!/bin/bash
# Auto-generated resume script for {agent}
ORCHESTRATOR_PATH="{orchestrator_path}"
"$ORCHESTRATOR_PATH/send-claude-message.sh" "{agent}" "Credits should be refreshed. Please continue your work where you left off."

# Verify credits are actually available
sleep 5
"$ORCHESTRATOR_PATH/credit_management/verify_credits.py" "{agent}"
""")
        
        resume_script.chmod(0o755)
        
        # Schedule with 'at' command if available, otherwise use simple background sleep
        at_time = resume_dt.strftime('%H:%M %Y-%m-%d')
        
        # Check if 'at' command is available
        at_check = subprocess.run(['which', 'at'], capture_output=True)
        
        if at_check.returncode == 0:
            try:
                subprocess.run(
                    ['at', at_time],
                    input=f'{resume_script}\n',
                    text=True,
                    capture_output=True
                )
                logger.info(f"Scheduled resume for {agent} at {at_time} using 'at' command")
            except Exception as e:
                logger.error(f"Failed to schedule with 'at': {e}")
        else:
            # Fallback to background sleep
            seconds_until = int((resume_dt - datetime.now()).total_seconds())
            if seconds_until > 0:
                subprocess.Popen(
                    ['bash', '-c', f'sleep {seconds_until} && {resume_script}'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info(f"Scheduled resume for {agent} in {seconds_until} seconds using background sleep")

def main():
    """Main monitoring loop or single check based on arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Claude Code Credit Monitor')
    parser.add_argument('--once', action='store_true', 
                       help='Run once and exit instead of continuous monitoring')
    parser.add_argument('--interval', type=int, default=5,
                       help='Check interval in minutes (default: 5)')
    args = parser.parse_args()
    
    monitor = CreditMonitor()
    
    if args.once:
        # Single check mode
        statuses = monitor.monitor_all_agents()
        
        # Print summary
        exhausted = sum(1 for s in statuses.values() if s['status'] == 'exhausted')
        warning = sum(1 for s in statuses.values() if s['status'] == 'warning')
        active = sum(1 for s in statuses.values() if s['status'] == 'active')
        
        print(f"\nCredit Status Summary:")
        print(f"  Active: {active}")
        print(f"  Warning: {warning}")
        print(f"  Exhausted: {exhausted}")
        
        if monitor.schedule.get('next_reset_time'):
            next_reset = datetime.fromisoformat(monitor.schedule['next_reset_time'])
            if next_reset > datetime.now():
                delta = next_reset - datetime.now()
                hours = int(delta.total_seconds() // 3600)
                minutes = int((delta.total_seconds() % 3600) // 60)
                print(f"\nNext reset in approximately {hours}h {minutes}m")
        
        return
    
    # Continuous monitoring mode
    check_interval = args.interval
    logger.info(f"Starting credit monitor with {check_interval} minute interval")
    logger.info("Press Ctrl+C to stop monitoring")
    
    while True:
        try:
            statuses = monitor.monitor_all_agents()
            
            # Log summary
            exhausted = sum(1 for s in statuses.values() if s['status'] == 'exhausted')
            warning = sum(1 for s in statuses.values() if s['status'] == 'warning')
            active = sum(1 for s in statuses.values() if s['status'] == 'active')
            
            logger.info(f"Status: {active} active, {warning} warning, {exhausted} exhausted")
            
            # Sleep until next check
            logger.info(f"Next check in {check_interval} minutes...")
            time.sleep(check_interval * 60)
            
        except KeyboardInterrupt:
            logger.info("\nMonitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            logger.info("Retrying in 60 seconds...")
            time.sleep(60)  # Wait a minute before retrying

if __name__ == '__main__':
    main()
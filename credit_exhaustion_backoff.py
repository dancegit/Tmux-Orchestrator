#!/usr/bin/env python3
"""
Credit exhaustion backoff handler for Tmux Orchestrator.
Prevents hammering agents when they're out of credits or showing /upgrade messages.
"""

import subprocess
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CreditExhaustionBackoff:
    """Manages exponential backoff for credit-exhausted agents"""
    
    def __init__(self, tmux_orchestrator_path: Path):
        self.tmux_orchestrator_path = tmux_orchestrator_path
        # Track backoff state per session/window
        self.backoff_tracker = {}  # {session:window: {'last_check': timestamp, 'backoff_minutes': int, 'consecutive_exhausted': int}}
        
        # Backoff configuration
        self.initial_backoff_minutes = 5
        self.max_backoff_minutes = 120  # 2 hours max
        self.backoff_multiplier = 2
        self.recovery_threshold_minutes = 30  # Reset backoff if no issues for this long
        
        # Credit exhaustion indicators
        self.exhaustion_indicators = [
            '/upgrade',
            'Approaching Opus usage limit',
            'usage limit reached',
            'out of credits',
            'credit limit',
            'credits exhausted',
            'upgrade your plan'
        ]
        
    def detect_credit_exhaustion(self, session_window: str) -> Tuple[bool, Optional[str]]:
        """Check if a window shows credit exhaustion"""
        try:
            # Capture recent pane content
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', session_window, '-p', '-S', '-50'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return False, None
                
            pane_text = result.stdout.lower()
            
            # Check for exhaustion indicators
            for indicator in self.exhaustion_indicators:
                if indicator.lower() in pane_text:
                    logger.info(f"Credit exhaustion detected in {session_window}: found '{indicator}'")
                    return True, indicator
                    
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking credit exhaustion for {session_window}: {e}")
            return False, None
    
    def should_send_checkin(self, session_window: str) -> Tuple[bool, Optional[int]]:
        """Determine if we should send a check-in based on backoff state"""
        now = datetime.now()
        
        # Check for credit exhaustion
        is_exhausted, indicator = self.detect_credit_exhaustion(session_window)
        
        # Get or create tracker entry
        if session_window not in self.backoff_tracker:
            self.backoff_tracker[session_window] = {
                'last_check': now,
                'backoff_minutes': 0,
                'consecutive_exhausted': 0
            }
        
        tracker = self.backoff_tracker[session_window]
        time_since_last = (now - tracker['last_check']).total_seconds() / 60
        
        if is_exhausted:
            # Credit exhausted - apply exponential backoff
            if tracker['consecutive_exhausted'] == 0:
                # First detection
                tracker['consecutive_exhausted'] = 1
                tracker['backoff_minutes'] = self.initial_backoff_minutes
                tracker['last_check'] = now
                logger.warning(f"Initial credit exhaustion detected for {session_window}, backing off {tracker['backoff_minutes']} minutes")
                return False, tracker['backoff_minutes']
            else:
                # Already in backoff
                if time_since_last < tracker['backoff_minutes']:
                    # Still in backoff period
                    remaining = int(tracker['backoff_minutes'] - time_since_last)
                    logger.debug(f"{session_window} still in backoff, {remaining} minutes remaining")
                    return False, remaining
                else:
                    # Backoff period expired, but still exhausted - increase backoff
                    tracker['consecutive_exhausted'] += 1
                    tracker['backoff_minutes'] = min(
                        tracker['backoff_minutes'] * self.backoff_multiplier,
                        self.max_backoff_minutes
                    )
                    tracker['last_check'] = now
                    logger.warning(f"{session_window} still exhausted after {tracker['consecutive_exhausted']} checks, "
                                 f"increasing backoff to {tracker['backoff_minutes']} minutes")
                    return False, tracker['backoff_minutes']
        else:
            # Not exhausted
            if tracker['consecutive_exhausted'] > 0:
                # Was exhausted before
                if time_since_last >= self.recovery_threshold_minutes:
                    # Enough time has passed - reset backoff
                    logger.info(f"{session_window} recovered from credit exhaustion, resetting backoff")
                    tracker['consecutive_exhausted'] = 0
                    tracker['backoff_minutes'] = 0
                    tracker['last_check'] = now
                    return True, None
                else:
                    # Recent recovery - allow but don't reset yet
                    logger.debug(f"{session_window} appears recovered but waiting for full recovery period")
                    return True, None
            else:
                # Normal state
                return True, None
    
    def get_backoff_status(self) -> Dict[str, Dict]:
        """Get current backoff status for all tracked windows"""
        now = datetime.now()
        status = {}
        
        for session_window, tracker in self.backoff_tracker.items():
            time_since_last = (now - tracker['last_check']).total_seconds() / 60
            remaining = max(0, tracker['backoff_minutes'] - time_since_last)
            
            status[session_window] = {
                'consecutive_exhausted': tracker['consecutive_exhausted'],
                'backoff_minutes': tracker['backoff_minutes'],
                'remaining_minutes': int(remaining) if remaining > 0 else 0,
                'in_backoff': remaining > 0 and tracker['consecutive_exhausted'] > 0
            }
        
        return status
    
    def reset_backoff(self, session_window: str):
        """Manually reset backoff for a window"""
        if session_window in self.backoff_tracker:
            logger.info(f"Manually resetting backoff for {session_window}")
            self.backoff_tracker[session_window] = {
                'last_check': datetime.now(),
                'backoff_minutes': 0,
                'consecutive_exhausted': 0
            }


def main():
    """Test credit exhaustion detection"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python credit_exhaustion_backoff.py <session:window>")
        sys.exit(1)
    
    session_window = sys.argv[1]
    backoff = CreditExhaustionBackoff(Path.cwd())
    
    # Check exhaustion
    is_exhausted, indicator = backoff.detect_credit_exhaustion(session_window)
    print(f"Credit exhaustion check for {session_window}:")
    print(f"  Exhausted: {is_exhausted}")
    print(f"  Indicator: {indicator}")
    
    # Check if should send
    should_send, backoff_minutes = backoff.should_send_checkin(session_window)
    print(f"  Should send check-in: {should_send}")
    print(f"  Backoff minutes: {backoff_minutes}")
    
    # Show all status
    print("\nBackoff status:")
    for window, status in backoff.get_backoff_status().items():
        print(f"  {window}: {status}")


if __name__ == '__main__':
    main()
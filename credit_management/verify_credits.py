#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Verify if credits are actually available after a resume attempt
"""

import sys
import subprocess
import time
import logging
from pathlib import Path
import os

# Set UV_NO_WORKSPACE environment variable for all subprocess calls
os.environ['UV_NO_WORKSPACE'] = '1'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('verify_credits')

def verify_agent_credits(agent: str, max_retries: int = 3):
    """Verify if agent actually has credits available"""
    
    orchestrator_dir = Path(__file__).parent.parent
    send_script = orchestrator_dir / 'send-claude-message.sh'
    
    for attempt in range(max_retries):
        if attempt > 0:
            wait_time = 5 * (attempt + 1)  # 10, 15 seconds
            logger.info(f"Retry {attempt} - waiting {wait_time} seconds")
            time.sleep(wait_time)
        
        # Capture current pane state
        result = subprocess.run(
            ['tmux', 'capture-pane', '-t', agent, '-p', '-S', '-50'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to capture pane for {agent}")
            continue
        
        pane_text = result.stdout
        
        # Check if still exhausted
        if '/upgrade' in pane_text:
            logger.warning(f"Agent {agent} still showing /upgrade - credits not yet available")
            
            # Try to parse new reset time
            if 'credits will reset at' in pane_text:
                logger.info("Found new reset time in UI - will be handled by monitor")
            
            # Send a gentle probe message
            subprocess.run([
                str(send_script),
                agent,
                "Checking credit availability..."
            ])
            
        else:
            # No /upgrade message - credits might be available
            logger.info(f"Agent {agent} appears to have credits available")
            
            # Send resume confirmation
            subprocess.run([
                str(send_script),
                agent,
                "Credits confirmed available. Resuming normal operations. Please continue with your assigned tasks."
            ])
            
            return True
    
    # Failed after all retries
    logger.error(f"Agent {agent} still exhausted after {max_retries} attempts")
    
    # Schedule another check in 1 hour
    subprocess.run([
        str(orchestrator_dir / 'schedule_with_note.sh'),
        '60',
        'Retry credit verification',
        agent
    ])
    
    return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: verify_credits.py <session:window>")
        sys.exit(1)
    
    agent = sys.argv[1]
    success = verify_agent_credits(agent)
    sys.exit(0 if success else 1)
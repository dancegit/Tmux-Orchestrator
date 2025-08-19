#!/usr/bin/env python3
"""
Manually terminate the stuck signalmatrix project and start the next in queue.
This handles the current broken state where the timeout system didn't work properly.
"""

import subprocess
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from project_failure_handler import ProjectFailureHandler
from session_state import SessionStateManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Manually handle the stuck signalmatrix project"""
    tmux_orch_path = Path(__file__).parent
    
    # Session details
    session_name = "signalmatrix-event-delivery-architecture-impl-a9601f5d"
    project_name = "Signalmatrix Event Delivery Architecture"
    
    logger.info("=== MANUAL TIMEOUT TERMINATION ===")
    logger.info(f"Target session: {session_name}")
    logger.info(f"Project: {project_name}")
    
    # Load session state
    state_manager = SessionStateManager(tmux_orch_path)
    state = state_manager.load_session_state(project_name)
    
    if not state:
        logger.error(f"No session state found for {project_name}")
        return False
    
    logger.info(f"Session state loaded - current status: {state.completion_status}")
    
    # Initialize failure handler
    handler = ProjectFailureHandler(tmux_orch_path)
    
    # Manually trigger timeout failure handling
    logger.info("Triggering manual timeout failure handling...")
    
    try:
        success = handler.handle_timeout_failure(project_name, state)
        if success:
            logger.info("✅ Manual timeout handling completed successfully")
            
            # Verify session is gone
            result = subprocess.run(['tmux', 'has-session', '-t', session_name], capture_output=True)
            if result.returncode == 0:
                logger.warning("⚠️  Session still exists - attempting force cleanup")
                
                # Force kill with SIGKILL if needed
                try:
                    subprocess.run(['tmux', 'kill-session', '-t', session_name], capture_output=True, timeout=5)
                    logger.info("Force killed session")
                except:
                    logger.error("Failed to force kill session")
            else:
                logger.info("✅ Verified session is terminated")
            
            # Check scheduled tasks are removed
            try:
                conn = sqlite3.connect(str(tmux_orch_path / 'task_queue.db'))
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE session_name = ?", (session_name,))
                task_count = cursor.fetchone()[0]
                conn.close()
                
                if task_count == 0:
                    logger.info("✅ All scheduled tasks removed")
                else:
                    logger.warning(f"⚠️  {task_count} scheduled tasks still exist")
            except Exception as e:
                logger.error(f"Could not check scheduled tasks: {e}")
            
            # Check next project in queue
            try:
                from scheduler import TmuxOrchestratorScheduler
                scheduler = TmuxOrchestratorScheduler()
                next_project = scheduler.get_next_project()
                
                if next_project:
                    logger.info(f"✅ Next project in queue: {next_project['spec_path']}")
                    logger.info("The next project should start automatically")
                else:
                    logger.info("ℹ️  No more projects in queue")
            except Exception as e:
                logger.error(f"Could not check queue: {e}")
                
        else:
            logger.error("❌ Manual timeout handling failed")
            return False
            
    except Exception as e:
        logger.error(f"Error during manual timeout handling: {e}")
        return False
    
    logger.info("=== MANUAL TERMINATION COMPLETE ===")
    return True

if __name__ == "__main__":
    main()
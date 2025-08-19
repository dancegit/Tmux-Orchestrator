#!/usr/bin/env python3
"""
Manually start the next project in queue using the improved failure handler system
"""

import logging
from pathlib import Path
from project_failure_handler import ProjectFailureHandler

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Start the next project using the improved orchestration system"""
    tmux_orch_path = Path(__file__).parent
    handler = ProjectFailureHandler(tmux_orch_path)
    
    # Get next project from queue
    try:
        from scheduler import TmuxOrchestratorScheduler
        scheduler = TmuxOrchestratorScheduler()
        next_project = scheduler.get_next_project()
        
        if not next_project:
            logger.info("No projects in queue")
            return
        
        logger.info(f"Starting project ID {next_project['id']}: {next_project['spec_path']}")
        
        # Mark as processing
        scheduler.update_project_status(next_project['id'], 'processing')
        
        # Use improved trigger method
        handler._trigger_next_orchestration(next_project)
        
        logger.info("Project startup initiated")
        
    except Exception as e:
        logger.error(f"Failed to start project: {e}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Mark a project as completed in the queue
"""

import sys
from scheduler import TmuxOrchestratorScheduler

def main():
    if len(sys.argv) != 2:
        print("Usage: mark_project_complete.py <project_id>")
        sys.exit(1)
    
    project_id = int(sys.argv[1])
    
    # Initialize scheduler
    scheduler = TmuxOrchestratorScheduler()
    
    # Mark project as complete
    scheduler.mark_project_complete(project_id, success=True)
    print(f"Project {project_id} marked as completed")
    
    # Cleanup
    scheduler.conn.close()

if __name__ == "__main__":
    main()
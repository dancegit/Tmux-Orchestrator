#!/usr/bin/env python3
"""Reset a project in the queue to be reprocessed"""

import sqlite3
import sys

if len(sys.argv) != 2:
    print("Usage: python3 reset_project.py <project_id>")
    sys.exit(1)

project_id = int(sys.argv[1])

conn = sqlite3.connect('task_queue.db')
cursor = conn.cursor()

# Reset the project status to queued
cursor.execute("""
    UPDATE project_queue 
    SET status = 'queued',
        started_at = NULL,
        completed_at = NULL,
        error_message = NULL,
        orchestrator_session = NULL,
        main_session = NULL
    WHERE id = ?
""", (project_id,))

if cursor.rowcount > 0:
    conn.commit()
    print(f"Project {project_id} has been reset to 'queued' status")
else:
    print(f"Project {project_id} not found")

conn.close()
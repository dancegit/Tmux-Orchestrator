#!/usr/bin/env python3
"""Update a project to request fresh start (overwrite)"""

import sqlite3
import sys

if len(sys.argv) != 2:
    print("Usage: python3 update_project_fresh_start.py <project_id>")
    sys.exit(1)

project_id = int(sys.argv[1])

conn = sqlite3.connect('task_queue.db')
cursor = conn.cursor()

# First check if fresh_start column exists, if not add it
try:
    cursor.execute("ALTER TABLE project_queue ADD COLUMN fresh_start INTEGER DEFAULT 0")
    conn.commit()
    print("Added fresh_start column to project_queue table")
except sqlite3.OperationalError:
    # Column already exists
    pass

# Update the project to request fresh start
cursor.execute("""
    UPDATE project_queue 
    SET fresh_start = 1
    WHERE id = ?
""", (project_id,))

if cursor.rowcount > 0:
    conn.commit()
    print(f"Project {project_id} marked for fresh start (overwrite)")
else:
    print(f"Project {project_id} not found")

conn.close()
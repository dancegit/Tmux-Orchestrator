#!/usr/bin/env python3
"""
Add projects to the queue directly without starting a new scheduler.
"""
import sqlite3
import time
from pathlib import Path
import uuid

def add_project_to_queue(spec_path, project_path=None):
    """Add a project to the queue directly."""
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    
    # Default project path to spec directory
    if not project_path:
        project_path = str(Path(spec_path).parent)
    
    # Generate batch ID
    batch_id = str(uuid.uuid4())
    
    # Insert into queue
    cursor.execute("""
    INSERT INTO project_queue (spec_path, project_path, status, batch_id)
    VALUES (?, ?, 'queued', ?)
    """, (spec_path, project_path, batch_id))
    
    project_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return project_id, batch_id

# Add the two projects
mobile_id, mobile_batch = add_project_to_queue(
    "/home/clauderun/mobile_app_spec_v2/MOBILE_APP_SPEC_V2.md",
    "/home/clauderun/mobile_app_spec_v2"
)
print(f"✓ Added Mobile App Spec V2 to queue (ID: {mobile_id}, Batch: {mobile_batch})")

mcp_id, mcp_batch = add_project_to_queue(
    "/home/clauderun/mcp_server_spec_v2/MCP_SERVER_SPEC_V2.md", 
    "/home/clauderun/mcp_server_spec_v2"
)
print(f"✓ Added MCP Server Spec V2 to queue (ID: {mcp_id}, Batch: {mcp_batch})")

print("\nProjects successfully queued! The daemon scheduler will process them automatically.")
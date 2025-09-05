#!/usr/bin/env python3
"""
Add projects to the queue directly without starting a new scheduler.

Usage:
    python3 add_to_queue.py <spec_path> [project_path]
    
Examples:
    python3 add_to_queue.py /path/to/spec.md
    python3 add_to_queue.py /path/to/spec.md /path/to/project/dir
"""
import sys
import sqlite3
import time
from pathlib import Path
import uuid

def add_project_to_queue(spec_path, project_path=None):
    """Add a project to the queue directly."""
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    
    # Validate spec path exists
    spec_path = Path(spec_path).resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")
    
    # Default project path to spec directory's parent or use provided path
    if not project_path:
        # For batch specs, use the batch_projects directory
        if 'batch_specs' in str(spec_path):
            project_name = spec_path.stem
            project_path = spec_path.parent.parent / 'batch_projects' / project_name
            project_path.mkdir(parents=True, exist_ok=True)
        else:
            project_path = spec_path.parent
    else:
        project_path = Path(project_path).resolve()
        project_path.mkdir(parents=True, exist_ok=True)
    
    # Generate batch ID
    batch_id = str(uuid.uuid4())
    
    # Extract project name from spec
    project_name = spec_path.stem.replace('_', ' ').title()
    
    # Insert into queue
    cursor.execute("""
    INSERT INTO project_queue (spec_path, project_path, status, batch_id)
    VALUES (?, ?, 'queued', ?)
    """, (str(spec_path), str(project_path), batch_id))
    
    project_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return project_id, batch_id, project_name

def main():
    """Main entry point for command-line usage."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    spec_path = sys.argv[1]
    project_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        project_id, batch_id, project_name = add_project_to_queue(spec_path, project_path)
        print(f"✓ Added {project_name} to queue")
        print(f"  Project ID: {project_id}")
        print(f"  Batch ID: {batch_id}")
        print(f"  Spec: {spec_path}")
        if project_path:
            print(f"  Project Dir: {project_path}")
        print("\nProject successfully queued! The daemon scheduler will process it automatically.")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to add project to queue: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
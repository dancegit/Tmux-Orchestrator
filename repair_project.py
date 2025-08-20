#!/usr/bin/env python3
"""
Project Repair Tool - Based on Grok's recommendations
Repairs git repositories, missing agents, and corrupted session state for resume functionality
"""

import subprocess
import json
import shutil
from pathlib import Path
from datetime import datetime
import sys

def repair_git_repo(project_path: Path, original_remote_url: str = None):
    """Idempotently repairs or initializes git repo."""
    print(f"🔧 Repairing git repository in {project_path}")
    
    try:
        # Check if repo exists
        result = subprocess.run(['git', '-C', str(project_path), 'rev-parse', '--is-inside-work-tree'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Git repo exists - validating remote...")
        else:
            raise subprocess.CalledProcessError(result.returncode, "git rev-parse")
    except subprocess.CalledProcessError:
        # Init if missing
        print("🔄 No git repo found - initializing...")
        subprocess.run(['git', '-C', str(project_path), 'init'], check=True)
        subprocess.run(['git', '-C', str(project_path), 'checkout', '-b', 'main'], check=True)

    # Repair remote if missing
    try:
        result = subprocess.run(['git', '-C', str(project_path), 'remote', 'show', 'origin'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Origin remote exists")
        else:
            raise subprocess.CalledProcessError(result.returncode, "git remote show")
    except subprocess.CalledProcessError:
        if original_remote_url:
            print(f"🔄 Adding missing origin: {original_remote_url}")
            subprocess.run(['git', '-C', str(project_path), 'remote', 'add', 'origin', original_remote_url], check=True)
        else:
            print("⚠️  No remote URL provided - initializing as local-only repo")
            # Create initial commit if needed
            try:
                subprocess.run(['git', '-C', str(project_path), 'log', '--oneline', '-1'], 
                             capture_output=True, check=True)
                print("✅ Repo has commits")
            except subprocess.CalledProcessError:
                print("🔄 Creating initial commit...")
                subprocess.run(['git', '-C', str(project_path), 'add', '.'], check=True)
                subprocess.run(['git', '-C', str(project_path), 'commit', '-m', 'Initial commit from repair'], check=True)

    # Safe fetch with fallback (only if remote exists)
    try:
        result = subprocess.run(['git', '-C', str(project_path), 'remote'], capture_output=True, text=True)
        if 'origin' in result.stdout:
            print("🔄 Attempting to fetch from origin...")
            subprocess.run(['git', '-C', str(project_path), 'fetch', 'origin'], check=True)
            print("✅ Git fetch successful")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Git fetch failed: {e} - Continuing with local-only mode")

def repair_missing_agents(registry_path: Path, expected_agents: list[str]):
    """Repair missing agents in session state"""
    print(f"🔧 Repairing missing agents in {registry_path}")
    
    state_file = registry_path / 'session_state.json'
    
    if not state_file.exists():
        print("⚠️  Session state file missing - creating new one")
        initial_state = {
            'session_name': f"repaired-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'project_name': 'Repaired Project',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'agents': {}
        }
    else:
        try:
            with open(state_file, 'r') as f:
                initial_state = json.load(f)
            print("✅ Loaded existing session state")
        except Exception as e:
            print(f"⚠️  Corrupted session state: {e} - Creating new one")
            initial_state = {
                'session_name': f"repaired-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                'project_name': 'Repaired Project',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'agents': {}
            }
    
    # Ensure agents dict exists
    if 'agents' not in initial_state:
        initial_state['agents'] = {}
    
    # Check for missing agents
    missing = [agent for agent in expected_agents if agent not in initial_state['agents']]
    
    if missing:
        print(f"🔄 Missing agents: {missing} - Recreating with defaults...")
        for agent in missing:
            initial_state['agents'][agent] = {
                'name': agent,
                'role': agent,
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'last_activity': datetime.now().isoformat(),
                'tasks_completed': 0,
                'current_task': None
            }
        
        # Update timestamp
        initial_state['updated_at'] = datetime.now().isoformat()
        
        # Save repaired state
        with open(state_file, 'w') as f:
            json.dump(initial_state, f, indent=2)
        print(f"✅ Repaired agents: {missing}")
    else:
        print("✅ All expected agents present")

def repair_project(project_id: int):
    """Main repair function for a project"""
    print(f"🚀 Starting repair for project {project_id}")
    
    # Get project details from database
    import sqlite3
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    cursor.execute('SELECT spec_path, project_path FROM project_queue WHERE id = ?', (project_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        print(f"❌ Project {project_id} not found in database")
        return False
    
    spec_path, project_path = result
    project_path = Path(project_path) if project_path else Path(spec_path).parent
    
    print(f"📋 Project details:")
    print(f"   Spec: {spec_path}")
    print(f"   Path: {project_path}")
    
    # Create project directory if missing
    project_path.mkdir(parents=True, exist_ok=True)
    
    # 1. Repair git repository
    repair_git_repo(project_path)
    
    # 2. Repair registry entries
    registry_path = Path('registry/projects') / f"project-{project_id}"
    registry_path.mkdir(parents=True, exist_ok=True)
    
    # 3. Repair missing agents (common agents for web server project)
    expected_agents = ['orchestrator', 'developer', 'sysadmin', 'tester']
    repair_missing_agents(registry_path, expected_agents)
    
    print(f"✅ Project {project_id} repair completed")
    return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: repair_project.py <project_id>")
        sys.exit(1)
    
    project_id = int(sys.argv[1])
    success = repair_project(project_id)
    sys.exit(0 if success else 1)
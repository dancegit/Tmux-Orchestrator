# Tmux Orchestrator System Improvement Specification

## Executive Summary

This specification documents comprehensive improvements to the Tmux Orchestrator system based on expert analysis and discussion. The improvements focus on four critical areas: scheduling reliability, git synchronization, dynamic team composition, and concurrent orchestration support.

## Context

The Tmux Orchestrator enables AI agents to work autonomously 24/7 across multiple projects. Current issues include:
- Self-scheduling randomly stops (agents schedule check-ins but sometimes don't fire)
- Git worktree sync delays causing integration bottlenecks
- Fixed team structure doesn't adapt to project needs
- No proper isolation for concurrent project orchestrations

Environment: Linux-based, single-node setup, 5-10 agents per project, 1-3 concurrent projects.

## Improvement Areas

### 1. Scheduling Reliability: Python-Based Scheduler

**Problem**: Current `at` command-based scheduling is brittle and randomly fails.

**Solution**: Implement a Python-based scheduler running in the Orchestrator's tmux window.

**Key Features**:
- SQLite-based persistent task queue
- Credit exhaustion detection integration
- Missed task recovery with exponential backoff
- Heartbeat monitoring for reliability

**Implementation**:
```python
# scheduler.py - Core scheduler daemon
import schedule
import time
import threading
import sqlite3
from session_state import get_agent_state

# SQLite setup for persistent queue
conn = sqlite3.connect('task_queue.db')
conn.execute('''CREATE TABLE IF NOT EXISTS tasks 
    (id INTEGER PRIMARY KEY, agent TEXT, next_run REAL, 
     interval INTEGER, note TEXT, last_run REAL)''')

def enqueue_task(agent, interval_minutes, note):
    """Agents call this instead of schedule_with_note.sh"""
    next_run = time.time() + interval_minutes * 60
    conn.execute("INSERT INTO tasks (agent, next_run, interval, note) VALUES (?, ?, ?, ?)", 
                 (agent, next_run, interval_minutes, note))
    conn.commit()

def run_task(agent, note):
    state = get_agent_state(agent)
    if state.get('credit_exhausted', False):
        # Defer with exponential backoff
        backoff = state.get('backoff_minutes', 1) * 2
        enqueue_task(agent, backoff, note + " (backoff)")
        return
    # Execute via tmux
    import os
    os.system(f'tmux send-keys -t {agent}-window "echo Running task: {note}" C-m')

def monitor_and_schedule():
    while True:
        schedule.run_pending()
        
        # Check for missed tasks
        cursor = conn.cursor()
        now = time.time()
        cursor.execute("SELECT * FROM tasks WHERE next_run < ?", (now,))
        for row in cursor.fetchall():
            id, agent, next_run, interval, note, last_run = row
            if last_run is None or (now - last_run > interval * 60 * 2):
                print(f"Recovering missed task for {agent}")
                run_task(agent, note)
                conn.execute("UPDATE tasks SET last_run = ? WHERE id = ?", (now, id))
            # Reschedule
            new_next = now + interval * 60
            conn.execute("UPDATE tasks SET next_run = ? WHERE id = ?", (new_next, id))
        conn.commit()
        time.sleep(60)
```

**Benefits**:
- Persistent scheduling survives crashes
- Automatic recovery from missed schedules
- Integrated credit management
- Low overhead (<1% CPU)

**Edge Cases & Mitigations**:
- Queue corruption → Backup on startup, use transactions
- High load delays → Timeouts and alerting
- Credit false positives → Manual override flags

### 2. Git Synchronization: Sync Coordinator

**Problem**: Complex "Fast Lane" approach adds overhead without solving sync delays.

**Solution**: Lightweight sync coordinator with event-driven updates.

**Key Features**:
- Git hooks for automatic trigger on commits
- Centralized sync logic in dedicated tmux window
- Simple dashboard for sync status monitoring
- Conflict escalation to Project Manager

**Implementation**:
```python
# sync_coordinator.py - Git sync management
import os
import time
import subprocess

WORKTREES_DIR = 'registry/projects/{project}/worktrees/'
NOTIFICATION_FILE = '/tmp/sync_notify'

def install_hooks(worktree_path):
    hook_path = f'{worktree_path}/.git/hooks/post-commit'
    with open(hook_path, 'w') as f:
        f.write('#!/bin/bash\ntouch {}'.format(NOTIFICATION_FILE))
    os.chmod(hook_path, 0o755)

def perform_sync(worktree):
    os.chdir(worktree)
    subprocess.run(['git', 'fetch', 'origin'])
    result = subprocess.run(['git', 'rebase', 'origin/main'], capture_output=True)
    if result.returncode != 0:
        # Log conflict for Project Manager
        with open('sync_dashboard.txt', 'a') as dash:
            dash.write(f"Conflict in {worktree}: {result.stderr}\n")
    else:
        with open('sync_dashboard.txt', 'a') as dash:
            dash.write(f"Synced {worktree} at {time.ctime()}\n")

def coordinator_loop(project):
    # Install hooks once
    for role in os.listdir(f'{WORKTREES_DIR}{project}'):
        install_hooks(f'{WORKTREES_DIR}{project}/{role}')
    
    while True:
        if os.path.exists(NOTIFICATION_FILE):
            os.remove(NOTIFICATION_FILE)
            for role in os.listdir(f'{WORKTREES_DIR}{project}'):
                perform_sync(f'{WORKTREES_DIR}{project}/{role}')
        time.sleep(1)
```

**Benefits**:
- Event-driven reduces polling overhead
- Centralized conflict handling
- Simple dashboard via `watch cat sync_dashboard.txt`
- Sub-minute sync latency

**Edge Cases & Mitigations**:
- Hook failures → Non-blocking background execution
- Sync conflicts → Rate limiting (once per minute)
- Coordinator downtime → Auto-restart via tmux

### 3. Dynamic Team Composition: Hybrid Approach

**Problem**: Fixed 5-agent teams don't adapt to project needs.

**Solution**: Rule-based detection with template inheritance and optional AI refinement.

**Key Features**:
- File-based project type detection
- YAML template inheritance system
- Optional Claude AI refinement
- Configurable role registry

**Implementation**:
```python
# Enhanced auto_orchestrate.py functions
import os
import yaml

def detect_project_type(project_dir):
    types = {'code': 0, 'data': 0, 'infrastructure': 0}
    for root, _, files in os.walk(project_dir):
        if any(f.endswith('.py') for f in files): 
            types['code'] += 1
        if 'data.csv' in files or 'pipeline.py' in files: 
            types['data'] += 1
        if 'terraform' in root or 'ansible' in root:
            types['infrastructure'] += 1
    return max(types, key=types.get)

def load_template(template_name, base='base'):
    with open(f'templates/{base}.yaml') as f:
        base_data = yaml.safe_load(f)
    if template_name != base:
        with open(f'templates/{template_name}.yaml') as f:
            child = yaml.safe_load(f)
            base_data['roles'].extend(child.get('roles', []))
    return base_data['roles']

def compose_team(project_dir, use_ai=False):
    proj_type = detect_project_type(project_dir)
    rules = {
        'code': 'code_project',
        'data': 'data_pipeline', 
        'infrastructure': 'system_deployment'
    }
    roles = load_template(rules.get(proj_type, 'base'))
    
    if use_ai:
        # Optional AI refinement
        from anthropic import Client
        client = Client(api_key='your_key')
        prompt = f"Refine roles for {proj_type} project with files: {os.listdir(project_dir)[:10]}"
        response = client.messages.create(
            model="claude-3-opus-20240229", 
            max_tokens=100, 
            messages=[{"role": "user", "content": prompt}]
        )
        # Parse and add suggested roles
        
    return list(set(roles))
```

**Template Examples**:
```yaml
# templates/base.yaml
roles:
  - orchestrator
  - project_manager

# templates/code_project.yaml
inherits: base
roles:
  - developer
  - tester
  - testrunner

# templates/system_deployment.yaml
inherits: base
roles:
  - sysadmin
  - devops
  - securityops
```

**Benefits**:
- Adapts to project type automatically
- Template inheritance for consistency
- Optional AI for edge cases
- Fast detection (<1s)

**Edge Cases & Mitigations**:
- Ambiguous projects → Scoring system with fallback
- Template conflicts → Depth-limited merging
- Detection errors → Recursive scan with exclusions

### 4. Concurrent Orchestrations: Minimal Locking

**Problem**: No isolation between concurrent project orchestrations.

**Solution**: File-based locking with UUID-namespaced sessions and registries.

**Key Features**:
- Project-level file locks with timeouts
- UUID-suffixed session names
- Isolated registry directories
- Multi-project status monitoring

**Implementation**:
```python
# Concurrent orchestration support
import uuid
from filelock import FileLock, Timeout

def start_orchestration(project):
    lock_file = f'/tmp/{project}.lock'
    try:
        with FileLock(lock_file, timeout=30):
            unique_id = str(uuid.uuid4())[:8]
            session_name = f'{project}-impl-{unique_id}'
            registry_dir = f'registry/projects/{project}-{unique_id}/'
            os.makedirs(registry_dir, exist_ok=True)
            
            # Check tmux session doesn't exist
            result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                                  capture_output=True)
            if result.returncode == 0:
                raise Exception(f"Session {session_name} already exists")
                
            # Proceed with deployment
            return session_name, registry_dir
    except Timeout:
        raise Exception(f"Could not acquire lock for project {project}")

# multi_status.py - Monitor all projects
import glob
from session_state import SessionStateManager

def monitor_all_projects():
    statuses = {}
    for state_file in glob.glob('registry/projects/*/session_state.json'):
        project = state_file.split('/')[-2]
        manager = SessionStateManager(Path('.'))
        state = manager.load_session_state(project)
        if state:
            statuses[project] = manager.get_session_summary(state)
    return statuses
```

**Benefits**:
- Prevents session conflicts
- Isolated project spaces
- Simple file-based approach
- Multi-project visibility

**Edge Cases & Mitigations**:
- Stale locks → Timeout and PID checks
- Name collisions → UUID uniqueness
- Monitoring overhead → Result caching

## Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)
1. Deploy Python scheduler to replace `at` command
2. Add file locking for concurrent orchestrations
3. Basic sync coordinator for git worktrees

### Phase 2: Enhancements (Week 2)
1. Implement dynamic team composition
2. Add sync status dashboard
3. Multi-project monitoring tool

### Phase 3: Optimization (Week 3)
1. AI refinement integration (optional)
2. Performance tuning
3. Comprehensive testing

## Testing Strategy

1. **Unit Tests**: Each component tested independently
2. **Integration Tests**: Full orchestration scenarios
3. **Chaos Testing**: Random failures and recovery
4. **Load Testing**: Multiple concurrent projects

## Monitoring & Metrics

- Scheduler reliability: % of successful executions
- Sync latency: Time from commit to propagation
- Team accuracy: % of correctly composed teams
- Concurrent capacity: Max simultaneous orchestrations

## Backwards Compatibility

All improvements maintain compatibility with existing:
- Tmux session structure
- Registry layout (with namespacing)
- Agent communication protocols
- Git workflow patterns

## Security Considerations

- Run all processes as non-root
- Validate file paths to prevent traversal
- Sanitize git hook inputs
- Restrict Redis/SQLite access if used

## Conclusion

These improvements address the core issues while maintaining simplicity and single-node operation. The modular approach allows incremental adoption, starting with critical scheduling and locking fixes, then enhancing team composition and synchronization.

Expected outcomes:
- 90%+ scheduling reliability (vs current random failures)
- <1 minute git sync latency (vs current delays)
- Dynamic teams adapted to project needs
- Support for 3+ concurrent orchestrations without conflicts
# Throughput Optimization Specification for Tmux Orchestrator

## Executive Summary

The Tmux Orchestrator system manages AI agents for software development but faces bottlenecks in idle time detection, authorization delays, and resource efficiency, leading to reduced development velocity. Key issues include conservative monitoring intervals (5-minute cycles allowing up to 25 minutes of undetected idle), fragile JSON-based state persistence (causing "WARNING: No state found" errors), slow authorization workflows (30-minute timeouts without escalation), and unoptimized credit usage on constrained plans (e.g., max5).

This specification outlines optimizations to increase throughput by 2x (commits per hour from 1-2 to 4-6) and reduce idle time by 50% (target <10% of runtime), while capping credit consumption increases at 20%. Improvements include adaptive intervals, SQLite migration for durability, priority-based authorization escalation, KPI tracking, and credit-aware throttling. Expected benefits: faster project completion, fewer stalls, and better scalability for concurrent sessions.

## Implementation Phases

Phases are prioritized by impact and dependencies, with effort estimates based on a single developer (assuming familiarity with the codebase). Total estimated effort: 10-15 days. Testing (unit/integration) is included in each phase.

### Phase 1: Optimize Monitoring and Nudging Intervals (High Impact, Low Effort: 1-2 days)
- **Focus**: Adaptive intervals to reduce idle time
- **Dependencies**: None
- **Output**: Updated checkin_monitor.py with phase-specific logic
- **Priority**: HIGH

### Phase 2: Migrate Session State to SQLite (High Impact, Medium Effort: 3-5 days)
- **Focus**: Durable persistence to eliminate state loss
- **Dependencies**: Phase 1 (for state integration)
- **Output**: Updated session_state.py with DB backend and migration script
- **Priority**: HIGH

### Phase 3: Implement Authorization Priority Queue and KPIs (Medium Impact, Medium Effort: 3-5 days)
- **Focus**: Faster escalations and velocity tracking
- **Dependencies**: Phase 2 (for reliable state)
- **Output**: Updates to scheduler.py, checkin_monitor.py, and session_state.py
- **Priority**: MEDIUM

### Phase 4: Add Credit-Aware Throttling (Medium Impact, Low-Medium Effort: 2-3 days)
- **Focus**: Balance responsiveness with resource constraints
- **Dependencies**: Phase 3 (for integrated KPIs)
- **Output**: Enhancements to checkin_monitor.py and scheduler.py
- **Priority**: MEDIUM

## Specific Code Changes Organized by File

### 1. checkin_monitor.py (Phases 1, 3, 4)

#### Phase 1: Adaptive Intervals and Phase Detection

```python
import asyncio  # For potential async enhancements
import heapq   # For priority queue in auth checks

class CheckinMonitor:
    def __init__(self, tmux_orchestrator_path: Path):
        # Existing init code...
        
        # NEW: Optimized intervals
        self.monitoring_cycle_sec = 120  # 2 minutes (down from 5)
        self.default_idle_threshold_min = 5  # Down from 10
        self.default_nudge_cooldown_min = 5  # Down from 10
        self.emergency_intervals = [0, 5, 15]  # Minutes (down from [0,10,30])
        
    def get_adaptive_intervals(self, state: SessionState) -> Dict[str, int]:
        """Get phase-specific intervals for monitoring"""
        current_phase = self.determine_phase(state)
        
        if current_phase == "active":
            return {'idle': 5, 'cooldown': 5}
        elif current_phase == "review":
            return {'idle': 8, 'cooldown': 7}
        else:  # idle
            return {'idle': 12, 'cooldown': 10}
    
    def determine_phase(self, state: SessionState) -> str:
        """Determine current project phase from state"""
        if not state.phases_completed:
            return "active"
            
        last_phase = state.phases_completed[-1].lower()
        if "implementation" in last_phase or "development" in last_phase:
            return "active"
        elif "testing" in last_phase or "review" in last_phase:
            return "review"
        return "idle"
    
    def run_continuous_monitoring(self, interval_minutes: int = None):
        """Enhanced monitoring loop with adaptive intervals"""
        # Use optimized default if not specified
        if interval_minutes is None:
            interval_minutes = self.monitoring_cycle_sec / 60
            
        logger.info(f"Starting continuous check-in monitoring (interval: {interval_minutes} minutes)")
        
        while True:
            try:
                interventions = self.monitor_all_projects()
                if interventions > 0:
                    logger.info(f"Performed {interventions} interventions")
                
                # Sleep with adaptive interval
                time.sleep(self.monitoring_cycle_sec)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Brief pause before retry
```

#### Phase 3: Authorization Checks and KPI Calculations

```python
    def check_authorizations_priority(self, session_name: str, state: SessionState):
        """Check authorizations with priority-based escalation"""
        # Query pending authorizations from scheduler DB
        try:
            conn = sqlite3.connect(str(self.scheduler_db))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, request_id, priority, from_role, to_role, 
                       timeout_min, created_at
                FROM authorizations
                WHERE session_name = ? AND status = 'pending'
                ORDER BY priority, created_at
            """, (session_name,))
            
            pending = cursor.fetchall()
            
            for auth in pending:
                auth_id, request_id, priority, from_role, to_role, timeout_min, created_at = auth
                elapsed_minutes = (time.time() - created_at) / 60
                
                # Escalate at 80% of timeout
                if elapsed_minutes > timeout_min * 0.8:
                    escalation_msg = f"""AUTHORIZATION ESCALATION
Request ID: {request_id}
From: {from_role} To: {to_role}
Priority: {'HIGH' if priority == 1 else 'MEDIUM' if priority == 2 else 'LOW'}
Time Elapsed: {elapsed_minutes:.0f}/{timeout_min} minutes
Action Required: Please respond immediately"""
                    
                    # Send to Orchestrator
                    send_script = self.tmux_orchestrator_path / "send-claude-message.sh"
                    if send_script.exists():
                        subprocess.run([
                            str(send_script),
                            f"{session_name}:0",
                            escalation_msg
                        ], capture_output=True)
                    
                    logger.warning(f"Escalated priority {priority} authorization {request_id}")
                    
            conn.close()
        except Exception as e:
            logger.error(f"Error checking priority authorizations: {e}")
    
    def calculate_velocity_metrics(self, state: SessionState) -> Dict[str, float]:
        """Calculate KPIs for velocity measurement"""
        metrics = {}
        
        # Idle time percentage
        total_idle_pct = 0
        active_agents = 0
        
        for role, agent in state.agents.items():
            if agent.is_alive:
                idle_pct = self.calculate_idle_percentage(state, role)
                total_idle_pct += idle_pct
                active_agents += 1
        
        metrics['idle_pct'] = total_idle_pct / active_agents if active_agents > 0 else 0
        
        # Commits per hour (from git logs in worktrees)
        try:
            project_path = self.get_project_worktree_path(state.project_name)
            result = subprocess.run([
                'git', '-C', str(project_path), 'log', 
                '--since=1 hour ago', '--oneline'
            ], capture_output=True, text=True)
            
            metrics['commits_per_hour'] = len(result.stdout.strip().split('\n')) if result.stdout else 0
        except:
            metrics['commits_per_hour'] = 0
        
        # Phase completion time
        if len(state.phases_completed) >= 2:
            # Calculate average time between phases
            phase_times = []
            for i in range(1, len(state.phases_completed)):
                # Assuming phases have timestamps
                phase_times.append(state.phase_durations.get(i, 0))
            metrics['avg_phase_hours'] = sum(phase_times) / len(phase_times) if phase_times else 0
        
        return metrics
    
    def calculate_idle_percentage(self, state: SessionState, agent_role: str) -> float:
        """Calculate idle percentage for a specific agent"""
        agent = state.agents[agent_role]
        
        # Get last activity time
        last_activity = datetime.fromisoformat(
            agent.last_check_in_time or state.created_at
        )
        
        # Calculate runtime and idle time
        start_time = datetime.fromisoformat(state.created_at)
        runtime_min = (datetime.now() - start_time).total_seconds() / 60
        idle_min = (datetime.now() - last_activity).total_seconds() / 60
        
        return (idle_min / runtime_min) * 100 if runtime_min > 0 else 0
```

#### Phase 4: Credit-Aware Throttling

```python
    def should_throttle(self, state: SessionState) -> bool:
        """Determine if monitoring should be throttled based on credits and plan"""
        # Get plan from state (set during auto_orchestrate)
        plan = getattr(state, 'subscription_plan', 'pro')
        
        # Count exhausted agents
        exhausted_count = sum(1 for a in state.agents.values() if a.is_exhausted)
        exhausted_ratio = exhausted_count / len(state.agents) if state.agents else 0
        
        # Throttle conditions
        if plan == "max5":
            # More conservative for limited plans
            self.monitoring_cycle_sec = 240  # 4 minutes
            self.idle_threshold_minutes = 8
            self.nudge_cooldown_minutes = 10
            return exhausted_ratio > 0.3  # Throttle if 30% exhausted
            
        elif exhausted_ratio > 0.5:
            # General throttling if many agents exhausted
            self.monitoring_cycle_sec = 180  # 3 minutes
            return True
            
        return False
    
    def check_project_health(self, session_name: str, state: SessionState) -> Dict:
        """Enhanced health check with throttling"""
        # Check throttling first
        if self.should_throttle(state):
            logger.info(f"Throttling active for {session_name} due to credit constraints")
            
        # Existing health check logic...
        health = {
            'session_name': session_name,
            'status': 'healthy',
            'issues': [],
            'recommendations': [],
            'metrics': {}  # NEW: Add metrics
        }
        
        # Calculate and add velocity metrics
        health['metrics'] = self.calculate_velocity_metrics(state)
        
        # Rest of existing health check...
        return health
```

### 2. scheduler.py (Phase 3)

```python
class TmuxOrchestratorScheduler:
    def setup_database(self):
        """Initialize SQLite database for persistent task storage"""
        # Existing tables...
        
        # NEW: Authorization tracking table
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS authorizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT NOT NULL,
                request_id TEXT UNIQUE NOT NULL,
                priority INTEGER NOT NULL,  -- 1=high, 2=medium, 3=low
                from_role TEXT NOT NULL,
                to_role TEXT NOT NULL,
                action TEXT NOT NULL,
                timeout_min INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',  -- pending, approved, denied, escalated
                created_at REAL DEFAULT (strftime('%s', 'now')),
                resolved_at REAL,
                resolution TEXT
            )
        ''')
        
        # Add indexes for performance
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_auth_session_status 
            ON authorizations(session_name, status)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_auth_priority_created 
            ON authorizations(priority, created_at)
        ''')
        
        self.conn.commit()
        logger.info("Database initialized with authorization support")
    
    def enqueue_authorization(self, session_name: str, request_id: str, 
                            from_role: str, to_role: str, action: str) -> int:
        """Enqueue an authorization request with priority"""
        # Determine priority based on action
        priority = self.get_action_priority(action)
        timeout_min = {1: 5, 2: 15, 3: 30}[priority]  # High: 5min, Medium: 15min, Low: 30min
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO authorizations 
            (session_name, request_id, priority, from_role, to_role, action, timeout_min)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session_name, request_id, priority, from_role, to_role, action, timeout_min))
        
        self.conn.commit()
        auth_id = cursor.lastrowid
        
        logger.info(f"Enqueued authorization {auth_id} (priority {priority}) for {action}")
        
        # Trigger event for immediate handling if high priority
        if priority == 1:
            self.trigger_event('high_priority_auth', {
                'auth_id': auth_id,
                'action': action,
                'from': from_role,
                'to': to_role
            })
        
        return auth_id
    
    def get_action_priority(self, action: str) -> int:
        """Determine priority level based on action type"""
        action_lower = action.lower()
        
        # High priority (5 min timeout)
        if any(keyword in action_lower for keyword in [
            'production', 'deploy', 'security', 'emergency', 'critical'
        ]):
            return 1
            
        # Medium priority (15 min timeout)
        elif any(keyword in action_lower for keyword in [
            'schema', 'database', 'infrastructure', 'config'
        ]):
            return 2
            
        # Low priority (30 min timeout)
        else:
            return 3
    
    def resolve_authorization(self, request_id: str, resolution: str, details: str = ""):
        """Mark an authorization as resolved"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE authorizations
            SET status = ?, resolution = ?, resolved_at = ?
            WHERE request_id = ?
        """, (resolution, details, time.time(), request_id))
        
        self.conn.commit()
        
        if cursor.rowcount > 0:
            logger.info(f"Authorization {request_id} resolved: {resolution}")
            
            # Clear waiting_for in session state
            # (Implementation depends on integration with session_state)
```

### 3. session_state.py (Phases 2, 3)

```python
import sqlite3
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class SessionState:
    """Enhanced with velocity metrics and subscription plan"""
    # Existing fields...
    
    # NEW fields
    velocity_metrics: Dict[str, float] = field(default_factory=dict)
    subscription_plan: str = "pro"  # pro, max5, max20, console
    phase_durations: Dict[int, float] = field(default_factory=dict)  # Phase index -> hours

class SessionStateManager:
    """SQLite-backed session state manager with migration support"""
    
    def __init__(self, tmux_orchestrator_path: Path):
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.registry_dir = tmux_orchestrator_path / "registry"
        self.projects_dir = self.registry_dir / "projects"
        
        # NEW: SQLite backend
        self.db_path = self.registry_dir / 'session_states.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        self._init_database()
        
    def _init_database(self):
        """Initialize database schema"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS session_states (
                project_name TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER DEFAULT 1
            )
        ''')
        
        # Add index for performance
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_updated_at 
            ON session_states(updated_at)
        ''')
        
        self.conn.commit()
        logger.info("Session state database initialized")
    
    def save_session_state(self, state: SessionState) -> None:
        """Save session state to SQLite with automatic migration"""
        try:
            state_dict = asdict(state)
            state_json = json.dumps(state_dict, default=str)  # Handle datetime serialization
            
            with self.conn:
                self.conn.execute('''
                    INSERT OR REPLACE INTO session_states 
                    (project_name, state_json, updated_at, version)
                    VALUES (?, ?, ?, ?)
                ''', (state.project_name, state_json, datetime.now().isoformat(), 1))
            
            logger.debug(f"Saved session state for {state.project_name}")
            
        except Exception as e:
            logger.error(f"Failed to save session state: {e}")
            # Fallback to JSON (temporary)
            self._save_legacy_json(state)
    
    def load_session_state(self, project_name: str) -> Optional[SessionState]:
        """Load session state from SQLite with fallback to JSON migration"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT state_json, updated_at 
                FROM session_states 
                WHERE project_name = ?
            ''', (project_name,))
            
            row = cursor.fetchone()
            
            if row:
                state_dict = json.loads(row['state_json'])
                
                # Reconstruct agents
                agents = {}
                for role, agent_data in state_dict.get('agents', {}).items():
                    agents[role] = AgentState(**agent_data)
                
                # Create SessionState with reconstructed agents
                state_dict['agents'] = agents
                state = SessionState(**state_dict)
                
                logger.debug(f"Loaded session state for {project_name} from DB")
                return state
                
            else:
                # Try to migrate from legacy JSON
                legacy_state = self._load_and_migrate_legacy(project_name)
                if legacy_state:
                    # Save to DB for next time
                    self.save_session_state(legacy_state)
                    logger.info(f"Migrated legacy JSON state for {project_name}")
                    return legacy_state
                    
                return None
                
        except Exception as e:
            logger.error(f"Failed to load session state: {e}")
            # Last resort: try legacy JSON
            return self._load_legacy_json_direct(project_name)
    
    def _load_and_migrate_legacy(self, project_name: str) -> Optional[SessionState]:
        """Load legacy JSON state and migrate to new format"""
        legacy_path = self.get_state_file_path(project_name)
        
        if not legacy_path.exists():
            return None
            
        try:
            with open(legacy_path, 'r') as f:
                state_dict = json.load(f)
            
            # Reconstruct agents
            agents = {}
            for role, agent_data in state_dict.get('agents', {}).items():
                agents[role] = AgentState(**agent_data)
            
            state_dict['agents'] = agents
            
            # Add new fields if missing
            if 'velocity_metrics' not in state_dict:
                state_dict['velocity_metrics'] = {}
            if 'subscription_plan' not in state_dict:
                state_dict['subscription_plan'] = 'pro'
            if 'phase_durations' not in state_dict:
                state_dict['phase_durations'] = {}
            
            state = SessionState(**state_dict)
            
            # Backup legacy file
            backup_path = legacy_path.with_suffix('.json.bak')
            legacy_path.rename(backup_path)
            logger.info(f"Backed up legacy state to {backup_path}")
            
            return state
            
        except Exception as e:
            logger.error(f"Failed to migrate legacy state: {e}")
            return None
    
    def update_velocity_metrics(self, project_name: str, metrics: Dict[str, float]):
        """Update velocity metrics for a project"""
        state = self.load_session_state(project_name)
        if state:
            state.velocity_metrics.update(metrics)
            self.save_session_state(state)
            logger.debug(f"Updated velocity metrics for {project_name}: {metrics}")
    
    def get_all_waiting_agents(self) -> List[Dict[str, Any]]:
        """Get all agents currently waiting for authorization across all projects"""
        waiting = []
        
        cursor = self.conn.cursor()
        cursor.execute('SELECT project_name, state_json FROM session_states')
        
        for row in cursor.fetchall():
            try:
                state_dict = json.loads(row['state_json'])
                project_name = row['project_name']
                
                for role, agent_data in state_dict.get('agents', {}).items():
                    if agent_data.get('waiting_for'):
                        waiting.append({
                            'project': project_name,
                            'role': role,
                            'waiting_for': agent_data['waiting_for']
                        })
                        
            except Exception as e:
                logger.error(f"Error parsing state for {row['project_name']}: {e}")
                
        return waiting
    
    def cleanup_old_states(self, days: int = 30):
        """Remove old session states"""
        cutoff = datetime.now() - timedelta(days=days)
        
        with self.conn:
            self.conn.execute('''
                DELETE FROM session_states 
                WHERE datetime(updated_at) < ?
            ''', (cutoff.isoformat(),))
            
        logger.info(f"Cleaned up states older than {days} days")
```

### 4. Script Updates

#### request-authorization.sh (Phase 3) - Add Priority Support

```bash
#!/bin/bash

# Enhanced with priority support
# Usage: request-authorization.sh <role> "<request_message>" "<target_role>" [priority]
# Example: request-authorization.sh developer "Deploy event_router.py to Modal production" "pm" "high"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

if [ $# -lt 3 ]; then
    echo "Usage: $0 <role> \"<request_message>\" \"<target_role>\" [priority]"
    echo "Priority: high, medium, low (default: low)"
    exit 1
fi

ROLE="$1"
REQUEST_MESSAGE="$2"
TARGET_ROLE="$3"
PRIORITY="${4:-low}"  # Default to low if not specified

# Existing session/window detection...

# Enhanced Python integration for priority queue
python3 << EOF
import sys
sys.path.append('$SCRIPT_DIR')
from scheduler import TmuxOrchestratorScheduler

try:
    scheduler = TmuxOrchestratorScheduler()
    auth_id = scheduler.enqueue_authorization(
        session_name="$SESSION",
        request_id="$REQUEST_ID",
        from_role="$ROLE",
        to_role="$TARGET_ROLE",
        action="$REQUEST_MESSAGE"
    )
    print(f"Authorization queued with ID {auth_id}")
except Exception as e:
    print(f"Error: {e}")
EOF

# Rest of script...
```

## Migration Plan for JSON to SQLite

### Phase 1: Preparation (Day 1)
1. **Backup all existing JSON files**:
   ```bash
   cd ~/Tmux-Orchestrator
   tar -czf registry_backup_$(date +%Y%m%d).tar.gz registry/
   ```

2. **Create migration script** (`migrate_states.py`):
   ```python
   #!/usr/bin/env python3
   import sys
   from pathlib import Path
   sys.path.append(str(Path(__file__).parent))
   
   from session_state import SessionStateManager
   import logging
   
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)
   
   def migrate_all_states(dry_run=True):
       """Migrate all JSON states to SQLite"""
       mgr = SessionStateManager(Path.cwd())
       
       json_files = list(Path('registry/projects').rglob('session_state.json'))
       logger.info(f"Found {len(json_files)} JSON state files")
       
       migrated = 0
       failed = 0
       
       for json_file in json_files:
           try:
               project_name = json_file.parent.parent.name
               logger.info(f"Migrating {project_name}...")
               
               if not dry_run:
                   state = mgr._load_and_migrate_legacy(project_name)
                   if state:
                       mgr.save_session_state(state)
                       migrated += 1
                   else:
                       failed += 1
               else:
                   logger.info(f"  [DRY RUN] Would migrate {json_file}")
                   migrated += 1
                   
           except Exception as e:
               logger.error(f"Failed to migrate {json_file}: {e}")
               failed += 1
       
       logger.info(f"Migration complete: {migrated} successful, {failed} failed")
       
   if __name__ == "__main__":
       import argparse
       parser = argparse.ArgumentParser()
       parser.add_argument('--execute', action='store_true', help='Execute migration (default: dry run)')
       args = parser.parse_args()
       
       migrate_all_states(dry_run=not args.execute)
   ```

### Phase 2: Testing (Days 2-3)
1. Run dry-run migration:
   ```bash
   python3 migrate_states.py
   ```

2. Test on single project:
   ```bash
   python3 -c "from session_state import SessionStateManager; mgr = SessionStateManager('.'); print(mgr.load_session_state('test-project'))"
   ```

3. Verify concurrent access handling

### Phase 3: Deployment (Day 4)
1. Stop all monitoring/scheduler processes
2. Execute migration:
   ```bash
   python3 migrate_states.py --execute
   ```
3. Update all scripts to use new SessionStateManager
4. Restart processes
5. Monitor logs for errors

### Phase 4: Validation (Day 5)
1. Verify all states load correctly
2. Check for performance improvements
3. Ensure no data loss
4. Keep backups for 1 week minimum

## Risk Mitigation Strategies

### 1. Data Loss Prevention
- **Risk**: Migration corruption or concurrent access issues
- **Mitigation**: 
  - Automated backups before any changes
  - Atomic transactions in SQLite
  - Fallback to JSON if DB fails
  - Dry-run mode for testing

### 2. Performance Degradation
- **Risk**: Faster monitoring overwhelms system
- **Mitigation**:
  - Minimum 1-minute monitoring interval
  - Async processing where possible
  - Circuit breakers for high load
  - Performance profiling with cProfile

### 3. False Positive Nudges
- **Risk**: Over-aggressive idle detection
- **Mitigation**:
  - Enhanced activity detection logic
  - Manual override flags
  - Logging all nudges for analysis
  - Target <10% false positive rate

### 4. Credit Exhaustion
- **Risk**: Increased monitoring burns credits faster
- **Mitigation**:
  - Credit-aware throttling
  - Plan-specific limits
  - Budget caps (max interactions/hour)
  - Automatic backoff on exhaustion

### 5. Implementation Bugs
- **Risk**: New code introduces errors
- **Mitigation**:
  - Comprehensive unit tests
  - Phased rollout by project
  - Feature flags for easy disable
  - Monitoring and alerting

## Success Metrics and Measurement

### Key Performance Indicators (KPIs)

1. **Development Velocity**
   - **Metric**: Commits per hour
   - **Target**: >4 (up from 1-2)
   - **Measurement**: Git log analysis in worktrees
   - **Query**: `git log --since="1 hour ago" --oneline | wc -l`

2. **Idle Time Reduction**
   - **Metric**: Idle time percentage
   - **Target**: <10% (down from 20-30%)
   - **Measurement**: Agent activity tracking
   - **Formula**: `(idle_minutes / total_runtime_minutes) * 100`

3. **Authorization Speed**
   - **Metric**: Average resolution time
   - **Target**: <10 minutes (down from 30)
   - **Measurement**: Authorization table timestamps
   - **Query**: `SELECT AVG((resolved_at - created_at)/60) FROM authorizations`

4. **Phase Completion**
   - **Metric**: Hours per phase
   - **Target**: 30% reduction
   - **Measurement**: Phase timestamp tracking
   - **Source**: `state.phase_durations`

5. **System Throughput**
   - **Metric**: Features/phases per day
   - **Target**: >1 feature/day
   - **Measurement**: Phases completed count
   - **Source**: `len(state.phases_completed)`

6. **Credit Efficiency**
   - **Metric**: Interactions per hour
   - **Target**: <20% increase
   - **Measurement**: Log analysis
   - **Source**: Count nudges + check-ins

### Monitoring Dashboard

Create `status_dashboard.py`:
```python
#!/usr/bin/env python3
from session_state import SessionStateManager
from pathlib import Path
import statistics

def show_metrics():
    mgr = SessionStateManager(Path.cwd())
    
    # Aggregate metrics across all projects
    all_metrics = []
    
    cursor = mgr.conn.cursor()
    cursor.execute('SELECT project_name, state_json FROM session_states')
    
    for row in cursor.fetchall():
        state = mgr.load_session_state(row['project_name'])
        if state and state.velocity_metrics:
            all_metrics.append(state.velocity_metrics)
    
    # Calculate aggregates
    if all_metrics:
        avg_idle = statistics.mean(m.get('idle_pct', 0) for m in all_metrics)
        avg_commits = statistics.mean(m.get('commits_per_hour', 0) for m in all_metrics)
        
        print(f"=== Tmux Orchestrator Metrics ===")
        print(f"Active Projects: {len(all_metrics)}")
        print(f"Avg Idle Time: {avg_idle:.1f}%")
        print(f"Avg Commits/Hour: {avg_commits:.1f}")
        print(f"Target Status: {'✅' if avg_idle < 10 else '❌'}")

if __name__ == "__main__":
    show_metrics()
```

## Rollback Procedures

### Immediate Rollback (Critical Issues)

1. **Stop all processes**:
   ```bash
   pkill -f checkin_monitor.py
   pkill -f scheduler.py
   ```

2. **Revert code changes**:
   ```bash
   cd ~/Tmux-Orchestrator
   git stash  # Save current changes
   git checkout main  # Or last known good commit
   ```

3. **Restore JSON states** (if migrated):
   ```bash
   cd registry/projects
   find . -name "session_state.json.bak" -exec sh -c 'mv "$1" "${1%.bak}"' _ {} \;
   ```

4. **Disable optimizations**:
   Create `config_override.py`:
   ```python
   # Temporary override flags
   ENABLE_OPTIMIZATIONS = False
   USE_LEGACY_INTERVALS = True
   FORCE_JSON_STORAGE = True
   ```

5. **Restart with safe defaults**:
   ```bash
   python3 checkin_monitor.py --interval 10  # Conservative 10-min
   ```

### Gradual Rollback (Non-Critical)

1. **Phase-specific revert**:
   - Phase 1: Restore original intervals in `checkin_monitor.py`
   - Phase 2: Re-enable JSON storage in `session_state.py`
   - Phase 3: Disable authorization queue in `scheduler.py`
   - Phase 4: Remove throttling logic

2. **Monitor for 24 hours** before full restoration

3. **Document issues** for post-mortem

### Validation After Rollback

1. Check system stability:
   ```bash
   tail -f scheduler.log checkin_monitor.log
   ```

2. Verify state persistence:
   ```bash
   ls -la registry/projects/*/session_state.json
   ```

3. Confirm agent responsiveness:
   ```bash
   tmux list-windows -t [session-name]
   ```

## Conclusion

This optimization spec provides a comprehensive roadmap to double Tmux Orchestrator throughput while maintaining stability. The phased approach allows for incremental improvements with measurable results. Key success factors include careful migration planning, thorough testing, and continuous monitoring of KPIs.

Implementation should begin with Phase 1 (adaptive intervals) for immediate impact, followed by the critical SQLite migration to resolve persistence issues. The total effort of 10-15 days will result in a significantly more responsive and efficient orchestration system.

**Document Version**: 1.0  
**Created**: 2025-08-19  
**Author**: Tmux Orchestrator Team  
**Next Review**: After Phase 1 completion
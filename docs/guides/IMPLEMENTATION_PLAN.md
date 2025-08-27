# Tmux Orchestrator Enhancement Implementation Plan

## Overview
This document outlines the step-by-step implementation of 8 pending TODO items for the Tmux Orchestrator system. The plan follows a logical dependency-based order prioritizing system reliability, then scalability, and finally optimizations.

**Current System State:**
- ✅ State Synchronizer implemented (state_synchronizer.py)
- ✅ Reboot recovery system implemented (docs/REBOOT_RECOVERY.md) 
- ✅ ProcessManager implemented (process_manager.py)
- ✅ Auto-orchestrate with resume capability exists
- ✅ Git worktree isolation and batch processing implemented

**Pending Items:**
- ☐ Integrate state synchronizer into scheduler for proactive state validation
- ☐ Add pre-flight checks to auto_orchestrate.py to validate requirements before tmux session creation
- ☐ Add session conflict resolution to auto_orchestrate.py
- ☐ Add database reconciliation for orphaned tmux sessions
- ☐ Implement default resume mode for existing sessions in scheduler
- ☐ Implement ProjectLock class to prevent future cross-project interference during resets
- ☐ Enhance reboot recovery logic to proactively repair null session names
- ☐ Add heartbeat system to extend ProcessManager timeout during long-running operations

**Total Estimated Effort**: 2-3 weeks (8 TODOs, ~2-4 days each with testing)

**Key Principles**:
- Use atomic operations (SQLite transactions) for consistency
- Add logging at DEBUG level for all new methods
- Write unit tests using pytest (extending existing test infrastructure)
- Update documentation as needed

---

## Implementation Order (Dependency-Based)

Based on expert analysis considering dependencies, risk, and impact:

1. **[TODO #7] Enhance reboot recovery logic to proactively repair null session names** - Builds on existing reboot recovery; low risk, high impact
2. **[TODO #1] Integrate state synchronizer into scheduler for proactive state validation** - Leverages existing state_synchronizer.py
3. **[TODO #4] Add database reconciliation for orphaned tmux sessions** - Depends on #1
4. **[TODO #6] Implement ProjectLock class** - Standalone but enhances system safety
5. **[TODO #5] Implement default resume mode** - Builds on existing resume logic
6. **[TODO #2] Add pre-flight checks to auto_orchestrate.py** - Entry point enhancement
7. **[TODO #3] Add session conflict resolution** - Pairs with #2
8. **[TODO #8] Add heartbeat system** - Optimization building on stable foundations

---

## Detailed Implementation Guide

### 1. [HIGH PRIORITY] Enhance Reboot Recovery Logic (TODO #7)
**Rationale**: Prevents phantom projects from null session names during reboot recovery.

**Dependencies**: 
- scheduler.py's `_recover_from_reboot()` method
- state_synchronizer.py's `repair_missing_session_name()` method

**Implementation Steps**:
1. Modify `_recover_from_reboot()` in scheduler.py to check and repair null session names
2. Add retry logic with exponential backoff (max 3 attempts)
3. Mark unrepairable projects as failed with descriptive error message

**Code Integration Point**:
```python
# In scheduler.py's _recover_from_reboot() method
# Add after processing_projects = cursor.fetchall()

from state_synchronizer import StateSynchronizer

# Inside the project loop:
synchronizer = StateSynchronizer(self.db_path, "registry")
max_attempts = 3
repaired = False

for attempt in range(max_attempts):
    if not session_name:
        logger.warning(f"Null session_name for project {project_id} (attempt {attempt+1}/{max_attempts})")
        if synchronizer.repair_missing_session_name(project_id):
            # Refresh session_name after repair
            cursor.execute("SELECT session_name FROM project_queue WHERE id = ?", (project_id,))
            session_name = cursor.fetchone()[0]
            repaired = True
            logger.info(f"Repaired null session for project {project_id}: {session_name}")
            break
        time.sleep(1)  # Backoff

if not repaired and not session_name:
    # Mark as failed if unrepairable
    cursor.execute("""
        UPDATE project_queue 
        SET status = 'failed', 
            error_message = 'Unrecoverable null session name after reboot',
            completed_at = strftime('%s', 'now')
        WHERE id = ?
    """, (project_id,))
    logger.error(f"Failed to repair null session for project {project_id} - marked as failed")
    continue
```

**Testing Strategy**:
- Extend `test_reboot_recovery.py` with null session name test cases
- Add integration test in `test_integration.py`
- Use chaos_tester.py to inject null session failures

**Risk Mitigation**:
- Max attempts with backoff prevents infinite loops
- Atomic SQLite transactions prevent partial updates
- Email alerts via existing notifier for unrecoverable failures

**Estimated Effort**: 1-2 days

---

### 2. [HIGH PRIORITY] Integrate State Synchronizer (TODO #1)
**Rationale**: Proactive validation prevents mismatches between SQLite, JSON states, and tmux sessions.

**Dependencies**:
- state_synchronizer.py (already implemented)
- scheduler.py's `_monitor_batches()` monitoring thread

**Implementation Steps**:
1. Add state synchronization calls to scheduler monitoring thread
2. Configure sync interval via environment variable
3. Escalate critical failures via email notification

**Code Integration Point**:
```python
# In scheduler.py __init__ method:
from state_synchronizer import StateSynchronizer

self.state_sync_interval = int(os.getenv('STATE_SYNC_INTERVAL_SEC', 300))  # 5min default
self.last_state_sync = 0

# New method in scheduler.py:
def _run_state_sync(self):
    try:
        synchronizer = StateSynchronizer(self.db_path, "registry")
        mismatches = synchronizer.detect_mismatches()
        
        if mismatches:
            logger.warning(f"Detected {len(mismatches)} state mismatches")
            results = synchronizer.auto_repair_mismatches(mismatches)
            logger.info(f"Repair results: {results}")
            
            # Escalate critical unresolved issues
            if results['failed'] > 0:
                notifier = get_email_notifier()
                notifier.send_email(
                    subject="State Synchronization Alert",
                    body=synchronizer.generate_report(mismatches)
                )
        else:
            logger.debug("No state mismatches detected")
    except Exception as e:
        logger.error(f"State sync failed: {e}")

# In _monitor_batches() while loop:
now = time.time()
if now - self.last_state_sync > self.state_sync_interval:
    self._run_state_sync()
    self.last_state_sync = now
```

**Testing Strategy**:
- Unit tests in `test_integration.py` with mocked mismatches
- End-to-end testing with induced state inconsistencies
- Load testing with multiple projects using `load_tester.py`

**Risk Mitigation**:
- Configurable dry-run mode (`STATE_SYNC_DRY_RUN=true`)
- Throttled execution to prevent performance impact
- Fallback to skip cycle if issues persist

**Estimated Effort**: 2-3 days

---

### 3. [MEDIUM PRIORITY] Database Reconciliation for Orphaned Sessions (TODO #4)
**Rationale**: Cleanup orphaned tmux sessions that exist but aren't tracked in SQLite/JSON.

**Dependencies**: 
- TODO #1 (state synchronization integration)
- Existing tmux session detection methods

**Implementation Steps**:
1. Add orphaned session detection to state synchronizer
2. Implement cleanup logic with grace periods
3. Integrate with monitoring thread

**Code Integration Point**:
```python
# Add to scheduler.py after _run_state_sync():
def _reconcile_orphaned_sessions(self):
    try:
        active_sessions = self.get_active_tmux_sessions()
        known_sessions = set()
        
        # Get sessions from database
        with self.queue_lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT session_name FROM project_queue WHERE session_name IS NOT NULL")
            known_sessions.update(row[0] for row in cursor.fetchall())
        
        # Get sessions from JSON states
        json_states = StateSynchronizer(self.db_path, "registry").get_json_session_states()
        known_sessions.update(state.get('session_name') for state in json_states if state.get('session_name'))
        
        orphaned = active_sessions - known_sessions
        
        for session_name in orphaned:
            # Grace period for new sessions (ignore if < 1 hour old)
            if self._is_session_recent(session_name, 3600):
                continue
                
            logger.warning(f"Terminating orphaned session: {session_name}")
            subprocess.run(['tmux', 'kill-session', '-t', session_name], check=False)
            
    except Exception as e:
        logger.error(f"Orphaned session reconciliation failed: {e}")

# Call in monitoring loop after state sync
```

**Testing Strategy**:
- Create test orphaned sessions and verify cleanup
- Test grace period functionality
- Integration with chaos testing

**Risk Mitigation**:
- Grace period prevents killing recent sessions
- Confirmation logs before termination
- Safe failure mode (log but continue)

**Estimated Effort**: 2 days

---

### 4. [MEDIUM PRIORITY] Implement ProjectLock Class (TODO #6)
**Rationale**: Prevents cross-project interference during resets in multi-project environments.

**Dependencies**: None (standalone implementation)

**Implementation Steps**:
1. Create new `project_lock.py` with file-based locking
2. Implement context manager for clean usage
3. Integrate with reset operations in scheduler and auto_orchestrate

**Code Implementation**:
```python
# New file: project_lock.py
import os
import fcntl
import time
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ProjectLock:
    def __init__(self, lock_dir: str = 'locks', timeout: int = 30):
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(exist_ok=True)
        self.timeout = timeout
        self._fd = None
        self.project_id = None

    def acquire(self, project_id: int) -> bool:
        self.project_id = project_id
        lock_file = self.lock_dir / f'project_{project_id}.lock'
        self._fd = open(lock_file, 'w')
        
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug(f"Acquired lock for project {project_id}")
                return True
            except IOError:
                time.sleep(0.5)
        
        logger.warning(f"Timeout acquiring lock for project {project_id}")
        self._fd.close()
        self._fd = None
        return False

    def release(self):
        if self._fd:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            self._fd.close()
            self._fd = None
            logger.debug(f"Released lock for project {self.project_id}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

# Usage in scheduler.py:
from project_lock import ProjectLock

def reset_project_to_queued(self, project_id: int, reason: str = "Manual reset"):
    lock = ProjectLock()
    if lock.acquire(project_id):
        try:
            # Existing reset logic
            logger.info(f"Resetting project {project_id}: {reason}")
            # ... existing implementation
        finally:
            lock.release()
    else:
        logger.error(f"Failed to acquire lock for reset of project {project_id}")
        return False
```

**Integration Points**:
- Wrap reset methods in scheduler.py
- Add to auto_orchestrate.py session management
- Use in concurrent operations

**Testing Strategy**:
- Unit tests for lock acquire/release/timeout
- Concurrency tests with threading
- Integration with existing reset flows

**Risk Mitigation**:
- Timeout prevents permanent deadlocks
- Automatic cleanup of stale lock files
- Fallback to queue reset for later if lock fails

**Estimated Effort**: 1-2 days

---

### 5. [LOW PRIORITY] Implement Default Resume Mode (TODO #5)
**Rationale**: Automates resumption of interrupted projects in daemon mode.

**Dependencies**: 
- Existing resume logic in auto_orchestrate.py
- scheduler.py's queue daemon

**Implementation Steps**:
1. Check for existing sessions before starting new projects
2. Attempt auto-resume if valid session found
3. Fallback to new session if resume fails

**Code Integration Point**:
```python
# In scheduler.py's run_queue_daemon() method:
# Before get_next_project_atomic():

def _attempt_auto_resume(self, project_path: str, spec_path: str) -> bool:
    """Attempt to resume existing orchestration for project"""
    try:
        # Check for existing session (pattern matching or JSON state)
        session_name = self._find_existing_session(project_path)
        if session_name:
            logger.info(f"Found existing session {session_name}, attempting auto-resume")
            
            cmd = [
                sys.executable, 'auto_orchestrate.py',
                '--project', project_path,
                '--resume',
                '--daemon'
            ]
            
            result = subprocess.run(cmd, cwd=self.tmux_orchestrator_path, 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Successfully resumed project {project_path}")
                return True
            else:
                logger.warning(f"Resume failed: {result.stderr}")
                
    except Exception as e:
        logger.error(f"Auto-resume attempt failed: {e}")
    
    return False

# Use in queue daemon:
if not self._attempt_auto_resume(project_path, spec_path):
    # Start new orchestration
    # ... existing logic
```

**Testing Strategy**:
- Mock interrupted projects and test auto-resume
- Verify fallback to new sessions
- Integration with queue daemon testing

**Risk Mitigation**:
- Health check before resume attempt
- Clear fallback path to new sessions
- Comprehensive logging of resume attempts

**Estimated Effort**: 1 day

---

### 6. [LOW PRIORITY] Add Pre-Flight Checks (TODO #2)
**Rationale**: Validates environment before tmux session creation, preventing partial failures.

**Dependencies**: None

**Implementation Steps**:
1. Create comprehensive environment validation
2. Check dependencies, conflicts, and resources
3. Integrate early in auto_orchestrate.py run()

**Code Integration Point**:
```python
# In auto_orchestrate.py, add new method:
def pre_flight_checks(self) -> bool:
    """Validate environment before starting orchestration"""
    checks = [
        self._check_tmux_available,
        self._check_git_repo_valid,
        self._check_dependencies_installed,
        self._check_no_session_conflicts,
        self._check_disk_space_sufficient
    ]
    
    for check in checks:
        try:
            if not check():
                return False
        except Exception as e:
            logger.error(f"Pre-flight check failed: {e}")
            return False
    
    logger.info("All pre-flight checks passed")
    return True

# Individual check methods:
def _check_tmux_available(self) -> bool:
    try:
        result = subprocess.run(['tmux', '-V'], capture_output=True)
        return result.returncode == 0
    except FileNotFoundError:
        logger.error("tmux not found - install tmux to continue")
        return False

def _check_no_session_conflicts(self) -> bool:
    # Check for session name conflicts
    return True  # Implementation details

# Call early in run() method:
if not self.pre_flight_checks():
    logger.error("Pre-flight checks failed - aborting")
    return False
```

**Testing Strategy**:
- Mock various failure conditions
- Test each individual check
- Integration with auto_orchestrate flow

**Risk Mitigation**:
- Graceful degradation for non-critical checks
- Clear error messages for user action
- Skip checks in daemon mode if needed

**Estimated Effort**: 1 day

---

### 7. [LOW PRIORITY] Add Session Conflict Resolution (TODO #3)
**Rationale**: Handles session name collisions during setup.

**Dependencies**: TODO #2 (pre-flight checks)

**Implementation Steps**:
1. Detect session conflicts during setup
2. Implement resolution strategies (kill, rename, prompt)
3. Integrate with session creation logic

**Testing Strategy**:
- Simulate various conflict scenarios
- Test resolution strategies
- Load testing with concurrent sessions

**Risk Mitigation**:
- Backup existing sessions before termination
- User confirmation in interactive mode
- Comprehensive logging of resolutions

**Estimated Effort**: 1-2 days

---

### 8. [OPTIMIZATION] Add Heartbeat System (TODO #8)
**Rationale**: Prevents premature timeouts during long-running operations.

**Dependencies**: process_manager.py

**Implementation Steps**:
1. Add heartbeat extension methods to ProcessManager
2. Integrate periodic heartbeats in long-running operations
3. Add adaptive timeout logic

**Testing Strategy**:
- Simulate long-running operations
- Verify timeout extensions work correctly
- Test under load conditions

**Risk Mitigation**:
- Cap maximum extensions to prevent abuse
- Monitor heartbeat frequency
- Fallback to original timeout if heartbeat fails

**Estimated Effort**: 1 day

---

## Testing Strategy

### Comprehensive Testing Plan
1. **Unit Tests**: Each TODO item gets dedicated unit tests
2. **Integration Tests**: Extend existing test_integration.py
3. **End-to-End Tests**: Use existing test infrastructure (test_reboot_recovery.py)
4. **Load Testing**: Use load_tester.py with new scenarios
5. **Chaos Testing**: Extend chaos_tester.py with new failure modes

### Test Coverage Goals
- 90%+ code coverage for new methods
- All error paths tested with mocked failures
- Concurrency testing for locking mechanisms
- Performance regression testing

## Risk Management

### High-Risk Items
1. **State Synchronization (#1)**: Could cause data loss if over-aggressive
   - Mitigation: Dry-run mode, comprehensive logging
2. **Project Locking (#6)**: Risk of deadlocks in multi-project scenarios
   - Mitigation: Timeouts, deadlock detection
3. **Null Session Repair (#7)**: Could mark active projects as failed
   - Mitigation: Multiple validation layers, atomic operations

### Medium-Risk Items  
4. **Database Reconciliation (#4)**: Could terminate valid sessions
   - Mitigation: Grace periods, confirmation steps
5. **Auto-Resume (#5)**: Could interfere with manual operations
   - Mitigation: Health checks, clear fallbacks

### Low-Risk Items
6. **Pre-flight Checks (#2)**: False positives could block valid operations
7. **Conflict Resolution (#3)**: Resolution strategies could be incorrect
8. **Heartbeat System (#8)**: Could extend timeouts inappropriately

## Documentation Updates

### Files to Update
- `README.md`: Add sections for new features
- `docs/REBOOT_RECOVERY.md`: Update with null session repair details
- Create new `docs/STATE_SYNCHRONIZATION.md`
- Create new `docs/PROJECT_LOCKING.md`

### API Documentation
- Document new environment variables
- Update command line options
- Add troubleshooting guides

## Deployment Plan

### Staging Testing
1. Test in WSL2/Linux environment
2. Run full test suite including chaos/load tests
3. Validate with real projects and specs

### Production Rollout
1. Deploy during low-usage window
2. Monitor logs for first 24 hours
3. Have rollback plan ready
4. Update systemd service if needed

### Monitoring
- Add metrics for new operations
- Set up alerts for failures
- Track performance impact

---

## Summary

This implementation plan provides a systematic approach to enhancing the Tmux Orchestrator with 8 critical improvements. The dependency-based ordering ensures stable progress, while comprehensive testing and risk mitigation strategies maintain system reliability.

**Key Success Metrics**:
- Reduced phantom project incidents (target: <1% of runs)
- Improved multi-project concurrency (target: 20+ concurrent projects)  
- Enhanced fault tolerance (target: 99.9% uptime)
- Streamlined user experience (target: 90% fewer manual interventions)

The modular implementation approach allows for iterative development and testing, ensuring each enhancement builds on a solid foundation.
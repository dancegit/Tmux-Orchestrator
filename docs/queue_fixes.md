# Queue System Fixes Documentation

## Overview
This document describes the fixes implemented to resolve batch processing issues in the Tmux Orchestrator queue system.

## Issues and Fixes

### 1. Sequential Batch Processing (FIXED ✅)
**Issue**: Multiple projects were being marked as IN_PROGRESS simultaneously instead of processing one at a time.

**Root Cause**: Non-atomic database operations in `get_next_project()` and `update_project_status()` caused race conditions when the queue daemon checked for new work.

**Fix Implementation**:
```python
def get_next_project_atomic(self) -> Optional[Dict[str, Any]]:
    """Atomically dequeue the next project if none are processing."""
    with self.queue_lock:
        try:
            with self.conn:  # Implicit BEGIN/COMMIT for transaction
                cursor = self.conn.cursor()
                
                # Step 1: Check if any project is already processing
                cursor.execute("SELECT COUNT(*) FROM project_queue WHERE status = 'processing'")
                active_count = cursor.fetchone()[0]
                if active_count > 0:
                    return None

                # Step 2: Select and update atomically
                cursor.execute("""
                    SELECT id, spec_path, project_path, batch_id, retry_count
                    FROM project_queue 
                    WHERE status = 'queued' 
                    ORDER BY priority DESC, enqueued_at ASC 
                    LIMIT 1
                """)
                # ... update to 'processing' within same transaction
```

**Result**: Projects now process sequentially with only one IN_PROGRESS at a time.

### 2. Duplicate Project Enqueuing (FIXED ✅)
**Issue**: Projects were being enqueued multiple times (e.g., Web Server #42 and #49).

**Root Cause**: `enqueue_project()` lacked idempotency checks, allowing duplicate entries when called multiple times.

**Fix Implementation**:
```python
def enqueue_project(self, spec_path: str, project_path: str = None, ...):
    """Add a project to the queue with idempotency checks"""
    # Check if project already exists in active states
    cursor.execute("""
        SELECT id, status, batch_id 
        FROM project_queue 
        WHERE spec_path = ? 
        AND (project_path = ? OR (project_path IS NULL AND ? IS NULL))
        AND status IN ('queued', 'processing')
        ORDER BY enqueued_at DESC
        LIMIT 1
    """, (spec_path, project_path, project_path))
    
    existing = cursor.fetchone()
    if existing:
        # Return existing ID instead of creating duplicate
        return existing[0]
```

**Database Constraint**:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_project 
ON project_queue(spec_path, project_path) 
WHERE status IN ('queued', 'processing')
```

**Result**: Duplicate enqueues are prevented at both application and database levels.

### 3. Premature Project Completion (FIXED ✅)
**Issue**: Projects were marked as "completed" within seconds of starting.

**Root Cause**: scheduler.py was incorrectly marking projects as "completed" immediately after auto_orchestrate.py finished its setup phase.

**Fix**: Removed the incorrect status update, keeping projects in 'processing' state until actual orchestration work completes.

## Testing

### Idempotent Enqueue Test
```python
# test_idempotent_enqueue.py
scheduler = TmuxOrchestratorScheduler()

# First enqueue
project_id1 = scheduler.enqueue_project("/tmp/test_spec.md", "/tmp/test_project")

# Second enqueue - should return same ID
project_id2 = scheduler.enqueue_project("/tmp/test_spec.md", "/tmp/test_project")

assert project_id1 == project_id2  # ✅ Passes
```

## Monitoring Enhancements

1. **Caller Traceback Logging**: Added stack trace logging to identify where duplicate enqueues originate
2. **Enhanced State Logging**: Better visibility into queue state transitions
3. **Atomic Operation Logging**: Debug logs for transaction boundaries

## Best Practices

1. **Always use atomic operations** for queue state changes
2. **Implement idempotency** for all enqueue operations
3. **Use database constraints** as a safety net
4. **Log state transitions** for debugging
5. **Test concurrent scenarios** to catch race conditions
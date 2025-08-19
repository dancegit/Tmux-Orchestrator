#!/usr/bin/env python3
"""
Test script for the project timeout and failure handling system.
Creates test scenarios and validates the complete timeout workflow.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from project_failure_handler import ProjectFailureHandler
from session_state import SessionStateManager, SessionState, AgentState
from scheduler import TmuxOrchestratorScheduler
from checkin_monitor import CheckinMonitor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_project_state(hours_old: float = 5.0) -> SessionState:
    """Create a test project state that appears to be running for the specified hours"""
    created_time = datetime.now() - timedelta(hours=hours_old)
    
    test_state = SessionState(
        session_name="test-timeout-project-impl-12345",
        project_path="/tmp/test_timeout_project",
        project_name="Test Timeout Project",
        implementation_spec_path="/tmp/test_spec.md",
        created_at=created_time.isoformat(),
        updated_at=datetime.now().isoformat(),
        agents={
            'orchestrator': AgentState(
                role='orchestrator',
                window_index=0,
                window_name='Orchestrator',
                worktree_path='/tmp/test_worktree/orchestrator',
                is_alive=True,
                is_exhausted=False
            ),
            'developer': AgentState(
                role='developer',
                window_index=1,
                window_name='Developer',
                worktree_path='/tmp/test_worktree/developer',
                is_alive=True,
                is_exhausted=True,  # Simulate exhausted agent
                credit_reset_time="2023-10-01T16:00:00"
            )
        },
        completion_status="pending",
        spec_path="/tmp/test_spec.md"
    )
    
    return test_state

def test_timeout_detection():
    """Test 1: Verify timeout detection logic"""
    logger.info("=== TEST 1: Timeout Detection ===")
    
    tmux_orchestrator_path = Path.cwd()
    monitor = CheckinMonitor(tmux_orchestrator_path)
    
    # Create a project that's 5 hours old
    old_project = create_test_project_state(hours_old=5.0)
    
    # Test timeout detection
    health = monitor.check_project_health("test-session", old_project)
    
    logger.info(f"Health status for 5-hour project: {health['status']}")
    logger.info(f"Issues: {health.get('issues', [])}")
    
    # Create a project that's only 2 hours old
    young_project = create_test_project_state(hours_old=2.0)
    health_young = monitor.check_project_health("test-session-young", young_project)
    
    logger.info(f"Health status for 2-hour project: {health_young['status']}")
    
    return health['status'] == 'critical' or 'timed out' in str(health.get('issues', []))

def test_batch_queue_detection():
    """Test 2: Verify batch queue detection"""
    logger.info("=== TEST 2: Batch Queue Detection ===")
    
    tmux_orchestrator_path = Path.cwd()
    
    # Create test scheduler and add some queued projects
    scheduler = TmuxOrchestratorScheduler()
    
    # Add a test project to the queue
    project_id = scheduler.enqueue_project("/tmp/test_spec1.md", "/tmp/test_project1")
    logger.info(f"Enqueued test project ID: {project_id}")
    
    # Test detection
    handler = ProjectFailureHandler(tmux_orchestrator_path)
    has_pending = handler.has_pending_batch_specs()
    
    logger.info(f"Has pending batch specs: {has_pending}")
    
    # Clean up
    scheduler.update_project_status(project_id, 'completed')
    
    return has_pending

def test_failure_handler():
    """Test 3: Verify failure handler functionality"""
    logger.info("=== TEST 3: Failure Handler ===")
    
    tmux_orchestrator_path = Path.cwd()
    state_manager = SessionStateManager(tmux_orchestrator_path)
    handler = ProjectFailureHandler(tmux_orchestrator_path)
    
    # Create and save test project state
    test_project = create_test_project_state(hours_old=5.5)
    state_manager.save_session_state(test_project)
    
    # Add a queued project to test progression
    scheduler = TmuxOrchestratorScheduler()
    next_project_id = scheduler.enqueue_project("/tmp/next_test_spec.md", "/tmp/next_test_project")
    
    try:
        # Test failure handling (won't actually clean tmux since session doesn't exist)
        success = handler.handle_timeout_failure(test_project.project_name, test_project)
        
        logger.info(f"Failure handling result: {success}")
        
        # Check if state was marked as failed
        updated_state = state_manager.load_session_state(test_project.project_name)
        if updated_state:
            logger.info(f"Updated completion status: {updated_state.completion_status}")
            logger.info(f"Failure reason: {updated_state.failure_reason}")
        
        # Check if failure was logged
        failure_log = tmux_orchestrator_path / 'registry' / 'logs' / 'failures.jsonl'
        if failure_log.exists():
            with open(failure_log, 'r') as f:
                lines = f.readlines()
                if lines:
                    try:
                        last_entry = json.loads(lines[-1].strip())
                        logger.info(f"Last failure log entry: {last_entry}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Could not parse failure log entry: {e}")
                        logger.info("Failure log exists and has entries")
        
        # Clean up
        scheduler.update_project_status(next_project_id, 'completed')
        
        return success and updated_state and updated_state.completion_status == 'failed'
        
    except Exception as e:
        logger.error(f"Failure handler test error: {e}")
        return False

def test_report_generation():
    """Test 4: Verify failure report generation"""
    logger.info("=== TEST 4: Report Generation ===")
    
    tmux_orchestrator_path = Path.cwd()
    handler = ProjectFailureHandler(tmux_orchestrator_path)
    
    # Create test project with status reports
    test_project = create_test_project_state(hours_old=4.5)
    test_project.status_reports = {
        'developer': {
            'topic': 'deployment',
            'status': 'FAILURE',
            'details': 'Test failure for report generation',
            'timestamp': datetime.now().isoformat()
        }
    }
    
    try:
        # Generate report
        report_path = handler._generate_failure_report(test_project.project_name, test_project, 4.5)
        
        logger.info(f"Generated report at: {report_path}")
        
        # Check if report exists and has content
        if report_path.exists():
            with open(report_path, 'r') as f:
                content = f.read()
                logger.info(f"Report length: {len(content)} characters")
                logger.info("Report contains failure details" if "Test failure" in content else "Report missing failure details")
            
            # Clean up
            report_path.unlink()
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Report generation test error: {e}")
        return False

def test_integration():
    """Test 5: Integration test with checkin_monitor"""
    logger.info("=== TEST 5: Integration Test ===")
    
    tmux_orchestrator_path = Path.cwd()
    state_manager = SessionStateManager(tmux_orchestrator_path)
    monitor = CheckinMonitor(tmux_orchestrator_path)
    scheduler = TmuxOrchestratorScheduler()
    
    # Create old project and save it
    old_project = create_test_project_state(hours_old=6.0)
    state_manager.save_session_state(old_project)
    
    # Add a queued project to trigger timeout conditions
    project_id = scheduler.enqueue_project("/tmp/integration_test_spec.md", "/tmp/integration_test_project")
    
    try:
        # Run monitoring check
        health = monitor.check_project_health(old_project.session_name, old_project)
        
        logger.info(f"Integration test health status: {health['status']}")
        logger.info(f"Integration test issues: {health.get('issues', [])}")
        logger.info(f"Integration test recommendations: {health.get('recommendations', [])}")
        
        # Check if project was handled
        handled = health.get('handled', False)
        logger.info(f"Project handled by timeout system: {handled}")
        
        # Clean up
        scheduler.update_project_status(project_id, 'completed')
        
        return 'timed out' in str(health.get('issues', []))
        
    except Exception as e:
        logger.error(f"Integration test error: {e}")
        return False

def run_all_tests():
    """Run all timeout system tests"""
    logger.info("🚀 Starting Timeout and Failure Handling System Tests")
    
    test_results = {
        'timeout_detection': test_timeout_detection(),
        'batch_queue_detection': test_batch_queue_detection(),
        'failure_handler': test_failure_handler(),
        'report_generation': test_report_generation(),
        'integration': test_integration()
    }
    
    logger.info("\\n" + "="*50)
    logger.info("📋 TEST RESULTS SUMMARY")
    logger.info("="*50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name.upper().replace('_', ' ')}: {status}")
        if result:
            passed += 1
    
    logger.info("="*50)
    logger.info(f"OVERALL: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        logger.info("🎉 All tests passed! Timeout system is working correctly.")
    else:
        logger.error("⚠️  Some tests failed. Check implementation.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
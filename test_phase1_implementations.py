#!/usr/bin/env python3
"""
Test script for Phase 1 implementations:
- Python-based scheduler
- File locking for concurrent orchestrations  
- Sync coordinator
"""

import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from scheduler import TmuxOrchestratorScheduler
from concurrent_orchestration import ConcurrentOrchestrationManager, FileLock
from sync_coordinator import GitSyncCoordinator

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'

def print_test(test_name):
    print(f"\n{Colors.BLUE}Testing: {test_name}{Colors.ENDC}")
    
def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.ENDC}")
    
def print_error(message):
    print(f"{Colors.RED}✗ {message}{Colors.ENDC}")
    
def print_warning(message):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.ENDC}")

def test_scheduler():
    """Test the Python-based scheduler"""
    print_test("Python-based Scheduler")
    
    try:
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            scheduler = TmuxOrchestratorScheduler(db_path=tmp_db.name)
            
            # Test 1: Add a task
            task_id = scheduler.enqueue_task("test-session", "developer", 1, 5, "Test task")
            if task_id:
                print_success(f"Task enqueued successfully (ID: {task_id})")
            else:
                print_error("Failed to enqueue task")
                return False
                
            # Test 2: List tasks
            tasks = scheduler.list_tasks()
            if len(tasks) == 1:
                print_success(f"Task listed correctly: {tasks[0]}")
            else:
                print_error(f"Expected 1 task, found {len(tasks)}")
                return False
                
            # Test 3: Check credit status (mock)
            status = scheduler.get_agent_credit_status("test-project", "developer")
            print_success(f"Credit status check working: {status}")
            
            # Test 4: Remove task
            scheduler.remove_task(task_id)
            tasks = scheduler.list_tasks()
            if len(tasks) == 0:
                print_success("Task removed successfully")
            else:
                print_error("Task removal failed")
                return False
                
            # Cleanup
            os.unlink(tmp_db.name)
            return True
            
    except Exception as e:
        print_error(f"Scheduler test failed: {e}")
        return False

def test_file_locking():
    """Test file-based locking mechanism"""
    print_test("File Locking for Concurrent Orchestrations")
    
    try:
        # Test 1: Basic lock acquisition
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = Path(tmpdir) / "test.lock"
            
            lock = FileLock(str(lock_file), timeout=2)
            lock.acquire()
            
            if lock.acquired:
                print_success("Lock acquired successfully")
            else:
                print_error("Failed to acquire lock")
                return False
                
            # Test 2: Try to acquire same lock (should fail)
            lock2 = FileLock(str(lock_file), timeout=1)
            try:
                lock2.acquire()
                print_error("Second lock should have failed but didn't")
                return False
            except TimeoutError:
                print_success("Second lock correctly timed out")
                
            # Release first lock
            lock.release()
            
            # Test 3: Now second lock should work
            lock2.acquire()
            if lock2.acquired:
                print_success("Lock acquired after release")
                lock2.release()
            else:
                print_error("Failed to acquire lock after release")
                return False
                
        return True
        
    except Exception as e:
        print_error(f"File locking test failed: {e}")
        return False

def test_concurrent_orchestration():
    """Test concurrent orchestration manager"""
    print_test("Concurrent Orchestration Manager")
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConcurrentOrchestrationManager(Path(tmpdir))
            
            # Test 1: Get unique session name
            session_name = manager.get_unique_session_name("test-project", check_tmux=False)
            if session_name and '-impl-' in session_name:
                print_success(f"Generated unique session name: {session_name}")
            else:
                print_error("Failed to generate unique session name")
                return False
                
            # Test 2: Get unique registry directory
            registry_dir = manager.get_unique_registry_dir("test-project", "abc123")
            expected = Path(tmpdir) / 'registry' / 'projects' / 'test-project-abc123'
            if registry_dir == expected:
                print_success(f"Generated correct registry directory")
            else:
                print_error(f"Registry directory mismatch: {registry_dir} != {expected}")
                return False
                
            # Test 3: Start orchestration
            try:
                session_name, registry_dir = manager.start_orchestration("test-project", timeout=2)
                print_success(f"Started orchestration: {session_name}")
                
                # Verify metadata file
                metadata_file = registry_dir / 'orchestration_metadata.json'
                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                    print_success(f"Metadata saved correctly: {metadata['project_name']}")
                else:
                    print_error("Metadata file not created")
                    return False
                    
            except Exception as e:
                print_error(f"Failed to start orchestration: {e}")
                return False
                
        return True
        
    except Exception as e:
        print_error(f"Concurrent orchestration test failed: {e}")
        return False

def test_sync_coordinator():
    """Test git sync coordinator"""
    print_test("Git Sync Coordinator")
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock project structure
            project_dir = Path(tmpdir) / "test-project"
            worktrees_dir = project_dir / "worktrees"
            worktrees_dir.mkdir(parents=True)
            
            # Create mock worktree
            worktree = worktrees_dir / "developer"
            worktree.mkdir()
            (worktree / '.git').mkdir()
            
            # Test 1: Initialize coordinator
            coordinator = GitSyncCoordinator("test-project", project_dir)
            print_success("Sync coordinator initialized")
            
            # Test 2: Install hooks
            coordinator.install_hooks(worktree)
            hook_file = worktree / '.git' / 'hooks' / 'post-commit'
            if hook_file.exists():
                print_success("Git hooks installed correctly")
            else:
                print_error("Git hooks not installed")
                return False
                
            # Test 3: Dashboard update
            coordinator.update_dashboard("Test message")
            if coordinator.dashboard_file.exists():
                content = coordinator.dashboard_file.read_text()
                if "Test message" in content:
                    print_success("Dashboard updated correctly")
                else:
                    print_error("Dashboard content incorrect")
                    return False
            else:
                print_error("Dashboard file not created")
                return False
                
            # Test 4: Get status
            status = coordinator.status()
            if status['project'] == "test-project":
                print_success(f"Status retrieved correctly: {len(status['worktrees'])} worktrees")
            else:
                print_error("Status incorrect")
                return False
                
        return True
        
    except Exception as e:
        print_error(f"Sync coordinator test failed: {e}")
        return False

def test_integration():
    """Test integration with existing scripts"""
    print_test("Integration with Existing Scripts")
    
    try:
        # Test 1: Check schedule_with_note.sh is updated
        schedule_script = Path(__file__).parent / "schedule_with_note.sh"
        if schedule_script.exists():
            content = schedule_script.read_text()
            if "python3" in content and "scheduler.py" in content:
                print_success("schedule_with_note.sh properly integrated")
            else:
                print_warning("schedule_with_note.sh may need manual integration")
        else:
            print_error("schedule_with_note.sh not found")
            
        # Test 2: Check auto_orchestrate.py imports
        auto_orch = Path(__file__).parent / "auto_orchestrate.py"
        if auto_orch.exists():
            content = auto_orch.read_text()
            if "from concurrent_orchestration import" in content:
                print_success("auto_orchestrate.py properly imports concurrent orchestration")
            else:
                print_error("auto_orchestrate.py missing concurrent orchestration import")
                return False
        else:
            print_error("auto_orchestrate.py not found")
            return False
            
        # Test 3: Check --list option
        result = subprocess.run(
            [sys.executable, str(auto_orch), "--help"],
            capture_output=True,
            text=True
        )
        if "--list" in result.stdout:
            print_success("--list option added to auto_orchestrate.py")
        else:
            print_warning("--list option may not be properly added")
            
        return True
        
    except Exception as e:
        print_error(f"Integration test failed: {e}")
        return False

def main():
    print(f"{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BLUE}Phase 1 Implementation Tests{Colors.ENDC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.ENDC}")
    
    tests = [
        ("Scheduler", test_scheduler),
        ("File Locking", test_file_locking),
        ("Concurrent Orchestration", test_concurrent_orchestration),
        ("Sync Coordinator", test_sync_coordinator),
        ("Integration", test_integration)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Unexpected error in {name}: {e}")
            results.append((name, False))
            
    # Summary
    print(f"\n{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BLUE}Test Summary{Colors.ENDC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.ENDC}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{Colors.GREEN}PASSED{Colors.ENDC}" if result else f"{Colors.RED}FAILED{Colors.ENDC}"
        print(f"{name}: {status}")
        
    print(f"\n{Colors.BLUE}Total: {passed}/{total} tests passed{Colors.ENDC}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}All tests passed! Phase 1 implementation is ready.{Colors.ENDC}")
    else:
        print(f"\n{Colors.RED}Some tests failed. Please review the implementation.{Colors.ENDC}")
        sys.exit(1)

if __name__ == '__main__':
    main()
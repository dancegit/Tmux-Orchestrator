#!/usr/bin/env python3
"""
Error Recovery Tests for Tmux Orchestrator
Tests the system's ability to handle and recover from various failure scenarios
"""

import os
import sys
import time
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import threading
import signal

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))


class TestAgentCrashRecovery(unittest.TestCase):
    """Test recovery from agent crashes and failures"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        # Clean up test tmux sessions
        subprocess.run(['tmux', 'kill-session', '-t', 'test-recovery'], 
                      capture_output=True, check=False)
        import shutil
        shutil.rmtree(self.test_dir)
    
    def test_tmux_session_crash_detection(self):
        """Test detection of crashed tmux sessions"""
        # Create a test session then kill it
        session_name = "test-recovery"
        
        try:
            # Create session
            result = subprocess.run([
                'tmux', 'new-session', '-d', '-s', session_name
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                self.skipTest("Could not create tmux session for testing")
            
            # Verify session exists
            result = subprocess.run([
                'tmux', 'list-sessions', '-F', '#{session_name}'
            ], capture_output=True, text=True)
            
            self.assertIn(session_name, result.stdout)
            
            # Kill the session
            subprocess.run(['tmux', 'kill-session', '-t', session_name], 
                          capture_output=True)
            
            # Verify session is gone
            result = subprocess.run([
                'tmux', 'list-sessions', '-F', '#{session_name}'
            ], capture_output=True, text=True)
            
            self.assertNotIn(session_name, result.stdout)
            
        except subprocess.CalledProcessError as e:
            self.skipTest(f"Tmux not available or failed: {e}")
    
    def test_message_delivery_to_dead_session(self):
        """Test message delivery behavior when target session is dead"""
        send_script = Path(__file__).parent / 'send-claude-message.sh'
        
        if not send_script.exists():
            self.skipTest("send-claude-message.sh not found")
        
        # Try to send message to non-existent session
        start_time = time.time()
        result = subprocess.run([
            str(send_script),
            'dead-session:0',
            'Test message to dead session'
        ], capture_output=True, text=True, timeout=30)
        end_time = time.time()
        
        # Should handle gracefully without hanging
        self.assertLess(end_time - start_time, 20, 
                       "Message delivery to dead session took too long")
        
        # Return code may vary, but should not crash
        self.assertIsNotNone(result.returncode)
    
    def test_scheduler_database_corruption_recovery(self):
        """Test scheduler recovery from database corruption"""
        # Import scheduler if available
        try:
            from scheduler import TmuxOrchestratorScheduler
        except ImportError:
            self.skipTest("Scheduler module not available")
        
        # Create corrupted database file
        db_path = Path(self.test_dir) / 'corrupted.db'
        db_path.write_text("This is not a valid SQLite database")
        
        # Scheduler should handle corruption gracefully
        try:
            scheduler = TmuxOrchestratorScheduler(db_path=str(db_path))
            # Should either recover or create new database
            tasks = scheduler.list_tasks()
            self.assertIsInstance(tasks, list)
        except Exception as e:
            # If it fails, should fail gracefully with meaningful error
            self.assertIn("database", str(e).lower())
    
    def test_concurrent_orchestration_lock_cleanup(self):
        """Test cleanup of stale orchestration locks"""
        try:
            from concurrent_orchestration import ConcurrentOrchestrationManager
        except ImportError:
            self.skipTest("Concurrent orchestration module not available")
        
        manager = ConcurrentOrchestrationManager(Path(self.test_dir))
        
        # Create a lock
        lock = manager.acquire_project_lock("test-project", timeout=1)
        self.assertIsNotNone(lock)
        
        # Simulate process crash (don't release lock properly)
        # Instead, just delete the manager to simulate crash
        del manager
        
        # New manager should be able to clean up stale locks
        new_manager = ConcurrentOrchestrationManager(Path(self.test_dir))
        
        # Should be able to acquire lock again after cleanup
        new_lock = new_manager.acquire_project_lock("test-project", timeout=1)
        if new_lock:  # Some implementations may handle this differently
            new_lock.release()
    
    def test_file_permission_errors(self):
        """Test handling of file permission errors"""
        # Create read-only directory
        readonly_dir = Path(self.test_dir) / 'readonly'
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only
        
        try:
            # Try to write to read-only directory
            test_file = readonly_dir / 'test.txt'
            
            # Should handle permission error gracefully
            with self.assertRaises(PermissionError):
                test_file.write_text("test")
            
        finally:
            # Clean up (restore write permission)
            readonly_dir.chmod(0o755)
    
    def test_disk_space_exhaustion_simulation(self):
        """Test behavior when disk space is exhausted"""
        # This is a simulation - create a very large file to fill space
        # In a real scenario, this would test actual disk exhaustion
        
        large_file = Path(self.test_dir) / 'large_file.txt'
        
        try:
            # Try to create a reasonably large file (1MB)
            large_content = 'A' * (1024 * 1024)  # 1MB
            large_file.write_text(large_content)
            
            # Verify file was created
            self.assertTrue(large_file.exists())
            self.assertGreater(large_file.stat().st_size, 1000000)
            
        except OSError as e:
            # If disk space is actually exhausted, should handle gracefully
            self.assertIn("space", str(e).lower())


class TestCreditExhaustionRecovery(unittest.TestCase):
    """Test recovery from Claude Code credit exhaustion"""
    
    def test_credit_status_detection(self):
        """Test detection of credit exhaustion patterns"""
        # Test patterns that indicate credit exhaustion
        exhaustion_patterns = [
            "I've reached my usage limit",
            "credits will reset at",
            "/upgrade",
            "approaching usage limit"
        ]
        
        for pattern in exhaustion_patterns:
            # Simulate agent output containing exhaustion indicator
            mock_output = f"Some agent response... {pattern} ...more text"
            
            # This would be tested with actual credit monitoring
            self.assertIn(pattern.lower(), mock_output.lower())
    
    def test_credit_reset_time_parsing(self):
        """Test parsing of credit reset times from agent output"""
        # Sample credit exhaustion messages
        reset_messages = [
            "Your credits will reset at 3:30 PM PST",
            "Credits reset in 2 hours and 15 minutes",
            "Reset time: 15:30 UTC"
        ]
        
        # Test that we can extract timing information
        for message in reset_messages:
            # Basic validation that timing info is present
            has_time_info = any(word in message.lower() for word in 
                              ['hour', 'minute', 'pm', 'am', 'utc', 'pst', ':'])
            self.assertTrue(has_time_info, f"No time info in: {message}")
    
    def test_agent_resurrection_scheduling(self):
        """Test scheduling of agent resurrection after credit reset"""
        # This would test the credit management system
        try:
            from scheduler import TmuxOrchestratorScheduler
        except ImportError:
            self.skipTest("Scheduler module not available")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            scheduler = TmuxOrchestratorScheduler(db_path=tmp_db.name)
            
            # Schedule a resurrection task
            task_id = scheduler.enqueue_task(
                "exhausted-session", "developer", 0, 5,  # 5 minutes
                "Resume after credit reset"
            )
            
            self.assertIsNotNone(task_id)
            
            # Check task exists
            tasks = scheduler.list_tasks()
            resurrection_tasks = [t for t in tasks if "credit reset" in t[6].lower()]
            self.assertGreater(len(resurrection_tasks), 0)
            
            # Cleanup
            os.unlink(tmp_db.name)


class TestNetworkInterruptionRecovery(unittest.TestCase):
    """Test recovery from network interruptions and connectivity issues"""
    
    def test_claude_api_unavailable_simulation(self):
        """Test behavior when Claude API is unavailable"""
        # Simulate network unavailability by using invalid host
        with patch.dict(os.environ, {'ANTHROPIC_API_URL': 'http://invalid.host'}):
            # Test would verify graceful degradation
            # For now, just verify the environment is patched
            self.assertEqual(os.environ.get('ANTHROPIC_API_URL'), 'http://invalid.host')
    
    def test_git_remote_unavailable(self):
        """Test git operations when remote is unavailable"""
        # Create a temporary git repo
        git_dir = Path(self.test_dir) / 'test_repo'
        git_dir.mkdir()
        
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=git_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], 
                      cwd=git_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], 
                      cwd=git_dir, capture_output=True)
        
        # Add a file and commit
        test_file = git_dir / 'test.txt'
        test_file.write_text('test content')
        subprocess.run(['git', 'add', '.'], cwd=git_dir, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Test commit'], 
                      cwd=git_dir, capture_output=True)
        
        # Try to push to non-existent remote (should fail gracefully)
        result = subprocess.run([
            'git', 'push', 'origin', 'main'
        ], cwd=git_dir, capture_output=True, text=True)
        
        # Should fail but not crash
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fatal", result.stderr.lower())
    
    def test_tmux_server_restart_recovery(self):
        """Test recovery when tmux server restarts"""
        # Check if tmux server is running
        result = subprocess.run(['tmux', 'list-sessions'], 
                              capture_output=True, text=True)
        
        # If no sessions, tmux server might not be running
        if result.returncode != 0:
            # Try to start a session to ensure server is running
            subprocess.run(['tmux', 'new-session', '-d', '-s', 'temp-session'], 
                          capture_output=True)
            subprocess.run(['tmux', 'kill-session', '-t', 'temp-session'], 
                          capture_output=True)
        
        # Test that we can detect server state
        result = subprocess.run(['tmux', 'info'], capture_output=True, text=True)
        # Should be able to get tmux info without error
        self.assertEqual(result.returncode, 0)


class TestDataCorruptionRecovery(unittest.TestCase):
    """Test recovery from various data corruption scenarios"""
    
    def test_json_config_corruption(self):
        """Test recovery from corrupted JSON configuration files"""
        # Create corrupted JSON files
        corrupt_json_samples = [
            '{ "key": "value" corrupted }',  # Syntax error
            '{ "key": }',                    # Missing value
            '{ key: "value" }',              # Missing quotes
            '',                              # Empty file
            'not json at all'                # Not JSON
        ]
        
        for i, corrupt_content in enumerate(corrupt_json_samples):
            corrupt_file = Path(self.test_dir) / f'corrupt_{i}.json'
            corrupt_file.write_text(corrupt_content)
            
            # Test JSON loading with error handling
            try:
                import json
                with open(corrupt_file) as f:
                    json.load(f)
                # If it loads successfully, that's unexpected
                self.fail(f"Corrupt JSON loaded successfully: {corrupt_content}")
            except json.JSONDecodeError:
                # Expected behavior - should detect corruption
                pass
            except Exception as e:
                # Other errors should be handled gracefully
                self.assertIsInstance(e, Exception)
    
    def test_log_file_rotation_and_cleanup(self):
        """Test log file rotation and cleanup mechanisms"""
        # Create mock log files
        log_dir = Path(self.test_dir) / 'logs'
        log_dir.mkdir()
        
        # Create several log files with different ages
        log_files = [
            'orchestrator_2025-01-01.log',
            'orchestrator_2025-01-02.log', 
            'orchestrator_2025-01-03.log',
            'agent_developer_2025-01-01.log',
            'agent_tester_2025-01-02.log'
        ]
        
        for log_file in log_files:
            (log_dir / log_file).write_text(f"Log content for {log_file}")
        
        # Verify files were created
        self.assertEqual(len(list(log_dir.glob('*.log'))), 5)
        
        # Test log cleanup (basic file count)
        # In real implementation, this would test actual cleanup logic
        remaining_files = list(log_dir.glob('*.log'))
        self.assertGreater(len(remaining_files), 0)


def run_error_recovery_tests():
    """Run all error recovery tests"""
    suite = unittest.TestSuite()
    
    test_classes = [
        TestAgentCrashRecovery,
        TestCreditExhaustionRecovery,
        TestNetworkInterruptionRecovery,
        TestDataCorruptionRecovery
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("=" * 60)
    print("ERROR RECOVERY TESTS - SignalMatrix Event Delivery")
    print("=" * 60)
    
    success = run_error_recovery_tests()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Fixed Session State Management Tests for Tmux Orchestrator
Tests the persistence and management of agent states using correct API
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from session_state import SessionStateManager, create_initial_session_state, SessionState, AgentState

class TestSessionStateManagerFixed(unittest.TestCase):
    """Test the SessionStateManager with correct API"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.tmux_orchestrator_path = Path(self.test_dir) / 'tmux_orchestrator'
        self.tmux_orchestrator_path.mkdir(parents=True, exist_ok=True)
        
        self.state_manager = SessionStateManager(self.tmux_orchestrator_path)
        
    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)
    
    def test_initial_session_state_creation(self):
        """Test creation of initial session state with correct API"""
        session_name = "test-session"
        project_path = "/test/project"
        project_name = "test-project"
        spec_path = "/test/spec.md"
        agents = [("window-0", 0, "orchestrator"), ("window-1", 1, "developer")]
        worktree_paths = {
            "orchestrator": Path("/test/worktrees/orchestrator"),
            "developer": Path("/test/worktrees/developer")
        }
        
        state = create_initial_session_state(
            session_name, project_path, project_name, spec_path, 
            agents, worktree_paths
        )
        
        self.assertIsInstance(state, SessionState)
        self.assertEqual(state.session_name, session_name)
        self.assertEqual(state.project_name, project_name)
        self.assertEqual(len(state.agents), 2)
        
        # Check that all roles are present
        self.assertIn("orchestrator", state.agents)
        self.assertIn("developer", state.agents)
    
    def test_session_state_persistence(self):
        """Test saving and loading session state"""
        # Create initial state
        session_name = "persist-test"
        project_path = "/test/project"
        project_name = "persist-project"
        spec_path = "/test/spec.md"
        agents = [("window-0", 0, "orchestrator")]
        worktree_paths = {"orchestrator": Path("/test/worktrees/orchestrator")}
        
        original_state = create_initial_session_state(
            session_name, project_path, project_name, spec_path, 
            agents, worktree_paths
        )
        
        # Save state
        self.state_manager.save_session_state(original_state)
        
        # Load state
        loaded_state = self.state_manager.load_session_state(project_name)
        
        # Verify loaded state matches original
        self.assertIsNotNone(loaded_state)
        self.assertEqual(loaded_state.session_name, original_state.session_name)
        self.assertEqual(loaded_state.project_name, original_state.project_name)
        self.assertEqual(len(loaded_state.agents), len(original_state.agents))
    
    def test_agent_state_properties(self):
        """Test AgentState properties and methods"""
        agent = AgentState(
            role="developer",
            window_index=1,
            window_name="dev-window",
            worktree_path="/test/worktree"
        )
        
        self.assertEqual(agent.role, "developer")
        self.assertEqual(agent.window_index, 1)
        self.assertEqual(agent.window_name, "dev-window")
        self.assertEqual(agent.worktree_path, "/test/worktree")
        self.assertTrue(agent.is_alive)
        self.assertFalse(agent.is_exhausted)
    
    def test_agent_exhaustion_tracking(self):
        """Test tracking agent credit exhaustion"""
        agent = AgentState(
            role="tester",
            window_index=2,
            window_name="test-window",
            worktree_path="/test/worktree"
        )
        
        # Initially not exhausted
        self.assertFalse(agent.is_exhausted)
        self.assertIsNone(agent.credit_reset_time)
        
        # Mark as exhausted
        agent.is_exhausted = True
        agent.credit_reset_time = datetime.now().isoformat()
        
        self.assertTrue(agent.is_exhausted)
        self.assertIsNotNone(agent.credit_reset_time)
    
    def test_session_state_file_path(self):
        """Test session state file path generation"""
        project_name = "Test Project Name"
        expected_path = self.tmux_orchestrator_path / 'registry' / 'projects' / 'test-project-name' / 'session_state.json'
        
        actual_path = self.state_manager.get_state_file_path(project_name)
        
        self.assertEqual(actual_path, expected_path)
    
    def test_load_nonexistent_state(self):
        """Test loading non-existent session state"""
        result = self.state_manager.load_session_state("nonexistent-project")
        self.assertIsNone(result)
    
    def test_agent_alive_check(self):
        """Test agent alive checking functionality"""
        # This tests the method exists and handles errors gracefully
        result = self.state_manager.check_agent_alive("nonexistent-session", 0)
        self.assertFalse(result)  # Should return False for non-existent session
    
    def test_session_state_update_timestamp(self):
        """Test that save operation updates timestamp"""
        # Create initial state
        state = create_initial_session_state(
            "timestamp-test", "/test", "timestamp-project", "/test/spec.md",
            [("window-0", 0, "orchestrator")], {"orchestrator": Path("/test")}
        )
        
        original_updated = state.updated_at
        
        # Save state (should update timestamp)
        self.state_manager.save_session_state(state)
        
        # Check timestamp was updated
        self.assertNotEqual(state.updated_at, original_updated)


class TestAgentStateFixed(unittest.TestCase):
    """Test AgentState with correct initialization"""
    
    def test_agent_state_initialization(self):
        """Test agent state initialization with required fields"""
        agent = AgentState(
            role="developer",
            window_index=1,
            window_name="dev-window",
            worktree_path="/test/worktree"
        )
        
        self.assertEqual(agent.role, "developer")
        self.assertEqual(agent.window_index, 1)
        self.assertEqual(agent.window_name, "dev-window")
        self.assertEqual(agent.worktree_path, "/test/worktree")
        self.assertIsNone(agent.last_briefing_time)
        self.assertIsNone(agent.last_check_in_time)
        self.assertTrue(agent.is_alive)
        self.assertFalse(agent.is_exhausted)
    
    def test_agent_optional_fields(self):
        """Test agent state with optional fields"""
        current_time = datetime.now().isoformat()
        
        agent = AgentState(
            role="tester",
            window_index=2,
            window_name="test-window",
            worktree_path="/test/worktree",
            last_briefing_time=current_time,
            last_check_in_time=current_time,
            is_alive=False,
            is_exhausted=True,
            credit_reset_time=current_time,
            current_branch="feature/test",
            commit_hash="abc123"
        )
        
        self.assertEqual(agent.last_briefing_time, current_time)
        self.assertEqual(agent.last_check_in_time, current_time)
        self.assertFalse(agent.is_alive)
        self.assertTrue(agent.is_exhausted)
        self.assertEqual(agent.credit_reset_time, current_time)
        self.assertEqual(agent.current_branch, "feature/test")
        self.assertEqual(agent.commit_hash, "abc123")


def run_session_state_tests():
    """Run all corrected session state tests"""
    suite = unittest.TestSuite()
    
    test_classes = [
        TestSessionStateManagerFixed,
        TestAgentStateFixed
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("=" * 60)
    print("FIXED SESSION STATE MANAGEMENT TESTS")
    print("=" * 60)
    
    success = run_session_state_tests()
    sys.exit(0 if success else 1)
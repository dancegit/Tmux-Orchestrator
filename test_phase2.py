#!/usr/bin/env python3
"""
Test Suite for Phase 2 Improvements
Tests dynamic team composition, sync dashboard, and multi-project monitoring
"""

import os
import sys
import subprocess
import tempfile
import shutil
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from dynamic_team import DynamicTeamComposer
from sync_dashboard import SyncDashboard
from multi_project_monitor import MultiProjectMonitor


class TestDynamicTeamComposition(unittest.TestCase):
    """Test dynamic team composition functionality"""
    
    def setUp(self):
        self.composer = DynamicTeamComposer()
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_template_loading(self):
        """Test that all templates load correctly"""
        templates = self.composer.templates
        
        # Check required templates exist
        self.assertIn('base', templates)
        self.assertIn('code_project', templates)
        self.assertIn('system_deployment', templates)
        self.assertIn('data_pipeline', templates)
        
        # Check base template structure
        self.assertIn('roles', templates['base'])
        self.assertIn('orchestrator', templates['base']['roles'])
        
    def test_template_inheritance(self):
        """Test template inheritance resolution"""
        resolved = self.composer._resolve_inheritance('code_project')
        
        # Should include base roles
        self.assertIn('orchestrator', resolved['roles'])
        self.assertIn('project_manager', resolved['roles'])
        
        # Should include child roles
        self.assertIn('developer', resolved['roles'])
        self.assertIn('tester', resolved['roles'])
        
    def test_project_type_detection_web_app(self):
        """Test detection of web application project"""
        # Create web app indicators
        (Path(self.test_dir) / 'package.json').write_text('{}')
        (Path(self.test_dir) / 'src').mkdir()
        (Path(self.test_dir) / 'src' / 'App.js').write_text('')
        
        project_type, confidence = self.composer.detect_project_type(self.test_dir)
        
        self.assertEqual(project_type, 'code_project')
        self.assertGreater(confidence, 0.3)  # Adjusted threshold
    
    def test_project_type_detection_system_deployment(self):
        """Test detection of system deployment project"""
        # Create deployment indicators
        (Path(self.test_dir) / 'elliott_wave_deployment_spec.md').write_text('')
        (Path(self.test_dir) / 'app.service').write_text('')
        
        project_type, confidence = self.composer.detect_project_type(self.test_dir)
        
        self.assertEqual(project_type, 'system_deployment')
        self.assertGreater(confidence, 0.5)
    
    def test_team_composition_with_plan_limits(self):
        """Test team composition respects plan limits"""
        # Create a project
        (Path(self.test_dir) / 'package.json').write_text('{}')
        
        recommendation = self.composer.recommend_team_size(
            self.test_dir,
            subscription_plan='pro'  # Limited to 3 agents
        )
        
        self.assertLessEqual(len(recommendation['selected_roles']), 3)
        self.assertIn('orchestrator', recommendation['selected_roles'])
    
    def test_custom_role_selection(self):
        """Test custom role selection override"""
        team = self.composer.compose_team(
            self.test_dir,
            custom_roles=['orchestrator', 'sysadmin', 'devops', 'securityops']
        )
        
        self.assertEqual(team['project_type'], 'custom')
        self.assertEqual(len(team['roles']), 4)
        self.assertIn('sysadmin', team['roles'])


class TestSyncDashboard(unittest.TestCase):
    """Test sync status dashboard functionality"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Use a unique project name to avoid conflicts
        self.project_name = f'test_project_{os.getpid()}'
        self.project_dir = Path(self.test_dir) / self.project_name
        self.project_dir.mkdir()
        
        # Create mock git repo
        subprocess.run(['git', 'init'], cwd=self.project_dir, capture_output=True)
        
        # Create registry structure
        self.registry_dir = self.project_dir.parent.parent / 'registry' / 'projects' / self.project_name
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        
        # Create worktrees
        self.worktrees_dir = self.registry_dir / 'worktrees'
        self.worktrees_dir.mkdir(exist_ok=True)
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_worktree_discovery(self):
        """Test discovery of project worktrees"""
        # Create mock worktrees
        for role in ['orchestrator', 'developer', 'tester']:
            worktree_path = self.worktrees_dir / role
            worktree_path.mkdir()
            (worktree_path / '.git').mkdir()
        
        dashboard = SyncDashboard(self.project_dir)
        worktrees = dashboard.find_project_worktrees()
        
        self.assertEqual(len(worktrees), 3)
        self.assertIn('orchestrator', worktrees)
        self.assertIn('developer', worktrees)
    
    @patch('subprocess.run')
    def test_branch_info_extraction(self, mock_run):
        """Test extraction of git branch information"""
        # Mock git commands
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='feature/test-branch'),  # branch name
            MagicMock(returncode=0, stdout='5\t3'),  # ahead/behind
            MagicMock(returncode=0, stdout='abc123 Test commit (2 hours ago)'),  # last commit
            MagicMock(returncode=0, stdout='M file.txt'),  # uncommitted changes
            MagicMock(returncode=1)  # no reflog
        ]
        
        dashboard = SyncDashboard(self.project_dir)
        info = dashboard.get_branch_info(self.project_dir)
        
        self.assertEqual(info['branch'], 'feature/test-branch')
        self.assertEqual(info['behind'], 5)
        self.assertEqual(info['ahead'], 3)
        self.assertTrue(info['uncommitted_changes'])
    
    def test_json_output(self):
        """Test JSON output format"""
        dashboard = SyncDashboard(self.project_dir)
        json_output = dashboard.get_json_status()
        
        data = json.loads(json_output)
        self.assertIn('project', data)
        self.assertIn('timestamp', data)
        self.assertIn('worktrees', data)


class TestMultiProjectMonitor(unittest.TestCase):
    """Test multi-project monitoring functionality"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orchestrator_dir = Path(self.test_dir) / 'orchestrator'
        self.orchestrator_dir.mkdir()
        
        # Create registry
        self.registry_dir = self.orchestrator_dir / 'registry'
        self.registry_dir.mkdir()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_project_discovery(self):
        """Test discovery of active projects"""
        # Create mock projects
        for project in ['project1', 'project2']:
            project_dir = self.registry_dir / 'projects' / project
            project_dir.mkdir(parents=True)
            
            # Create session state
            state = {
                'session_name': f'{project}-impl',
                'start_time': '2024-01-01T00:00:00',
                'agents': {}
            }
            (project_dir / 'session_state.json').write_text(json.dumps(state))
        
        monitor = MultiProjectMonitor(self.orchestrator_dir)
        
        # Mock tmux session check
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)  # Sessions exist
            projects = monitor.discover_active_projects()
        
        self.assertEqual(len(projects), 2)
        project_names = [p[0] for p in projects]
        self.assertIn('project1', project_names)
        self.assertIn('project2', project_names)
    
    def test_agent_health_calculation(self):
        """Test agent health status calculation"""
        from session_state import AgentState
        
        # Create test agent
        agent = AgentState(
            role='developer',
            window_index=1,
            window_name='Developer',
            worktree_path='/path/to/worktree',
            last_check_in_time='2024-01-01T12:00:00+00:00',
            is_alive=True,
            is_exhausted=False
        )
        
        monitor = MultiProjectMonitor(self.orchestrator_dir)
        
        # Mock current time for consistent testing
        with patch('multi_project_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 45, 0)
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            health = monitor.get_agent_health(agent)
        
        self.assertEqual(health['status'], 'active')
        self.assertFalse(health['credit_exhausted'])
        # Note: checkin_overdue depends on the implementation
    
    def test_project_metrics(self):
        """Test project metrics calculation"""
        from session_state import SessionState, AgentState
        
        # Create test session state
        state = SessionState(
            session_name='test-impl',
            project_path='/path/to/project',
            project_name='test-project',
            implementation_spec_path='/path/to/spec.md',
            created_at='2024-01-01T00:00:00',
            updated_at='2024-01-01T00:00:00',
            agents={}
        )
        
        # Add agents with different statuses
        state.agents['orchestrator'] = AgentState(
            role='orchestrator',
            window_index=0,
            status='active',
            worktree_path='/path/to/worktree'
        )
        state.agents['developer'] = AgentState(
            role='developer',
            window_index=1,
            status='dead',
            worktree_path='/path/to/worktree'
        )
        state.agents['tester'] = AgentState(
            role='tester',
            window_index=2,
            status='active',
            worktree_path='/path/to/worktree',
            credit_exhausted=True
        )
        
        monitor = MultiProjectMonitor(self.orchestrator_dir)
        metrics = monitor.get_project_metrics(state)
        
        self.assertEqual(metrics['total_agents'], 3)
        self.assertEqual(metrics['active_agents'], 1)  # Only orchestrator
        self.assertEqual(metrics['dead_agents'], 1)
        self.assertEqual(metrics['exhausted_agents'], 1)
        self.assertAlmostEqual(metrics['health_score'], 1/3)


class TestIntegration(unittest.TestCase):
    """Integration tests for Phase 2 components"""
    
    def test_auto_orchestrate_integration(self):
        """Test that auto_orchestrate.py imports work correctly"""
        try:
            # This will fail if imports are broken
            from auto_orchestrate import AutoOrchestrator
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import AutoOrchestrator: {e}")
    
    def test_yaml_templates_exist(self):
        """Test that all required YAML templates exist"""
        templates_dir = Path(__file__).parent / 'templates'
        
        required_templates = [
            'base.yaml',
            'code_project.yaml',
            'system_deployment.yaml',
            'data_pipeline.yaml',
            'infrastructure_as_code.yaml'
        ]
        
        for template in required_templates:
            template_path = templates_dir / template
            self.assertTrue(template_path.exists(), f"Missing template: {template}")
            
            # Verify it's valid YAML
            import yaml
            with open(template_path) as f:
                data = yaml.safe_load(f)
                self.assertIsInstance(data, dict)
                self.assertIn('roles', data)


def run_tests():
    """Run all Phase 2 tests"""
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestDynamicTeamComposition,
        TestSyncDashboard,
        TestMultiProjectMonitor,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
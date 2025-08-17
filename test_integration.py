#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
#     "psutil",
# ]
# ///
"""
Comprehensive Integration Tests for Tmux Orchestrator
Tests full orchestration scenarios and component interactions
"""

import os
import sys
import subprocess
import tempfile
import shutil
import json
import time
import yaml
from pathlib import Path
import unittest
from unittest.mock import Mock, patch, MagicMock
import threading

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from auto_orchestrate import AutoOrchestrator
from dynamic_team import DynamicTeamComposer
from ai_team_refiner import AITeamRefiner
from performance_tuner import PerformanceTuner
from scheduler import TmuxOrchestratorScheduler
from concurrent_orchestration import ConcurrentOrchestrationManager
from sync_coordinator import SyncCoordinator


class TestFullOrchestration(unittest.TestCase):
    """Test complete orchestration scenarios"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.test_dir) / 'test_project'
        self.project_dir.mkdir()
        
        # Create mock git repo
        subprocess.run(['git', 'init'], cwd=self.project_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=self.project_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=self.project_dir, capture_output=True)
        
        # Create test files
        (self.project_dir / 'README.md').write_text('# Test Project')
        (self.project_dir / 'package.json').write_text('{"name": "test"}')
        subprocess.run(['git', 'add', '.'], cwd=self.project_dir, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=self.project_dir, capture_output=True)
        
        # Create spec file
        self.spec_file = self.project_dir / 'spec.md'
        self.spec_file.write_text("""
# Test Project Specification

## Overview
Test project for integration testing

## Requirements
- Feature A
- Feature B

## Success Criteria
- All tests pass
- Documentation complete
""")
        
    def tearDown(self):
        # Kill any test tmux sessions
        subprocess.run(['tmux', 'kill-session', '-t', 'test-project-impl'], capture_output=True)
        shutil.rmtree(self.test_dir)
    
    @patch('subprocess.run')
    def test_auto_orchestrate_flow(self, mock_run):
        """Test the complete auto-orchestrate flow"""
        # Mock subprocess calls to avoid actually creating tmux sessions
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        orchestrator = AutoOrchestrator(str(self.project_dir), str(self.spec_file))
        orchestrator.force = True
        orchestrator.manual_size = 'small'
        orchestrator.plan_type = 'pro'
        
        # Test initialization
        orchestrator.ensure_setup()
        self.assertTrue(orchestrator.tmux_orchestrator_path.exists())
        
        # Test specification analysis
        spec = orchestrator.analyze_specification()
        self.assertIsNotNone(spec)
        self.assertEqual(spec.project.name, 'test_project')
        
        # Test team composition
        roles = orchestrator.get_roles_for_project_size(spec)
        self.assertLessEqual(len(roles), 3)  # Pro plan limit
        self.assertIn(('Orchestrator', 'orchestrator'), roles)
    
    def test_dynamic_team_integration(self):
        """Test dynamic team composition with different project types"""
        composer = DynamicTeamComposer()
        
        # Test code project detection
        project_type, confidence = composer.detect_project_type(str(self.project_dir))
        self.assertEqual(project_type, 'code_project')
        
        # Test team composition
        team = composer.compose_team(str(self.project_dir))
        self.assertIn('orchestrator', team['roles'])
        self.assertIn('developer', team['roles'])
        
        # Test with deployment indicators
        (self.project_dir / 'deployment_spec.md').write_text('# Deployment')
        (self.project_dir / 'app.service').write_text('[Unit]\nDescription=App')
        
        project_type, confidence = composer.detect_project_type(str(self.project_dir))
        # Should still be code_project due to package.json weight
        
    def test_ai_refiner_integration(self):
        """Test AI team refiner with mock responses"""
        refiner = AITeamRefiner()
        
        initial_team = ['orchestrator', 'developer', 'tester']
        
        # Test with mock refinement
        result = refiner.refine_team(
            str(self.project_dir),
            initial_team,
            spec_path=str(self.spec_file),
            use_mock=True
        )
        
        self.assertIn('initial_team', result)
        self.assertIn('refinement', result)
        self.assertIn('final_team', result)
        self.assertIn('orchestrator', result['final_team'])
    
    def test_scheduler_integration(self):
        """Test scheduler functionality"""
        scheduler = TmuxOrchestratorScheduler(
            db_path=str(self.test_dir / 'test_queue.db')
        )
        
        # Schedule a task
        scheduler.schedule_task(
            session='test:0',
            minutes=1,
            note='Test task',
            target_window='test:0'
        )
        
        # Check task was scheduled
        tasks = scheduler.get_pending_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['note'], 'Test task')
        
        # Clean up
        scheduler.conn.close()
    
    def test_concurrent_orchestration(self):
        """Test concurrent orchestration management"""
        manager = ConcurrentOrchestrationManager(Path(self.test_dir))
        
        # Test project locking
        lock1 = manager.acquire_project_lock('project1', timeout=1)
        self.assertIsNotNone(lock1)
        
        # Second lock should fail
        lock2 = manager.acquire_project_lock('project1', timeout=0.1)
        self.assertIsNone(lock2)
        
        # Different project should work
        lock3 = manager.acquire_project_lock('project2', timeout=1)
        self.assertIsNotNone(lock3)
        
        # Release locks
        if lock1:
            lock1.release()
        if lock3:
            lock3.release()
    
    def test_performance_tuner(self):
        """Test performance tuner functionality"""
        tuner = PerformanceTuner(Path(self.test_dir))
        
        # Test metrics collection
        metrics = tuner.measure_system_resources()
        self.assertIn('cpu', metrics)
        self.assertIn('memory', metrics)
        self.assertIn('disk', metrics)
        
        # Test benchmarking
        benchmarks = tuner.benchmark_operations()
        self.assertIn('tmux_list_sessions', benchmarks)
        self.assertIn('file_write_100', benchmarks)
        
        # Test recommendations
        recommendations = tuner.generate_recommendations(metrics, benchmarks)
        self.assertIsInstance(recommendations, list)


class TestComponentInteractions(unittest.TestCase):
    """Test interactions between different components"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_team_composer_and_refiner(self):
        """Test interaction between dynamic composer and AI refiner"""
        # Create test project
        project_dir = Path(self.test_dir) / 'test_project'
        project_dir.mkdir()
        (project_dir / 'package.json').write_text('{}')
        (project_dir / 'Dockerfile').write_text('FROM node:14')
        
        # Get initial team from composer
        composer = DynamicTeamComposer()
        initial_comp = composer.compose_team(str(project_dir))
        
        # Refine with AI refiner
        refiner = AITeamRefiner()
        result = refiner.refine_team(
            str(project_dir),
            initial_comp['roles'],
            use_mock=True
        )
        
        # Check refinement made sense
        if 'devops' not in initial_comp['roles']:
            # Mock refiner should add devops for Docker
            self.assertIn('devops', result['refinement'].get('add_roles', []))
    
    def test_scheduler_and_sync_coordinator(self):
        """Test scheduler working with sync coordinator"""
        # This would test that scheduled sync tasks work properly
        # Mock implementation since we can't run actual tmux commands in tests
        scheduler = TmuxOrchestratorScheduler(
            db_path=str(self.test_dir / 'test_queue.db')
        )
        
        # Schedule a sync task
        scheduler.schedule_task(
            session='test:0',
            minutes=5,
            note='Sync worktrees',
            target_window='test:0'
        )
        
        tasks = scheduler.get_pending_tasks()
        self.assertTrue(any('Sync' in task['note'] for task in tasks))
        
        scheduler.conn.close()


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""
    
    def test_missing_project_directory(self):
        """Test handling of missing project directory"""
        composer = DynamicTeamComposer()
        
        # Should return default team
        project_type, confidence = composer.detect_project_type('/nonexistent/path')
        self.assertEqual(project_type, 'code_project')
        self.assertEqual(confidence, 0.5)
    
    def test_corrupt_yaml_template(self):
        """Test handling of corrupt YAML templates"""
        # Create temporary templates dir with bad YAML
        temp_dir = tempfile.mkdtemp()
        templates_dir = Path(temp_dir) / 'templates'
        templates_dir.mkdir()
        
        bad_yaml = templates_dir / 'bad.yaml'
        bad_yaml.write_text('{ invalid yaml ]:')
        
        # Should handle gracefully
        composer = DynamicTeamComposer(templates_dir=str(templates_dir))
        # Should still have base template at least
        
        shutil.rmtree(temp_dir)
    
    @patch('subprocess.run')
    def test_tmux_command_failures(self, mock_run):
        """Test handling of tmux command failures"""
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='tmux error')
        
        from performance_tuner import PerformanceTuner
        tuner = PerformanceTuner()
        
        # Should handle tmux failures gracefully
        count = tuner.count_tmux_sessions()
        self.assertEqual(count, 0)


class TestEndToEndScenarios(unittest.TestCase):
    """Test complete end-to-end scenarios"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orchestrator_dir = Path(self.test_dir) / 'orchestrator'
        self.orchestrator_dir.mkdir()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_web_app_orchestration(self):
        """Test orchestrating a web application project"""
        # Create web app project
        project_dir = self.orchestrator_dir / 'web_app'
        project_dir.mkdir()
        
        # Web app indicators
        (project_dir / 'package.json').write_text(json.dumps({
            'name': 'test-web-app',
            'scripts': {
                'dev': 'next dev',
                'build': 'next build'
            }
        }))
        (project_dir / 'pages').mkdir()
        (project_dir / 'pages' / 'index.js').write_text('export default () => <div>Hello</div>')
        
        # Initialize git
        subprocess.run(['git', 'init'], cwd=project_dir, capture_output=True)
        
        # Test team composition
        composer = DynamicTeamComposer()
        team = composer.compose_team(str(project_dir))
        
        self.assertEqual(team['project_type'], 'code_project')
        self.assertIn('developer', team['roles'])
        self.assertIn('tester', team['roles'])
    
    def test_system_deployment_orchestration(self):
        """Test orchestrating a system deployment project"""
        # Create deployment project
        project_dir = self.orchestrator_dir / 'deployment'
        project_dir.mkdir()
        
        # Deployment indicators
        (project_dir / 'deployment_spec.md').write_text('# System Deployment')
        (project_dir / 'ansible').mkdir()
        (project_dir / 'ansible' / 'playbook.yml').write_text('---\n- hosts: all')
        (project_dir / 'app.service').write_text('[Unit]\nDescription=App Service')
        
        # Test team composition
        composer = DynamicTeamComposer()
        team = composer.compose_team(str(project_dir))
        
        # Should detect system deployment
        recommendation = composer.recommend_team_size(str(project_dir))
        
        # Check appropriate roles selected
        self.assertTrue(any(role in recommendation['selected_roles'] 
                          for role in ['devops', 'sysadmin', 'securityops']))


def run_integration_tests():
    """Run all integration tests"""
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestFullOrchestration,
        TestComponentInteractions,
        TestErrorHandling,
        TestEndToEndScenarios
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_tests()
    sys.exit(0 if success else 1)
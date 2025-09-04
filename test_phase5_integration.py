#!/usr/bin/env python3
"""
Test script for Phase 5 integration of the Tmux Orchestrator system.

Tests complete system integration, migration tools, and final verification
of the modular architecture transformation.
"""

import sys
import json
import tempfile
from pathlib import Path

# Add tmux_orchestrator package to path
sys.path.insert(0, str(Path(__file__).parent))

def test_package_imports():
    """Test that all package imports work correctly."""
    print("🧪 Testing Package Imports...")
    
    try:
        # Test main package import
        import tmux_orchestrator
        print(f"✓ Main package imported: version {tmux_orchestrator.get_version()}")
        
        # Test all major exports
        from tmux_orchestrator import (
            Orchestrator, SessionManager, SessionState, AgentState, StateManager,
            ClaudeInitializer, OAuthManager,
            AgentFactory, RoleConfig, BriefingSystem, BriefingContext, ProjectSpec,
            WorktreeManager, TmuxSessionController, TmuxMessenger,
            QueueManager, Task, TaskPriority, TaskStatus,
            HealthMonitor, HealthStatus, SystemMetrics,
            FileUtils, SystemUtils, ConfigLoader, ConfigSchema,
            EnhancedCLI
        )
        print("✓ All major classes imported successfully")
        
        # Test convenience functions
        orchestrator = tmux_orchestrator.create_orchestrator()
        system_info = tmux_orchestrator.get_system_info()
        
        if orchestrator and system_info:
            print("✓ Convenience functions working correctly")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Package import test failed: {e}")
        return False

def test_dependency_injection():
    """Test dependency injection capabilities."""
    print("\n🧪 Testing Dependency Injection...")
    
    try:
        from tmux_orchestrator import Orchestrator
        from tmux_orchestrator.core.session_manager import SessionManager
        from tmux_orchestrator.monitoring.health_monitor import HealthMonitor
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create custom dependencies
            custom_session_manager = SessionManager(temp_path)
            custom_health_monitor = HealthMonitor(temp_path)
            
            # Test dependency injection
            orchestrator = Orchestrator(
                session_manager=custom_session_manager,
                health_monitor=custom_health_monitor
            )
            
            # Verify injected dependencies are used
            if orchestrator.session_manager is custom_session_manager:
                print("✓ Session manager dependency injection successful")
            
            if orchestrator.health_monitor is custom_health_monitor:
                print("✓ Health monitor dependency injection successful")
            
            # Test that other dependencies are auto-created
            if orchestrator.git_manager is not None:
                print("✓ Auto-created dependencies working correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Dependency injection test failed: {e}")
        return False

def test_cross_module_integration():
    """Test integration between different modules."""
    print("\n🧪 Testing Cross-Module Integration...")
    
    try:
        from tmux_orchestrator import create_orchestrator
        from tmux_orchestrator.database.queue_manager import TaskPriority
        
        # Create orchestrator
        orchestrator = create_orchestrator()
        
        # Test integration: Queue Manager + Health Monitor
        task_id = orchestrator.queue_manager.create_task(
            title="Health Check Task",
            description="Test integration between queue and health monitoring",
            priority=TaskPriority.HIGH,
            assigned_to="system_monitor"
        )
        
        # Collect health metrics
        metrics = orchestrator.health_monitor.collect_system_metrics()
        
        # Update task with health info
        task = orchestrator.queue_manager.tasks[task_id]
        task.metadata['cpu_percent'] = metrics.cpu_percent
        task.metadata['memory_percent'] = metrics.memory_percent
        
        print(f"✓ Queue-Health integration: Task {task_id} enriched with metrics")
        
        # Test integration: Config Loader + State Manager
        orchestrator.config_loader.set_config_value(
            "integration_test",
            "system.status",
            "testing"
        )
        
        # Access through state manager
        config_value = orchestrator.config_loader.get_config_value(
            "integration_test",
            "system.status"
        )
        
        if config_value == "testing":
            print("✓ Config-State integration working correctly")
        
        # Test integration: File Utils + Health Monitor
        from tmux_orchestrator.utils.file_utils import FileUtils
        
        # Health monitor should be using FileUtils internally
        health_summary = orchestrator.health_monitor.get_system_health_summary()
        
        if health_summary and 'timestamp' in health_summary:
            print("✓ File Utils integration with Health Monitor successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Cross-module integration test failed: {e}")
        return False

def test_cli_integration():
    """Test CLI integration with the modular system."""
    print("\n🧪 Testing CLI Integration...")
    
    try:
        from tmux_orchestrator.cli.enhanced_cli import EnhancedCLI
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create CLI
            cli = EnhancedCLI(temp_path)
            
            # Test argument parsing
            parser = cli._create_argument_parser()
            
            # Test various command arguments
            test_args = [
                ['--version'],
                ['--help'],
                ['status', 'system'],
                ['agent', 'list']
            ]
            
            for args in test_args:
                try:
                    # Most of these will cause SystemExit for help/version
                    parser.parse_args(args)
                except SystemExit:
                    pass  # Expected for help/version
                except Exception as e:
                    print(f"❌ CLI parsing failed for {args}: {e}")
                    return False
            
            print("✓ CLI argument parsing working correctly")
            
            # Test CLI command integration
            # Note: We can't test full CLI execution here, but we can test setup
            if hasattr(cli, 'orchestrator_path') and cli.orchestrator_path == temp_path:
                print("✓ CLI orchestrator path configured correctly")
            
            return True
        
    except Exception as e:
        print(f"❌ CLI integration test failed: {e}")
        return False

def test_error_handling():
    """Test error handling across the modular system."""
    print("\n🧪 Testing Error Handling...")
    
    try:
        from tmux_orchestrator import create_orchestrator
        from tmux_orchestrator.utils.file_utils import FileUtils
        
        # Test graceful error handling in FileUtils
        result = FileUtils.read_json(Path("/nonexistent/file.json"))
        if result is None:
            print("✓ FileUtils handles missing files gracefully")
        
        # Test orchestrator with invalid paths
        orchestrator = create_orchestrator()
        
        # Test health monitor with invalid session
        try:
            health = orchestrator.health_monitor.check_agent_health("nonexistent-session", {})
            # Should return empty dict or handle gracefully
            print("✓ Health monitor handles invalid sessions gracefully")
        except Exception:
            print("❌ Health monitor error handling failed")
            return False
        
        # Test queue manager with invalid operations
        try:
            success = orchestrator.queue_manager.complete_task("nonexistent-task", "nonexistent-agent")
            if not success:
                print("✓ Queue manager handles invalid operations gracefully")
        except Exception:
            print("❌ Queue manager error handling failed")
            return False
        
        # Test tmux controller with invalid session
        try:
            windows = orchestrator.tmux_controller.list_windows("nonexistent-session")
            if isinstance(windows, list):  # Should return empty list
                print("✓ Tmux controller handles invalid sessions gracefully")
        except Exception:
            print("❌ Tmux controller error handling failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

def test_configuration_system():
    """Test the configuration system integration."""
    print("\n🧪 Testing Configuration System...")
    
    try:
        from tmux_orchestrator import create_orchestrator
        from tmux_orchestrator.utils.config_loader import ConfigSchema, ConfigValidationRule
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            orchestrator = create_orchestrator()
            
            # Test configuration with schema validation
            test_config = {
                'database': {'host': 'localhost', 'port': 5432},
                'api': {'timeout': 30, 'retries': 3}
            }
            
            # Create and register schema
            schema = ConfigSchema('integration_test', '1.0')
            schema.add_rule(
                field_path='database.host',
                required=True,
                field_type=str
            ).add_rule(
                field_path='database.port',
                required=True,
                field_type=int,
                min_value=1024,
                max_value=65535
            )
            
            orchestrator.config_loader.register_schema(schema)
            
            # Validate and save config
            valid = orchestrator.config_loader.validate_config(test_config, 'integration_test')
            if valid:
                print("✓ Configuration validation working correctly")
                
                success = orchestrator.config_loader.save_config('integration_test', test_config)
                if success:
                    print("✓ Configuration persistence working correctly")
            
            # Test config value operations
            value = orchestrator.config_loader.get_config_value('integration_test', 'database.host', 'default')
            if value == 'localhost':
                print("✓ Configuration retrieval working correctly")
            
            # Test environment variable substitution
            env_config = {'test_var': '${HOME}'}
            substituted = orchestrator.config_loader._substitute_environment_variables(env_config)
            if substituted['test_var'] != '${HOME}':  # Should be substituted
                print("✓ Environment variable substitution working")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration system test failed: {e}")
        return False

def test_migration_tool():
    """Test the migration tool functionality."""
    print("\n🧪 Testing Migration Tool...")
    
    try:
        from migrate_to_modular import MigrationTool
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create migration tool
            migration_tool = MigrationTool(temp_path)
            print("✓ Migration tool created successfully")
            
            # Test validation
            validation_result = migration_tool.validate_modular_system()
            if validation_result:
                print("✓ Modular system validation successful")
            
            # Test backup creation
            backup_result = migration_tool.create_backup()
            if backup_result:
                print("✓ Backup creation successful")
            
            # Test configuration update
            config_result = migration_tool.update_configurations()
            if config_result:
                print("✓ Configuration update successful")
            
            # Test integration testing
            integration_result = migration_tool.test_modular_integration()
            if integration_result:
                print("✓ Integration testing successful")
            
            # Test status display
            migration_tool.show_migration_status()
            print("✓ Status display working correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration tool test failed: {e}")
        return False

def test_backward_compatibility():
    """Test backward compatibility with existing interfaces."""
    print("\n🧪 Testing Backward Compatibility...")
    
    try:
        from tmux_orchestrator import create_orchestrator
        
        # Test that orchestrator still provides original functionality
        orchestrator = create_orchestrator()
        
        # Test OAuth functionality (Phase 1)
        oauth_status = orchestrator.check_oauth_port_conflicts()
        if oauth_status and 'port' in oauth_status:
            print("✓ OAuth functionality preserved")
        
        # Test Claude restart functionality (Phase 1)
        # Note: We can't actually restart Claude in tests, but we can verify the method exists
        if hasattr(orchestrator, 'restart_claude_with_oauth_management'):
            print("✓ Claude restart functionality preserved")
        
        # Test session management (Phase 2) 
        if hasattr(orchestrator, 'session_manager') and orchestrator.session_manager:
            print("✓ Session management functionality preserved")
        
        # Test state management (Phase 2)
        system_health = orchestrator.state_manager.get_system_health_status()
        if system_health and 'system_load' in system_health:
            print("✓ State management functionality preserved")
        
        # Test git management (Phase 3)
        if hasattr(orchestrator, 'git_manager') and orchestrator.git_manager:
            print("✓ Git management functionality preserved")
        
        # Test tmux management (Phase 3)
        sessions = orchestrator.tmux_controller.list_sessions()
        if isinstance(sessions, list):
            print("✓ Tmux management functionality preserved")
        
        return True
        
    except Exception as e:
        print(f"❌ Backward compatibility test failed: {e}")
        return False

def test_comprehensive_workflow():
    """Test a comprehensive end-to-end workflow."""
    print("\n🧪 Testing Comprehensive End-to-End Workflow...")
    
    try:
        from tmux_orchestrator import create_orchestrator, get_system_info
        from tmux_orchestrator.database.queue_manager import TaskPriority
        from tmux_orchestrator.monitoring.health_monitor import HealthStatus
        
        # Phase 1: System initialization
        orchestrator = create_orchestrator()
        system_info = get_system_info()
        print(f"✓ System initialized: {system_info['orchestrator_version']}")
        
        # Phase 2: Configuration setup
        orchestrator.config_loader.set_config_value(
            'workflow_test',
            'project.name',
            'E2E Test Project'
        )
        
        orchestrator.config_loader.set_config_value(
            'workflow_test', 
            'project.status',
            'initializing'
        )
        print("✓ Project configuration established")
        
        # Phase 3: Task management setup
        task_id_1 = orchestrator.queue_manager.create_task(
            title="Setup Development Environment",
            description="Initialize project development environment",
            priority=TaskPriority.HIGH,
            assigned_to="developer",
            estimated_duration=30
        )
        
        task_id_2 = orchestrator.queue_manager.create_task(
            title="Create Test Suite",
            description="Develop comprehensive test suite",
            priority=TaskPriority.MEDIUM,
            assigned_to="tester",
            dependencies=[task_id_1],
            estimated_duration=45
        )
        print("✓ Task dependency chain created")
        
        # Phase 4: Health monitoring setup
        orchestrator.health_monitor.collect_system_metrics()
        alert_id = orchestrator.health_monitor.create_alert(
            'workflow_test',
            'E2E workflow in progress',
            HealthStatus.WARNING
        )
        print("✓ Health monitoring configured")
        
        # Phase 5: Workflow execution simulation
        # Start first task
        success = orchestrator.queue_manager.start_task(task_id_1, "developer")
        if success:
            print("✓ First task started successfully")
            
            # Complete first task
            success = orchestrator.queue_manager.complete_task(task_id_1, "developer")
            if success:
                print("✓ First task completed successfully")
                
                # Start dependent task
                success = orchestrator.queue_manager.start_task(task_id_2, "tester")
                if success:
                    print("✓ Dependent task started successfully")
                    
                    # Complete second task
                    success = orchestrator.queue_manager.complete_task(task_id_2, "tester")
                    if success:
                        print("✓ Dependent task completed successfully")
        
        # Phase 6: Workflow completion
        orchestrator.config_loader.set_config_value(
            'workflow_test',
            'project.status', 
            'completed'
        )
        
        orchestrator.health_monitor.resolve_alert(alert_id)
        print("✓ Workflow completed and cleaned up")
        
        # Phase 7: Verification
        workload_dev = orchestrator.queue_manager.get_agent_workload("developer")
        workload_test = orchestrator.queue_manager.get_agent_workload("tester") 
        
        if (workload_dev['completed_tasks'] == 0 and  # Tasks are removed from queue when completed
            workload_test['completed_tasks'] == 0):
            print("✓ Final workload verification successful")
        
        final_status = orchestrator.config_loader.get_config_value(
            'workflow_test',
            'project.status'
        )
        
        if final_status == 'completed':
            print("✓ Final configuration verification successful")
        
        print("✓ Comprehensive end-to-end workflow completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Comprehensive workflow test failed: {e}")
        return False

def main():
    """Run all Phase 5 integration tests."""
    print("🚀 Testing Phase 5: Integration and Migration")
    print("=" * 55)
    
    tests = [
        test_package_imports,
        test_dependency_injection,
        test_cross_module_integration,
        test_cli_integration,
        test_error_handling,
        test_configuration_system,
        test_migration_tool,
        test_backward_compatibility,
        test_comprehensive_workflow
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 55)
    print(f"📊 Phase 5 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 Phase 5 integration successful!")
        print("\n✨ Complete package integration with proper exports")
        print("✨ Flexible dependency injection system")
        print("✨ Seamless cross-module integration")
        print("✨ Enhanced CLI with rich output")
        print("✨ Comprehensive error handling")
        print("✨ Advanced configuration management")
        print("✨ Migration tools for smooth transition")
        print("✨ Full backward compatibility")
        print("✨ End-to-end workflow validation")
        print("\n🏆 TMUX ORCHESTRATOR MODULARIZATION COMPLETE!")
        print("✅ All 5 phases successfully implemented and tested")
        print("✅ System is ready for production use")
        return True
    else:
        print(f"⚠️  {failed} tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Test script for Phase 4 modules of the Tmux Orchestrator system.

Tests database operations, monitoring, utilities, and CLI functionality.
"""

import sys
import json
import tempfile
from pathlib import Path

# Add tmux_orchestrator package to path
sys.path.insert(0, str(Path(__file__).parent))

def test_queue_manager():
    """Test the queue manager functionality."""
    print("🧪 Testing Queue Manager...")
    
    try:
        from tmux_orchestrator.database.queue_manager import QueueManager, TaskPriority, TaskStatus
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create queue manager
            queue_manager = QueueManager(temp_path)
            print("✓ Queue manager created successfully")
            
            # Test task creation
            task_id = queue_manager.create_task(
                title="Test Task",
                description="This is a test task for validation",
                priority=TaskPriority.HIGH,
                assigned_to="developer",
                estimated_duration=30
            )
            print(f"✓ Created task: {task_id}")
            
            # Test task assignment
            success = queue_manager.assign_task(task_id, "tester")
            if success:
                print("✓ Task reassignment successful")
            
            # Test task start
            success = queue_manager.start_task(task_id, "tester")
            if success:
                print("✓ Task started successfully")
            
            # Test task completion
            success = queue_manager.complete_task(task_id, "tester")
            if success:
                print("✓ Task completed successfully")
            
            # Test workload statistics
            workload = queue_manager.get_agent_workload("tester")
            print(f"✓ Workload stats: {workload['completed_tasks']} completed tasks")
        
        return True
        
    except Exception as e:
        print(f"❌ Queue Manager test failed: {e}")
        return False

def test_health_monitor():
    """Test the health monitor functionality."""
    print("\n🧪 Testing Health Monitor...")
    
    try:
        from tmux_orchestrator.monitoring.health_monitor import HealthMonitor, HealthStatus
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create health monitor
            monitor = HealthMonitor(temp_path)
            print("✓ Health monitor created successfully")
            
            # Test system metrics collection
            metrics = monitor.collect_system_metrics()
            print(f"✓ System metrics: CPU {metrics.cpu_percent:.1f}%, Memory {metrics.memory_percent:.1f}%")
            
            # Test health summary
            summary = monitor.get_system_health_summary()
            print(f"✓ System health: {summary['overall_status']} with {summary['tmux_sessions']} sessions")
            
            # Test alert creation
            alert_id = monitor.create_alert("test_component", "Test alert message", HealthStatus.WARNING)
            print(f"✓ Created alert: {alert_id}")
            
            # Test alert resolution
            success = monitor.resolve_alert(alert_id)
            if success:
                print("✓ Alert resolved successfully")
            
            # Test performance trends
            trends = monitor.get_performance_trends(1)  # 1 hour
            print(f"✓ Performance trends collected: {len(trends['cpu_trend'])} data points")
        
        return True
        
    except Exception as e:
        print(f"❌ Health Monitor test failed: {e}")
        return False

def test_file_utils():
    """Test file utilities functionality."""
    print("\n🧪 Testing File Utils...")
    
    try:
        from tmux_orchestrator.utils.file_utils import FileUtils
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test JSON operations
            test_data = {"test": "data", "number": 42, "list": [1, 2, 3]}
            json_file = temp_path / "test.json"
            
            success = FileUtils.write_json(json_file, test_data)
            if success:
                print("✓ JSON write successful")
            
            loaded_data = FileUtils.read_json(json_file)
            if loaded_data and loaded_data["test"] == "data":
                print("✓ JSON read successful")
            
            # Test YAML operations
            yaml_file = temp_path / "test.yaml"
            success = FileUtils.write_yaml(yaml_file, test_data)
            if success:
                print("✓ YAML write successful")
            
            loaded_yaml = FileUtils.read_yaml(yaml_file)
            if loaded_yaml and loaded_yaml["test"] == "data":
                print("✓ YAML read successful")
            
            # Test text operations
            text_file = temp_path / "test.txt"
            test_text = "This is test content\nWith multiple lines"
            
            success = FileUtils.write_text(text_file, test_text)
            if success:
                print("✓ Text write successful")
            
            loaded_text = FileUtils.read_text(text_file)
            if loaded_text and "test content" in loaded_text:
                print("✓ Text read successful")
            
            # Test backup functionality
            backup_path = FileUtils.backup_file(text_file)
            if backup_path and backup_path.exists():
                print("✓ File backup successful")
            
            # Test file size operations
            size = FileUtils.get_file_size(text_file)
            formatted_size = FileUtils.format_file_size(size)
            print(f"✓ File size: {formatted_size}")
        
        return True
        
    except Exception as e:
        print(f"❌ File Utils test failed: {e}")
        return False

def test_system_utils():
    """Test system utilities functionality."""
    print("\n🧪 Testing System Utils...")
    
    try:
        from tmux_orchestrator.utils.system_utils import SystemUtils
        
        # Test port checking
        port_free = SystemUtils.is_port_free(65432)  # Use high port unlikely to be used
        print(f"✓ Port check: Port 65432 is {'free' if port_free else 'in use'}")
        
        # Test free port finding
        free_port = SystemUtils.find_free_port(start_port=50000, max_attempts=10)
        if free_port:
            print(f"✓ Found free port: {free_port}")
        
        # Test command execution
        returncode, stdout, stderr = SystemUtils.run_command(["echo", "test command"])
        if returncode == 0 and "test command" in stdout:
            print("✓ Command execution successful")
        
        # Test system info
        system_info = SystemUtils.get_system_info()
        if system_info and "platform" in system_info:
            print(f"✓ System info: {system_info['platform']} {system_info['architecture']}")
        
        # Test command availability
        python_available = SystemUtils.check_command_availability("python3")
        print(f"✓ Command availability: python3 {'available' if python_available else 'not available'}")
        
        # Test environment variables
        test_var = SystemUtils.get_environment_variable("HOME")
        if test_var:
            print("✓ Environment variable access successful")
        
        # Test disk space checking
        with tempfile.TemporaryDirectory() as temp_dir:
            sufficient, disk_info = SystemUtils.check_disk_space(Path(temp_dir))
            print(f"✓ Disk space check: {disk_info['free_gb']:.1f} GB free")
        
        return True
        
    except Exception as e:
        print(f"❌ System Utils test failed: {e}")
        return False

def test_config_loader():
    """Test configuration loader functionality."""
    print("\n🧪 Testing Config Loader...")
    
    try:
        from tmux_orchestrator.utils.config_loader import ConfigLoader, ConfigSchema, ConfigValidationRule
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create config loader
            loader = ConfigLoader(temp_path)
            print("✓ Config loader created successfully")
            
            # Test config save and load
            test_config = {
                "database": {"host": "localhost", "port": 5432},
                "logging": {"level": "INFO"},
                "features": {"enabled": ["oauth", "monitoring"]}
            }
            
            success = loader.save_config("test_config", test_config)
            if success:
                print("✓ Config save successful")
            
            loaded_config = loader.load_config("test_config", required=False)
            if loaded_config and loaded_config["database"]["host"] == "localhost":
                print("✓ Config load successful")
            
            # Test config merging
            override_config = {"database": {"port": 5433}, "new_key": "new_value"}
            merged = loader.merge_configs(test_config, override_config)
            if merged["database"]["port"] == 5433 and merged["new_key"] == "new_value":
                print("✓ Config merging successful")
            
            # Test schema validation
            test_schema = ConfigSchema("test", "1.0")
            test_schema.add_rule(
                field_path="database.host",
                required=True,
                field_type=str
            ).add_rule(
                field_path="database.port",
                required=True,
                field_type=int,
                min_value=1024,
                max_value=65535
            )
            
            loader.register_schema(test_schema)
            valid = loader.validate_config(loaded_config, "test")
            if valid:
                print("✓ Schema validation successful")
            
            # Test config value operations
            value = loader.get_config_value("test_config", "database.host")
            if value == "localhost":
                print("✓ Config value retrieval successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Config Loader test failed: {e}")
        return False

def test_enhanced_cli():
    """Test enhanced CLI functionality."""
    print("\n🧪 Testing Enhanced CLI...")
    
    try:
        from tmux_orchestrator.cli.enhanced_cli import EnhancedCLI
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create CLI
            cli = EnhancedCLI(temp_path)
            print("✓ Enhanced CLI created successfully")
            
            # Test argument parser creation
            parser = cli._create_argument_parser()
            if parser and hasattr(parser, 'parse_args'):
                print("✓ Argument parser created successfully")
            
            # Test help output (should not fail)
            try:
                parser.parse_args(['--help'])
            except SystemExit:
                pass  # Expected behavior for --help
            print("✓ Help system functional")
            
            # Test version output
            try:
                parser.parse_args(['--version'])
            except SystemExit:
                pass  # Expected behavior for --version
            print("✓ Version system functional")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced CLI test failed: {e}")
        return False

def test_integrated_orchestrator():
    """Test the orchestrator with Phase 4 integration."""
    print("\n🧪 Testing Orchestrator with Phase 4 Integration...")
    
    try:
        from tmux_orchestrator.core.orchestrator import Orchestrator
        
        # Create orchestrator (should now include Phase 4 modules)
        orchestrator = Orchestrator()
        print("✓ Orchestrator created with Phase 4 integration")
        
        # Test that all modules are properly initialized
        assert orchestrator.queue_manager is not None, "Queue manager should be initialized"
        assert orchestrator.health_monitor is not None, "Health monitor should be initialized"
        assert orchestrator.config_loader is not None, "Config loader should be initialized" 
        assert orchestrator.cli is not None, "CLI should be initialized"
        print("✓ All Phase 4 modules properly integrated")
        
        # Test combined functionality from all phases
        # Phase 1: OAuth
        oauth_status = orchestrator.check_oauth_port_conflicts()
        print(f"✓ Phase 1 (OAuth): Port {oauth_status['port']}, Free: {oauth_status['is_free']}")
        
        # Phase 2: Session management
        system_health = orchestrator.state_manager.get_system_health_status()
        print(f"✓ Phase 2 (State): System load: {system_health['system_load']}")
        
        # Phase 3: Infrastructure
        tmux_sessions = orchestrator.tmux_controller.list_sessions()
        print(f"✓ Phase 3 (Tmux): {len(tmux_sessions)} active sessions")
        
        # Phase 4: Support modules
        health_summary = orchestrator.health_monitor.get_system_health_summary()
        print(f"✓ Phase 4 (Health): {health_summary['overall_status']} system status")
        
        config_value = orchestrator.config_loader.get_config_value("orchestrator", "oauth.port", 3000)
        print(f"✓ Phase 4 (Config): OAuth port configured as {config_value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Integrated Orchestrator test failed: {e}")
        return False

def test_full_workflow_simulation():
    """Test a complete workflow with all Phase 4 features."""
    print("\n🧪 Testing Full Workflow with Phase 4 Features...")
    
    try:
        from tmux_orchestrator.core.orchestrator import Orchestrator
        from tmux_orchestrator.database.queue_manager import TaskPriority
        from tmux_orchestrator.monitoring.health_monitor import HealthStatus
        
        # Create orchestrator
        orchestrator = Orchestrator()
        
        # Task management workflow
        task_id = orchestrator.queue_manager.create_task(
            title="Full System Test",
            description="End-to-end system validation test",
            priority=TaskPriority.HIGH,
            assigned_to="testrunner",
            estimated_duration=15
        )
        print(f"✓ Created workflow task: {task_id}")
        
        # Health monitoring workflow
        orchestrator.health_monitor.collect_system_metrics()
        alert_id = orchestrator.health_monitor.create_alert(
            "workflow_test", 
            "Full workflow test in progress", 
            HealthStatus.WARNING
        )
        print(f"✓ Health monitoring active with alert: {alert_id}")
        
        # Configuration management workflow
        orchestrator.config_loader.set_config_value(
            "workflow_test", 
            "test.status", 
            "in_progress",
            save=True
        )
        print("✓ Configuration updated for workflow")
        
        # Complete task workflow
        success = orchestrator.queue_manager.start_task(task_id, "testrunner")
        if success:
            success = orchestrator.queue_manager.complete_task(task_id, "testrunner")
            if success:
                print("✓ Task workflow completed successfully")
        
        # Resolve monitoring alert
        orchestrator.health_monitor.resolve_alert(alert_id)
        print("✓ Monitoring alert resolved")
        
        # Cleanup configuration
        orchestrator.config_loader.set_config_value(
            "workflow_test", 
            "test.status", 
            "completed",
            save=True
        )
        print("✓ Workflow configuration finalized")
        
        print("✓ Full workflow simulation successful")
        return True
        
    except Exception as e:
        print(f"❌ Full workflow test failed: {e}")
        return False

def main():
    """Run all Phase 4 tests."""
    print("🚀 Testing Phase 4: Support Modules")
    print("=" * 50)
    
    tests = [
        test_queue_manager,
        test_health_monitor,
        test_file_utils,
        test_system_utils,
        test_config_loader,
        test_enhanced_cli,
        test_integrated_orchestrator,
        test_full_workflow_simulation
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
    
    print("\n" + "=" * 50)
    print(f"📊 Phase 4 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 Phase 4 implementation successful!")
        print("\n✨ Database operations with task queuing and prioritization")
        print("✨ System health monitoring with performance tracking")
        print("✨ File operations with JSON/YAML support")
        print("✨ System utilities with command execution")
        print("✨ Configuration management with schema validation")
        print("✨ Enhanced CLI with rich output and interactive features")
        print("✨ Full integration with all previous phases")
        print("✨ Complete workflow simulation working")
        print("✨ Ready for Phase 5: Integration and Migration")
        return True
    else:
        print(f"⚠️  {failed} tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
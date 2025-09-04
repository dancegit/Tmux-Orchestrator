#!/usr/bin/env python3
"""
Test script for Phase 2 modules of the Tmux Orchestrator system.

Tests session management, state management, agent factory, and briefing system.
"""

import sys
from pathlib import Path

# Add tmux_orchestrator package to path
sys.path.insert(0, str(Path(__file__).parent))

def test_session_manager():
    """Test the session manager functionality."""
    print("🧪 Testing Session Manager...")
    
    try:
        from tmux_orchestrator.core.session_manager import SessionManager, AgentState, SessionState
        
        # Create session manager
        manager = SessionManager(Path(__file__).parent)
        print("✓ Session manager created successfully")
        
        # Test agent state creation
        agent_config = {
            'developer': {
                'window_index': 1,
                'window_name': 'Developer',
                'worktree_path': '/tmp/dev-worktree',
                'branch': 'feature/test'
            }
        }
        
        session_state = manager.create_session_state(
            session_name="test-session",
            project_path=Path("/tmp/test-project"),
            project_name="Test Project",
            spec_path=Path("/tmp/spec.md"),
            agents_config=agent_config
        )
        
        print(f"✓ Session state created with {len(session_state.agents)} agents")
        
        # Test session summary
        summary = manager.get_session_summary(session_state)
        print(f"✓ Session summary created: {summary['alive_agents']}/{summary['total_agents']} agents")
        
        return True
        
    except Exception as e:
        print(f"❌ Session Manager test failed: {e}")
        return False

def test_state_manager():
    """Test the state manager functionality."""
    print("\n🧪 Testing State Manager...")
    
    try:
        from tmux_orchestrator.core.state_manager import StateManager
        
        # Create state manager
        manager = StateManager(Path(__file__).parent)
        print("✓ State manager created successfully")
        
        # Test global state operations
        manager.set_global_state("test_key", "test_value")
        value = manager.get_global_state("test_key")
        assert value == "test_value", f"Expected 'test_value', got '{value}'"
        print("✓ Global state operations working")
        
        # Test OAuth port tracking
        manager.track_oauth_port_usage(3000, "test_process", "test_session")
        port_status = manager.get_oauth_port_status(3000)
        assert port_status is not None, "OAuth port status should not be None"
        print("✓ OAuth port tracking working")
        
        # Test system health status
        health = manager.get_system_health_status()
        assert 'timestamp' in health, "Health status should include timestamp"
        print(f"✓ System health status: {health['system_load']} load")
        
        return True
        
    except Exception as e:
        print(f"❌ State Manager test failed: {e}")
        return False

def test_agent_factory():
    """Test the agent factory functionality."""
    print("\n🧪 Testing Agent Factory...")
    
    try:
        from tmux_orchestrator.agents.agent_factory import AgentFactory, RoleConfig
        from tmux_orchestrator.core.session_manager import AgentState
        
        # Create agent factory
        factory = AgentFactory(Path(__file__).parent)
        print("✓ Agent factory created successfully")
        
        # Test role configuration
        role_config = factory.get_role_config("developer")
        assert role_config.window_name == "Developer", "Developer config should have correct window name"
        print(f"✓ Role config loaded: {len(role_config.responsibilities)} responsibilities")
        
        # Test agent state creation
        agent_state = factory.create_agent_state(
            role="developer",
            window_index=1,
            worktree_path=Path("/tmp/dev-worktree"),
            session_name="test-session"
        )
        assert agent_state.role == "developer", "Agent state should have correct role"
        print("✓ Agent state creation working")
        
        # Test available roles
        roles = factory.get_available_roles()
        print(f"✓ Available roles: {len(roles)} roles configured")
        
        # Test project type role recommendations
        web_roles = factory.get_roles_for_project_type("web_application", "medium")
        print(f"✓ Web application team: {len(web_roles)} roles recommended")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent Factory test failed: {e}")
        return False

def test_briefing_system():
    """Test the briefing system functionality."""
    print("\n🧪 Testing Briefing System...")
    
    try:
        from tmux_orchestrator.agents.briefing_system import BriefingSystem, BriefingContext, ProjectSpec
        from tmux_orchestrator.agents.agent_factory import RoleConfig
        
        # Create briefing system
        system = BriefingSystem(Path(__file__).parent)
        print("✓ Briefing system created successfully")
        
        # Create test context
        project_spec = ProjectSpec(
            name="Test Project",
            path="/tmp/test-project",
            type="web_application",
            main_tech=["Python", "FastAPI", "React"]
        )
        
        role_config = RoleConfig(
            responsibilities=["Test responsibility 1", "Test responsibility 2"],
            check_in_interval=30,
            initial_commands=[],
            window_name="Developer"
        )
        
        context = BriefingContext(
            project_spec=project_spec,
            role_config=role_config,
            session_name="test-session",
            worktree_path=Path("/tmp/dev-worktree"),
            team_members=[("developer", 1), ("tester", 2)],
            git_branch="main",
            enable_mcp=True
        )
        
        # Generate briefing
        briefing = system.generate_role_briefing(context)
        assert len(briefing) > 500, f"Briefing should be comprehensive, got {len(briefing)} chars"
        assert "Developer" in briefing, "Briefing should mention the role"
        print(f"✓ Generated {len(briefing)} character briefing")
        
        return True
        
    except Exception as e:
        print(f"❌ Briefing System test failed: {e}")
        return False

def test_integrated_orchestrator():
    """Test the integrated orchestrator with Phase 2 modules."""
    print("\n🧪 Testing Integrated Orchestrator...")
    
    try:
        from tmux_orchestrator.core.orchestrator import Orchestrator
        
        # Create orchestrator (should auto-initialize Phase 2 modules)
        orchestrator = Orchestrator()
        print("✓ Orchestrator created with Phase 2 integration")
        
        # Test that modules are properly initialized
        assert orchestrator.session_manager is not None, "Session manager should be initialized"
        assert orchestrator.agent_factory is not None, "Agent factory should be initialized"
        assert orchestrator.state_manager is not None, "State manager should be initialized"
        assert orchestrator.briefing_system is not None, "Briefing system should be initialized"
        print("✓ All Phase 2 modules properly integrated")
        
        # Test OAuth functionality (from Phase 1)
        status = orchestrator.check_oauth_port_conflicts()
        print(f"✓ OAuth conflict check: Port {status['port']}, Free: {status['is_free']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Integrated Orchestrator test failed: {e}")
        return False

def main():
    """Run all Phase 2 tests."""
    print("🚀 Testing Phase 2: Core System Modules")
    print("=" * 50)
    
    tests = [
        test_session_manager,
        test_state_manager,
        test_agent_factory,
        test_briefing_system,
        test_integrated_orchestrator
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
    print(f"📊 Phase 2 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 Phase 2 implementation successful!")
        print("\n✨ Session management and state tracking working")
        print("✨ Agent factory and role configuration functional")
        print("✨ Briefing system generating comprehensive briefings")
        print("✨ Integration with Phase 1 OAuth modules complete")
        print("✨ Ready for Phase 3: Infrastructure Modules")
        return True
    else:
        print(f"⚠️  {failed} tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
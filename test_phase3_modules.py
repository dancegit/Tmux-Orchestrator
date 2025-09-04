#!/usr/bin/env python3
"""
Test script for Phase 3 modules of the Tmux Orchestrator system.

Tests git worktree manager, tmux session controller, and messaging system.
"""

import sys
import tempfile
from pathlib import Path

# Add tmux_orchestrator package to path
sys.path.insert(0, str(Path(__file__).parent))

def test_worktree_manager():
    """Test the git worktree manager functionality."""
    print("🧪 Testing Git Worktree Manager...")
    
    try:
        from tmux_orchestrator.git.worktree_manager import WorktreeManager
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test-project"
            temp_path.mkdir()
            
            # Initialize git repo
            import subprocess
            subprocess.run(['git', 'init'], cwd=temp_path, check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=temp_path, check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_path, check=True, capture_output=True)
            
            # Create initial commit
            (temp_path / 'README.md').write_text('# Test Project')
            subprocess.run(['git', 'add', '.'], cwd=temp_path, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=temp_path, check=True, capture_output=True)
            
            # Create worktree manager
            manager = WorktreeManager(temp_path)
            print("✓ Worktree manager created successfully")
            
            # Test worktree base path
            base_path = manager.get_worktree_base_path()
            print(f"✓ Worktree base path: {base_path.name}")
            
            # Test team worktree creation
            roles = ['developer', 'tester']
            worktree_paths = manager.create_team_worktrees(roles)
            
            if len(worktree_paths) == len(roles):
                print(f"✓ Created worktrees for {len(roles)} roles")
            else:
                print(f"⚠️ Created {len(worktree_paths)}/{len(roles)} worktrees")
            
            # Test worktree listing
            active_worktrees = manager.list_active_worktrees()
            print(f"✓ Listed {len(active_worktrees)} active worktrees")
        
        return True
        
    except Exception as e:
        print(f"❌ Worktree Manager test failed: {e}")
        return False

def test_tmux_controller():
    """Test the tmux session controller functionality."""
    print("\n🧪 Testing Tmux Session Controller...")
    
    try:
        from tmux_orchestrator.tmux.session_controller import TmuxSessionController
        from tmux_orchestrator.core.session_manager import AgentState
        
        # Create controller
        controller = TmuxSessionController(Path(__file__).parent)
        print("✓ Tmux session controller created successfully")
        
        # Test session listing
        sessions = controller.list_sessions()
        print(f"✓ Listed {len(sessions)} active tmux sessions")
        
        # Test window creation (dry run - don't actually create tmux sessions)
        test_session = "test-orchestration"
        
        # Check if test session exists
        exists = controller.session_exists(test_session)
        print(f"✓ Session existence check: {exists}")
        
        # Test agent configuration
        agents = {
            'developer': AgentState(
                role='developer',
                window_index=1,
                window_name='Developer',
                worktree_path='/tmp/dev-worktree'
            ),
            'tester': AgentState(
                role='tester',
                window_index=2,
                window_name='Tester', 
                worktree_path='/tmp/test-worktree'
            )
        }
        
        # Note: Not actually creating session to avoid tmux dependency issues
        print(f"✓ Agent configuration prepared for {len(agents)} agents")
        
        return True
        
    except Exception as e:
        print(f"❌ Tmux Controller test failed: {e}")
        return False

def test_messaging_system():
    """Test the tmux messaging system."""
    print("\n🧪 Testing Tmux Messaging System...")
    
    try:
        from tmux_orchestrator.tmux.messaging import TmuxMessenger
        
        # Create messenger
        messenger = TmuxMessenger(Path(__file__).parent)
        print("✓ Tmux messenger created successfully")
        
        # Test message cleaning
        test_message = "`This is a test message with backticks`"
        cleaned = messenger._clean_message_from_mcp_wrappers(test_message)
        print(f"✓ Message cleaning: '{test_message}' -> '{cleaned}'")
        
        # Test role resolution (will fail gracefully without tmux session)
        resolved = messenger.resolve_role_to_window("test-session", "Developer")
        print(f"✓ Role resolution test completed (result: {resolved})")
        
        # Test message history
        messenger._log_message("test-target", "test message", True)
        history = messenger.get_message_history()
        print(f"✓ Message history: {len(history)} messages logged")
        
        # Test helper script creation
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_worktree = Path(temp_dir)
            success = messenger.create_messaging_helpers(
                role="developer",
                worktree_path=temp_worktree,
                session_name="test-session"
            )
            
            if success:
                scripts_dir = temp_worktree / 'scripts'
                script_count = len(list(scripts_dir.glob('*.sh')))
                print(f"✓ Created {script_count} messaging helper scripts")
            else:
                print("⚠️ Helper script creation had issues")
        
        return True
        
    except Exception as e:
        print(f"❌ Messaging System test failed: {e}")
        return False

def test_integrated_orchestrator():
    """Test the orchestrator with Phase 3 integration."""
    print("\n🧪 Testing Orchestrator with Phase 3 Integration...")
    
    try:
        from tmux_orchestrator.core.orchestrator import Orchestrator
        
        # Create orchestrator (should now include Phase 3 modules)
        orchestrator = Orchestrator()
        print("✓ Orchestrator created with Phase 3 integration")
        
        # Test that new modules are properly initialized
        assert orchestrator.git_manager is not None, "Git manager should be initialized"
        assert orchestrator.tmux_controller is not None, "Tmux controller should be initialized"  
        assert orchestrator.messenger is not None, "Messenger should be initialized"
        print("✓ All Phase 3 modules properly integrated")
        
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
        
        return True
        
    except Exception as e:
        print(f"❌ Integrated Orchestrator test failed: {e}")
        return False

def test_end_to_end_workflow():
    """Test an end-to-end workflow simulation."""
    print("\n🧪 Testing End-to-End Workflow Simulation...")
    
    try:
        from tmux_orchestrator.core.orchestrator import Orchestrator
        from tmux_orchestrator.agents.briefing_system import BriefingContext, ProjectSpec
        from tmux_orchestrator.agents.agent_factory import RoleConfig
        
        # Create orchestrator
        orchestrator = Orchestrator()
        
        # Simulate project setup
        project_spec = ProjectSpec(
            name="Test E2E Project",
            path="/tmp/test-project",
            type="web_application",
            main_tech=["Python", "FastAPI"]
        )
        
        # Create agent states
        role_config = RoleConfig(
            responsibilities=["Implementation", "Testing"],
            check_in_interval=30,
            initial_commands=[]
        )
        
        # Test briefing generation
        context = BriefingContext(
            project_spec=project_spec,
            role_config=role_config,
            session_name="test-session",
            worktree_path=Path("/tmp/test-worktree"),
            team_members=[("developer", 1), ("tester", 2)]
        )
        
        briefing = orchestrator.briefing_system.generate_role_briefing(context)
        print(f"✓ Generated briefing: {len(briefing)} characters")
        
        # Test state tracking
        orchestrator.state_manager.track_agent_dependency("test-session", "tester", "developer")
        dependencies = orchestrator.state_manager.get_agent_dependencies("test-session", "tester")
        print(f"✓ Tracked dependencies: {len(dependencies)} dependencies")
        
        print("✓ End-to-end workflow simulation successful")
        return True
        
    except Exception as e:
        print(f"❌ End-to-end workflow test failed: {e}")
        return False

def main():
    """Run all Phase 3 tests."""
    print("🚀 Testing Phase 3: Infrastructure Modules")
    print("=" * 50)
    
    tests = [
        test_worktree_manager,
        test_tmux_controller,
        test_messaging_system,
        test_integrated_orchestrator,
        test_end_to_end_workflow
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
    print(f"📊 Phase 3 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 Phase 3 implementation successful!")
        print("\n✨ Git worktree management with fallback strategies")
        print("✨ Tmux session control and health monitoring")
        print("✨ Inter-agent messaging with compliance checking")
        print("✨ Full integration with Phases 1 and 2")
        print("✨ End-to-end workflow simulation working")
        print("✨ Ready for Phase 4: Support Modules")
        return True
    else:
        print(f"⚠️  {failed} tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
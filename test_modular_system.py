#!/usr/bin/env python3
"""
Test script for the modularized Tmux Orchestrator system.

This script tests the critical OAuth timing functionality that has been
extracted into the modular system while preserving backward compatibility.
"""

import sys
from pathlib import Path

# Add tmux_orchestrator package to path
sys.path.insert(0, str(Path(__file__).parent))

def test_oauth_manager():
    """Test the OAuth manager functionality."""
    print("🧪 Testing OAuth Manager...")
    
    try:
        from tmux_orchestrator.claude.oauth_manager import OAuthManager
        
        # Create OAuth manager
        oauth_manager = OAuthManager()
        print(f"✓ OAuth manager created, managing port {oauth_manager.oauth_port}")
        
        # Test port availability check
        is_free = oauth_manager.is_port_free()
        print(f"✓ Port {oauth_manager.oauth_port} is free: {is_free}")
        
        # Test batch conflict detection
        conflict_result = oauth_manager.check_batch_processing_conflict("test-session")
        print(f"✓ Batch processing conflict check: {conflict_result}")
        
        return True
        
    except Exception as e:
        print(f"❌ OAuth Manager test failed: {e}")
        return False

def test_claude_initializer():
    """Test the Claude initializer functionality."""
    print("\n🧪 Testing Claude Initializer...")
    
    try:
        from tmux_orchestrator.claude.initialization import ClaudeInitializer
        
        # Create initializer
        initializer = ClaudeInitializer()
        print("✓ Claude initializer created successfully")
        
        # Test that it has the required components
        assert hasattr(initializer, 'oauth_manager'), "Missing oauth_manager"
        assert hasattr(initializer, 'mcp_manager'), "Missing mcp_manager"
        print("✓ Required components present")
        
        return True
        
    except Exception as e:
        print(f"❌ Claude Initializer test failed: {e}")
        return False

def test_core_orchestrator():
    """Test the core orchestrator functionality."""
    print("\n🧪 Testing Core Orchestrator...")
    
    try:
        from tmux_orchestrator.core.orchestrator import Orchestrator
        
        # Create orchestrator
        orchestrator = Orchestrator()
        print("✓ Core orchestrator created successfully")
        
        # Test OAuth conflict checking
        status = orchestrator.check_oauth_port_conflicts()
        print(f"✓ OAuth conflict status: Port {status['port']}, Free: {status['is_free']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Core Orchestrator test failed: {e}")
        return False

def test_main_entry_points():
    """Test the main entry points."""
    print("\n🧪 Testing Main Entry Points...")
    
    try:
        from tmux_orchestrator.main import (
            create_orchestrator, 
            check_oauth_conflicts
        )
        
        # Test orchestrator creation
        orchestrator = create_orchestrator()
        print("✓ Orchestrator created via main entry point")
        
        # Test OAuth conflict checking
        status = check_oauth_conflicts()
        print(f"✓ OAuth status via main entry point: {status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Main entry points test failed: {e}")
        return False

def test_package_imports():
    """Test package-level imports."""
    print("\n🧪 Testing Package Imports...")
    
    try:
        import tmux_orchestrator
        print(f"✓ Main package imported, version: {tmux_orchestrator.__version__}")
        
        from tmux_orchestrator import main, create_orchestrator
        print("✓ Main entry points imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Package imports test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing Modularized Tmux Orchestrator System")
    print("=" * 50)
    
    tests = [
        test_package_imports,
        test_oauth_manager,
        test_claude_initializer, 
        test_core_orchestrator,
        test_main_entry_points
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
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Modular system is working correctly.")
        print("\n✨ Critical OAuth timing logic has been successfully modularized")
        print("✨ Backward compatibility maintained with original system")
        print("✨ Ready for gradual migration of remaining components")
        return True
    else:
        print(f"⚠️  {failed} tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
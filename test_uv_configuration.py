#!/usr/bin/env python3
"""Test script to verify UV configuration is working correctly"""

import os
import subprocess
import sys
from pathlib import Path

def test_uv_environment():
    """Test that UV_NO_WORKSPACE is set correctly"""
    print("Testing UV environment configuration...")
    
    # Test 1: Check if UV_NO_WORKSPACE is set
    uv_no_workspace = os.environ.get('UV_NO_WORKSPACE')
    if uv_no_workspace == '1':
        print("✅ UV_NO_WORKSPACE is correctly set to '1'")
    else:
        print(f"❌ UV_NO_WORKSPACE is not set correctly: {uv_no_workspace}")
        return False
    
    # Test 2: Try running a simple UV command
    try:
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ UV is accessible: {result.stdout.strip()}")
        else:
            print(f"❌ UV command failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ UV command not found in PATH")
        return False
    
    # Test 3: Test UV command with UV_NO_WORKSPACE
    try:
        # Create a temporary directory to test UV behavior
        test_dir = Path("/tmp/uv_test_dir")
        test_dir.mkdir(exist_ok=True)
        
        # Run UV command in the test directory
        result = subprocess.run(
            ['uv', 'run', 'python', '-c', 'print("UV test successful")'],
            cwd=str(test_dir),
            capture_output=True,
            text=True,
            env={**os.environ, 'UV_NO_WORKSPACE': '1'}
        )
        
        if result.returncode == 0 and "UV test successful" in result.stdout:
            print("✅ UV run command works with UV_NO_WORKSPACE=1")
        else:
            print(f"❌ UV run command failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing UV command: {e}")
        return False
    
    # Test 4: Test tmux window environment setting
    try:
        # Create a test tmux session
        session_name = "uv_test_session"
        subprocess.run(['tmux', 'kill-session', '-t', session_name], capture_output=True)
        subprocess.run(['tmux', 'new-session', '-d', '-s', session_name], check=True)
        
        # Set UV_NO_WORKSPACE in the tmux session
        subprocess.run([
            'tmux', 'set-environment', '-t', session_name,
            'UV_NO_WORKSPACE', '1'
        ], check=True)
        
        # Check if it was set correctly
        result = subprocess.run([
            'tmux', 'show-environment', '-t', session_name, 'UV_NO_WORKSPACE'
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and 'UV_NO_WORKSPACE=1' in result.stdout:
            print("✅ Tmux environment variable setting works correctly")
        else:
            print(f"❌ Tmux environment setting failed: {result.stdout}")
            return False
            
        # Clean up
        subprocess.run(['tmux', 'kill-session', '-t', session_name], capture_output=True)
        
    except Exception as e:
        print(f"⚠️  Could not test tmux environment (tmux might not be available): {e}")
    
    return True

def test_auto_orchestrate_import():
    """Test that auto_orchestrate.py can be imported with UV configuration"""
    print("\nTesting auto_orchestrate.py import...")
    
    # Set UV_NO_WORKSPACE before import
    os.environ['UV_NO_WORKSPACE'] = '1'
    
    try:
        # Add current directory to Python path
        sys.path.insert(0, str(Path(__file__).parent))
        
        # Try to import auto_orchestrate
        import auto_orchestrate
        print("✅ auto_orchestrate.py imported successfully")
        
        # Check if UV_NO_WORKSPACE is still set after import
        if os.environ.get('UV_NO_WORKSPACE') == '1':
            print("✅ UV_NO_WORKSPACE remains set after import")
        else:
            print("❌ UV_NO_WORKSPACE was cleared during import")
            return False
            
    except Exception as e:
        print(f"❌ Failed to import auto_orchestrate.py: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("=== UV Configuration Test Suite ===\n")
    
    all_passed = True
    
    # Run environment test
    if not test_uv_environment():
        all_passed = False
    
    # Run import test
    if not test_auto_orchestrate_import():
        all_passed = False
    
    print("\n=== Test Summary ===")
    if all_passed:
        print("✅ All tests passed! UV configuration is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
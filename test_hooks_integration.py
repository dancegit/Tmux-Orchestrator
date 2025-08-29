#!/usr/bin/env python3
"""
Integration test script for hooks-based message queue system.
Tests database setup, message enqueueing, hook scripts, and integration.
"""

import os
import sys
import sqlite3
import subprocess
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add claude_hooks to path
sys.path.insert(0, str(Path(__file__).parent / 'claude_hooks'))

def test_database_setup():
    """Test database migration and table creation."""
    print("\n=== Testing Database Setup ===")
    
    # Create a test database
    test_db = Path("test_queue.db")
    if test_db.exists():
        test_db.unlink()
    
    # Create an empty database file
    conn = sqlite3.connect(test_db)
    conn.close()
    
    # Run migration
    result = subprocess.run([
        'python3', 'migrate_queue_db.py',
        '--db-path', str(test_db)
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Migration failed: {result.stderr}")
        return False
    
    # Verify tables
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = ['message_queue', 'agents', 'sequence_generator', 'migrations', 'agent_context', 'session_events']
    for table in expected_tables:
        if table in tables:
            print(f"✅ Table '{table}' created")
        else:
            print(f"❌ Table '{table}' missing")
            return False
    
    conn.close()
    test_db.unlink()
    return True

def test_message_enqueueing():
    """Test message enqueueing functionality."""
    print("\n=== Testing Message Enqueueing ===")
    
    # Create test database
    test_db = Path("test_queue.db")
    subprocess.run(['python3', 'migrate_queue_db.py', '--db-path', str(test_db)], 
                  capture_output=True)
    
    # Set environment variable
    os.environ['QUEUE_DB_PATH'] = str(test_db)
    
    from enqueue_message import enqueue_message, get_queue_status
    
    try:
        # Test single message
        msg_id = enqueue_message(
            agent_id="test-session:1",
            message="Test message 1",
            priority=10
        )
        print(f"✅ Enqueued message with ID: {msg_id}")
        
        # Test high priority message
        msg_id2 = enqueue_message(
            agent_id="test-session:1", 
            message="Urgent message",
            priority=90
        )
        print(f"✅ Enqueued high-priority message with ID: {msg_id2}")
        
        # Check queue status
        status = get_queue_status("test-session:1")
        print(f"✅ Queue status: {status}")
        
        if status.get('pending') != 2:
            print(f"❌ Expected 2 pending messages, got {status.get('pending')}")
            return False
            
    except Exception as e:
        print(f"❌ Enqueueing failed: {e}")
        return False
    finally:
        test_db.unlink()
    
    return True

def test_check_queue_script():
    """Test the check_queue hook script."""
    print("\n=== Testing Check Queue Script ===")
    
    # Create test database with messages
    test_db = Path("test_queue.db")
    subprocess.run(['python3', 'migrate_queue_db.py', '--db-path', str(test_db)],
                  capture_output=True)
    
    os.environ['QUEUE_DB_PATH'] = str(test_db)
    
    from enqueue_message import enqueue_message
    
    # Enqueue test messages
    enqueue_message("test-session:1", "Message 1", priority=10)
    enqueue_message("test-session:1", "Message 2", priority=20)
    
    # Test bootstrap mode
    result = subprocess.run([
        'python3', 'claude_hooks/check_queue_enhanced.py',
        '--agent', 'test-session:1',
        '--bootstrap',
        '--no-validation'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        # Should output the highest priority message
        if "Message 2" in result.stdout:
            print("✅ Bootstrap mode returned correct message")
        else:
            print(f"❌ Unexpected output: {result.stdout}")
            return False
    else:
        print(f"❌ Check queue failed: {result.stderr}")
        return False
    
    test_db.unlink()
    return True

def test_cleanup_script():
    """Test the cleanup_agent script."""
    print("\n=== Testing Cleanup Script ===")
    
    # Create test database
    test_db = Path("test_queue.db") 
    subprocess.run(['python3', 'migrate_queue_db.py', '--db-path', str(test_db)],
                  capture_output=True)
    
    os.environ['QUEUE_DB_PATH'] = str(test_db)
    
    # Run cleanup
    result = subprocess.run([
        'python3', 'claude_hooks/cleanup_agent.py',
        '--agent', 'test-session:1'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Cleanup script executed successfully")
    else:
        print(f"❌ Cleanup failed: {result.stderr}")
        test_db.unlink()
        return False
    
    test_db.unlink()
    return True

def test_hook_setup():
    """Test agent hook setup process."""
    print("\n=== Testing Hook Setup ===")
    
    # Create temporary worktree
    with tempfile.TemporaryDirectory() as tmpdir:
        worktree = Path(tmpdir)
        
        # Run setup script
        result = subprocess.run([
            'python3', 'setup_agent_hooks.py',
            str(worktree),
            '--agent-id', 'test-session:1'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Setup failed: {result.stderr}")
            return False
        
        # Verify files
        claude_dir = worktree / '.claude'
        required_files = [
            claude_dir / 'settings.json',
            claude_dir / 'settings.local.json',
            claude_dir / 'hooks' / 'check_queue_enhanced.py'
        ]
        
        for file_path in required_files:
            if file_path.exists():
                print(f"✅ Created: {file_path.relative_to(worktree)}")
            else:
                print(f"❌ Missing: {file_path.relative_to(worktree)}")
                return False
    
    return True

def test_tmux_messenger_integration():
    """Test TmuxMessenger with hooks enabled."""
    print("\n=== Testing TmuxMessenger Integration ===")
    
    # Create test database
    test_db = Path("test_queue.db")
    subprocess.run(['python3', 'migrate_queue_db.py', '--db-path', str(test_db)],
                  capture_output=True)
    
    os.environ['QUEUE_DB_PATH'] = str(test_db)
    
    # Import with modified sys.path
    from tmux_messenger_hooks import TmuxMessenger
    
    try:
        messenger = TmuxMessenger(Path.cwd())
        
        # Test sending a message
        success = messenger.send_message(
            "test-session:1",
            "Test message via messenger",
            priority=50
        )
        
        if success:
            print("✅ Message sent via hooks")
        else:
            print("❌ Message send failed")
            return False
        
        # Check queue stats
        stats = messenger.get_queue_stats("test-session:1")
        print(f"✅ Queue stats: {stats}")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False
    finally:
        test_db.unlink()
    
    return True

def test_postcompact_rebriefing():
    """Test PostCompact rebriefing functionality."""
    print("\n=== Testing PostCompact Rebriefing ===")
    
    # Create test database
    test_db = Path("test_queue.db")
    subprocess.run(['python3', 'migrate_queue_db.py', '--db-path', str(test_db)],
                  capture_output=True)
    
    os.environ['QUEUE_DB_PATH'] = str(test_db)
    
    # Test rebriefing trigger
    result = subprocess.run([
        'python3', 'claude_hooks/check_queue_enhanced.py',
        '--agent', 'test-session:1',
        '--rebrief',
        '--no-validation'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        output = json.loads(result.stdout)
        if output.get('status') == 'rebrief_queued':
            print("✅ Rebrief message queued successfully")
        else:
            print(f"❌ Unexpected status: {output}")
            test_db.unlink()
            return False
    else:
        print(f"❌ Rebrief failed: {result.stderr}")
        test_db.unlink()
        return False
    
    # Check that a message was queued
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM message_queue WHERE agent_id = 'test-session:1' AND priority > 90")
    messages = cursor.fetchall()
    conn.close()
    
    if messages and any('Context Restoration After Compaction' in msg[0] for msg in messages):
        print("✅ Rebriefing message found in queue")
    else:
        print("❌ No rebriefing message found")
        test_db.unlink()
        return False
    
    test_db.unlink()
    return True

def test_end_to_end_flow():
    """Test complete message flow from enqueue to delivery."""
    print("\n=== Testing End-to-End Flow ===")
    
    # This would require a running tmux session with Claude
    # For now, we'll simulate the flow
    
    test_db = Path("test_queue.db")
    subprocess.run(['python3', 'migrate_queue_db.py', '--db-path', str(test_db)],
                  capture_output=True)
    
    os.environ['QUEUE_DB_PATH'] = str(test_db)
    
    from enqueue_message import enqueue_message
    
    # Simulate message flow
    print("1. Enqueueing message...")
    msg_id = enqueue_message("test-session:1", "End-to-end test message", priority=50)
    
    print("2. Simulating hook trigger...")
    result = subprocess.run([
        'python3', 'claude_hooks/check_queue_enhanced.py',
        '--agent', 'test-session:1',
        '--no-validation'
    ], capture_output=True, text=True)
    
    if "End-to-end test message" in result.stdout:
        print("✅ Message pulled successfully")
    else:
        print(f"❌ Message not pulled: {result.stdout}")
        test_db.unlink()
        return False
    
    # Check database state
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM message_queue WHERE id = ?", (msg_id,))
    status = cursor.fetchone()[0]
    
    if status == 'pulled':
        print("✅ Message marked as pulled in database")
    else:
        print(f"❌ Unexpected status: {status}")
        conn.close()
        test_db.unlink()
        return False
    
    conn.close()
    test_db.unlink()
    return True

def main():
    """Run all tests."""
    print("🧪 Tmux-Orchestrator Hooks Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Database Setup", test_database_setup),
        ("Message Enqueueing", test_message_enqueueing),
        ("Check Queue Script", test_check_queue_script),
        ("Cleanup Script", test_cleanup_script),
        ("Hook Setup", test_hook_setup),
        ("TmuxMessenger Integration", test_tmux_messenger_integration),
        ("PostCompact Rebriefing", test_postcompact_rebriefing),
        ("End-to-End Flow", test_end_to_end_flow)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {failed} test(s) failed")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
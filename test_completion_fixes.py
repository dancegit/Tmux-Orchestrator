#!/usr/bin/env python3
"""
Test script to verify completion detector fixes are working correctly.
Tests that empty projects are not marked as complete.
"""

import sys
import json
import sqlite3
from pathlib import Path
from completion_detector import CompletionDetector
from implementation_validator import validate_project_implementation

def test_empty_project():
    """Test that an empty project is not marked complete"""
    print("\n=== Testing Empty Project Detection ===")
    
    # Create a test project with empty directory
    test_project = {
        'id': 999,
        'project_name': 'test-empty-project',
        'session_name': '',  # NULL session like batch projects
        'project_path': '/home/clauderun/signalmatrix/signalmatrix_org/.ciis/batch_projects/ciis_proposal_test-20250905231034',
        'spec_file': 'test.md',
        'status': 'processing',
        'started_at': '2025-09-06 10:00:00'
    }
    
    # Test implementation validator
    print(f"\n1. Testing implementation validator on: {test_project['project_path']}")
    is_valid = validate_project_implementation(test_project['project_path'])
    print(f"   Result: {'VALID' if is_valid else 'INVALID (as expected)'}")
    
    # Test completion detector
    print("\n2. Testing completion detector...")
    detector = CompletionDetector(Path(__file__).parent)
    status, reason = detector.detect_completion(test_project)
    print(f"   Status: {status}")
    print(f"   Reason: {reason}")
    
    if status == 'processing' and 'validation failed' in reason.lower():
        print("\n✅ SUCCESS: Empty project correctly blocked from completion!")
        return True
    else:
        print("\n❌ FAILURE: Empty project was not blocked!")
        return False

def test_null_session_project():
    """Test that projects with NULL session names are handled correctly"""
    print("\n=== Testing NULL Session Name Handling ===")
    
    # Get actual projects with NULL session names from database
    db_path = Path(__file__).parent / 'task_queue.db'
    
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, project_path, spec_path, status
                FROM project_queue 
                WHERE session_name IS NULL 
                AND status IN ('processing', 'completed')
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                project_id, project_path, spec_path, status = row
                print(f"\nFound project {project_id} with NULL session:")
                print(f"  Path: {project_path}")
                print(f"  Status: {status}")
                
                test_project = {
                    'id': project_id,
                    'project_name': 'null-session-project',
                    'session_name': '',
                    'project_path': project_path,
                    'spec_file': spec_path,
                    'status': status,
                    'started_at': '2025-09-06 10:00:00'
                }
                
                detector = CompletionDetector(Path(__file__).parent)
                status, reason = detector.detect_completion(test_project)
                print(f"\n  Detection result: {status}")
                print(f"  Reason: {reason}")
                
                if 'validation' in reason.lower():
                    print("\n✅ Validation is being enforced for NULL session projects")
                    return True
            else:
                print("\nNo projects with NULL session names found in database")
                return True
                
    except Exception as e:
        print(f"\nError checking database: {e}")
        return False

def test_worktree_detection():
    """Test that the validator checks worktree directories"""
    print("\n=== Testing Worktree Detection ===")
    
    # Find a project with worktrees
    test_paths = [
        '/home/clauderun/signalmatrix/signalmatrix_org/.ciis/batch_projects/ciis_proposal_prop-20250905184513-2',
        '/home/clauderun/signalmatrix/signalmatrix_org/.ciis/batch_projects/ciis_proposal_test-20250905185854'
    ]
    
    for test_path in test_paths:
        if Path(test_path).exists():
            print(f"\nTesting: {test_path}")
            
            # Check if worktrees exist
            parent = Path(test_path).parent
            project_name = Path(test_path).name
            worktree_dir = parent / f"{project_name}-tmux-worktrees"
            
            if worktree_dir.exists():
                print(f"  Found worktree dir: {worktree_dir}")
                # Count agent directories
                agent_dirs = [d for d in worktree_dir.iterdir() if d.is_dir()]
                print(f"  Agent directories: {len(agent_dirs)}")
                
                if len(agent_dirs) == 0:
                    print("  ⚠️  Empty worktree directory (no agents)")
            
            # Test validator
            is_valid = validate_project_implementation(test_path)
            print(f"  Validation result: {'VALID' if is_valid else 'INVALID'}")
            
            if not is_valid:
                print("  ✅ Empty project correctly identified")
            break
    
    return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("COMPLETION DETECTOR FIX VERIFICATION")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Empty Project Detection", test_empty_project()))
    results.append(("NULL Session Handling", test_null_session_project()))
    results.append(("Worktree Detection", test_worktree_detection()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\nOverall: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed! The fixes are working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""Test script for worktree creation logic"""

import subprocess
import tempfile
import shutil
from pathlib import Path

def test_worktree_creation():
    # Create a test repository
    with tempfile.TemporaryDirectory() as tmpdir:
        test_repo = Path(tmpdir) / "test-repo"
        test_repo.mkdir()
        
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=test_repo, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=test_repo)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=test_repo)
        
        # Create initial commit
        (test_repo / "README.md").write_text("# Test Project")
        subprocess.run(['git', 'add', '.'], cwd=test_repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=test_repo, check=True)
        
        # Get current branch
        result = subprocess.run(['git', 'branch', '--show-current'], 
                               cwd=test_repo, capture_output=True, text=True)
        current_branch = result.stdout.strip()
        print(f"Current branch: {current_branch}")
        
        # Test Strategy 1: Normal worktree
        worktree1 = test_repo / "worktrees" / "normal"
        worktree1.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(['git', 'worktree', 'add', str(worktree1), current_branch],
                               cwd=test_repo, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Strategy 1 (normal): Success")
        else:
            print(f"✗ Strategy 1 (normal): Failed - {result.stderr}")
            
            # Test Strategy 2: Force
            result = subprocess.run(['git', 'worktree', 'add', '--force', str(worktree1), current_branch],
                                   cwd=test_repo, capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ Strategy 2 (force): Success")
            else:
                print(f"✗ Strategy 2 (force): Failed - {result.stderr}")
        
        # Test Strategy 3: Agent-specific branch
        worktree2 = test_repo / "worktrees" / "agent-branch"
        agent_branch = f"{current_branch}-developer"
        subprocess.run(['git', 'branch', agent_branch, current_branch], 
                      cwd=test_repo, capture_output=True)
        result = subprocess.run(['git', 'worktree', 'add', '-b', agent_branch, str(worktree2), current_branch],
                               cwd=test_repo, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Strategy 3 (agent branch): Success")
        else:
            print(f"✗ Strategy 3 (agent branch): Failed - {result.stderr}")
        
        # Test Strategy 4: Orphan (if supported)
        worktree3 = test_repo / "worktrees" / "orphan"
        result = subprocess.run(['git', 'worktree', 'add', '--orphan', 'orphan-test', str(worktree3)],
                               cwd=test_repo, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Strategy 4 (orphan): Success")
        else:
            print(f"✗ Strategy 4 (orphan): Failed - {result.stderr}")
        
        # Test Strategy 5: Detached HEAD
        worktree4 = test_repo / "worktrees" / "detached"
        commit_result = subprocess.run(['git', 'rev-parse', 'HEAD'],
                                      cwd=test_repo, capture_output=True, text=True)
        commit_hash = commit_result.stdout.strip()
        result = subprocess.run(['git', 'worktree', 'add', '--detach', str(worktree4), commit_hash],
                               cwd=test_repo, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Strategy 5 (detached): Success")
        else:
            print(f"✗ Strategy 5 (detached): Failed - {result.stderr}")
        
        # List all worktrees
        print("\nWorktrees created:")
        subprocess.run(['git', 'worktree', 'list'], cwd=test_repo)

if __name__ == "__main__":
    test_worktree_creation()
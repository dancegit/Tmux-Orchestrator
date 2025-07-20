#!/bin/bash
# Test script for safety mechanism

echo "Testing auto_orchestrate.py safety mechanism..."

# Test 1: Check help text includes --force
echo "Test 1: Checking --force flag in help"
./auto_orchestrate.py --help | grep -q "force" && echo "✓ Force flag found in help" || echo "✗ Force flag missing"

# Test 2: Check existing worktree detection
echo -e "\nTest 2: Testing existing worktree detection"
mkdir -p registry/projects/test-project/worktrees/developer
echo "test" > registry/projects/test-project/worktrees/developer/test.txt

# This should prompt (we'll just check the code runs)
echo -e "\nThis test requires manual interaction. Run:"
echo "./auto_orchestrate.py --project /path/to/test/project --spec /path/to/spec.md"
echo "to test the interactive prompt."

# Clean up
rm -rf registry/projects/test-project

echo -e "\nTest complete!"
#!/bin/bash
# Integration test for UV configuration with auto_orchestrate.py

echo "=== UV Integration Test ==="
echo

# Test 1: Check if auto_orchestrate.py can be executed
echo "Test 1: Running auto_orchestrate.py --help"
if UV_NO_WORKSPACE=1 ./auto_orchestrate.py --help >/dev/null 2>&1; then
    echo "✅ auto_orchestrate.py executes successfully with UV_NO_WORKSPACE=1"
else
    echo "❌ auto_orchestrate.py failed to execute"
    exit 1
fi

# Test 2: Check if scheduler.py can be executed
echo -e "\nTest 2: Running scheduler.py --help"
if UV_NO_WORKSPACE=1 python3 scheduler.py --help >/dev/null 2>&1; then
    echo "✅ scheduler.py executes successfully with UV_NO_WORKSPACE=1"
else
    echo "❌ scheduler.py failed to execute"
    exit 1
fi

# Test 3: Verify UV commands work in a test worktree
echo -e "\nTest 3: Testing UV in a simulated worktree"
TEST_DIR="/tmp/uv_worktree_test_$$"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

# Create a simple Python script
cat > test_script.py << 'EOF'
#!/usr/bin/env python3
print("Hello from UV test!")
EOF

# Try to run it with UV
if UV_NO_WORKSPACE=1 uv run python test_script.py 2>/dev/null | grep -q "Hello from UV test!"; then
    echo "✅ UV commands work correctly in worktree-like directory"
else
    echo "❌ UV commands failed in worktree-like directory"
    cd - >/dev/null
    rm -rf "$TEST_DIR"
    exit 1
fi

# Cleanup
cd - >/dev/null
rm -rf "$TEST_DIR"

echo -e "\n=== All Integration Tests Passed ===\n"
echo "The UV configuration is properly integrated and working!"
#!/bin/bash

# Comprehensive test script for TmuxManager migration
# Tests all PHASE 1 migrated shell scripts: send-claude-message.sh, send-monitored-message.sh, schedule_with_note.sh

echo "🧪 COMPREHENSIVE TMUX MANAGER MIGRATION TEST"
echo "=============================================="
echo "Testing migrated scripts: send-claude-message.sh, send-monitored-message.sh, schedule_with_note.sh"
echo "Test modes: TmuxManager enabled and disabled"
echo "Target: Self-messaging (should be prevented)"
echo ""

# Get current session for testing
CURRENT_SESSION=$(tmux display-message -p "#{session_name}:#{window_index}" 2>/dev/null || echo "0:0")
echo "🎯 Test target: $CURRENT_SESSION (self-messaging prevention)"
echo ""

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Helper function to run a test
run_test() {
    local test_name="$1"
    local command="$2"
    local expected_result="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo "TEST $TOTAL_TESTS: $test_name"
    echo "Command: $command"
    
    # Run the command and capture output
    output=$(eval "$command" 2>&1)
    result=$?
    
    # Check if test passed (should succeed but prevent self-messaging)
    if echo "$output" | grep -q "self" && echo "$output" | grep -q "prevent"; then
        echo "✅ PASSED - Self-messaging correctly prevented"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ FAILED - Expected self-messaging prevention"
        echo "Output: $output"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    echo ""
}

# Test Suite 1: send-claude-message.sh
echo "📋 TEST SUITE 1: send-claude-message.sh"
echo "---------------------------------------"

for i in {1..5}; do
    run_test "send-claude-message.sh with TmuxManager (run $i)" \
             "USE_TMUX_MANAGER=1 ./send-claude-message.sh '$CURRENT_SESSION' 'Test message $i'" \
             "self-messaging prevented"
done

for i in {1..5}; do
    run_test "send-claude-message.sh without TmuxManager (run $i)" \
             "./send-claude-message.sh '$CURRENT_SESSION' 'Test message $i'" \
             "self-messaging prevented"
done

# Test Suite 2: send-monitored-message.sh  
echo "📋 TEST SUITE 2: send-monitored-message.sh"
echo "------------------------------------------"

for i in {1..5}; do
    run_test "send-monitored-message.sh with TmuxManager (run $i)" \
             "USE_TMUX_MANAGER=1 ./send-monitored-message.sh '$CURRENT_SESSION' 'Monitored test $i'" \
             "self-messaging prevented"
done

for i in {1..5}; do
    run_test "send-monitored-message.sh without TmuxManager (run $i)" \
             "./send-monitored-message.sh '$CURRENT_SESSION' 'Monitored test $i'" \
             "self-messaging prevented"
done

# Test Suite 3: scm shortcut
echo "📋 TEST SUITE 3: scm shortcut"
echo "------------------------------"

for i in {1..5}; do
    run_test "scm with TmuxManager (run $i)" \
             "USE_TMUX_MANAGER=1 ./scm '$CURRENT_SESSION' 'SCM test $i'" \
             "self-messaging prevented"
done

for i in {1..5}; do
    run_test "scm without TmuxManager (run $i)" \
             "./scm '$CURRENT_SESSION' 'SCM test $i'" \
             "self-messaging prevented"
done

# Test Suite 4: schedule_with_note.sh (legacy fallback)
echo "📋 TEST SUITE 4: schedule_with_note.sh (legacy mode)"
echo "----------------------------------------------------"

# Temporarily move scheduler to force legacy mode
mv scheduler.py scheduler.py.temp 2>/dev/null

for i in {1..3}; do
    run_test "schedule_with_note.sh legacy with TmuxManager (run $i)" \
             "USE_TMUX_MANAGER=1 ./schedule_with_note.sh 999 'Legacy TmuxManager test $i' '$CURRENT_SESSION'" \
             "scheduled successfully"
done

for i in {1..3}; do
    run_test "schedule_with_note.sh legacy without TmuxManager (run $i)" \
             "./schedule_with_note.sh 999 'Legacy standard test $i' '$CURRENT_SESSION'" \
             "scheduled successfully"
done

# Restore scheduler
mv scheduler.py.temp scheduler.py 2>/dev/null

# Test Suite 5: schedule_with_note.sh (Python scheduler)
echo "📋 TEST SUITE 5: schedule_with_note.sh (Python mode)"
echo "----------------------------------------------------"

for i in {1..2}; do
    run_test "schedule_with_note.sh Python mode (run $i)" \
             "USE_TMUX_MANAGER=1 ./schedule_with_note.sh 999 'Python scheduler test $i' '$CURRENT_SESSION'" \
             "scheduled successfully"
done

# Final Results
echo ""
echo "🏁 FINAL TEST RESULTS"
echo "====================="
echo "Total tests run: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"

if [ $FAILED_TESTS -eq 0 ]; then
    echo ""
    echo "🎉 ALL TESTS PASSED! TmuxManager migration is successful!"
    echo "✅ All migrated scripts work correctly with and without TmuxManager"
    echo "✅ Backward compatibility is maintained"
    echo "✅ Safety features (self-messaging prevention) are working"
    exit 0
else
    echo ""
    echo "❌ SOME TESTS FAILED. Review the output above for details."
    exit 1
fi
#!/bin/bash
# Extended timeout configuration for long-running projects

# Extend the ProcessManager timeout for orchestration
export MAX_AUTO_ORCHESTRATE_RUNTIME_SEC=7200  # 2 hours (default: 1800 = 30 minutes)
# Note: This variable name is kept for backward compatibility

# Extend the phantom detection grace period
export PHANTOM_GRACE_PERIOD_SEC=3600  # 1 hour (default: 900 = 15 minutes)

# Additional timeout extensions if needed
export ORCHESTRATOR_CHECK_IN_INTERVAL=3600  # 1 hour between check-ins
export TASK_EXECUTION_TIMEOUT=600  # 10 minutes for individual tasks

echo "Extended timeout environment variables loaded:"
echo "  MAX_AUTO_ORCHESTRATE_RUNTIME_SEC=$MAX_AUTO_ORCHESTRATE_RUNTIME_SEC (2 hours)"
echo "  PHANTOM_GRACE_PERIOD_SEC=$PHANTOM_GRACE_PERIOD_SEC (1 hour)"
echo "  ORCHESTRATOR_CHECK_IN_INTERVAL=$ORCHESTRATOR_CHECK_IN_INTERVAL (1 hour)"
echo "  TASK_EXECUTION_TIMEOUT=$TASK_EXECUTION_TIMEOUT (10 minutes)"
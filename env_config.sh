#!/bin/bash
# Tmux Orchestrator Environment Configuration
# Source this file before running the scheduler for custom settings

# Scheduler Settings
export MAX_TASK_RETRIES=5               # Maximum retry attempts before permanently disabling a task
export POLL_INTERVAL_SEC=60             # Polling interval for checking tasks
export MAX_AUTO_ORCHESTRATE_RUNTIME_SEC=7200  # 2 hours runtime limit
export PHANTOM_GRACE_PERIOD_SEC=3600    # 1 hour grace period for phantom detection

# Message Delivery Settings
export RESET_WITH_CTRL_C=0              # Set to 1 to enable Ctrl-C in reset (not recommended)
export RESET_PANE_BEFORE_SEND=1         # Reset pane state before sending messages
export VERIFY_TIMEOUT=5                 # Timeout for message verification
export MAX_ATTEMPTS=3                   # Maximum send attempts
export INITIAL_DELAY=1                  # Initial retry delay in seconds
export BACKOFF_MULTIPLIER=2             # Exponential backoff multiplier

# Logging Settings
export LOG_LEVEL=INFO                   # Log level (DEBUG, INFO, WARNING, ERROR)

echo "Environment configuration loaded:"
echo "  MAX_TASK_RETRIES=$MAX_TASK_RETRIES"
echo "  RESET_WITH_CTRL_C=$RESET_WITH_CTRL_C (Ctrl-C in reset: $([ $RESET_WITH_CTRL_C -eq 1 ] && echo 'enabled' || echo 'disabled'))"
echo "  MAX_ATTEMPTS=$MAX_ATTEMPTS"
echo "  BACKOFF_MULTIPLIER=$BACKOFF_MULTIPLIER"
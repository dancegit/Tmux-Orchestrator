#!/bin/bash
# Cleanup orphaned orchestration tmux sessions
cd /home/clauderun/Tmux-Orchestrator
/usr/bin/python3 cleanup_orphaned_sessions.py --kill >> logs/session_cleanup.log 2>&1

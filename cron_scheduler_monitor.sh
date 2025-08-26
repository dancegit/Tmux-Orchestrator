#!/bin/bash
# Cron wrapper for scheduler monitoring

# Change to the correct directory
cd /home/clauderun/Tmux-Orchestrator

# Run the scheduler monitor and log output
/usr/bin/python3 scheduler_monitor.py status >> logs/scheduler_monitor.log 2>&1
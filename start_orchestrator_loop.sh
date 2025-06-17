#!/bin/bash
# Start the orchestrator loop
# This script ensures the orchestrator keeps running

while true; do
    echo "==================================="
    echo "Orchestrator Loop Check"
    echo "Time: $(date)"
    echo "==================================="
    
    # Run the orchestrator check
    python3 /Users/jasonedward/Coding/Tmux\ orchestrator/orchestrator_claude_loop.py
    
    # Wait 10 minutes before next check
    echo "Next check in 10 minutes..."
    sleep 600
done
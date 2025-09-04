#!/bin/bash
# Queue monitoring script for 7 hours

echo "Starting 7-hour queue monitoring at $(date)"
echo "Will check every 30 minutes (14 checks total)"
echo "============================================"

for i in {1..14}; do
    echo -e "\n📋 Check #$i at $(date '+%H:%M:%S')"
    echo "----------------------------------------"
    
    # Check queue status
    echo "Queue Summary:"
    python3 scheduler.py --queue-list 2>/dev/null | grep -E "processing|queued|failed" | wc -l | while read count; do
        echo "  Total active projects: $count"
    done
    
    # Check for stuck projects
    echo -e "\nProject Status:"
    python3 scheduler.py --queue-list 2>/dev/null | grep -E "^7[0-6]" | while IFS='|' read -r id spec project status rest; do
        echo "  Project $id: $(echo $status | xargs)"
    done
    
    # Check for tmux sessions
    echo -e "\nActive tmux sessions:"
    tmux ls 2>/dev/null | grep -v "tmux-orchestrator-server" | wc -l | while read count; do
        echo "  Agent sessions: $count"
    done
    
    # Check for errors in recent logs
    echo -e "\nRecent errors:"
    find logs/auto_orchestrate/ -name "*.log" -mmin -30 2>/dev/null | xargs grep -l "error\|failed" 2>/dev/null | wc -l | while read count; do
        echo "  Logs with errors (last 30 min): $count"
    done
    
    # If it's not the last check, sleep for 30 minutes
    if [ $i -lt 14 ]; then
        echo -e "\nNext check in 30 minutes..."
        sleep 1800
    fi
done

echo -e "\n============================================"
echo "Monitoring complete at $(date)"

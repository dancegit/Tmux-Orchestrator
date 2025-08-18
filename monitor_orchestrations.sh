#!/bin/bash

# Monitor all running orchestrations
echo "=== SignalMatrix Orchestration Monitor ==="
echo "Current time: $(date)"
echo

# Check running processes
echo "=== Running Orchestration Processes ==="
ps aux | grep auto_orchestrate | grep -v grep | while read line; do
    pid=$(echo "$line" | awk '{print $2}')
    slice=$(echo "$line" | grep -o 'signalmatrix-slice-[^/]*' | head -1)
    echo "PID: $pid - $slice"
done
echo

# Check tmux sessions  
echo "=== Active Tmux Sessions ==="
tmux list-sessions 2>/dev/null | grep -E '(analytics|api-gateway|authentication|backtesting|data-ingestion|signal-detection)' || echo "No orchestration sessions found"
echo

# Check log file status
echo "=== Log File Status ==="
for log in *_orchestrate.log; do
    if [[ -f "$log" ]]; then
        size=$(wc -l < "$log")
        slice=$(echo "$log" | sed 's/_orchestrate.log//')
        echo "$slice: $size lines"
        
        # Show last few lines if there are errors
        if grep -q -i "error\|traceback\|exception" "$log"; then
            echo "  ⚠️  ERRORS DETECTED - Last 3 lines:"
            tail -3 "$log" | sed 's/^/    /'
        fi
    fi
done
echo

echo "=== Recent Log Activity ==="
ls -lt *_orchestrate.log | head -3
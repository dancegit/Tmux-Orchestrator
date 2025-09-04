#!/bin/bash
# Fixed monitoring scheduler with correct target format

echo "Scheduling monitoring check-ins with correct target (33:0)..."

# Calculate remaining checks based on current time
current_time=$(date +%s)
start_time=$(date +%s)

# Create check-in scripts for remaining time (about 6 hours left)
for i in {2..13}; do
    check_num=$((i))
    minutes=$((i * 30))
    
    # Create a script for this check
    cat > /tmp/monitor_check_fixed_$i.sh << EOF
#!/bin/bash
sleep ${minutes}m
cd /home/clauderun/Tmux-Orchestrator
./send-direct-message.sh 33:0 "CHECK QUEUE $check_num/14: Check ./qs and fix any issues ($(($minutes)) min mark)"
echo "Check $check_num sent at \$(date)" >> /tmp/monitor_checks.log
EOF
    
    chmod +x /tmp/monitor_check_fixed_$i.sh
    
    # Run it in background
    nohup /tmp/monitor_check_fixed_$i.sh > /tmp/monitor_check_fixed_$i.log 2>&1 &
    echo "Scheduled check $check_num at $minutes minutes from now (PID: $!)"
done

# Also schedule immediate check for testing
./send-direct-message.sh 33:0 "CHECK QUEUE: Monitoring fixed and restarted. Checks 2-13 scheduled."

echo "Monitoring check-ins scheduled with correct target 33:0!"
#!/bin/bash
# Schedule monitoring messages every 30 minutes for 7 hours

echo "Scheduling 14 monitoring check-ins over 7 hours..."

# Create individual scripts for each check
for i in {1..14}; do
    minutes=$((i * 30))
    
    # Create a script for this check
    cat > /tmp/monitor_check_$i.sh << EOF
#!/bin/bash
sleep ${minutes}m
cd /home/clauderun/Tmux-Orchestrator
./send-direct-message.sh 33 "CHECK QUEUE $i/14: Check ./qs and fix any issues (${minutes} min mark)"
EOF
    
    chmod +x /tmp/monitor_check_$i.sh
    
    # Run it in background
    nohup /tmp/monitor_check_$i.sh > /tmp/monitor_check_$i.log 2>&1 &
    echo "Scheduled check $i at $minutes minutes (PID: $!)"
done

echo "All 14 check-ins scheduled!"
echo "They will run at: 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360, 390, 420 minutes"
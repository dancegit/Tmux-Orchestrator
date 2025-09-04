#!/bin/bash
#
# Control script for Tmux Orchestrator Queue Error Monitoring Service
#

set -euo pipefail

SERVICE_NAME="tmux-queue-error-monitor"
TIMER_NAME="tmux-queue-error-monitor.timer"
SESSION_NAME="queue-error-monitoring-service"
LOG_FILE="/home/clauderun/Tmux-Orchestrator/logs/queue_error_monitor.log"

show_usage() {
    echo "Usage: $0 {start|stop|restart|status|logs|run-now|attach|clean}"
    echo ""
    echo "Commands:"
    echo "  start     - Start the monitoring timer"
    echo "  stop      - Stop the monitoring timer"
    echo "  restart   - Restart the monitoring timer"
    echo "  status    - Show service and timer status"
    echo "  logs      - Show recent service logs"
    echo "  run-now   - Run the monitoring service immediately"
    echo "  attach    - Attach to the monitoring tmux session"
    echo "  clean     - Clean up logs and tmux session"
}

cmd_start() {
    echo "Starting queue error monitoring timer..."
    sudo systemctl start "$TIMER_NAME"
    sudo systemctl enable "$TIMER_NAME"
    echo "Timer started and enabled"
}

cmd_stop() {
    echo "Stopping queue error monitoring timer..."
    sudo systemctl stop "$TIMER_NAME"
    echo "Timer stopped"
}

cmd_restart() {
    echo "Restarting queue error monitoring timer..."
    sudo systemctl restart "$TIMER_NAME"
    echo "Timer restarted"
}

cmd_status() {
    echo "=== Timer Status ==="
    sudo systemctl status "$TIMER_NAME" --no-pager || true
    echo ""
    echo "=== Service Status ==="
    sudo systemctl status "$SERVICE_NAME" --no-pager || true
    echo ""
    echo "=== Timer Schedule ==="
    sudo systemctl list-timers "$TIMER_NAME" --no-pager || true
    echo ""
    echo "=== Tmux Session Status ==="
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "Tmux session '$SESSION_NAME' is running"
        tmux list-windows -t "$SESSION_NAME" 2>/dev/null || true
    else
        echo "Tmux session '$SESSION_NAME' is not running"
    fi
}

cmd_logs() {
    echo "=== Recent Service Logs (journalctl) ==="
    sudo journalctl -u "$SERVICE_NAME" --no-pager -n 50 || true
    echo ""
    echo "=== Recent File Logs ==="
    if [[ -f "$LOG_FILE" ]]; then
        tail -n 30 "$LOG_FILE"
    else
        echo "No log file found at $LOG_FILE"
    fi
}

cmd_run_now() {
    echo "Running monitoring service immediately..."
    sudo systemctl start "$SERVICE_NAME"
    echo "Service started. Use 'logs' command to check results."
}

cmd_attach() {
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "Attaching to monitoring session '$SESSION_NAME'"
        echo "Use Ctrl+B then D to detach without stopping the session"
        tmux attach-session -t "$SESSION_NAME"
    else
        echo "Monitoring session '$SESSION_NAME' is not running"
        echo "Run 'run-now' to start the service first"
    fi
}

cmd_clean() {
    echo "Cleaning up monitoring service..."
    
    # Stop timer
    sudo systemctl stop "$TIMER_NAME" 2>/dev/null || true
    
    # Kill tmux session
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "Killing tmux session '$SESSION_NAME'"
        tmux kill-session -t "$SESSION_NAME"
    fi
    
    # Clean old logs
    if [[ -f "$LOG_FILE" ]]; then
        echo "Archiving current log file"
        mv "$LOG_FILE" "${LOG_FILE}.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Remove lock file
    if [[ -f "/home/clauderun/Tmux-Orchestrator/logs/queue_monitor.lock" ]]; then
        echo "Removing lock file"
        rm -f "/home/clauderun/Tmux-Orchestrator/logs/queue_monitor.lock"
    fi
    
    echo "Cleanup completed"
}

# Main command handling
case "${1:-}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    run-now)
        cmd_run_now
        ;;
    attach)
        cmd_attach
        ;;
    clean)
        cmd_clean
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
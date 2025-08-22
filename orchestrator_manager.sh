#!/bin/bash
# Tmux Orchestrator Manager CLI
# Provides centralized control for all orchestrator components

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CONFIG="$SCRIPT_DIR/orchestrator_config.yaml"
LOG_DIR="$SCRIPT_DIR/logs"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function print_status() {
    echo -e "${BLUE}[STATUS]${NC} $1"
}

function print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

function print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

function print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

function check_config() {
    if [ ! -f "$CONFIG" ]; then
        print_error "Configuration file not found: $CONFIG"
        print_warning "Please create orchestrator_config.yaml first"
        exit 1
    fi
}

function start() {
    print_status "Starting Tmux Orchestrator components..."
    check_config
    
    # Start event bus and state updater first (core infrastructure)
    print_status "Starting state updater..."
    nohup python3 "$SCRIPT_DIR/state_updater.py" > "$LOG_DIR/state_updater.out" 2>&1 &
    echo $! > "$LOG_DIR/state_updater.pid"
    sleep 2
    
    # Start compliance monitor
    print_status "Starting compliance monitor..."
    nohup python3 "$SCRIPT_DIR/monitoring/compliance_monitor.py" > "$LOG_DIR/compliance_monitor.out" 2>&1 &
    echo $! > "$LOG_DIR/compliance_monitor.pid"
    
    # Start credit monitor if it exists
    if [ -f "$SCRIPT_DIR/credit_management/credit_monitor_v2.py" ]; then
        print_status "Starting credit monitor v2..."
        nohup python3 "$SCRIPT_DIR/credit_management/credit_monitor_v2.py" > "$LOG_DIR/credit_monitor.out" 2>&1 &
        echo $! > "$LOG_DIR/credit_monitor.pid"
    elif [ -f "$SCRIPT_DIR/credit_management/credit_monitor.py" ]; then
        print_status "Starting credit monitor..."
        nohup python3 "$SCRIPT_DIR/credit_management/credit_monitor.py" > "$LOG_DIR/credit_monitor.out" 2>&1 &
        echo $! > "$LOG_DIR/credit_monitor.pid"
    fi
    
    # Start git workflow monitor if it exists
    if [ -f "$SCRIPT_DIR/monitoring/monitor_git_workflow.py" ]; then
        print_status "Starting git workflow monitor..."
        nohup python3 "$SCRIPT_DIR/monitoring/monitor_git_workflow.py" > "$LOG_DIR/git_monitor.out" 2>&1 &
        echo $! > "$LOG_DIR/git_monitor.pid"
    fi
    
    # Start scheduler if needed
    if [ -f "$SCRIPT_DIR/scheduler.py" ]; then
        print_status "Starting scheduler..."
        nohup python3 "$SCRIPT_DIR/scheduler.py" --daemon > "$LOG_DIR/scheduler.out" 2>&1 &
        echo $! > "$LOG_DIR/scheduler.pid"
    fi
    
    print_success "All components started. Check logs in $LOG_DIR for details."
}

function stop() {
    print_status "Stopping Tmux Orchestrator components..."
    
    # Stop all processes gracefully
    for pidfile in "$LOG_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            PID=$(cat "$pidfile")
            PROCESS_NAME=$(basename "$pidfile" .pid)
            if ps -p $PID > /dev/null 2>&1; then
                print_status "Stopping $PROCESS_NAME (PID: $PID)..."
                kill -TERM $PID 2>/dev/null
                
                # Wait for graceful shutdown
                for i in {1..10}; do
                    if ! ps -p $PID > /dev/null 2>&1; then
                        break
                    fi
                    sleep 1
                done
                
                # Force kill if still running
                if ps -p $PID > /dev/null 2>&1; then
                    print_warning "Force killing $PROCESS_NAME..."
                    kill -9 $PID 2>/dev/null
                fi
            fi
            rm -f "$pidfile"
        fi
    done
    
    # Additional cleanup for any orphaned processes
    print_status "Cleaning up any orphaned processes..."
    pkill -f "monitor" 2>/dev/null || true
    pkill -f "compliance" 2>/dev/null || true
    pkill -f "credit_monitor" 2>/dev/null || true
    pkill -f "state_updater" 2>/dev/null || true
    pkill -f "scheduler" 2>/dev/null || true
    
    print_success "All components stopped."
}

function status() {
    print_status "Tmux Orchestrator component status:"
    echo
    
    # Check each component
    for pidfile in "$LOG_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            PID=$(cat "$pidfile")
            PROCESS_NAME=$(basename "$pidfile" .pid)
            if ps -p $PID > /dev/null 2>&1; then
                print_success "$PROCESS_NAME is running (PID: $PID)"
            else
                print_error "$PROCESS_NAME is not running (stale PID file)"
            fi
        fi
    done
    
    # Check for event logs
    if [ -d "$LOG_DIR/events" ]; then
        EVENT_COUNT=$(find "$LOG_DIR/events" -name "*.jsonl" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}')
        print_status "Total events logged: ${EVENT_COUNT:-0}"
    fi
    
    # Check for violations
    if [ -d "$LOG_DIR/communications" ]; then
        VIOLATION_COUNT=$(find "$LOG_DIR/communications" -name "violations.jsonl" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}')
        if [ "${VIOLATION_COUNT:-0}" -gt 0 ]; then
            print_warning "Violations detected: $VIOLATION_COUNT"
        fi
    fi
}

function restart() {
    stop
    sleep 2
    start
}

function logs() {
    # Show tail of all log files
    print_status "Recent logs from all components:"
    echo
    
    for logfile in "$LOG_DIR"/*.out; do
        if [ -f "$logfile" ]; then
            COMPONENT=$(basename "$logfile" .out)
            echo -e "${BLUE}=== $COMPONENT ===${NC}"
            tail -n 20 "$logfile"
            echo
        fi
    done
}

function clear_queues() {
    print_status "Clearing message queues and resetting state..."
    
    # Clear SQLite queue if exists
    if [ -f "$SCRIPT_DIR/task_queue.db" ]; then
        sqlite3 "$SCRIPT_DIR/task_queue.db" "DELETE FROM tasks;" 2>/dev/null || true
        print_success "Cleared task queue"
    fi
    
    # Clear event logs for fresh start (optional)
    read -p "Clear all event logs? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$LOG_DIR/events"/*
        rm -rf "$LOG_DIR/communications"/*
        print_success "Cleared event logs"
    fi
}

function help() {
    echo "Tmux Orchestrator Manager"
    echo "Usage: $0 {start|stop|restart|status|logs|clear-queues|help}"
    echo
    echo "Commands:"
    echo "  start        - Start all orchestrator components"
    echo "  stop         - Stop all orchestrator components"
    echo "  restart      - Restart all components"
    echo "  status       - Show component status"
    echo "  logs         - Show recent logs from all components"
    echo "  clear-queues - Clear message queues and optionally reset logs"
    echo "  help         - Show this help message"
}

# Main command handling
case "${1:-help}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    clear-queues)
        clear_queues
        ;;
    help|*)
        help
        ;;
esac
#!/bin/bash

# Send message to Claude agent in tmux window
# Now with TmuxManager integration and smart /compact handling!
# Usage: send-claude-message.sh <session:window> <message> [project_id]

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window> <message> [project_id]"
    echo "Example: $0 agentic-seek:3 'Hello Claude!' default"
    echo "Set USE_TMUX_MANAGER=1 to use centralized TmuxManager"
    exit 1
fi

WINDOW="$1"
shift  # Remove first argument
MESSAGE="$1"
shift  # Remove message
PROJECT_ID="${1:-default}"  # Optional project_id for socket isolation

# Feature flag: Use TmuxManager if enabled, otherwise fallback to raw tmux
if [ "$USE_TMUX_MANAGER" = "1" ]; then
    echo "🔧 Using TmuxManager for centralized tmux operations"
    
    # Use TmuxManager with socket isolation
    python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from tmux_utils import TmuxManager, TmuxSocketManager
    
    # Set up socket isolation for project
    project_id = '$PROJECT_ID'
    if project_id == 'default' or project_id == '':
        # Use default tmux socket for default project
        tmux_manager = TmuxManager()
    else:
        # Use isolated socket for specific project
        socket_mgr = TmuxSocketManager()
        socket_path = socket_mgr.get_project_socket(project_id)
        tmux_manager = TmuxManager(socket_path=socket_path)
    
    # Send message with validation
    success = tmux_manager.send_message('$WINDOW', '''$MESSAGE''', validate=True)
    
    if success:
        print(f'✅ Message sent to $WINDOW via TmuxManager')
        sys.exit(0)
    else:
        print(f'❌ TmuxManager failed to send message to $WINDOW')
        sys.exit(1)
        
except Exception as e:
    print(f'❌ TmuxManager error: {e}')
    sys.exit(1)
" 
    TMUX_MANAGER_RESULT=$?
    
    # If TmuxManager succeeded, exit
    if [ $TMUX_MANAGER_RESULT -eq 0 ]; then
        exit 0
    fi
    
    # If TmuxManager failed, log and fall back to raw tmux
    echo "⚠️  TmuxManager failed, falling back to raw tmux for safety"
fi

# Legacy/Fallback: Raw tmux operations (original implementation)
echo "🔧 Using raw tmux operations"

# Self-referential detection - prevent agents from messaging themselves
CURRENT_WINDOW=$(tmux display-message -p "#{session_name}:#{window_index}" 2>/dev/null || echo "")
if [ "$CURRENT_WINDOW" = "$WINDOW" ]; then
    echo "WARNING: Attempting to send message to self ($WINDOW). Skipping to prevent feedback loop."
    exit 0
fi

# Enhanced validation - check if target session exists and is alive
if ! tmux has-session -t "$WINDOW" 2>/dev/null; then
    echo "ERROR: Target session/window $WINDOW does not exist. Preventing phantom message routing."
    exit 1
fi

# Check if target process is alive
TARGET_PID=$(tmux display-message -p -t "$WINDOW" '#{pid}' 2>/dev/null)
if [ -z "$TARGET_PID" ]; then
    echo "ERROR: Cannot get PID for target $WINDOW. Target may be dead."
    exit 1
fi

if ! ps -p "$TARGET_PID" > /dev/null 2>&1; then
    echo "ERROR: Target process $TARGET_PID is dead. Preventing message to phantom session."
    exit 1
fi

# Check if message contains /compact
if echo "$MESSAGE" | grep -q "/compact"; then
    # Extract message without /compact
    MESSAGE_WITHOUT_COMPACT=$(echo "$MESSAGE" | sed 's|/compact||g' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//')
    
    # Send the main message if it's not empty
    if [ -n "$MESSAGE_WITHOUT_COMPACT" ] && [ "$MESSAGE_WITHOUT_COMPACT" != " " ]; then
        tmux send-keys -t "$WINDOW" "$MESSAGE_WITHOUT_COMPACT"
        sleep 0.5
        tmux send-keys -t "$WINDOW" Enter
        echo "Message sent to $WINDOW: $MESSAGE_WITHOUT_COMPACT"
        
        # Wait for the message to be processed
        sleep 2
    fi
    
    # Now send /compact as a separate command
    tmux send-keys -t "$WINDOW" "/compact"
    sleep 0.5
    tmux send-keys -t "$WINDOW" Enter
    echo "Compact command sent separately to $WINDOW"
else
    # Normal message sending
    tmux send-keys -t "$WINDOW" "$MESSAGE"
    sleep 0.5
    tmux send-keys -t "$WINDOW" Enter
    echo "Message sent to $WINDOW: $MESSAGE"
fi
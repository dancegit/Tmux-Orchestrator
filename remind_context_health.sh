#!/bin/bash
# Remind agents to check their context health and compact if needed

# Get session name from argument or default
SESSION="${1:-}"
if [ -z "$SESSION" ]; then
    echo "Usage: $0 <session-name> [window-numbers]"
    echo "Example: $0 myproject-impl '1 2 3 4'"
    exit 1
fi

# Get window numbers or default to all Claude windows
WINDOWS="${2:-}"
if [ -z "$WINDOWS" ]; then
    # Find all windows that likely have Claude agents
    WINDOWS=$(tmux list-windows -t "$SESSION" -F "#{window_index} #{window_name}" | \
              grep -E "(Claude|Developer|Tester|PM|Project|Researcher|TestRunner|LogTracker|DevOps)" | \
              awk '{print $1}' | tr '\n' ' ')
fi

echo "Reminding agents in session $SESSION windows: $WINDOWS"

# Context health reminder message
REMINDER="🧠 Context Health Check:

If you've been working for 2+ hours or feeling confused:
1. Create checkpoint: ROLE_CHECKPOINT_\$(date +%Y%m%d_%H%M).md
2. Run: /compact
3. Reload: /context-prime (or read CLAUDE.md + checkpoint)
4. Continue from checkpoint

Reply 'ACK' if context is healthy, or 'COMPACTING' if you need to compact."

# Send reminder to each window
for WINDOW in $WINDOWS; do
    echo "Sending reminder to $SESSION:$WINDOW"
    ./send-claude-message.sh "$SESSION:$WINDOW" "$REMINDER"
done

echo ""
echo "✅ Context health reminders sent!"
echo ""
echo "Check responses with:"
echo "  tmux capture-pane -t $SESSION:[window] -p | tail -20"
echo ""
echo "If an agent is compacting, wait 2-3 minutes for them to reload context."
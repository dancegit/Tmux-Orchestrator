#!/bin/bash
# Help an agent with low context to compact and recover

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <session:window> [handoff-file]"
    echo "Example: $0 myproject-impl:3"
    echo "         $0 myproject-impl:3 TESTRUNNER_HANDOFF.md"
    exit 1
fi

TARGET="$1"
HANDOFF_FILE="${2:-}"

echo "🧠 Helping agent at $TARGET to compact and recover..."

# Step 1: Prompt agent to create handoff if they haven't
if [ -z "$HANDOFF_FILE" ]; then
    echo "Step 1: Asking agent to create handoff document..."
    ./send-claude-message.sh "$TARGET" "Before we clear your context, please create a handoff document:

cat > \$(echo \$ROLE)_HANDOFF_\$(date +%Y%m%d_%H%M).md << 'EOF'
## Context Handoff
- Current task: [what you're working on]
- Branch: \$(git branch --show-current)
- Recent work: [what you completed]
- Next steps: [specific actions to continue]
- Key context: [important things to remember]
EOF

Then reply 'HANDOFF CREATED' when done."
    
    echo "Waiting for handoff creation (20 seconds)..."
    sleep 20
fi

# Step 2: Ask agent to type /compact
echo ""
echo "Step 2: Asking agent to type /compact..."
./send-claude-message.sh "$TARGET" "Now please type the following command and press Enter to clear your context:

/compact

(Just type those 8 characters and hit Enter - this will clear your conversation history while keeping your session active)

Reply 'COMPACT DONE' when complete."

echo "Waiting for compact to complete (10 seconds)..."
sleep 10

# Step 3: Guide reload process
echo ""
echo "Step 3: Guiding context reload..."

if [ -n "$HANDOFF_FILE" ]; then
    RELOAD_MSG="Excellent! Now reload your context:

1. Try: /context-prime
   (If not available, continue to step 2)

2. Read essential files:
   - Read CLAUDE.md
   - Read $HANDOFF_FILE
   - Read README.md (if exists)

3. Check current state:
   - git status
   - git log --oneline -5
   - pwd

4. Continue from the 'Next steps' section in $HANDOFF_FILE

Reply 'CONTEXT RELOADED' when ready to continue."
else
    RELOAD_MSG="Excellent! Now reload your context:

1. Try: /context-prime
   (If not available, continue to step 2)

2. Read essential files:
   - Read CLAUDE.md
   - Read your HANDOFF document (find it with: ls *HANDOFF*.md)
   - Read README.md (if exists)

3. Check current state:
   - git status
   - git log --oneline -5
   - pwd

4. Continue from the 'Next steps' in your handoff document

Reply 'CONTEXT RELOADED' when ready to continue."
fi

./send-claude-message.sh "$TARGET" "$RELOAD_MSG"

echo ""
echo "✅ Recovery process initiated!"
echo ""
echo "Monitor the agent's response with:"
echo "  tmux capture-pane -t $TARGET -p | tail -30"
echo ""
echo "The agent should be back to work within 2-3 minutes."
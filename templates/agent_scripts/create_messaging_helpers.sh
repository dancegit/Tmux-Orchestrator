#!/bin/bash
# Script to create messaging helper scripts in an existing agent worktree
# Usage: ./create_messaging_helpers.sh <session_name> <my_role>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session_name> <my_role>"
    echo "Example: $0 orchestrator-mobile-ux-impl-cd43aa77 Developer"
    exit 1
fi

SESSION_NAME="$1"
MY_ROLE="$2"
ORCHESTRATOR_PATH="/home/clauderun/Tmux-Orchestrator"

# Create scripts directory
mkdir -p scripts

# Common roles to create scripts for
COMMON_ROLES=("Orchestrator" "Project-Manager" "Developer" "Tester" "TestRunner" "Researcher" "DevOps" "SysAdmin" "SecurityOps" "NetworkOps" "MonitoringOps" "DatabaseOps")

echo "🔧 Creating messaging helper scripts for $MY_ROLE..."

# Create individual messaging scripts for each role
for TARGET_ROLE in "${COMMON_ROLES[@]}"; do
    if [ "$TARGET_ROLE" = "$MY_ROLE" ]; then
        continue  # Skip self-messaging script
    fi
    
    SCRIPT_NAME="msg_$(echo "$TARGET_ROLE" | tr '[:upper:]' '[:lower:]' | sed 's/-/_/g').sh"
    
    cat > "scripts/$SCRIPT_NAME" << EOF
#!/bin/bash
# Quick message to $TARGET_ROLE
# Usage: ./msg_$(echo "$TARGET_ROLE" | tr '[:upper:]' '[:lower:]' | sed 's/-/_/g').sh "Your message here"

if [ \$# -lt 1 ]; then
    echo "Usage: \$0 <message>"
    echo "Example: \$0 'Status update: Feature completed'"
    exit 1
fi

MESSAGE="\$*"
ORCHESTRATOR_PATH="$ORCHESTRATOR_PATH"

# Use the smart messaging system
"\$ORCHESTRATOR_PATH/monitoring/smart_send_message.sh" "$SESSION_NAME:$TARGET_ROLE" "\$MESSAGE"
EOF
    
    chmod +x "scripts/$SCRIPT_NAME"
    echo "  ✅ Created scripts/$SCRIPT_NAME"
done

# Create general messaging script
cat > "scripts/msg.sh" << EOF
#!/bin/bash
# General messaging script
# Usage: ./msg.sh <role_name> "Your message"
# Examples:
#   ./msg.sh Orchestrator "Task completed"
#   ./msg.sh Developer "Need clarification on requirements"

if [ \$# -lt 2 ]; then
    echo "Usage: \$0 <role_name> <message>"
    echo "Available roles: Orchestrator, Project-Manager, Developer, Tester, TestRunner, etc."
    echo "Examples:"
    echo "  \$0 Orchestrator 'Task completed successfully'"
    echo "  \$0 Developer 'Need input on API design'"
    exit 1
fi

ROLE="\$1"
shift
MESSAGE="\$*"
ORCHESTRATOR_PATH="$ORCHESTRATOR_PATH"

# Use the smart messaging system
"\$ORCHESTRATOR_PATH/monitoring/smart_send_message.sh" "$SESSION_NAME:\$ROLE" "\$MESSAGE"
EOF

chmod +x "scripts/msg.sh"
echo "  ✅ Created scripts/msg.sh (general messaging)"

# Create team list script
cat > "scripts/list_team.sh" << EOF
#!/bin/bash
# List all team members (tmux windows) in this session
echo "🏢 Team members in session $SESSION_NAME:"
tmux list-windows -t "$SESSION_NAME" -F '  {window_index}: {window_name}'
EOF

chmod +x "scripts/list_team.sh"
echo "  ✅ Created scripts/list_team.sh (team directory)"

echo ""
echo "🎉 Messaging helper scripts created successfully!"
echo ""
echo "Usage examples:"
echo "  ./scripts/msg_orchestrator.sh 'Task completed successfully'"
echo "  ./scripts/msg_developer.sh 'Need code review on authentication'"
echo "  ./scripts/msg.sh TestRunner 'Please run the new test suite'"
echo "  ./scripts/list_team.sh  # Show all team members"
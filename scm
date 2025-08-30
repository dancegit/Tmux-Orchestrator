#\!/bin/bash
# Smart Claude Messaging (scm) - Convenient wrapper for smart messaging
# Usage: scm <session:role_name> <message>
# Examples:
#   scm my-session:TestRunner "Run the tests please"
#   scm my-session:Developer "Status update needed"
#   scm my-session:Project-Manager "Review required"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Call the smart send message script
exec "$SCRIPT_DIR/monitoring/smart_send_message.sh" "$@"
EOF < /dev/null

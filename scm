#!/bin/bash
# Shortcut for send-claude-message.sh with monitoring
# Usage: scm <target> <message>

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
"$SCRIPT_DIR/send-monitored-message.sh" "$@"
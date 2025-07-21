#!/bin/bash
# Wrapper to use monitored messaging
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
"$SCRIPT_DIR/monitoring/monitored_send_message.sh" "$@"

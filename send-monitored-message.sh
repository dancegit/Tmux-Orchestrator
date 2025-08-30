#!/bin/bash
# Wrapper to use smart monitored messaging with window name resolution
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Use the smart send message script for window name resolution
"$SCRIPT_DIR/monitoring/smart_send_message.sh" "$@"

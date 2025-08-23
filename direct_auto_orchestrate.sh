#!/bin/bash
# Direct wrapper to ensure auto_orchestrate.py is called without nested uv
# This bypasses any Python caching issues

# Get the absolute path to auto_orchestrate.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_ORCHESTRATE="$SCRIPT_DIR/auto_orchestrate.py"

# Make sure it's executable
chmod +x "$AUTO_ORCHESTRATE"

# Call it directly (the shebang will handle uv)
exec "$AUTO_ORCHESTRATE" "$@"
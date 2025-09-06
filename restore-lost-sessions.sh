#!/bin/bash
# Convenient script to restore lost tmux sessions

echo "🔄 Session Restoration Tool"
echo "=========================="
echo

# Check for lost sessions first
echo "1. Checking for lost sessions..."
python3 session_restoration_system.py --check-only

echo
read -p "Do you want to restore the lost sessions? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "2. Restoring lost sessions..."
    python3 session_restoration_system.py
    
    if [ $? -eq 0 ]; then
        echo "✅ Session restoration completed successfully"
    else
        echo "❌ Session restoration failed or no sessions to restore"
    fi
else
    echo "Restoration cancelled"
fi

echo
echo "To check manually: python3 session_restoration_system.py --check-only"
echo "To restore all: python3 session_restoration_system.py"
#!/bin/bash
# Tmux Orchestrator Setup Script
# This script helps set up the Tmux Orchestrator for your environment

echo "=== Tmux Orchestrator Setup ==="
echo

# Check if config.local.sh exists
if [ ! -f "config.local.sh" ]; then
    echo "Creating config.local.sh from template..."
    cp config.sh config.local.sh
    echo "✓ Created config.local.sh"
    echo
fi

# Source the configuration
source config.local.sh

# Ask user about their projects directory
echo "Current projects directory: $PROJECTS_DIR"
read -p "Is this correct? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter your projects directory path: " new_projects_dir
    # Expand tilde if present
    new_projects_dir="${new_projects_dir/#\~/$HOME}"
    sed -i.bak "s|export PROJECTS_DIR=.*|export PROJECTS_DIR=\"$new_projects_dir\"|" config.local.sh
    export PROJECTS_DIR="$new_projects_dir"
    echo "✓ Updated projects directory to: $PROJECTS_DIR"
fi

# Create required directories
echo
echo "Creating required directories..."
mkdir -p "$TMO_REGISTRY/logs"
mkdir -p "$TMO_REGISTRY/notes"
echo "✓ Created registry directories"

# Check for required dependencies
echo
echo "Checking dependencies..."

# Check tmux
if command -v tmux >/dev/null 2>&1; then
    echo "✓ tmux is installed ($(tmux -V))"
else
    echo "✗ tmux is not installed. Please install tmux to use Tmux Orchestrator."
fi

# Check Python
if command -v python3 >/dev/null 2>&1; then
    echo "✓ Python 3 is installed ($(python3 --version))"
else
    echo "✗ Python 3 is not installed. Some features may not work."
fi

# Check if running on Linux or macOS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "✓ Running on Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "✓ Running on macOS"
else
    echo "⚠ Unknown operating system: $OSTYPE"
fi

# Make scripts executable
echo
echo "Making scripts executable..."
chmod +x *.sh
chmod +x *.py 2>/dev/null || true
echo "✓ Scripts are now executable"

echo
echo "=== Setup Complete ==="
echo
echo "To use Tmux Orchestrator:"
echo "1. Start tmux: tmux new -s orchestrator"
echo "2. Run: ./schedule_with_note.sh 5 'Start orchestrating'"
echo "3. Use ./send-claude-message.sh to communicate with agents"
echo
echo "Remember to update CLAUDE.md with your specific paths if needed."
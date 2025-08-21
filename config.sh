#!/bin/bash
# Tmux Orchestrator Configuration File
# This file contains environment-specific settings
# Copy this to config.local.sh and modify for your environment

# Default project directory where your coding projects are stored
# Change this to match your local setup (e.g., ~/Coding, ~/Development, ~/projects)
export PROJECTS_DIR="${PROJECTS_DIR:-$HOME/projects}"

# Tmux Orchestrator home directory
export TMO_HOME="${TMO_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

# Registry directory for logs and session data
export TMO_REGISTRY="${TMO_REGISTRY:-$TMO_HOME/registry}"

# Default tmux session name for the orchestrator
export TMO_DEFAULT_SESSION="${TMO_DEFAULT_SESSION:-tmux-orc}"

# Default window index for the orchestrator
export TMO_DEFAULT_WINDOW="${TMO_DEFAULT_WINDOW:-0}"

# Python interpreter to use
export PYTHON_CMD="${PYTHON_CMD:-python3}"

# Enable TmuxManager by default for centralized tmux operations (PHASE 1 MIGRATION)
export USE_TMUX_MANAGER="${USE_TMUX_MANAGER:-1}"

# Create necessary directories if they don't exist
mkdir -p "$TMO_REGISTRY/logs"
mkdir -p "$TMO_REGISTRY/notes"

# Function to get project path
get_project_path() {
    local project_name="$1"
    echo "$PROJECTS_DIR/$project_name"
}

# Function to log messages
tmo_log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$TMO_REGISTRY/orchestrator.log"
}
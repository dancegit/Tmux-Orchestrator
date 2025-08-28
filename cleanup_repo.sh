#!/bin/bash
set -e

echo "🧹 Starting comprehensive repository cleanup..."

# Categories of files to remove:
# 1. Session states and project data
# 2. Database files (sensitive data)
# 3. Log files 
# 4. Emergency backups
# 5. Registry/project metadata
# 6. Temporary and generated files

echo "📋 Files to be removed from git history and current state:"

# Create .gitignore for future protection
echo "📝 Creating comprehensive .gitignore..."
cat > .gitignore << 'EOF'
# Database files
*.db
*.db-shm 
*.db-wal
task_queue.db*
scheduler.db*
session_state.db*
orchestration_tracking.db*

# Session and state data
session_states/
sessions/
registry/

# Log files
*.log
logs/
*.out
*.pid

# Temporary and backup files
emergency_backup/
*_backup_*/
*.tar.gz

# Generated files
locks/
*.lock
*_process.info

# Project-specific sensitive data
all_projects_batch*.log
*_orchestrate.log
debug_*.log
test-output*.log

# Config files with potential secrets
config.local.sh

# Temporary scripts
temp_*.py
fix_*.py
mark_project_*.py
reset_project_*.py
repair_*.py
EOF

# Remove files from current working directory
echo "🗑️ Removing files from current state..."

# Session and project data
rm -rf session_states/ || true
rm -rf sessions/ || true
rm -rf registry/ || true
rm -rf emergency_backup/ || true

# Database files
rm -f *.db *.db-shm *.db-wal || true
rm -f task_queue.db* scheduler.db* session_state.db* tmux_scheduler.db || true

# Log files
rm -rf logs/ || true
rm -f *.log || true
rm -f *.out || true
rm -f *.pid || true

# Lock files
rm -rf locks/ || true

# Temporary files
rm -f all_projects_batch*.log || true
rm -f *_orchestrate.log || true
rm -f debug_*.log || true
rm -f test-output*.log || true
rm -f scheduler_*.log || true
rm -f queue_daemon*.log || true
rm -f enhanced_*.log || true
rm -f final_*.log || true
rm -f fixed_*.log || true
rm -f new_*.log || true
rm -f persistent_*.log || true
rm -f mcp_*.log || true

# Temporary fix scripts (keep main utilities)
rm -f temp_*.py || true
rm -f mark_project_*.py || true
rm -f reset_project_*.py || true
rm -f repair_*.py || true
rm -f fix_*.py || true

# Generated config
rm -f config.local.sh || true

# Signals directory if empty or temporary
if [ -d "signals" ]; then
    if [ -z "$(ls -A signals)" ]; then
        rm -rf signals/ || true
    fi
fi

echo "✅ Removed files from current state"

# Add .gitignore to git
git add .gitignore

echo "🎯 Files cleaned from current repository state"
echo "📝 .gitignore created to prevent future commits of sensitive files"
echo ""
echo "⚠️  IMPORTANT: This only cleans the current state."
echo "   To remove from git history, you'll need to use git filter commands"
echo "   or create a fresh repository from clean state."
echo ""
echo "🔧 Next steps:"
echo "   1. Review remaining files"
echo "   2. Commit this cleanup"
echo "   3. Consider creating fresh repo if git history cleanup is critical"
#!/bin/bash
# Cleanup script to remove unused and duplicate files

echo "=== Tmux-Orchestrator Cleanup Script ==="
echo "This will remove unused duplicate/test/backup files"
echo ""

# Create a trash directory with timestamp
TRASH_DIR="$HOME/.trash/tmux-orchestrator-cleanup-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TRASH_DIR"
echo "Moving files to: $TRASH_DIR"
echo ""

# Move unused Python files
echo "Moving unused Python files..."
for file in scheduler_enhanced.py scheduler_fixed.py scheduler_backup_*.py enhanced_notifications.py cleanup_old_tasks.py test_*.py; do
    if [ -f "$file" ]; then
        echo "  - $file"
        mv "$file" "$TRASH_DIR/"
    fi
done

# Move unused shell scripts
echo -e "\nMoving unused shell scripts..."
for file in send-claude-message-clean.sh clean_phantoms.sh test_*.sh; do
    if [ -f "$file" ]; then
        echo "  - $file"
        mv "$file" "$TRASH_DIR/"
    fi
done

# Move backup files
echo -e "\nMoving backup files..."
for file in *.backup *.backup_* *.bak *.old *.tmp; do
    if [ -f "$file" ]; then
        echo "  - $file"
        mv "$file" "$TRASH_DIR/"
    fi
done

# Move specific unused files identified
echo -e "\nMoving other identified unused files..."
for file in scheduler_idempotent_patch.py scheduler_health_check.py claude_startup_fix.py fix_tmux_enter_issue.py investigate_flooding.py start_scheduler_safe.py tmux_session_manager.py; do
    if [ -f "$file" ]; then
        echo "  - $file"
        mv "$file" "$TRASH_DIR/"
    fi
done

# Move old log/text files that aren't needed
echo -e "\nMoving old logs and temporary files..."
for file in scheduler_errors.txt scheduler_lifecycle.txt scheduler_logs_tail.txt scheduler_processes.txt systemd_status.txt pending_tasks.txt scheduled_tasks.txt lock_files.txt journalctl_queue_service.txt; do
    if [ -f "$file" ]; then
        echo "  - $file"
        mv "$file" "$TRASH_DIR/"
    fi
done

# Move old patches
echo -e "\nMoving old patch files..."
for file in hub_spoke_enforcement.patch; do
    if [ -f "$file" ]; then
        echo "  - $file"
        mv "$file" "$TRASH_DIR/"
    fi
done

# Move old registry backups
echo -e "\nMoving old registry backups..."
for file in registry.bak registry_backup_*.tar.gz; do
    if [ -f "$file" ]; then
        echo "  - $file"
        mv "$file" "$TRASH_DIR/"
    fi
done

# Database backups
echo -e "\nMoving old database backups..."
for file in task_queue.db.backup_* task_queue.db.bak*; do
    if [ -f "$file" ]; then
        echo "  - $file"
        mv "$file" "$TRASH_DIR/"
    fi
done

echo -e "\n=== Cleanup Complete ==="
echo "Files moved to: $TRASH_DIR"
echo "You can permanently delete with: rm -rf $TRASH_DIR"
echo ""
echo "Remaining Python files:"
ls -1 *.py | wc -l
echo ""
echo "Remaining Shell scripts:"
ls -1 *.sh | wc -l
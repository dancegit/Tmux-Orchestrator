#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Git Sync Coordinator for Tmux Orchestrator
Provides event-driven synchronization between agent worktrees with conflict handling
"""

import os
import sys
import time
import subprocess
import json
import logging
from pathlib import Path
from datetime import datetime
import threading
import queue

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync_coordinator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GitSyncCoordinator:
    def __init__(self, project_name, registry_dir=None):
        self.project_name = project_name
        
        # Determine registry directory
        if registry_dir:
            self.registry_dir = Path(registry_dir)
        else:
            # Try to find from current directory structure
            tmux_orchestrator_path = Path(__file__).parent
            self.registry_dir = tmux_orchestrator_path / 'registry' / 'projects' / project_name
            
        self.worktrees_dir = self.registry_dir / 'worktrees'
        self.notification_file = Path('/tmp') / f'sync_notify_{project_name}'
        self.dashboard_file = self.registry_dir / 'sync_dashboard.txt'
        self.sync_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # Create dashboard file
        self.dashboard_file.parent.mkdir(parents=True, exist_ok=True)
        self.update_dashboard(f"Sync Coordinator started for {project_name}")
        
    def install_hooks(self, worktree_path):
        """Install git hooks for automatic sync notification"""
        worktree_path = Path(worktree_path)
        hooks_dir = worktree_path / '.git' / 'hooks'
        
        # Create hooks directory if it doesn't exist
        hooks_dir.mkdir(parents=True, exist_ok=True)
        
        # Post-commit hook
        post_commit_hook = hooks_dir / 'post-commit'
        hook_content = f"""#!/bin/bash
# Tmux Orchestrator Sync Hook
touch {self.notification_file}
echo "$(date): Commit in $(pwd)" >> {self.notification_file}
"""
        
        post_commit_hook.write_text(hook_content)
        post_commit_hook.chmod(0o755)
        
        # Post-merge hook (for when agents pull changes)
        post_merge_hook = hooks_dir / 'post-merge'
        post_merge_hook.write_text(hook_content)
        post_merge_hook.chmod(0o755)
        
        logger.info(f"Installed hooks in {worktree_path}")
        
    def update_dashboard(self, message, level="INFO"):
        """Update the sync dashboard with status information"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}\n"
        
        with open(self.dashboard_file, 'a') as f:
            f.write(entry)
            
        # Keep only last 1000 lines
        if self.dashboard_file.stat().st_size > 100000:  # ~100KB
            lines = self.dashboard_file.read_text().splitlines()
            self.dashboard_file.write_text('\n'.join(lines[-1000:]) + '\n')
            
    def get_current_branch(self, worktree_path):
        """Get the current branch of a worktree"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"Error getting branch for {worktree_path}: {e}")
        return None
        
    def get_latest_commit(self, worktree_path):
        """Get the latest commit hash and message"""
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--oneline'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"Error getting commit for {worktree_path}: {e}")
        return None
        
    def perform_sync(self, worktree_name, worktree_path):
        """Perform synchronization for a specific worktree"""
        worktree_path = Path(worktree_path)
        
        try:
            # Get current state
            current_branch = self.get_current_branch(worktree_path)
            if not current_branch:
                self.update_dashboard(f"{worktree_name}: Unable to determine branch", "ERROR")
                return
                
            # Fetch latest from origin
            self.update_dashboard(f"{worktree_name}: Fetching from origin...")
            fetch_result = subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            
            if fetch_result.returncode != 0:
                self.update_dashboard(f"{worktree_name}: Fetch failed - {fetch_result.stderr}", "ERROR")
                return
                
            # Check if we're behind origin/main
            behind_result = subprocess.run(
                ['git', 'rev-list', '--count', f'HEAD..origin/main'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            
            if behind_result.returncode == 0 and int(behind_result.stdout.strip()) > 0:
                commits_behind = behind_result.stdout.strip()
                self.update_dashboard(f"{worktree_name}: {commits_behind} commits behind origin/main")
                
                # Try to rebase or merge
                if current_branch == 'main':
                    # On main branch, just pull
                    pull_result = subprocess.run(
                        ['git', 'pull', 'origin', 'main'],
                        cwd=worktree_path,
                        capture_output=True,
                        text=True
                    )
                else:
                    # On feature branch, try to rebase
                    rebase_result = subprocess.run(
                        ['git', 'rebase', 'origin/main'],
                        cwd=worktree_path,
                        capture_output=True,
                        text=True
                    )
                    
                    if rebase_result.returncode != 0:
                        # Rebase failed, abort and log conflict
                        subprocess.run(['git', 'rebase', '--abort'], cwd=worktree_path)
                        
                        self.update_dashboard(
                            f"{worktree_name}: CONFLICT - Rebase failed on branch {current_branch}",
                            "WARNING"
                        )
                        
                        # Create conflict report
                        conflict_file = self.registry_dir / f'conflict_{worktree_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
                        conflict_file.write_text(f"""
Conflict Report for {worktree_name}
Time: {datetime.now()}
Branch: {current_branch}
Error: {rebase_result.stderr}

To resolve:
1. cd {worktree_path}
2. git rebase origin/main
3. Resolve conflicts
4. git rebase --continue
""")
                        
                        self.update_dashboard(f"{worktree_name}: Conflict report saved to {conflict_file.name}")
                        return
                        
                self.update_dashboard(f"{worktree_name}: Successfully synced with origin/main")
            else:
                # Check if we have local commits to push
                ahead_result = subprocess.run(
                    ['git', 'rev-list', '--count', f'origin/{current_branch}..HEAD'],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True
                )
                
                if ahead_result.returncode == 0 and int(ahead_result.stdout.strip()) > 0:
                    commits_ahead = ahead_result.stdout.strip()
                    self.update_dashboard(f"{worktree_name}: {commits_ahead} commits ahead - ready to push")
                else:
                    latest_commit = self.get_latest_commit(worktree_path)
                    self.update_dashboard(f"{worktree_name}: Up to date - {latest_commit}")
                    
        except Exception as e:
            logger.error(f"Sync error for {worktree_name}: {e}")
            self.update_dashboard(f"{worktree_name}: Sync error - {str(e)}", "ERROR")
            
    def sync_all_worktrees(self):
        """Synchronize all worktrees in the project"""
        if not self.worktrees_dir.exists():
            logger.error(f"Worktrees directory not found: {self.worktrees_dir}")
            return
            
        self.update_dashboard("Starting full synchronization...")
        
        for worktree in self.worktrees_dir.iterdir():
            if worktree.is_dir() and (worktree / '.git').exists():
                self.sync_queue.put((worktree.name, worktree))
                
    def process_sync_queue(self):
        """Process synchronization tasks from the queue"""
        while not self.stop_event.is_set():
            try:
                # Wait for sync task with timeout
                worktree_name, worktree_path = self.sync_queue.get(timeout=1)
                self.perform_sync(worktree_name, worktree_path)
                self.sync_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                
    def watch_for_notifications(self):
        """Watch for sync notifications from git hooks"""
        while not self.stop_event.is_set():
            if self.notification_file.exists():
                # Read and clear notification
                try:
                    notifications = self.notification_file.read_text()
                    self.notification_file.unlink()
                    
                    self.update_dashboard("Received sync notification - triggering sync")
                    self.sync_all_worktrees()
                    
                except Exception as e:
                    logger.error(f"Notification processing error: {e}")
                    
            time.sleep(1)  # Check every second
            
    def run(self):
        """Main coordinator loop"""
        logger.info(f"Starting Git Sync Coordinator for {self.project_name}")
        
        # Install hooks in all worktrees
        if self.worktrees_dir.exists():
            for worktree in self.worktrees_dir.iterdir():
                if worktree.is_dir() and (worktree / '.git').exists():
                    self.install_hooks(worktree)
                    
        # Start sync processing thread
        sync_thread = threading.Thread(target=self.process_sync_queue)
        sync_thread.start()
        
        # Initial sync
        self.sync_all_worktrees()
        
        # Watch for notifications
        try:
            self.watch_for_notifications()
        except KeyboardInterrupt:
            logger.info("Coordinator stopped by user")
        finally:
            self.stop_event.set()
            sync_thread.join()
            
        logger.info("Sync Coordinator stopped")
        
    def status(self):
        """Get current sync status for all worktrees"""
        status_data = {
            'project': self.project_name,
            'worktrees': {},
            'last_update': datetime.now().isoformat()
        }
        
        if self.worktrees_dir.exists():
            for worktree in self.worktrees_dir.iterdir():
                if worktree.is_dir() and (worktree / '.git').exists():
                    branch = self.get_current_branch(worktree)
                    commit = self.get_latest_commit(worktree)
                    
                    status_data['worktrees'][worktree.name] = {
                        'branch': branch,
                        'latest_commit': commit,
                        'path': str(worktree)
                    }
                    
        return status_data

# CLI interface
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Git Sync Coordinator for Tmux Orchestrator')
    parser.add_argument('project', help='Project name to coordinate')
    parser.add_argument('--registry-dir', help='Override registry directory path')
    parser.add_argument('--status', action='store_true', help='Show current sync status')
    parser.add_argument('--sync-now', action='store_true', help='Trigger immediate sync')
    
    args = parser.parse_args()
    
    coordinator = GitSyncCoordinator(args.project, args.registry_dir)
    
    if args.status:
        status = coordinator.status()
        print(json.dumps(status, indent=2))
    elif args.sync_now:
        coordinator.sync_all_worktrees()
        print(f"Sync triggered for {args.project}")
        print(f"Check dashboard: {coordinator.dashboard_file}")
    else:
        # Run the coordinator
        coordinator.run()

if __name__ == '__main__':
    main()
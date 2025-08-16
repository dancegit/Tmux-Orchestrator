#!/usr/bin/env python3
"""
Git Sync Status Dashboard for Tmux Orchestrator
Real-time monitoring of git worktree synchronization status
"""

import os
import subprocess
import json
import time
import curses
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import argparse


class SyncDashboard:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.registry_path = self.project_path.parent.parent / 'registry'
        self.refresh_interval = 5  # seconds
        self.sync_status: Dict[str, Dict] = {}
        
    def find_project_worktrees(self) -> Dict[str, Path]:
        """Find all worktrees for the project"""
        worktrees = {}
        
        # Look for worktrees in registry
        project_name = self.project_path.name
        worktree_base = self.registry_path / 'projects' / project_name / 'worktrees'
        
        if worktree_base.exists():
            for role_dir in worktree_base.iterdir():
                if role_dir.is_dir() and (role_dir / '.git').exists():
                    worktrees[role_dir.name] = role_dir
        
        return worktrees
    
    def get_branch_info(self, worktree_path: Path) -> Dict[str, any]:
        """Get branch information for a worktree"""
        info = {
            'branch': 'unknown',
            'ahead': 0,
            'behind': 0,
            'last_commit': None,
            'uncommitted_changes': False,
            'last_sync': None
        }
        
        try:
            # Get current branch
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                info['branch'] = result.stdout.strip()
            
            # Get ahead/behind status
            result = subprocess.run(
                ['git', 'rev-list', '--left-right', '--count', 'origin/main...HEAD'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                behind, ahead = result.stdout.strip().split('\t')
                info['behind'] = int(behind)
                info['ahead'] = int(ahead)
            
            # Get last commit
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%h %s (%ar)'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                info['last_commit'] = result.stdout.strip()
            
            # Check for uncommitted changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            info['uncommitted_changes'] = bool(result.stdout.strip())
            
            # Get last fetch time (approximation using reflog)
            result = subprocess.run(
                ['git', 'reflog', 'show', '--date=iso', '-n', '1', 'FETCH_HEAD'],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                stderr=subprocess.DEVNULL
            )
            if result.returncode == 0 and result.stdout:
                # Extract date from reflog
                parts = result.stdout.strip().split()
                for i, part in enumerate(parts):
                    if part.startswith('20'):  # Look for date starting with year
                        try:
                            sync_time = datetime.fromisoformat(part + ' ' + parts[i+1])
                            info['last_sync'] = sync_time
                        except:
                            pass
                        break
                        
        except Exception as e:
            pass
            
        return info
    
    def check_conflicts(self, worktree_path: Path) -> List[str]:
        """Check for merge conflicts"""
        conflicts = []
        
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', '--diff-filter=U'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout:
                conflicts = result.stdout.strip().split('\n')
        except:
            pass
            
        return conflicts
    
    def update_sync_status(self):
        """Update sync status for all worktrees"""
        worktrees = self.find_project_worktrees()
        
        for role, path in worktrees.items():
            branch_info = self.get_branch_info(path)
            conflicts = self.check_conflicts(path)
            
            self.sync_status[role] = {
                'path': str(path),
                'branch_info': branch_info,
                'conflicts': conflicts,
                'last_updated': datetime.now()
            }
    
    def format_time_ago(self, dt: Optional[datetime]) -> str:
        """Format datetime as time ago"""
        if not dt:
            return "never"
            
        delta = datetime.now() - dt
        if delta < timedelta(minutes=1):
            return "just now"
        elif delta < timedelta(hours=1):
            return f"{int(delta.total_seconds() / 60)}m ago"
        elif delta < timedelta(days=1):
            return f"{int(delta.total_seconds() / 3600)}h ago"
        else:
            return f"{delta.days}d ago"
    
    def draw_dashboard(self, stdscr):
        """Draw the dashboard using curses"""
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(1)   # Non-blocking input
        
        # Color pairs
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Good
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Warning
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)     # Error
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)    # Info
        
        last_update = time.time()
        
        while True:
            # Update data periodically
            if time.time() - last_update > self.refresh_interval:
                self.update_sync_status()
                last_update = time.time()
            
            # Clear screen
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            
            # Header
            header = f"Git Sync Dashboard - {self.project_path.name}"
            subheader = f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            stdscr.addstr(0, (width - len(header)) // 2, header, curses.A_BOLD)
            stdscr.addstr(1, (width - len(subheader)) // 2, subheader)
            
            # Column headers
            y = 3
            headers = ["Role", "Branch", "Status", "Behind", "Ahead", "Last Commit", "Last Sync"]
            col_widths = [15, 25, 15, 8, 8, 40, 12]
            x = 0
            for i, header in enumerate(headers):
                stdscr.addstr(y, x, header, curses.A_BOLD | curses.A_UNDERLINE)
                x += col_widths[i]
            
            # Data rows
            y = 5
            for role, status in sorted(self.sync_status.items()):
                if y >= height - 2:
                    break
                    
                info = status['branch_info']
                
                # Determine status color
                if status['conflicts']:
                    color = curses.color_pair(3)  # Red for conflicts
                    status_text = "CONFLICT"
                elif info['uncommitted_changes']:
                    color = curses.color_pair(2)  # Yellow for uncommitted
                    status_text = "UNCOMMITTED"
                elif info['behind'] > 0:
                    color = curses.color_pair(2)  # Yellow for behind
                    status_text = "BEHIND"
                else:
                    color = curses.color_pair(1)  # Green for synced
                    status_text = "SYNCED"
                
                # Draw row
                x = 0
                stdscr.addstr(y, x, role[:col_widths[0]-1], color)
                x += col_widths[0]
                
                stdscr.addstr(y, x, info['branch'][:col_widths[1]-1])
                x += col_widths[1]
                
                stdscr.addstr(y, x, status_text, color)
                x += col_widths[2]
                
                behind_text = str(info['behind']) if info['behind'] > 0 else "-"
                stdscr.addstr(y, x, behind_text, curses.color_pair(2) if info['behind'] > 0 else 0)
                x += col_widths[3]
                
                ahead_text = str(info['ahead']) if info['ahead'] > 0 else "-"
                stdscr.addstr(y, x, ahead_text, curses.color_pair(4) if info['ahead'] > 0 else 0)
                x += col_widths[4]
                
                commit_text = (info['last_commit'] or 'No commits')[:col_widths[5]-1]
                stdscr.addstr(y, x, commit_text)
                x += col_widths[5]
                
                sync_text = self.format_time_ago(info['last_sync'])
                stdscr.addstr(y, x, sync_text)
                
                # Show conflicts on next line if any
                if status['conflicts']:
                    y += 1
                    if y < height - 2:
                        conflict_text = f"  ⚠ Conflicts: {', '.join(status['conflicts'][:3])}"
                        if len(status['conflicts']) > 3:
                            conflict_text += f" (+{len(status['conflicts'])-3} more)"
                        stdscr.addstr(y, 2, conflict_text[:width-4], curses.color_pair(3))
                
                y += 1
            
            # Footer
            footer = "Press 'q' to quit, 'r' to refresh"
            stdscr.addstr(height-1, (width - len(footer)) // 2, footer, curses.A_DIM)
            
            # Refresh display
            stdscr.refresh()
            
            # Handle input
            key = stdscr.getch()
            if key == ord('q'):
                break
            elif key == ord('r'):
                self.update_sync_status()
                last_update = time.time()
            
            # Small delay to prevent CPU spinning
            time.sleep(0.1)
    
    def run_dashboard(self):
        """Run the dashboard in curses mode"""
        # Initial data fetch
        self.update_sync_status()
        
        # Run curses interface
        curses.wrapper(self.draw_dashboard)
    
    def get_json_status(self) -> str:
        """Get sync status as JSON (for non-interactive use)"""
        self.update_sync_status()
        
        output = {
            'project': str(self.project_path),
            'timestamp': datetime.now().isoformat(),
            'worktrees': {}
        }
        
        for role, status in self.sync_status.items():
            info = status['branch_info']
            output['worktrees'][role] = {
                'branch': info['branch'],
                'behind': info['behind'],
                'ahead': info['ahead'],
                'uncommitted_changes': info['uncommitted_changes'],
                'conflicts': status['conflicts'],
                'last_commit': info['last_commit'],
                'last_sync': info['last_sync'].isoformat() if info['last_sync'] else None
            }
        
        return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Git Sync Status Dashboard')
    parser.add_argument('project', help='Path to the project')
    parser.add_argument('--json', action='store_true', help='Output JSON instead of interactive dashboard')
    parser.add_argument('--watch', action='store_true', help='Continuously update JSON output')
    parser.add_argument('--interval', type=int, default=5, help='Update interval in seconds (for --watch)')
    
    args = parser.parse_args()
    
    dashboard = SyncDashboard(args.project)
    dashboard.refresh_interval = args.interval
    
    if args.json:
        if args.watch:
            try:
                while True:
                    print("\033[2J\033[H")  # Clear screen
                    print(dashboard.get_json_status())
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                pass
        else:
            print(dashboard.get_json_status())
    else:
        dashboard.run_dashboard()


if __name__ == "__main__":
    main()
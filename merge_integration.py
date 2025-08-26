#!/usr/bin/env python3

# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "rich",
#     "pathlib",
# ]
# ///

"""
Merge Integration Tool

Merges completed worktree integrations from agent orchestrations back to the main project directory.
Only processes projects that are marked as 'completed' in the scheduler database, ensuring
that only finalized work is integrated.

This tool consolidates the final results from agent worktrees into the main project,
creating a clean integration history with proper git tags and backup branches.

Usage Examples:
    ./merge_integration.py --list                                    # Show last 4 completed integrations
    ./merge_integration.py --list --all                              # Show all completed integrations
    ./merge_integration.py --list --page 2                           # Show page 2 of integrations
    ./merge_integration.py --list-progress                           # Show last 10 in-progress projects
    ./merge_integration.py --list-progress --all                     # Show all in-progress projects
    ./merge_integration.py --project "web server" --dry-run          # Preview merge for Web Server project
    ./merge_integration.py --commit da20996a --dry-run               # Preview merge by commit hash
    ./merge_integration.py --project "web server" --force            # Auto-merge Web Server project
    ./merge_integration.py --from /path/to/worktree --to /path/to/project  # Direct path merge

Enhanced Features:
    - Filters to completed projects only (database validation)
    - Shows in-progress projects for monitoring (--list-progress)
    - Pagination support for large numbers of projects (completed and in-progress)
    - Sorted by completion/activity timestamp (most recent first)
    - Rich table display with status indicators and session info
    - Auto-detects integration worktrees with latest commits
    - Creates backup branches before merging
    - Initializes git repositories if needed
    - Tags successful integrations with timestamps
    - Handles merge conflicts gracefully with detailed error reporting
    - Prevents conflicts by managing .mcp.json and CLAUDE.md files
    - Dry-run mode for safe preview
    - Project name fuzzy matching and commit hash selection
"""

import argparse
import json
import subprocess
import shutil
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()
logger = logging.getLogger(__name__)


def find_git_root(start_path: Path) -> Optional[Path]:
    """Find the git root directory"""
    current = start_path
    while current != current.parent:
        if (current / '.git').exists():
            return current
        current = current.parent
    return None


def run_git_command(command: List[str], cwd: str, capture_output: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result"""
    try:
        result = subprocess.run(
            ['git'] + command,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=False
        )
        return result
    except Exception as e:
        console.print(f"[red]Error running git command: {e}[/red]")
        raise


def get_latest_integration_info(worktree_path: Path) -> Dict[str, any]:
    """Get information about the latest integration in a worktree"""
    if not worktree_path.exists() or not (worktree_path / '.git').exists():
        return {}
    
    try:
        # Get current branch
        result = run_git_command(['branch', '--show-current'], str(worktree_path))
        current_branch = result.stdout.strip() if result.returncode == 0 else 'unknown'
        
        # Get latest commit info
        result = run_git_command(['log', '-1', '--format=%H|%aI|%s|%an'], str(worktree_path))
        if result.returncode != 0 or not result.stdout.strip():
            return {}
            
        commit_hash, commit_time, commit_message, author = result.stdout.strip().split('|', 3)
        
        # Get commit count
        result = run_git_command(['rev-list', '--count', 'HEAD'], str(worktree_path))
        commit_count = int(result.stdout.strip()) if result.returncode == 0 else 0
        
        # Check if worktree is clean
        result = run_git_command(['status', '--porcelain'], str(worktree_path))
        is_clean = len(result.stdout.strip()) == 0
        
        return {
            'worktree_path': worktree_path,
            'current_branch': current_branch,
            'commit_hash': commit_hash,
            'commit_hash_short': commit_hash[:8],
            'commit_time': commit_time,
            'commit_message': commit_message,
            'author': author,
            'commit_count': commit_count,
            'is_clean': is_clean
        }
        
    except Exception as e:
        console.print(f"[red]Error analyzing worktree {worktree_path}: {e}[/red]")
        return {}


def find_progress_projects(page: int = 1, per_page: int = 10, all_items: bool = False) -> List[Dict[str, any]]:
    """
    Find in-progress (non-completed) projects from database, with pagination and sorting.
    Shows projects that are currently being worked on or queued.
    """
    projects = []
    try:
        # Import dynamically to avoid circular imports
        from list_completed_projects import get_completed_projects_from_db
        
        # Get database path
        possible_paths = [
            Path(__file__).parent / 'task_queue.db',
            Path.home() / '.tmux-orchestrator' / 'scheduler.db',
            Path(__file__).parent / 'scheduler.db',
            Path(__file__).parent / 'registry' / 'scheduler.db'
        ]
        
        db_path = None
        for path in possible_paths:
            if path.exists():
                db_path = path
                break
        
        if not db_path:
            return []
        
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get non-completed projects (processing, queued, failed)
        cursor.execute("""
            SELECT id, spec_path, project_path, status, enqueued_at, started_at, session_name, error_message
            FROM project_queue
            WHERE status != 'completed'
            ORDER BY COALESCE(started_at, enqueued_at) DESC
        """)
        
        for row in cursor.fetchall():
            spec_path = row[1]
            name = Path(spec_path).stem.replace('_', ' ').title() if spec_path else f"Project {row[0]}"
            
            # Determine timing info
            enqueued_at = row[4]
            started_at = row[5]
            session_name = row[6]
            error_message = row[7]
            
            project = {
                'id': row[0],
                'project_name': name,
                'spec_path': spec_path,
                'project_path': row[2],
                'status': row[3],
                'enqueued_at': enqueued_at,
                'started_at': started_at,
                'session_name': session_name,
                'error_message': error_message,
                'is_active': bool(session_name),  # Has active session
                'display_time': started_at or enqueued_at
            }
            projects.append(project)
        
        conn.close()
        
        # Sort by most recent activity (started_at or enqueued_at)
        projects.sort(
            key=lambda p: datetime.fromisoformat(p.get('display_time') or '1970-01-01') if isinstance(p.get('display_time'), str) else p.get('display_time') or 0,
            reverse=True
        )
        
        if all_items:
            return projects
        
        # Apply pagination
        start = (page - 1) * per_page
        end = start + per_page
        if start >= len(projects) and projects:
            logger.warning(f"Page {page} is out of range (total items: {len(projects)})")
            return []
        
        return projects[start:end]
        
    except Exception as e:
        console.print(f"[red]Error getting in-progress projects: {e}[/red]")
        return []


def find_available_integrations(page: int = 1, per_page: int = 4, all_items: bool = False) -> List[Dict[str, any]]:
    """
    Find available integrations from completed projects only, with pagination and sorting.
    Filters to completed projects via DB/session state, sorts by recency.
    """
    integrations = []
    try:
        # Import dynamically to avoid circular imports
        from list_completed_projects import get_completed_integrations
        
        # Fetch paginated, sorted integrations (new function from list_completed_projects.py)
        integrations = get_completed_integrations(page=page, per_page=per_page, all_items=all_items)
        
        # Cross-validate with session state for each integration (optional validation)
        try:
            from session_state import SessionStateManager
            state_manager = SessionStateManager(Path(__file__).parent)
            validated = []
            for integration in integrations:
                state = state_manager.load_session_state(integration['project_name'])
                if state and state.completion_status == 'completed':
                    # Add completion details from state if available
                    integration['completion_time'] = state.completion_time
                    integration['failure_reason'] = state.failure_reason  # For display if needed
                    validated.append(integration)
                elif state and state.completion_status != 'completed':
                    # Skip projects that have session state but are not completed
                    logger.warning(f"Skipping {integration['project_name']}: Session state shows status '{state.completion_status}'")
                else:
                    # No session state found - trust database completion status
                    logger.info(f"Including {integration['project_name']}: No session state found, but database shows completed")
                    validated.append(integration)
            
            return validated
        except ImportError:
            logger.warning("SessionStateManager not available - using DB data only")
            return integrations
    
    except ImportError as e:
        logger.warning(f"Could not import listing functions: {e} - Falling back to manual scan")
        # Fallback: Manual scan with session state filtering (no pagination in fallback)
        from list_completed_projects import scan_registry_projects, find_project_locations, analyze_worktree_integration
        try:
            from session_state import SessionStateManager
            state_manager = SessionStateManager(Path(__file__).parent)
            projects = scan_registry_projects()
            for project in projects:
                state = state_manager.load_session_state(project['name'])
                if state and state.completion_status == 'completed':
                    locations = find_project_locations(project['name'], project.get('project_path'))
                    integration_info = analyze_worktree_integration(locations)
                    if integration_info['integration_worktree']:
                        integration = {
                            'project_name': project['name'],
                            'project_path': locations.get('project'),
                            'integration_worktree': integration_info['integration_worktree'],
                            'integration_branch': integration_info['integration_branch'],
                            'latest_commit_hash': integration_info['latest_commit_hash'],
                            'latest_commit_message': integration_info['latest_commit_message'],
                            'latest_commit_time': integration_info['latest_commit_time'],
                            'completed_at': state.completion_time or 'N/A',
                            'completion_time': state.completion_time,
                            'failure_reason': state.failure_reason
                        }
                        integrations.append(integration)
            
            # Sort by completion_time in fallback
            integrations.sort(key=lambda i: datetime.fromisoformat(i.get('completion_time') or '1970-01-01'), reverse=True)
            return integrations
        except ImportError:
            logger.warning("SessionStateManager not available - showing all projects")
            # Final fallback: show all projects (original behavior)
            projects = scan_registry_projects()
            for project in projects:
                locations = find_project_locations(project['name'], project.get('project_path'))
                integration_info = analyze_worktree_integration(locations)
                if integration_info['integration_worktree']:
                    integrations.append({
                        'project_name': project['name'],
                        'project_path': locations.get('project'),
                        'integration_worktree': integration_info['integration_worktree'],
                        'integration_branch': integration_info['integration_branch'],
                        'latest_commit_hash': integration_info['latest_commit_hash'],
                        'latest_commit_message': integration_info['latest_commit_message'],
                        'latest_commit_time': integration_info['latest_commit_time']
                    })
            return integrations


def initialize_git_repo(project_path: Path, worktree_path: Path) -> bool:
    """Initialize a git repository in the project directory"""
    console.print(f"[yellow]Initializing git repository in {project_path}[/yellow]")
    
    try:
        # Initialize git repo
        result = run_git_command(['init'], str(project_path))
        if result.returncode != 0:
            console.print(f"[red]Failed to initialize git repo: {result.stderr}[/red]")
            return False
        
        # Configure git user if not set globally
        result = run_git_command(['config', 'user.name'], str(project_path))
        if result.returncode != 0:
            run_git_command(['config', 'user.name', 'Tmux Orchestrator'], str(project_path))
            run_git_command(['config', 'user.email', 'orchestrator@tmux.local'], str(project_path))
        
        # Get the main branch name from worktree
        result = run_git_command(['rev-parse', '--abbrev-ref', 'HEAD'], str(worktree_path))
        main_branch = result.stdout.strip() if result.returncode == 0 else 'main'
        
        # Create initial commit if directory is not empty
        has_files = any(project_path.iterdir())
        if has_files:
            # Add existing files
            result = run_git_command(['add', '.'], str(project_path))
            if result.returncode == 0:
                run_git_command(['commit', '-m', 'Initial commit: existing project files'], str(project_path))
        
        console.print(f"[green]✓ Git repository initialized in {project_path}[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]Error initializing git repo: {e}[/red]")
        return False


def prepare_files_for_merge(project_path: Path) -> bool:
    """
    Prepare .mcp.json and CLAUDE.md files to prevent merge conflicts by:
    1. Adding them to .gitignore if not already present
    2. Running git rm --cached to untrack them
    3. Committing these changes
    """
    try:
        gitignore_path = project_path / '.gitignore'
        files_to_ignore = ['.mcp.json', 'CLAUDE.md']
        
        # Read existing .gitignore
        existing_ignore = set()
        if gitignore_path.exists():
            with open(gitignore_path, 'r') as f:
                existing_ignore = set(line.strip() for line in f if line.strip() and not line.startswith('#'))
        
        # Add files to .gitignore if not already present
        files_added = []
        for file_to_ignore in files_to_ignore:
            if file_to_ignore not in existing_ignore:
                files_added.append(file_to_ignore)
        
        if files_added:
            console.print(f"[yellow]Adding {', '.join(files_added)} to .gitignore[/yellow]")
            with open(gitignore_path, 'a') as f:
                f.write('\n# Auto-added by merge_integration.py to prevent merge conflicts\n')
                for file_to_ignore in files_added:
                    f.write(f'{file_to_ignore}\n')
        
        # Remove files from git tracking if they exist
        files_to_untrack = []
        for file_name in files_to_ignore:
            file_path = project_path / file_name
            if file_path.exists():
                files_to_untrack.append(file_name)
        
        if files_to_untrack:
            console.print(f"[yellow]Removing {', '.join(files_to_untrack)} from git tracking[/yellow]")
            result = run_git_command(['rm', '--cached'] + files_to_untrack, str(project_path))
            if result.returncode != 0 and 'did not match any files' not in result.stderr:
                console.print(f"[yellow]Warning: Could not untrack some files: {result.stderr}[/yellow]")
        
        # Stage .gitignore changes if any were made
        if files_added:
            result = run_git_command(['add', '.gitignore'], str(project_path))
            if result.returncode != 0:
                console.print(f"[red]Failed to stage .gitignore: {result.stderr}[/red]")
                return False
        
        # Commit the changes if there are any staged changes
        result = run_git_command(['diff', '--cached', '--quiet'], str(project_path))
        if result.returncode != 0:  # There are staged changes
            commit_message = f"Prepare for merge: ignore {', '.join(files_to_ignore)} to prevent conflicts"
            result = run_git_command(['commit', '-m', commit_message], str(project_path))
            if result.returncode != 0:
                console.print(f"[red]Failed to commit .gitignore changes: {result.stderr}[/red]")
                return False
            console.print(f"[green]✓ Committed changes to prepare for merge[/green]")
        
        return True
        
    except Exception as e:
        console.print(f"[red]Error preparing files for merge: {e}[/red]")
        return False


def merge_worktree_to_project(worktree_path: Path, project_path: Path, dry_run: bool = False) -> bool:
    """Merge worktree content to main project directory"""
    if not worktree_path.exists() or not (worktree_path / '.git').exists():
        console.print(f"[red]Worktree not found or not a git repository: {worktree_path}[/red]")
        return False
    
    if not project_path.exists():
        console.print(f"[red]Project directory not found: {project_path}[/red]")
        return False
    
    # Check if project has git repo, initialize if needed
    if not (project_path / '.git').exists():
        if not dry_run:
            if not initialize_git_repo(project_path, worktree_path):
                return False
        else:
            console.print(f"[yellow]DRY RUN: Would initialize git repo in {project_path}[/yellow]")
    
    # Get integration info
    integration_info = get_latest_integration_info(worktree_path)
    if not integration_info:
        console.print(f"[red]Could not get integration info from {worktree_path}[/red]")
        return False
    
    console.print(f"\n[bold]Integration Details:[/bold]")
    console.print(f"• Source: {worktree_path}")
    console.print(f"• Target: {project_path}")
    console.print(f"• Branch: {integration_info['current_branch']}")
    console.print(f"• Latest commit: {integration_info['commit_hash_short']} - {integration_info['commit_message']}")
    console.print(f"• Author: {integration_info['author']}")
    console.print(f"• Commit count: {integration_info['commit_count']}")
    console.print(f"• Worktree clean: {'✓' if integration_info['is_clean'] else '✗'}")
    
    if not integration_info['is_clean']:
        console.print("[yellow]Warning: Worktree has uncommitted changes[/yellow]")
    
    if dry_run:
        console.print(f"\n[yellow]DRY RUN: Would merge {worktree_path} to {project_path}[/yellow]")
        return True
    
    try:
        # Add worktree as remote if not already added
        result = run_git_command(['remote'], str(project_path))
        remotes = result.stdout.strip().split('\n') if result.returncode == 0 else []
        
        remote_name = f"worktree-{worktree_path.name}"
        if remote_name not in remotes:
            console.print(f"[yellow]Adding worktree as remote: {remote_name}[/yellow]")
            result = run_git_command(['remote', 'add', remote_name, str(worktree_path)], str(project_path))
            if result.returncode != 0:
                console.print(f"[red]Failed to add remote: {result.stderr}[/red]")
                return False
        
        # Fetch from worktree
        console.print(f"[yellow]Fetching from worktree...[/yellow]")
        result = run_git_command(['fetch', remote_name], str(project_path))
        if result.returncode != 0:
            console.print(f"[red]Failed to fetch from worktree: {result.stderr}[/red]")
            return False
        
        # Get current branch in project
        result = run_git_command(['branch', '--show-current'], str(project_path))
        current_branch = result.stdout.strip() if result.returncode == 0 else 'main'
        
        # Create backup branch
        backup_branch = f"backup-before-merge-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        run_git_command(['branch', backup_branch], str(project_path))
        console.print(f"[green]Created backup branch: {backup_branch}[/green]")
        
        # Handle .mcp.json and CLAUDE.md files to prevent merge conflicts
        console.print(f"[yellow]Preparing files to prevent merge conflicts...[/yellow]")
        if not prepare_files_for_merge(project_path):
            console.print(f"[red]Failed to prepare files for merge[/red]")
            return False
        
        # Merge from worktree
        worktree_branch = f"{remote_name}/{integration_info['current_branch']}"
        console.print(f"[yellow]Merging {worktree_branch} into {current_branch}...[/yellow]")
        
        result = run_git_command(['merge', worktree_branch, '--no-ff', '-m', 
                                f"Merge integration from {worktree_path.name}\n\nCommit: {integration_info['commit_hash_short']}\nMessage: {integration_info['commit_message']}\nAuthor: {integration_info['author']}"], 
                               str(project_path))
        
        if result.returncode != 0:
            console.print(f"[red]Merge failed with return code: {result.returncode}[/red]")
            if result.stderr.strip():
                console.print(f"[red]Error: {result.stderr}[/red]")
            if result.stdout.strip():
                console.print(f"[yellow]Output: {result.stdout}[/yellow]")
            
            # Try to resolve the merge conflict automatically
            if "would be overwritten by merge" in result.stderr:
                console.print(f"[yellow]Attempting automatic conflict resolution...[/yellow]")
                return handle_merge_conflict_automatically(project_path, worktree_branch, current_branch, integration_info)
            
            # Get current git status to show conflicts
            status_result = run_git_command(['status', '--porcelain'], str(project_path))
            if status_result.stdout.strip():
                console.print(f"[yellow]Git status shows conflicts in:[/yellow]")
                for line in status_result.stdout.strip().split('\n'):
                    if line.startswith('UU ') or line.startswith('AA '):
                        console.print(f"  • {line}")
            
            # Show merge conflict info
            conflict_result = run_git_command(['diff', '--name-only', '--diff-filter=U'], str(project_path))
            if conflict_result.stdout.strip():
                console.print(f"[red]Conflicted files:[/red]")
                for file in conflict_result.stdout.strip().split('\n'):
                    console.print(f"  • {file}")
                
                # Try Claude-based conflict resolution
                console.print(f"[yellow]Attempting Claude-based conflict resolution...[/yellow]")
                if resolve_conflicts_with_claude(project_path, conflict_result.stdout.strip().split('\n')):
                    # Complete the merge after resolution
                    merge_result = run_git_command(['commit', '--no-edit'], str(project_path))
                    if merge_result.returncode == 0:
                        console.print(f"[green]✓ Conflicts resolved and merge completed with Claude![/green]")
                        # Merge successful - continue to tagging section
                    else:
                        console.print(f"[red]Failed to complete merge after conflict resolution[/red]")
                        return False
                else:
                    console.print("[yellow]Claude conflict resolution failed, you may need to resolve conflicts manually[/yellow]")
                    return False
            else:
                console.print("[yellow]You may need to resolve conflicts manually[/yellow]")
                return False
        else:
            # Merge was successful on first try
            console.print(f"[green]✓ Merge completed successfully![/green]")
        
        # Tag the merge
        tag_name = f"integration-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        run_git_command(['tag', '-a', tag_name, '-m', f"Integration from {worktree_path.name}"], str(project_path))
        console.print(f"[green]Created tag: {tag_name}[/green]")
        
        console.print(f"\n[green]✓ Successfully merged integration from {worktree_path} to {project_path}[/green]")
        console.print(f"[green]✓ Backup created as branch: {backup_branch}[/green]")
        console.print(f"[green]✓ Tagged as: {tag_name}[/green]")
        
        return True
        
    except Exception as e:
        console.print(f"[red]Error during merge: {e}[/red]")
        return False


def handle_merge_conflict_automatically(project_path: Path, worktree_branch: str, current_branch: str, integration_info: dict) -> bool:
    """Handle merge conflicts automatically using stash and retry strategy."""
    try:
        console.print(f"[yellow]Strategy 1: Stashing local changes and retrying merge...[/yellow]")
        
        # Check if there are local changes that can be stashed
        stash_result = run_git_command(['stash', 'push', '-m', 'Auto-stash before merge integration'], str(project_path))
        if stash_result.returncode != 0:
            console.print(f"[red]Failed to stash changes: {stash_result.stderr}[/red]")
            return False
            
        console.print(f"[green]✓ Local changes stashed successfully[/green]")
        
        # Retry the merge
        console.print(f"[yellow]Retrying merge after stashing...[/yellow]")
        result = run_git_command(['merge', worktree_branch, '--no-ff', '-m', 
                                f"Merge integration from worktree\n\nCommit: {integration_info['commit_hash_short']}\nMessage: {integration_info['commit_message']}\nAuthor: {integration_info['author']}"], 
                               str(project_path))
        
        if result.returncode == 0:
            console.print(f"[green]✓ Merge successful after stashing![/green]")
            
            # Try to reapply stashed changes
            console.print(f"[yellow]Reapplying stashed changes...[/yellow]")
            pop_result = run_git_command(['stash', 'pop'], str(project_path))
            if pop_result.returncode == 0:
                console.print(f"[green]✓ Stashed changes reapplied successfully[/green]")
                
                # Commit the reapplied changes if needed
                status_result = run_git_command(['status', '--porcelain'], str(project_path))
                if status_result.stdout.strip():
                    console.print(f"[yellow]Committing reapplied changes...[/yellow]")
                    run_git_command(['add', '.'], str(project_path))
                    run_git_command(['commit', '-m', 'Reapply local changes after integration merge'], str(project_path))
                    console.print(f"[green]✓ Local changes committed after merge[/green]")
                    
            else:
                console.print(f"[yellow]Warning: Could not reapply stashed changes automatically[/yellow]")
                console.print(f"[yellow]Run 'git stash pop' manually in {project_path} to reapply your changes[/yellow]")
            
            return True
        else:
            console.print(f"[red]Merge still failed after stashing: {result.stderr}[/red]")
            # Try to restore stashed changes
            run_git_command(['stash', 'pop'], str(project_path))
            return False
            
    except Exception as e:
        console.print(f"[red]Error during automatic conflict resolution: {e}[/red]")
        return False


def resolve_conflicts_with_claude(project_path: Path, conflicted_files: List[str]) -> bool:
    """Resolve merge conflicts using Claude AI and handle common conflict patterns."""
    try:
        console.print(f"[yellow]Attempting to resolve {len(conflicted_files)} conflicted files with Claude...[/yellow]")
        
        # First check for deletion/modification conflicts using git ls-files --unmerged
        unmerged_result = run_git_command(['ls-files', '--unmerged'], str(project_path))
        if unmerged_result.returncode == 0 and unmerged_result.stdout.strip():
            deletion_conflicts = set()
            for line in unmerged_result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        stage_info = parts[0].split()
                        if len(stage_info) >= 3:
                            stage = stage_info[2]  # Stage number: 1=base, 2=ours, 3=theirs
                            filename = parts[1]
                            if stage in ['1', '3']:  # Base or theirs exists
                                deletion_conflicts.add(filename)
            
            # Handle deletion conflicts (deleted by us, modified by them)
            for filename in deletion_conflicts:
                console.print(f"[yellow]Handling deletion conflict for: {filename}[/yellow]")
                
                # For deleted-by-us, modified-by-them: keep their version (add the file)
                result = run_git_command(['add', filename], str(project_path))
                if result.returncode == 0:
                    console.print(f"[green]✓ Resolved deletion conflict: kept modified version of {filename}[/green]")
                else:
                    console.print(f"[red]Failed to resolve deletion conflict for {filename}: {result.stderr}[/red]")
                    return False
        
        for file_path in conflicted_files:
            if not file_path.strip():
                continue
                
            full_file_path = project_path / file_path.strip()
            if not full_file_path.exists():
                console.print(f"[yellow]Conflicted file not found (may have been resolved): {file_path}[/yellow]")
                continue
                
            console.print(f"[yellow]Resolving content conflicts in: {file_path}[/yellow]")
            
            # Create a temporary file with conflict resolution prompt
            with open(full_file_path, 'r') as f:
                content = f.read()
            
            # Check if file has merge conflict markers
            if '<<<<<<< HEAD' not in content:
                console.print(f"[yellow]No conflict markers found in {file_path}, skipping[/yellow]")
                continue
            
            # Create prompt for Claude
            prompt = f"""Please resolve the merge conflicts in this file. Remove all conflict markers (<<<<<<< HEAD, =======, >>>>>>>) and merge the code intelligently.

File: {file_path}
Content with conflicts:
{content}

Please output ONLY the resolved file content with no explanation or markdown formatting."""
            
            try:
                # Use Claude via command line
                claude_process = subprocess.run(['claude', '-p', prompt], 
                                             capture_output=True, text=True, cwd=str(project_path))
                
                if claude_process.returncode == 0 and claude_process.stdout.strip():
                    resolved_content = claude_process.stdout.strip()
                    
                    # Verify the resolved content doesn't have conflict markers
                    if ('<<<<<<< HEAD' not in resolved_content and 
                        '=======' not in resolved_content and 
                        '>>>>>>>' not in resolved_content):
                        
                        # Write resolved content back
                        with open(full_file_path, 'w') as f:
                            f.write(resolved_content)
                        
                        # Stage the resolved file
                        run_git_command(['add', file_path], str(project_path))
                        console.print(f"[green]✓ Resolved conflicts in {file_path}[/green]")
                    else:
                        console.print(f"[red]Claude resolution still contains conflict markers in {file_path}[/red]")
                        return False
                else:
                    console.print(f"[red]Claude failed to resolve conflicts in {file_path}[/red]")
                    console.print(f"[red]Error: {claude_process.stderr}[/red]")
                    return False
                    
            except FileNotFoundError:
                console.print(f"[red]Claude command not found. Install claude CLI or add it to PATH[/red]")
                return False
            except Exception as e:
                console.print(f"[red]Error calling Claude for {file_path}: {e}[/red]")
                return False
        
        console.print(f"[green]✓ All conflicts resolved with Claude[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]Error during Claude conflict resolution: {e}[/red]")
        return False


def list_progress_projects(projects: List[Dict[str, any]], args):
    """Display in-progress projects with rich table and status indicators."""
    console.print(Panel.fit(
        "[bold yellow]In-Progress Projects[/bold yellow]\n"
        "Showing projects currently being worked on, queued, or failed",
        border_style="yellow"
    ))
    
    if not projects:
        if args.all:
            console.print("[yellow]No in-progress projects found.[/yellow]")
        else:
            per_page = args.per_page or 10
            console.print(f"[yellow]No in-progress projects on page {args.page}. Use --all to see everything.[/yellow]")
        return
    
    # Create rich table
    table = Table(title=f"In-Progress Projects ({len(projects)} shown)", show_lines=True)
    table.add_column(" # ", style="cyan", width=4)
    table.add_column("Project Name", style="blue", width=25)
    table.add_column("Status", style="yellow", width=12)
    table.add_column("Activity", style="bright_blue", width=20)
    table.add_column("Session", style="green", width=15)
    table.add_column("Error/Notes", style="red", width=30)
    
    for i, project in enumerate(projects, 1):
        # Status with color coding
        status = project['status']
        if status == 'processing':
            status_display = "[green]⚙️ Processing[/green]"
        elif status == 'queued':
            status_display = "[yellow]⏳ Queued[/yellow]"
        elif status == 'failed':
            status_display = "[red]❌ Failed[/red]"
        else:
            status_display = f"[dim]{status}[/dim]"
        
        # Activity time
        display_time = project.get('display_time')
        activity_time = 'N/A'
        if display_time:
            try:
                if isinstance(display_time, str):
                    dt = datetime.fromisoformat(display_time)
                else:
                    dt = datetime.fromtimestamp(display_time)
                activity_time = dt.strftime('%Y-%m-%d %H:%M')
            except:
                activity_time = str(display_time)[:16] if str(display_time) else 'N/A'
        
        # Session status
        session_name = project.get('session_name')
        if session_name:
            session_display = f"[green]✓ {session_name[:12]}...[/green]" if len(session_name) > 15 else f"[green]✓ {session_name}[/green]"
        elif project.get('is_active'):
            session_display = "[green]✓ Active[/green]"
        else:
            session_display = "[dim]No Session[/dim]"
        
        # Error message or notes
        error_msg = project.get('error_message', '') or ''
        if error_msg:
            error_display = error_msg[:27] + '...' if len(error_msg) > 30 else error_msg
        else:
            error_display = '[dim]—[/dim]'
        
        table.add_row(
            str(i),
            project['project_name'],
            status_display,
            activity_time,
            session_display,
            error_display
        )
    
    console.print(table)
    
    # Pagination info
    if not args.all:
        per_page = args.per_page or 10
        console.print(f"[dim]Showing page {args.page} ({per_page} per page). Use --page {args.page + 1} for more or --all for everything.[/dim]")
    
    # Quick info
    console.print(f"\n[bold blue]Status Legend:[/bold blue]")
    console.print(f"• [green]⚙️ Processing[/green]: Currently being worked on")
    console.print(f"• [yellow]⏳ Queued[/yellow]: Waiting to be started")
    console.print(f"• [red]❌ Failed[/red]: Encountered errors")
    console.print(f"• [green]✓ Session[/green]: Has active tmux session")


def check_integration_merge_status(integration: Dict[str, any]) -> tuple[str, str]:
    """
    Check if an integration has already been merged to the main project.
    
    Returns:
        (status, details): 
        - status: "merged", "not_merged", "unknown"  
        - details: descriptive text for display
    """
    try:
        project_path = Path(integration.get('project_path', ''))
        if not project_path.exists() or not (project_path / '.git').exists():
            return "unknown", "No git repo"
            
        # Check for integration tags (created by successful merges)
        tag_result = run_git_command(['tag', '--list', 'integration-*'], str(project_path))
        if tag_result.returncode == 0 and tag_result.stdout.strip():
            # Check if any recent integration tags exist (within last 7 days)
            recent_tags = []
            for tag in tag_result.stdout.strip().split('\n'):
                if tag.strip():
                    # Get tag date
                    tag_date_result = run_git_command(['log', '-1', '--format=%ct', tag.strip()], str(project_path))
                    if tag_date_result.returncode == 0:
                        try:
                            tag_timestamp = int(tag_date_result.stdout.strip())
                            days_ago = (time.time() - tag_timestamp) / 86400  # seconds to days
                            if days_ago <= 7:  # Within last week
                                recent_tags.append((tag.strip(), days_ago))
                        except ValueError:
                            pass
            
            if recent_tags:
                most_recent = min(recent_tags, key=lambda x: x[1])
                days = int(most_recent[1])
                return "merged", f"Tag: {most_recent[0][:20]} ({days}d ago)"
        
        # Check for merge commits in recent history
        commit_hash = integration.get('latest_commit_hash', '')[:8]
        if commit_hash:
            # Search for merge commits that might contain this hash
            merge_result = run_git_command(['log', '--oneline', '--merges', '-10'], str(project_path))
            if merge_result.returncode == 0:
                for line in merge_result.stdout.split('\n'):
                    if commit_hash.lower() in line.lower() or 'integration' in line.lower():
                        return "merged", f"Found merge commit"
        
        # Check if the worktree branch has been merged
        worktree_path = Path(integration.get('integration_worktree', ''))
        if worktree_path.exists():
            branch_info = integration.get('latest_branch', '')
            if branch_info:
                # Check if this branch exists in main project and has been merged
                branch_result = run_git_command(['branch', '--merged', 'main'], str(project_path))
                if branch_result.returncode == 0 and branch_info in branch_result.stdout:
                    return "merged", "Branch merged"
        
        return "not_merged", "Ready to merge"
        
    except Exception as e:
        return "unknown", f"Error: {str(e)[:15]}"


def list_available_integrations(integrations: List[Dict[str, any]], args):
    """Enhanced display with rich table, completion indicators, and pagination info."""
    console.print(Panel.fit(
        "[bold cyan]Available Completed Integrations[/bold cyan]\n"
        "Showing most recent completed projects ready for merge",
        border_style="cyan"
    ))
    
    if not integrations:
        if args.all:
            console.print("[yellow]No completed integrations found.[/yellow]")
        else:
            console.print(f"[yellow]No completed integrations on page {args.page}. Use --all to see everything or check with ./list_completed_projects.py.[/yellow]")
        return
    
    # Group integrations by unique project paths to avoid duplicates
    unique_integrations = {}
    for integration in integrations:
        key = f"{integration['project_path']}-{integration['integration_worktree']}"
        if key not in unique_integrations:
            unique_integrations[key] = integration
    
    integrations = list(unique_integrations.values())
    
    # Create rich table
    table = Table(title=f"Completed Integrations ({len(integrations)} shown)", show_lines=True)
    table.add_column(" # ", style="cyan", width=4)
    table.add_column("Project Name", style="green", width=22)
    table.add_column("Status", style="yellow", width=12)
    table.add_column("Merge Status", style="bright_cyan", width=18)
    table.add_column("Completed At", style="bright_blue", width=16)
    table.add_column("Latest Commit", style="magenta", width=25)
    table.add_column("Merge Command", style="white", width=40)
    
    for i, integration in enumerate(integrations, 1):
        status = "[green]✓ Completed[/green]" if integration.get('completed_at') else "[yellow]Completed (time N/A)[/yellow]"
        
        # Check merge status
        merge_status, merge_details = check_integration_merge_status(integration)
        if merge_status == "merged":
            merge_display = f"[green]✓ {merge_details}[/green]"
        elif merge_status == "not_merged":
            merge_display = f"[yellow]⏳ {merge_details}[/yellow]"
        else:  # unknown
            merge_display = f"[dim]? {merge_details}[/dim]"
        
        completed_at = integration.get('completed_at') or integration.get('completion_time') or 'N/A'
        if completed_at != 'N/A':
            try:
                # Handle both timestamp (float) and ISO string formats
                if isinstance(completed_at, (int, float)):
                    dt = datetime.fromtimestamp(completed_at)
                else:
                    dt = datetime.fromisoformat(str(completed_at))
                completed_at = dt.strftime('%m-%d %H:%M')
            except:
                completed_at = str(completed_at)  # Ensure it's a string for table rendering
        
        commit_info = f"{integration['latest_commit_hash'][:8]}: {integration['latest_commit_message'][:22]}..." if integration.get('latest_commit_message') else 'N/A'
        
        # Adjust merge command based on merge status
        if merge_status == "merged":
            merge_cmd = "[dim]Already merged[/dim]"
        else:
            merge_cmd = f"./merge_integration.py --commit {integration['latest_commit_hash'][:8]} --force"
        
        table.add_row(
            str(i),
            integration['project_name'],
            status,
            merge_display,
            completed_at,
            commit_info,
            merge_cmd
        )
    
    console.print(table)
    
    # Pagination info
    if not args.all:
        console.print(f"[dim]Showing page {args.page} ({args.per_page} per page). Use --page {args.page + 1} for more or --all for everything.[/dim]")
    
    # Status legends
    console.print(f"\n[bold blue]Merge Status Legend:[/bold blue]")
    console.print(f"• [green]✓ Tag: integration-... (Xd ago)[/green]: Successfully merged with integration tag")
    console.print(f"• [green]✓ Found merge commit[/green]: Merge commit detected in git history")
    console.print(f"• [green]✓ Branch merged[/green]: Feature branch has been merged to main")
    console.print(f"• [yellow]⏳ Ready to merge[/yellow]: Integration completed but not yet merged")
    console.print(f"• [dim]? No git repo[/dim]: Project directory has no git repository")
    console.print(f"• [dim]? Error: ...[/dim]: Could not determine merge status")

    # Quick start hints
    console.print(f"\n[bold green]Quick Start Commands:[/bold green]")
    console.print(f"• Preview: ./merge_integration.py --project \"project-name\" --dry-run")
    console.print(f"• Merge: ./merge_integration.py --project \"project-name\" --force")
    console.print(f"• By commit: ./merge_integration.py --commit abc12345 --force")
    console.print(f"• [dim]Note: Already merged integrations are shown for reference but cannot be merged again[/dim]")


def main():
    parser = argparse.ArgumentParser(
        description="Merge completed worktree integrations from agent worktrees back to main project directories",
        epilog="""
Examples:
  %(prog)s --list                                    # Show last 4 completed integrations
  %(prog)s --list --all                              # Show all completed integrations  
  %(prog)s --list --page 2                           # Show page 2 of completed integrations
  %(prog)s --list-progress                           # Show last 10 in-progress projects
  %(prog)s --list-progress --all                     # Show all in-progress projects
  %(prog)s --list-progress --per-page 5              # Show 5 in-progress projects per page
  %(prog)s --project "web server" --dry-run          # Preview merge for Web Server project
  %(prog)s --commit da20996a --dry-run               # Preview merge by commit hash
  %(prog)s --project "web server" --force            # Auto-merge Web Server project
  %(prog)s --from /path/to/worktree --to /path/to/project  # Direct path merge

Notes: 
- Only projects marked as 'completed' are available for merge via --list
- Use --list-progress to monitor currently active projects (queued, processing, failed)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Listing options
    listing_group = parser.add_argument_group('Listing Options', 'Options for viewing project integrations')
    listing_group.add_argument('--list', action='store_true', 
                              help='List available completed integrations ready for merge (default: last 4)')
    listing_group.add_argument('--list-progress', action='store_true',
                              help='List non-completed in-progress projects (default: last 10)')
    listing_group.add_argument('--page', type=int, default=1, metavar='N',
                              help='Page number for listing (default: 1)')
    listing_group.add_argument('--per-page', type=int, metavar='N',
                              help='Items per page (default: 4 for --list, 10 for --list-progress)')
    listing_group.add_argument('--all', action='store_true',
                              help='Show all items without pagination (use with --list or --list-progress)')
    
    # Selection options
    selection_group = parser.add_argument_group('Project Selection', 'Choose which integration to merge')
    selection_group.add_argument('--project', metavar='NAME',
                                help='Project name or partial name for fuzzy matching (auto-detects paths)')
    selection_group.add_argument('--commit', metavar='HASH',
                                help='Commit hash prefix to merge (minimum 8 characters, auto-detects project)')
    selection_group.add_argument('--from', dest='from_path', metavar='PATH',
                                help='Source worktree path (manual override, requires --to)')
    selection_group.add_argument('--to', dest='to_path', metavar='PATH',
                                help='Target project path (manual override, requires --from)')
    
    # Execution options
    execution_group = parser.add_argument_group('Execution Options', 'Control how the merge is performed')
    execution_group.add_argument('--dry-run', action='store_true',
                                help='Preview what would be done without making any changes')
    execution_group.add_argument('--force', action='store_true',
                                help='Skip interactive confirmation prompts (auto-select first match for ambiguous names)')
    
    args = parser.parse_args()
    
    # Set default per_page based on list type
    if not args.per_page:
        args.per_page = 10 if args.list_progress else 4
    
    if args.list:
        integrations = find_available_integrations(page=args.page, per_page=args.per_page, all_items=args.all)
        list_available_integrations(integrations, args)
        return
    
    if args.list_progress:
        projects = find_progress_projects(page=args.page, per_page=args.per_page, all_items=args.all)
        list_progress_projects(projects, args)
        return
    
    # Determine source and target paths
    from_path = None
    to_path = None
    
    if args.commit:
        # Find integration by commit hash - use all items for hash matching
        integrations = find_available_integrations(all_items=True)
        matching = [i for i in integrations if i['latest_commit_hash'] and i['latest_commit_hash'].startswith(args.commit)]
        
        if not matching:
            console.print(f"[red]No integration found with commit hash: {args.commit}[/red]")
            console.print("Use --list to see available commit hashes")
            return
        
        if len(matching) > 1:
            console.print(f"[yellow]Multiple matches found for commit '{args.commit}':[/yellow]")
            for i, match in enumerate(matching):
                console.print(f"{i+1}. {match['project_name']} - {match['latest_commit_hash'][:8]}")
            
            # Use first match if non-interactive or force flag
            if args.force or args.dry_run:
                console.print(f"[yellow]Using first match: {matching[0]['project_name']} ({matching[0]['latest_commit_hash'][:8]})[/yellow]")
                selected = matching[0]
            else:
                try:
                    choice = int(input("Select integration (number): ")) - 1
                    if 0 <= choice < len(matching):
                        selected = matching[choice]
                    else:
                        console.print("[red]Invalid selection[/red]")
                        return
                except (ValueError, KeyboardInterrupt, EOFError):
                    console.print("[red]Invalid selection or non-interactive mode[/red]")
                    console.print("[yellow]Use --force to auto-select first match[/yellow]")
                    return
        else:
            selected = matching[0]
        
        from_path = Path(selected['integration_worktree'])
        to_path = Path(selected['project_path'])
        console.print(f"[green]Selected by commit hash {args.commit}: {selected['project_name']}[/green]")
        
    elif args.project:
        # Auto-detect paths from project name - use all items for name matching
        integrations = find_available_integrations(all_items=True)
        matching = [i for i in integrations if args.project.lower() in i['project_name'].lower()]
        
        if not matching:
            console.print(f"[red]No integration found for project: {args.project}[/red]")
            console.print("Use --list to see available projects")
            return
        
        if len(matching) > 1:
            console.print(f"[yellow]Multiple matches found for '{args.project}':[/yellow]")
            for i, match in enumerate(matching):
                console.print(f"{i+1}. {match['project_name']}")
            
            # Use first match if non-interactive or force flag
            if args.force or args.dry_run:
                console.print(f"[yellow]Using first match: {matching[0]['project_name']}[/yellow]")
                selected = matching[0]
            else:
                try:
                    choice = int(input("Select project (number): ")) - 1
                    if 0 <= choice < len(matching):
                        selected = matching[choice]
                    else:
                        console.print("[red]Invalid selection[/red]")
                        return
                except (ValueError, KeyboardInterrupt, EOFError):
                    console.print("[red]Invalid selection or non-interactive mode[/red]")
                    console.print("[yellow]Use --force to auto-select first match[/yellow]")
                    return
        else:
            selected = matching[0]
        
        from_path = Path(selected['integration_worktree'])
        to_path = Path(selected['project_path'])
        
    elif args.from_path and args.to_path:
        from_path = Path(args.from_path)
        to_path = Path(args.to_path)
    else:
        console.print("[red]Must specify either --project, --commit, or both --from and --to[/red]")
        parser.print_help()
        return
    
    # Validate paths
    if not from_path.exists():
        console.print(f"[red]Source path does not exist: {from_path}[/red]")
        return
    
    if not to_path.exists():
        console.print(f"[red]Target path does not exist: {to_path}[/red]")
        return
    
    # Show what will be done
    console.print(f"\n[bold]Merge Plan:[/bold]")
    console.print(f"• From: {from_path}")
    console.print(f"• To: {to_path}")
    console.print(f"• Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    
    # Confirm unless forced or dry run
    if not args.force and not args.dry_run:
        if not Confirm.ask("\nProceed with merge?"):
            console.print("[yellow]Merge cancelled[/yellow]")
            return
    
    # Perform the merge
    success = merge_worktree_to_project(from_path, to_path, dry_run=args.dry_run)
    
    if success:
        if not args.dry_run:
            console.print(f"\n[green]✓ Integration merge completed successfully![/green]")
            console.print(f"[green]✓ Check {to_path} for the merged code[/green]")
        else:
            console.print(f"\n[blue]✓ Dry run completed - no changes made[/blue]")
    else:
        console.print(f"\n[red]✗ Integration merge failed[/red]")


if __name__ == "__main__":
    main()
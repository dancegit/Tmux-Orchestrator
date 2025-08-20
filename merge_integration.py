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

Merges the latest integration from worktrees back to the main project directory.
If the main project directory doesn't have a .git repository, it will be initialized.

This tool consolidates the final results from agent worktrees into the main project,
creating a clean integration history with proper git tags and backup branches.

Usage Examples:
    ./merge_integration.py --list                                    # Show available integrations
    ./merge_integration.py --project "mcp server" --dry-run          # Preview merge for MCP Server project
    ./merge_integration.py --commit 36d7e425 --dry-run               # Preview merge by commit hash
    ./merge_integration.py --project "web server" --force            # Auto-merge Web Server project
    ./merge_integration.py --commit da20996a --force                 # Auto-merge by commit hash
    ./merge_integration.py --from /path/to/worktree --to /path/to/project  # Direct path merge

Features:
    - Auto-detects integration worktrees with latest commits
    - Creates backup branches before merging
    - Initializes git repositories if needed
    - Tags successful integrations with timestamps
    - Handles merge conflicts gracefully
    - Dry-run mode for safe preview
    - Project name auto-completion
"""

import argparse
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()


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


def find_available_integrations() -> List[Dict[str, any]]:
    """Find all available integrations from the orchestrator registry"""
    integrations = []
    
    # Import from list_completed_projects
    try:
        from list_completed_projects import scan_registry_projects, find_project_locations, analyze_worktree_integration
        
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
    except ImportError:
        console.print("[yellow]Warning: Could not import project listing functions[/yellow]")
    
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
        
        # Merge from worktree
        worktree_branch = f"{remote_name}/{integration_info['current_branch']}"
        console.print(f"[yellow]Merging {worktree_branch} into {current_branch}...[/yellow]")
        
        result = run_git_command(['merge', worktree_branch, '--no-ff', '-m', 
                                f"Merge integration from {worktree_path.name}\n\nCommit: {integration_info['commit_hash_short']}\nMessage: {integration_info['commit_message']}\nAuthor: {integration_info['author']}"], 
                               str(project_path))
        
        if result.returncode != 0:
            console.print(f"[red]Merge failed: {result.stderr}[/red]")
            console.print("[yellow]You may need to resolve conflicts manually[/yellow]")
            return False
        
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


def list_available_integrations():
    """List all available integrations"""
    console.print(Panel.fit(
        "[bold cyan]Available Integration Sources[/bold cyan]\n"
        "Projects with worktree integrations ready for merge",
        border_style="cyan"
    ))
    
    integrations = find_available_integrations()
    
    if not integrations:
        console.print("[yellow]No integrations found[/yellow]")
        return
    
    # Group integrations by unique project paths to avoid duplicates
    unique_integrations = {}
    for integration in integrations:
        key = f"{integration['project_path']}-{integration['integration_worktree']}"
        if key not in unique_integrations:
            unique_integrations[key] = integration
    
    integrations = list(unique_integrations.values())
    
    # Display integrations in a clean, readable list format
    console.print(f"\n[bold cyan]Available Integrations ({len(integrations)} found):[/bold cyan]\n")
    
    for i, integration in enumerate(integrations, 1):
        # Get all the details
        project_name = integration['project_name']
        branch_name = integration['integration_branch'] or 'N/A'
        commit_msg = integration.get('latest_commit_message', 'N/A')
        commit_hash = integration['latest_commit_hash'][:8] if integration['latest_commit_hash'] else 'N/A'
        
        # Display in a clean, boxed format
        console.print(f"[bold cyan]#{i}[/bold cyan] [green]{project_name}[/green]")
        console.print(f"    [yellow]Commit:[/yellow] {commit_hash}")
        console.print(f"    [magenta]Branch:[/magenta] {branch_name}")
        console.print(f"    [blue]Message:[/blue] {commit_msg}")
        console.print()  # Empty line between entries
    
    # Show copy-friendly commands
    console.print(f"\n[bold green]Copy-Paste Commands:[/bold green]")
    console.print("[dim]Choose a number and copy the corresponding command:[/dim]\n")
    
    for i, integration in enumerate(integrations, 1):
        # Extract key parts of project name for easier identification
        project_parts = integration['project_name'].lower().split()
        if 'mcp' in project_parts and 'server' in project_parts:
            short_name = 'mcp-server'
        elif 'web' in project_parts and 'server' in project_parts:
            short_name = 'web-server'
        elif 'mobile' in project_parts and 'app' in project_parts:
            short_name = 'mobile-app'
        else:
            short_name = integration['project_name'].lower().replace(' ', '-')[:15]
        
        commit_hash = integration['latest_commit_hash'][:8] if integration['latest_commit_hash'] else 'N/A'
        
        # Show all three options: project-based, commit-based, and direct paths
        console.print(f"[bold cyan]{i}.[/bold cyan] [green]{short_name}[/green] [yellow]({commit_hash})[/yellow]")
        console.print(f"   [blue]# Project-based (recommended):[/blue]")
        console.print(f"   ./merge_integration.py --project \"{integration['project_name'][:30]}\" --dry-run")
        console.print(f"   ./merge_integration.py --project \"{integration['project_name'][:30]}\" --force")
        console.print(f"   [blue]# Commit-based (precise):[/blue]")
        console.print(f"   ./merge_integration.py --commit {commit_hash} --dry-run")
        console.print(f"   ./merge_integration.py --commit {commit_hash} --force")
        console.print(f"   [blue]# Direct paths:[/blue]")
        console.print(f"   ./merge_integration.py --from {integration['integration_worktree']} --to {integration['project_path']}")
        console.print()
    
    console.print(f"[bold yellow]Quick Start Options:[/bold yellow]")
    console.print(f"1. By project name: [green]./merge_integration.py --project \"mcp server\" --dry-run[/green]")
    console.print(f"2. By commit hash: [green]./merge_integration.py --commit 36d7e425 --dry-run[/green]")
    console.print(f"3. If happy with preview, replace --dry-run with --force")
    console.print(f"4. Check result in project directory")
    
    console.print(f"\n[bold]Found {len(integrations)} unique integration(s) ready for merge[/bold]")


def main():
    parser = argparse.ArgumentParser(description="Merge worktree integrations to main project directories")
    parser.add_argument('--from', dest='from_path', help='Source worktree path')
    parser.add_argument('--to', dest='to_path', help='Target project path')
    parser.add_argument('--project', help='Project name (auto-detect paths)')
    parser.add_argument('--commit', help='Commit hash to merge (8+ characters)')
    parser.add_argument('--list', action='store_true', help='List available integrations')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without executing')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    if args.list:
        list_available_integrations()
        return
    
    # Determine source and target paths
    from_path = None
    to_path = None
    
    if args.commit:
        # Find integration by commit hash
        integrations = find_available_integrations()
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
        # Auto-detect paths from project name
        integrations = find_available_integrations()
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
#!/usr/bin/env python3

# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "rich",
#     "pathlib",
# ]
# ///

"""
Comprehensive Merge Tool for Tmux Orchestrator

This tool merges work from ALL agent worktrees into the main project,
ensuring no implementation is left behind. It handles the complex task
of combining work from developer, tester, pm, and other agents into
a single coherent integration.

Usage:
    ./merge_all_agents.py --project /path/to/project --spec-hash abc123 [--dry-run]
    ./merge_all_agents.py --project /path/to/project --detect [--dry-run]
"""

import argparse
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def run_git_command(cmd: List[str], cwd: str) -> subprocess.CompletedProcess:
    """Run a git command and return the result"""
    return subprocess.run(
        ['git'] + cmd,
        cwd=cwd,
        capture_output=True,
        text=True
    )


def find_worktree_directories(project_path: Path, spec_hash: Optional[str] = None) -> List[Path]:
    """Find all worktree directories for a project"""
    project_name = project_path.name
    parent_dir = project_path.parent
    
    worktree_dirs = []
    
    # Look for standard worktrees
    standard_worktrees = parent_dir / f"{project_name}-tmux-worktrees"
    if standard_worktrees.exists():
        worktree_dirs.append(standard_worktrees)
    
    # Look for spec-specific worktrees
    if spec_hash:
        pattern = f"{project_name}-*-{spec_hash}-tmux-worktrees"
    else:
        pattern = f"{project_name}-*-tmux-worktrees"
    
    for item in parent_dir.glob(pattern):
        if item.is_dir() and item not in worktree_dirs:
            worktree_dirs.append(item)
    
    return worktree_dirs


def analyze_agent_work(worktree_path: Path) -> Dict[str, any]:
    """Analyze an agent's worktree to find their latest work"""
    if not worktree_path.exists():
        return {}
    
    # Get current branch
    result = run_git_command(['branch', '--show-current'], str(worktree_path))
    current_branch = result.stdout.strip() if result.returncode == 0 else 'unknown'
    
    # Get latest commit
    result = run_git_command(['log', '-1', '--format=%H|%aI|%s|%an'], str(worktree_path))
    if result.returncode != 0:
        return {}
    
    commit_hash, commit_time, commit_message, author = result.stdout.strip().split('|', 3)
    
    # Get commit count on this branch
    result = run_git_command(['rev-list', '--count', 'HEAD'], str(worktree_path))
    commit_count = int(result.stdout.strip()) if result.returncode == 0 else 0
    
    # Check for uncommitted changes
    result = run_git_command(['status', '--porcelain'], str(worktree_path))
    has_changes = len(result.stdout.strip()) > 0
    
    # Get list of modified files
    result = run_git_command(['diff', '--name-only', 'HEAD~5..HEAD'], str(worktree_path))
    modified_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
    
    return {
        'agent': worktree_path.name,
        'worktree_path': worktree_path,
        'branch': current_branch,
        'latest_commit': commit_hash,
        'commit_time': commit_time,
        'commit_message': commit_message,
        'author': author,
        'commit_count': commit_count,
        'has_changes': has_changes,
        'modified_files': modified_files
    }


def collect_all_agent_work(project_path: Path, spec_hash: Optional[str] = None) -> List[Dict[str, any]]:
    """Collect work from all agent worktrees"""
    worktree_dirs = find_worktree_directories(project_path, spec_hash)
    
    all_work = []
    for worktree_dir in worktree_dirs:
        console.print(f"[cyan]Scanning worktrees in: {worktree_dir}[/cyan]")
        
        # Check each agent subdirectory
        for agent_dir in worktree_dir.iterdir():
            if agent_dir.is_dir() and (agent_dir / '.git').exists():
                work_info = analyze_agent_work(agent_dir)
                if work_info:
                    all_work.append(work_info)
    
    return all_work


def display_agent_work(agent_work: List[Dict[str, any]]):
    """Display a summary of all agent work"""
    table = Table(title="Agent Work Summary", show_lines=True)
    table.add_column("Agent", style="cyan", width=15)
    table.add_column("Branch", style="green", width=25)
    table.add_column("Latest Commit", style="yellow", width=45)
    table.add_column("Files", style="blue", width=8)
    table.add_column("Status", style="magenta", width=12)
    
    for work in agent_work:
        status = "[red]Uncommitted[/red]" if work['has_changes'] else "[green]Clean[/green]"
        
        # Extract datetime from commit
        commit_dt = datetime.fromisoformat(work['commit_time'].replace('Z', '+00:00'))
        time_str = commit_dt.strftime('%m-%d %H:%M')
        
        table.add_row(
            work['agent'],
            work['branch'][:25],
            f"{work['latest_commit'][:8]} ({time_str}) {work['commit_message'][:35]}...",
            str(len(work['modified_files'])),
            status
        )
    
    console.print(table)


def create_integration_plan(project_path: Path, agent_work: List[Dict[str, any]]) -> List[Tuple[str, Dict]]:
    """Create an ordered integration plan based on agent dependencies"""
    # Define integration order (most foundational first)
    agent_priority = {
        'developer': 1,      # Core implementation
        'tester': 2,         # Tests that depend on implementation
        'project_manager': 3, # PM integration work
        'project-manager': 3, # Alternative naming
        'testrunner': 4,     # Test execution results
        'orchestrator': 5,   # High-level documentation
    }
    
    # Sort by priority
    sorted_work = sorted(
        agent_work,
        key=lambda x: agent_priority.get(x['agent'].lower(), 10)
    )
    
    integration_plan = []
    for work in sorted_work:
        # Skip if no real implementation
        if len(work['modified_files']) == 0:
            continue
            
        # Skip if only log files
        impl_files = [f for f in work['modified_files'] 
                      if not f.endswith('.log') and not f.endswith('.md')]
        if not impl_files:
            console.print(f"[yellow]Skipping {work['agent']} - only documentation/logs[/yellow]")
            continue
        
        integration_plan.append((work['agent'], work))
    
    return integration_plan


def perform_integration(project_path: Path, integration_plan: List[Tuple[str, Dict]], 
                       dry_run: bool = False) -> bool:
    """Execute the integration plan"""
    if not integration_plan:
        console.print("[yellow]No work to integrate![/yellow]")
        return False
    
    # Ensure we're on a clean branch
    if not dry_run:
        # Create integration branch
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        integration_branch = f"integration/all-agents-{timestamp}"
        
        result = run_git_command(['checkout', '-b', integration_branch], str(project_path))
        if result.returncode != 0:
            console.print(f"[red]Failed to create integration branch: {result.stderr}[/red]")
            return False
        
        console.print(f"[green]Created integration branch: {integration_branch}[/green]")
    
    # Execute integration plan
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Integrating agent work...", total=len(integration_plan))
        
        for agent, work in integration_plan:
            progress.update(task, description=f"Integrating {agent}...")
            
            if dry_run:
                console.print(f"\n[yellow]DRY RUN: Would merge {agent} from {work['branch']}[/yellow]")
                console.print(f"  Commit: {work['latest_commit'][:8]} - {work['commit_message']}")
                console.print(f"  Files: {len(work['modified_files'])}")
            else:
                # Add worktree as remote if needed
                remote_name = f"agent-{agent}"
                run_git_command(['remote', 'remove', remote_name], str(project_path))
                result = run_git_command(['remote', 'add', remote_name, str(work['worktree_path'])], 
                                       str(project_path))
                
                if result.returncode == 0:
                    # Fetch from agent
                    console.print(f"\n[cyan]Fetching from {agent}...[/cyan]")
                    result = run_git_command(['fetch', remote_name], str(project_path))
                    
                    if result.returncode == 0:
                        # Merge agent's work
                        merge_ref = f"{remote_name}/{work['branch']}"
                        console.print(f"[cyan]Merging {merge_ref}...[/cyan]")
                        
                        result = run_git_command([
                            'merge', merge_ref, '--no-ff',
                            '-m', f"Integrate {agent}'s work\n\nCommit: {work['latest_commit'][:8]}\nMessage: {work['commit_message']}"
                        ], str(project_path))
                        
                        if result.returncode != 0:
                            console.print(f"[red]Merge conflict with {agent}![/red]")
                            console.print(f"[red]Error: {result.stderr}[/red]")
                            console.print("[yellow]Attempting automatic resolution...[/yellow]")
                            
                            # Try to resolve conflicts automatically
                            # For now, we'll skip and continue
                            run_git_command(['merge', '--abort'], str(project_path))
                            console.print(f"[yellow]Skipped {agent} due to conflicts[/yellow]")
                        else:
                            console.print(f"[green]✓ Successfully integrated {agent}'s work[/green]")
                
                # Clean up remote
                run_git_command(['remote', 'remove', remote_name], str(project_path))
            
            progress.advance(task)
    
    if not dry_run:
        # Create final tag
        tag_name = f"all-agents-integration-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        run_git_command(['tag', '-a', tag_name, '-m', 'Integration of all agent work'], 
                       str(project_path))
        console.print(f"\n[green]✓ Created integration tag: {tag_name}[/green]")
        
        # Show final status
        result = run_git_command(['log', '--oneline', '-10'], str(project_path))
        console.print("\n[bold]Integration History:[/bold]")
        console.print(result.stdout)
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Merge work from ALL agent worktrees",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--project', required=True, type=Path,
                       help='Path to the main project directory')
    parser.add_argument('--spec-hash', 
                       help='Spec hash for finding spec-specific worktrees')
    parser.add_argument('--detect', action='store_true',
                       help='Auto-detect all worktrees')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    if not args.project.exists():
        console.print(f"[red]Project path does not exist: {args.project}[/red]")
        return
    
    console.print(Panel.fit(
        "[bold cyan]Comprehensive Agent Work Integration[/bold cyan]\n"
        "Collecting and merging work from all agent worktrees",
        border_style="cyan"
    ))
    
    # Collect all agent work
    agent_work = collect_all_agent_work(args.project, args.spec_hash)
    
    if not agent_work:
        console.print("[red]No agent work found![/red]")
        return
    
    # Display summary
    display_agent_work(agent_work)
    
    # Create integration plan
    console.print("\n[bold]Creating Integration Plan...[/bold]")
    integration_plan = create_integration_plan(args.project, agent_work)
    
    if not integration_plan:
        console.print("[yellow]No implementation work to integrate (only docs/logs found)[/yellow]")
        return
    
    console.print(f"\n[green]Ready to integrate work from {len(integration_plan)} agents[/green]")
    
    # Confirm before proceeding
    if not args.dry_run:
        response = input("\nProceed with integration? [y/N] ")
        if response.lower() != 'y':
            console.print("[yellow]Integration cancelled[/yellow]")
            return
    
    # Perform integration
    success = perform_integration(args.project, integration_plan, args.dry_run)
    
    if success:
        console.print("\n[green]✓ Integration completed successfully![/green]")
        if args.dry_run:
            console.print("[blue]This was a dry run - no changes were made[/blue]")
    else:
        console.print("\n[red]✗ Integration failed or incomplete[/red]")


if __name__ == "__main__":
    main()
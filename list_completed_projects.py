#!/usr/bin/env python3

# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "rich",
#     "pathlib",
#     "sqlite3",
# ]
# ///

"""
List all completed projects with their locations and integrated code.

This tool scans both the legacy registry and new sibling directory structures
to find all completed projects and their code locations.
"""

import json
import sqlite3
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

logger = logging.getLogger(__name__)

console = Console()


def find_git_root(start_path: Path) -> Optional[Path]:
    """Find the git root directory"""
    current = start_path
    while current != current.parent:
        if (current / '.git').exists():
            return current
        current = current.parent
    return None


def get_completed_projects_from_db() -> List[Dict]:
    """Get completed projects from the scheduler database"""
    # Try multiple possible locations for the database
    possible_paths = [
        Path(__file__).parent / 'task_queue.db',  # Current Tmux-Orchestrator directory (primary)
        Path.home() / '.tmux-orchestrator' / 'scheduler.db',  # Original expected location
        Path(__file__).parent / 'scheduler.db',  # Current Tmux-Orchestrator directory
        Path(__file__).parent / 'registry' / 'scheduler.db'  # Registry subfolder
    ]
    
    db_path = None
    for path in possible_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        return []
    
    completed_projects = []
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, spec_path, spec_path, project_path, status, completed_at
            FROM project_queue
            WHERE status = 'completed'
            ORDER BY completed_at DESC
        """)
        
        for row in cursor.fetchall():
            # Extract project name from spec_path
            spec_path = row[1]
            name = Path(spec_path).stem.replace('_', ' ').title() if spec_path else f"Project {row[0]}"
            
            completed_projects.append({
                'id': row[0],
                'name': name,
                'spec_path': row[2],
                'project_path': row[3],
                'status': row[4],
                'completed_at': row[5]
            })
        
        conn.close()
    except Exception as e:
        console.print(f"[red]Error reading database: {e}[/red]")
    
    return completed_projects


def find_project_locations(project_name: str, project_path: Optional[str] = None) -> Dict[str, Path]:
    """Find all locations related to a project"""
    locations = {}
    
    # First try direct project path (from implementation spec)
    if project_path and Path(project_path).exists():
        project_dir = Path(project_path)
        locations['project'] = project_dir
        
        # Check for sibling worktree and metadata directories
        worktree_dir = project_dir.parent / f"{project_dir.name}-tmux-worktrees"
        metadata_dir = project_dir.parent / f"{project_dir.name}-tmux-metadata"
        
        if worktree_dir.exists():
            locations['worktrees'] = worktree_dir
        if metadata_dir.exists():
            locations['metadata'] = metadata_dir
    
    # Also check legacy registry
    orchestrator_path = Path(__file__).parent
    legacy_registry = orchestrator_path / 'registry' / 'projects'
    
    # Clean project name for registry lookup
    clean_name = project_name.lower().replace(' ', '-')
    
    # Look for project in registry (might have UUID suffix)
    if legacy_registry.exists():
        for proj_dir in legacy_registry.iterdir():
            if proj_dir.is_dir() and clean_name in proj_dir.name:
                locations['legacy_registry'] = proj_dir
                
                # Check for session state
                session_state_file = proj_dir / 'session_state.json'
                if session_state_file.exists():
                    try:
                        with open(session_state_file) as f:
                            state = json.load(f)
                            if 'project_path' in state and state['project_path']:
                                actual_project = Path(state['project_path'])
                                if actual_project.exists():
                                    locations['project'] = actual_project
                                    
                                    # Check for new structure
                                    worktree_dir = actual_project.parent / f"{actual_project.name}-tmux-worktrees"
                                    metadata_dir = actual_project.parent / f"{actual_project.name}-tmux-metadata"
                                    
                                    if worktree_dir.exists():
                                        locations['worktrees'] = worktree_dir
                                    if metadata_dir.exists():
                                        locations['metadata'] = metadata_dir
                    except:
                        pass
                
                # Check for implementation spec if no session state paths found
                if 'project' not in locations:
                    impl_spec_file = proj_dir / 'implementation_spec.json'
                    if impl_spec_file.exists():
                        try:
                            with open(impl_spec_file) as f:
                                spec = json.load(f)
                                if 'project' in spec and 'path' in spec['project']:
                                    spec_project_path = Path(spec['project']['path'])
                                    if spec_project_path.exists():
                                        locations['project'] = spec_project_path
                                        
                                        # Check for new structure
                                        worktree_dir = spec_project_path.parent / f"{spec_project_path.name}-tmux-worktrees"
                                        metadata_dir = spec_project_path.parent / f"{spec_project_path.name}-tmux-metadata"
                                        
                                        if worktree_dir.exists():
                                            locations['worktrees'] = worktree_dir
                                        if metadata_dir.exists():
                                            locations['metadata'] = metadata_dir
                        except:
                            pass
    
    return locations


def get_project_start_time(locations: Dict[str, Path]) -> Optional[str]:
    """Get project start time from session state or git history"""
    # First try session state
    if 'legacy_registry' in locations:
        session_state_file = locations['legacy_registry'] / 'session_state.json'
        if session_state_file.exists():
            try:
                with open(session_state_file) as f:
                    state = json.load(f)
                    if 'created_at' in state:
                        return state['created_at']
            except:
                pass
    
    # Fallback to git history in project directory
    if 'project' in locations:
        try:
            result = subprocess.run(
                ['git', 'log', '--reverse', '--format=%aI', '--max-count=1'],
                cwd=str(locations['project']),
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
    
    return None


def analyze_worktree_integration(locations: Dict[str, Path]) -> Dict[str, any]:
    """Analyze worktrees to find the most recent integration"""
    integration_info = {
        'latest_commit_time': None,
        'latest_commit_hash': None,
        'latest_commit_message': None,
        'integration_worktree': None,
        'integration_branch': None,
        'total_commits': 0
    }
    
    if 'worktrees' not in locations:
        return integration_info
    
    worktree_base = locations['worktrees']
    latest_time = None
    
    # Check each worktree for integration activity
    for worktree_dir in worktree_base.iterdir():
        if not worktree_dir.is_dir() or not (worktree_dir / '.git').exists():
            continue
        
        try:
            # Get the current branch
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=str(worktree_dir),
                capture_output=True,
                text=True
            )
            current_branch = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get latest commit info
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%aI|%H|%s'],
                cwd=str(worktree_dir),
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                commit_time_str, commit_hash, commit_message = result.stdout.strip().split('|', 2)
                commit_time = datetime.fromisoformat(commit_time_str.replace('Z', '+00:00'))
                
                # Count total commits
                count_result = subprocess.run(
                    ['git', 'rev-list', '--count', 'HEAD'],
                    cwd=str(worktree_dir),
                    capture_output=True,
                    text=True
                )
                commit_count = int(count_result.stdout.strip()) if count_result.returncode == 0 else 0
                integration_info['total_commits'] += commit_count
                
                # Check if this is the latest commit
                if latest_time is None or commit_time > latest_time:
                    latest_time = commit_time
                    integration_info['latest_commit_time'] = commit_time_str
                    integration_info['latest_commit_hash'] = commit_hash[:8]
                    integration_info['latest_commit_message'] = commit_message
                    integration_info['integration_worktree'] = worktree_dir
                    integration_info['integration_branch'] = current_branch
                    
        except Exception as e:
            continue
    
    return integration_info


def get_integrated_code_location(locations: Dict[str, Path]) -> Optional[Path]:
    """Determine where the integrated code is located"""
    # First check for most recent integration in worktrees
    integration_info = analyze_worktree_integration(locations)
    if integration_info['integration_worktree']:
        return integration_info['integration_worktree']
    
    # Fallback: The integrated code is in the main project directory
    if 'project' in locations:
        return locations['project']
    
    # Final fallback: check worktrees for integration branch
    if 'worktrees' in locations:
        # Usually the PM or orchestrator worktree has the integrated code
        for role in ['project-manager', 'pm', 'orchestrator']:
            role_worktree = locations['worktrees'] / role
            if role_worktree.exists():
                # Check if it has an integration branch
                try:
                    result = subprocess.run(
                        ['git', 'branch', '--show-current'],
                        cwd=str(role_worktree),
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0 and 'integration' in result.stdout:
                        return role_worktree
                except:
                    pass
    
    return None


def scan_registry_projects() -> List[Dict]:
    """Scan registry for projects when database is not available"""
    projects = []
    orchestrator_path = Path(__file__).parent
    registry_path = orchestrator_path / 'registry' / 'projects'
    
    if not registry_path.exists():
        return projects
    
    for proj_dir in registry_path.iterdir():
        if not proj_dir.is_dir():
            continue
            
        project_info = {
            'id': 'N/A',
            'name': proj_dir.name,
            'spec_path': None,
            'project_path': None,
            'status': 'unknown',
            'completed_at': 'Unknown'
        }
        
        # Try to read session state
        session_state_file = proj_dir / 'session_state.json'
        if session_state_file.exists():
            try:
                with open(session_state_file) as f:
                    state = json.load(f)
                    if 'project_path' in state and state['project_path']:
                        project_info['project_path'] = state['project_path']
                    if 'spec_path' in state:
                        project_info['spec_path'] = state['spec_path']
                    # Check if has completion markers
                    if 'completion_status' in state:
                        project_info['status'] = state['completion_status']
                    if 'project_name' in state:
                        project_info['name'] = state['project_name']
            except:
                pass
        
        # Try to read implementation spec
        impl_spec_file = proj_dir / 'implementation_spec.json'
        if impl_spec_file.exists():
            try:
                with open(impl_spec_file) as f:
                    spec = json.load(f)
                    if 'project' in spec:
                        if 'name' in spec['project']:
                            project_info['name'] = spec['project']['name']
                        # Get project path from implementation spec if not from session state
                        if 'path' in spec['project'] and not project_info['project_path']:
                            project_info['project_path'] = spec['project']['path']
                    
                    # Try to get spec_path if available
                    if 'spec_path' in spec and not project_info['spec_path']:
                        project_info['spec_path'] = spec['spec_path']
            except:
                pass
        
        # Only add if we have some meaningful information
        if project_info['name'] != proj_dir.name or project_info['project_path']:
            projects.append(project_info)
    
    return projects


def main():
    """Main function to list completed projects"""
    console.print(Panel.fit(
        "[bold cyan]Completed Projects Listing[/bold cyan]\n"
        "Showing all completed orchestrations with their code locations",
        border_style="cyan"
    ))
    
    # Get completed projects from database
    completed_projects = get_completed_projects_from_db()
    
    # If no database, scan registry
    if not completed_projects:
        console.print("\n[yellow]No database found. Scanning registry for projects...[/yellow]")
        completed_projects = scan_registry_projects()
        
        if not completed_projects:
            console.print("[yellow]No projects found in registry either.[/yellow]")
            return
    
    # Create table with enhanced columns
    table = Table(title="Completed Projects", show_lines=True)
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Project Name", style="green", width=12)
    table.add_column("Started At", style="bright_blue", width=10)
    table.add_column("Completed At", style="yellow", width=10)
    table.add_column("Project Location", style="blue", width=15)
    table.add_column("Final Integration", style="magenta", width=12)
    table.add_column("Integration Path", style="white", width=25, no_wrap=False)
    table.add_column("Latest Commit", style="bright_green", width=20)
    
    for project in completed_projects:
        # Find all project locations
        locations = find_project_locations(project['name'], project.get('project_path'))
        
        # Get project start time
        start_time = get_project_start_time(locations)
        
        # Analyze integration status
        integration_info = analyze_worktree_integration(locations)
        
        # Determine integrated code location
        code_location = get_integrated_code_location(locations)
        
        # Format locations for display
        project_location = locations.get('project', 'Not found')
        if project_location != 'Not found':
            project_loc = str(project_location).replace('/home/clauderun/', '/home/clauderun/\n')
        else:
            project_loc = 'Not found'
        
        # Format start time
        started_at = 'Unknown'
        if start_time:
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                started_at = dt.strftime('%Y-%m-%d %H:%M')
            except:
                started_at = start_time[:16] if len(start_time) > 16 else start_time
        
        # Format completion time
        completed_at = project.get('completed_at', 'Unknown')
        if completed_at and completed_at != 'Unknown':
            try:
                dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                completed_at = dt.strftime('%Y-%m-%d %H:%M')
            except:
                pass
        
        # Format integration info
        if integration_info['integration_worktree']:
            integration_branch = integration_info['integration_branch']
            
            # Format path with line breaks for readability
            full_path = str(integration_info['integration_worktree'])
            # Break path at logical points (after home directory and project name)
            integration_path = full_path.replace('/home/clauderun/', '/home/clauderun/\n').replace('-tmux-worktrees/', '-tmux-worktrees/\n')
            
            # Format commit message
            commit_msg = integration_info['latest_commit_message']
            if len(commit_msg) > 25:
                latest_commit = f"{integration_info['latest_commit_hash']}\n{commit_msg[:25]}..."
            else:
                latest_commit = f"{integration_info['latest_commit_hash']}\n{commit_msg}"
        else:
            integration_branch = str(code_location) if code_location else 'Not found'
            integration_path = 'N/A'
            latest_commit = 'N/A'
        
        table.add_row(
            str(project['id']),
            project['name'],
            started_at,
            completed_at,
            project_loc,
            integration_branch,
            integration_path,
            latest_commit
        )
    
    console.print(table)
    
    # Calculate and show summary statistics
    total_projects = len(completed_projects)
    projects_with_worktrees = sum(1 for project in completed_projects 
                                 if analyze_worktree_integration(find_project_locations(project['name'], project.get('project_path')))['integration_worktree'])
    projects_with_start_times = sum(1 for project in completed_projects 
                                   if get_project_start_time(find_project_locations(project['name'], project.get('project_path'))))
    
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"• Total projects found: {total_projects}")
    console.print(f"• Projects with worktree integration: {projects_with_worktrees}")
    console.print(f"• Projects with start times: {projects_with_start_times}")
    console.print(f"• Projects with git history analysis: {projects_with_worktrees}")
    
    # Show copy-friendly integration paths
    console.print("\n[bold]Integration Paths (copy-friendly):[/bold]")
    for project in completed_projects:
        locations = find_project_locations(project['name'], project.get('project_path'))
        integration_info = analyze_worktree_integration(locations)
        
        if integration_info['integration_worktree']:
            console.print(f"• [cyan]{project['name'][:30]}[/cyan]: {integration_info['integration_worktree']}")
        else:
            project_location = locations.get('project')
            if project_location:
                console.print(f"• [cyan]{project['name'][:30]}[/cyan]: {project_location} (main project)")
    
    # Show additional information
    console.print("\n[bold]Column Descriptions:[/bold]")
    console.print("• [bright_blue]Started At[/bright_blue]: Project creation time from session state or first git commit")
    console.print("• [yellow]Completed At[/yellow]: Project completion time (if available)")
    console.print("• [blue]Project Location[/blue]: The main project repository")
    console.print("• [magenta]Final Integration[/magenta]: Branch with the most recent commit across all worktrees")
    console.print("• [white]Integration Path[/white]: Path to the worktree containing the final integration")
    console.print("• [bright_green]Latest Commit[/bright_green]: Most recent commit hash and message")
    
    console.print("\n[bold]Note:[/bold] Final integration is determined by analyzing git history across all agent worktrees.")
    console.print("Use the Integration Path to examine the complete development history of the project.")


def get_completed_integrations(page: int = 1, per_page: int = 4, all_items: bool = False) -> List[Dict[str, any]]:
    """
    Get integrations from completed projects only, sorted by recency, with optional pagination.
    Returns a list of dicts ready for display/merging.
    """
    try:
        projects = get_completed_projects_from_db()  # Already filters to status='completed', ordered by completed_at DESC
        
        integrations = []
        for project in projects:
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
                    'completed_at': project['completed_at']  # For sorting and display
                }
                integrations.append(integration)
        
        # Sort by completed_at (DB timestamp) descending (most recent first), fallback to latest_commit_time
        integrations.sort(
            key=lambda i: datetime.fromisoformat(i.get('completed_at') or i.get('latest_commit_time') or '1970-01-01'),
            reverse=True
        )
        
        if all_items:
            return integrations
        
        # Apply pagination
        start = (page - 1) * per_page
        end = start + per_page
        paginated = integrations[start:end]
        if start >= len(integrations):
            logger.warning(f"Page {page} is out of range (total items: {len(integrations)})")
            return []
        
        return paginated
    
    except sqlite3.Error as e:
        logger.error(f"DB error in get_completed_integrations: {e}")
        raise  # Let caller handle fallback


if __name__ == "__main__":
    main()
#!/usr/bin/env python3

# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "rich",
#     "pathlib",
# ]
# ///

"""
Repair incomplete session_state.json files by deriving missing paths.

This tool scans the registry for session_state.json files with empty path fields
and attempts to repair them by deriving the paths from various sources.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def find_git_root(start_path: Path) -> Optional[Path]:
    """Find the git root directory"""
    current = start_path
    while current != current.parent:
        if (current / '.git').exists():
            return current
        current = current.parent
    return None


def derive_project_path_from_spec(registry_dir: Path) -> Optional[Path]:
    """Try to derive project path from implementation spec"""
    impl_spec_files = list(registry_dir.glob('implementation_spec*.json'))
    
    for spec_file in impl_spec_files:
        try:
            spec_data = json.loads(spec_file.read_text())
            
            # Try spec_path first
            if 'spec_path' in spec_data:
                spec_path = Path(spec_data['spec_path'])
                if spec_path.exists():
                    git_root = find_git_root(spec_path.parent)
                    if git_root:
                        return git_root
            
            # Try project.path
            if 'project' in spec_data and 'path' in spec_data['project']:
                project_path = Path(spec_data['project']['path'])
                if project_path.exists():
                    return project_path
                    
        except Exception:
            pass
    
    return None


def find_worktree_paths(project_path: Path, project_name: str) -> Dict[str, Path]:
    """Find worktree paths for a project"""
    worktree_paths = {}
    
    # Check for sibling worktree directory
    worktree_base = project_path.parent / f"{project_path.name}-tmux-worktrees"
    if worktree_base.exists():
        worktree_paths['base'] = worktree_base
        
        # Look for role-specific directories
        for role_dir in worktree_base.iterdir():
            if role_dir.is_dir() and (role_dir / '.git').exists():
                # Map directory name to role
                role = map_dir_to_role(role_dir.name)
                if role:
                    worktree_paths[role] = role_dir
    
    return worktree_paths


def map_dir_to_role(dir_name: str) -> Optional[str]:
    """Map directory name to agent role"""
    name_lower = dir_name.lower()
    
    mappings = {
        'orchestrator': 'orchestrator',
        'project-manager': 'project_manager',
        'pm': 'project_manager',
        'developer': 'developer',
        'dev': 'developer',
        'tester': 'tester',
        'test': 'tester',
        'testrunner': 'testrunner',
        'test-runner': 'testrunner',
        'devops': 'devops',
        'sysadmin': 'sysadmin',
        'securityops': 'securityops',
        'networkops': 'networkops',
        'monitoringops': 'monitoringops',
        'databaseops': 'databaseops',
        'researcher': 'researcher'
    }
    
    for pattern, role in mappings.items():
        if pattern in name_lower:
            return role
    
    return None


def repair_session_state(state_file: Path) -> Dict[str, any]:
    """Attempt to repair a session state file"""
    changes = {}
    
    try:
        # Load current state
        state_data = json.loads(state_file.read_text())
        original_state = json.dumps(state_data, indent=2)
        
        project_name = state_data.get('project_name', '')
        registry_dir = state_file.parent
        
        # Try to derive project path
        if not state_data.get('project_path'):
            project_path = derive_project_path_from_spec(registry_dir)
            if project_path:
                state_data['project_path'] = str(project_path)
                changes['project_path'] = str(project_path)
                
                # Also look for worktrees
                worktree_paths = find_worktree_paths(project_path, project_name)
                
                if worktree_paths.get('base'):
                    state_data['worktree_base_path'] = str(worktree_paths['base'])
                    changes['worktree_base_path'] = str(worktree_paths['base'])
                
                # Update agent worktree paths
                if 'agents' in state_data:
                    for role, agent in state_data['agents'].items():
                        if not agent.get('worktree_path') and role in worktree_paths:
                            agent['worktree_path'] = str(worktree_paths[role])
                            changes[f'agent_{role}_worktree'] = str(worktree_paths[role])
        
        # Try to find spec path from implementation spec
        if not state_data.get('spec_path'):
            impl_spec_files = list(registry_dir.glob('implementation_spec*.json'))
            if impl_spec_files:
                try:
                    spec_data = json.loads(impl_spec_files[0].read_text())
                    if 'spec_path' in spec_data:
                        state_data['spec_path'] = spec_data['spec_path']
                        changes['spec_path'] = spec_data['spec_path']
                except Exception:
                    pass
        
        # Save repaired state if changes were made
        if changes:
            # Backup original
            backup_file = state_file.with_suffix('.json.backup')
            backup_file.write_text(original_state)
            
            # Save repaired state
            state_file.write_text(json.dumps(state_data, indent=2))
            
        return changes
        
    except Exception as e:
        console.print(f"[red]Error repairing {state_file}: {e}[/red]")
        return {}


def find_related_project_dir(registry_path: Path, project_name: str) -> Optional[Path]:
    """Find related project directory that might have an implementation spec"""
    # Look for directories with similar names
    base_name = project_name.lower().replace(' ', '-')
    
    for proj_dir in registry_path.iterdir():
        if not proj_dir.is_dir():
            continue
        
        # Check if it's a related directory (with UUID suffix)
        if proj_dir.name.startswith(base_name) and proj_dir != registry_path / project_name:
            # Check if it has implementation spec
            if list(proj_dir.glob('implementation_spec*.json')):
                return proj_dir
    
    return None


def scan_and_repair_registry():
    """Scan registry for incomplete session states and repair them"""
    orchestrator_path = Path(__file__).parent
    registry_path = orchestrator_path / 'registry' / 'projects'
    
    if not registry_path.exists():
        console.print("[yellow]No registry directory found[/yellow]")
        return
    
    console.print(Panel.fit(
        "[bold cyan]Session State Repair Tool[/bold cyan]\n"
        "Scanning for incomplete session states and attempting repairs",
        border_style="cyan"
    ))
    
    # Create results table
    table = Table(title="Repair Results", show_lines=True)
    table.add_column("Project", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Changes Made", style="yellow")
    
    repaired_count = 0
    total_count = 0
    
    # Scan all project directories
    for proj_dir in registry_path.iterdir():
        if not proj_dir.is_dir():
            continue
            
        state_file = proj_dir / 'session_state.json'
        if not state_file.exists():
            continue
            
        total_count += 1
        
        # Check if repair is needed
        try:
            state_data = json.loads(state_file.read_text())
            
            # Check for empty fields
            needs_repair = (
                not state_data.get('project_path') or
                not state_data.get('worktree_base_path') or
                any(not agent.get('worktree_path') for agent in state_data.get('agents', {}).values())
            )
            
            if needs_repair:
                # Special handling for directories without implementation spec
                if not list(proj_dir.glob('implementation_spec*.json')):
                    # Try to find related directory with UUID
                    project_name = state_data.get('project_name', '')
                    related_dir = find_related_project_dir(registry_path, project_name)
                    
                    if related_dir:
                        # Copy implementation spec from related directory
                        impl_specs = list(related_dir.glob('implementation_spec*.json'))
                        if impl_specs:
                            import shutil
                            shutil.copy(impl_specs[0], proj_dir / 'implementation_spec.json')
                            console.print(f"[yellow]Copied implementation spec from {related_dir.name}[/yellow]")
                
                changes = repair_session_state(state_file)
                
                if changes:
                    repaired_count += 1
                    changes_str = '\n'.join(f"• {k}: {v}" for k, v in changes.items())
                    table.add_row(
                        proj_dir.name,
                        "[green]Repaired[/green]",
                        changes_str
                    )
                else:
                    table.add_row(
                        proj_dir.name,
                        "[yellow]Failed[/yellow]",
                        "Could not derive paths"
                    )
            else:
                table.add_row(
                    proj_dir.name,
                    "[blue]OK[/blue]",
                    "No repair needed"
                )
                
        except Exception as e:
            table.add_row(
                proj_dir.name,
                "[red]Error[/red]",
                str(e)
            )
    
    console.print(table)
    
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"• Total projects scanned: {total_count}")
    console.print(f"• Projects repaired: {repaired_count}")
    console.print(f"• Success rate: {repaired_count/total_count*100:.1f}%" if total_count > 0 else "N/A")
    
    if repaired_count > 0:
        console.print(f"\n[green]✓ Repaired {repaired_count} session state files[/green]")
        console.print("[yellow]Original files backed up with .backup extension[/yellow]")


def main():
    """Main entry point"""
    scan_and_repair_registry()


if __name__ == "__main__":
    main()
"""
Git Worktree Manager Module

Handles git worktree creation, management, and coordination for agent isolation.
This module provides safe worktree operations that prevent conflicts and 
ensure proper git repository structure.
"""

import hashlib
import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


class WorktreeManager:
    """
    Manages git worktrees for agent isolation and parallel development.
    
    Features:
    - Spec-specific worktree paths to prevent conflicts
    - Safe worktree creation with fallback strategies
    - Shared directory symlink setup for cross-worktree access
    - Worktree cleanup and maintenance
    - Git repository validation and repair
    """
    
    def __init__(self, project_path: Path):
        """
        Initialize worktree manager for a project.
        
        Args:
            project_path: Path to the main project directory
        """
        self.project_path = Path(project_path).resolve()
        self.metadata_file = self.project_path / '.worktree_metadata.json'
        
        # Ensure project is a git repository
        self._ensure_git_repository()
    
    def get_worktree_base_path(self, spec_path: Optional[Path] = None) -> Path:
        """
        Get base path for worktrees, ensuring they are siblings to the project.
        
        Args:
            spec_path: Optional specification file path for unique naming
            
        Returns:
            Path: Base directory for all worktrees (sibling to project)
        """
        if spec_path:
            spec_hash = self._get_spec_hash(spec_path)
            spec_name = spec_path.stem.lower().replace('_', '-')
            worktree_name = f"{self.project_path.name}-{spec_name}-{spec_hash}-tmux-worktrees"
        else:
            worktree_name = f"{self.project_path.name}-tmux-worktrees"
        
        # Worktrees are ALWAYS siblings to the project directory
        return self.project_path.parent / worktree_name
    
    def create_agent_worktree(self,
                            role: str,
                            spec_path: Optional[Path] = None,
                            branch_name: str = "main") -> Tuple[bool, Path]:
        """
        Create a worktree for a specific agent role.
        
        Args:
            role: Agent role (e.g., 'developer', 'tester')
            spec_path: Optional specification file path
            branch_name: Branch to base the worktree on
            
        Returns:
            Tuple[bool, Path]: (success, worktree_path)
        """
        console.print(f"[cyan]Creating worktree for {role}[/cyan]")
        
        # Get worktree paths
        worktree_base = self.get_worktree_base_path(spec_path)
        role_worktree = worktree_base / role.lower().replace('_', '-')
        
        try:
            # Ensure base directory exists
            worktree_base.mkdir(parents=True, exist_ok=True)
            
            # Try multiple strategies to create worktree
            success = self._create_worktree_with_fallback(
                worktree_path=role_worktree,
                branch_name=branch_name,
                role=role
            )
            
            if not success:
                console.print(f"[red]❌ Failed to create worktree for {role}[/red]")
                return False, role_worktree
            
            # Set up shared directory symlinks
            self._setup_shared_directory(role_worktree, worktree_base)
            
            # Copy essential files
            self._copy_essential_files(role_worktree)
            
            # Save metadata
            if spec_path:
                self._save_worktree_metadata(spec_path, role_worktree, role)
            
            console.print(f"[green]✅ Created worktree for {role} at {role_worktree}[/green]")
            return True, role_worktree
            
        except Exception as e:
            console.print(f"[red]❌ Error creating worktree for {role}: {e}[/red]")
            return False, role_worktree
    
    def create_team_worktrees(self,
                            roles: List[str],
                            spec_path: Optional[Path] = None,
                            branch_name: str = "main") -> Dict[str, Path]:
        """
        Create worktrees for an entire team.
        
        Args:
            roles: List of agent roles
            spec_path: Optional specification file path
            branch_name: Branch to base worktrees on
            
        Returns:
            Dict mapping role to worktree path
        """
        console.print(f"[blue]🏗️  Creating worktrees for {len(roles)} team members[/blue]")
        
        worktree_paths = {}
        failed_roles = []
        
        for role in roles:
            success, worktree_path = self.create_agent_worktree(
                role=role,
                spec_path=spec_path,
                branch_name=branch_name
            )
            
            if success:
                worktree_paths[role] = worktree_path
            else:
                failed_roles.append(role)
        
        if failed_roles:
            console.print(f"[yellow]⚠️  Failed to create worktrees for: {', '.join(failed_roles)}[/yellow]")
        
        console.print(f"[green]✅ Created {len(worktree_paths)} worktrees successfully[/green]")
        return worktree_paths
    
    def setup_local_remotes(self, worktree_paths: Dict[str, Path]) -> bool:
        """
        Set up local Git remotes between worktrees for fast coordination.
        
        Args:
            worktree_paths: Dict mapping role to worktree path
            
        Returns:
            bool: True if setup succeeded
        """
        console.print("[cyan]Setting up local Git remotes for fast coordination[/cyan]")
        
        try:
            for role, worktree_path in worktree_paths.items():
                # Add remotes for all other worktrees
                for other_role, other_path in worktree_paths.items():
                    if role != other_role:
                        remote_name = other_role.lower().replace('_', '-')
                        
                        # Add remote pointing to other worktree
                        result = subprocess.run([
                            'git', '-C', str(worktree_path),
                            'remote', 'add', remote_name, str(other_path)
                        ], capture_output=True, stderr=subprocess.DEVNULL)
                        
                        if result.returncode == 0:
                            console.print(f"[green]✓ Added {remote_name} remote to {role}[/green]")
            
            console.print("[green]✅ Local remotes configured for fast coordination[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Failed to set up local remotes: {e}[/red]")
            return False
    
    def validate_worktree_integrity(self, worktree_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate worktree integrity and identify issues.
        
        Args:
            worktree_path: Path to worktree to validate
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_issues)
        """
        issues = []
        
        # Check if worktree exists
        if not worktree_path.exists():
            issues.append(f"Worktree directory does not exist: {worktree_path}")
            return False, issues
        
        # Check if it's a valid git worktree
        git_dir = worktree_path / '.git'
        if not git_dir.exists():
            issues.append(f"No .git directory found: {git_dir}")
        else:
            # Check if .git is a file (worktree) or directory (main repo)
            if git_dir.is_file():
                try:
                    with open(git_dir, 'r') as f:
                        content = f.read().strip()
                    if not content.startswith('gitdir:'):
                        issues.append(f"Invalid .git file format: {content}")
                except Exception as e:
                    issues.append(f"Cannot read .git file: {e}")
        
        # Check shared directory symlinks
        shared_dir = worktree_path / 'shared'
        if shared_dir.exists() and shared_dir.is_symlink():
            if not shared_dir.resolve().exists():
                issues.append(f"Broken shared directory symlink: {shared_dir}")
        
        # Test git operations
        try:
            result = subprocess.run([
                'git', '-C', str(worktree_path), 'status'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                issues.append(f"Git status failed: {result.stderr}")
        except Exception as e:
            issues.append(f"Cannot run git commands: {e}")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def cleanup_stale_worktrees(self, max_age_hours: int = 24) -> int:
        """
        Clean up stale or unused worktrees.
        
        Args:
            max_age_hours: Maximum age before worktree is considered stale
            
        Returns:
            int: Number of worktrees cleaned up
        """
        console.print(f"[cyan]Cleaning up stale worktrees (older than {max_age_hours}h)[/cyan]")
        
        cleaned_count = 0
        
        try:
            # Find all worktree directories
            parent_dir = self.project_path.parent
            for item in parent_dir.iterdir():
                if item.is_dir() and item.name.endswith('-tmux-worktrees'):
                    # Check age
                    age_hours = (time.time() - item.stat().st_mtime) / 3600
                    
                    if age_hours > max_age_hours:
                        # Check if worktree is still active (has running tmux session)
                        if not self._is_worktree_active(item):
                            try:
                                shutil.rmtree(item)
                                cleaned_count += 1
                                console.print(f"[green]✓ Cleaned up stale worktree: {item.name}[/green]")
                            except Exception as e:
                                console.print(f"[yellow]Warning: Could not clean {item}: {e}[/yellow]")
            
            if cleaned_count > 0:
                console.print(f"[green]✅ Cleaned up {cleaned_count} stale worktrees[/green]")
            else:
                console.print("[green]✓ No stale worktrees found[/green]")
                
        except Exception as e:
            console.print(f"[red]❌ Error during worktree cleanup: {e}[/red]")
        
        return cleaned_count
    
    def list_active_worktrees(self) -> List[Dict[str, Any]]:
        """
        List all active worktrees for this project.
        
        Returns:
            List of worktree information dictionaries
        """
        worktrees = []
        
        try:
            parent_dir = self.project_path.parent
            for item in parent_dir.iterdir():
                if item.is_dir() and item.name.endswith('-tmux-worktrees'):
                    for role_dir in item.iterdir():
                        if role_dir.is_dir():
                            is_valid, issues = self.validate_worktree_integrity(role_dir)
                            
                            worktree_info = {
                                'role': role_dir.name,
                                'path': str(role_dir),
                                'valid': is_valid,
                                'issues': issues,
                                'age_hours': (time.time() - role_dir.stat().st_mtime) / 3600,
                                'size_mb': sum(f.stat().st_size for f in role_dir.rglob('*') if f.is_file()) / (1024 * 1024)
                            }
                            
                            worktrees.append(worktree_info)
        
        except Exception as e:
            console.print(f"[yellow]Warning: Could not list worktrees: {e}[/yellow]")
        
        return worktrees
    
    def _ensure_git_repository(self) -> bool:
        """Ensure the project path is a git repository."""
        git_dir = self.project_path / '.git'
        
        if not git_dir.exists():
            console.print(f"[yellow]Initializing git repository in {self.project_path}[/yellow]")
            try:
                subprocess.run(['git', 'init'], cwd=self.project_path, check=True, capture_output=True)
                subprocess.run(['git', 'config', 'user.email', 'tmux-orchestrator@example.com'], 
                              cwd=self.project_path, check=True, capture_output=True)
                subprocess.run(['git', 'config', 'user.name', 'Tmux Orchestrator'], 
                              cwd=self.project_path, check=True, capture_output=True)
                
                # Create initial commit if needed
                result = subprocess.run(['git', 'status', '--porcelain'], 
                                      cwd=self.project_path, capture_output=True, text=True)
                if result.stdout.strip():
                    subprocess.run(['git', 'add', '.'], cwd=self.project_path, check=True, capture_output=True)
                    subprocess.run(['git', 'commit', '-m', 'Initial commit for Tmux Orchestrator'], 
                                  cwd=self.project_path, check=True, capture_output=True)
                
                console.print(f"[green]✓ Initialized git repository[/green]")
                return True
            except subprocess.CalledProcessError as e:
                console.print(f"[red]❌ Failed to initialize git repository: {e}[/red]")
                return False
        
        return True
    
    def _create_worktree_with_fallback(self, 
                                     worktree_path: Path,
                                     branch_name: str,
                                     role: str) -> bool:
        """Create worktree using multiple fallback strategies."""
        strategies = [
            ("normal", self._create_worktree_normal),
            ("force", self._create_worktree_force),
            ("detached", self._create_worktree_detached),
            ("agent_branch", self._create_worktree_agent_branch)
        ]
        
        for strategy_name, strategy_func in strategies:
            try:
                console.print(f"[yellow]Trying {strategy_name} strategy for {role}[/yellow]")
                
                if strategy_func(worktree_path, branch_name, role):
                    console.print(f"[green]✓ {strategy_name} strategy succeeded for {role}[/green]")
                    return True
                    
            except Exception as e:
                console.print(f"[yellow]Strategy {strategy_name} failed for {role}: {e}[/yellow]")
                continue
        
        return False
    
    def _create_worktree_normal(self, worktree_path: Path, branch_name: str, role: str) -> bool:
        """Normal worktree creation strategy."""
        result = subprocess.run([
            'git', '-C', str(self.project_path),
            'worktree', 'add', str(worktree_path), branch_name
        ], capture_output=True, text=True)
        
        return result.returncode == 0
    
    def _create_worktree_force(self, worktree_path: Path, branch_name: str, role: str) -> bool:
        """Force worktree creation (handles branch checkout conflicts)."""
        result = subprocess.run([
            'git', '-C', str(self.project_path),
            'worktree', 'add', '--force', str(worktree_path), branch_name
        ], capture_output=True, text=True)
        
        return result.returncode == 0
    
    def _create_worktree_detached(self, worktree_path: Path, branch_name: str, role: str) -> bool:
        """Create detached worktree at current commit."""
        result = subprocess.run([
            'git', '-C', str(self.project_path),
            'worktree', 'add', '--detach', str(worktree_path)
        ], capture_output=True, text=True)
        
        return result.returncode == 0
    
    def _create_worktree_agent_branch(self, worktree_path: Path, branch_name: str, role: str) -> bool:
        """Create worktree with agent-specific branch."""
        agent_branch = f"{branch_name}-{role}"
        
        # Create the agent branch first
        subprocess.run([
            'git', '-C', str(self.project_path),
            'checkout', '-b', agent_branch, branch_name
        ], capture_output=True)
        
        # Create worktree with agent branch
        result = subprocess.run([
            'git', '-C', str(self.project_path),
            'worktree', 'add', str(worktree_path), agent_branch
        ], capture_output=True, text=True)
        
        return result.returncode == 0
    
    def _setup_shared_directory(self, worktree_path: Path, worktree_base: Path) -> bool:
        """Set up shared directory with symlinks for cross-worktree access."""
        try:
            shared_dir = worktree_path / 'shared'
            shared_dir.mkdir(exist_ok=True)
            
            # Create symlink to main project (relative path)
            main_project_link = shared_dir / 'main-project'
            if not main_project_link.exists():
                relative_path = os.path.relpath(self.project_path, shared_dir)
                main_project_link.symlink_to(relative_path)
            
            # Create symlinks to other agent worktrees
            for other_worktree in worktree_base.iterdir():
                if other_worktree.is_dir() and other_worktree != worktree_path:
                    link_name = shared_dir / other_worktree.name
                    if not link_name.exists():
                        relative_path = os.path.relpath(other_worktree, shared_dir)
                        link_name.symlink_to(relative_path)
            
            return True
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not set up shared directory: {e}[/yellow]")
            return False
    
    def _copy_essential_files(self, worktree_path: Path) -> None:
        """Copy essential files to the worktree."""
        essential_files = ['.mcp.json', 'CLAUDE.md']
        
        for filename in essential_files:
            src_file = self.project_path / filename
            if src_file.exists():
                try:
                    shutil.copy2(src_file, worktree_path / filename)
                    console.print(f"[green]✓ Copied {filename} to worktree[/green]")
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not copy {filename}: {e}[/yellow]")
    
    def _get_spec_hash(self, spec_path: Path) -> str:
        """Generate unique hash for specification file."""
        try:
            content = spec_path.read_text()
            return hashlib.sha256(content.encode()).hexdigest()[:12]
        except Exception:
            return "unknown"
    
    def _save_worktree_metadata(self, spec_path: Path, worktree_path: Path, role: str) -> None:
        """Save worktree metadata for tracking."""
        try:
            metadata = {}
            if self.metadata_file.exists():
                metadata = json.loads(self.metadata_file.read_text())
            
            worktree_key = str(worktree_path)
            metadata[worktree_key] = {
                'spec_path': str(spec_path),
                'spec_hash': self._get_spec_hash(spec_path),
                'role': role,
                'created_at': time.time(),
                'project_path': str(self.project_path)
            }
            
            self.metadata_file.write_text(json.dumps(metadata, indent=2))
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save worktree metadata: {e}[/yellow]")
    
    def _is_worktree_active(self, worktree_base: Path) -> bool:
        """Check if worktree has active tmux sessions."""
        try:
            # Look for tmux sessions that might be using this worktree
            result = subprocess.run(['tmux', 'list-sessions'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                # Check if any session name matches the worktree pattern
                session_names = result.stdout
                worktree_name = worktree_base.name.replace('-tmux-worktrees', '')
                return worktree_name in session_names
            
        except Exception:
            pass  # If tmux isn't available or fails, assume not active
        
        return False
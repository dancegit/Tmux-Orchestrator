"""
ProjectResolver - CIIS Integration for SignalMatrix Slice Repository Resolution

This module resolves CIIS batch project specifications to the correct SignalMatrix
slice repositories, enabling proper git worktree creation for tmux orchestration.

Addresses the core issue where CIIS projects were trying to create worktrees from
empty directories instead of valid git repositories.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import time

logger = logging.getLogger(__name__)

class ProjectResolver:
    """
    Resolves CIIS project specifications to correct SignalMatrix slice repositories.
    
    Implements the High Impact, Low Effort solution recommended by Grok analysis:
    - Slice ID extraction from CIIS specs
    - Dynamic repository path resolution
    - Pre-validation caching for performance
    - Fallback mechanisms for robustness
    """
    
    def __init__(self, signalmatrix_base: str = "/home/clauderun/signalmatrix/signalmatrix_org"):
        self.signalmatrix_base = Path(signalmatrix_base)
        self._repository_cache: Dict[str, Path] = {}
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes
        
        # Known slice patterns for validation
        self.known_slices = {
            'options_pricing', 'elliott_wave', 'reporting', 'deployment_validation',
            'rollback_mechanism', 'enhanced_health_checks', 'error_reporting'
        }
        
    def resolve_project_path(self, project_spec_path: str) -> Tuple[Path, str]:
        """
        Resolve CIIS project specification to correct SignalMatrix repository.
        
        Args:
            project_spec_path: Path to CIIS batch specification JSON file
            
        Returns:
            Tuple[Path, str]: (resolved_repository_path, primary_slice_id)
            
        Raises:
            FileNotFoundError: If spec file doesn't exist
            ValueError: If no valid slice repository found
        """
        spec_path = Path(project_spec_path)
        if not spec_path.exists():
            raise FileNotFoundError(f"Project spec not found: {project_spec_path}")
            
        logger.info(f"Resolving project path for spec: {spec_path}")
        
        # Parse CIIS specification
        with open(spec_path, 'r') as f:
            spec_data = json.load(f)
            
        # Extract slice IDs from tasks
        slice_ids = self._extract_slice_ids(spec_data)
        logger.info(f"Extracted slice IDs: {slice_ids}")
        
        if not slice_ids:
            raise ValueError(f"No slice IDs found in specification: {project_spec_path}")
            
        # Find best repository match
        repository_path, primary_slice = self._resolve_repository(slice_ids)
        
        if not repository_path:
            raise ValueError(f"No valid repository found for slices: {slice_ids}")
            
        logger.info(f"Resolved to repository: {repository_path}, primary slice: {primary_slice}")
        return repository_path, primary_slice
        
    def _extract_slice_ids(self, spec_data: Dict) -> Set[str]:
        """Extract all slice IDs from CIIS specification tasks."""
        slice_ids = set()
        
        tasks = spec_data.get('tasks', [])
        for task in tasks:
            # From slice_update tasks
            if task.get('type') == 'slice_update':
                slice_id = task.get('slice_id')
                if slice_id:
                    slice_ids.add(slice_id)
                    
            # From implementation tasks target_slices
            elif task.get('type') == 'implementation':
                target_slices = task.get('target_slices', [])
                for slice_name in target_slices:
                    # Convert slice names to slice IDs (remove _slice suffix if present)
                    clean_name = slice_name.replace('_slice', '')
                    slice_ids.add(clean_name)
                    
        return slice_ids
        
    def _resolve_repository(self, slice_ids: Set[str]) -> Tuple[Optional[Path], Optional[str]]:
        """
        Resolve slice IDs to the best matching repository.
        
        Strategy:
        1. Try direct slice repository matches
        2. Use priority ordering for conflicts
        3. Fall back to main signalmatrix repository
        """
        self._refresh_repository_cache()
        
        # Priority order for slice selection (most specific first)
        slice_priority = [
            'options_pricing', 'elliott_wave', 'reporting',
            'deployment_validation', 'rollback_mechanism', 
            'enhanced_health_checks', 'error_reporting'
        ]
        
        # Try to find direct repository matches
        for slice_id in slice_priority:
            if slice_id in slice_ids:
                repo_path = self._find_slice_repository(slice_id)
                if repo_path and self._validate_repository(repo_path):
                    return repo_path, slice_id
                    
        # Try all slice_ids if priority didn't work
        for slice_id in slice_ids:
            if slice_id not in slice_priority:  # Skip already tried
                repo_path = self._find_slice_repository(slice_id)
                if repo_path and self._validate_repository(repo_path):
                    return repo_path, slice_id
                    
        # Fallback to main repository if it exists and is valid
        main_repo = self.signalmatrix_base
        if self._validate_repository(main_repo):
            logger.warning(f"Falling back to main repository: {main_repo}")
            return main_repo, list(slice_ids)[0] if slice_ids else 'unknown'
            
        return None, None
        
    def _find_slice_repository(self, slice_id: str) -> Optional[Path]:
        """Find repository for a specific slice ID."""
        if slice_id in self._repository_cache:
            return self._repository_cache[slice_id]
            
        # Try different naming patterns
        patterns = [
            f"signalmatrix-slice-{slice_id}",
            f"signalmatrix-slice-{slice_id.replace('_', '-')}",
            f"{slice_id}",
            f"{slice_id.replace('_', '-')}"
        ]
        
        for pattern in patterns:
            repo_path = self.signalmatrix_base / pattern
            if repo_path.exists() and (repo_path / '.git').exists():
                self._repository_cache[slice_id] = repo_path
                logger.debug(f"Found repository for {slice_id}: {repo_path}")
                return repo_path
                
        logger.warning(f"No repository found for slice: {slice_id}")
        return None
        
    def _validate_repository(self, repo_path: Path) -> bool:
        """Validate that a path is a proper git repository."""
        if not repo_path.exists():
            return False
            
        git_dir = repo_path / '.git'
        if not git_dir.exists():
            logger.debug(f"No .git directory found in {repo_path}")
            return False
            
        # Check for basic git repository structure
        if git_dir.is_file():
            # Worktree reference file
            try:
                with open(git_dir, 'r') as f:
                    gitdir_line = f.read().strip()
                    if gitdir_line.startswith('gitdir: '):
                        actual_git_dir = Path(repo_path / gitdir_line[8:])
                        return actual_git_dir.exists()
            except Exception as e:
                logger.debug(f"Error reading git reference: {e}")
                return False
        else:
            # Regular git directory
            required_files = ['HEAD', 'config', 'refs']
            return all((git_dir / item).exists() for item in required_files)
            
        return False
        
    def _refresh_repository_cache(self):
        """Refresh repository cache if TTL expired."""
        current_time = time.time()
        if current_time - self._cache_timestamp > self._cache_ttl:
            logger.debug("Refreshing repository cache")
            self._repository_cache.clear()
            self._cache_timestamp = current_time
            
    def get_available_repositories(self) -> Dict[str, Path]:
        """Get all available slice repositories for debugging/verification."""
        self._refresh_repository_cache()
        
        repositories = {}
        
        # Scan for all slice repositories
        if self.signalmatrix_base.exists():
            for item in self.signalmatrix_base.iterdir():
                if item.is_dir() and item.name.startswith('signalmatrix-slice-'):
                    if self._validate_repository(item):
                        slice_name = item.name.replace('signalmatrix-slice-', '')
                        repositories[slice_name] = item
                        
        return repositories
        
    def validate_project_spec(self, project_spec_path: str) -> Dict[str, any]:
        """
        Validate a project specification and return analysis.
        
        Returns:
            Dict with validation results and recommendations
        """
        try:
            repo_path, primary_slice = self.resolve_project_path(project_spec_path)
            
            spec_path = Path(project_spec_path)
            with open(spec_path, 'r') as f:
                spec_data = json.load(f)
                
            slice_ids = self._extract_slice_ids(spec_data)
            available_repos = self.get_available_repositories()
            
            return {
                'valid': True,
                'resolved_repository': str(repo_path),
                'primary_slice': primary_slice,
                'extracted_slices': list(slice_ids),
                'available_repositories': {k: str(v) for k, v in available_repos.items()},
                'validation_timestamp': time.time()
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'validation_timestamp': time.time()
            }


def resolve_project_for_orchestrator(project_spec_path: str) -> str:
    """
    Main entry point for scheduler integration.
    
    Args:
        project_spec_path: Path to CIIS batch specification
        
    Returns:
        str: Resolved repository path for tmux_orchestrator_cli.py
        
    Raises:
        ValueError: If resolution fails
    """
    resolver = ProjectResolver()
    
    try:
        repo_path, primary_slice = resolver.resolve_project_path(project_spec_path)
        logger.info(f"ProjectResolver: {project_spec_path} -> {repo_path} (slice: {primary_slice})")
        return str(repo_path)
        
    except Exception as e:
        logger.error(f"ProjectResolver failed for {project_spec_path}: {e}")
        raise ValueError(f"Could not resolve project path: {e}")


if __name__ == "__main__":
    # CLI testing interface
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python project_resolver.py <spec_path> [command]")
        print("Commands: resolve, validate, list-repos")
        sys.exit(1)
        
    spec_path = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else 'resolve'
    
    resolver = ProjectResolver()
    
    if command == 'resolve':
        try:
            repo_path, primary_slice = resolver.resolve_project_path(spec_path)
            print(f"Repository: {repo_path}")
            print(f"Primary Slice: {primary_slice}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
            
    elif command == 'validate':
        result = resolver.validate_project_spec(spec_path)
        print(json.dumps(result, indent=2))
        
    elif command == 'list-repos':
        repos = resolver.get_available_repositories()
        print("Available repositories:")
        for slice_id, path in repos.items():
            print(f"  {slice_id}: {path}")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
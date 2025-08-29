#!/usr/bin/env python3
"""
Worktree Manager - Prevents worktree reuse conflicts between different specs
"""

import os
import shutil
import json
import hashlib
import time
from pathlib import Path
from typing import Dict, Optional, List
import subprocess
import logging

logger = logging.getLogger(__name__)

class WorktreeManager:
    """Manages worktree lifecycle to prevent spec conflicts"""
    
    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.metadata_file = self.project_path / '.worktree_metadata.json'
        
    def get_spec_hash(self, spec_path: str) -> str:
        """Generate unique hash for spec file content"""
        try:
            with open(spec_path, 'r') as f:
                content = f.read()
            return hashlib.sha256(content.encode()).hexdigest()[:12]
        except Exception as e:
            logger.error(f"Could not hash spec {spec_path}: {e}")
            return "unknown"
    
    def get_worktree_path(self, spec_path: str) -> Path:
        """Generate worktree path specific to this spec"""
        spec_hash = self.get_spec_hash(spec_path)
        spec_name = Path(spec_path).stem.lower().replace('_', '-')
        
        # Include spec hash to ensure uniqueness
        worktree_name = f"{self.project_path.name}-{spec_name}-{spec_hash}-tmux-worktrees"
        return self.project_path.parent / worktree_name
    
    def load_metadata(self) -> Dict:
        """Load worktree metadata"""
        if not self.metadata_file.exists():
            return {}
        
        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Could not load worktree metadata: {e}")
            return {}
    
    def save_metadata(self, metadata: Dict):
        """Save worktree metadata"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save worktree metadata: {e}")
    
    def is_worktree_compatible(self, spec_path: str, worktree_path: Path) -> bool:
        """Check if existing worktree is compatible with current spec"""
        if not worktree_path.exists():
            return False
            
        metadata = self.load_metadata()
        current_hash = self.get_spec_hash(spec_path)
        
        worktree_key = str(worktree_path)
        if worktree_key in metadata:
            stored_hash = metadata[worktree_key].get('spec_hash')
            return stored_hash == current_hash
        
        return False
    
    def create_worktree_metadata(self, spec_path: str, worktree_path: Path, session_name: str):
        """Record worktree metadata for this spec"""
        metadata = self.load_metadata()
        
        worktree_key = str(worktree_path)
        metadata[worktree_key] = {
            'spec_path': spec_path,
            'spec_hash': self.get_spec_hash(spec_path),
            'session_name': session_name,
            'created_at': time.time(),
            'project_path': str(self.project_path)
        }
        
        self.save_metadata(metadata)
    
    def cleanup_incompatible_worktrees(self, spec_path: str) -> List[str]:
        """Remove worktrees that belong to different specs"""
        removed = []
        current_hash = self.get_spec_hash(spec_path)
        
        # Find all worktrees for this project
        worktree_pattern = f"{self.project_path.name}-*-tmux-worktrees"
        parent_dir = self.project_path.parent
        
        for item in parent_dir.glob(worktree_pattern):
            if item.is_dir():
                if not self.is_worktree_compatible(spec_path, item):
                    logger.info(f"Removing incompatible worktree: {item}")
                    
                    # Remove git worktrees first
                    self._remove_git_worktrees(item)
                    
                    # Remove directory
                    shutil.rmtree(item, ignore_errors=True)
                    removed.append(str(item))
        
        return removed
    
    def _remove_git_worktrees(self, worktree_base: Path):
        """Remove git worktree registrations"""
        try:
            # List all subdirectories that might be git worktrees
            for subdir in worktree_base.glob('*/'):
                if (subdir / '.git').exists():
                    try:
                        subprocess.run([
                            'git', 'worktree', 'remove', str(subdir)
                        ], cwd=self.project_path, capture_output=True, check=False)
                    except Exception as e:
                        logger.debug(f"Could not remove worktree {subdir}: {e}")
        except Exception as e:
            logger.error(f"Error removing git worktrees: {e}")
    
    def get_or_create_worktree_path(self, spec_path: str, session_name: str) -> Path:
        """Get existing compatible worktree or create new path"""
        worktree_path = self.get_worktree_path(spec_path)
        
        if self.is_worktree_compatible(spec_path, worktree_path):
            logger.info(f"Reusing compatible worktree: {worktree_path}")
            return worktree_path
        
        # Clean up incompatible worktrees
        removed = self.cleanup_incompatible_worktrees(spec_path)
        if removed:
            logger.info(f"Cleaned up {len(removed)} incompatible worktrees")
        
        # Create metadata for new worktree
        self.create_worktree_metadata(spec_path, worktree_path, session_name)
        
        logger.info(f"Creating new spec-specific worktree: {worktree_path}")
        return worktree_path

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: worktree_manager.py <project_path> <spec_path> [session_name]")
        sys.exit(1)
    
    project_path = sys.argv[1]
    spec_path = sys.argv[2]
    session_name = sys.argv[3] if len(sys.argv) > 3 else "test"
    
    manager = WorktreeManager(Path(project_path))
    worktree_path = manager.get_or_create_worktree_path(spec_path, session_name)
    
    print(f"Worktree path: {worktree_path}")
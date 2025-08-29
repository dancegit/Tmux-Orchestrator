#!/usr/bin/env python3
"""
Git Commit Manager with automatic tagging and pushing functionality.
Integrates with the Tmux Orchestrator to provide standardized git operations.
"""

import subprocess
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class GitCommitManager:
    """Manages git commits with automatic versioning, tagging, and pushing"""
    
    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.version_pattern = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)(-.*)?$')
        
    def get_current_version(self) -> Optional[str]:
        """Get the current version from git tags"""
        try:
            result = subprocess.run(
                ['git', 'describe', '--tags', '--abbrev=0'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                tag = result.stdout.strip()
                if self.version_pattern.match(tag):
                    return tag
        except Exception as e:
            logger.debug(f"No version tags found: {e}")
        
        # Check all tags for version patterns
        try:
            result = subprocess.run(
                ['git', 'tag', '-l', '--sort=-version:refname'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                for tag in result.stdout.strip().split('\n'):
                    if tag and self.version_pattern.match(tag):
                        return tag
        except Exception as e:
            logger.debug(f"Error listing tags: {e}")
            
        return None
    
    def increment_version(self, version: str, bump_type: str = 'patch') -> str:
        """Increment version number based on bump type"""
        match = self.version_pattern.match(version)
        if not match:
            return 'v0.1.0'
            
        major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
        suffix = match.group(4) or ''
        
        if bump_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump_type == 'minor':
            minor += 1
            patch = 0
        else:  # patch
            patch += 1
            
        return f"v{major}.{minor}.{patch}{suffix}"
    
    def detect_bump_type(self, commit_message: str) -> str:
        """Detect version bump type from commit message"""
        message_lower = commit_message.lower()
        
        # Breaking changes -> major
        if 'breaking change' in message_lower or 'breaking:' in message_lower:
            return 'major'
        
        # New features -> minor
        if any(prefix in message_lower for prefix in ['feat:', 'feature:', 'add:']):
            return 'minor'
            
        # Everything else -> patch
        return 'patch'
    
    def get_uncommitted_changes(self) -> Tuple[List[str], List[str], List[str]]:
        """Get lists of staged, modified, and untracked files"""
        staged = []
        modified = []
        untracked = []
        
        try:
            # Get status
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue
                    
                    status = line[:2]
                    filename = line[3:]
                    
                    if status[0] in ['M', 'A', 'D', 'R', 'C']:
                        staged.append(filename)
                    if status[1] == 'M':
                        modified.append(filename)
                    if status == '??':
                        untracked.append(filename)
                        
        except Exception as e:
            logger.error(f"Error getting git status: {e}")
            
        return staged, modified, untracked
    
    def stage_files(self, files: Optional[List[str]] = None, all_files: bool = False) -> bool:
        """Stage files for commit"""
        try:
            if all_files:
                cmd = ['git', 'add', '-A']
            elif files:
                cmd = ['git', 'add'] + files
            else:
                return True
                
            result = subprocess.run(cmd, cwd=self.project_path, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to stage files: {result.stderr}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error staging files: {e}")
            return False
    
    def commit_changes(self, message: str, add_co_author: bool = True) -> Optional[str]:
        """Create a commit with optional co-author"""
        try:
            # Add co-author if requested
            if add_co_author and "\n\nCo-Authored-By:" not in message:
                message += "\n\n🤖 Generated with Tmux Orchestrator\n\nCo-Authored-By: Orchestrator <noreply@tmux-orchestrator.local>"
            
            # Create commit
            result = subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to commit: {result.stderr}")
                return None
                
            # Get commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
                
        except Exception as e:
            logger.error(f"Error creating commit: {e}")
            
        return None
    
    def create_tag(self, tag_name: str, message: Optional[str] = None) -> bool:
        """Create a git tag"""
        try:
            if message:
                cmd = ['git', 'tag', '-a', tag_name, '-m', message]
            else:
                cmd = ['git', 'tag', tag_name]
                
            result = subprocess.run(cmd, cwd=self.project_path, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to create tag: {result.stderr}")
                return False
                
            logger.info(f"Created tag: {tag_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating tag: {e}")
            return False
    
    def push_changes(self, push_tags: bool = True, branch: Optional[str] = None) -> bool:
        """Push commits and optionally tags to remote"""
        try:
            # Get current branch if not specified
            if not branch:
                result = subprocess.run(
                    ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    branch = result.stdout.strip()
                else:
                    logger.error("Could not determine current branch")
                    return False
            
            # Push branch
            result = subprocess.run(
                ['git', 'push', '-u', 'origin', branch],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to push branch: {result.stderr}")
                return False
                
            logger.info(f"Pushed branch: {branch}")
            
            # Push tags if requested
            if push_tags:
                result = subprocess.run(
                    ['git', 'push', 'origin', '--tags'],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    logger.error(f"Failed to push tags: {result.stderr}")
                    return False
                    
                logger.info("Pushed tags")
                
            return True
            
        except Exception as e:
            logger.error(f"Error pushing changes: {e}")
            return False
    
    def commit_tag_push(self, 
                       message: str,
                       files: Optional[List[str]] = None,
                       all_files: bool = False,
                       auto_version: bool = True,
                       bump_type: Optional[str] = None,
                       push: bool = True) -> Dict[str, any]:
        """
        Complete workflow: stage, commit, tag, and push
        
        Args:
            message: Commit message
            files: Specific files to stage (if None and not all_files, stages already staged files)
            all_files: Stage all changes
            auto_version: Automatically create version tag
            bump_type: Version bump type (major/minor/patch), auto-detected if None
            push: Whether to push to remote
            
        Returns:
            Dict with results of each operation
        """
        result = {
            'success': False,
            'commit_hash': None,
            'tag': None,
            'pushed': False,
            'error': None
        }
        
        try:
            # Stage files
            if not self.stage_files(files, all_files):
                result['error'] = "Failed to stage files"
                return result
            
            # Create commit
            commit_hash = self.commit_changes(message)
            if not commit_hash:
                result['error'] = "Failed to create commit"
                return result
                
            result['commit_hash'] = commit_hash
            
            # Create version tag if requested
            if auto_version:
                current_version = self.get_current_version() or 'v0.0.0'
                
                # Detect bump type from message if not specified
                if not bump_type:
                    bump_type = self.detect_bump_type(message)
                
                new_version = self.increment_version(current_version, bump_type)
                
                if self.create_tag(new_version, f"Release {new_version}\n\n{message}"):
                    result['tag'] = new_version
                else:
                    logger.warning("Failed to create tag, continuing...")
            
            # Push changes
            if push:
                if self.push_changes(push_tags=bool(result['tag'])):
                    result['pushed'] = True
                else:
                    result['error'] = "Failed to push changes"
                    return result
            
            result['success'] = True
            return result
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error in commit_tag_push workflow: {e}")
            return result


def create_commit_command():
    """Create a command-line interface for the git commit manager"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Git commit with automatic tagging and pushing')
    parser.add_argument('message', help='Commit message')
    parser.add_argument('-p', '--path', default='.', help='Project path (default: current directory)')
    parser.add_argument('-a', '--all', action='store_true', help='Stage all changes')
    parser.add_argument('-f', '--files', nargs='+', help='Specific files to stage')
    parser.add_argument('--no-tag', action='store_true', help='Skip automatic tagging')
    parser.add_argument('--no-push', action='store_true', help='Skip pushing to remote')
    parser.add_argument('--bump', choices=['major', 'minor', 'patch'], help='Version bump type')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # Create manager
    manager = GitCommitManager(Path(args.path))
    
    # Execute workflow
    result = manager.commit_tag_push(
        message=args.message,
        files=args.files,
        all_files=args.all,
        auto_version=not args.no_tag,
        bump_type=args.bump,
        push=not args.no_push
    )
    
    # Report results
    if result['success']:
        print(f"✅ Commit created: {result['commit_hash'][:8]}")
        if result['tag']:
            print(f"✅ Tagged as: {result['tag']}")
        if result['pushed']:
            print(f"✅ Pushed to remote")
    else:
        print(f"❌ Error: {result['error']}")
        return 1
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(create_commit_command())
"""
File Utilities Module

Common file operations and utilities for the Tmux Orchestrator system.
"""

import json
import yaml
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from rich.console import Console

console = Console()


class FileUtils:
    """
    File operation utilities with error handling and validation.
    """
    
    @staticmethod
    def read_json(file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Safely read JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Dict containing JSON data or None if error
        """
        try:
            if not file_path.exists():
                console.print(f"[yellow]⚠️ JSON file not found: {file_path}[/yellow]")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return data
            
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ Invalid JSON in {file_path}: {e}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]❌ Error reading {file_path}: {e}[/red]")
            return None
    
    @staticmethod
    def write_json(file_path: Path, data: Dict[str, Any], indent: int = 2) -> bool:
        """
        Safely write JSON file.
        
        Args:
            file_path: Path to write JSON file
            data: Data to write
            indent: JSON indentation
            
        Returns:
            bool: True if write succeeded
        """
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error writing JSON to {file_path}: {e}[/red]")
            return False
    
    @staticmethod
    def read_yaml(file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Safely read YAML file.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            Dict containing YAML data or None if error
        """
        try:
            if not file_path.exists():
                console.print(f"[yellow]⚠️ YAML file not found: {file_path}[/yellow]")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            return data or {}
            
        except yaml.YAMLError as e:
            console.print(f"[red]❌ Invalid YAML in {file_path}: {e}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]❌ Error reading YAML {file_path}: {e}[/red]")
            return None
    
    @staticmethod
    def write_yaml(file_path: Path, data: Dict[str, Any]) -> bool:
        """
        Safely write YAML file.
        
        Args:
            file_path: Path to write YAML file
            data: Data to write
            
        Returns:
            bool: True if write succeeded
        """
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, default_flow_style=False, indent=2)
            
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error writing YAML to {file_path}: {e}[/red]")
            return False
    
    @staticmethod
    def read_text(file_path: Path) -> Optional[str]:
        """
        Safely read text file.
        
        Args:
            file_path: Path to text file
            
        Returns:
            File content or None if error
        """
        try:
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return content
            
        except Exception as e:
            console.print(f"[red]❌ Error reading text file {file_path}: {e}[/red]")
            return None
    
    @staticmethod
    def write_text(file_path: Path, content: str) -> bool:
        """
        Safely write text file.
        
        Args:
            file_path: Path to write text file
            content: Content to write
            
        Returns:
            bool: True if write succeeded
        """
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error writing text to {file_path}: {e}[/red]")
            return False
    
    @staticmethod
    def backup_file(file_path: Path, backup_suffix: str = ".backup") -> Optional[Path]:
        """
        Create backup of file.
        
        Args:
            file_path: Path to file to backup
            backup_suffix: Suffix for backup file
            
        Returns:
            Path to backup file or None if error
        """
        try:
            if not file_path.exists():
                console.print(f"[yellow]⚠️ File not found for backup: {file_path}[/yellow]")
                return None
            
            backup_path = file_path.with_suffix(file_path.suffix + backup_suffix)
            shutil.copy2(file_path, backup_path)
            
            console.print(f"[green]✅ Created backup: {backup_path}[/green]")
            return backup_path
            
        except Exception as e:
            console.print(f"[red]❌ Error creating backup of {file_path}: {e}[/red]")
            return None
    
    @staticmethod
    def restore_backup(backup_path: Path, target_path: Optional[Path] = None) -> bool:
        """
        Restore file from backup.
        
        Args:
            backup_path: Path to backup file
            target_path: Target path for restoration (defaults to original)
            
        Returns:
            bool: True if restore succeeded
        """
        try:
            if not backup_path.exists():
                console.print(f"[red]❌ Backup file not found: {backup_path}[/red]")
                return False
            
            if target_path is None:
                # Remove backup suffix to get original path
                target_path = backup_path.with_suffix(
                    backup_path.suffix.replace('.backup', '')
                )
            
            shutil.copy2(backup_path, target_path)
            
            console.print(f"[green]✅ Restored from backup: {target_path}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error restoring backup {backup_path}: {e}[/red]")
            return False
    
    @staticmethod
    def ensure_directory(dir_path: Path) -> bool:
        """
        Ensure directory exists, creating if necessary.
        
        Args:
            dir_path: Directory path to create
            
        Returns:
            bool: True if directory exists or was created
        """
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error creating directory {dir_path}: {e}[/red]")
            return False
    
    @staticmethod
    def clean_directory(dir_path: Path, keep_patterns: List[str] = None) -> bool:
        """
        Clean directory, optionally keeping files matching patterns.
        
        Args:
            dir_path: Directory to clean
            keep_patterns: List of glob patterns for files to keep
            
        Returns:
            bool: True if cleanup succeeded
        """
        try:
            if not dir_path.exists():
                return True
            
            keep_patterns = keep_patterns or []
            files_removed = 0
            
            for item in dir_path.iterdir():
                # Check if item should be kept
                should_keep = False
                for pattern in keep_patterns:
                    if item.match(pattern):
                        should_keep = True
                        break
                
                if not should_keep:
                    if item.is_file():
                        item.unlink()
                        files_removed += 1
                    elif item.is_dir():
                        shutil.rmtree(item)
                        files_removed += 1
            
            if files_removed > 0:
                console.print(f"[green]✅ Cleaned directory {dir_path}: {files_removed} items removed[/green]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error cleaning directory {dir_path}: {e}[/red]")
            return False
    
    @staticmethod
    def get_file_size(file_path: Path) -> Optional[int]:
        """
        Get file size in bytes.
        
        Args:
            file_path: Path to file
            
        Returns:
            File size in bytes or None if error
        """
        try:
            if file_path.exists():
                return file_path.stat().st_size
            return None
            
        except Exception as e:
            console.print(f"[red]❌ Error getting file size {file_path}: {e}[/red]")
            return None
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Format file size in human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        size_index = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and size_index < len(size_names) - 1:
            size /= 1024.0
            size_index += 1
        
        return f"{size:.1f} {size_names[size_index]}"
    
    @staticmethod
    def find_files(directory: Path, pattern: str = "*", recursive: bool = True) -> List[Path]:
        """
        Find files matching pattern in directory.
        
        Args:
            directory: Directory to search
            pattern: Glob pattern to match
            recursive: Whether to search recursively
            
        Returns:
            List of matching file paths
        """
        try:
            if not directory.exists():
                return []
            
            if recursive:
                return list(directory.rglob(pattern))
            else:
                return list(directory.glob(pattern))
                
        except Exception as e:
            console.print(f"[red]❌ Error finding files in {directory}: {e}[/red]")
            return []
    
    @staticmethod
    def validate_file_permissions(file_path: Path, required_perms: str = "rw") -> bool:
        """
        Validate file has required permissions.
        
        Args:
            file_path: Path to file
            required_perms: Required permissions ('r', 'w', 'x' or combinations)
            
        Returns:
            bool: True if file has required permissions
        """
        try:
            if not file_path.exists():
                return False
            
            stat = file_path.stat()
            
            # Check readable
            if 'r' in required_perms and not (stat.st_mode & 0o400):
                return False
            
            # Check writable
            if 'w' in required_perms and not (stat.st_mode & 0o200):
                return False
            
            # Check executable
            if 'x' in required_perms and not (stat.st_mode & 0o100):
                return False
            
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error checking permissions for {file_path}: {e}[/red]")
            return False
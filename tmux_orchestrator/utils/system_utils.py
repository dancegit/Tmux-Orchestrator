"""
System Utilities Module

System-level utilities and helpers for the Tmux Orchestrator system.
"""

import os
import sys
import subprocess
import socket
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from rich.console import Console

console = Console()


class SystemUtils:
    """
    System-level utilities and process management.
    """
    
    @staticmethod
    def is_port_free(port: int, host: str = 'localhost') -> bool:
        """
        Check if a port is available.
        
        Args:
            port: Port number to check
            host: Host to check (default: localhost)
            
        Returns:
            bool: True if port is available
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result != 0
                
        except Exception as e:
            console.print(f"[yellow]⚠️ Error checking port {port}: {e}[/yellow]")
            return False
    
    @staticmethod
    def find_free_port(start_port: int = 3000, max_attempts: int = 100) -> Optional[int]:
        """
        Find an available port starting from start_port.
        
        Args:
            start_port: Port to start searching from
            max_attempts: Maximum number of ports to try
            
        Returns:
            Available port number or None if none found
        """
        for port in range(start_port, start_port + max_attempts):
            if SystemUtils.is_port_free(port):
                return port
        
        console.print(f"[red]❌ No free ports found in range {start_port}-{start_port + max_attempts}[/red]")
        return None
    
    @staticmethod
    def run_command(command: List[str], 
                   cwd: Optional[Path] = None,
                   timeout: Optional[int] = None,
                   capture_output: bool = True) -> Tuple[int, str, str]:
        """
        Run system command with proper error handling.
        
        Args:
            command: Command and arguments as list
            cwd: Working directory for command
            timeout: Command timeout in seconds
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                timeout=timeout,
                capture_output=capture_output,
                text=True
            )
            
            return (result.returncode, result.stdout or "", result.stderr or "")
            
        except subprocess.TimeoutExpired as e:
            console.print(f"[red]❌ Command timeout: {' '.join(command)}[/red]")
            return (124, "", f"Command timed out after {timeout} seconds")
            
        except FileNotFoundError as e:
            console.print(f"[red]❌ Command not found: {command[0]}[/red]")
            return (127, "", f"Command not found: {command[0]}")
            
        except Exception as e:
            console.print(f"[red]❌ Error running command {' '.join(command)}: {e}[/red]")
            return (1, "", str(e))
    
    @staticmethod
    def run_command_async(command: List[str], 
                         cwd: Optional[Path] = None) -> subprocess.Popen:
        """
        Run command asynchronously.
        
        Args:
            command: Command and arguments as list
            cwd: Working directory for command
            
        Returns:
            Popen process object
        """
        try:
            return subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
        except Exception as e:
            console.print(f"[red]❌ Error starting async command {' '.join(command)}: {e}[/red]")
            raise
    
    @staticmethod
    def kill_process_by_port(port: int) -> bool:
        """
        Kill process using specified port.
        
        Args:
            port: Port number
            
        Returns:
            bool: True if process was killed
        """
        try:
            # Find process using port
            if sys.platform == "darwin":  # macOS
                cmd = ["lsof", "-ti", f":{port}"]
            else:  # Linux
                cmd = ["fuser", "-n", "tcp", str(port)]
            
            returncode, stdout, stderr = SystemUtils.run_command(cmd)
            
            if returncode == 0 and stdout.strip():
                pids = [pid.strip() for pid in stdout.strip().split('\n') if pid.strip()]
                
                for pid in pids:
                    try:
                        os.kill(int(pid), 15)  # SIGTERM
                        time.sleep(1)
                        os.kill(int(pid), 9)   # SIGKILL
                        console.print(f"[green]✅ Killed process {pid} on port {port}[/green]")
                    except ProcessLookupError:
                        pass  # Process already dead
                    except Exception as e:
                        console.print(f"[yellow]⚠️ Error killing process {pid}: {e}[/yellow]")
                
                return True
            
            return False
            
        except Exception as e:
            console.print(f"[red]❌ Error killing process on port {port}: {e}[/red]")
            return False
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """
        Get system information.
        
        Returns:
            Dict containing system information
        """
        import platform
        import getpass
        
        try:
            return {
                'platform': platform.system(),
                'platform_release': platform.release(),
                'platform_version': platform.version(),
                'architecture': platform.machine(),
                'hostname': platform.node(),
                'username': getpass.getuser(),
                'python_version': platform.python_version(),
                'python_executable': sys.executable,
                'working_directory': str(Path.cwd())
            }
            
        except Exception as e:
            console.print(f"[yellow]⚠️ Error getting system info: {e}[/yellow]")
            return {}
    
    @staticmethod
    def check_command_availability(command: str) -> bool:
        """
        Check if a command is available in PATH.
        
        Args:
            command: Command name to check
            
        Returns:
            bool: True if command is available
        """
        try:
            result = subprocess.run(['which', command], capture_output=True)
            return result.returncode == 0
            
        except Exception:
            return False
    
    @staticmethod
    def get_environment_variable(var_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get environment variable with optional default.
        
        Args:
            var_name: Environment variable name
            default: Default value if variable not set
            
        Returns:
            Environment variable value or default
        """
        return os.environ.get(var_name, default)
    
    @staticmethod
    def set_environment_variable(var_name: str, value: str) -> None:
        """
        Set environment variable.
        
        Args:
            var_name: Environment variable name
            value: Value to set
        """
        os.environ[var_name] = value
    
    @staticmethod
    def get_user_home() -> Path:
        """
        Get user home directory.
        
        Returns:
            Path to user home directory
        """
        return Path.home()
    
    @staticmethod
    def get_current_user() -> str:
        """
        Get current username.
        
        Returns:
            Current username
        """
        import getpass
        return getpass.getuser()
    
    @staticmethod
    def check_disk_space(path: Path, min_gb: float = 1.0) -> Tuple[bool, Dict[str, Any]]:
        """
        Check available disk space.
        
        Args:
            path: Path to check
            min_gb: Minimum required space in GB
            
        Returns:
            Tuple of (sufficient_space, disk_info)
        """
        try:
            import shutil
            
            total, used, free = shutil.disk_usage(path)
            
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)
            
            disk_info = {
                'total_gb': round(total_gb, 2),
                'used_gb': round(used_gb, 2),
                'free_gb': round(free_gb, 2),
                'used_percent': round((used_gb / total_gb) * 100, 1)
            }
            
            sufficient = free_gb >= min_gb
            
            return sufficient, disk_info
            
        except Exception as e:
            console.print(f"[red]❌ Error checking disk space: {e}[/red]")
            return False, {}
    
    @staticmethod
    def wait_for_port(port: int, host: str = 'localhost', timeout: int = 30) -> bool:
        """
        Wait for a port to become available or occupied.
        
        Args:
            port: Port number to wait for
            host: Host to check
            timeout: Timeout in seconds
            
        Returns:
            bool: True if port became available within timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if not SystemUtils.is_port_free(port, host):
                return True
            time.sleep(0.5)
        
        return False
    
    @staticmethod
    def create_symlink(source: Path, target: Path, force: bool = False) -> bool:
        """
        Create symbolic link.
        
        Args:
            source: Source file/directory
            target: Target link path
            force: Whether to overwrite existing link
            
        Returns:
            bool: True if symlink created successfully
        """
        try:
            if target.exists() or target.is_symlink():
                if not force:
                    console.print(f"[yellow]⚠️ Target already exists: {target}[/yellow]")
                    return False
                
                # Remove existing target
                if target.is_dir() and not target.is_symlink():
                    target.rmdir()
                else:
                    target.unlink()
            
            # Ensure parent directory exists
            target.parent.mkdir(parents=True, exist_ok=True)
            
            # Create symlink
            target.symlink_to(source)
            
            console.print(f"[green]✅ Created symlink: {target} -> {source}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error creating symlink {target} -> {source}: {e}[/red]")
            return False
    
    @staticmethod
    def get_process_info(pid: int) -> Optional[Dict[str, Any]]:
        """
        Get information about a process.
        
        Args:
            pid: Process ID
            
        Returns:
            Dict containing process information or None if not found
        """
        try:
            import psutil
            
            process = psutil.Process(pid)
            
            return {
                'pid': process.pid,
                'name': process.name(),
                'status': process.status(),
                'cpu_percent': process.cpu_percent(),
                'memory_percent': process.memory_percent(),
                'create_time': process.create_time(),
                'cmdline': process.cmdline()
            }
            
        except psutil.NoSuchProcess:
            return None
        except Exception as e:
            console.print(f"[yellow]⚠️ Error getting process info for PID {pid}: {e}[/yellow]")
            return None
    
    @staticmethod
    def cleanup_temp_files(temp_dir: Path, max_age_hours: int = 24) -> int:
        """
        Clean up temporary files older than specified age.
        
        Args:
            temp_dir: Temporary directory to clean
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of files cleaned up
        """
        try:
            if not temp_dir.exists():
                return 0
            
            cutoff_time = time.time() - (max_age_hours * 3600)
            files_removed = 0
            
            for file_path in temp_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        if file_path.stat().st_mtime < cutoff_time:
                            file_path.unlink()
                            files_removed += 1
                    except Exception:
                        pass  # Skip files we can't process
            
            if files_removed > 0:
                console.print(f"[green]✅ Cleaned up {files_removed} temporary files[/green]")
            
            return files_removed
            
        except Exception as e:
            console.print(f"[red]❌ Error cleaning temp files: {e}[/red]")
            return 0
"""
Tmux Messaging Module

Handles inter-agent communication through tmux sessions. Provides reliable
message delivery with monitoring and compliance checking.
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.console import Console

console = Console()


class TmuxMessenger:
    """
    Handles messaging between agents in tmux sessions.
    
    Features:
    - Reliable message delivery with Enter key handling
    - Message monitoring and logging
    - Window name resolution to prevent targeting errors
    - Hub-and-spoke communication enforcement
    - Message compliance checking
    """
    
    def __init__(self, tmux_orchestrator_path: Path):
        """
        Initialize tmux messenger.
        
        Args:
            tmux_orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.send_script = tmux_orchestrator_path / 'send-claude-message.sh'
        
        # Message monitoring
        self.message_history: List[Dict[str, Any]] = []
    
    def send_message(self, target: str, message: str, use_monitoring: bool = True) -> bool:
        """
        Send a message to a tmux target with proper Enter key handling.
        
        Args:
            target: Target in format 'session:window' or 'session:role_name'
            message: Message to send
            use_monitoring: Whether to use monitored messaging for compliance
            
        Returns:
            bool: True if message was sent successfully
        """
        try:
            # Clean message from any MCP wrapper syntax
            cleaned_message = self._clean_message_from_mcp_wrappers(message)
            
            if use_monitoring and self.send_script.exists():
                # Use monitored messaging script
                result = subprocess.run([
                    str(self.send_script), target, cleaned_message
                ], capture_output=True, text=True, timeout=30)
                
                success = result.returncode == 0
                if not success:
                    console.print(f"[yellow]⚠️  Monitored messaging failed, falling back to direct send[/yellow]")
                    success = self._send_direct(target, cleaned_message)
            else:
                # Direct tmux send
                success = self._send_direct(target, cleaned_message)
            
            # Log message
            if success:
                self._log_message(target, message, success=True)
                console.print(f"[green]✓ Message sent to {target}[/green]")
            else:
                self._log_message(target, message, success=False)
                console.print(f"[red]❌ Failed to send message to {target}[/red]")
            
            return success
            
        except Exception as e:
            console.print(f"[red]❌ Error sending message to {target}: {e}[/red]")
            self._log_message(target, message, success=False, error=str(e))
            return False
    
    def send_command(self, target: str, command: str) -> bool:
        """
        Send a command to a tmux target.
        
        Args:
            target: Target in format 'session:window'
            command: Command to execute
            
        Returns:
            bool: True if command was sent successfully
        """
        try:
            result = subprocess.run([
                'tmux', 'send-keys', '-t', target, command, 'Enter'
            ], capture_output=True, text=True)
            
            success = result.returncode == 0
            if success:
                console.print(f"[green]✓ Command sent to {target}: {command}[/green]")
            else:
                console.print(f"[red]❌ Failed to send command to {target}: {result.stderr}[/red]")
            
            return success
            
        except Exception as e:
            console.print(f"[red]❌ Error sending command to {target}: {e}[/red]")
            return False
    
    def resolve_role_to_window(self, session_name: str, role_name: str) -> Optional[str]:
        """
        Resolve a role name to a window target.
        
        Args:
            session_name: Tmux session name
            role_name: Role name to resolve (e.g., 'Developer', 'Tester')
            
        Returns:
            Optional[str]: Window target (session:window) or None if not found
        """
        try:
            # Get list of windows with their names
            result = subprocess.run([
                'tmux', 'list-windows', '-t', session_name, '-F',
                '#{window_index}:#{window_name}'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                return None
            
            # Find matching window
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    window_index, window_name = line.split(':', 1)
                    if window_name.lower() == role_name.lower():
                        return f"{session_name}:{window_index}"
                    
                    # Also try with common variations
                    role_variations = [
                        role_name.lower().replace('-', '_'),
                        role_name.lower().replace('_', '-'),
                        role_name.title(),
                        role_name.title().replace('_', '-')
                    ]
                    
                    if window_name.lower() in [v.lower() for v in role_variations]:
                        return f"{session_name}:{window_index}"
            
            return None
            
        except Exception as e:
            console.print(f"[yellow]⚠️  Error resolving role {role_name}: {e}[/yellow]")
            return None
    
    def broadcast_message(self, session_name: str, message: str, exclude_windows: List[int] = None) -> Dict[int, bool]:
        """
        Broadcast a message to all windows in a session.
        
        Args:
            session_name: Session to broadcast to
            message: Message to broadcast
            exclude_windows: Window indices to exclude
            
        Returns:
            Dict mapping window index to success status
        """
        exclude_windows = exclude_windows or []
        results = {}
        
        try:
            # Get list of windows
            result = subprocess.run([
                'tmux', 'list-windows', '-t', session_name, '-F', '#{window_index}'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                console.print(f"[red]❌ Failed to list windows for {session_name}[/red]")
                return results
            
            # Send to each window
            for line in result.stdout.strip().split('\n'):
                if line and line.isdigit():
                    window_index = int(line)
                    if window_index not in exclude_windows:
                        target = f"{session_name}:{window_index}"
                        success = self.send_message(target, message)
                        results[window_index] = success
            
            successful_sends = sum(1 for success in results.values() if success)
            console.print(f"[green]✓ Broadcast complete: {successful_sends}/{len(results)} messages sent[/green]")
            
        except Exception as e:
            console.print(f"[red]❌ Error broadcasting to {session_name}: {e}[/red]")
        
        return results
    
    def create_messaging_helpers(self, 
                                role: str, 
                                worktree_path: Path, 
                                session_name: str) -> bool:
        """
        Create helper scripts for agents to message other roles easily.
        
        Args:
            role: Current role name
            worktree_path: Path to role's worktree
            session_name: Session name for messaging
            
        Returns:
            bool: True if helper scripts were created successfully
        """
        try:
            scripts_dir = worktree_path / 'scripts'
            scripts_dir.mkdir(exist_ok=True)
            
            # Common roles that might be present
            common_roles = [
                'Orchestrator', 'Project-Manager', 'Developer', 'Tester', 'TestRunner',
                'Researcher', 'DevOps', 'SysAdmin', 'SecurityOps', 'NetworkOps',
                'MonitoringOps', 'DatabaseOps'
            ]
            
            # Create individual messaging scripts for each role
            for target_role in common_roles:
                if target_role.lower() == role.lower():
                    continue  # Skip self-messaging script
                
                script_name = f"msg_{target_role.lower().replace('-', '_')}.sh"
                script_path = scripts_dir / script_name
                
                script_content = f"""#!/bin/bash
# Quick messaging script for {target_role}
# Usage: ./{script_name} "Your message"

if [ $# -eq 0 ]; then
    echo "Usage: $0 \"Your message\""
    echo "Send a message to {target_role}"
    exit 1
fi

# Use the smart messaging command that resolves role names
scm {session_name}:{target_role} "$1"
"""
                
                script_path.write_text(script_content)
                script_path.chmod(0o755)
            
            # Create general messaging script
            general_script = scripts_dir / 'msg.sh'
            general_script.write_text(f"""#!/bin/bash
# General messaging script
# Usage: ./msg.sh RoleName "Your message"

if [ $# -lt 2 ]; then
    echo "Usage: $0 RoleName \"Your message\""
    echo "Available roles: {', '.join(common_roles)}"
    exit 1
fi

ROLE="$1"
MESSAGE="$2"

scm {session_name}:$ROLE "$MESSAGE"
""")
            general_script.chmod(0o755)
            
            # Create team list script
            list_script = scripts_dir / 'list_team.sh'
            list_script.write_text(f"""#!/bin/bash
# List all team members and their window assignments

echo "Team Members for {session_name}:"
echo "=================================="
tmux list-windows -t {session_name} -F '#{{window_index}}: #{{window_name}}'
""")
            list_script.chmod(0o755)
            
            console.print(f"[green]✓ Created messaging helper scripts for {role} in {scripts_dir}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[yellow]⚠️  Failed to create messaging helpers for {role}: {e}[/yellow]")
            return False
    
    def get_message_history(self, target: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get message history.
        
        Args:
            target: Optional target to filter by
            limit: Maximum number of messages to return
            
        Returns:
            List of message dictionaries
        """
        messages = self.message_history
        
        if target:
            messages = [msg for msg in messages if msg['target'] == target]
        
        return messages[-limit:]
    
    def clear_message_history(self) -> None:
        """Clear message history."""
        self.message_history.clear()
        console.print("[green]✓ Message history cleared[/green]")
    
    def _send_direct(self, target: str, message: str) -> bool:
        """Send message directly using tmux send-keys."""
        try:
            # Send message text
            result1 = subprocess.run([
                'tmux', 'send-keys', '-t', target, message
            ], capture_output=True, text=True)
            
            if result1.returncode != 0:
                return False
            
            # Send Enter key separately to ensure it's sent
            result2 = subprocess.run([
                'tmux', 'send-keys', '-t', target, 'Enter'
            ], capture_output=True, text=True)
            
            return result2.returncode == 0
            
        except Exception:
            return False
    
    def _clean_message_from_mcp_wrappers(self, message: str) -> str:
        """
        Clean message from MCP wrapper syntax that might cause issues.
        
        Args:
            message: Raw message text
            
        Returns:
            str: Cleaned message text
        """
        # Remove common MCP wrapper patterns
        cleaned = message.strip()
        
        # Remove backticks at start/end if they wrap the entire message
        if cleaned.startswith('`') and cleaned.endswith('`') and cleaned.count('`') == 2:
            cleaned = cleaned[1:-1].strip()
        
        # Remove triple backticks if they wrap the entire message
        if cleaned.startswith('```') and cleaned.endswith('```'):
            lines = cleaned.split('\n')
            if len(lines) >= 2:
                cleaned = '\n'.join(lines[1:-1]).strip()
        
        # Escape special characters that might cause tmux issues
        cleaned = cleaned.replace('"', '\\"')
        cleaned = cleaned.replace('$', '\\$')
        cleaned = cleaned.replace('`', '\\`')
        
        return cleaned
    
    def _log_message(self, target: str, message: str, success: bool, error: Optional[str] = None) -> None:
        """Log a message for history and monitoring."""
        log_entry = {
            'timestamp': time.time(),
            'target': target,
            'message': message[:100] + ('...' if len(message) > 100 else ''),  # Truncate long messages
            'success': success,
            'error': error
        }
        
        self.message_history.append(log_entry)
        
        # Keep only recent history to prevent memory bloat
        if len(self.message_history) > 1000:
            self.message_history = self.message_history[-500:]
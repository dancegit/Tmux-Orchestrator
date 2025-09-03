"""
MCP (Model Context Protocol) Manager

This module handles MCP configuration management, including .mcp.json creation,
MCP server configuration, and MCP tools availability detection.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.console import Console

console = Console()


class MCPManager:
    """
    Manages MCP configuration and server setup.
    
    Handles creation and management of .mcp.json files, MCP server configurations,
    and provides utilities for MCP tools detection and management.
    """
    
    def __init__(self):
        """Initialize the MCP manager."""
        pass
    
    def create_mcp_config(self, worktree_path: Path, role: str, project_config: Dict[str, Any] = None) -> bool:
        """
        Create .mcp.json configuration file for a specific role.
        
        This creates a role-specific MCP configuration that includes:
        - Tmux MCP server for session management
        - Context7 for technical documentation
        - Role-specific MCP tools based on agent responsibilities
        
        Args:
            worktree_path: Path to the agent's worktree
            role: Agent role (orchestrator, developer, tester, etc.)
            project_config: Optional project-specific configuration
            
        Returns:
            bool: True if configuration was created successfully
        """
        try:
            mcp_config = self._generate_role_mcp_config(role, project_config)
            
            mcp_file_path = worktree_path / '.mcp.json'
            with open(mcp_file_path, 'w') as f:
                json.dump(mcp_config, f, indent=2)
            
            console.print(f"[green]✓ Created MCP config for {role} at {mcp_file_path}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Failed to create MCP config for {role}: {e}[/red]")
            return False
    
    def _generate_role_mcp_config(self, role: str, project_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate role-specific MCP configuration.
        
        Args:
            role: Agent role
            project_config: Project-specific settings
            
        Returns:
            Dict containing MCP configuration
        """
        # Base configuration common to all roles
        base_config = {
            "mcpServers": {
                "tmux-mcp": {
                    "command": "npm",
                    "args": ["exec", "tmux-mcp", "--shell-type=bash"],
                    "env": {}
                },
                "context7": {
                    "command": "npm",
                    "args": ["exec", "@upstash/context7-mcp@latest"],
                    "env": {}
                }
            }
        }
        
        # Add role-specific MCP servers
        role_specific = self._get_role_specific_mcp_servers(role, project_config)
        base_config["mcpServers"].update(role_specific)
        
        return base_config
    
    def _get_role_specific_mcp_servers(self, role: str, project_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get MCP servers specific to an agent role.
        
        Args:
            role: Agent role
            project_config: Project configuration
            
        Returns:
            Dict of role-specific MCP servers
        """
        role_servers = {}
        
        # Developer-specific MCP tools
        if role == 'developer':
            role_servers.update({
                "brave-search": {
                    "command": "npm",
                    "args": ["exec", "brave-search-mcp"],
                    "env": {}
                }
            })
        
        # Researcher-specific MCP tools  
        elif role == 'researcher':
            role_servers.update({
                "brave-search": {
                    "command": "npm", 
                    "args": ["exec", "brave-search-mcp"],
                    "env": {}
                },
                "web-search": {
                    "command": "npm",
                    "args": ["exec", "web-search-mcp"], 
                    "env": {}
                }
            })
        
        # Tester-specific MCP tools
        elif role == 'tester':
            role_servers.update({
                "playwright": {
                    "command": "npm",
                    "args": ["exec", "playwright-mcp"],
                    "env": {}
                }
            })
        
        # System operations roles
        elif role in ['sysadmin', 'devops', 'securityops']:
            role_servers.update({
                "system-tools": {
                    "command": "npm", 
                    "args": ["exec", "system-tools-mcp"],
                    "env": {}
                }
            })
        
        # Project-specific MCP servers
        if project_config:
            project_servers = project_config.get('mcp_servers', {})
            role_servers.update(project_servers)
        
        return role_servers
    
    def verify_mcp_availability(self, worktree_path: Path) -> bool:
        """
        Verify that MCP configuration exists and is valid.
        
        Args:
            worktree_path: Path to check for MCP configuration
            
        Returns:
            bool: True if MCP is properly configured
        """
        mcp_file = worktree_path / '.mcp.json'
        
        if not mcp_file.exists():
            console.print(f"[yellow]⚠️ No .mcp.json found at {worktree_path}[/yellow]")
            return False
        
        try:
            with open(mcp_file, 'r') as f:
                config = json.load(f)
            
            # Basic validation
            if 'mcpServers' not in config:
                console.print(f"[red]❌ Invalid MCP config: missing mcpServers[/red]")
                return False
            
            server_count = len(config['mcpServers'])
            console.print(f"[green]✓ Valid MCP config with {server_count} servers[/green]")
            return True
            
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ Invalid JSON in .mcp.json: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Error reading MCP config: {e}[/red]")
            return False
    
    def get_mcp_tools_info(self, role: str) -> str:
        """
        Get formatted information about available MCP tools for a role.
        
        Args:
            role: Agent role
            
        Returns:
            str: Formatted MCP tools information for briefings
        """
        role_tools = self._get_role_mcp_tools_description(role)
        
        if not role_tools:
            return "**MCP Tools**: No role-specific MCP tools configured for this role."
        
        return f"""**MCP Tools Available**:
{role_tools}

**Using MCP Tools**:
- Type `@` to see available MCP resources
- Type `/mcp__` to see MCP commands
- Use MCP tools for enhanced capabilities in your role"""
    
    def _get_role_mcp_tools_description(self, role: str) -> str:
        """
        Get description of MCP tools available for a specific role.
        
        Args:
            role: Agent role
            
        Returns:
            str: Description of available tools
        """
        descriptions = {
            'orchestrator': "- Tmux session management\n- Context7 for technical documentation\n- System monitoring and control",
            'developer': "- Brave search for technical solutions\n- Context7 for framework documentation\n- Tmux for coordination",
            'researcher': "- Brave search for comprehensive research\n- Web search for current information\n- Context7 for technical depth",
            'tester': "- Playwright for browser automation testing\n- Context7 for testing frameworks\n- Tmux for test coordination", 
            'sysadmin': "- System tools for administration\n- Context7 for system documentation\n- Tmux for system coordination",
            'devops': "- System tools for deployment automation\n- Context7 for DevOps best practices\n- Tmux for pipeline management",
            'securityops': "- System tools for security configuration\n- Context7 for security documentation\n- Tmux for security coordination"
        }
        
        return descriptions.get(role, "- Tmux session management\n- Context7 for documentation")
    
    def cleanup_mcp_config(self, worktree_path: Path) -> bool:
        """
        Clean up MCP configuration files.
        
        Args:
            worktree_path: Path to clean up
            
        Returns:
            bool: True if cleanup was successful
        """
        try:
            mcp_file = worktree_path / '.mcp.json'
            if mcp_file.exists():
                mcp_file.unlink()
                console.print(f"[green]✓ Cleaned up MCP config at {worktree_path}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Failed to cleanup MCP config: {e}[/red]")
            return False
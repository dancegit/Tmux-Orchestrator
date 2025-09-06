"""
Claude Initialization Module

CRITICAL MODULE: Contains the complete Claude startup and MCP initialization sequence
with OAuth port timing logic. This module handles the complex two-phase Claude startup:

1. Start Claude → Accept .mcp.json → Exit
2. Start Claude with --dangerously-skip-permissions 

All timing sequences in this module have been calibrated for batch processing
reliability and MUST be preserved.
"""

import os
import subprocess
import time
from pathlib import Path
from rich.console import Console

from .oauth_manager import OAuthManager
from .mcp_manager import MCPManager

console = Console()


class ClaudeInitializer:
    """
    Handles Claude initialization with MCP configuration.
    
    CRITICAL: This class contains the complete MCP initialization sequence
    that prevents OAuth port conflicts during batch processing.
    """
    
    def __init__(self):
        """Initialize the Claude initializer with OAuth and MCP managers."""
        self.oauth_manager = OAuthManager()
        self.mcp_manager = MCPManager()
    
    def initialize_claude_with_mcp(self, session_name: str, window_idx: int, role_key: str) -> bool:
        """
        Initialize Claude with MCP configuration in a tmux window.
        
        This function implements the critical two-phase Claude startup sequence:
        
        Phase 1: Claude accepts MCP configuration
        - Start Claude (without --dangerously-skip-permissions)
        - Wait for Claude to fully initialize
        - Send MCP configuration acceptance
        - Exit Claude cleanly
        - Wait for OAuth port release (CRITICAL 60-second timeout)
        
        Phase 2: Claude starts with MCP enabled
        - Start Claude with --dangerously-skip-permissions
        - MCP tools are now available
        
        CRITICAL: All timeouts in this sequence have been calibrated for batch
        processing and must not be reduced without comprehensive testing.
        
        Args:
            session_name: Tmux session name
            window_idx: Window index for the agent
            role_key: Role identifier (for logging)
            
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        # Pre-flight check: Ensure OAuth port is available
        if not self.oauth_manager.check_batch_processing_conflict(f"{session_name}:{window_idx}"):
            return False
        
        console.print(f"[blue]🚀 Starting MCP initialization for {role_key}...[/blue]")
        
        # Phase 1: Start Claude and configure MCP
        success = self._phase1_mcp_configuration(session_name, window_idx, role_key)
        if not success:
            console.print(f"[red]❌ Phase 1 (MCP configuration) failed for {role_key}[/red]")
            return False
        
        # Phase 2: Start Claude with MCP enabled
        success = self._phase2_claude_with_mcp(session_name, window_idx, role_key)
        if not success:
            console.print(f"[red]❌ Phase 2 (Claude with MCP) failed for {role_key}[/red]")
            return False
        
        console.print(f"[green]✅ MCP initialization complete for {role_key}[/green]")
        return True
    
    def initialize_claude_with_preapproved_mcp(self, session_name: str, window_idx: int, role_key: str, worktree_path: str) -> bool:
        """
        IMPROVED: Initialize Claude with pre-approved MCP configuration.
        
        This method uses the simplified approach with settings.local.json pre-approval:
        
        1. Ensure .claude directory exists in worktree
        2. Copy pre-approved settings.local.json to worktree/.claude/
        3. Start Claude with --dangerously-skip-permissions
        4. MCP tools are immediately available (no manual approval needed)
        
        This eliminates the complex two-phase initialization and OAuth timing issues.
        
        Args:
            session_name: Tmux session name
            window_idx: Window index for the agent
            role_key: Role identifier (for logging)
            worktree_path: Path to agent's worktree directory
            
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        console.print(f"[blue]🚀 Starting simplified MCP initialization for {role_key}...[/blue]")
        
        # Step 1: Set up pre-approved MCP settings
        success = self._setup_preapproved_mcp_settings(worktree_path, role_key)
        if not success:
            console.print(f"[red]❌ Failed to setup MCP settings for {role_key}[/red]")
            return False
        
        # Step 2: Start Claude with --dangerously-skip-permissions
        success = self._start_claude_with_mcp(session_name, window_idx, role_key)
        if not success:
            console.print(f"[red]❌ Failed to start Claude for {role_key}[/red]")
            return False
            
        console.print(f"[green]✅ Simplified MCP initialization complete for {role_key}[/green]")
        return True
    
    def _setup_preapproved_mcp_settings(self, worktree_path: str, role_key: str) -> bool:
        """Set up pre-approved MCP settings in agent worktree."""
        import json
        import shutil
        from pathlib import Path
        
        try:
            worktree = Path(worktree_path)
            claude_dir = worktree / ".claude"
            settings_file = claude_dir / "settings.local.json"
            
            # Create .claude directory
            claude_dir.mkdir(exist_ok=True)
            
            # Master settings path
            master_settings = Path("/home/clauderun/Tmux-Orchestrator/.claude/settings.local.json")
            
            if master_settings.exists():
                shutil.copy2(master_settings, settings_file)
                console.print(f"[blue]📋 Copied master MCP settings to {role_key} worktree[/blue]")
            else:
                # Default MCP configuration
                default_config = {
                    "enabledMcpjsonServers": [
                        "grok", "tmux", "context7", "supabase", 
                        "brave-search", "puppeteer", "firecrawl", "playwright"
                    ],
                    "enableAllProjectMcpServers": True
                }
                
                with open(settings_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                console.print(f"[blue]📋 Created default MCP settings for {role_key}[/blue]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error setting up MCP settings for {role_key}: {e}[/red]")
            return False
    
    def _start_claude_with_mcp(self, session_name: str, window_idx: int, role_key: str) -> bool:
        """Start Claude with --dangerously-skip-permissions (MCP pre-approved)."""
        import subprocess
        import time
        
        try:
            # Start Claude with --dangerously-skip-permissions
            subprocess.run([
                'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
                'claude --dangerously-skip-permissions', 'Enter'
            ])
            
            console.print(f"[blue]⚡ Starting Claude with pre-approved MCP for {role_key}...[/blue]")
            
            # Brief wait for Claude startup (much shorter than the old method)
            time.sleep(5)
            
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Error starting Claude for {role_key}: {e}[/red]")
            return False
    
    def _phase1_mcp_configuration(self, session_name: str, window_idx: int, role_key: str) -> bool:
        """
        Phase 1: Start Claude and accept MCP configuration.
        
        This phase handles:
        1. Starting Claude normally (OAuth server starts on port 3000)
        2. Waiting for Claude full initialization (30s timeout)
        3. Sending MCP configuration acceptance
        4. Clean exit from Claude
        5. Critical OAuth port release wait (60s timeout)
        
        Args:
            session_name: Tmux session name
            window_idx: Window index
            role_key: Role identifier
            
        Returns:
            bool: True if phase completed successfully
        """
        console.print(f"[blue]Phase 1: Configuring MCP for {role_key}...[/blue]")
        
        # Start Claude normally (without --dangerously-skip-permissions)
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            'claude', 'Enter'
        ])
        
        # Critical wait for Claude initialization
        # This timeout accounts for:
        # - Claude binary startup (3-5 seconds)
        # - OAuth server initialization (5-10 seconds) 
        # - MCP discovery and loading (10-15 seconds)
        # - Network initialization in containers (additional buffer)
        console.print(f"[yellow]⏳ Waiting for Claude to initialize (30s timeout)...[/yellow]")
        time.sleep(30)
        
        # Send MCP configuration acceptance
        # The 'y' confirms acceptance of .mcp.json configuration
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            'y', 'Enter'
        ])
        
        console.print(f"[blue]📝 MCP configuration accepted, waiting for processing...[/blue]")
        
        # Wait for MCP configuration processing
        # This allows Claude to:
        # - Parse and validate .mcp.json
        # - Download and initialize MCP servers
        # - Establish MCP connections
        time.sleep(10)
        
        # Exit Claude cleanly
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            '/exit', 'Enter'
        ])
        
        # Wait for the exit command to be processed
        time.sleep(2)
        
        # CRITICAL: Wait for OAuth server shutdown after Claude exit
        success = self.oauth_manager.wait_after_claude_exit(max_wait=60)
        
        if success:
            console.print(f"[green]✓ Phase 1 completed successfully for {role_key}[/green]")
        else:
            console.print(f"[red]❌ Phase 1 failed - OAuth port not released for {role_key}[/red]")
        
        return success
    
    def _phase2_claude_with_mcp(self, session_name: str, window_idx: int, role_key: str) -> bool:
        """
        Phase 2: Start Claude with MCP tools enabled.
        
        This phase starts Claude with --dangerously-skip-permissions flag,
        which enables MCP tools configured in Phase 1.
        
        Args:
            session_name: Tmux session name  
            window_idx: Window index
            role_key: Role identifier
            
        Returns:
            bool: True if Claude started successfully with MCP
        """
        console.print(f"[blue]Phase 2: Starting Claude with MCP enabled for {role_key}...[/blue]")
        
        # Start Claude with MCP tools enabled
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            'claude --dangerously-skip-permissions', 'Enter'
        ])
        
        # Allow time for Claude to start and establish MCP connections
        # This timeout accounts for:
        # - Claude startup with MCP tools (10-15 seconds)
        # - MCP server connections (5-10 seconds)
        # - OAuth server re-initialization (5-10 seconds)
        console.print(f"[yellow]⏳ Waiting for Claude with MCP to initialize (20s)...[/yellow]")
        time.sleep(20)
        
        console.print(f"[green]✅ Phase 2 completed - Claude with MCP is ready for {role_key}[/green]")
        return True
    
    def restart_claude_in_window(self, session_name: str, window_idx: int, window_name: str, worktree_path: str) -> bool:
        """
        Restart Claude in an existing tmux window with full MCP initialization.
        
        This function handles the complete window restart sequence:
        1. Kill the existing window
        2. Wait for OAuth port release (CRITICAL)
        3. Create new window
        4. Initialize Claude with MCP
        
        Args:
            session_name: Tmux session name
            window_idx: Window index to restart
            window_name: Name for the new window
            worktree_path: Working directory path
            
        Returns:
            bool: True if restart succeeded
        """
        console.print(f"[blue]🔄 Restarting Claude in window {session_name}:{window_idx}...[/blue]")
        
        # Kill the existing window
        subprocess.run([
            'tmux', 'kill-window', '-t', f'{session_name}:{window_idx}'
        ], capture_output=True)
        
        # CRITICAL: Wait for OAuth port release after window kill
        success = self.oauth_manager.wait_after_window_kill(max_wait=45)
        if not success:
            console.print(f"[yellow]⚠️ Continuing with potential port conflict...[/yellow]")
        
        # Create a new window at the same index
        subprocess.run([
            'tmux', 'new-window', '-t', f'{session_name}:{window_idx}',
            '-n', window_name, '-c', worktree_path
        ], capture_output=True)
        
        # Initialize Claude with MCP in the new window
        return self.initialize_claude_with_mcp(session_name, window_idx, f"{window_name}")
    
    def simple_claude_start(self, session_name: str, window_idx: int) -> bool:
        """
        Start Claude without MCP initialization (fallback method).
        
        This method is used when MCP initialization fails or is not needed.
        It only starts Claude with the --dangerously-skip-permissions flag.
        
        Args:
            session_name: Tmux session name
            window_idx: Window index
            
        Returns:
            bool: True if Claude started successfully
        """
        console.print(f"[blue]Starting Claude (simple mode) in {session_name}:{window_idx}...[/blue]")
        
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            'claude --dangerously-skip-permissions', 'Enter'
        ])
        
        # Basic wait for Claude startup
        time.sleep(10)
        
        console.print(f"[green]✓ Claude started in simple mode[/green]")
        return True
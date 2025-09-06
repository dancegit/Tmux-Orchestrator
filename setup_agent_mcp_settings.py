#!/usr/bin/env python3
"""
Improved Agent MCP Setup Script

This script implements the improved MCP initialization approach using pre-approved
settings.local.json files instead of the complex two-phase initialization process.

Instead of:
1. Start Claude normally
2. Wait for initialization 
3. Accept MCP configuration
4. Exit Claude
5. Wait for OAuth cleanup
6. Start Claude with --dangerously-skip-permissions

We now simply:
1. Copy pre-approved settings.local.json to agent .claude directory
2. Start Claude with --dangerously-skip-permissions

This eliminates the complex timing and OAuth port conflict issues.
"""

import os
import shutil
import json
from pathlib import Path
from typing import List, Dict, Any

class AgentMCPSetup:
    """Simplified MCP setup using pre-approved settings files."""
    
    def __init__(self, orchestrator_path: str = "/home/clauderun/Tmux-Orchestrator"):
        self.orchestrator_path = Path(orchestrator_path)
        self.master_settings_path = self.orchestrator_path / ".claude" / "settings.local.json"
        
        # Default MCP servers configuration
        self.default_mcp_config = {
            "enabledMcpjsonServers": [
                "grok",
                "tmux", 
                "context7",
                "supabase",
                "brave-search",
                "puppeteer",
                "firecrawl",
                "playwright"
            ],
            "enableAllProjectMcpServers": True
        }
    
    def setup_agent_mcp_settings(self, worktree_path: str, agent_name: str) -> bool:
        """
        Set up MCP settings for a single agent worktree.
        
        Args:
            worktree_path: Path to the agent's worktree directory
            agent_name: Name of the agent (for logging)
            
        Returns:
            bool: True if setup successful, False otherwise
        """
        try:
            worktree = Path(worktree_path)
            claude_dir = worktree / ".claude"
            settings_file = claude_dir / "settings.local.json"
            
            # Create .claude directory if it doesn't exist
            claude_dir.mkdir(exist_ok=True)
            
            # Use master settings if available, otherwise use default
            if self.master_settings_path.exists():
                shutil.copy2(self.master_settings_path, settings_file)
                print(f"✅ Copied master MCP settings to {agent_name}")
            else:
                # Write default configuration
                with open(settings_file, 'w') as f:
                    json.dump(self.default_mcp_config, f, indent=2)
                print(f"✅ Created default MCP settings for {agent_name}")
                
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup MCP settings for {agent_name}: {e}")
            return False
    
    def setup_all_agents_in_session(self, session_worktree_base: str, agent_names: List[str]) -> Dict[str, bool]:
        """
        Set up MCP settings for all agents in a tmux orchestrator session.
        
        Args:
            session_worktree_base: Base path to session worktrees (e.g., ~/project-name-tmux-worktrees)
            agent_names: List of agent directory names
            
        Returns:
            Dict mapping agent names to success status
        """
        results = {}
        base_path = Path(session_worktree_base)
        
        for agent in agent_names:
            agent_path = base_path / agent
            if agent_path.exists():
                results[agent] = self.setup_agent_mcp_settings(str(agent_path), agent)
            else:
                print(f"⚠️  Agent directory not found: {agent_path}")
                results[agent] = False
                
        return results
    
    def setup_vso_android_session(self) -> Dict[str, bool]:
        """Set up MCP settings for the current VSO Android session."""
        session_base = Path.home() / "vso-monitor-android-app-20250906-163029-tmux-worktrees"
        agents = ["developer", "tester", "testrunner", "project_manager"]
        
        print("🚀 Setting up MCP settings for VSO Monitor Android session...")
        results = self.setup_all_agents_in_session(str(session_base), agents)
        
        success_count = sum(1 for success in results.values() if success)
        print(f"📊 Setup completed: {success_count}/{len(agents)} agents configured")
        
        return results

def main():
    """Main function for standalone execution."""
    setup = AgentMCPSetup()
    
    # Set up current VSO session
    results = setup.setup_vso_android_session()
    
    # Print summary
    print("\n📋 Setup Summary:")
    for agent, success in results.items():
        status = "✅ Success" if success else "❌ Failed"
        print(f"  {agent}: {status}")

if __name__ == "__main__":
    main()
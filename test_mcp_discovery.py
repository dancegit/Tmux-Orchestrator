#!/usr/bin/env python3
"""Test script for MCP discovery functionality"""

import json
import tempfile
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from auto_orchestrate import AutoOrchestrator

def test_mcp_discovery():
    """Test MCP discovery with sample configurations"""
    
    # Create sample configurations
    sample_global_config = {
        "mcpServers": {
            "websearch": {
                "command": "mcp-server-websearch",
                "args": []
            },
            "firecrawl": {
                "command": "mcp-server-firecrawl",
                "args": ["--api-key", "test-key"]
            },
            "filesystem": {
                "command": "mcp-server-filesystem",
                "args": ["/tmp"]
            },
            "sqlite-db": {
                "command": "mcp-server-sqlite",
                "args": ["test.db"]
            },
            "context7-knowledge": {
                "command": "mcp-server-context7",
                "args": []
            },
            "puppeteer-browser": {
                "command": "mcp-server-puppeteer",
                "args": []
            }
        }
    }
    
    sample_project_config = {
        "project-specific-db": {
            "command": "mcp-server-sqlite",
            "args": ["project.db"]
        },
        "custom-api": {
            "command": "mcp-server-http",
            "args": ["--base-url", "https://api.example.com"]
        }
    }
    
    # Create temporary files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create fake project and spec paths
        project_path = tmppath / "test-project"
        project_path.mkdir()
        
        spec_path = tmppath / "spec.md"
        spec_path.write_text("# Test Spec")
        
        # Create test .mcp.json in project
        project_mcp = project_path / ".mcp.json"
        project_mcp.write_text(json.dumps(sample_project_config, indent=2))
        
        # Create AutoOrchestrator instance
        orchestrator = AutoOrchestrator(str(project_path), str(spec_path))
        
        # Test 1: Save and restore original ~/.claude.json
        home_claude = Path.home() / ".claude.json"
        original_content = None
        if home_claude.exists():
            original_content = home_claude.read_text()
            
        try:
            # Write sample global config
            home_claude.write_text(json.dumps(sample_global_config, indent=2))
            
            # Test discovery
            print("Testing MCP discovery...")
            mcp_info = orchestrator.discover_mcp_servers()
            
            print(f"\nDiscovered {len(mcp_info['servers'])} MCP servers")
            print(f"Project has .mcp.json: {mcp_info['project_has_mcp']}")
            
            # Test categorization
            print("\nTesting MCP categorization...")
            categories = orchestrator.categorize_mcp_tools(mcp_info['servers'])
            
            print("\nCategorized MCP tools:")
            for category, servers in categories.items():
                print(f"  {category}: {', '.join(servers)}")
            
            # Test role-specific guidance
            print("\nTesting role-specific guidance...")
            for role in ['orchestrator', 'developer', 'researcher', 'tester']:
                print(f"\n--- {role.upper()} ---")
                guidance = orchestrator.get_role_mcp_guidance(role, categories)
                print(guidance[:200] + "..." if len(guidance) > 200 else guidance)
            
        finally:
            # Restore original ~/.claude.json
            if original_content:
                home_claude.write_text(original_content)
            elif home_claude.exists():
                home_claude.unlink()
        
        print("\n✓ MCP discovery test completed successfully!")

if __name__ == "__main__":
    test_mcp_discovery()
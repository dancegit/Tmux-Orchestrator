"""Claude initialization and MCP management.

CRITICAL MODULE: Contains OAuth port timing logic that prevents
port 3000 conflicts during batch processing.
"""

__all__ = ["initialization", "mcp_manager", "oauth_manager"]
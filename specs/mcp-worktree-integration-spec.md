# MCP Tools in Git Worktrees - Integration Specification

## Problem Statement

MCP (Model Context Protocol) tools are not working in git worktrees created by `auto_orchestrate.py`. When agents are deployed to their isolated worktrees, they cannot access MCP tools that are configured in the parent project.

## Root Cause Analysis

### 1. Per-Directory Configuration
- Claude Code stores MCP server configurations per project directory in `~/.claude.json`
- Each directory path gets its own isolated configuration block
- No inheritance mechanism exists between parent and child directories

### 2. Worktrees as Separate Projects
- Git worktrees are treated as completely separate projects by Claude Code
- Example: `/home/per/gitrepos/SignalMatrix` (parent) vs `/home/per/gitrepos/Tmux-Orchestrator/registry/projects/stf-playwright-mcp-integration/worktrees/orchestrator` (worktree)
- Each gets its own entry in `~/.claude.json` with independent settings

### 3. Configuration Structure
```json
{
  "projects": {
    "/path/to/main/project": {
      "mcpServers": {
        "modal-mcp-server": { ... }
      },
      "enabledMcpjsonServers": ["server1", "server2"]
    },
    "/path/to/worktree": {
      "mcpServers": {},  // Empty!
      "enabledMcpjsonServers": []
    }
  }
}
```

## Current Behavior

1. `auto_orchestrate.py` creates worktrees for each agent
2. Copies `.mcp.json` file to each worktree (already implemented)
3. However, Claude Code doesn't automatically:
   - Enable servers defined in `.mcp.json`
   - Copy MCP configurations from parent project
   - Inherit any MCP settings

## Proposed Solutions

### Solution 1: Local .mcp.json Merging (Recommended)

**Approach**: Modify `auto_orchestrate.py` to merge parent project's MCP configurations into the local `.mcp.json` file in each worktree.

**Implementation Steps**:
1. Create `setup_mcp_for_worktree()` method that:
   - Reads parent project's MCP configuration from `~/.claude.json` (read-only)
   - Reads existing `.mcp.json` from project (if exists)
   - Merges the parent's `mcpServers` configuration with project `.mcp.json`
   - Writes the merged configuration to worktree's `.mcp.json`
   - Does NOT modify global `~/.claude.json`

**Pros**:
- No modification of user's global Claude configuration
- Self-contained MCP configuration per worktree
- Safer approach with no risk of corrupting global settings
- Each worktree has complete MCP configuration

**Cons**:
- Slightly larger `.mcp.json` files in worktrees
- Need to handle merge conflicts between configurations
- Configuration changes in parent won't auto-propagate

### Solution 2: Global MCP Configuration

**Approach**: Configure MCP servers globally in `~/.claude/settings.json` instead of per-project.

**Implementation Steps**:
1. Document how to move MCP configurations to global settings
2. Update documentation to recommend global configuration for orchestrated projects

**Pros**:
- Simple, no code changes needed
- Works across all projects and worktrees

**Cons**:
- Not all MCP servers should be global
- Requires manual user action
- May expose project-specific tools globally

### Solution 3: Claude Code Enhancement

**Approach**: Request Claude Code team to add worktree awareness or configuration inheritance.

**Feature Request**:
- Detect git worktrees and inherit parent repo's MCP configuration
- Add configuration option for MCP inheritance
- Support `.mcp.json` auto-enablement

**Pros**:
- Proper long-term solution
- Benefits all Claude Code users

**Cons**:
- Outside our control
- Timeline uncertain
- Need workaround in meantime

## Recommended Implementation Plan

### Phase 1: Immediate Fix
1. Implement `setup_mcp_for_worktree()` in `auto_orchestrate.py`
2. Read parent project's MCP config from `~/.claude.json` (read-only)
3. Merge configurations into worktree's `.mcp.json`
4. Test with various MCP configurations

### Phase 2: Enhanced Discovery
1. Improve MCP discovery to handle:
   - Global configurations in `~/.claude/settings.json`
   - Project-specific `.mcp.json`
   - Parent project's MCP servers from `~/.claude.json`
2. Create consolidated MCP inventory

### Phase 3: Documentation
1. Document MCP-worktree behavior
2. Explain the merge strategy
3. Create troubleshooting guide

## Technical Considerations

### JSON File Handling
- Read `~/.claude.json` safely (read-only access)
- Merge strategy for conflicting server names
- Validate JSON structure before writing
- Handle missing keys gracefully
- Create `.mcp.json` if it doesn't exist

### Merge Strategy
```python
# Pseudocode for merging MCP configurations
def merge_mcp_configs(parent_config, project_config):
    merged = {
        "mcpServers": {}
    }
    
    # Start with project config (if exists)
    if project_config and "mcpServers" in project_config:
        merged["mcpServers"].update(project_config["mcpServers"])
    
    # Add parent's MCP servers (from ~/.claude.json)
    if parent_config and "mcpServers" in parent_config:
        for server_name, server_config in parent_config["mcpServers"].items():
            if server_name not in merged["mcpServers"]:
                merged["mcpServers"][server_name] = server_config
    
    return merged
```

### MCP Server Types
- stdio servers (command-based)
- Different argument patterns
- Environment variables
- API keys and secrets

### Worktree Lifecycle
- Configuration merged when worktree created
- No cleanup needed (`.mcp.json` removed with worktree)
- Handle existing `.mcp.json` in worktrees

## Success Criteria

1. Agents in worktrees can access same MCP tools as parent project
2. No manual configuration required by users
3. Global `~/.claude.json` remains unmodified
4. Each worktree has self-contained MCP configuration
5. Clear documentation for troubleshooting

## Open Questions

1. How to handle MCP server name conflicts during merge?
   - Current approach: Project config takes precedence
2. Should we include global MCP servers from `~/.claude/settings.json`?
3. Should orchestrator have different MCP tools than other agents?
4. How to handle sensitive data (API keys) in MCP configurations?

## Next Steps

1. Prototype `setup_mcp_for_worktree()` method that:
   - Reads parent's MCP config from `~/.claude.json`
   - Merges with existing `.mcp.json`
   - Writes to worktree's `.mcp.json`
2. Test with real-world MCP configurations
3. Consider security implications of copying API keys
4. Document the merge behavior clearly

## Example Implementation

```python
def setup_mcp_for_worktree(self, worktree_path: Path, project_path: Path):
    """Merge parent project's MCP config into worktree's .mcp.json"""
    
    # Read parent project's MCP config from ~/.claude.json
    claude_json_path = Path.home() / '.claude.json'
    parent_mcp_servers = {}
    
    if claude_json_path.exists():
        with open(claude_json_path, 'r') as f:
            claude_config = json.load(f)
            project_key = str(project_path)
            if project_key in claude_config.get('projects', {}):
                parent_mcp_servers = claude_config['projects'][project_key].get('mcpServers', {})
    
    # Read existing .mcp.json from worktree
    worktree_mcp_path = worktree_path / '.mcp.json'
    existing_config = {}
    
    if worktree_mcp_path.exists():
        with open(worktree_mcp_path, 'r') as f:
            existing_config = json.load(f)
    
    # Merge configurations
    merged_config = {
        "mcpServers": {}
    }
    
    # Project config takes precedence
    if "mcpServers" in existing_config:
        merged_config["mcpServers"].update(existing_config["mcpServers"])
    
    # Add parent's servers that don't conflict
    for server_name, server_config in parent_mcp_servers.items():
        if server_name not in merged_config["mcpServers"]:
            merged_config["mcpServers"][server_name] = server_config
    
    # Write merged config
    with open(worktree_mcp_path, 'w') as f:
        json.dump(merged_config, f, indent=2)
```
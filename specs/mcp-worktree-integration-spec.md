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

### Solution 1: Programmatic Configuration Update (Recommended)

**Approach**: Modify `auto_orchestrate.py` to programmatically update `~/.claude.json` after creating worktrees.

**Implementation Steps**:
1. Create `setup_mcp_for_worktree()` method that:
   - Reads parent project's MCP configuration from `~/.claude.json`
   - Reads `.mcp.json` from project (if exists)
   - Updates `~/.claude.json` to add worktree configuration
   - Copies `mcpServers` from parent
   - Sets `enabledMcpjsonServers` based on `.mcp.json` content

**Pros**:
- Automatic and seamless for users
- Preserves exact parent configuration
- Works with both global and project-specific MCP servers

**Cons**:
- Requires modifying user's Claude configuration file
- Need to handle JSON parsing/writing carefully
- May need to handle concurrent access

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
2. Parse and update `~/.claude.json` safely
3. Test with various MCP configurations

### Phase 2: Enhanced Discovery
1. Improve MCP discovery to handle:
   - Global configurations in `~/.claude/settings.json`
   - Project-specific `.mcp.json`
   - Environment variable configured servers
2. Create consolidated MCP inventory

### Phase 3: Documentation
1. Document MCP-worktree behavior
2. Provide manual configuration steps as fallback
3. Create troubleshooting guide

## Technical Considerations

### JSON File Handling
- Need file locking to prevent corruption
- Backup before modification
- Validate JSON structure
- Handle missing keys gracefully

### MCP Server Types
- stdio servers (command-based)
- Different argument patterns
- Environment variables
- API keys and secrets

### Worktree Lifecycle
- Configuration when worktree created
- Cleanup when worktree removed
- Handle existing worktrees

## Success Criteria

1. Agents in worktrees can access same MCP tools as parent project
2. No manual configuration required by users
3. Existing Claude Code functionality preserved
4. Clear documentation for troubleshooting

## Open Questions

1. Should we preserve project-specific MCP configurations or merge with global?
2. How to handle MCP server conflicts between projects?
3. Should orchestrator have different MCP tools than other agents?
4. How to handle MCP configuration updates after worktree creation?

## Next Steps

1. Prototype `setup_mcp_for_worktree()` method
2. Test with real-world MCP configurations
3. Consider security implications of copying configurations
4. Get user feedback on preferred approach
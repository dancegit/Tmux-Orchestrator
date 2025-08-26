# Auto_orchestrate.py Bug Fixes

## Summary

Two critical bugs were fixed in `auto_orchestrate.py` based on the investigation of Project 69 (MCP Server V2) where the orchestrator's scheduled check-in never happened and the Project Manager got stuck at MCP prompts.

## Bug 1: Orchestrator Check-in Task Bug

### Problem
- The orchestrator's own window (window 0) never gets a scheduled check-in task created during setup
- Line 2929 explicitly excluded orchestrators with `if role_key != 'orchestrator':`
- This caused orchestrators to reference check-ins that never existed (e.g., "22:21" in Project 69)

### Solution
- Added CLI flag `--enable-orchestrator-scheduling` (default: False for backward compatibility)
- Modified the scheduling exclusion to be conditional based on the flag
- When enabled, orchestrator gets scheduled check-ins like other agents
- Default check-in interval: 30 minutes (configurable via role config)

### Usage
```bash
./auto_orchestrate.py --project /path --spec spec.md --enable-orchestrator-scheduling
```

## Bug 2: MCP Config Acceptance Bug

### Problem
- MCP pre-initialization only worked for agents with `.mcp.json` in their worktree
- Some roles (like Project Manager) didn't get the file copied, causing Claude to hang at MCP prompts
- The check was too narrow, only looking at worktree-specific paths

### Solution
- Added CLI flag `--global-mcp-init` (default: False for backward compatibility)
- When enabled, checks global/system paths first:
  - `~/.mcp.json` (user-level)
  - `/etc/mcp.json` (system-level)
- Falls back to worktree-specific `.mcp.json` if no global config found
- This ensures all agents can access MCP tools regardless of worktree setup

### Usage
```bash
./auto_orchestrate.py --project /path --spec spec.md --global-mcp-init
```

## Combined Usage

For maximum reliability, use both flags:
```bash
./auto_orchestrate.py --project /path --spec spec.md \
  --enable-orchestrator-scheduling \
  --global-mcp-init
```

## Code Changes

### Files Modified
- `auto_orchestrate.py`: Added new CLI options, modified AutoOrchestrator class, updated scheduling and MCP init logic

### Key Changes
1. Added flags to CLI (@click.option)
2. Added flags to AutoOrchestrator.__init__
3. Modified scheduling exclusion (lines ~2933-2954)
4. Enhanced MCP initialization check (lines ~2837-2856)

## Testing

To verify the fixes work:
1. Run with `--enable-orchestrator-scheduling` and check `scheduler.py --list` for orchestrator window 0 tasks
2. Run with `--global-mcp-init` and verify all agents start without MCP prompt hangs
3. Check that existing behavior is preserved when flags are not used

## Backward Compatibility

Both flags default to False, preserving existing behavior unless explicitly enabled. This ensures no breaking changes for current users.
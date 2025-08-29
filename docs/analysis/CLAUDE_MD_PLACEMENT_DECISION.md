# CLAUDE.md Placement Decision & Implementation Guide

## Decision: Keep CLAUDE.md in Root Directory

After analyzing the CLAUDE.md placement question, the decision is to **maintain CLAUDE.md in the root directory** where it currently resides.

## Quick Summary

- **Current Location**: `/CLAUDE.md` (root directory) ✅
- **Previous Location**: `docs/guides/CLAUDE.md` ❌
- **Decision**: Keep in root
- **References**: 26 files currently reference CLAUDE.md
- **No Action Required**: System already configured correctly

## Why Root Directory?

### 1. It's Both Configuration AND Documentation
CLAUDE.md serves a dual purpose:
- **Runtime Configuration**: Defines agent behavior, git rules, team compositions
- **Knowledge Base**: Documents project architecture and workflows
- **Not Just a Guide**: Active configuration file read by automated tools

### 2. Tool Integration
Critical integrations that expect root location:
- `auto_orchestrate.py` - Reads for agent briefings
- `monitoring/` - Extracts compliance rules in real-time
- `setup.sh` - Installation process
- 20+ other scripts and tools

### 3. Visibility and Convention
- Follows convention like README.md, LICENSE
- Immediately visible to new users
- Signals importance to the project
- Easy discovery by both humans and tools

### 4. User Decision Validated
The user moved it FROM docs/guides/ TO root for good reasons:
- Better accessibility
- Clearer importance
- Simplified tool access
- Matches its dual nature

## Implementation Status

### ✅ Current State is Correct
No changes needed - the file is already in the optimal location.

### 📁 Current Structure
```
Tmux-Orchestrator/
├── CLAUDE.md              # ✅ Correct location
├── README.md
├── auto_orchestrate.py    # References ./CLAUDE.md
├── monitoring/
│   ├── claude_md_watcher.py
│   └── extract_rules.py   # Monitors ./CLAUDE.md
└── docs/
    └── guides/            # Previous location (not used)
```

## Future Considerations

### When to Reconsider Placement
1. If CLAUDE.md exceeds 5,000 lines
2. If multiple projects need different rulesets  
3. If modular override system becomes necessary

### Potential Future Enhancement
If modularity is needed later, consider:
```
Tmux-Orchestrator/
├── CLAUDE.md             # Main configuration (keep in root)
└── .claude/              # Optional overrides
    ├── rules/
    ├── workflows/
    └── project-specific/
```

## Migration Guide (If Ever Needed)

If future requirements demand moving CLAUDE.md:

### Option 1: Symlink Approach (Recommended)
```bash
# Move file but maintain compatibility
mv CLAUDE.md docs/guides/CLAUDE.md
ln -s docs/guides/CLAUDE.md CLAUDE.md
```

### Option 2: Full Migration (Complex)
Would require updating:
- 26+ file references
- Path resolution in auto_orchestrate.py
- Monitoring system watchers
- All documentation references
- Risk of breaking active orchestrations

## Best Practices Going Forward

1. **Document the Decision**: Add note to README.md explaining why CLAUDE.md is in root
2. **Monitor Growth**: Track file size and complexity
3. **Preserve Location**: Resist urge to "clean up" by moving to docs/
4. **Enhance, Don't Move**: Add features through includes/imports rather than relocation

## Conclusion

The current placement of CLAUDE.md in the root directory is correct and should be maintained. It properly reflects the file's importance as both configuration and documentation. The user's decision to move it to root was the right choice, and the system is already optimized for this location.
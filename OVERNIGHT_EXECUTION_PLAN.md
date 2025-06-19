# Overnight Execution Plan - June 18, 2025

## Overview
Focused work on two projects: AI Chat (SourceWave) and Glacier Backend, with strict session locking to prevent accidental modifications to other projects.

## Session Lock Mechanism
- **Allowed Sessions**: `ai-chat`, `glacier-backend` ONLY
- **Forbidden Sessions**: `task-templates`, `glacier-frontend`, `tmux-orc`
- **Lock File**: `/session_lock.json` - Check before ANY tmux command

## Project 1: AI Chat (SourceWave)

### Phase 1: Setup & Discovery (20:55 - 21:15)
1. **Commit Current Work**
   - Check git status in ai-chat
   - Commit with descriptive message
   - Tag checkpoint: "pre-overnight-work-2025-06-18"

2. **Find Vision Document**
   - Search for vision.md, README.md, or similar
   - Understand core purpose: Quick content creation, prompt testing, save to sources
   - App name: SourceWave

### Phase 2: Homepage Variants (21:15 - 22:15)
Create 5 different homepage layout styles:
1. **Dashboard Style**: Metrics, recent activity, quick actions
2. **Minimal Focus**: Large central CTA for new content
3. **Card Grid**: Visual preview of recent sources/workflows
4. **Split View**: Sources on left, workflows on right
5. **Timeline**: Activity feed with inline actions

Each variant should emphasize quick content creation and prompt testing.

### Phase 3: Workflow Execution Fix (22:15 - 23:00)
**Problem**: When a node connects to multiple nodes, they should ALL execute before moving to next stage
**Solution**:
- Implement execution queue that tracks dependencies
- Ensure all sibling nodes complete before progressing
- Avoid parallel execution (API key conflicts)
- Example: Node A → [B, C, D] → Node E (B,C,D must ALL finish before E starts)

### Phase 4: Workflow Card Variations (23:00 - 23:45)
Create 5 design variations for workflow cards:
1. **Compact**: Minimal, just title and status
2. **Expanded**: Current design with input/output visible
3. **Preview**: Shows first few lines of input/output
4. **Icon-based**: Visual representation with minimal text
5. **Metrics**: Shows execution stats, success rate

### Phase 5: Node Inspector Redesign (23:45 - 00:30)
**3-Pane Center Layout** (like N8n):
- **Left Pane**: Context/connections
- **Center Pane**: Controls (model selection, input prompt)
- **Right Pane**: Outputs in accordion format
  - Latest output at top, auto-expanded
  - Click to see related input + metadata
  - Foldable for space management

### Phase 6: Source Chat Feature (00:30 - 01:15)
Implement chat functionality:
- Chat button on each source
- Chat with entire collection or specific entity
- Access to all context for that entity
- Modal-based chat interface
- Maintain conversation history

### Phase 7: Git Management (01:15 - 01:45)
- Implement checkpoint naming system
- Create merge strategy for selected checkpoints
- Add descriptive commit messages
- Document in git log for morning review

## Project 2: Glacier Backend

### Phase 1: Discovery (21:00 - 21:30)
1. **Find Analytics Documentation**
   - Look for customer LTV, conversion metrics docs
   - Find DuckDB notebook with SQL examples

2. **Schema Investigation**
   - Have agent check all available tables
   - Document table structures
   - Identify join relationships

### Phase 2: SQL Query Planning (21:30 - 22:30)
Create queries for:

1. **Customer LTV**
   - Total revenue per customer
   - Average order value
   - Purchase frequency

2. **Lead-to-Conversion Ratio**
   - Track from first engagement to purchase
   - Conversion funnel metrics

3. **Product Analysis**
   - Most common first products
   - Most common second products
   - Product purchase sequences

4. **Repeat Purchase Rate**
   - Customers with 2+ purchases
   - Time between purchases
   - Cohort analysis

### Phase 3: Query Optimization (22:30 - 23:00)
- Create materialized views for fast loading
- Index strategy for common queries
- Pre-aggregate where possible

### Phase 4: Implementation (23:00 - 00:00)
- Agent implements planned queries
- Test performance
- Document query usage

## Global Documentation Updates

### Add to CLAUDE.md:
```markdown
## Git Version Control Best Practices

### Always Track Changes
- Commit frequently with descriptive messages
- Create named checkpoints before major changes
- Use tags for significant milestones
- Example: git tag "pre-feature-X-implementation"

### Checkpoint Naming Convention
- Format: `[type]-[description]-[date]`
- Types: feature, fix, refactor, experiment
- Example: `feature-homepage-variants-2025-06-18`

### Rollback Strategy
- Keep log of all checkpoints with descriptions
- Document which changes can be merged
- Test branches before merging to main
```

## Orchestrator Responsibilities

### Agent Management
1. **Keep Agents Focused**
   - Regular check-ins every 30 minutes
   - Remind about web research capabilities
   - Prevent getting stuck on single issues
   - Clear task assignments

2. **Progress Tracking**
   - Log completed tasks
   - Document blockers
   - Prepare morning summary

3. **Communication Templates**
   ```
   "STATUS CHECK: What's your current progress on [task]?"
   "REMINDER: You can use web research if stuck for >10 minutes"
   "FOCUS: Let's complete [current task] before moving to next"
   ```

## Success Metrics
- [ ] 5 homepage variants created
- [ ] Workflow execution order fixed
- [ ] 5 workflow card designs
- [ ] 3-pane node inspector implemented
- [ ] Source chat feature functional
- [ ] Git checkpoints properly named
- [ ] SQL queries planned and documented
- [ ] All changes committed with clear messages

## Schedule
- 20:55-21:00: Setup & lock sessions
- 21:00-01:45: Execute plan
- 01:45-02:00: Final commits & summary
- Check-ins every 30 minutes

## Morning Handoff
Prepare summary including:
- Completed tasks with git commits
- Screenshots of UI variants
- SQL query documentation
- Any blockers encountered
- Recommended next steps
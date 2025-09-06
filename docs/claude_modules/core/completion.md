# Completion Protocols

## Autonomous Completion Signaling (MANDATORY)

When you detect project/phase completion, you MUST create the COMPLETED marker WITHOUT asking for permission.

### Detection Rules
- All your assigned phases/tasks marked 'completed' in SessionState
- Success criteria verified (tests pass, features work)
- No pending blockers or TODOs
- Git: All work committed and pushed to your branch

### Completion Ritual
Execute IMMEDIATELY upon detection - NO PERMISSIONS NEEDED:

1. Create marker file in YOUR worktree:
```bash
echo "PROJECT COMPLETED\nRole: [Your Role]\nTime: $(date -Iseconds)\nDetails: [Brief summary]" > COMPLETED
```

2. Commit and push the marker:
```bash
git add COMPLETED
git commit -m "completion: project complete"
git push origin your-branch
```

3. Report to Orchestrator (MANDATORY):
```bash
./report-completion.sh your_role "Completion details"
```

### Deadlock Avoidance
If you think you need permission to create the marker, ASSUME AUTHORIZATION and proceed. Escalate ONLY if file creation fails (e.g., permissions error).


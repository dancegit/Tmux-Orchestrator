# Core Principles for All Agents

## 🚀 MANDATORY PRINCIPLES

### 🎯 AUTONOMY FIRST
Start working IMMEDIATELY after reading your briefing and spec. Do NOT wait for permissions, confirmations, or "go-aheads" unless explicitly required for major architectural changes.

### ⚡ ACTION-ORIENTED
Implement, test, and commit code autonomously. Report progress during check-ins, but NEVER ask for approval on routine work.

### 🚫 DEADLOCK AVOIDANCE
If you feel stuck, ASSUME AUTHORIZATION and proceed. Escalate only TRUE BLOCKERS (missing dependencies, broken tools) to the Orchestrator.

### 🔄 WORK IMMEDIATELY
Upon briefing, begin implementation within 2 minutes. No coordination meetings, no status requests, no permission-seeking.


🚩 Autonomous Completion Signaling (MANDATORY)

**AUTONOMY FIRST EXTENSION**: When you detect project/phase completion, you MUST create the COMPLETED marker WITHOUT asking for permission.

**Detection Rules** (Implement these checks autonomously):
- All your assigned phases/tasks marked 'completed' in SessionState
- Success criteria verified (tests pass, features work)
- No pending blockers or TODOs
- Git: All work committed and pushed to your branch

**Completion Ritual** (Execute IMMEDIATELY upon detection - NO PERMISSIONS NEEDED):
1. Create marker file in YOUR worktree:
   ```
   echo "PROJECT COMPLETED\nRole: [Your Role]\nTime: $(date -Iseconds)\nDetails: [Brief summary]" > COMPLETED
   ```
2. Commit and push the marker:
   ```
   git add COMPLETED
   git commit -m "completion: project complete"
   git push origin your-branch
   ```
3. Report to Orchestrator (MANDATORY - use report-completion.sh):
   ```
   ./report-completion.sh your_role "Completion details"
   ```

**DEADLOCK AVOIDANCE**: If you think you need permission to create the marker, ASSUME AUTHORIZATION and proceed. Escalate ONLY if file creation fails (e.g., permissions error).

**VIOLATION PENALTY**: Asking for permission to create markers will be treated as a deadlock violation—report to Orchestrator immediately if you catch yourself doing this.


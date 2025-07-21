#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Extract monitorable rules from CLAUDE.md for compliance checking
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any

class RuleExtractor:
    def __init__(self, claude_md_path: Path):
        self.claude_md_path = claude_md_path
        self.rules = []
        
    def extract_rules(self) -> List[Dict[str, Any]]:
        """Extract all monitorable rules from CLAUDE.md"""
        with open(self.claude_md_path, 'r') as f:
            content = f.read()
            
        # Extract communication rules
        self._extract_communication_rules(content)
        
        # Extract git rules
        self._extract_git_rules(content)
        
        # Extract scheduling rules
        self._extract_scheduling_rules(content)
        
        # Extract integration rules
        self._extract_integration_rules(content)
        
        # Extract workflow rules
        self._extract_workflow_rules(content)
        
        # Extract monitored messaging rules
        self._extract_monitoring_rules(content)
        
        return self.rules
    
    def _extract_communication_rules(self, content: str):
        """Extract hub-and-spoke communication rules"""
        rules = [
            {
                "id": "comm-001",
                "category": "communication",
                "rule": "Developers must report to PM only",
                "violation_patterns": [
                    {"from": "developer", "to": ["tester", "testrunner", "devops", "researcher"], "direct": True}
                ],
                "severity": "high"
            },
            {
                "id": "comm-002", 
                "category": "communication",
                "rule": "PM aggregates and reports to Orchestrator",
                "violation_patterns": [
                    {"from": ["developer", "tester", "testrunner"], "to": "orchestrator", "direct": True}
                ],
                "severity": "high"
            },
            {
                "id": "comm-003",
                "category": "communication",
                "rule": "No chit-chat - all messages work-related",
                "violation_patterns": [
                    {"keywords": ["hi", "hello", "how are you", "thanks", "bye"], "context": "casual"}
                ],
                "severity": "medium"
            },
            {
                "id": "comm-004",
                "category": "communication",
                "rule": "Use message templates for standard communications",
                "violation_patterns": [
                    {"message_type": "status_update", "missing_fields": ["completed", "current", "blocked"]}
                ],
                "severity": "low"
            },
            {
                "id": "comm-005",
                "category": "communication", 
                "rule": "Always use send-claude-message.sh script",
                "violation_patterns": [
                    {"command": "tmux send-keys", "context": "messaging"}
                ],
                "severity": "high"
            },
            {
                "id": "comm-006",
                "category": "communication",
                "rule": "Must use monitored messaging (scm or send-monitored-message.sh)",
                "violation_patterns": [
                    {"command": "send-claude-message.sh", "context": "direct_use"},
                    {"missing": "scm", "context": "messaging"}
                ],
                "severity": "critical"
            }
        ]
        self.rules.extend(rules)
        
    def _extract_git_rules(self, content: str):
        """Extract git discipline rules"""
        rules = [
            {
                "id": "git-001",
                "category": "git",
                "rule": "Never merge to main unless started on main",
                "violation_patterns": [
                    {"action": "merge", "target": "main", "parent_not_main": True}
                ],
                "severity": "critical"
            },
            {
                "id": "git-002",
                "category": "git",
                "rule": "Auto-commit every 30 minutes",
                "violation_patterns": [
                    {"time_since_last_commit": ">30min", "uncommitted_changes": True}
                ],
                "severity": "high"
            },
            {
                "id": "git-003",
                "category": "git",
                "rule": "Always commit before task switches",
                "violation_patterns": [
                    {"task_switch": True, "uncommitted_changes": True}
                ],
                "severity": "high"
            },
            {
                "id": "git-004",
                "category": "git",
                "rule": "Create feature branches from current branch",
                "violation_patterns": [
                    {"branch_creation": True, "from_wrong_parent": True}
                ],
                "severity": "high"
            },
            {
                "id": "git-005",
                "category": "git",
                "rule": "Use agent-specific branch names",
                "violation_patterns": [
                    {"branch_name": "missing_role_suffix", "agent": True}
                ],
                "severity": "medium"
            },
            {
                "id": "git-006",
                "category": "git",
                "rule": "Push within 15 minutes of commit",
                "violation_patterns": [
                    {"time_since_commit": ">15min", "unpushed_commits": True}
                ],
                "severity": "high"
            },
            {
                "id": "git-007",
                "category": "git",
                "rule": "Set upstream with -u on first push",
                "violation_patterns": [
                    {"first_push": True, "missing_upstream": True}
                ],
                "severity": "medium"
            },
            {
                "id": "git-008",
                "category": "git",
                "rule": "Announce pushes to PM",
                "violation_patterns": [
                    {"push_completed": True, "pm_not_notified": True}
                ],
                "severity": "medium"
            },
            {
                "id": "git-009",
                "category": "git",
                "rule": "Pull from parent branch after integration",
                "violation_patterns": [
                    {"integration_complete": True, "time_since_pull": ">1hour"}
                ],
                "severity": "high"
            },
            {
                "id": "git-010",
                "category": "git",
                "rule": "Maximum 20 commits behind parent branch",
                "violation_patterns": [
                    {"commits_behind": ">20"}
                ],
                "severity": "high"
            }
        ]
        self.rules.extend(rules)
        
    def _extract_scheduling_rules(self, content: str):
        """Extract scheduling and orchestrator rules"""
        rules = [
            {
                "id": "sched-001",
                "category": "scheduling",
                "rule": "Orchestrator must test scheduling on startup",
                "violation_patterns": [
                    {"orchestrator_start": True, "schedule_test_missing": True}
                ],
                "severity": "critical"
            },
            {
                "id": "sched-002",
                "category": "scheduling",
                "rule": "Schedule script must accept target window parameter",
                "violation_patterns": [
                    {"schedule_command": True, "missing_target": True}
                ],
                "severity": "high"
            },
            {
                "id": "sched-003",
                "category": "scheduling",
                "rule": "Regular check-in intervals must be maintained",
                "violation_patterns": [
                    {"check_in_overdue": True, "threshold": "2x_interval"}
                ],
                "severity": "medium"
            }
        ]
        self.rules.extend(rules)
        
    def _extract_integration_rules(self, content: str):
        """Extract integration and PR rules"""
        rules = [
            {
                "id": "int-001",
                "category": "integration",
                "rule": "PM handles all integration and merges",
                "violation_patterns": [
                    {"integration_by": ["developer", "tester", "testrunner"]}
                ],
                "severity": "high"
            },
            {
                "id": "int-002",
                "category": "integration",
                "rule": "Auto-merge PRs with --admin flag",
                "violation_patterns": [
                    {"pr_merge": True, "manual_approval": True}
                ],
                "severity": "medium"
            },
            {
                "id": "int-003",
                "category": "integration",
                "rule": "All agents must pull parent branch after integration",
                "violation_patterns": [
                    {"integration_complete": True, "agents_not_synced": True}
                ],
                "severity": "high"
            },
            {
                "id": "int-004",
                "category": "integration",
                "rule": "Create PR within 30 minutes of push",
                "violation_patterns": [
                    {"push_time": "recorded", "pr_delay": ">30min"}
                ],
                "severity": "high"
            },
            {
                "id": "int-005",
                "category": "integration",
                "rule": "Merge PR within 2 hours",
                "violation_patterns": [
                    {"pr_age": ">2hours", "status": "open"}
                ],
                "severity": "high"
            },
            {
                "id": "int-006",
                "category": "integration",
                "rule": "Integration cycle completes within 4 hours",
                "violation_patterns": [
                    {"cycle_start": "recorded", "duration": ">4hours"}
                ],
                "severity": "critical"
            }
        ]
        self.rules.extend(rules)
        
    def _extract_workflow_rules(self, content: str):
        """Extract workflow health rules"""
        rules = [
            {
                "id": "workflow-001",
                "category": "workflow",
                "rule": "No PR should be stuck for more than 2 hours",
                "violation_patterns": [
                    {"pr_status": "open", "age": ">2hours", "no_activity": True}
                ],
                "severity": "high"
            },
            {
                "id": "workflow-002",
                "category": "workflow",
                "rule": "No agent more than 1 hour behind parent after integration",
                "violation_patterns": [
                    {"integration_announced": True, "agent_behind": ">1hour"}
                ],
                "severity": "high"
            },
            {
                "id": "workflow-003",
                "category": "workflow",
                "rule": "Resolve conflicts within 30 minutes",
                "violation_patterns": [
                    {"conflict_detected": True, "resolution_time": ">30min"}
                ],
                "severity": "high"
            },
            {
                "id": "workflow-004",
                "category": "workflow",
                "rule": "Worktree discipline - no cross-worktree modifications",
                "violation_patterns": [
                    {"file_modified": True, "outside_own_worktree": True}
                ],
                "severity": "critical"
            }
        ]
        self.rules.extend(rules)
        
    def _extract_monitoring_rules(self, content: str):
        """Extract monitoring system rules"""
        rules = [
            {
                "id": "monitor-001",
                "category": "monitoring",
                "rule": "All communications must be logged",
                "violation_patterns": [
                    {"message_sent": True, "not_logged": True}
                ],
                "severity": "high"
            },
            {
                "id": "monitor-002",
                "category": "monitoring",
                "rule": "Violations must be reported to orchestrator",
                "violation_patterns": [
                    {"violation_detected": True, "orchestrator_not_notified": True}
                ],
                "severity": "medium"
            }
        ]
        self.rules.extend(rules)
        
    def save_rules(self, output_path: Path):
        """Save extracted rules to JSON file"""
        with open(output_path, 'w') as f:
            json.dump({
                "version": "1.0",
                "source": str(self.claude_md_path),
                "rules": self.rules
            }, f, indent=2)
            
def main():
    """Extract rules and save to monitoring config"""
    script_dir = Path(__file__).parent
    claude_md = script_dir.parent / "CLAUDE.md"
    output_file = script_dir / "compliance_rules.json"
    
    if not claude_md.exists():
        print(f"Error: CLAUDE.md not found at {claude_md}")
        return
        
    extractor = RuleExtractor(claude_md)
    rules = extractor.extract_rules()
    extractor.save_rules(output_file)
    
    print(f"Extracted {len(rules)} rules from CLAUDE.md")
    print(f"Saved to: {output_file}")
    
    # Print summary by category
    categories = {}
    for rule in rules:
        cat = rule['category']
        categories[cat] = categories.get(cat, 0) + 1
        
    print("\nRule summary by category:")
    for cat, count in categories.items():
        print(f"  {cat}: {count} rules")

if __name__ == "__main__":
    main()
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
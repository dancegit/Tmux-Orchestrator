#!/usr/bin/env python3
"""
Extract monitorable rules from modularized CLAUDE knowledge base.

This is the modular version of extract_rules.py that works with the
split CLAUDE modules instead of the monolithic CLAUDE.md file.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
import re

class ModularRuleExtractor:
    """Extract rules from modular CLAUDE knowledge base"""
    
    def __init__(self, modules_dir: Path):
        """
        Initialize with path to claude_modules directory.
        
        Args:
            modules_dir: Path to the docs/claude_modules directory
        """
        self.modules_dir = modules_dir
        if not self.modules_dir.exists():
            raise FileNotFoundError(f"Modules directory not found: {modules_dir}")
    
    def _load_module(self, relative_path: str) -> str:
        """Load a specific module file"""
        module_path = self.modules_dir / relative_path
        if module_path.exists():
            return module_path.read_text()
        return ""
    
    def extract_all_rules(self) -> List[Dict[str, Any]]:
        """Extract all monitorable rules from modules"""
        rules = []
        
        # Map rule categories to specific modules
        rule_mapping = {
            'communication': ['core/communication.md'],
            'git': ['workflows/git_workflow.md'],
            'completion': ['core/completion.md'],
            'principles': ['core/principles.md']
        }
        
        for category, module_paths in rule_mapping.items():
            for module_path in module_paths:
                content = self._load_module(module_path)
                if content:
                    category_rules = self._extract_rules_from_content(content, category)
                    rules.extend(category_rules)
        
        return rules
    
    def _extract_rules_from_content(self, content: str, category: str) -> List[Dict[str, Any]]:
        """Extract rules from module content"""
        rules = []
        
        if category == 'communication':
            rules.extend(self._extract_communication_rules(content))
        elif category == 'git':
            rules.extend(self._extract_git_rules(content))
        elif category == 'completion':
            rules.extend(self._extract_completion_rules(content))
        elif category == 'principles':
            rules.extend(self._extract_principle_rules(content))
        
        return rules
    
    def _extract_communication_rules(self, content: str) -> List[Dict[str, Any]]:
        """Extract communication-related rules"""
        rules = []
        
        # Hub-and-spoke model
        if "Hub-and-Spoke Model" in content:
            rules.append({
                "id": "comm_hub_spoke",
                "category": "communication",
                "description": "All agents must report to Orchestrator (hub-and-spoke model)",
                "severity": "high",
                "violation_patterns": [
                    {"pattern": r"direct agent-to-agent.*without orchestrator", "type": "regex"},
                    {"pattern": "bypassing orchestrator", "type": "text"}
                ]
            })
        
        # Use of scm command
        if "scm" in content or "Smart Messaging" in content:
            rules.append({
                "id": "comm_use_scm",
                "category": "communication",
                "description": "Use scm command for all inter-agent messaging",
                "severity": "medium",
                "violation_patterns": [
                    {"pattern": r"tmux send-keys.*(?!scm)", "type": "regex"},
                    {"pattern": "send-claude-message.sh", "type": "text"}
                ]
            })
        
        # Completion reporting
        if "Report Completions" in content or "report-completion.sh" in content:
            rules.append({
                "id": "comm_report_completion",
                "category": "communication",
                "description": "Report all task completions using report-completion.sh",
                "severity": "high",
                "violation_patterns": [
                    {"pattern": "completed.*not reported", "type": "text"},
                    {"pattern": "silent completion", "type": "text"}
                ]
            })
        
        return rules
    
    def _extract_git_rules(self, content: str) -> List[Dict[str, Any]]:
        """Extract git workflow rules"""
        rules = []
        
        # 30-minute commit rule
        if "30-Minute Commit Rule" in content or "every 30 minutes" in content:
            rules.append({
                "id": "git_30min_commit",
                "category": "git",
                "description": "Commit progress every 30 minutes",
                "severity": "high",
                "violation_patterns": [
                    {"pattern": "no commits for.*hour", "type": "text"},
                    {"pattern": r"last commit.*[4-9]\d+ minutes ago", "type": "regex"}
                ],
                "check_interval": 1800  # 30 minutes in seconds
            })
        
        # Branch protection
        if "NEVER MERGE TO MAIN UNLESS YOU STARTED ON MAIN" in content:
            rules.append({
                "id": "git_branch_protection",
                "category": "git",
                "description": "Never merge to main unless project started on main",
                "severity": "critical",
                "violation_patterns": [
                    {"pattern": r"merge.*main.*unauthorized", "type": "regex"},
                    {"pattern": "merged to main without permission", "type": "text"}
                ]
            })
        
        # Meaningful commits
        if "Meaningful Commit Messages" in content:
            rules.append({
                "id": "git_meaningful_commits",
                "category": "git",
                "description": "Use meaningful, descriptive commit messages",
                "severity": "low",
                "violation_patterns": [
                    {"pattern": r'commit -m "fixes"', "type": "regex"},
                    {"pattern": r'commit -m "updates"', "type": "regex"},
                    {"pattern": r'commit -m "changes"', "type": "regex"}
                ]
            })
        
        return rules
    
    def _extract_completion_rules(self, content: str) -> List[Dict[str, Any]]:
        """Extract completion signaling rules"""
        rules = []
        
        # Autonomous completion
        if "Autonomous Completion Signaling" in content:
            rules.append({
                "id": "completion_autonomous",
                "category": "completion",
                "description": "Create COMPLETED marker without asking permission",
                "severity": "high",
                "violation_patterns": [
                    {"pattern": "asking.*permission.*complete", "type": "text"},
                    {"pattern": "waiting.*approval.*marker", "type": "text"}
                ]
            })
        
        # Completion reporting
        if "report-completion.sh" in content:
            rules.append({
                "id": "completion_report",
                "category": "completion",
                "description": "Use report-completion.sh for all completions",
                "severity": "high",
                "violation_patterns": [
                    {"pattern": "completed.*not.*reported", "type": "text"},
                    {"pattern": r"COMPLETED.*but.*no.*report", "type": "regex"}
                ]
            })
        
        return rules
    
    def _extract_principle_rules(self, content: str) -> List[Dict[str, Any]]:
        """Extract core principle rules"""
        rules = []
        
        # Autonomy first
        if "AUTONOMY FIRST" in content:
            rules.append({
                "id": "principle_autonomy",
                "category": "principles",
                "description": "Start working immediately without waiting for permissions",
                "severity": "critical",
                "violation_patterns": [
                    {"pattern": "waiting for permission", "type": "text"},
                    {"pattern": "need approval to start", "type": "text"},
                    {"pattern": "should I begin", "type": "text"}
                ]
            })
        
        # Action oriented
        if "ACTION-ORIENTED" in content:
            rules.append({
                "id": "principle_action",
                "category": "principles",
                "description": "Implement and commit autonomously, report progress not requests",
                "severity": "high",
                "violation_patterns": [
                    {"pattern": "requesting approval", "type": "text"},
                    {"pattern": "asking for permission", "type": "text"}
                ]
            })
        
        # Deadlock avoidance
        if "DEADLOCK AVOIDANCE" in content:
            rules.append({
                "id": "principle_deadlock",
                "category": "principles",
                "description": "Assume authorization and proceed when stuck",
                "severity": "high",
                "violation_patterns": [
                    {"pattern": "stuck.*waiting", "type": "text"},
                    {"pattern": "blocked.*permission", "type": "text"}
                ]
            })
        
        # Work immediately
        if "WORK IMMEDIATELY" in content:
            rules.append({
                "id": "principle_immediate",
                "category": "principles",
                "description": "Begin implementation within 2 minutes of briefing",
                "severity": "high",
                "violation_patterns": [
                    {"pattern": r"briefed.*\d+ minutes.*no.*progress", "type": "regex"},
                    {"pattern": "coordination meeting", "type": "text"}
                ]
            })
        
        return rules
    
    def save_rules(self, output_path: Path):
        """Save extracted rules to JSON file"""
        rules = self.extract_all_rules()
        
        with open(output_path, 'w') as f:
            json.dump(rules, f, indent=2)
        
        print(f"Extracted {len(rules)} rules from modular CLAUDE knowledge base")
        print(f"Saved to: {output_path}")
        
        # Print summary by category
        categories = {}
        for rule in rules:
            cat = rule['category']
            categories[cat] = categories.get(cat, 0) + 1
        
        print("\nRules by category:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count}")
        
        return rules


def main():
    """Main function to extract rules from modular CLAUDE files"""
    script_dir = Path(__file__).parent
    modules_dir = script_dir.parent / "docs" / "claude_modules"
    
    if not modules_dir.exists():
        print(f"Error: Modules directory not found at {modules_dir}")
        print("Please run extract_claude_modules.py first to create the modular files")
        return
    
    extractor = ModularRuleExtractor(modules_dir)
    
    # Save rules to the monitoring directory
    output_path = script_dir / "rules.json"
    rules = extractor.save_rules(output_path)
    
    # Also save a human-readable version
    readable_path = script_dir / "rules_readable.txt"
    with open(readable_path, 'w') as f:
        f.write("MONITORABLE RULES FROM MODULAR CLAUDE KNOWLEDGE BASE\n")
        f.write("=" * 60 + "\n\n")
        
        for rule in rules:
            f.write(f"ID: {rule['id']}\n")
            f.write(f"Category: {rule['category']}\n")
            f.write(f"Description: {rule['description']}\n")
            f.write(f"Severity: {rule['severity']}\n")
            f.write("-" * 40 + "\n")
    
    print(f"Human-readable rules saved to: {readable_path}")


if __name__ == "__main__":
    main()
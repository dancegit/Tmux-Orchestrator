#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Generate comprehensive compliance reports for Tmux Orchestrator
"""

import json
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import sys

class ReportGenerator:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.registry_dir = self.script_dir.parent / "registry"
        self.logs_dir = self.registry_dir / "logs"
        self.reports_dir = self.logs_dir / "compliance" / "daily_reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_daily_report(self, target_date: Optional[date] = None) -> Path:
        """Generate comprehensive daily compliance report"""
        
        if not target_date:
            target_date = date.today()
            
        report_data = self._collect_daily_data(target_date)
        report_path = self._create_report(target_date, report_data)
        
        print(f"Report generated: {report_path}")
        return report_path
        
    def _collect_daily_data(self, target_date: date) -> Dict[str, Any]:
        """Collect all compliance data for the specified date"""
        
        date_str = target_date.strftime("%Y-%m-%d")
        daily_comm_dir = self.logs_dir / "communications" / date_str
        
        data = {
            "date": date_str,
            "total_messages": 0,
            "analyzed_messages": 0,
            "violations": [],
            "violation_summary": defaultdict(int),
            "agent_activity": defaultdict(lambda: {"sent": 0, "received": 0, "violations": 0}),
            "rule_violations": defaultdict(int),
            "severity_breakdown": defaultdict(int),
            "top_offenders": [],
            "compliance_rate": 0.0
        }
        
        # Process message log
        messages_file = daily_comm_dir / "messages.jsonl"
        if messages_file.exists():
            self._process_messages(messages_file, data)
            
        # Process violations
        violations_file = daily_comm_dir / "violations.jsonl"
        if violations_file.exists():
            self._process_violations(violations_file, data)
            
        # Calculate compliance rate
        if data["analyzed_messages"] > 0:
            violation_count = len(data["violations"])
            data["compliance_rate"] = ((data["analyzed_messages"] - violation_count) / 
                                      data["analyzed_messages"]) * 100
                                      
        # Identify top offenders
        offender_counts = defaultdict(int)
        for v in data["violations"]:
            sender = v["message"]["sender"]["pane"]
            offender_counts[sender] += 1
            
        data["top_offenders"] = sorted(
            offender_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        return data
        
    def _process_messages(self, messages_file: Path, data: Dict[str, Any]):
        """Process message log file"""
        with open(messages_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                    
                try:
                    message = json.loads(line)
                    data["total_messages"] += 1
                    
                    # Track agent activity
                    sender = message["sender"]["pane"]
                    recipient = message["recipient"]["pane"]
                    
                    data["agent_activity"][sender]["sent"] += 1
                    data["agent_activity"][recipient]["received"] += 1
                    
                    if message.get("compliance_checked", False):
                        data["analyzed_messages"] += 1
                        
                except Exception as e:
                    print(f"Error processing message: {e}")
                    
    def _process_violations(self, violations_file: Path, data: Dict[str, Any]):
        """Process violations log file"""
        with open(violations_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                    
                try:
                    entry = json.loads(line)
                    data["violations"].append(entry)
                    
                    # Process each violation
                    violations = entry.get("analysis", {}).get("violations", [])
                    sender = entry["message"]["sender"]["pane"]
                    
                    data["agent_activity"][sender]["violations"] += len(violations)
                    
                    for v in violations:
                        rule_id = v.get("rule_id", "unknown")
                        severity = v.get("severity", "unknown")
                        
                        data["rule_violations"][rule_id] += 1
                        data["severity_breakdown"][severity] += 1
                        data["violation_summary"][rule_id] += 1
                        
                except Exception as e:
                    print(f"Error processing violation: {e}")
                    
    def _create_report(self, target_date: date, data: Dict[str, Any]) -> Path:
        """Create markdown report from collected data"""
        
        report_path = self.reports_dir / f"compliance_report_{data['date']}.md"
        
        with open(report_path, 'w') as f:
            # Header
            f.write(f"# Tmux Orchestrator Compliance Report\n")
            f.write(f"**Date**: {data['date']}\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary
            f.write("## Executive Summary\n\n")
            f.write(f"- **Total Messages**: {data['total_messages']}\n")
            f.write(f"- **Messages Analyzed**: {data['analyzed_messages']}\n")
            f.write(f"- **Total Violations**: {len(data['violations'])}\n")
            f.write(f"- **Compliance Rate**: {data['compliance_rate']:.1f}%\n\n")
            
            # Severity Breakdown
            if data['severity_breakdown']:
                f.write("## Violations by Severity\n\n")
                f.write("| Severity | Count |\n")
                f.write("|----------|-------|\n")
                for severity in ['critical', 'high', 'medium', 'low']:
                    if severity in data['severity_breakdown']:
                        f.write(f"| {severity.title()} | {data['severity_breakdown'][severity]} |\n")
                f.write("\n")
                
            # Top Rule Violations
            if data['rule_violations']:
                f.write("## Top Rule Violations\n\n")
                f.write("| Rule ID | Description | Count |\n")
                f.write("|---------|-------------|-------|\n")
                
                # Load rule descriptions
                rules_file = self.script_dir / "compliance_rules.json"
                rule_descriptions = {}
                if rules_file.exists():
                    with open(rules_file, 'r') as rf:
                        rules_data = json.load(rf)
                        for rule in rules_data.get('rules', []):
                            rule_descriptions[rule['id']] = rule['rule']
                            
                for rule_id, count in sorted(data['rule_violations'].items(), 
                                            key=lambda x: x[1], reverse=True)[:10]:
                    desc = rule_descriptions.get(rule_id, "Unknown rule")[:50]
                    f.write(f"| {rule_id} | {desc}... | {count} |\n")
                f.write("\n")
                
            # Top Offenders
            if data['top_offenders']:
                f.write("## Agents with Most Violations\n\n")
                f.write("| Agent | Violations |\n")
                f.write("|-------|------------|\n")
                for agent, count in data['top_offenders']:
                    f.write(f"| {agent} | {count} |\n")
                f.write("\n")
                
            # Agent Activity Summary
            f.write("## Agent Communication Activity\n\n")
            f.write("| Agent | Messages Sent | Messages Received | Violations |\n")
            f.write("|-------|---------------|-------------------|------------|\n")
            
            for agent, stats in sorted(data['agent_activity'].items()):
                f.write(f"| {agent} | {stats['sent']} | {stats['received']} | {stats['violations']} |\n")
            f.write("\n")
            
            # Detailed Violations (first 10)
            if data['violations']:
                f.write("## Sample Violations (First 10)\n\n")
                
                for i, violation in enumerate(data['violations'][:10]):
                    message = violation['message']
                    analysis = violation.get('analysis', {})
                    violations_list = analysis.get('violations', [])
                    
                    f.write(f"### Violation {i+1}\n")
                    f.write(f"**Time**: {message['timestamp']}\n")
                    f.write(f"**From**: {message['sender']['pane']} → **To**: {message['recipient']['pane']}\n")
                    f.write(f"**Message**: {message['message'][:100]}...\n\n")
                    
                    for v in violations_list:
                        f.write(f"- **{v['rule_id']}**: {v['rule_description']}\n")
                        f.write(f"  - Severity: {v['severity']}\n")
                        f.write(f"  - Correction: {v['correction']}\n")
                    f.write("\n")
                    
            # Recommendations
            f.write("## Recommendations\n\n")
            
            if data['compliance_rate'] < 80:
                f.write("⚠️ **Low compliance rate detected!**\n\n")
                f.write("1. Review hub-and-spoke communication model with all agents\n")
                f.write("2. Ensure all agents use `send-claude-message.sh` script\n")
                f.write("3. Reinforce proper communication channels\n\n")
                
            if 'comm-001' in data['rule_violations'] and data['rule_violations']['comm-001'] > 5:
                f.write("📋 **High direct communication violations**\n\n")
                f.write("- Developers are bypassing PM too frequently\n")
                f.write("- Consider additional training on communication hierarchy\n\n")
                
            if 'git-002' in data['rule_violations']:
                f.write("💾 **Git commit frequency issues**\n\n")
                f.write("- Agents not committing every 30 minutes\n")
                f.write("- Set up automated reminders\n\n")
                
        return report_path
        
def main():
    """Generate report for specified date or today"""
    generator = ReportGenerator()
    
    if len(sys.argv) > 1:
        # Parse date argument
        try:
            target_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        target_date = date.today()
        
    report_path = generator.generate_daily_report(target_date)
    
    # Optionally display the report
    if "--show" in sys.argv:
        with open(report_path, 'r') as f:
            print(f.read())

if __name__ == "__main__":
    main()
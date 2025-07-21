#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Detect workflow bottlenecks by analyzing git and communication patterns
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import subprocess

class WorkflowBottleneckDetector:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.registry_dir = self.script_dir.parent / "registry"
        self.logs_dir = self.registry_dir / "logs"
        
        # Load monitoring results
        self.git_data = self._load_git_data()
        self.github_data = self._load_github_data()
        self.communication_data = self._load_communication_data()
        
    def _load_git_data(self) -> Dict[str, Any]:
        """Load latest git activity data"""
        today = datetime.now().strftime("%Y-%m-%d")
        git_log = self.logs_dir / "git-activity" / today / "git_activity.jsonl"
        
        if git_log.exists():
            with open(git_log, 'r') as f:
                lines = f.readlines()
                if lines:
                    # Get the most recent entry
                    return json.loads(lines[-1])
        return {}
        
    def _load_github_data(self) -> Dict[str, Any]:
        """Load latest GitHub activity data"""
        today = datetime.now().strftime("%Y-%m-%d")
        github_log = self.logs_dir / "git-activity" / today / "github_activity.jsonl"
        
        if github_log.exists():
            with open(github_log, 'r') as f:
                lines = f.readlines()
                if lines:
                    return json.loads(lines[-1])
        return {}
        
    def _load_communication_data(self) -> List[Dict[str, Any]]:
        """Load recent communications"""
        today = datetime.now().strftime("%Y-%m-%d")
        comm_log = self.logs_dir / "communications" / today / "messages.jsonl"
        
        messages = []
        if comm_log.exists():
            with open(comm_log, 'r') as f:
                for line in f:
                    if line.strip():
                        messages.append(json.loads(line))
        return messages
        
    def detect_bottlenecks(self) -> Dict[str, Any]:
        """Analyze all data to detect workflow bottlenecks"""
        bottlenecks = {
            "timestamp": datetime.now().isoformat(),
            "bottlenecks": [],
            "workflow_health": "healthy",
            "recommendations": []
        }
        
        # Check git activity bottlenecks
        git_bottlenecks = self._check_git_bottlenecks()
        bottlenecks["bottlenecks"].extend(git_bottlenecks)
        
        # Check GitHub/PR bottlenecks
        github_bottlenecks = self._check_github_bottlenecks()
        bottlenecks["bottlenecks"].extend(github_bottlenecks)
        
        # Check communication patterns
        comm_bottlenecks = self._check_communication_bottlenecks()
        bottlenecks["bottlenecks"].extend(comm_bottlenecks)
        
        # Check integration workflow
        integration_bottlenecks = self._check_integration_workflow()
        bottlenecks["bottlenecks"].extend(integration_bottlenecks)
        
        # Determine overall health
        if any(b["severity"] == "critical" for b in bottlenecks["bottlenecks"]):
            bottlenecks["workflow_health"] = "critical"
        elif any(b["severity"] == "high" for b in bottlenecks["bottlenecks"]):
            bottlenecks["workflow_health"] = "degraded"
        elif bottlenecks["bottlenecks"]:
            bottlenecks["workflow_health"] = "warning"
            
        # Generate recommendations
        bottlenecks["recommendations"] = self._generate_recommendations(bottlenecks["bottlenecks"])
        
        return bottlenecks
        
    def _check_git_bottlenecks(self) -> List[Dict[str, Any]]:
        """Check for git-related bottlenecks"""
        bottlenecks = []
        
        if not self.git_data:
            return bottlenecks
            
        agents = self.git_data.get("agents", {})
        
        # Check for stuck agents (no commits in >1 hour with changes)
        for agent, data in agents.items():
            if data["uncommitted_changes"] > 0 and data.get("minutes_since_commit", 0) > 60:
                bottlenecks.append({
                    "type": "stuck_agent",
                    "agent": agent,
                    "severity": "high",
                    "details": f"{agent} has {data['uncommitted_changes']} uncommitted changes for {data['minutes_since_commit']} minutes",
                    "impact": "Work not being shared with team"
                })
                
            # Check for unpushed work
            if data["unpushed_commits"] > 3:
                bottlenecks.append({
                    "type": "unpushed_work",
                    "agent": agent,
                    "severity": "medium",
                    "details": f"{agent} has {data['unpushed_commits']} unpushed commits",
                    "impact": "Team cannot see or integrate work"
                })
                
            # Check for out-of-sync agents
            if data["commits_behind"] > 10:
                bottlenecks.append({
                    "type": "out_of_sync",
                    "agent": agent,
                    "severity": "high" if data["commits_behind"] > 20 else "medium",
                    "details": f"{agent} is {data['commits_behind']} commits behind parent branch",
                    "impact": "Increased merge conflict risk"
                })
                
        return bottlenecks
        
    def _check_github_bottlenecks(self) -> List[Dict[str, Any]]:
        """Check for GitHub/PR bottlenecks"""
        bottlenecks = []
        
        if not self.github_data:
            return bottlenecks
            
        # Check for stale PRs
        stale_prs = self.github_data.get("pr_summary", {}).get("stale_prs", [])
        for pr in stale_prs:
            if pr["age_hours"] > 4:
                bottlenecks.append({
                    "type": "stale_pr",
                    "pr_number": pr["number"],
                    "severity": "critical" if pr["age_hours"] > 8 else "high",
                    "details": f"PR #{pr['number']} open for {pr['age_hours']:.1f} hours",
                    "impact": "Blocking integration and deployment"
                })
                
        # Check integration status
        int_status = self.github_data.get("integration_status", {})
        if int_status.get("hours_since_last_integration", 0) > 4:
            bottlenecks.append({
                "type": "integration_delay",
                "severity": "critical",
                "details": f"No integration merge for {int_status['hours_since_last_integration']:.1f} hours",
                "impact": "Multiple features not being integrated"
            })
            
        return bottlenecks
        
    def _check_communication_bottlenecks(self) -> List[Dict[str, Any]]:
        """Check for communication pattern issues"""
        bottlenecks = []
        
        if not self.communication_data:
            return bottlenecks
            
        # Analyze last 2 hours of messages
        cutoff = datetime.now() - timedelta(hours=2)
        recent_messages = []
        
        for msg in self.communication_data:
            try:
                msg_time = datetime.fromisoformat(msg["timestamp"].replace('Z', '+00:00'))
                if msg_time.replace(tzinfo=None) > cutoff:
                    recent_messages.append(msg)
            except:
                continue
                
        # Check for lack of status updates
        status_updates = [m for m in recent_messages if "STATUS" in m.get("message", "")]
        if len(status_updates) < 3:  # Expect at least 3 status updates in 2 hours
            bottlenecks.append({
                "type": "poor_communication",
                "severity": "medium",
                "details": f"Only {len(status_updates)} status updates in last 2 hours",
                "impact": "Orchestrator lacks visibility into progress"
            })
            
        # Check for repeated requests (sign of non-responsiveness)
        message_counts = {}
        for msg in recent_messages:
            key = f"{msg['sender']['session']}→{msg['recipient']['session']}"
            similar_msg = msg["message"][:50]  # First 50 chars
            msg_key = f"{key}:{similar_msg}"
            message_counts[msg_key] = message_counts.get(msg_key, 0) + 1
            
        for msg_key, count in message_counts.items():
            if count > 2:  # Same message pattern sent 3+ times
                bottlenecks.append({
                    "type": "unresponsive_agent",
                    "severity": "high",
                    "details": f"Message pattern repeated {count} times: {msg_key}",
                    "impact": "Agent may be stuck or unresponsive"
                })
                break  # Only report once
                
        return bottlenecks
        
    def _check_integration_workflow(self) -> List[Dict[str, Any]]:
        """Check the overall integration workflow"""
        bottlenecks = []
        
        # Combine git and GitHub data
        if self.git_data and self.github_data:
            # Check if agents have pushed but no PR created
            agents_with_unpushed = 0
            for agent, data in self.git_data.get("agents", {}).items():
                if data.get("unpushed_commits", 0) > 0:
                    agents_with_unpushed += 1
                    
            open_prs = self.github_data.get("open_prs", 0)
            
            if agents_with_unpushed > 2 and open_prs == 0:
                bottlenecks.append({
                    "type": "integration_not_started",
                    "severity": "high",
                    "details": f"{agents_with_unpushed} agents have unpushed work but no integration PR exists",
                    "impact": "Integration cycle not initiated"
                })
                
        return bottlenecks
        
    def _generate_recommendations(self, bottlenecks: List[Dict[str, Any]]) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Group by type
        by_type = {}
        for b in bottlenecks:
            b_type = b["type"]
            if b_type not in by_type:
                by_type[b_type] = []
            by_type[b_type].append(b)
            
        # Generate type-specific recommendations
        if "stuck_agent" in by_type:
            agents = [b["agent"] for b in by_type["stuck_agent"]]
            recommendations.append(f"🚨 Ask {', '.join(agents)} to commit their changes immediately")
            
        if "stale_pr" in by_type:
            pr_nums = [f"#{b['pr_number']}" for b in by_type["stale_pr"]]
            recommendations.append(f"🚨 PM should merge PRs {', '.join(pr_nums)} with --admin flag")
            
        if "integration_delay" in by_type:
            recommendations.append("🚨 PM needs to create integration PR immediately")
            
        if "out_of_sync" in by_type:
            agents = [b["agent"] for b in by_type["out_of_sync"]]
            recommendations.append(f"⚠️ {', '.join(agents)} should pull from parent branch")
            
        if "unresponsive_agent" in by_type:
            recommendations.append("⚠️ Check if agents need /compact or credit exhaustion")
            
        return recommendations
        
    def save_bottleneck_report(self, bottlenecks: Dict[str, Any]):
        """Save bottleneck analysis"""
        today = datetime.now().strftime("%Y-%m-%d")
        report_dir = self.logs_dir / "workflow-analysis" / today
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / "bottlenecks.jsonl"
        with open(report_file, 'a') as f:
            json.dump(bottlenecks, f)
            f.write('\n')
            
    def notify_orchestrator(self, bottlenecks: Dict[str, Any]):
        """Send critical bottlenecks to orchestrator"""
        critical = [b for b in bottlenecks["bottlenecks"] if b["severity"] == "critical"]
        
        if critical:
            # Find orchestrator session
            orchestrator_session = self._find_orchestrator_session()
            if orchestrator_session:
                message = "🚨 WORKFLOW BOTTLENECKS DETECTED:\n"
                for b in critical[:3]:  # Top 3 critical issues
                    message += f"- {b['details']}\n"
                    
                if bottlenecks["recommendations"]:
                    message += "\nRECOMMENDED ACTIONS:\n"
                    for rec in bottlenecks["recommendations"][:3]:
                        message += f"{rec}\n"
                        
                # Use scm to send message
                try:
                    subprocess.run(['scm', orchestrator_session, message])
                except:
                    # Fallback to send-monitored-message.sh
                    script_path = self.script_dir.parent / "send-monitored-message.sh"
                    if script_path.exists():
                        subprocess.run([str(script_path), orchestrator_session, message])
                        
    def _find_orchestrator_session(self) -> str:
        """Find orchestrator tmux session"""
        try:
            result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                sessions = result.stdout.strip().split('\n')
                for session in sessions:
                    if 'orchestrator' in session.lower() or 'orc' in session.lower():
                        return f"{session}:0"
        except:
            pass
        return "tmux-orc:0"  # Default
        
    def print_summary(self, bottlenecks: Dict[str, Any]):
        """Print bottleneck summary"""
        print(f"\n=== Workflow Bottleneck Analysis ===")
        print(f"Time: {bottlenecks['timestamp']}")
        print(f"Health: {bottlenecks['workflow_health'].upper()}")
        
        if bottlenecks['bottlenecks']:
            print(f"\nBottlenecks Found: {len(bottlenecks['bottlenecks'])}")
            
            # Group by severity
            by_severity = {"critical": [], "high": [], "medium": [], "low": []}
            for b in bottlenecks['bottlenecks']:
                by_severity[b['severity']].append(b)
                
            for severity in ["critical", "high", "medium"]:
                if by_severity[severity]:
                    print(f"\n{severity.upper()} Issues:")
                    for b in by_severity[severity]:
                        print(f"  - [{b['type']}] {b['details']}")
                        print(f"    Impact: {b['impact']}")
                        
            if bottlenecks['recommendations']:
                print(f"\nRecommended Actions:")
                for i, rec in enumerate(bottlenecks['recommendations'], 1):
                    print(f"  {i}. {rec}")
        else:
            print("\n✓ No bottlenecks detected - workflow running smoothly")

def main():
    """Detect and report workflow bottlenecks"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Detect workflow bottlenecks')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--notify', action='store_true', help='Notify orchestrator of critical issues')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=300, help='Check interval in seconds')
    
    args = parser.parse_args()
    
    if args.continuous:
        import time
        print("Starting continuous bottleneck detection (Ctrl+C to stop)...")
        while True:
            detector = WorkflowBottleneckDetector()
            bottlenecks = detector.detect_bottlenecks()
            detector.save_bottleneck_report(bottlenecks)
            
            if args.json:
                print(json.dumps(bottlenecks, indent=2))
            else:
                detector.print_summary(bottlenecks)
                
            if args.notify and bottlenecks['workflow_health'] in ['critical', 'degraded']:
                detector.notify_orchestrator(bottlenecks)
                
            time.sleep(args.interval)
    else:
        detector = WorkflowBottleneckDetector()
        bottlenecks = detector.detect_bottlenecks()
        detector.save_bottleneck_report(bottlenecks)
        
        if args.json:
            print(json.dumps(bottlenecks, indent=2))
        else:
            detector.print_summary(bottlenecks)
            
        if args.notify and bottlenecks['workflow_health'] in ['critical', 'degraded']:
            detector.notify_orchestrator(bottlenecks)

if __name__ == "__main__":
    main()
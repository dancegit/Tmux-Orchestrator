#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Monitor GitHub activity (PRs, merges, etc) using gh CLI
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class GitHubActivityMonitor:
    def __init__(self, repo_path: Optional[Path] = None):
        self.script_dir = Path(__file__).parent
        self.registry_dir = self.script_dir.parent / "registry"
        self.log_dir = self.registry_dir / "logs" / "git-activity" / datetime.now().strftime("%Y-%m-%d")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Change to repo directory if provided
        if repo_path:
            import os
            os.chdir(repo_path)
            
    def check_gh_cli(self) -> bool:
        """Check if gh CLI is available and authenticated"""
        try:
            result = subprocess.run(['gh', 'auth', 'status'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
            
    def get_open_prs(self) -> List[Dict[str, Any]]:
        """Get all open PRs with details"""
        try:
            result = subprocess.run([
                'gh', 'pr', 'list', 
                '--json', 'number,title,author,createdAt,updatedAt,headRefName,baseRefName,mergeable,reviews,isDraft',
                '--limit', '50'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                prs = json.loads(result.stdout)
                
                # Calculate age and last activity for each PR
                for pr in prs:
                    created = datetime.fromisoformat(pr['createdAt'].replace('Z', '+00:00'))
                    updated = datetime.fromisoformat(pr['updatedAt'].replace('Z', '+00:00'))
                    
                    pr['age_hours'] = int((datetime.now(created.tzinfo) - created).total_seconds() / 3600)
                    pr['hours_since_update'] = int((datetime.now(updated.tzinfo) - updated).total_seconds() / 3600)
                    
                    # Determine PR type based on branch name
                    pr['pr_type'] = self._classify_pr(pr['headRefName'])
                    
                return prs
            return []
        except Exception as e:
            print(f"Error getting PRs: {e}")
            return []
            
    def _classify_pr(self, branch_name: str) -> str:
        """Classify PR based on branch name"""
        if branch_name.startswith('integration/'):
            return 'integration'
        elif branch_name.startswith('pm-'):
            return 'pm'
        elif branch_name.startswith('feature/'):
            return 'developer'
        elif branch_name.startswith('test/'):
            return 'tester'
        elif branch_name.startswith('testrunner/'):
            return 'testrunner'
        else:
            return 'other'
            
    def get_recent_merges(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recently merged PRs"""
        try:
            since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d')
            
            result = subprocess.run([
                'gh', 'pr', 'list',
                '--state', 'merged',
                '--json', 'number,title,author,mergedAt,headRefName,mergeCommit',
                '--limit', '50',
                '--search', f'merged:>{since}'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            return []
        except:
            return []
            
    def get_pr_details(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific PR"""
        try:
            result = subprocess.run([
                'gh', 'pr', 'view', str(pr_number),
                '--json', 'number,title,body,author,createdAt,updatedAt,commits,additions,deletions,files,reviews,mergeable'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            return None
        except:
            return None
            
    def check_integration_status(self) -> Dict[str, Any]:
        """Check status of integration workflow"""
        open_prs = self.get_open_prs()
        recent_merges = self.get_recent_merges(4)  # Last 4 hours
        
        integration_prs = [pr for pr in open_prs if pr['pr_type'] == 'integration']
        last_integration = None
        
        # Find last integration merge
        for merge in recent_merges:
            if merge.get('headRefName', '').startswith('integration/'):
                last_integration = merge
                break
                
        return {
            "open_integration_prs": len(integration_prs),
            "oldest_integration_pr": min([pr['age_hours'] for pr in integration_prs]) if integration_prs else None,
            "last_integration_merge": last_integration,
            "hours_since_last_integration": self._hours_since_merge(last_integration) if last_integration else None
        }
        
    def _hours_since_merge(self, merge: Dict[str, Any]) -> float:
        """Calculate hours since a merge"""
        if 'mergedAt' in merge:
            merged = datetime.fromisoformat(merge['mergedAt'].replace('Z', '+00:00'))
            return (datetime.now(merged.tzinfo) - merged).total_seconds() / 3600
        return 0
        
    def check_violations(self, prs: List[Dict[str, Any]], integration_status: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for workflow violations"""
        violations = []
        
        for pr in prs:
            # int-005: Merge PR within 2 hours
            if pr['age_hours'] > 2 and not pr.get('isDraft', False):
                violations.append({
                    "rule_id": "int-005",
                    "severity": "high",
                    "pr_number": pr['number'],
                    "details": f"PR #{pr['number']} ({pr['title']}) open for {pr['age_hours']} hours"
                })
                
            # workflow-001: No PR stuck >2 hours without activity
            if pr['hours_since_update'] > 2:
                violations.append({
                    "rule_id": "workflow-001",
                    "severity": "high",
                    "pr_number": pr['number'],
                    "details": f"PR #{pr['number']} no activity for {pr['hours_since_update']} hours"
                })
                
        # int-006: Integration cycle within 4 hours
        if integration_status['hours_since_last_integration'] and integration_status['hours_since_last_integration'] > 4:
            violations.append({
                "rule_id": "int-006",
                "severity": "critical",
                "details": f"No integration merge for {integration_status['hours_since_last_integration']:.1f} hours"
            })
            
        return violations
        
    def monitor_github_activity(self) -> Dict[str, Any]:
        """Main monitoring function"""
        if not self.check_gh_cli():
            return {"error": "gh CLI not available or not authenticated"}
            
        open_prs = self.get_open_prs()
        integration_status = self.check_integration_status()
        violations = self.check_violations(open_prs, integration_status)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "open_prs": len(open_prs),
            "pr_summary": self._summarize_prs(open_prs),
            "integration_status": integration_status,
            "violations": violations
        }
        
        return results
        
    def _summarize_prs(self, prs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize PR status"""
        summary = {
            "by_type": {},
            "by_age": {
                "<30min": 0,
                "30min-2h": 0,
                "2h-4h": 0,
                ">4h": 0
            },
            "stale_prs": []
        }
        
        for pr in prs:
            # By type
            pr_type = pr['pr_type']
            if pr_type not in summary['by_type']:
                summary['by_type'][pr_type] = 0
            summary['by_type'][pr_type] += 1
            
            # By age
            age = pr['age_hours']
            if age < 0.5:
                summary['by_age']['<30min'] += 1
            elif age < 2:
                summary['by_age']['30min-2h'] += 1
            elif age < 4:
                summary['by_age']['2h-4h'] += 1
            else:
                summary['by_age']['>4h'] += 1
                
            # Stale PRs
            if age > 2 or pr['hours_since_update'] > 2:
                summary['stale_prs'].append({
                    "number": pr['number'],
                    "title": pr['title'],
                    "age_hours": pr['age_hours'],
                    "inactive_hours": pr['hours_since_update']
                })
                
        return summary
        
    def save_activity_log(self, results: Dict[str, Any]):
        """Save activity to log file"""
        log_file = self.log_dir / "github_activity.jsonl"
        
        with open(log_file, 'a') as f:
            json.dump(results, f)
            f.write('\n')
            
        # Save violations separately
        if results.get("violations"):
            violations_file = self.log_dir / "github_violations.jsonl"
            for violation in results["violations"]:
                violation["timestamp"] = results["timestamp"]
                with open(violations_file, 'a') as f:
                    json.dump(violation, f)
                    f.write('\n')
                    
    def print_summary(self, results: Dict[str, Any]):
        """Print activity summary"""
        print(f"\n=== GitHub Activity Monitor ===")
        print(f"Time: {results['timestamp']}")
        
        if "error" in results:
            print(f"Error: {results['error']}")
            return
            
        print(f"\nOpen PRs: {results['open_prs']}")
        
        if results['open_prs'] > 0:
            print("\nPR Summary:")
            summary = results['pr_summary']
            
            print("  By Type:")
            for pr_type, count in summary['by_type'].items():
                print(f"    {pr_type}: {count}")
                
            print("  By Age:")
            for age_range, count in summary['by_age'].items():
                if count > 0:
                    status = "✓" if age_range in ["<30min", "30min-2h"] else "⚠️" if age_range == "2h-4h" else "❌"
                    print(f"    {status} {age_range}: {count}")
                    
        print(f"\nIntegration Status:")
        int_status = results['integration_status']
        if int_status['hours_since_last_integration']:
            hours = int_status['hours_since_last_integration']
            status = "✓" if hours < 2 else "⚠️" if hours < 4 else "❌"
            print(f"  {status} Last integration: {hours:.1f} hours ago")
        else:
            print(f"  ⚠️ No recent integration merges")
            
        if int_status['open_integration_prs'] > 0:
            print(f"  ⚠️ {int_status['open_integration_prs']} open integration PRs")
            
        if results.get('violations'):
            print(f"\n❌ {len(results['violations'])} violations detected:")
            for v in results['violations']:
                print(f"  - [{v['rule_id']}] {v['details']}")
        else:
            print(f"\n✓ No violations detected")
            
        if summary.get('stale_prs'):
            print(f"\n⚠️ Stale PRs requiring attention:")
            for pr in summary['stale_prs'][:5]:  # Show top 5
                print(f"  - PR #{pr['number']}: {pr['title'][:50]}...")
                print(f"    Age: {pr['age_hours']:.1f}h, Inactive: {pr['inactive_hours']:.1f}h")

def main():
    """Monitor GitHub activity"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor GitHub PR and merge activity')
    parser.add_argument('--repo', help='Repository path')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=300, help='Check interval in seconds (default: 300)')
    
    args = parser.parse_args()
    
    monitor = GitHubActivityMonitor(Path(args.repo) if args.repo else None)
    
    if args.continuous:
        import time
        print("Starting continuous GitHub monitoring (Ctrl+C to stop)...")
        while True:
            results = monitor.monitor_github_activity()
            monitor.save_activity_log(results)
            
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                monitor.print_summary(results)
                
            time.sleep(args.interval)
    else:
        results = monitor.monitor_github_activity()
        monitor.save_activity_log(results)
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            monitor.print_summary(results)

if __name__ == "__main__":
    main()
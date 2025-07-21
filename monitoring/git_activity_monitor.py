#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Monitor git activity across all agent worktrees for compliance
"""

import os
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class GitActivityMonitor:
    def __init__(self, project_dir: Optional[Path] = None):
        self.script_dir = Path(__file__).parent
        self.registry_dir = self.script_dir.parent / "registry"
        
        # Find active projects from registry
        if project_dir:
            self.project_dir = Path(project_dir)
        else:
            self.project_dir = self._find_active_project()
            
        self.worktrees_dir = self.project_dir / "worktrees" if self.project_dir else None
        self.log_dir = self.registry_dir / "logs" / "git-activity" / datetime.now().strftime("%Y-%m-%d")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    def _find_active_project(self) -> Optional[Path]:
        """Find the most recently active project from registry"""
        projects_dir = self.registry_dir / "projects"
        if not projects_dir.exists():
            return None
            
        # Find most recently modified project
        latest_project = None
        latest_time = 0
        
        for project in projects_dir.iterdir():
            if project.is_dir() and (project / "worktrees").exists():
                mtime = project.stat().st_mtime
                if mtime > latest_time:
                    latest_time = mtime
                    latest_project = project
                    
        return latest_project
        
    def monitor_all_worktrees(self) -> Dict[str, Any]:
        """Monitor git activity across all agent worktrees"""
        if not self.worktrees_dir or not self.worktrees_dir.exists():
            return {"error": "No worktrees directory found"}
            
        results = {
            "timestamp": datetime.now().isoformat(),
            "project": str(self.project_dir),
            "agents": {},
            "violations": []
        }
        
        # Check each agent worktree
        for worktree in self.worktrees_dir.iterdir():
            if worktree.is_dir() and (worktree / ".git").exists():
                agent_name = worktree.name
                agent_data = self._check_worktree(worktree, agent_name)
                results["agents"][agent_name] = agent_data
                
                # Check for violations
                violations = self._check_violations(agent_data, agent_name)
                results["violations"].extend(violations)
                
        return results
        
    def _check_worktree(self, worktree_path: Path, agent_name: str) -> Dict[str, Any]:
        """Check git status for a single worktree"""
        os.chdir(worktree_path)
        
        data = {
            "worktree": str(worktree_path),
            "current_branch": self._get_current_branch(),
            "parent_branch": self._get_parent_branch(),
            "last_commit_time": self._get_last_commit_time(),
            "uncommitted_changes": self._count_uncommitted_changes(),
            "unpushed_commits": self._count_unpushed_commits(),
            "commits_behind": self._get_commits_behind(),
            "commits_ahead": self._get_commits_ahead(),
            "branch_age": self._get_branch_age(),
            "remote_status": self._check_remote_status()
        }
        
        # Calculate derived metrics
        if data["last_commit_time"]:
            last_commit = datetime.fromisoformat(data["last_commit_time"])
            # Handle timezone-aware datetime
            now = datetime.now(last_commit.tzinfo) if last_commit.tzinfo else datetime.now()
            data["minutes_since_commit"] = int((now - last_commit).total_seconds() / 60)
        else:
            data["minutes_since_commit"] = None
            
        # Check branch naming convention
        data["branch_name_compliant"] = self._check_branch_naming(data["current_branch"], agent_name)
        
        return data
        
    def _get_current_branch(self) -> str:
        """Get current branch name"""
        try:
            result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                  capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
            
    def _get_parent_branch(self) -> str:
        """Get parent/upstream branch"""
        try:
            # Try to get upstream branch
            result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split('/')[-1]
                
            # Default to main/master
            return "main"
        except:
            return "main"
            
    def _get_last_commit_time(self) -> Optional[str]:
        """Get timestamp of last commit"""
        try:
            result = subprocess.run(['git', 'log', '-1', '--format=%cI'],
                                  capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else None
        except:
            return None
            
    def _count_uncommitted_changes(self) -> int:
        """Count uncommitted changes"""
        try:
            result = subprocess.run(['git', 'status', '--porcelain'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split('\n') if l]
                return len(lines)
            return 0
        except:
            return 0
            
    def _count_unpushed_commits(self) -> int:
        """Count commits not pushed to remote"""
        try:
            result = subprocess.run(['git', 'cherry', '-v'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split('\n') if l.startswith('+')]
                return len(lines)
            return 0
        except:
            return 0
            
    def _get_commits_behind(self) -> int:
        """Get number of commits behind parent branch"""
        try:
            parent = self._get_parent_branch()
            result = subprocess.run(['git', 'rev-list', '--count', f'HEAD..origin/{parent}'],
                                  capture_output=True, text=True)
            return int(result.stdout.strip()) if result.returncode == 0 else 0
        except:
            return 0
            
    def _get_commits_ahead(self) -> int:
        """Get number of commits ahead of parent branch"""
        try:
            parent = self._get_parent_branch()
            result = subprocess.run(['git', 'rev-list', '--count', f'origin/{parent}..HEAD'],
                                  capture_output=True, text=True)
            return int(result.stdout.strip()) if result.returncode == 0 else 0
        except:
            return 0
            
    def _get_branch_age(self) -> Optional[int]:
        """Get age of current branch in hours"""
        try:
            # Get first commit on this branch not on parent
            parent = self._get_parent_branch()
            result = subprocess.run(['git', 'log', f'origin/{parent}..HEAD', '--format=%cI', '--reverse'],
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                first_commit_time = result.stdout.strip().split('\n')[0]
                first_commit = datetime.fromisoformat(first_commit_time)
                # Handle timezone-aware datetime
                now = datetime.now(first_commit.tzinfo) if first_commit.tzinfo else datetime.now()
                return int((now - first_commit).total_seconds() / 3600)
            return None
        except:
            return None
            
    def _check_remote_status(self) -> Dict[str, Any]:
        """Check if branch has remote tracking"""
        try:
            # Check if branch has upstream
            result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', '@{u}'],
                                  capture_output=True, text=True)
            has_upstream = result.returncode == 0
            
            # Check if it's pushed
            if has_upstream:
                result = subprocess.run(['git', 'diff', '@{u}', '--quiet'],
                                      capture_output=True)
                in_sync = result.returncode == 0
            else:
                in_sync = False
                
            return {
                "has_upstream": has_upstream,
                "in_sync": in_sync
            }
        except:
            return {"has_upstream": False, "in_sync": False}
            
    def _check_branch_naming(self, branch: str, agent: str) -> bool:
        """Check if branch follows agent-specific naming convention"""
        agent_prefixes = {
            "developer": "feature/",
            "project-manager": "pm-feature/",
            "project_manager": "pm-feature/",
            "tester": "test/",
            "testrunner": "testrunner/",
            "researcher": "research/",
            "devops": "devops/",
            "code_reviewer": "review/",
            "documentation_writer": "docs/"
        }
        
        expected_prefix = agent_prefixes.get(agent, "")
        if not expected_prefix:
            return True  # No specific requirement
            
        return branch.startswith(expected_prefix)
        
    def _check_violations(self, agent_data: Dict[str, Any], agent_name: str) -> List[Dict[str, Any]]:
        """Check for rule violations"""
        violations = []
        
        # git-002: 30-minute commit rule
        if agent_data["uncommitted_changes"] > 0 and agent_data["minutes_since_commit"]:
            if agent_data["minutes_since_commit"] > 30:
                violations.append({
                    "rule_id": "git-002",
                    "agent": agent_name,
                    "severity": "high",
                    "details": f"{agent_data['minutes_since_commit']} minutes since last commit with {agent_data['uncommitted_changes']} uncommitted changes"
                })
                
        # git-005: Agent-specific branch names
        if not agent_data["branch_name_compliant"]:
            violations.append({
                "rule_id": "git-005",
                "agent": agent_name,
                "severity": "medium",
                "details": f"Branch '{agent_data['current_branch']}' doesn't follow naming convention for {agent_name}"
            })
            
        # git-006: Push within 15 minutes
        if agent_data["unpushed_commits"] > 0 and agent_data["minutes_since_commit"]:
            if agent_data["minutes_since_commit"] > 15:
                violations.append({
                    "rule_id": "git-006",
                    "agent": agent_name,
                    "severity": "high",
                    "details": f"{agent_data['unpushed_commits']} unpushed commits, last commit {agent_data['minutes_since_commit']} minutes ago"
                })
                
        # git-007: Set upstream
        if not agent_data["remote_status"]["has_upstream"] and agent_data["commits_ahead"] > 0:
            violations.append({
                "rule_id": "git-007",
                "agent": agent_name,
                "severity": "medium",
                "details": "Branch has commits but no upstream set"
            })
            
        # git-010: Maximum 20 commits behind
        if agent_data["commits_behind"] > 20:
            violations.append({
                "rule_id": "git-010",
                "agent": agent_name,
                "severity": "high",
                "details": f"{agent_data['commits_behind']} commits behind parent branch"
            })
            
        return violations
        
    def save_activity_log(self, results: Dict[str, Any]):
        """Save activity log to file"""
        log_file = self.log_dir / "git_activity.jsonl"
        
        with open(log_file, 'a') as f:
            json.dump(results, f)
            f.write('\n')
            
        # Save violations separately
        if results["violations"]:
            violations_file = self.log_dir / "git_violations.jsonl"
            for violation in results["violations"]:
                violation["timestamp"] = results["timestamp"]
                with open(violations_file, 'a') as f:
                    json.dump(violation, f)
                    f.write('\n')
                    
    def print_summary(self, results: Dict[str, Any]):
        """Print summary of git activity"""
        print(f"\n=== Git Activity Monitor ===")
        print(f"Time: {results['timestamp']}")
        print(f"Project: {Path(results['project']).name}")
        print(f"\nAgent Status:")
        
        for agent, data in results["agents"].items():
            status_parts = []
            
            # Commit status
            if data["minutes_since_commit"] is not None:
                if data["minutes_since_commit"] > 30 and data["uncommitted_changes"] > 0:
                    status_parts.append(f"❌ {data['minutes_since_commit']}m since commit")
                else:
                    status_parts.append(f"✓ {data['minutes_since_commit']}m since commit")
            
            # Changes
            if data["uncommitted_changes"] > 0:
                status_parts.append(f"{data['uncommitted_changes']} changes")
                
            # Push status
            if data["unpushed_commits"] > 0:
                status_parts.append(f"⚠️ {data['unpushed_commits']} unpushed")
                
            # Sync status
            if data["commits_behind"] > 20:
                status_parts.append(f"❌ {data['commits_behind']} behind")
            elif data["commits_behind"] > 0:
                status_parts.append(f"⚠️ {data['commits_behind']} behind")
                
            print(f"  {agent:20} {data['current_branch']:30} {' | '.join(status_parts)}")
            
        if results["violations"]:
            print(f"\n❌ {len(results['violations'])} violations detected:")
            for v in results["violations"]:
                print(f"  - [{v['rule_id']}] {v['agent']}: {v['details']}")
        else:
            print(f"\n✓ No violations detected")

def main():
    """Monitor git activity across agent worktrees"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor git activity for compliance')
    parser.add_argument('--project', help='Project directory path')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=120, help='Check interval in seconds (default: 120)')
    
    args = parser.parse_args()
    
    monitor = GitActivityMonitor(Path(args.project) if args.project else None)
    
    if args.continuous:
        import time
        print("Starting continuous git monitoring (Ctrl+C to stop)...")
        while True:
            results = monitor.monitor_all_worktrees()
            monitor.save_activity_log(results)
            
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                monitor.print_summary(results)
                
            time.sleep(args.interval)
    else:
        results = monitor.monitor_all_worktrees()
        monitor.save_activity_log(results)
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            monitor.print_summary(results)

if __name__ == "__main__":
    main()
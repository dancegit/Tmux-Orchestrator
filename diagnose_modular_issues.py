#!/usr/bin/env python3
"""
Diagnostic tool for identifying and fixing modularization issues
in the Tmux Orchestrator system.
"""

import sys
import os
import subprocess
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

TMUX_ORCHESTRATOR_HOME = Path(os.environ.get('TMUX_ORCHESTRATOR_HOME', '/home/clauderun/Tmux-Orchestrator'))
sys.path.insert(0, str(TMUX_ORCHESTRATOR_HOME))

class ModularizationDiagnostic:
    def __init__(self):
        self.issues = []
        self.fixes_applied = []
        self.tmux_path = TMUX_ORCHESTRATOR_HOME
        
    def check_module_structure(self):
        """Check if modular packages exist and are properly structured."""
        print("\n🔍 Checking module structure...")
        
        # Check tmux_orchestrator package
        tmux_orch_path = self.tmux_path / 'tmux_orchestrator'
        if tmux_orch_path.exists():
            print(f"✅ tmux_orchestrator package found at {tmux_orch_path}")
            
            # Check critical submodules
            critical_modules = [
                'core/orchestrator.py',
                'claude/oauth_manager.py',
                'claude/initialization.py',
                'cli/enhanced_cli.py'
            ]
            
            for module in critical_modules:
                module_path = tmux_orch_path / module
                if module_path.exists():
                    print(f"  ✅ {module} exists")
                else:
                    print(f"  ❌ {module} missing")
                    self.issues.append(f"Missing module: {module}")
        else:
            print(f"❌ tmux_orchestrator package NOT found")
            self.issues.append("tmux_orchestrator package missing")
            
        # Check scheduler_modules package
        sched_mod_path = self.tmux_path / 'scheduler_modules'
        if sched_mod_path.exists():
            print(f"✅ scheduler_modules package found at {sched_mod_path}")
        else:
            print(f"⚠️  scheduler_modules package NOT found (Phase 2+ not started)")
            
    def check_cli_functionality(self):
        """Test if tmux_orchestrator_cli.py can be imported and run."""
        print("\n🔍 Testing tmux_orchestrator_cli.py...")
        
        cli_path = self.tmux_path / 'tmux_orchestrator_cli.py'
        if not cli_path.exists():
            print(f"❌ tmux_orchestrator_cli.py not found")
            self.issues.append("tmux_orchestrator_cli.py missing")
            return
            
        # Test import
        try:
            import tmux_orchestrator_cli
            print("✅ tmux_orchestrator_cli.py imports successfully")
        except ImportError as e:
            print(f"❌ Import error: {e}")
            self.issues.append(f"CLI import error: {e}")
            
        # Check if it has the run command
        try:
            result = subprocess.run(
                ['python3', str(cli_path), 'run', '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print("✅ tmux_orchestrator_cli.py run command works")
            else:
                print(f"❌ run command failed: {result.stderr}")
                self.issues.append(f"CLI run command error: {result.stderr[:200]}")
        except Exception as e:
            print(f"❌ Failed to test CLI: {e}")
            self.issues.append(f"CLI test failed: {e}")
            
    def check_orchestrator_delegation(self):
        """Check if Orchestrator properly delegates to auto_orchestrate.py."""
        print("\n🔍 Checking Orchestrator delegation...")
        
        orch_path = self.tmux_path / 'tmux_orchestrator' / 'core' / 'orchestrator.py'
        if not orch_path.exists():
            print(f"❌ orchestrator.py not found")
            self.issues.append("orchestrator.py missing")
            return
            
        # Check for start_orchestration method
        with open(orch_path, 'r') as f:
            content = f.read()
            
        if 'def start_orchestration' in content:
            print("✅ start_orchestration method exists")
            
            # Check if it delegates to auto_orchestrate.py
            if 'auto_orchestrate.py' in content or 'subprocess' in content:
                print("✅ Appears to delegate to auto_orchestrate.py")
            else:
                print("⚠️  May not properly delegate to auto_orchestrate.py")
                self.issues.append("Orchestrator may not delegate properly")
        else:
            print("❌ start_orchestration method missing")
            self.issues.append("start_orchestration method missing in Orchestrator")
            
    def check_recent_failures(self):
        """Analyze recent project failures from the queue."""
        print("\n🔍 Analyzing recent queue failures...")
        
        db_path = self.tmux_path / 'task_queue.db'
        if not db_path.exists():
            print("❌ task_queue.db not found")
            return
            
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Get recent failed projects
            cursor.execute("""
                SELECT id, spec_path, error_message, completed_at
                FROM project_queue
                WHERE status = 'FAILED'
                AND datetime(completed_at, 'unixepoch') > datetime('now', '-24 hours')
                ORDER BY completed_at DESC
                LIMIT 10
            """)
            
            failures = cursor.fetchall()
            
            if failures:
                print(f"\n📊 Found {len(failures)} recent failures:")
                
                modular_failures = 0
                for project_id, spec_path, error_message, completed_at in failures:
                    spec_name = Path(spec_path).stem if spec_path else f"Project {project_id}"
                    if error_message and ('tmux_orchestrator_cli' in error_message or 'Subprocess failed' in error_message):
                        modular_failures += 1
                        print(f"  ❌ Project {project_id} ({spec_name}): {error_message[:100]}")
                        
                if modular_failures > 0:
                    print(f"\n⚠️  {modular_failures} failures related to modularization")
                    self.issues.append(f"{modular_failures} recent modularization-related failures")
            else:
                print("✅ No recent failures in last 24 hours")
                
            conn.close()
        except Exception as e:
            print(f"❌ Database error: {e}")
            
    def suggest_fixes(self):
        """Suggest fixes for identified issues."""
        print("\n🔧 Suggested Fixes:")
        
        if not self.issues:
            print("✅ No critical issues found!")
            return
            
        for issue in self.issues:
            print(f"\n❌ Issue: {issue}")
            
            if "tmux_orchestrator package missing" in issue:
                print("  Fix: The modular package structure needs to be created.")
                print("       Run: python3 migrate_to_modular.py")
                
            elif "start_orchestration method missing" in issue:
                print("  Fix: The Orchestrator class needs the start_orchestration method.")
                print("       This should delegate to auto_orchestrate.py via subprocess.")
                
            elif "CLI import error" in issue:
                print("  Fix: Check module imports in tmux_orchestrator_cli.py")
                print("       Ensure all tmux_orchestrator modules are importable.")
                
            elif "modularization-related failures" in issue:
                print("  Fix: The CLI is being called but failing to create sessions.")
                print("       1. Check if auto_orchestrate.py path is correct in orchestrator.py")
                print("       2. Verify subprocess calls are properly formatted")
                print("       3. Check for missing environment variables")
                
    def generate_report(self):
        """Generate a modularization status report."""
        report_path = self.tmux_path / 'logs' / 'modularization_diagnostic.json'
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'issues_found': len(self.issues),
            'issues': self.issues,
            'fixes_applied': self.fixes_applied,
            'recommendations': []
        }
        
        # Add recommendations based on issues
        if self.issues:
            if any('package missing' in i for i in self.issues):
                report['recommendations'].append("Run migration script to create package structure")
            if any('failures' in i for i in self.issues):
                report['recommendations'].append("Fix orchestrator delegation to auto_orchestrate.py")
                report['recommendations'].append("Update CLI to handle fallback correctly")
                
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\n📄 Report saved to: {report_path}")
        return report
        
    def run_diagnostics(self):
        """Run all diagnostic checks."""
        print("=" * 60)
        print("TMUX ORCHESTRATOR MODULARIZATION DIAGNOSTIC")
        print("=" * 60)
        
        self.check_module_structure()
        self.check_cli_functionality()
        self.check_orchestrator_delegation()
        self.check_recent_failures()
        self.suggest_fixes()
        
        report = self.generate_report()
        
        print("\n" + "=" * 60)
        print(f"SUMMARY: {len(self.issues)} issues found")
        if self.issues:
            print("\nTop Priority:")
            print(f"  • {self.issues[0]}")
        print("=" * 60)
        
        return len(self.issues) == 0

if __name__ == "__main__":
    diagnostic = ModularizationDiagnostic()
    success = diagnostic.run_diagnostics()
    sys.exit(0 if success else 1)
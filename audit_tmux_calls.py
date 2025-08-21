#!/usr/bin/env python3
"""
Tmux Call Audit Script
Scans the codebase for all tmux-related calls to track migration progress
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

class TmuxCallAuditor:
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)
        self.patterns = {
            'direct_tmux': [
                r'\btmux\s+\w+',  # Direct tmux commands
                r'`tmux\s+[^`]+`',  # Backtick tmux commands
                r'"tmux\s+[^"]+\"',  # Quoted tmux commands
                r"'tmux\s+[^']+\'",  # Single quoted tmux commands
            ],
            'subprocess_tmux': [
                r'subprocess\.\w+\(\s*\[?\s*[\'"]tmux[\'"]',  # subprocess.run(['tmux'...
                r'subprocess\.\w+\(\s*[\'"]tmux\s+',  # subprocess.run('tmux ...
                r'Popen\(\s*\[?\s*[\'"]tmux[\'"]',  # Popen(['tmux'...
            ],
            'tmux_vars': [
                r'\$TMUX\b',  # $TMUX environment variable
                r'os\.environ\[[\'"]\s*TMUX\s*[\'"]\]',  # os.environ['TMUX']
            ],
            'tmux_manager_usage': [
                r'from\s+tmux_utils\s+import.*TmuxManager',  # TmuxManager imports
                r'TmuxManager\(',  # TmuxManager instantiation
                r'tmux_send_message\(',  # Convenience function usage
                r'USE_TMUX_MANAGER',  # Feature flag usage
            ]
        }
    
    def scan_file(self, file_path: Path) -> Dict[str, List[Tuple[int, str]]]:
        """Scan a file for tmux-related patterns"""
        results = {category: [] for category in self.patterns}
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            for line_num, line in enumerate(lines, 1):
                line_clean = line.strip()
                if not line_clean or line_clean.startswith('#'):
                    continue
                    
                for category, patterns in self.patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            results[category].append((line_num, line.strip()))
                            
        except Exception as e:
            print(f"Error reading {file_path}: {e}", file=sys.stderr)
            
        return results
    
    def should_scan_file(self, file_path: Path) -> bool:
        """Determine if a file should be scanned"""
        # Skip binary files, hidden files, and irrelevant directories
        if file_path.name.startswith('.'):
            return False
            
        skip_dirs = {'.git', '__pycache__', 'node_modules', '.pytest_cache', 'venv', 'env'}
        if any(part in skip_dirs for part in file_path.parts):
            return False
            
        # Scan relevant file types
        relevant_extensions = {'.py', '.sh', '.bash', '.zsh', '.fish', '.pl', '.rb', '.js', '.ts'}
        if file_path.suffix.lower() in relevant_extensions:
            return True
            
        # Scan files without extensions that might be scripts
        if not file_path.suffix and file_path.is_file():
            try:
                with open(file_path, 'rb') as f:
                    first_line = f.readline()
                    if first_line.startswith(b'#!'):
                        return True
            except:
                pass
                
        return False
    
    def audit_codebase(self) -> Dict[str, Dict[str, List[Tuple[int, str]]]]:
        """Audit the entire codebase for tmux calls"""
        results = {}
        
        for file_path in self.root_dir.rglob('*'):
            if file_path.is_file() and self.should_scan_file(file_path):
                relative_path = file_path.relative_to(self.root_dir)
                file_results = self.scan_file(file_path)
                
                # Only include files that have matches
                if any(matches for matches in file_results.values()):
                    results[str(relative_path)] = file_results
        
        return results
    
    def generate_report(self, results: Dict[str, Dict[str, List[Tuple[int, str]]]]) -> str:
        """Generate a human-readable report"""
        report = []
        report.append("🔍 TMUX CALL AUDIT REPORT")
        report.append("=" * 50)
        report.append("")
        
        # Summary statistics
        total_files = len(results)
        total_calls = sum(
            len(matches) 
            for file_results in results.values() 
            for matches in file_results.values()
        )
        
        migrated_files = len([
            f for f, file_results in results.items()
            if any(file_results.get('tmux_manager_usage', []))
        ])
        
        unmigrated_files = len([
            f for f, file_results in results.items()
            if any(file_results.get('direct_tmux', [])) or any(file_results.get('subprocess_tmux', []))
        ])
        
        report.append(f"📊 SUMMARY:")
        report.append(f"  Total files with tmux calls: {total_files}")
        report.append(f"  Total tmux-related patterns found: {total_calls}")
        report.append(f"  Files using TmuxManager: {migrated_files}")
        report.append(f"  Files needing migration: {unmigrated_files}")
        report.append(f"  Migration progress: {migrated_files}/{total_files} files ({migrated_files/max(total_files,1)*100:.1f}%)")
        report.append("")
        
        # Priority migration targets
        priority_files = []
        for file_path, file_results in results.items():
            direct_count = len(file_results.get('direct_tmux', []))
            subprocess_count = len(file_results.get('subprocess_tmux', []))
            total_count = direct_count + subprocess_count
            
            if total_count > 0:
                priority_files.append((file_path, total_count, direct_count, subprocess_count))
        
        priority_files.sort(key=lambda x: x[1], reverse=True)
        
        if priority_files:
            report.append("🎯 PRIORITY MIGRATION TARGETS:")
            for file_path, total, direct, subprocess in priority_files[:10]:
                report.append(f"  {file_path}: {total} calls ({direct} direct, {subprocess} subprocess)")
            report.append("")
        
        # Files already using TmuxManager
        migrated = [f for f, file_results in results.items() if any(file_results.get('tmux_manager_usage', []))]
        if migrated:
            report.append("✅ MIGRATED FILES (using TmuxManager):")
            for file_path in sorted(migrated):
                usage_count = len(results[file_path].get('tmux_manager_usage', []))
                report.append(f"  {file_path}: {usage_count} TmuxManager calls")
            report.append("")
        
        # Detailed breakdown by file
        report.append("📋 DETAILED BREAKDOWN:")
        report.append("")
        
        for file_path, file_results in sorted(results.items()):
            report.append(f"📄 {file_path}")
            
            for category, matches in file_results.items():
                if matches:
                    emoji = {
                        'direct_tmux': '🔴',
                        'subprocess_tmux': '🟡', 
                        'tmux_vars': '🔵',
                        'tmux_manager_usage': '✅'
                    }.get(category, '⚪')
                    
                    report.append(f"  {emoji} {category.replace('_', ' ').title()}: {len(matches)} matches")
                    for line_num, line in matches[:5]:  # Show first 5 matches
                        report.append(f"    Line {line_num}: {line[:80]}{'...' if len(line) > 80 else ''}")
                    if len(matches) > 5:
                        report.append(f"    ... and {len(matches) - 5} more")
            report.append("")
        
        return "\n".join(report)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Audit tmux calls in codebase')
    parser.add_argument('--dir', default='.', help='Directory to scan (default: current)')
    parser.add_argument('--output', help='Output file for report (default: stdout)')
    parser.add_argument('--summary-only', action='store_true', help='Show only summary statistics')
    
    args = parser.parse_args()
    
    auditor = TmuxCallAuditor(args.dir)
    results = auditor.audit_codebase()
    
    if args.summary_only:
        # Quick summary
        total_files = len(results)
        migrated_files = len([
            f for f, file_results in results.items()
            if any(file_results.get('tmux_manager_usage', []))
        ])
        unmigrated_files = len([
            f for f, file_results in results.items()
            if any(file_results.get('direct_tmux', [])) or any(file_results.get('subprocess_tmux', []))
        ])
        
        print(f"Files with tmux calls: {total_files}")
        print(f"Migrated to TmuxManager: {migrated_files}")
        print(f"Need migration: {unmigrated_files}")
        print(f"Progress: {migrated_files/max(total_files,1)*100:.1f}%")
    else:
        report = auditor.generate_report(results)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"Report written to {args.output}")
        else:
            print(report)

if __name__ == "__main__":
    main()
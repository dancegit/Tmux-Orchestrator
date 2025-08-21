#!/usr/bin/env python3
"""
Debug pattern matching for session detection
"""

import subprocess
import os
import time

def debug_pattern_matching():
    spec_path = "/home/clauderun/signalmatrix/signalmatrix_org/signalmatrix-slice-reporting/REPORTING_MVP_IMPLEMENTATION.md"
    
    print("🔍 Debug Pattern Matching")
    print("=" * 40)
    
    # Generate keywords like the scheduler does
    project_keywords = []
    if spec_path:
        # Extract keywords from spec path for pattern matching
        path_parts = spec_path.lower().split('/')
        print(f"Path parts: {path_parts}")
        
        for part in path_parts:
            # Look for relevant parts
            if any(term in part for term in ['elliott', 'wave', 'options', 'reporting', 'backtesting']):
                project_keywords.extend(part.split('_'))
                project_keywords.extend(part.split('-'))
        
        # Add specific keywords based on spec name patterns
        spec_name = os.path.basename(spec_path).lower()
        print(f"Spec name: {spec_name}")
        
        if 'reporting' in spec_name:
            project_keywords.extend(['elliott', 'wave', 'options', 'report', 'reporting', 'generation'])
        elif 'backtesting' in spec_name:
            project_keywords.extend(['elliott', 'wave', 'backtesting', 'implementation'])
        elif 'elliott' in spec_name:
            project_keywords.extend(['elliott', 'wave'])
    
    print(f"Generated keywords: {project_keywords}")
    
    # Get active sessions
    result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}:#{session_created}'], 
                          capture_output=True, text=True)
    
    print(f"\nActive sessions:")
    for line in result.stdout.strip().split('\n'):
        if ':' not in line:
            continue
            
        session_name, created_str = line.split(':', 1)
        print(f"  {session_name}")
        
        # Test matching logic
        is_project_session = False
        
        # Direct impl pattern match
        if '-impl-' in session_name:
            is_project_session = True
            print(f"    ✓ Matches -impl- pattern")
        
        # Keyword-based match (more flexible)
        matching_keywords = [keyword for keyword in project_keywords 
                           if keyword and len(keyword) > 2 and keyword in session_name.lower()]
        if matching_keywords:
            is_project_session = True
            print(f"    ✓ Matches keywords: {matching_keywords}")
        
        # Elliott Wave specific patterns
        elliott_matches = []
        if 'elliott' in session_name.lower():
            elliott_matches.append('elliott')
        if any(term in session_name.lower() for term in ['wave', 'options', 'report', 'backtesting']):
            for term in ['wave', 'options', 'report', 'backtesting']:
                if term in session_name.lower():
                    elliott_matches.append(term)
        
        if len(elliott_matches) >= 2:  # elliott + at least one other term
            is_project_session = True
            print(f"    ✓ Matches Elliott Wave pattern: {elliott_matches}")
        
        print(f"    → Final match result: {is_project_session}")
        
        # Check if session is recent enough to be relevant
        now = int(time.time())
        try:
            created_time = int(created_str)
            age_hours = (now - created_time) // 3600
            print(f"    → Session age: {age_hours} hours")
            if now - created_time > 28800:  # Skip sessions older than 8 hours
                print(f"    → Too old (>8 hours), would be skipped")
            else:
                print(f"    → Recent enough, would be considered")
        except:
            print(f"    → Could not parse creation time: {created_str}")

if __name__ == "__main__":
    debug_pattern_matching()
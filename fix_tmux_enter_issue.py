#!/usr/bin/env python3
"""
Fix script to ensure all tmux send-keys commands properly handle Enter key.
This addresses the issue where MCP markers and other messages aren't executed.
"""

import os
import re
import shutil
from pathlib import Path

def fix_tmux_send_keys_in_file(filepath):
    """Fix tmux send-keys commands to ensure Enter is properly sent."""
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    fixes_made = []
    
    # Pattern 1: Fix tmux send-keys that might not have Enter
    # Look for tmux send-keys without immediate Enter
    pattern1 = r'(tmux\s+send-keys[^;]*?)(\s*(?:;|&&|\|\||$))'
    
    def check_and_fix_pattern1(match):
        command = match.group(1)
        separator = match.group(2)
        
        # Check if this already has Enter or C-m
        if 'Enter' in command or 'C-m' in command:
            return match.group(0)
        
        # Check if the next line has Enter
        full_match = match.group(0)
        if separator.strip() == '':
            # This might be followed by Enter on next line
            return full_match
            
        # Add Enter before separator
        fixed = f"{command} Enter{separator}"
        fixes_made.append(f"Added Enter to: {command.strip()}")
        return fixed
    
    content = re.sub(pattern1, check_and_fix_pattern1, content, flags=re.MULTILINE)
    
    # Pattern 2: Fix echo chains that create MCP markers
    # These need to be sent as separate commands
    pattern2 = r'echo\s+"TMUX_MCP_START";\s*echo\s+.*?;\s*echo\s+"TMUX_MCP_DONE_\$\?"'
    
    if re.search(pattern2, content):
        fixes_made.append("Found MCP marker echo chain - needs refactoring")
    
    # Pattern 3: Ensure send-keys with message variables include Enter
    pattern3 = r'(tmux\s+send-keys[^"]*?"\$\{?[A-Za-z_]+\}?")\s*(\n|;|$)'
    
    def check_and_fix_pattern3(match):
        command = match.group(1)
        separator = match.group(2)
        
        # Add Enter after the variable
        fixed = f'{command} Enter{separator}'
        fixes_made.append(f"Added Enter after variable in: {command}")
        return fixed
    
    # Only apply this fix if Enter is not on the next line
    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'tmux send-keys' in line and '"$' in line and 'Enter' not in line:
            # Check next line
            if i + 1 < len(lines) and 'Enter' in lines[i + 1]:
                # Enter is on next line, don't modify
                new_lines.append(line)
            else:
                # Need to add Enter
                if line.rstrip().endswith('"'):
                    line = line.rstrip() + ' Enter'
                    fixes_made.append(f"Added Enter to: {line.strip()}")
                new_lines.append(line)
        else:
            new_lines.append(line)
        i += 1
    
    content = '\n'.join(new_lines)
    
    if content != original_content:
        # Backup original
        backup_path = f"{filepath}.backup_enter_fix"
        if not os.path.exists(backup_path):
            shutil.copy2(filepath, backup_path)
        
        # Write fixed content
        with open(filepath, 'w') as f:
            f.write(content)
        
        return True, fixes_made
    
    return False, []

def main():
    """Fix tmux Enter issue in all relevant scripts."""
    
    orchestrator_path = Path('/home/clauderun/Tmux-Orchestrator')
    
    # Files to check and fix
    files_to_fix = [
        'send-claude-message.sh',
        'send-claude-message-hubspoke.sh',
        'send-claude-message-enhanced.sh',
        'schedule_with_note.sh',
        'compact-agent.sh',
        'monitor_agent_context.sh',
        'scheduler.py',
        'monitoring/monitored_send_message.sh'
    ]
    
    print("Fixing tmux Enter key issue in all scripts...")
    print("=" * 50)
    
    total_fixes = 0
    
    for file_rel in files_to_fix:
        filepath = orchestrator_path / file_rel
        if not filepath.exists():
            print(f"⚠️  File not found: {file_rel}")
            continue
        
        fixed, fixes = fix_tmux_send_keys_in_file(filepath)
        
        if fixed:
            print(f"✅ Fixed {file_rel}:")
            for fix in fixes:
                print(f"   - {fix}")
            total_fixes += len(fixes)
        else:
            print(f"✓ No fixes needed in {file_rel}")
    
    print("=" * 50)
    print(f"Total fixes applied: {total_fixes}")
    
    # Special check for MCP marker issue
    print("\n🔍 Checking for MCP marker patterns...")
    
    # Search for any file that might be creating the echo chain
    for root, dirs, files in os.walk(orchestrator_path):
        # Skip .git and other hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.endswith(('.py', '.sh')):
                filepath = Path(root) / file
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                    
                    # Look for suspicious patterns
                    if 'TMUX_MCP_START' in content or 'echo.*echo.*echo' in content:
                        print(f"⚠️  Found potential MCP pattern in: {filepath.relative_to(orchestrator_path)}")
                except:
                    pass
    
    print("\n✅ Fix script completed!")
    print("\nRecommendations:")
    print("1. Test monitored messaging with: ./send-monitored-message.sh test:0 'Test message'")
    print("2. Use ./send-direct-message.sh for critical messages that need immediate delivery")
    print("3. Consider refactoring any scripts that create echo chains with MCP markers")

if __name__ == "__main__":
    main()
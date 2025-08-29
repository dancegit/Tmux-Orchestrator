#!/usr/bin/env python3
"""
Test the completion detection logic with current session
"""

import subprocess
import sys
from pathlib import Path

def test_orchestrator_output_analysis():
    """Test analyzing orchestrator output for completion"""
    
    # Capture output from the mobile app session
    session_name = "orchestrator-mobile-app-impl-6b4fe3de"
    
    try:
        result = subprocess.run(
            ['tmux', 'capture-pane', '-t', f'{session_name}:0', '-p', '-S', '-100'],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print(f"Failed to capture session output: {result.stderr}")
            return
        
        output = result.stdout
        print("=== ORCHESTRATOR OUTPUT (last 100 lines) ===")
        print(output[-2000:])  # Show last 2000 chars
        print("\n=== END OUTPUT ===")
        
        # Test with claude -p
        prompt = f"""Based on the following orchestrator output, determine if the project is FULLY COMPLETE.

ORCHESTRATOR OUTPUT:
{output}

Answer with just "YES" if the project is completely done, or "NO" if there's still work to do.
Consider a project complete only if:
- All agents have reported completion
- No tasks are pending or in progress  
- The orchestrator has indicated all work is done

Answer (YES/NO):"""
        
        print("\n=== TESTING CLAUDE ANALYSIS ===")
        print("Asking Claude to analyze the output...")
        
        # Use claude -p for analysis
        claude_result = subprocess.run(
            ['claude', '-p', prompt],
            capture_output=True, text=True
        )
        
        if claude_result.returncode == 0:
            answer = claude_result.stdout.strip()
            print(f"Claude's response: {answer}")
            
            is_complete = "YES" in answer.upper()
            print(f"Completion detected: {is_complete}")
            
            if is_complete:
                print("\n🎉 Project appears complete! This would trigger completion marking.")
            else:
                print("\n⏳ Project is still in progress.")
                
        else:
            print(f"Claude analysis failed: {claude_result.stderr}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_orchestrator_output_analysis()
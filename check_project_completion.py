#!/usr/bin/env python3
"""
Simple project completion checker that asks the orchestrator agent
"""

import subprocess
import sys
import json
import time
from pathlib import Path
from typing import Optional, Tuple

def capture_orchestrator_output(session_name: str, lines: int = 100) -> Optional[str]:
    """Capture recent output from orchestrator window"""
    try:
        result = subprocess.run(
            ['tmux', 'capture-pane', '-t', f'{session_name}:0', '-p', '-S', f'-{lines}'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception as e:
        print(f"Error capturing orchestrator output: {e}")
        return None

def ask_claude_about_completion(output_text: str) -> Tuple[bool, str]:
    """Use claude -p to analyze if project is complete"""
    prompt = f"""You are analyzing orchestrator output to determine if a multi-agent software project is FULLY COMPLETE.

ORCHESTRATOR OUTPUT:
{output_text}

Analyze the output and answer with EXACTLY "YES" or "NO" based on these criteria:

✅ Answer "YES" if you see clear indicators like:
- "Project completed successfully" or similar completion statements
- "All tasks completed" or "100% complete"
- "Ready for decommission" or "marked for decommission"
- All agents have reported their work is done
- No pending tasks or active work mentioned

❌ Answer "NO" if you see:
- Active work in progress
- Pending tasks or "TODO" items
- Agents still working or "in progress" status
- Error messages or failures
- Incomplete implementations

IMPORTANT: Only answer "YES" if you are confident the project is completely finished.

Answer (YES/NO):"""
    
    try:
        # Use claude -p for quick analysis
        result = subprocess.run(
            ['claude', '-p', prompt],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            answer = result.stdout.strip().upper()
            is_complete = "YES" in answer
            return is_complete, answer
        return False, "Failed to get response"
        
    except Exception as e:
        print(f"Error asking Claude: {e}")
        return False, str(e)

def send_completion_command(session_name: str):
    """Send command to orchestrator to mark project as complete"""
    completion_command = f"""
Please run the following bash commands to mark this project as complete:

!/home/clauderun/Tmux-Orchestrator/report-completion.sh orchestrator "All tasks completed successfully - detected via automated completion system"

The '!' prefix will execute this directly in bash mode to properly record the completion.
"""
    
    try:
        # Send message to orchestrator
        send_script = Path(__file__).parent / 'send-claude-message.sh'
        if send_script.exists():
            subprocess.run([
                str(send_script), 
                f'{session_name}:0', 
                completion_command
            ])
            print(f"Sent completion command to orchestrator in {session_name}")
            return True
    except Exception as e:
        print(f"Error sending completion command: {e}")
    return False

def check_and_complete_project(project_id: int):
    """Main function to check and potentially complete a project"""
    # Get project details from database
    import sqlite3
    conn = sqlite3.connect('task_queue.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT session_name, spec_path, status 
        FROM project_queue 
        WHERE id = ?
    """, (project_id,))
    
    row = cursor.fetchone()
    if not row:
        print(f"Project {project_id} not found")
        return False
        
    session_name, spec_path, status = row
    
    if status != 'processing':
        print(f"Project {project_id} is not in processing state (current: {status})")
        return False
    
    # Capture orchestrator output
    output = capture_orchestrator_output(session_name)
    if not output:
        print(f"Could not capture output from {session_name}")
        return False
    
    # Ask Claude if project is complete
    is_complete, response = ask_claude_about_completion(output)
    
    print(f"Completion check for project {project_id}:")
    print(f"  Session: {session_name}")
    print(f"  Claude says: {response}")
    
    if is_complete:
        print("🎉 Project appears complete! Sending completion command to orchestrator...")
        
        # Send completion command
        if send_completion_command(session_name):
            print("📤 Completion command sent successfully. Waiting for orchestrator to process...")
            
            # Give orchestrator time to process
            for attempt in range(6):  # Wait up to 30 seconds
                time.sleep(5)
                
                cursor.execute("""
                    SELECT status FROM project_queue WHERE id = ?
                """, (project_id,))
                new_status = cursor.fetchone()
                
                if new_status and new_status[0] == 'completed':
                    print(f"✅ Project {project_id} successfully marked as complete!")
                    return True
                elif new_status and new_status[0] != 'processing':
                    print(f"⚠️  Project status changed to: {new_status[0]} (may have been overridden by scheduler)")
                    # Don't return False - this might be temporary due to phantom detection
                
                print(f"⏳ Waiting for status update... (attempt {attempt + 1}/6)")
            
            print(f"⚠️  Project completion may take longer to process. Check manually with: ./qs")
            return False
        else:
            print("❌ Failed to send completion command to orchestrator")
            return False
    else:
        print(f"📊 Project {project_id} analysis: Not yet complete.")
        print(f"   Claude response: {response}")
        return False
    
    conn.close()
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: check_project_completion.py <project_id>")
        print("   or: check_project_completion.py --all")
        sys.exit(1)
    
    if sys.argv[1] == "--all":
        # Check all processing projects
        import sqlite3
        conn = sqlite3.connect('task_queue.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM project_queue 
            WHERE status = 'processing'
        """)
        
        for row in cursor.fetchall():
            print(f"\nChecking project {row[0]}...")
            check_and_complete_project(row[0])
            time.sleep(2)  # Don't overwhelm claude
            
        conn.close()
    else:
        project_id = int(sys.argv[1])
        check_and_complete_project(project_id)
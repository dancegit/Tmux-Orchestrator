#!/usr/bin/env python3
"""
Orchestrator Claude Loop
This script manages the continuous Claude orchestrator by:
1. Checking if a Claude orchestrator is already running
2. If not, summoning a new Claude instance with instructions
3. If yes, checking if it's idle and needs a reminder
"""

import subprocess
import time
import json
import os
from datetime import datetime
from pathlib import Path

class OrchestratorClaudeLoop:
    def __init__(self):
        self.orchestrator_window = "tmux-orc:0"  # Main orchestrator Claude window
        self.instruction_file = Path("/Users/jasonedward/Coding/Tmux orchestrator/next_check_instruction.md")
        self.claude_spawned_flag = Path("/Users/jasonedward/Coding/Tmux orchestrator/registry/claude_active.flag")
        
    def is_claude_busy(self, session: str, window: int) -> bool:
        """Check if Claude is currently processing something"""
        try:
            # Capture last 200 chars of the window
            cmd = ["tmux", "capture-pane", "-t", f"{session}:{window}", "-p", "-S", "-200", "-E", "-1"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            content = result.stdout.lower()
            
            # Claude is busy if we see these indicators
            busy_indicators = [
                "thinking",
                "working", 
                "analyzing",
                "creating",
                "updating",
                "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"  # Spinner characters
            ]
            
            return any(indicator in content for indicator in busy_indicators)
            
        except Exception as e:
            print(f"Error checking Claude status: {e}")
            return True  # Assume busy if we can't check
    
    def is_claude_present(self, session: str, window: int) -> bool:
        """Check if Claude is running in the window"""
        try:
            cmd = ["tmux", "capture-pane", "-t", f"{session}:{window}", "-p"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            content = result.stdout.lower()
            
            # Look for Claude indicators
            claude_indicators = [
                "claude code",
                "claude>",
                "> ",
                "? for shortcuts"
            ]
            
            is_present = any(indicator in content for indicator in claude_indicators)
            
            # If Claude is present, remove the flag
            if is_present and self.claude_spawned_flag.exists():
                self.claude_spawned_flag.unlink()
            
            return is_present
            
        except Exception:
            return False
    
    def create_instruction_file(self):
        """Create instruction file for the next Claude instance"""
        instruction = f"""# Orchestrator Check-In - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

You are the Tmux Orchestrator. Your job is to:

1. **Check all active sessions** using:
   ```bash
   cd "/Users/jasonedward/Coding/Tmux orchestrator" && python3 claude_control.py status detailed
   ```

2. **Analyze agent status** and identify:
   - Which agents are idle and need new tasks
   - Which processes are still running (overnight loads, builds, etc)
   - Any errors or issues that need attention

3. **Assign new tasks** to idle agents based on project goals:
   - ai-chat: Continue auth implementation
   - glacier-backend: Continue cloud deployment research or data validation
   - tmux-orc: Improve orchestrator capabilities

4. **Monitor progress** by checking specific windows:
   ```bash
   python3 claude_control.py analyze <session> <window> <lines>
   ```

5. **Update registry** with current status:
   ```bash
   python3 claude_control.py update '<json_updates>'
   ```

6. **CRITICAL**: Before you finish, schedule the next check:
   ```bash
   sleep 600 && python3 /Users/jasonedward/Coding/Tmux\\ orchestrator/orchestrator_claude_loop.py
   ```

Remember:
- Never interact with server windows (npm dev, convex dev)
- Only assign meaningful tasks that move projects toward production
- Document all decisions in the registry
- Keep the loop going - always schedule the next check!
"""
        
        self.instruction_file.write_text(instruction)
    
    def summon_claude_orchestrator(self):
        """Summon a new Claude instance with orchestrator instructions"""
        # Check if we already spawned Claude recently
        if self.claude_spawned_flag.exists():
            flag_age = time.time() - self.claude_spawned_flag.stat().st_mtime
            if flag_age < 300:  # Less than 5 minutes old
                print(f"Claude was already spawned {int(flag_age)}s ago, skipping...")
                return
        
        print("Summoning new Claude orchestrator with --continue flag...")
        
        # Create flag file
        self.claude_spawned_flag.parent.mkdir(exist_ok=True)
        self.claude_spawned_flag.touch()
        
        # Create instruction file
        self.create_instruction_file()
        
        # Send commands to summon Claude WITH CONTINUE FLAG
        cmds = [
            # First, go to orchestrator directory
            ["tmux", "send-keys", "-t", self.orchestrator_window, "cd '/Users/jasonedward/Coding/Tmux orchestrator'", "C-m"],
            # Clear the screen
            ["tmux", "send-keys", "-t", self.orchestrator_window, "clear", "C-m"],
            # Summon Claude with --continue to maintain context
            ["tmux", "send-keys", "-t", self.orchestrator_window, "claude --continue", "C-m"]
        ]
        
        for cmd in cmds:
            subprocess.run(cmd, check=True)
            time.sleep(1)
        
        # Wait for Claude to start
        time.sleep(5)
        
        # Send the instruction
        instruction = f"cat {self.instruction_file} && rm {self.instruction_file}"
        subprocess.run(["tmux", "send-keys", "-t", self.orchestrator_window, instruction, "C-m"], check=True)
    
    def remind_claude(self):
        """Send a reminder to an existing Claude instance"""
        print("Sending reminder to existing Claude...")
        
        reminder = (
            "Time for orchestrator check-in! Please: "
            "1) Check all sessions with claude_control.py status, "
            "2) Analyze idle agents, "
            "3) Assign new tasks if needed, "
            "4) Schedule next check with: sleep 600 && python3 /Users/jasonedward/Coding/Tmux\\ orchestrator/orchestrator_claude_loop.py"
        )
        
        subprocess.run(["tmux", "send-keys", "-t", self.orchestrator_window, reminder, "C-m"], check=True)
    
    def run_check(self):
        """Main check logic"""
        print(f"\n{'='*60}")
        print(f"Orchestrator Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Check orchestrator window status
        session, window = self.orchestrator_window.split(':')
        
        if not self.is_claude_present(session, int(window)):
            print("No Claude instance found in orchestrator window")
            self.summon_claude_orchestrator()
        elif self.is_claude_busy(session, int(window)):
            print("Claude is currently busy - will check again later")
            # Schedule next check
            time.sleep(300)  # Wait 5 minutes
            self.run_check()  # Recursive check
        else:
            print("Claude is idle - sending reminder")
            self.remind_claude()
        
        # Log this check
        self.log_check()
    
    def log_check(self):
        """Log this check for tracking"""
        log_file = Path("/Users/jasonedward/Coding/Tmux orchestrator/registry/loop_checks.json")
        
        try:
            if log_file.exists():
                with open(log_file, 'r') as f:
                    log = json.load(f)
            else:
                log = {"checks": []}
        except:
            log = {"checks": []}
        
        log["checks"].append({
            "timestamp": datetime.now().isoformat(),
            "action": "check_complete"
        })
        
        # Keep only last 100 checks
        log["checks"] = log["checks"][-100:]
        
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, 'w') as f:
            json.dump(log, f, indent=2)

if __name__ == "__main__":
    loop = OrchestratorClaudeLoop()
    loop.run_check()
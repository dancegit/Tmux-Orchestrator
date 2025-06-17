#!/usr/bin/env python3
"""
Continuous Orchestrator Loop
This script keeps the orchestrator running continuously, checking on agents
and assigning new tasks even when the user is away.
"""

import time
import sys
import json
from datetime import datetime
from direct_orchestrator import DirectOrchestrator

class ContinuousOrchestrator:
    def __init__(self, check_interval=300):  # 5 minutes default
        self.orchestrator = DirectOrchestrator()
        self.check_interval = check_interval
        self.iteration = 0
        
    def run_continuous_loop(self):
        """Main continuous loop that keeps checking and managing agents"""
        print(f"Starting continuous orchestrator loop (interval: {self.check_interval}s)")
        
        while True:
            self.iteration += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"\n{'='*60}")
            print(f"Iteration {self.iteration} - {timestamp}")
            print(f"{'='*60}")
            
            try:
                # Get current status
                status = self.orchestrator.get_full_status(include_content=True, lines_per_window=100)
                
                # Analyze each session
                for session_name, session_data in status["sessions"].items():
                    print(f"\nChecking session: {session_name}")
                    self._analyze_and_manage_session(session_name, session_data)
                
                # Log iteration complete
                self._log_iteration_summary()
                
            except Exception as e:
                print(f"Error in iteration {self.iteration}: {e}")
            
            # Wait for next check
            print(f"\nNext check in {self.check_interval} seconds...")
            time.sleep(self.check_interval)
    
    def _analyze_and_manage_session(self, session_name: str, session_data: dict):
        """Analyze a session and determine if agents need new tasks"""
        
        # Skip server windows (convex, npm run dev, etc)
        server_keywords = ['convex dev', 'npm run', 'yarn dev', 'next dev']
        
        for window_idx, window_data in session_data["windows"].items():
            window_name = window_data.get("name", "")
            content = window_data.get("content", "")
            
            # Check if it's a server window
            is_server = any(keyword in content.lower() for keyword in server_keywords)
            if is_server:
                print(f"  Window {window_idx} ({window_name}): Server running, skipping")
                continue
            
            # Check if it's a Claude agent window
            if "claude" in window_name.lower() or ">" in content[-100:]:
                self._check_agent_status(session_name, int(window_idx), window_data)
    
    def _check_agent_status(self, session_name: str, window_idx: int, window_data: dict):
        """Check if an agent needs attention or new tasks"""
        content = window_data.get("content", "")
        
        # Look for signs the agent is idle
        idle_indicators = [
            "What would you like",
            "Is there anything else",
            "Task completed",
            "Waiting for",
            "> "  # Claude prompt
        ]
        
        is_idle = any(indicator in content[-200:] for indicator in idle_indicators)
        
        if is_idle:
            print(f"  Window {window_idx}: Agent appears idle")
            # Log this for the next Claude session to handle
            self._log_idle_agent(session_name, window_idx)
        else:
            print(f"  Window {window_idx}: Agent appears busy")
    
    def _log_idle_agent(self, session_name: str, window_idx: int):
        """Log idle agents for next Claude session to assign tasks"""
        log_file = "/Users/jasonedward/Coding/Tmux orchestrator/registry/idle_agents.json"
        
        try:
            with open(log_file, 'r') as f:
                idle_agents = json.load(f)
        except:
            idle_agents = {"agents": [], "last_updated": ""}
        
        idle_agents["agents"].append({
            "session": session_name,
            "window": window_idx,
            "timestamp": datetime.now().isoformat(),
            "iteration": self.iteration
        })
        idle_agents["last_updated"] = datetime.now().isoformat()
        
        with open(log_file, 'w') as f:
            json.dump(idle_agents, f, indent=2)
    
    def _log_iteration_summary(self):
        """Log summary of this iteration"""
        summary_file = "/Users/jasonedward/Coding/Tmux orchestrator/registry/orchestrator_log.json"
        
        try:
            with open(summary_file, 'r') as f:
                log = json.load(f)
        except:
            log = {"iterations": []}
        
        log["iterations"].append({
            "iteration": self.iteration,
            "timestamp": datetime.now().isoformat(),
            "sessions_checked": list(self.orchestrator.get_full_status()["sessions"].keys())
        })
        
        # Keep only last 100 iterations
        log["iterations"] = log["iterations"][-100:]
        
        with open(summary_file, 'w') as f:
            json.dump(log, f, indent=2)

if __name__ == "__main__":
    # Check interval from command line or default to 5 minutes
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    
    orchestrator = ContinuousOrchestrator(check_interval=interval)
    orchestrator.run_continuous_loop()
#!/usr/bin/env python3

import time
import threading
import signal
import sys
from typing import Optional, Dict
from datetime import datetime, timedelta
from tmux_utils import TmuxOrchestrator
from claude_agent import ClaudeAgent

class TmuxMonitoringOrchestrator:
    def __init__(self, monitoring_interval: int = 60):
        self.tmux = TmuxOrchestrator()
        self.claude = ClaudeAgent(self.tmux)
        self.monitoring_interval = monitoring_interval
        self.running = False
        self.last_snapshot = None
        self.last_analysis = None
        self.monitoring_thread = None
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        self.stop_monitoring()
        sys.exit(0)
    
    def start_monitoring(self):
        """Start the continuous monitoring loop"""
        if self.running:
            print("Monitoring is already running")
            return
        
        self.running = True
        print(f"Starting tmux monitoring (interval: {self.monitoring_interval}s)")
        print("Press Ctrl+C to stop monitoring")
        
        # Start monitoring in a separate thread
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        # Run the command interface in the main thread
        self._command_interface()
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        print("Monitoring stopped")
    
    def _monitoring_loop(self):
        """The main monitoring loop that runs in a separate thread"""
        while self.running:
            try:
                # Get current analysis
                analysis_result = self.claude.continuous_monitoring_analysis(self.last_snapshot)
                
                # Store results
                self.last_snapshot = analysis_result['snapshot']
                self.last_analysis = analysis_result
                
                # Print update
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{timestamp}] Monitoring update:")
                print(f"Sessions active: {len(self.tmux.get_tmux_sessions())}")
                
                # If there's significant new activity, show brief analysis
                if analysis_result.get('has_previous') and 'activity' in analysis_result['analysis'].lower():
                    print(f"New activity detected - check with 'status' command")
                
                # Wait for next interval
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(self.monitoring_interval)
    
    def _command_interface(self):
        """Interactive command interface"""
        print("\n" + "="*50)
        print("Tmux Orchestrator Command Interface")
        print("="*50)
        print("Commands:")
        print("  status        - Get current status of all windows")
        print("  analyze       - Get detailed Claude analysis")
        print("  window <s>:<w> - Analyze specific window")
        print("  send <s>:<w> <cmd> - Send command to window (with confirmation)")
        print("  find <name>   - Find windows by name")
        print("  interval <n>  - Change monitoring interval")
        print("  help          - Show this help")
        print("  quit          - Exit orchestrator")
        print()
        
        while self.running:
            try:
                user_input = input("tmux> ").strip()
                if not user_input:
                    continue
                
                self._handle_command(user_input)
                
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def _handle_command(self, command: str):
        """Handle user commands"""
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == "quit" or cmd == "exit":
            self.stop_monitoring()
            return
        
        elif cmd == "status":
            self._show_status()
        
        elif cmd == "analyze":
            self._show_analysis()
        
        elif cmd == "window" and len(parts) > 1:
            self._analyze_window(parts[1])
        
        elif cmd == "send" and len(parts) > 2:
            self._send_command_to_window(parts[1], " ".join(parts[2:]))
        
        elif cmd == "find" and len(parts) > 1:
            self._find_windows(" ".join(parts[1:]))
        
        elif cmd == "interval" and len(parts) > 1:
            self._change_interval(parts[1])
        
        elif cmd == "help":
            self._show_help()
        
        else:
            print(f"Unknown command: {command}")
            print("Type 'help' for available commands")
    
    def _show_status(self):
        """Show current status of all sessions and windows"""
        sessions = self.tmux.get_tmux_sessions()
        
        print(f"\nTmux Status - {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 40)
        
        for session in sessions:
            status = "ATTACHED" if session.attached else "DETACHED"
            print(f"Session: {session.name} ({status})")
            
            for window in session.windows:
                active_marker = " ●" if window.active else ""
                print(f"  {window.window_index}: {window.window_name}{active_marker}")
        
        print(f"\nTotal: {len(sessions)} sessions, {sum(len(s.windows) for s in sessions)} windows")
    
    def _show_analysis(self):
        """Show detailed Claude analysis"""
        if self.last_analysis:
            print(f"\nClaude Analysis - {datetime.fromtimestamp(self.last_analysis['timestamp']).strftime('%H:%M:%S')}")
            print("-" * 40)
            print(self.last_analysis['analysis'])
        else:
            print("No analysis available yet. Please wait for monitoring cycle.")
    
    def _analyze_window(self, window_spec: str):
        """Analyze a specific window"""
        try:
            if ':' not in window_spec:
                print("Invalid window format. Use session:window (e.g., main:0)")
                return
            
            session_name, window_index = window_spec.split(':', 1)
            window_index = int(window_index)
            
            print(f"\nAnalyzing window {session_name}:{window_index}...")
            analysis = self.claude.get_window_specific_analysis(session_name, window_index)
            print("-" * 40)
            print(analysis)
            
        except ValueError:
            print("Invalid window index. Must be a number.")
        except Exception as e:
            print(f"Error analyzing window: {e}")
    
    def _send_command_to_window(self, window_spec: str, command: str):
        """Send a command to a specific window"""
        try:
            if ':' not in window_spec:
                print("Invalid window format. Use session:window (e.g., main:0)")
                return
            
            session_name, window_index = window_spec.split(':', 1)
            window_index = int(window_index)
            
            # Get Claude's safety analysis first
            suggestion = self.claude.suggest_command_for_window(session_name, window_index, f"Execute: {command}")
            
            print(f"\nClaude Safety Analysis:")
            print(f"Command: {command}")
            print(f"Safety Level: {suggestion['safety_level']}")
            print(f"Reasoning: {suggestion['reasoning']}")
            
            if suggestion['safety_level'] == 'unsafe':
                print(f"Alternative: {suggestion.get('alternative', 'None')}")
                print("Command blocked for safety reasons.")
                return
            
            # Proceed with confirmation
            success = self.tmux.send_command_to_window(session_name, window_index, command, confirm=True)
            if success:
                print(f"Command sent to {window_spec}")
            else:
                print("Command cancelled or failed")
                
        except ValueError:
            print("Invalid window index. Must be a number.")
        except Exception as e:
            print(f"Error sending command: {e}")
    
    def _find_windows(self, search_term: str):
        """Find windows by name"""
        matches = self.tmux.find_window_by_name(search_term)
        
        if matches:
            print(f"\nFound {len(matches)} windows matching '{search_term}':")
            for session_name, window_index in matches:
                window_info = self.tmux.get_window_info(session_name, window_index)
                print(f"  {session_name}:{window_index} - {window_info.get('name', 'unknown')}")
        else:
            print(f"No windows found matching '{search_term}'")
    
    def _change_interval(self, interval_str: str):
        """Change monitoring interval"""
        try:
            new_interval = int(interval_str)
            if new_interval < 10:
                print("Minimum interval is 10 seconds")
                return
            
            self.monitoring_interval = new_interval
            print(f"Monitoring interval changed to {new_interval} seconds")
        except ValueError:
            print("Invalid interval. Must be a number of seconds.")
    
    def _show_help(self):
        """Show help information"""
        print("\nAvailable Commands:")
        print("  status                    - Show all sessions and windows")
        print("  analyze                   - Show latest Claude analysis")
        print("  window <session>:<index>  - Analyze specific window")
        print("  send <session>:<index> <command> - Send command to window")
        print("  find <name>               - Find windows by name")
        print("  interval <seconds>        - Change monitoring interval")
        print("  help                      - Show this help")
        print("  quit                      - Exit orchestrator")
        print("\nExamples:")
        print("  window main:0")
        print("  send dev:1 'git status'")
        print("  find server")
        print("  interval 30")

def main():
    """Main entry point"""
    print("Tmux Orchestrator v1.0")
    print("Initializing...")
    
    # Check if we're in tmux
    import os
    if 'TMUX' not in os.environ:
        print("Warning: Not running inside tmux. Some features may not work correctly.")
    
    # Create and start orchestrator
    orchestrator = TmuxMonitoringOrchestrator(monitoring_interval=60)
    
    try:
        orchestrator.start_monitoring()
    except KeyboardInterrupt:
        print("\nShutdown requested")
    finally:
        orchestrator.stop_monitoring()
        print("Goodbye!")

if __name__ == "__main__":
    main()
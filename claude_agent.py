#!/usr/bin/env python3

import subprocess
import tempfile
import os
import json
import time
from typing import Dict, List, Optional
from tmux_utils import TmuxOrchestrator

class ClaudeAgent:
    def __init__(self, tmux_orchestrator: TmuxOrchestrator):
        self.tmux = tmux_orchestrator
        self.claude_available = self._check_claude_availability()
        
    def _check_claude_availability(self) -> bool:
        """Check if Claude CLI is available"""
        try:
            result = subprocess.run(["claude", "--version"], capture_output=True, text=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Warning: Claude CLI not found. Agent features will be limited.")
            return False
    
    def analyze_tmux_snapshot(self, snapshot: str, user_query: Optional[str] = None) -> str:
        """Send tmux snapshot to Claude for analysis"""
        if not self.claude_available:
            return "Claude CLI not available for analysis"
        
        prompt = self._build_analysis_prompt(snapshot, user_query)
        
        try:
            # Create temporary file for the prompt
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                temp_file = f.name
            
            # Run Claude CLI
            cmd = ["claude", "--file", temp_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            # Clean up
            os.unlink(temp_file)
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"Claude analysis failed: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return "Claude analysis timed out"
        except Exception as e:
            return f"Error running Claude analysis: {e}"
    
    def _build_analysis_prompt(self, snapshot: str, user_query: Optional[str]) -> str:
        """Build the prompt for Claude analysis"""
        base_prompt = """You are a tmux session monitoring assistant. Your job is to analyze the current state of tmux sessions and provide helpful insights.

Key responsibilities:
1. Summarize what's happening in each window
2. Identify any errors, warnings, or issues
3. Suggest actions if needed
4. Be concise but informative
5. Focus on actionable insights

SAFETY RULES:
- NEVER suggest destructive commands
- NEVER recommend closing windows or sessions
- NEVER suggest commands that could lose data
- Always prioritize safety over convenience

Current tmux state:
"""
        
        prompt = base_prompt + snapshot + "\n\n"
        
        if user_query:
            prompt += f"User's specific question: {user_query}\n\n"
        
        prompt += """Please provide:
1. Brief overview of what's active
2. Any issues or concerns you notice
3. Suggested next steps (if any)
4. Answer to user's question (if provided)

Keep your response concise and focused."""
        
        return prompt
    
    def get_window_specific_analysis(self, session_name: str, window_index: int, user_query: str = "") -> str:
        """Get Claude's analysis of a specific window"""
        window_info = self.tmux.get_window_info(session_name, window_index)
        
        if 'error' in window_info:
            return window_info['error']
        
        prompt = f"""Analyze this tmux window content and provide insights:

Session: {session_name}
Window: {window_index} ({window_info.get('name', 'unknown')})

Content:
{window_info.get('content', 'No content available')}

User question: {user_query}

Provide analysis of what's happening and suggest actions if needed. Be concise and safety-focused."""
        
        if not self.claude_available:
            return f"Claude not available. Window shows: {window_info.get('name', 'unknown')}"
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                temp_file = f.name
            
            cmd = ["claude", "--file", temp_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            os.unlink(temp_file)
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"Analysis failed: {result.stderr}"
                
        except Exception as e:
            return f"Error analyzing window: {e}"
    
    def suggest_command_for_window(self, session_name: str, window_index: int, goal: str) -> Dict[str, str]:
        """Get Claude's suggestion for a command to achieve a goal in a specific window"""
        window_info = self.tmux.get_window_info(session_name, window_index)
        
        prompt = f"""Given this tmux window state, suggest a safe command to achieve the user's goal:

Session: {session_name}
Window: {window_index} ({window_info.get('name', 'unknown')})

Current content:
{window_info.get('content', 'No content available')}

User's goal: {goal}

CRITICAL SAFETY REQUIREMENTS:
- Only suggest safe, non-destructive commands
- Do not suggest commands that could delete files or kill processes
- Prefer read-only or status commands when possible
- If the goal requires destructive actions, suggest safer alternatives

Respond with JSON in this format:
{
    "command": "suggested command (or 'UNSAFE' if goal requires destructive action)",
    "reasoning": "explanation of the command and why it's safe",
    "safety_level": "safe|caution|unsafe",
    "alternative": "safer alternative if command is risky"
}"""
        
        if not self.claude_available:
            return {
                "command": "UNAVAILABLE",
                "reasoning": "Claude CLI not available",
                "safety_level": "unknown",
                "alternative": "Use manual tmux commands"
            }
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                temp_file = f.name
            
            cmd = ["claude", "--file", temp_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            os.unlink(temp_file)
            
            if result.returncode == 0:
                try:
                    return json.loads(result.stdout.strip())
                except json.JSONDecodeError:
                    return {
                        "command": "PARSE_ERROR",
                        "reasoning": result.stdout.strip(),
                        "safety_level": "unknown",
                        "alternative": "Review response manually"
                    }
            else:
                return {
                    "command": "ERROR",
                    "reasoning": f"Claude error: {result.stderr}",
                    "safety_level": "unknown",
                    "alternative": "Use manual approach"
                }
                
        except Exception as e:
            return {
                "command": "EXCEPTION",
                "reasoning": f"Error: {e}",
                "safety_level": "unknown",
                "alternative": "Use manual approach"
            }
    
    def continuous_monitoring_analysis(self, previous_snapshot: Optional[str] = None) -> Dict:
        """Perform continuous monitoring analysis, comparing with previous state if available"""
        current_snapshot = self.tmux.create_monitoring_snapshot()
        
        if previous_snapshot:
            prompt = f"""Compare these two tmux snapshots and identify changes:

PREVIOUS STATE:
{previous_snapshot}

CURRENT STATE:
{current_snapshot}

Identify:
1. New activity in any windows
2. Processes that finished/started
3. Errors or issues that appeared
4. Any concerning changes

Be concise and focus on actionable insights."""
        else:
            prompt = f"""Analyze this tmux monitoring snapshot:

{current_snapshot}

Provide a brief overview of current activity and any issues requiring attention."""
        
        analysis = self.analyze_tmux_snapshot(current_snapshot, None)
        
        return {
            "timestamp": time.time(),
            "snapshot": current_snapshot,
            "analysis": analysis,
            "has_previous": previous_snapshot is not None
        }
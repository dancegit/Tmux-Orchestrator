#!/usr/bin/env python3
"""
Enhanced Project Health Monitor with Claude AI Integration
Uses Claude with /dwg for intelligent problem analysis and automatic fixes
"""

import sqlite3
import subprocess
import json
import logging
import sys
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import tempfile

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('project_health_monitor_claude.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ClaudeProjectHealthMonitor:
    def __init__(self):
        self.db_path = Path('task_queue.db')
        self.orchestrator_path = Path(__file__).parent
        self.claude_md_path = self.orchestrator_path / 'CLAUDE.md'
        self.readme_path = self.orchestrator_path / 'README.md'
        
    def get_failed_projects(self) -> List[Dict]:
        """Get all failed projects from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, session_name, status, error_message, spec_path, completed_at
            FROM project_queue 
            WHERE status = 'failed'
            ORDER BY id DESC
        ''')
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        conn.close()
        return results
    
    def get_processing_projects(self) -> List[Dict]:
        """Get all processing projects to check for false positives"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, session_name, status, started_at, spec_path
            FROM project_queue 
            WHERE status = 'processing'
            ORDER BY id DESC
        ''')
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        conn.close()
        return results
    
    def analyze_with_claude(self, problem_description: str, project_info: Dict) -> str:
        """Use Claude to analyze the problem and generate fixes"""
        
        # Create a comprehensive prompt for Claude
        prompt = f"""You are the Tmux Orchestrator health monitor. A project has failed and needs analysis and fixing.

PROJECT FAILURE DETAILS:
========================
Project ID: {project_info['id']}
Session Name: {project_info.get('session_name', 'None')}
Error Message: {project_info.get('error_message', 'Unknown error')}
Spec Path: {project_info.get('spec_path', 'Unknown')}
Status: {project_info.get('status', 'failed')}

PROBLEM DESCRIPTION:
{problem_description}

CONTEXT:
- This is part of the Tmux Orchestrator system for managing AI agents
- Projects are orchestrated using auto_orchestrate.py
- Common issues include: missing dependencies, tmux session failures, stuck agents, false positive failures
- The completion detector sometimes marks active projects as failed

YOUR TASKS:
1. First, read the README.md to understand the system
2. Read CLAUDE.md for project-specific rules
3. Run /dwg to discuss the problem and find root causes
4. Check if the tmux session exists: tmux list-sessions | grep "{project_info.get('session_name', '')}"
5. Check the database for project status
6. Determine if this is a false positive or real failure
7. Apply the appropriate fix:
   - If session missing and real failure: Reset the project using: python3 queue_status.py --reset {project_info['id']}
   - If false positive: Update status to processing
   - If stuck agents: Attempt recovery or reset
   - If missing dependencies: Restore from .trash or install
8. Document what you did and why

Start by analyzing the situation and then take action to fix it."""
        
        # Write prompt to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name
        
        try:
            # Execute Claude with the prompt
            logger.info(f"Invoking Claude to analyze project {project_info['id']} failure...")
            
            result = subprocess.run(
                ['claude', '-p', '--dangerously-skip-permissions'],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Claude analysis complete for project {project_info['id']}")
                return result.stdout
            else:
                logger.error(f"Claude analysis failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Claude analysis timed out after 2 minutes")
            return None
        except Exception as e:
            logger.error(f"Error invoking Claude: {e}")
            return None
        finally:
            # Clean up temp file
            if os.path.exists(prompt_file):
                os.remove(prompt_file)
    
    def check_tmux_session_exists(self, session_name: str) -> bool:
        """Check if a tmux session exists"""
        if not session_name:
            return False
            
        try:
            result = subprocess.run(
                ['tmux', 'has-session', '-t', session_name],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def monitor_cycle(self):
        """Main monitoring cycle with Claude integration"""
        logger.info("=" * 60)
        logger.info("Starting Claude-enhanced health monitoring cycle")
        
        # Check failed projects
        failed = self.get_failed_projects()
        logger.info(f"Found {len(failed)} failed projects")
        
        for project in failed:
            logger.info(f"\nAnalyzing failed project {project['id']}: {project.get('session_name', 'no session')}")
            
            # Build problem description
            session_exists = self.check_tmux_session_exists(project.get('session_name', ''))
            
            problem_desc = f"""
Project {project['id']} has failed with the following details:
- Session exists: {session_exists}
- Error type: {project.get('error_message', 'Unknown')}
- Time failed: {project.get('completed_at', 'Unknown')}

Analysis needed:
1. Is this a real failure or false positive?
2. If real, what's the root cause?
3. What's the best recovery strategy?
"""
            
            # Use Claude to analyze and fix
            claude_response = self.analyze_with_claude(problem_desc, project)
            
            if claude_response:
                logger.info(f"Claude has analyzed and attempted to fix project {project['id']}")
                # Log Claude's response for audit
                with open(f'claude_fix_{project["id"]}.log', 'w') as f:
                    f.write(claude_response)
            else:
                logger.warning(f"Claude analysis failed for project {project['id']}, using fallback")
                # Fallback to simple reset
                self.fallback_reset(project['id'])
        
        # Check for false positives in processing projects
        processing = self.get_processing_projects()
        long_running = []
        
        for project in processing:
            if project.get('started_at'):
                started = datetime.fromtimestamp(project['started_at'])
                if datetime.now() - started > timedelta(hours=4):
                    long_running.append(project)
        
        if long_running:
            logger.info(f"\nFound {len(long_running)} long-running projects (>4 hours)")
            
            for project in long_running:
                session_exists = self.check_tmux_session_exists(project.get('session_name', ''))
                
                if not session_exists:
                    logger.warning(f"Project {project['id']} running >4 hours but no session")
                    
                    problem_desc = f"""
Project {project['id']} has been processing for over 4 hours but the tmux session doesn't exist.
This is likely a stuck project that needs to be marked as failed or reset.
Session name: {project.get('session_name', 'None')}
Started at: {datetime.fromtimestamp(project['started_at']).isoformat()}
"""
                    
                    # Ask Claude to handle it
                    claude_response = self.analyze_with_claude(problem_desc, project)
                    
                    if claude_response:
                        logger.info(f"Claude handled long-running project {project['id']}")
        
        logger.info("\nClaude-enhanced monitoring cycle complete")
        logger.info("=" * 60)
    
    def fallback_reset(self, project_id: int):
        """Simple fallback reset if Claude fails"""
        try:
            logger.info(f"Fallback: Resetting project {project_id}...")
            result = subprocess.run(
                ['python3', 'queue_status.py', '--reset', str(project_id)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully reset project {project_id}")
            else:
                logger.error(f"Failed to reset project {project_id}: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error resetting project {project_id}: {e}")
    
    def run_continuous(self, interval_minutes: int = 30):
        """Run continuous monitoring with Claude"""
        logger.info(f"Starting Claude-enhanced continuous monitoring (interval: {interval_minutes} minutes)")
        
        while True:
            try:
                self.monitor_cycle()
                
                # Wait for next cycle
                logger.info(f"Waiting {interval_minutes} minutes until next check...")
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                logger.info("Waiting 5 minutes before retry...")
                time.sleep(300)

def main():
    monitor = ClaudeProjectHealthMonitor()
    
    if '--once' in sys.argv:
        # Run once for testing
        monitor.monitor_cycle()
    else:
        # Run continuously
        monitor.run_continuous(interval_minutes=30)

if __name__ == '__main__':
    main()
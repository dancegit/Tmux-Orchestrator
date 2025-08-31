#!/usr/bin/env python3
"""
Agent Health Monitoring System
Detects stuck agents and provides auto-recovery capabilities
"""

import subprocess
import time
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import psutil
import sqlite3

logger = logging.getLogger(__name__)

class AgentHealthMonitor:
    """Comprehensive health monitoring for tmux agents"""
    
    def __init__(self):
        self.health_check_interval = 300  # 5 minutes
        self.stuck_threshold = 1800       # 30 minutes
        self.recovery_timeout = 30        # 30 seconds for recovery attempts
        
    def check_agent_health(self, session_name: str) -> Dict[str, Any]:
        """Comprehensive health check for all agents in session"""
        health_status = {}
        
        try:
            # Get all windows in session
            windows = self._get_session_windows(session_name)
            
            for window_idx, window_name in windows:
                try:
                    # Check pane command
                    pane_cmd = self._get_pane_command(f"{session_name}:{window_idx}")
                    
                    # Check for Claude process
                    has_claude = self._check_claude_process(session_name, window_idx)
                    
                    # Check last activity
                    last_activity = self._get_last_activity(session_name, window_idx)
                    
                    # Calculate if stuck
                    is_stuck = pane_cmd == 'bash' and not has_claude
                    stuck_duration = self._calculate_stuck_duration(session_name, window_idx) if is_stuck else 0
                    
                    health_status[window_name] = {
                        'window_index': window_idx,
                        'pane_command': pane_cmd,
                        'has_claude': has_claude,
                        'last_activity': last_activity,
                        'is_stuck': is_stuck,
                        'stuck_duration': stuck_duration,
                        'needs_recovery': is_stuck and stuck_duration > self.stuck_threshold
                    }
                    
                except Exception as e:
                    logger.warning(f"Failed to check health for window {window_idx} ({window_name}): {e}")
                    health_status[window_name] = {
                        'window_index': window_idx,
                        'error': str(e),
                        'is_stuck': False,
                        'needs_recovery': False
                    }
            
        except Exception as e:
            logger.error(f"Failed to check session health for {session_name}: {e}")
            
        return health_status
    
    def _get_session_windows(self, session_name: str) -> List[tuple]:
        """Get all windows in a session"""
        try:
            result = subprocess.run([
                'tmux', 'list-windows', '-t', session_name, '-F', '#{window_index}:#{window_name}'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                windows = []
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        idx, name = line.split(':', 1)
                        windows.append((int(idx), name))
                return windows
            else:
                logger.warning(f"Failed to list windows for session {session_name}: {result.stderr}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting session windows for {session_name}: {e}")
            return []
    
    def _get_pane_command(self, target: str) -> str:
        """Get the current command running in a pane"""
        try:
            result = subprocess.run([
                'tmux', 'display-message', '-t', target, '-p', '#{pane_current_command}'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return "unknown"
                
        except Exception as e:
            logger.debug(f"Failed to get pane command for {target}: {e}")
            return "unknown"
    
    def _check_claude_process(self, session_name: str, window_idx: int) -> bool:
        """Check if Claude is running in the window"""
        try:
            # Get tmux server PID for this session
            result = subprocess.run([
                'tmux', 'display-message', '-t', f"{session_name}:{window_idx}", '-p', '#{client_pid}'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                return False
                
            # Look for Claude processes in the session
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] in ['claude', 'node'] and proc.info['cmdline']:
                        cmdline = ' '.join(proc.info['cmdline'])
                        if 'claude' in cmdline.lower() or 'claude-code' in cmdline.lower():
                            # Check if process is associated with this session
                            parent = proc.parent()
                            if parent and session_name in str(parent.cmdline()):
                                return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            logger.debug(f"Error checking Claude process for {session_name}:{window_idx}: {e}")
            
        return False
    
    def _get_last_activity(self, session_name: str, window_idx: int) -> int:
        """Get timestamp of last activity in the window"""
        try:
            result = subprocess.run([
                'tmux', 'display-message', '-t', f"{session_name}:{window_idx}", '-p', '#{window_activity}'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                return int(result.stdout.strip())
            else:
                return int(time.time())  # Default to now if can't determine
                
        except Exception as e:
            logger.debug(f"Failed to get last activity for {session_name}:{window_idx}: {e}")
            return int(time.time())
    
    def _calculate_stuck_duration(self, session_name: str, window_idx: int) -> int:
        """Calculate how long an agent has been stuck"""
        last_activity = self._get_last_activity(session_name, window_idx)
        current_time = int(time.time())
        return max(0, current_time - last_activity)
    
    def auto_recover_stuck_agent(self, session_name: str, window_idx: int) -> bool:
        """Attempt to recover a stuck agent"""
        logger.info(f"Attempting to recover stuck agent in {session_name}:{window_idx}")
        
        # First verify Claude authentication is still valid
        if not self._verify_claude_authentication():
            logger.error(f"Cannot recover agent {session_name}:{window_idx} - Claude authentication incomplete")
            return False
        
        try:
            # Try sending claude command with permissions skip
            subprocess.run([
                'tmux', 'send-keys', '-t', f"{session_name}:{window_idx}",
                'claude --dangerously-skip-permissions', 'Enter'
            ], timeout=self.recovery_timeout)
            
            time.sleep(5)
            
            # Check if recovery was successful
            if self._check_claude_process(session_name, window_idx):
                logger.info(f"Successfully recovered stuck agent in {session_name}:{window_idx}")
                
                # Re-brief the agent with context and role-specific instructions
                if self._send_recovery_briefing(session_name, window_idx):
                    logger.info(f"Re-briefing completed for recovered agent {session_name}:{window_idx}")
                    return True
                else:
                    logger.warning(f"Recovery successful but re-briefing failed for {session_name}:{window_idx}")
                    return True  # Still consider recovery successful
            else:
                logger.warning(f"Failed to recover stuck agent in {session_name}:{window_idx} - manual intervention required")
                return False
                
        except Exception as e:
            logger.error(f"Exception during recovery attempt for {session_name}:{window_idx}: {e}")
            return False
    
    def _verify_claude_authentication(self) -> bool:
        """Verify Claude authentication status"""
        try:
            result = subprocess.run([
                'claude', 'config', 'ls'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                logger.error("Claude config command failed")
                return False
                
            try:
                config = json.loads(result.stdout)
                has_trust = config.get('hasTrustDialogAccepted', False)
                has_onboarding = config.get('hasCompletedProjectOnboarding', False)
                
                if not has_trust or not has_onboarding:
                    logger.error("Claude authentication incomplete - missing required flags")
                    return False
                    
                return True
                
            except json.JSONDecodeError:
                logger.error("Failed to parse Claude config output")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Claude config command timed out")
            return False
        except FileNotFoundError:
            logger.error("Claude command not found")
            return False
        except Exception as e:
            logger.error(f"Authentication verification failed: {e}")
            return False
    
    def _send_recovery_briefing(self, session_name: str, window_idx: int) -> bool:
        """Send agent-specific recovery briefing after Claude restart"""
        try:
            # Determine agent role from window name or session state
            agent_role = self._get_agent_role(session_name, window_idx)
            if not agent_role:
                logger.warning(f"Could not determine agent role for {session_name}:{window_idx}")
                return False
            
            # Get project context
            project_context = self._get_project_context(session_name)
            
            # Create role-specific recovery briefing
            briefing = self._create_recovery_briefing(agent_role, session_name, project_context)
            
            # Send briefing to agent
            subprocess.run([
                'tmux', 'send-keys', '-t', f"{session_name}:{window_idx}",
                briefing, 'Enter'
            ], timeout=30)
            
            # Wait for briefing to be processed
            time.sleep(3)
            
            # Send follow-up context restoration command
            context_cmd = f"Please check your current working directory and recent work. You were recovered from a stuck state at {time.strftime('%Y-%m-%d %H:%M:%S')}. Continue from where you left off."
            subprocess.run([
                'tmux', 'send-keys', '-t', f"{session_name}:{window_idx}",
                context_cmd, 'Enter'
            ], timeout=30)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send recovery briefing to {session_name}:{window_idx}: {e}")
            return False
    
    def _get_agent_role(self, session_name: str, window_idx: int) -> str:
        """Determine agent role from tmux window name or session state"""
        try:
            # Try to get window name from tmux
            result = subprocess.run([
                'tmux', 'display-message', '-t', f"{session_name}:{window_idx}",
                '-p', '#{window_name}'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                window_name = result.stdout.strip().lower()
                role_mapping = {
                    'orchestrator': 'orchestrator',
                    'project-manager': 'project_manager', 
                    'developer': 'developer',
                    'tester': 'tester',
                    'testrunner': 'testrunner',
                    'sysadmin': 'sysadmin',
                    'devops': 'devops',
                    'securityops': 'securityops',
                    'networkops': 'networkops',
                    'monitoringops': 'monitoringops',
                    'databaseops': 'databaseops'
                }
                return role_mapping.get(window_name, 'unknown')
                
        except Exception as e:
            logger.warning(f"Could not get window name for {session_name}:{window_idx}: {e}")
            
        return 'unknown'
    
    def _get_project_context(self, session_name: str) -> dict:
        """Get project context from session state or registry"""
        context = {
            'session_name': session_name,
            'recovery_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'spec_path': None,
            'project_path': None
        }
        
        try:
            # Try to load from session state manager
            project_base = session_name.split('-impl-')[0] if '-impl-' in session_name else session_name
            
            # Look for spec in registry
            registry_path = Path(f'registry/projects/{project_base}')
            if registry_path.exists():
                metadata_file = registry_path / 'orchestration_metadata.json'
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        context.update({
                            'spec_path': metadata.get('spec_path'),
                            'project_path': metadata.get('project_path'),
                            'roles': metadata.get('roles', [])
                        })
                        
        except Exception as e:
            logger.warning(f"Could not load project context for {session_name}: {e}")
            
        return context
    
    def _create_recovery_briefing(self, agent_role: str, session_name: str, context: dict) -> str:
        """Create role-specific recovery briefing message"""
        
        base_briefing = f"""
RECOVERY BRIEFING - Agent Restarted at {context['recovery_time']}

You are the {agent_role.upper()} for session: {session_name}
You were automatically recovered from a stuck state.

IMPORTANT: 
- Check your working directory with 'pwd'
- Review any recent commits with 'git log --oneline -5'
- Check session state files for your progress
- Continue autonomous work from where you left off
"""
        
        role_specific_instructions = {
            'orchestrator': """
ORCHESTRATOR RECOVERY TASKS:
- Check project status and team coordination
- Review scheduled check-ins and update timing
- Verify all agents are active and making progress
- Update project status and communicate with team
- Schedule next check-in cycle
""",
            'project_manager': """
PROJECT MANAGER RECOVERY TASKS:
- Review team progress and quality metrics
- Check git workflow and integration status
- Verify testing coverage and code quality
- Update project documentation and status
- Coordinate with Orchestrator on blockers
""",
            'developer': """
DEVELOPER RECOVERY TASKS:
- Check current implementation status
- Review recent commits and continue coding
- Verify development environment setup
- Run tests to ensure code quality
- Commit progress every 30 minutes
""",
            'tester': """
TESTER RECOVERY TASKS:
- Review test suite status and coverage
- Check for new features requiring tests
- Run existing tests and verify results
- Update test documentation
- Coordinate with Developer on test requirements
""",
            'sysadmin': """
SYSADMIN RECOVERY TASKS:
- Check system status and services
- Verify permissions and user access
- Review system logs for issues
- Continue infrastructure setup tasks
- Monitor resource usage and performance
""",
            'devops': """
DEVOPS RECOVERY TASKS:
- Check deployment pipeline status
- Verify CI/CD configurations
- Review containerization and orchestration
- Monitor deployment health
- Update infrastructure as code
""",
            'securityops': """
SECURITY OPS RECOVERY TASKS:
- Review security configurations and policies
- Check for security vulnerabilities
- Verify access controls and permissions
- Update security documentation
- Monitor for security incidents
""",
        }
        
        specific_instructions = role_specific_instructions.get(agent_role, """
RECOVERY TASKS:
- Review your role-specific responsibilities
- Check progress on assigned tasks
- Continue autonomous work
- Report status to Orchestrator
""")
        
        return f"{base_briefing}\n{specific_instructions}\nBegin recovery work now."


# Database tracking for agent health
class AgentHealthDatabase:
    """Database tracking for agent health metrics"""
    
    def __init__(self, db_path: str = "task_queue.db"):
        self.db_path = db_path
        self._create_tables()
    
    def _create_tables(self):
        """Create agent health tracking tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    session_name TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    window_index INTEGER,
                    last_health_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_stuck BOOLEAN DEFAULT FALSE,
                    stuck_since TIMESTAMP,
                    recovery_attempts INTEGER DEFAULT 0,
                    last_recovery_attempt TIMESTAMP,
                    health_data TEXT  -- JSON blob for detailed health info
                )
            """)
            
            # Create indices for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_health_session ON agent_health(session_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_health_stuck ON agent_health(is_stuck)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_health_check_time ON agent_health(last_health_check)")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to create agent health tables: {e}")
    
    def record_health_check(self, session_name: str, health_status: Dict[str, Any]):
        """Record health check results in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            current_time = int(time.time())
            
            for agent_name, health_data in health_status.items():
                # Get project_id if available
                project_id = None
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM project_queue WHERE main_session = ? LIMIT 1", (session_name,))
                row = cursor.fetchone()
                if row:
                    project_id = row[0]
                
                # Insert or update health record
                cursor.execute("""
                    INSERT OR REPLACE INTO agent_health 
                    (project_id, session_name, agent_name, window_index, last_health_check, 
                     is_stuck, stuck_since, health_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    project_id,
                    session_name,
                    agent_name,
                    health_data.get('window_index'),
                    current_time,
                    health_data.get('is_stuck', False),
                    current_time if health_data.get('is_stuck') else None,
                    json.dumps(health_data)
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to record health check for {session_name}: {e}")
    
    def record_recovery_attempt(self, session_name: str, agent_name: str, success: bool):
        """Record recovery attempt results"""
        try:
            conn = sqlite3.connect(self.db_path)
            current_time = int(time.time())
            
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE agent_health 
                SET recovery_attempts = recovery_attempts + 1,
                    last_recovery_attempt = ?,
                    is_stuck = ?
                WHERE session_name = ? AND agent_name = ?
            """, (current_time, not success, session_name, agent_name))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to record recovery attempt for {session_name}:{agent_name}: {e}")


if __name__ == "__main__":
    # Test the agent health monitor
    logging.basicConfig(level=logging.INFO)
    
    monitor = AgentHealthMonitor()
    db = AgentHealthDatabase()
    
    # Test with a session (replace with actual session name)
    test_session = "test-session"
    health_status = monitor.check_agent_health(test_session)
    
    print(f"Health status for {test_session}:")
    for agent, status in health_status.items():
        print(f"  {agent}: {status}")
    
    # Record to database
    db.record_health_check(test_session, health_status)
    
    print("Health check completed and recorded.")
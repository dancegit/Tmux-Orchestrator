#!/usr/bin/env python3
"""
Enhanced completion detection system with multiple fallback methods.
Reduces reliance on fragile string matching.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Import health monitoring only when available
try:
    from agent_health_monitor import AgentHealthMonitor
    HEALTH_MONITORING_AVAILABLE = True
except ImportError:
    HEALTH_MONITORING_AVAILABLE = False
    logger.debug("Agent health monitoring not available")


class CompletionDetector:
    """Multi-method completion detection system"""
    
    def __init__(self, tmux_orchestrator_path: Path = None):
        self.tmux_orchestrator_path = tmux_orchestrator_path or Path(__file__).parent
        
        # Initialize health monitoring if available
        if HEALTH_MONITORING_AVAILABLE:
            self.health_monitor = AgentHealthMonitor()
        else:
            self.health_monitor = None
        
    def check_completion_marker(self, session_name: str) -> bool:
        """Check if a completion marker file exists"""
        marker_path = self.tmux_orchestrator_path / 'registry' / 'projects' / session_name / 'COMPLETION_MARKER'
        if marker_path.exists():
            try:
                with open(marker_path) as f:
                    data = json.load(f)
                    logger.info(f"Found completion marker for {session_name}: {data}")
                    return True
            except:
                # Even corrupted marker indicates completion attempt
                return True
        return False
    
    def check_git_completion(self, project_path: str, session_name: str) -> bool:
        """Check git commits for completion indicators"""
        try:
            # Look for worktrees related to this session
            worktree_patterns = [
                f"{project_path}*{session_name}*worktrees",
                f"{project_path}*worktrees"
            ]
            
            for pattern in worktree_patterns:
                worktree_dirs = list(Path(project_path).parent.glob(pattern))
                for worktree_dir in worktree_dirs:
                    # Check each agent's worktree for completion commits
                    for agent_dir in worktree_dir.iterdir():
                        if agent_dir.is_dir() and (agent_dir / '.git').exists():
                            result = subprocess.run(
                                ['git', '-C', str(agent_dir), 'log', '--oneline', '-10', '--grep=complete', '-i'],
                                capture_output=True, text=True
                            )
                            if result.returncode == 0 and result.stdout:
                                # Found commits with "complete" in message
                                logger.info(f"Found completion commits in {agent_dir}: {result.stdout[:100]}...")
                                return True
        except Exception as e:
            logger.debug(f"Git check failed: {e}")
        return False
    
    def check_phase_completion(self, session_name: str) -> Tuple[bool, int, int]:
        """Check implementation phases completion in SessionState"""
        try:
            session_state_path = self.tmux_orchestrator_path / 'registry' / 'projects' / session_name / 'session_state.json'
            if session_state_path.exists():
                with open(session_state_path) as f:
                    state = json.load(f)
                    
                # Check implementation phases
                phases = state.get('implementation_plan', {}).get('phases', [])
                if phases:
                    completed = sum(1 for p in phases if p.get('status') == 'completed')
                    total = len(phases)
                    
                    # If all phases completed, project is done
                    if completed == total and total > 0:
                        logger.info(f"All {total} phases completed for {session_name}")
                        return True, completed, total
                    
                    return False, completed, total
        except Exception as e:
            logger.debug(f"Phase check failed: {e}")
        return False, 0, 0
    
    def check_tmux_output(self, session_name: str) -> Optional[str]:
        """Capture recent tmux output for analysis"""
        try:
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', f'{session_name}:0', '-p', '-S', '-200'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout
        except:
            pass
        return None
    
    def analyze_completion_indicators(self, output: str) -> Dict[str, Any]:
        """Analyze output for multiple completion indicators"""
        indicators = {
            'explicit_complete': False,
            'all_tasks_done': False,
            'decommission_ready': False,
            'no_active_work': False,
            'error_indicators': False,
            'confidence': 0.0
        }
        
        if not output:
            return indicators
        
        output_lower = output.lower()
        
        # Explicit completion statements
        completion_phrases = [
            'project completed successfully',
            'all tasks completed',
            '100% complete',
            'project complete',
            'implementation complete',
            'ready for decommission',
            'marked for decommission',
            'decommissioning agents',
            'project is complete'
        ]
        
        for phrase in completion_phrases:
            if phrase in output_lower:
                indicators['explicit_complete'] = True
                indicators['confidence'] += 0.4
                break
        
        # All tasks done indicators
        if ('all tasks' in output_lower and 'complet' in output_lower) or \
           ('no pending' in output_lower and 'task' in output_lower) or \
           ('todo' in output_lower and 'empty' in output_lower):
            indicators['all_tasks_done'] = True
            indicators['confidence'] += 0.3
        
        # Decommission indicators
        if 'decommission' in output_lower or 'shutting down' in output_lower:
            indicators['decommission_ready'] = True
            indicators['confidence'] += 0.2
        
        # Check for active work indicators (negative signals)
        active_phrases = [
            'working on',
            'in progress',
            'implementing',
            'currently',
            'starting task',
            'beginning'
        ]
        
        active_count = sum(1 for phrase in active_phrases if phrase in output_lower)
        if active_count == 0:
            indicators['no_active_work'] = True
            indicators['confidence'] += 0.1
        else:
            indicators['confidence'] -= 0.1 * active_count
        
        # Error indicators
        error_phrases = ['error:', 'failed:', 'exception:', 'critical:']
        if any(phrase in output_lower for phrase in error_phrases):
            indicators['error_indicators'] = True
            indicators['confidence'] -= 0.2
        
        # Boost confidence based on output volume (indicates substantial work)
        if output:
            line_count = len(output.splitlines())
            if line_count > 5000:  # Threshold for "substantial" output
                indicators['confidence'] += 0.2
                logger.debug(f"Boosted confidence by 0.2 due to high output volume ({line_count} lines)")
            elif line_count > 1000:
                indicators['confidence'] += 0.1
                logger.debug(f"Boosted confidence by 0.1 due to moderate output volume ({line_count} lines)")
        
        # Clamp confidence between 0 and 1
        indicators['confidence'] = max(0.0, min(1.0, indicators['confidence']))
        
        return indicators
    
    def detect_completion(self, project: Dict[str, Any]) -> Tuple[str, str]:
        """
        Comprehensive completion detection using multiple methods.
        
        Returns: (status, reason)
            status: 'completed', 'failed', 'processing'
            reason: Human-readable explanation
        """
        session_name = project.get('session_name', '')
        project_path = project.get('project_path', '')
        
        # Method 1: Check for completion marker (highest priority)
        if self.check_completion_marker(session_name):
            return 'completed', 'Completion marker file found'
        
        # Method 2: Check git for completion commits
        if project_path and self.check_git_completion(project_path, session_name):
            return 'completed', 'Git commits indicate completion'
        
        # Method 3: Check phase completion
        phase_complete, completed_phases, total_phases = self.check_phase_completion(session_name)
        if phase_complete:
            return 'completed', f'All {total_phases} implementation phases completed'
        
        # Method 4: Check for stuck agents (NEW)
        if self.health_monitor and session_name:
            health_status = self.health_monitor.check_agent_health(session_name)
            
            if health_status:
                stuck_agents = [
                    name for name, status in health_status.items() 
                    if status.get('is_stuck', False) and status.get('stuck_duration', 0) > 1800
                ]
                
                if stuck_agents:
                    # Don't mark as failed if other agents are active
                    active_agents = [
                        name for name, status in health_status.items()
                        if status.get('has_claude', False) and not status.get('is_stuck', False)
                    ]
                    
                    if not active_agents:
                        return 'failed', f"All agents stuck in bash mode: {', '.join(stuck_agents)}"
                    else:
                        logger.warning(f"Stuck agents detected but others active: {stuck_agents}")
                        # Attempt recovery is handled by the monitor daemon, not here
                        # Continue with other detection methods
        
        # Method 5: Analyze tmux output
        output = self.check_tmux_output(session_name)
        if output:
            indicators = self.analyze_completion_indicators(output)
            
            # High confidence completion
            if indicators['confidence'] >= 0.7:
                reasons = []
                if indicators['explicit_complete']:
                    reasons.append('explicit completion statement')
                if indicators['all_tasks_done']:
                    reasons.append('all tasks done')
                if indicators['decommission_ready']:
                    reasons.append('ready for decommission')
                
                return 'completed', f"High confidence ({indicators['confidence']:.2f}): {', '.join(reasons)}"
            
            # Check for failures
            if indicators['error_indicators'] and indicators['confidence'] < 0.3:
                return 'failed', f"Error indicators detected with low confidence ({indicators['confidence']:.2f})"
        
        # Still processing
        progress_info = []
        if total_phases > 0:
            progress_info.append(f"{completed_phases}/{total_phases} phases done")
        
        return 'processing', f"Still in progress: {', '.join(progress_info) if progress_info else 'no clear completion indicators'}"


def create_completion_marker(session_name: str, project_id: int, reason: str = ""):
    """Create a completion marker file for a project"""
    tmux_orchestrator_path = Path(__file__).parent
    marker_dir = tmux_orchestrator_path / 'registry' / 'projects' / session_name
    marker_dir.mkdir(parents=True, exist_ok=True)
    
    marker_path = marker_dir / 'COMPLETION_MARKER'
    marker_data = {
        'completed_at': datetime.now().isoformat(),
        'project_id': project_id,
        'session_name': session_name,
        'reason': reason,
        'version': '1.0'
    }
    
    with open(marker_path, 'w') as f:
        json.dump(marker_data, f, indent=2)
    
    logger.info(f"Created completion marker for {session_name} (project {project_id})")
    return marker_path
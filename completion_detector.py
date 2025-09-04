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
            'confidence': 0.0,
            'is_status_report': False  # New indicator for status reports
        }
        
        if not output:
            return indicators
        
        output_lower = output.lower()
        
        # Check if this is a status report (not an error)
        status_report_indicators = [
            'orchestrator report',
            'status report',
            'project status',
            'team status',
            'progress report',
            'status update'
        ]
        
        for indicator in status_report_indicators:
            if indicator in output_lower:
                indicators['is_status_report'] = True
                break
        
        # Handle "NOT READY" status - this means processing, not failure!
        if '❌ not ready' in output_lower or 'not ready' in output_lower:
            if indicators['is_status_report']:
                # In a status report, "NOT READY" means still processing
                indicators['confidence'] += 0.2  # Boost confidence - project is active
                logger.debug("Found 'NOT READY' in status report - treating as active processing")
            else:
                # Outside status report, might be a concern
                indicators['confidence'] -= 0.1
        
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
        
        # Error indicators (with better context awareness)
        # Only count as errors if they appear multiple times and not in normal messages
        error_phrases = ['error:', 'failed:', 'exception:']
        error_count = 0
        false_positive_patterns = [
            'critical: you work from',  # Part of orchestrator briefing
            'error: /bin/bash',  # Normal bash command errors
            'error: python3:',  # Normal python errors from wrong paths
            'attempt 1/3',  # Retry messages
            'command not found',  # Minor script errors
            'not ready',  # Status indicator, not error
            '❌ not ready',  # Status with emoji
            'project completion: ❌',  # Status report
        ]
        
        # Skip error counting in status reports
        if not indicators['is_status_report']:
            for line in output_lower.split('\n'):
                # Skip lines that are known false positives
                if any(pattern in line for pattern in false_positive_patterns):
                    continue
                
                # Count real errors
                for phrase in error_phrases:
                    if phrase in line:
                        # Check if it's a significant error (not just a path or command issue)
                        if 'traceback' in line or 'assertion' in line or 'unhandled' in line:
                            error_count += 2  # More serious errors
                        else:
                            error_count += 1
        
        # Only flag as error if we have multiple significant errors
        if error_count >= 5:  # Threshold for real problems
            indicators['error_indicators'] = True
            indicators['confidence'] -= 0.2
        elif error_count >= 3:
            indicators['confidence'] -= 0.1  # Minor confidence reduction for some errors
        
        # Handle emoji indicators intelligently
        emoji_context = self._analyze_emoji_context(output)
        indicators['confidence'] += emoji_context['score']
        
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
        
        # CRITICAL: First validate actual implementation exists
        # This prevents marking empty projects as complete
        if project_path:
            try:
                from implementation_validator import validate_project_implementation
                if not validate_project_implementation(project_path):
                    logger.warning(f"Project {session_name} has NO valid implementation - cannot mark complete")
                    return 'processing', 'Implementation validation failed - no actual code found'
            except Exception as e:
                logger.error(f"Error validating implementation: {e}")
                # Don't mark complete if we can't validate
                return 'processing', 'Unable to validate implementation'
        
        # Method 1: Check for completion marker (highest priority)
        if self.check_completion_marker(session_name):
            # Even with marker, validate implementation
            if project_path:
                try:
                    from implementation_validator import validate_project_implementation
                    if not validate_project_implementation(project_path):
                        logger.error(f"Completion marker found but NO IMPLEMENTATION - removing marker")
                        marker_path = self.tmux_orchestrator_path / 'registry' / 'projects' / session_name / 'COMPLETION_MARKER'
                        marker_path.unlink(missing_ok=True)
                        return 'processing', 'Marker found but implementation invalid - removed marker'
                except:
                    pass
            return 'completed', 'Completion marker file found'
        
        # Method 2: Check git for completion commits
        if project_path and self.check_git_completion(project_path, session_name):
            # Validate implementation before accepting git completion
            try:
                from implementation_validator import validate_project_implementation
                if validate_project_implementation(project_path):
                    # Auto-create marker if git indicates completion but marker missing
                    self.auto_create_marker(project, 'Git commits indicate completion')
                    return 'completed', 'Git commits indicate completion (marker auto-created)'
                else:
                    return 'processing', 'Git shows completion commits but implementation is invalid'
            except:
                return 'processing', 'Unable to validate git completion'
        
        # Method 3: Check phase completion
        phase_complete, completed_phases, total_phases = self.check_phase_completion(session_name)
        if phase_complete:
            # Validate implementation before accepting phase completion
            if project_path:
                try:
                    from implementation_validator import validate_project_implementation
                    if validate_project_implementation(project_path):
                        # Auto-create marker if phases complete but marker missing
                        self.auto_create_marker(project, f'All {total_phases} implementation phases completed')
                        return 'completed', f'All {total_phases} implementation phases completed (marker auto-created)'
                    else:
                        return 'processing', f'Phases show complete but implementation is invalid'
                except:
                    return 'processing', 'Unable to validate phase completion'
        
        # Method 4: Check for stuck agents (NEW)
        active_agent_count = 0
        if self.health_monitor and session_name:
            health_status = self.health_monitor.check_agent_health(session_name)
            
            if health_status:
                stuck_agents = [
                    name for name, status in health_status.items() 
                    if status.get('is_stuck', False) and status.get('stuck_duration', 0) > 1800
                ]
                
                active_agents = [
                    name for name, status in health_status.items()
                    if status.get('has_claude', False) and not status.get('is_stuck', False)
                ]
                
                active_agent_count = len(active_agents)
                
                if stuck_agents:
                    # Don't mark as failed if other agents are active
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
                
                reason_text = f"High confidence ({indicators['confidence']:.2f}): {', '.join(reasons)}"
                # Auto-create marker if tmux output indicates completion but marker missing
                self.auto_create_marker(project, reason_text)
                return 'completed', f"{reason_text} (marker auto-created)"
            
            # Check for failures - but override if agents are active
            if indicators['error_indicators'] and indicators['confidence'] < 0.3:
                # IMPORTANT: Override failure if we have active agents
                if active_agent_count > 0:
                    logger.info(f"Would mark as failed but {active_agent_count} agents are active - keeping as processing")
                    return 'processing', f"Errors detected but {active_agent_count} agents still active"
                
                # Also check for recent activity as override
                if indicators.get('is_status_report', False):
                    logger.info("Would mark as failed but this is a status report - keeping as processing")
                    return 'processing', "Status report with low confidence - still processing"
                
                return 'failed', f"Error indicators detected with low confidence ({indicators['confidence']:.2f})"
        
        # Still processing
        progress_info = []
        if total_phases > 0:
            progress_info.append(f"{completed_phases}/{total_phases} phases done")
        
        return 'processing', f"Still in progress: {', '.join(progress_info) if progress_info else 'no clear completion indicators'}"
    
    def _analyze_emoji_context(self, output: str) -> Dict[str, float]:
        """Analyze emoji usage in context to determine sentiment"""
        result = {'score': 0.0}
        
        # Define emoji mappings with context-aware scoring
        emoji_map = {
            '✅': 0.15,   # Success/completion
            '❌': 0.0,    # Context-dependent (see below)
            '⚠️': -0.05,  # Warning, not failure
            '🚀': 0.1,    # Progress/deployment
            '📊': 0.05,   # Status/metrics (neutral-positive)
            '🔍': 0.05,   # Investigation/analysis
            '⏳': 0.0,    # Waiting/pending (neutral)
            '🛠️': 0.05,   # Working/building
        }
        
        output_lower = output.lower()
        
        for emoji, base_score in emoji_map.items():
            count = output.count(emoji)
            if count > 0:
                # Special handling for ❌
                if emoji == '❌':
                    # Check context around each occurrence
                    for i in range(count):
                        idx = output.find('❌', 0)
                        if idx != -1:
                            # Get surrounding context (50 chars each side)
                            start = max(0, idx - 50)
                            end = min(len(output), idx + 50)
                            context = output[start:end].lower()
                            
                            # ❌ is neutral/positive in these contexts
                            if 'not ready' in context or 'pending' in context or 'in progress' in context:
                                pass  # No score change
                            else:
                                # ❌ is negative in failure context
                                result['score'] -= 0.1
                else:
                    # Apply normal scoring for other emojis
                    result['score'] += base_score * count
        
        return result
    
    def auto_create_marker(self, project: Dict[str, Any], reason: str):
        """Auto-create marker when completion detected but marker missing (enforces autonomy)"""
        session_name = project.get('session_name', '')
        project_id = project.get('id', 0)
        project_path = project.get('project_path', '')
        
        if not session_name:
            logger.warning("Cannot auto-create marker: missing session_name")
            return
            
        try:
            # Create the registry-based marker first
            marker_path = create_completion_marker(session_name, project_id, f"Auto-created by monitor: {reason}")
            logger.info(f"Auto-created registry marker for {session_name}")
            
            # Also try to create COMPLETED file in project worktree if path available
            if project_path:
                try:
                    completed_file = Path(project_path) / 'COMPLETED'
                    if not completed_file.exists():
                        with open(completed_file, 'w') as f:
                            f.write(f"Auto-created by monitor: {reason}\n{datetime.now().isoformat()}\n")
                        logger.info(f"Auto-created COMPLETED file in {project_path}")
                        
                        # Try to git add/commit if in repo
                        try:
                            subprocess.run(['git', 'add', str(completed_file)], 
                                         cwd=project_path, check=True, timeout=10)
                            subprocess.run(['git', 'commit', '-m', 'auto: completion marker created by monitor'], 
                                         cwd=project_path, check=True, timeout=10)
                            logger.info(f"Auto-committed marker to git in {project_path}")
                        except subprocess.CalledProcessError:
                            logger.debug("Could not auto-commit marker to git (normal if not in repo)")
                        except Exception as e:
                            logger.debug(f"Git operations failed: {e}")
                except Exception as e:
                    logger.warning(f"Could not create worktree marker: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to auto-create marker for {session_name}: {e}")


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
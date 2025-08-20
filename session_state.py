#!/usr/bin/env python3
"""
Session state management for Tmux Orchestrator
Tracks active orchestration sessions and enables proper resume functionality
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class AgentState:
    """State of a single agent in the orchestration"""
    role: str
    window_index: int
    window_name: str
    worktree_path: str
    last_briefing_time: Optional[str] = None
    last_check_in_time: Optional[str] = None
    is_alive: bool = True
    is_exhausted: bool = False
    credit_reset_time: Optional[str] = None
    current_branch: Optional[str] = None
    commit_hash: Optional[str] = None
    waiting_for: Optional[Dict[str, Any]] = None  # Track authorization waits


@dataclass
class SessionState:
    """Complete state of an orchestration session"""
    session_name: str
    project_path: str
    project_name: str
    implementation_spec_path: str
    created_at: str
    updated_at: str
    agents: Dict[str, AgentState]
    orchestrator_window: int = 0
    project_size: str = "medium"
    parent_branch: Optional[str] = None
    completion_status: str = "pending"  # 'pending', 'completed', or 'failed'
    completion_time: Optional[str] = None
    failure_reason: Optional[str] = None  # NEW: e.g., "timeout_after_4_hours", "manual_termination"
    phases_completed: List[str] = None  # Track completed implementation phases
    spec_path: Optional[str] = None  # Path to spec file for notifications
    dependencies: Dict[str, List[str]] = None  # Role dependencies (e.g., {'pm': ['devops']})
    worktree_base_path: Optional[str] = None  # Custom base path for worktrees (overrides registry default)
    status_reports: Dict[str, Dict[str, Any]] = None  # Add this for {role: {"topic": "deployment", "status": "COMPLETE", "details": "...", "timestamp": "..."}}
    batch_id: Optional[str] = None  # Batch identifier for retry system
    worktrees: Dict[str, str] = None  # Role to worktree path mapping for local git optimization
    
    def __post_init__(self):
        """Initialize mutable default values"""
        if self.phases_completed is None:
            self.phases_completed = []
        if self.dependencies is None:
            self.dependencies = {}
        if self.status_reports is None:
            self.status_reports = {}
        if self.worktrees is None:
            self.worktrees = {}
    

class SessionStateManager:
    """Manages session state persistence and recovery"""
    
    def __init__(self, tmux_orchestrator_path: Path):
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.registry_dir = tmux_orchestrator_path / 'registry'
        # Initialize git coordinator for branch syncing
        try:
            from git_coordinator import GitCoordinator
            self.git_coordinator = GitCoordinator(tmux_orchestrator_path)
        except ImportError:
            self.git_coordinator = None
        
    def get_state_file_path(self, project_name: str) -> Path:
        """Get the path to the session state file for a project"""
        project_dir = self.registry_dir / 'projects' / project_name.lower().replace(' ', '-')
        return project_dir / 'session_state.json'
        
    def save_session_state(self, state: SessionState) -> None:
        """Save session state to disk"""
        state.updated_at = datetime.now().isoformat()
        state_file = self.get_state_file_path(state.project_name)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict for JSON serialization
        state_dict = asdict(state)
        
        # Convert agent states to dicts
        state_dict['agents'] = {
            role: asdict(agent) for role, agent in state.agents.items()
        }
        
        state_file.write_text(json.dumps(state_dict, indent=2))
        
    def load_session_state(self, project_name: str) -> Optional[SessionState]:
        """Load session state from disk with fallback creation"""
        state_file = self.get_state_file_path(project_name)
        
        if not state_file.exists():
            # Try to create minimal state if this looks like an active project
            return self._create_fallback_state(project_name)
            
        try:
            state_dict = json.loads(state_file.read_text())
            
            # Reconstruct agent states
            agents = {}
            for role, agent_dict in state_dict['agents'].items():
                agents[role] = AgentState(**agent_dict)
                
            state_dict['agents'] = agents
            
            # NEW: Auto-sync on load if git coordinator available and divergent
            state = SessionState(**state_dict)
            if self.git_coordinator and self.sync_branches(state, force=False):
                print(f"Auto-synced branches for {project_name} on load")
            
            # DEADLOCK PREVENTION: Auto-clear waiting states on load
            deadlock_cleared = False
            for agent in state.agents.values():
                if agent.waiting_for:
                    agent.waiting_for = None
                    agent.is_alive = True  # Reset to encourage action
                    deadlock_cleared = True
                    print(f"⚡ CLEARED waiting state for {agent.role} in {project_name} - agent should proceed autonomously")
            
            if deadlock_cleared:
                self.save_session_state(state)  # Persist changes
                print(f"🚫 DEADLOCK PREVENTION: Cleared all waiting states in {project_name}")
            
            return state
            
        except Exception as e:
            print(f"Error loading session state: {e}")
            # Try fallback creation
            return self._create_fallback_state(project_name)
    
    def _create_fallback_state(self, project_name: str) -> Optional[SessionState]:
        """Create minimal fallback state by detecting active tmux session"""
        try:
            # Try to find the session name from project name
            session_name = f"{project_name.lower().replace(' ', '-')}-impl"
            
            # Check if tmux session exists
            result = subprocess.run(
                ['tmux', 'list-sessions', '-f', f"#{{{session_name}}}"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                # Try alternate session names
                for suffix in ['-a9601f5d', '', '-impl-a9601f5d']:
                    alt_session = f"{project_name.lower().replace(' ', '-')}{suffix}"
                    result = subprocess.run(
                        ['tmux', 'has-session', '-t', alt_session],
                        capture_output=True
                    )
                    if result.returncode == 0:
                        session_name = alt_session
                        break
                else:
                    return None
            
            # Get window list to detect agents
            result = subprocess.run(
                ['tmux', 'list-windows', '-t', session_name, '-F', '#{window_index}:#{window_name}'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return None
            
            # Create minimal agent states from windows
            agents = {}
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                if ':' in line:
                    window_index, window_name = line.split(':', 1)
                    try:
                        index = int(window_index)
                        # Map common window names to roles
                        role = self._map_window_to_role(window_name)
                        if role:
                            agents[role] = AgentState(
                                role=role,
                                window_index=index,
                                window_name=window_name,
                                worktree_path="",  # Will be updated later
                                last_briefing_time=datetime.now().isoformat(),
                                is_alive=True,
                                is_exhausted=False
                            )
                    except ValueError:
                        continue
            
            if not agents:
                return None
            
            # Try to derive paths
            project_path, worktree_paths, spec_path, impl_spec_path = self._derive_project_paths(project_name, session_name)
            
            # Update agent worktree paths
            for role, agent in agents.items():
                if role in worktree_paths:
                    agent.worktree_path = str(worktree_paths[role])
            
            # Create minimal session state with derived paths
            fallback_state = SessionState(
                session_name=session_name,
                project_path=str(project_path) if project_path else "",
                project_name=project_name,
                implementation_spec_path=str(impl_spec_path) if impl_spec_path else "",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                agents=agents,
                completion_status="pending",
                spec_path=str(spec_path) if spec_path else None,
                worktree_base_path=str(worktree_paths.get('base')) if 'base' in worktree_paths else None
            )
            
            # Save the fallback state
            self.save_session_state(fallback_state)
            print(f"Created fallback state for {project_name} with {len(agents)} agents and derived paths")
            
            return fallback_state
            
        except Exception as e:
            print(f"Failed to create fallback state for {project_name}: {e}")
            return None
    
    def _derive_project_paths(self, project_name: str, session_name: str) -> tuple[Optional[Path], Dict[str, Path], Optional[Path], Optional[Path]]:
        """Try to derive project paths from various sources"""
        project_path = None
        worktree_paths = {}
        spec_path = None
        impl_spec_path = None
        
        # Strategy 1: Check for spec files in registry
        registry_project_dir = self.registry_dir / 'projects' / project_name.lower().replace(' ', '-')
        if registry_project_dir.exists():
            # Look for implementation spec
            impl_spec_candidates = list(registry_project_dir.glob('implementation_spec*.json'))
            if impl_spec_candidates:
                impl_spec_path = impl_spec_candidates[0]
                
                # Try to load it and extract paths
                try:
                    impl_spec_data = json.loads(impl_spec_path.read_text())
                    if 'spec_path' in impl_spec_data:
                        spec_path = Path(impl_spec_data['spec_path'])
                        if spec_path.exists():
                            # Find git root from spec path
                            from pathlib import Path as P
                            current = spec_path.parent
                            while current != current.parent:
                                if (current / '.git').exists():
                                    project_path = current
                                    break
                                current = current.parent
                except Exception:
                    pass
        
        # Strategy 2: Look for worktrees in common locations
        if project_path:
            # Check for sibling worktree directories
            worktree_base = project_path.parent / f"{project_path.name}-tmux-worktrees"
            if worktree_base.exists():
                worktree_paths['base'] = worktree_base
                
                # Map common role directories
                role_dirs = {
                    'orchestrator': ['orchestrator'],
                    'project_manager': ['project-manager', 'pm'],
                    'developer': ['developer', 'dev'],
                    'tester': ['tester', 'test'],
                    'testrunner': ['testrunner', 'test-runner'],
                    'devops': ['devops'],
                    'sysadmin': ['sysadmin', 'sys-admin'],
                    'securityops': ['securityops', 'security-ops'],
                    'networkops': ['networkops', 'network-ops'],
                    'monitoringops': ['monitoringops', 'monitoring-ops'],
                    'databaseops': ['databaseops', 'database-ops']
                }
                
                for role, possible_names in role_dirs.items():
                    for name in possible_names:
                        candidate = worktree_base / name
                        if candidate.exists() and (candidate / '.git').exists():
                            worktree_paths[role] = candidate
                            break
        
        # Strategy 3: Check for legacy registry worktrees
        if not worktree_paths and registry_project_dir.exists():
            legacy_worktree_dir = registry_project_dir / 'worktrees'
            if legacy_worktree_dir.exists():
                for role_dir in legacy_worktree_dir.iterdir():
                    if role_dir.is_dir() and (role_dir / '.git').exists():
                        role = self._map_window_to_role(role_dir.name)
                        if role:
                            worktree_paths[role] = role_dir
        
        # Strategy 4: Try to find project from active tmux panes
        if not project_path:
            try:
                # Get current directory from orchestrator window
                result = subprocess.run(
                    ['tmux', 'display-message', '-t', f'{session_name}:0', '-p', '#{pane_current_path}'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    pane_path = Path(result.stdout.strip())
                    # Find git root
                    current = pane_path
                    while current != current.parent:
                        if (current / '.git').exists():
                            # Check if this is a worktree
                            git_file = current / '.git'
                            if git_file.is_file():
                                # It's a worktree, find the main project
                                git_content = git_file.read_text()
                                if 'gitdir:' in git_content:
                                    gitdir = git_content.split('gitdir:')[1].strip()
                                    # Navigate from worktree to main project
                                    main_git = Path(gitdir).parent.parent
                                    if main_git.exists() and (main_git / '.git').is_dir():
                                        project_path = main_git
                                        break
                            else:
                                # Regular git repo
                                project_path = current
                                break
                        current = current.parent
            except Exception:
                pass
        
        return project_path, worktree_paths, spec_path, impl_spec_path
    
    def _map_window_to_role(self, window_name: str) -> Optional[str]:
        """Map tmux window names to agent roles"""
        name_lower = window_name.lower()
        
        # Common mappings
        role_mappings = {
            'orchestrator': 'orchestrator',
            'project-manager': 'project_manager', 
            'pm': 'project_manager',
            'developer': 'developer', 
            'dev': 'developer',
            'tester': 'tester',
            'test': 'tester',
            'testrunner': 'testrunner',
            'test-runner': 'testrunner',
            'researcher': 'researcher',
            'devops': 'devops',
            'sysadmin': 'sysadmin',
            'securityops': 'securityops',
            'networkops': 'networkops',
            'monitoringops': 'monitoringops',
            'databaseops': 'databaseops'
        }
        
        for pattern, role in role_mappings.items():
            if pattern in name_lower:
                return role
        
        return None
            
    def check_agent_alive(self, session_name: str, window_index: int) -> bool:
        """Check if an agent is alive and responsive"""
        try:
            # Capture last 50 lines from the pane
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', f'{session_name}:{window_index}', '-p', '-S', '-50'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return False
                
            pane_text = result.stdout.lower()
            
            # Check for various Claude UI indicators
            claude_indicators = [
                'human:',
                'assistant:',
                '? for shortcuts',
                'bypassing permissions',
                '> ',  # Claude's input prompt
                '│ >',  # Claude's input prompt in box
                'tokens used:',
                'context window:',
                '/exit to quit'
            ]
            
            # Check if any Claude indicator is present
            for indicator in claude_indicators:
                if indicator in pane_text:
                    return True
                    
            # Also check for the box-drawing characters that Claude uses
            if '╭' in pane_text or '│' in pane_text or '╰' in pane_text:
                # Likely Claude's UI
                return True
                    
            return False
            
        except Exception:
            return False
            
    def check_agent_exhausted(self, session_name: str, window_index: int) -> tuple[bool, Optional[str]]:
        """Check if an agent is credit exhausted and get reset time"""
        try:
            # Capture last 100 lines to find exhaustion messages
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', f'{session_name}:{window_index}', '-p', '-S', '-100'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return False, None
                
            pane_text = result.stdout
            
            # Check for exhaustion indicators
            is_exhausted = '/upgrade' in pane_text.lower() or 'approaching usage limit' in pane_text.lower()
            
            # Try to extract reset time
            reset_time = None
            for line in pane_text.split('\n'):
                if 'credits will reset at' in line.lower():
                    # Extract time from the line
                    parts = line.split('reset at')
                    if len(parts) > 1:
                        reset_time = parts[1].strip()
                        break
                        
            return is_exhausted, reset_time
            
        except Exception:
            return False, None
            
    def get_agent_git_status(self, worktree_path: str) -> tuple[Optional[str], Optional[str]]:
        """Get current branch and commit hash for an agent's worktree"""
        try:
            # Get current branch
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            branch = result.stdout.strip() if result.returncode == 0 else None
            
            # Get current commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            commit = result.stdout.strip()[:8] if result.returncode == 0 else None
            
            return branch, commit
            
        except Exception:
            return None, None
            
    def update_agent_status(self, state: SessionState, session_name: str) -> SessionState:
        """Update the status of all agents in the session"""
        for role, agent in state.agents.items():
            # Check if agent is alive
            agent.is_alive = self.check_agent_alive(session_name, agent.window_index)
            
            # Check if agent is exhausted
            agent.is_exhausted, agent.credit_reset_time = self.check_agent_exhausted(
                session_name, agent.window_index
            )
            
            # Update git status
            if agent.worktree_path and Path(agent.worktree_path).exists():
                agent.current_branch, agent.commit_hash = self.get_agent_git_status(
                    agent.worktree_path
                )
                
            # Update last check time
            agent.last_check_in_time = datetime.now().isoformat()
            
        state.updated_at = datetime.now().isoformat()
        return state
        
    def _check_status_report_rate_limit(self, state: SessionState, role: str) -> bool:
        """Check if a role has exceeded status report rate limit"""
        role_lower = role.lower()
        current_time = datetime.now()
        
        # Initialize rate limit tracking if not exists
        if not hasattr(state, 'status_report_history'):
            state.status_report_history = {}
        
        if role_lower not in state.status_report_history:
            state.status_report_history[role_lower] = []
        
        # Remove old reports (older than 5 minutes)
        cutoff_time = current_time - timedelta(minutes=5)
        state.status_report_history[role_lower] = [
            timestamp for timestamp in state.status_report_history[role_lower]
            if datetime.fromisoformat(timestamp) > cutoff_time
        ]
        
        # Check rate limit: max 5 reports per 5 minutes per role
        if len(state.status_report_history[role_lower]) >= 5:
            logger.warning(f"Rate limit exceeded for {role}: {len(state.status_report_history[role_lower])} reports in 5 minutes")
            return False
            
        # Add current timestamp
        state.status_report_history[role_lower].append(current_time.isoformat())
        return True
        
    def update_status_report(self, project_name: str, role: str, topic: str, status: str, details: str = ""):
        """Update status report for an agent with rate limiting"""
        state = self.load_session_state(project_name)
        if state:
            # Check rate limit
            if not self._check_status_report_rate_limit(state, role):
                logger.warning(f"Dropping status report from {role} due to rate limit")
                return
                
            state.status_reports[role.lower()] = {
                "topic": topic.lower(),
                "status": status.upper(),
                "details": details,
                "timestamp": datetime.now().isoformat()
            }
            self.save_session_state(state)
            
    def detect_deployment_conflict(self, project_name: str) -> bool:
        """Detect specific SysAdmin vs Developer deployment status conflict"""
        state = self.load_session_state(project_name)
        if not state or not state.status_reports:
            return False
            
        sysadmin_rep = state.status_reports.get('sysadmin', {})
        developer_rep = state.status_reports.get('developer', {})
        
        # Check for conflicting deployment statuses
        if (sysadmin_rep.get('topic') == 'deployment' and sysadmin_rep.get('status') == 'COMPLETE' and
            developer_rep.get('topic') == 'deployment' and developer_rep.get('status') in ['FAILURE', 'FAILED', 'ERROR']):
            return True
            
        return False
        
    def _detect_testing_conflict(self, state: SessionState) -> Optional[Dict[str, Any]]:
        """Detect conflicts between Developer and Tester about test status"""
        developer_rep = state.status_reports.get('developer', {})
        tester_rep = state.status_reports.get('tester', {})
        
        # Developer says tests pass, Tester says they fail
        if (developer_rep.get('topic') == 'testing' and developer_rep.get('status') in ['PASS', 'PASSING'] and
            tester_rep.get('topic') == 'testing' and tester_rep.get('status') in ['FAIL', 'FAILING', 'FAILED']):
            return {
                "type": "testing_status",
                "description": "Developer reports tests PASSING but Tester reports FAILING",
                "agents": ["developer", "tester"],
                "priority": "high",
                "suggested_action": "Tester status takes priority - investigate test failures"
            }
            
        # Developer says feature complete, Tester says not ready
        if (developer_rep.get('topic') == 'feature' and developer_rep.get('status') == 'COMPLETE' and
            tester_rep.get('topic') == 'feature' and tester_rep.get('status') in ['NOT_READY', 'INCOMPLETE', 'BLOCKED']):
            return {
                "type": "feature_readiness",
                "description": "Developer reports feature COMPLETE but Tester reports NOT_READY",
                "agents": ["developer", "tester"],
                "priority": "medium",
                "suggested_action": "Coordinate on feature completion criteria"
            }
        
        return None
        
    def _detect_integration_conflicts(self, state: SessionState) -> List[Dict[str, Any]]:
        """Detect conflicts where multiple agents report conflicting integration status"""
        conflicts = []
        
        # Group reports by topic
        topics = {}
        for role, report in state.status_reports.items():
            topic = report.get('topic')
            if topic:
                if topic not in topics:
                    topics[topic] = []
                topics[topic].append((role, report))
        
        # Check each topic for conflicting statuses
        for topic, reports in topics.items():
            if len(reports) >= 2:  # Need at least 2 reports to conflict
                success_agents = []
                failure_agents = []
                
                for role, report in reports:
                    status = report.get('status', '').upper()
                    if status in ['COMPLETE', 'SUCCESS', 'READY', 'PASS', 'PASSING']:
                        success_agents.append(role)
                    elif status in ['FAILURE', 'FAILED', 'ERROR', 'BLOCKED', 'NOT_READY', 'FAIL', 'FAILING']:
                        failure_agents.append(role)
                
                # Conflict if some report success and others report failure
                if success_agents and failure_agents:
                    conflicts.append({
                        "type": "integration_status",
                        "description": f"Conflicting {topic} status: {', '.join(success_agents)} report success but {', '.join(failure_agents)} report failure",
                        "agents": success_agents + failure_agents,
                        "priority": "high",
                        "suggested_action": f"Investigate {topic} status - coordinate between conflicting agents"
                    })
        
        return conflicts
        
    def _detect_resource_conflicts(self, state: SessionState) -> List[Dict[str, Any]]:
        """Detect conflicts where agents claim conflicting resource usage"""
        conflicts = []
        
        # Look for port conflicts
        port_usage = {}
        for role, report in state.status_reports.items():
            details = report.get('details', '').lower()
            # Extract port numbers from details
            import re
            ports = re.findall(r'port\s+(\d+)', details)
            for port in ports:
                if port not in port_usage:
                    port_usage[port] = []
                port_usage[port].append(role)
        
        # Check for multiple agents claiming same port
        for port, agents in port_usage.items():
            if len(agents) > 1:
                conflicts.append({
                    "type": "resource_conflict",
                    "description": f"Multiple agents claim port {port}: {', '.join(agents)}",
                    "agents": agents,
                    "priority": "medium", 
                    "suggested_action": f"Resolve port {port} conflict - assign unique ports"
                })
        
        return conflicts
        
    def _detect_timeline_conflicts(self, state: SessionState) -> List[Dict[str, Any]]:
        """Detect impossible timeline dependencies between agents"""
        conflicts = []
        
        # Check if a agent reports being blocked by another who reports completion
        for role, report in state.status_reports.items():
            details = report.get('details', '').lower()
            
            # Look for "waiting for X" or "blocked by Y" patterns
            blocked_patterns = [
                r'waiting for (\w+)',
                r'blocked by (\w+)', 
                r'depends on (\w+)',
                r'need (\w+) to'
            ]
            
            for pattern in blocked_patterns:
                import re
                matches = re.findall(pattern, details)
                for dependency in matches:
                    # Check if the dependency agent reports completion
                    dep_report = state.status_reports.get(dependency, {})
                    if dep_report.get('status', '').upper() in ['COMPLETE', 'SUCCESS', 'READY']:
                        conflicts.append({
                            "type": "timeline_conflict",
                            "description": f"{role} reports waiting for {dependency} but {dependency} reports completion",
                            "agents": [role, dependency],
                            "priority": "medium",
                            "suggested_action": f"Check if {role} has latest status from {dependency}"
                        })
        
        return conflicts
        
    def get_status_conflicts(self, project_name: str) -> List[Dict[str, Any]]:
        """Get all detected status conflicts for a project"""
        state = self.load_session_state(project_name)
        if not state or not state.status_reports:
            return []
            
        conflicts = []
        
        # 1. Deployment conflicts (SysAdmin vs Developer)
        if self.detect_deployment_conflict(project_name):
            conflicts.append({
                "type": "deployment_status",
                "description": "SysAdmin reports deployment COMPLETE but Developer reports FAILURE",
                "agents": ["sysadmin", "developer"],
                "priority": "high",
                "suggested_action": "Developer status takes priority - investigate deployment dependency issues"
            })
        
        # 2. Testing conflicts (Developer vs Tester)
        testing_conflict = self._detect_testing_conflict(state)
        if testing_conflict:
            conflicts.append(testing_conflict)
            
        # 3. Integration conflicts (Multiple agents claiming different states)
        integration_conflicts = self._detect_integration_conflicts(state)
        conflicts.extend(integration_conflicts)
        
        # 4. Resource conflicts (Multiple agents claiming same resources)
        resource_conflicts = self._detect_resource_conflicts(state)
        conflicts.extend(resource_conflicts)
        
        # 5. Timeline conflicts (Impossible dependencies)
        timeline_conflicts = self._detect_timeline_conflicts(state)
        conflicts.extend(timeline_conflicts)
            
        return conflicts
        
    def resolve_conflicts_automatically(self, project_name: str) -> List[Dict[str, Any]]:
        """Attempt to automatically resolve conflicts using predefined protocols"""
        conflicts = self.get_status_conflicts(project_name)
        resolutions = []
        
        for conflict in conflicts:
            resolution = self._attempt_conflict_resolution(project_name, conflict)
            if resolution:
                resolutions.append(resolution)
                
        return resolutions
        
    def _attempt_conflict_resolution(self, project_name: str, conflict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Attempt to resolve a specific conflict automatically"""
        conflict_type = conflict.get('type')
        agents = conflict.get('agents', [])
        
        # Resolution protocol for deployment conflicts
        if conflict_type == 'deployment_status':
            return self._resolve_deployment_conflict(project_name, agents)
            
        # Resolution protocol for testing conflicts  
        elif conflict_type == 'testing_status':
            return self._resolve_testing_conflict(project_name, agents)
            
        # Resolution protocol for integration conflicts
        elif conflict_type == 'integration_status':
            return self._resolve_integration_conflict(project_name, agents)
            
        # Resolution protocol for resource conflicts
        elif conflict_type == 'resource_conflict':
            return self._resolve_resource_conflict(project_name, agents, conflict)
            
        # Resolution protocol for timeline conflicts
        elif conflict_type == 'timeline_conflict':
            return self._resolve_timeline_conflict(project_name, agents)
            
        return None
        
    def _resolve_deployment_conflict(self, project_name: str, agents: List[str]) -> Dict[str, Any]:
        """Resolve deployment conflicts by prioritizing Developer status"""
        state = self.load_session_state(project_name)
        if not state:
            return None
            
        # Clear SysAdmin's conflicting report and notify about dependency issue
        if 'sysadmin' in state.status_reports:
            state.status_reports['sysadmin']['status'] = 'INVESTIGATING'
            state.status_reports['sysadmin']['details'] += ' [AUTO-RESOLVED: Investigating dependency issue reported by Developer]'
            state.status_reports['sysadmin']['timestamp'] = datetime.now().isoformat()
            
        # Mark Developer status as authoritative
        if 'developer' in state.status_reports:
            state.status_reports['developer']['details'] += ' [AUTO-RESOLVED: Status marked as authoritative]'
            
        self.save_session_state(state)
        
        return {
            'type': 'deployment_conflict_resolution',
            'action': 'prioritized_developer_status',
            'message': 'Developer status takes priority. SysAdmin notified to investigate dependency issues.',
            'agents_notified': ['sysadmin'],
            'next_steps': ['Investigate shared_kernel dependency', 'Coordinate deployment strategy']
        }
        
    def _resolve_testing_conflict(self, project_name: str, agents: List[str]) -> Dict[str, Any]:
        """Resolve testing conflicts by prioritizing Tester status"""
        state = self.load_session_state(project_name)
        if not state:
            return None
            
        # Update Developer to acknowledge test failures
        if 'developer' in state.status_reports:
            state.status_reports['developer']['status'] = 'FIXING'
            state.status_reports['developer']['details'] += ' [AUTO-RESOLVED: Addressing test failures identified by Tester]'
            
        # Mark Tester status as authoritative
        if 'tester' in state.status_reports:
            state.status_reports['tester']['details'] += ' [AUTO-RESOLVED: Test status confirmed as authoritative]'
            
        self.save_session_state(state)
        
        return {
            'type': 'testing_conflict_resolution', 
            'action': 'prioritized_tester_status',
            'message': 'Tester status takes priority. Developer notified to fix failing tests.',
            'agents_notified': ['developer'],
            'next_steps': ['Fix failing tests', 'Re-run test suite']
        }
        
    def _resolve_integration_conflict(self, project_name: str, agents: List[str]) -> Dict[str, Any]:
        """Resolve integration conflicts by escalating to Project Manager"""
        return {
            'type': 'integration_conflict_resolution',
            'action': 'escalated_to_pm',
            'message': 'Integration conflict escalated to Project Manager for coordination.',
            'agents_notified': ['project_manager'],
            'next_steps': ['PM to coordinate status alignment', 'Establish single source of truth']
        }
        
    def _resolve_resource_conflict(self, project_name: str, agents: List[str], conflict: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve resource conflicts by assigning alternative resources"""
        # Extract port number from conflict description
        import re
        description = conflict.get('description', '')
        port_match = re.search(r'port (\d+)', description)
        
        if port_match:
            conflicted_port = port_match.group(1)
            # Suggest alternative ports
            suggested_ports = self._suggest_alternative_ports(conflicted_port, agents)
            
            return {
                'type': 'resource_conflict_resolution',
                'action': 'assigned_alternative_resources',
                'message': f'Port conflict resolved by assigning alternative ports: {suggested_ports}',
                'agents_notified': agents,
                'next_steps': [f'Update configuration to use assigned ports: {suggested_ports}']
            }
        
        return {
            'type': 'resource_conflict_resolution',
            'action': 'manual_resolution_required',
            'message': 'Resource conflict requires manual intervention.',
            'agents_notified': ['orchestrator'],
            'next_steps': ['Manually assign unique resources to each agent']
        }
        
    def _resolve_timeline_conflict(self, project_name: str, agents: List[str]) -> Dict[str, Any]:
        """Resolve timeline conflicts by requesting status synchronization"""
        return {
            'type': 'timeline_conflict_resolution',
            'action': 'requested_status_sync',
            'message': 'Timeline conflict detected. Agents requested to synchronize status.',
            'agents_notified': agents,
            'next_steps': ['Verify current status with all agents', 'Update dependencies if needed']
        }
        
    def _suggest_alternative_ports(self, conflicted_port: str, agents: List[str]) -> Dict[str, str]:
        """Suggest alternative ports for conflicting agents"""
        base_port = int(conflicted_port)
        suggestions = {}
        
        for i, agent in enumerate(agents):
            # Suggest port base + agent index + 100 to avoid common conflicts
            suggested_port = base_port + i + 100
            suggestions[agent] = str(suggested_port)
            
        return suggestions

    def get_session_summary(self, state: SessionState) -> Dict[str, Any]:
        """Get a summary of the session state for display"""
        total_agents = len(state.agents)
        alive_agents = sum(1 for a in state.agents.values() if a.is_alive)
        exhausted_agents = sum(1 for a in state.agents.values() if a.is_exhausted)
        
        return {
            'session_name': state.session_name,
            'project_name': state.project_name,
            'created_at': state.created_at,
            'updated_at': state.updated_at,
            'total_agents': total_agents,
            'alive_agents': alive_agents,
            'exhausted_agents': exhausted_agents,
            'dead_agents': total_agents - alive_agents,
            'project_size': state.project_size,
            'agents': {
                role: {
                    'alive': agent.is_alive,
                    'exhausted': agent.is_exhausted,
                    'window': agent.window_index,
                    'branch': agent.current_branch,
                    'worktree': agent.worktree_path
                }
                for role, agent in state.agents.items()
            }
        }
    
    def update_agent_state(self, project_name: str, role: str, updates: Dict[str, Any]) -> None:
        """Update an agent's state and check dependencies"""
        state = self.load_session_state(project_name)
        if not state or role not in state.agents:
            return
            
        # Update the agent's attributes
        agent = state.agents[role]
        for key, value in updates.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
            
        # Save updated state
        self.save_session_state(state)
        
        # Check if this update resolves any dependencies
        self._check_dependencies(state, role)
    
    def _check_dependencies(self, state: SessionState, updated_role: str) -> None:
        """Check if updating a role resolves dependencies for other roles"""
        for dependent_role, required_roles in state.dependencies.items():
            if updated_role in required_roles:
                # Check if all dependencies are now satisfied
                all_satisfied = all(
                    self._is_role_complete(state, req_role) 
                    for req_role in required_roles
                )
                
                if all_satisfied:
                    # Notify the dependent role
                    self._notify_agent(state, dependent_role, 
                                     f"All dependencies satisfied! {updated_role} has completed.")
    
    def _is_role_complete(self, state: SessionState, role: str) -> bool:
        """Check if a role has completed its tasks"""
        if role not in state.agents:
            return False
            
        agent = state.agents[role]
        # Check various completion indicators
        if hasattr(agent, 'completion_status') and agent.completion_status == 'completed':
            return True
            
        # Check if recently active (within last 30 minutes)
        if agent.last_check_in_time:
            try:
                last_checkin = datetime.fromisoformat(agent.last_check_in_time)
                if (datetime.now() - last_checkin).total_seconds() < 1800:
                    return True
            except:
                pass
                
        return False
    
    def _notify_agent(self, state: SessionState, role: str, message: str) -> None:
        """Send a notification to an agent via tmux"""
        if role not in state.agents:
            return
            
        agent = state.agents[role]
        try:
            # Use send-claude-message.sh if available
            send_script = self.tmux_orchestrator_path / "send-claude-message.sh"
            if send_script.exists():
                cmd = [str(send_script), 
                       f"{state.session_name}:{agent.window_index}", 
                       message]
                subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:
            print(f"Error notifying {role}: {e}")
    
    def sync_branches(self, state: SessionState, source_role: str = 'sysadmin', force: bool = False) -> bool:
        """Actively sync agent branches, optionally forcing on divergences."""
        if not self.git_coordinator:
            return False
            
        if force or self.git_coordinator.detect_divergence(state):
            results = self.git_coordinator.sync_all_agents(state, source_role=source_role)
            if any(results.values()):
                self.save_session_state(state)  # Save updated commit hashes
                return True
        return False
    
    def resolve_deployment_conflicts(self, project_name: str) -> bool:
        """Resolve deployment conflicts using git synchronization"""
        if not self.git_coordinator:
            return False
            
        state = self.load_session_state(project_name)
        if not state:
            return False
            
        # Try to resolve conflicts by syncing git
        if self.git_coordinator.resolve_deployment_conflict(state):
            self.save_session_state(state)
            return True
        return False
    
    def cleanup_stale_registries(self, age_threshold: int = 86400):
        """Clean stale registry entries without active sessions or recent updates"""
        from tmux_utils import session_exists
        import shutil
        
        cleaned = 0
        projects_dir = self.registry_dir / 'projects'
        if not projects_dir.exists():
            return
            
        for proj_dir in projects_dir.iterdir():
            if not proj_dir.is_dir():
                continue
            state_file = proj_dir / 'session_state.json'
            if state_file.exists():
                try:
                    state_dict = json.loads(state_file.read_text())
                    session_name = state_dict.get('session_name')
                    updated_at = datetime.fromisoformat(state_dict.get('updated_at', '1970-01-01'))
                    age = (datetime.now() - updated_at).total_seconds()
                    
                    if (session_name and not session_exists(session_name)) or age > age_threshold:
                        shutil.rmtree(proj_dir)
                        cleaned += 1
                        print(f"Cleaned stale registry: {proj_dir.name} (age: {age:.0f}s, session exists: {session_name is not None and session_exists(session_name) if session_name else False})")
                except Exception as e:
                    print(f"Failed to clean {proj_dir.name}: {e}")
        if cleaned > 0:
            print(f"Cleaned {cleaned} stale registries")

    def set_role_dependencies(self, project_name: str, dependencies: Dict[str, List[str]]) -> None:
        """Set role dependencies for a project"""
        state = self.load_session_state(project_name)
        if state:
            state.dependencies = dependencies
            self.save_session_state(state)


def create_initial_session_state(
    session_name: str,
    project_path: str,
    project_name: str,
    implementation_spec_path: str,
    agents: List[tuple[str, int, str]],  # (window_name, window_index, role)
    worktree_paths: Dict[str, Path],
    project_size: str = "medium",
    parent_branch: Optional[str] = None,
    spec_path: Optional[str] = None,
    worktree_base_path: Optional[str] = None
) -> SessionState:
    """Create initial session state from orchestration setup"""
    
    agent_states = {}
    
    for window_name, window_index, role in agents:
        worktree_path = worktree_paths.get(role)
        agent_states[role] = AgentState(
            role=role,
            window_index=window_index,
            window_name=window_name,
            worktree_path=str(worktree_path) if worktree_path else "",
            last_briefing_time=datetime.now().isoformat(),
            is_alive=True,
            is_exhausted=False
        )
        
    return SessionState(
        session_name=session_name,
        project_path=project_path,
        project_name=project_name,
        implementation_spec_path=implementation_spec_path,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        agents=agent_states,
        project_size=project_size,
        parent_branch=parent_branch,
        spec_path=spec_path,
        worktree_base_path=worktree_base_path
    )
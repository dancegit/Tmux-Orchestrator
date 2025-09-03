"""
Agent Factory Module

Handles agent creation, deployment, and configuration. This module provides
centralized agent management with role-specific configuration and dynamic
team composition capabilities.
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from rich.console import Console

from ..core.session_manager import AgentState, SessionState
from ..claude.initialization import ClaudeInitializer

console = Console()


@dataclass
class RoleConfig:
    """Configuration for a specific agent role."""
    responsibilities: List[str]
    check_in_interval: int
    initial_commands: List[str]
    window_name: Optional[str] = None
    mcp_tools: List[str] = None
    
    def __post_init__(self):
        if self.mcp_tools is None:
            self.mcp_tools = []


class AgentIdManager:
    """Manages agent identification using session:window format for multi-window tmux architecture."""
    
    def __init__(self, session_name: str):
        self.session_name = session_name
        self.id_cache = {}  # role -> 'session:window'
    
    def get_agent_id(self, role: str, window_index: int) -> str:
        """Get agent ID in session:window format."""
        agent_id = f"{self.session_name}:{window_index}"
        self.id_cache[role] = agent_id
        return agent_id
    
    def get_cached_id(self, role: str) -> Optional[str]:
        """Get cached agent ID for a role."""
        return self.id_cache.get(role)


class AgentFactory:
    """
    Factory for creating and deploying agents in the orchestration system.
    
    Provides functionality for:
    - Dynamic role configuration based on project type
    - Agent deployment to tmux windows
    - Role-specific briefing generation
    - Team composition management
    - Agent lifecycle management
    """
    
    def __init__(self, tmux_orchestrator_path: Path):
        """
        Initialize agent factory.
        
        Args:
            tmux_orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.claude_initializer = ClaudeInitializer()
        
        # Standard role configurations
        self.role_configs = self._initialize_role_configs()
    
    def create_agent_state(self,
                          role: str,
                          window_index: int,
                          worktree_path: Path,
                          session_name: str,
                          custom_config: Optional[RoleConfig] = None) -> AgentState:
        """
        Create an agent state for a specific role.
        
        Args:
            role: Agent role (e.g., 'developer', 'tester')
            window_index: Tmux window index
            worktree_path: Path to agent's worktree
            session_name: Session name for ID generation
            custom_config: Optional custom role configuration
            
        Returns:
            AgentState: Configured agent state
        """
        config = custom_config or self.role_configs.get(role, self._get_default_role_config(role))
        window_name = config.window_name or role.title()
        
        agent_state = AgentState(
            role=role,
            window_index=window_index,
            window_name=window_name,
            worktree_path=str(worktree_path),
            current_branch='main'  # Default branch
        )
        
        console.print(f"[green]✓ Created agent state for {role} at window {window_index}[/green]")
        return agent_state
    
    def deploy_agent(self,
                    session_name: str,
                    agent_state: AgentState,
                    role_config: RoleConfig,
                    enable_mcp: bool = True) -> bool:
        """
        Deploy an agent to a tmux window.
        
        Args:
            session_name: Tmux session name
            agent_state: Agent state configuration
            role_config: Role configuration
            enable_mcp: Whether to enable MCP initialization
            
        Returns:
            bool: True if deployment succeeded
        """
        console.print(f"[blue]🚀 Deploying {agent_state.role} to {session_name}:{agent_state.window_index}[/blue]")
        
        try:
            # Create tmux window
            success = self._create_tmux_window(session_name, agent_state)
            if not success:
                return False
            
            # Initialize Claude with MCP if enabled
            if enable_mcp:
                worktree_path = Path(agent_state.worktree_path)
                if (worktree_path / '.mcp.json').exists():
                    success = self.claude_initializer.initialize_claude_with_mcp(
                        session_name=session_name,
                        window_idx=agent_state.window_index,
                        role_key=agent_state.role
                    )
                    if not success:
                        console.print(f"[yellow]Warning: MCP initialization failed for {agent_state.role}[/yellow]")
                        # Fall back to simple Claude start
                        self.claude_initializer.simple_claude_start(session_name, agent_state.window_index)
                else:
                    # No MCP config, start Claude normally
                    self.claude_initializer.simple_claude_start(session_name, agent_state.window_index)
            else:
                # Start Claude without MCP
                self.claude_initializer.simple_claude_start(session_name, agent_state.window_index)
            
            console.print(f"[green]✅ Successfully deployed {agent_state.role}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Failed to deploy {agent_state.role}: {e}[/red]")
            return False
    
    def deploy_team(self,
                   session_name: str,
                   agents: Dict[str, AgentState],
                   role_configs: Dict[str, RoleConfig]) -> Dict[str, bool]:
        """
        Deploy multiple agents as a coordinated team.
        
        Args:
            session_name: Tmux session name
            agents: Dict of role -> AgentState
            role_configs: Dict of role -> RoleConfig
            
        Returns:
            Dict of role -> deployment success status
        """
        console.print(f"[blue]🚀 Deploying team of {len(agents)} agents[/blue]")
        
        deployment_results = {}
        
        # Deploy agents in dependency order (orchestrator first, then others)
        deployment_order = self._get_deployment_order(list(agents.keys()))
        
        for role in deployment_order:
            if role in agents:
                agent_state = agents[role]
                role_config = role_configs.get(role, self._get_default_role_config(role))
                
                success = self.deploy_agent(
                    session_name=session_name,
                    agent_state=agent_state,
                    role_config=role_config
                )
                deployment_results[role] = success
                
                if success:
                    # Small delay between deployments to avoid OAuth conflicts
                    time.sleep(2)
                else:
                    console.print(f"[red]❌ Failed to deploy {role}, continuing with remaining agents[/red]")
        
        successful_deployments = sum(1 for success in deployment_results.values() if success)
        console.print(f"[green]✅ Team deployment complete: {successful_deployments}/{len(agents)} agents deployed[/green]")
        
        return deployment_results
    
    def restart_agent(self,
                     session_name: str,
                     agent_state: AgentState,
                     role_config: Optional[RoleConfig] = None) -> bool:
        """
        Restart a failed or unresponsive agent.
        
        Args:
            session_name: Tmux session name
            agent_state: Agent state to restart
            role_config: Optional role configuration
            
        Returns:
            bool: True if restart succeeded
        """
        console.print(f"[yellow]🔄 Restarting {agent_state.role} agent[/yellow]")
        
        try:
            # Use Claude initializer for proper OAuth-managed restart
            success = self.claude_initializer.restart_claude_in_window(
                session_name=session_name,
                window_idx=agent_state.window_index,
                window_name=agent_state.window_name,
                worktree_path=agent_state.worktree_path
            )
            
            if success:
                # Update agent state
                agent_state.is_alive = True
                agent_state.is_exhausted = False
                console.print(f"[green]✅ Successfully restarted {agent_state.role}[/green]")
            else:
                console.print(f"[red]❌ Failed to restart {agent_state.role}[/red]")
            
            return success
            
        except Exception as e:
            console.print(f"[red]❌ Error restarting {agent_state.role}: {e}[/red]")
            return False
    
    def get_role_config(self, role: str) -> RoleConfig:
        """
        Get configuration for a specific role.
        
        Args:
            role: Role name
            
        Returns:
            RoleConfig: Configuration for the role
        """
        return self.role_configs.get(role, self._get_default_role_config(role))
    
    def get_available_roles(self) -> List[str]:
        """
        Get list of available agent roles.
        
        Returns:
            List of role names
        """
        return list(self.role_configs.keys())
    
    def get_roles_for_project_type(self, project_type: str, project_size: str = "medium") -> List[Tuple[str, str]]:
        """
        Get recommended roles for a project type.
        
        Args:
            project_type: Type of project (web_application, system_deployment, etc.)
            project_size: Size of project (small, medium, large)
            
        Returns:
            List of (role_name, role_type) tuples
        """
        # Base roles for all projects
        base_roles = [
            ("orchestrator", "orchestrator"),
            ("pm", "project_manager")
        ]
        
        # Project-specific roles
        if project_type == "web_application":
            base_roles.extend([
                ("developer", "developer"),
                ("tester", "tester"),
                ("testrunner", "testrunner")
            ])
            
            if project_size in ["large", "enterprise"]:
                base_roles.extend([
                    ("devops", "devops"),
                    ("researcher", "researcher")
                ])
        
        elif project_type == "system_deployment":
            base_roles.extend([
                ("sysadmin", "sysadmin"),
                ("devops", "devops"),
                ("securityops", "securityops")
            ])
            
            if project_size in ["large", "enterprise"]:
                base_roles.extend([
                    ("networkops", "networkops"),
                    ("monitoringops", "monitoringops"),
                    ("databaseops", "databaseops")
                ])
        
        elif project_type == "data_pipeline":
            base_roles.extend([
                ("developer", "developer"),
                ("databaseops", "databaseops"),
                ("devops", "devops")
            ])
            
            if project_size in ["large", "enterprise"]:
                base_roles.extend([
                    ("monitoringops", "monitoringops"),
                    ("researcher", "researcher")
                ])
        
        return base_roles
    
    def _create_tmux_window(self, session_name: str, agent_state: AgentState) -> bool:
        """Create a tmux window for the agent."""
        try:
            result = subprocess.run([
                'tmux', 'new-window', '-t', f'{session_name}:{agent_state.window_index}',
                '-n', agent_state.window_name, '-c', agent_state.worktree_path,
                '-d'  # Create in detached mode
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                console.print(f"[green]✓ Created tmux window for {agent_state.role}[/green]")
                return True
            else:
                console.print(f"[red]❌ Failed to create tmux window: {result.stderr}[/red]")
                return False
                
        except Exception as e:
            console.print(f"[red]❌ Error creating tmux window: {e}[/red]")
            return False
    
    def _get_deployment_order(self, roles: List[str]) -> List[str]:
        """Get the optimal deployment order for roles."""
        # Orchestrator should always be first
        ordered_roles = []
        
        if "orchestrator" in roles:
            ordered_roles.append("orchestrator")
        
        # PM should be early for coordination
        if "pm" in roles:
            ordered_roles.append("pm")
        
        # System roles that others might depend on
        system_roles = ["sysadmin", "devops", "securityops", "networkops"]
        for role in system_roles:
            if role in roles and role not in ordered_roles:
                ordered_roles.append(role)
        
        # Development roles
        dev_roles = ["developer", "tester", "testrunner", "researcher"]
        for role in dev_roles:
            if role in roles and role not in ordered_roles:
                ordered_roles.append(role)
        
        # Add any remaining roles
        for role in roles:
            if role not in ordered_roles:
                ordered_roles.append(role)
        
        return ordered_roles
    
    def _initialize_role_configs(self) -> Dict[str, RoleConfig]:
        """Initialize standard role configurations."""
        return {
            "orchestrator": RoleConfig(
                responsibilities=[
                    "High-level project coordination",
                    "Agent deployment and management", 
                    "Architecture decision making",
                    "Quality assurance oversight",
                    "Resource allocation and scheduling"
                ],
                check_in_interval=30,
                initial_commands=[],
                window_name="Orchestrator"
            ),
            "pm": RoleConfig(
                responsibilities=[
                    "Team coordination and communication",
                    "Quality standards enforcement",
                    "Progress tracking and reporting", 
                    "Risk management and mitigation",
                    "Git workflow management"
                ],
                check_in_interval=30,
                initial_commands=[],
                window_name="Project-Manager"
            ),
            "developer": RoleConfig(
                responsibilities=[
                    "Feature implementation",
                    "Code quality and testing",
                    "Architecture implementation",
                    "Documentation updates",
                    "Code reviews and collaboration"
                ],
                check_in_interval=45,
                initial_commands=[],
                window_name="Developer"
            ),
            "tester": RoleConfig(
                responsibilities=[
                    "Test suite creation and maintenance",
                    "Quality assurance testing",
                    "Test automation setup",
                    "Bug identification and reporting",
                    "Test coverage monitoring"
                ],
                check_in_interval=45,
                initial_commands=[],
                window_name="Tester"
            ),
            "testrunner": RoleConfig(
                responsibilities=[
                    "Automated test execution",
                    "Test result analysis and reporting",
                    "Performance test monitoring", 
                    "CI/CD test integration",
                    "Test infrastructure management"
                ],
                check_in_interval=60,
                initial_commands=[],
                window_name="TestRunner"
            ),
            "sysadmin": RoleConfig(
                responsibilities=[
                    "System configuration and setup",
                    "User and permission management",
                    "Service deployment and management",
                    "System monitoring and maintenance",
                    "Security implementation"
                ],
                check_in_interval=45,
                initial_commands=[],
                window_name="SysAdmin"
            ),
            "devops": RoleConfig(
                responsibilities=[
                    "Deployment automation",
                    "Infrastructure management",
                    "CI/CD pipeline setup",
                    "Container orchestration",
                    "Environment management"
                ],
                check_in_interval=45,
                initial_commands=[],
                window_name="DevOps"
            ),
            "securityops": RoleConfig(
                responsibilities=[
                    "Security hardening implementation",
                    "Access control configuration",
                    "Security monitoring setup",
                    "Compliance verification",
                    "Incident response preparation"
                ],
                check_in_interval=60,
                initial_commands=[],
                window_name="SecurityOps"
            )
        }
    
    def _get_default_role_config(self, role: str) -> RoleConfig:
        """Get default configuration for unknown roles."""
        return RoleConfig(
            responsibilities=[f"Perform {role} related tasks"],
            check_in_interval=45,
            initial_commands=[],
            window_name=role.title()
        )
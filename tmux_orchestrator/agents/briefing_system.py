"""
Briefing System Module

Handles generation of role-specific briefings for agents. This module creates
comprehensive briefings that include role responsibilities, project context,
team coordination information, and technical guidance.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from rich.console import Console

from .agent_factory import RoleConfig
from .module_loader import ModuleLoader
from ..claude.mcp_manager import MCPManager

console = Console()


@dataclass
class ProjectSpec:
    """Simplified project specification for briefing generation."""
    name: str
    path: str
    type: str
    main_tech: List[str]
    description: str = ""


@dataclass 
class BriefingContext:
    """Context information for generating agent briefings."""
    project_spec: ProjectSpec
    role_config: RoleConfig
    session_name: str
    worktree_path: Path
    team_members: List[Tuple[str, int]]  # (role, window_index) pairs
    git_branch: str = "main"
    enable_mcp: bool = True


class BriefingSystem:
    """
    Generates role-specific briefings for orchestration agents.
    
    Provides comprehensive briefings that include:
    - Role-specific responsibilities and guidance
    - Project context and technical details
    - Team coordination and communication protocols
    - MCP tools and available capabilities
    - Git workflow and worktree instructions
    - Completion reporting protocols
    """
    
    def __init__(self, tmux_orchestrator_path: Path):
        """
        Initialize briefing system.
        
        Args:
            tmux_orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.mcp_manager = MCPManager()
        
        # Initialize module loader for modularized CLAUDE knowledge base
        modules_path = tmux_orchestrator_path / 'docs' / 'claude_modules'
        self.module_loader = ModuleLoader(modules_path)
    
    def generate_role_briefing(self, context: BriefingContext) -> str:
        """
        Generate a comprehensive briefing for a specific role.
        
        Args:
            context: Briefing context with project and role information
            
        Returns:
            str: Complete briefing text for the agent
        """
        role = context.role_config.window_name or "Agent"
        
        console.print(f"[cyan]Generating briefing for {role}[/cyan]")
        
        # Build briefing components
        components = []
        
        # Header and context
        components.append(self._create_briefing_header(context))
        
        # Role-specific briefing based on role type
        role_key = context.role_config.window_name.lower().replace('-', '_') if context.role_config.window_name else "generic"
        
        if role_key == "orchestrator":
            components.append(self._create_orchestrator_briefing(context))
        elif role_key == "project_manager":
            components.append(self._create_pm_briefing(context))
        elif role_key == "developer":
            components.append(self._create_developer_briefing(context))
        elif role_key == "tester":
            components.append(self._create_tester_briefing(context))
        elif role_key == "testrunner":
            components.append(self._create_testrunner_briefing(context))
        elif role_key == "sysadmin":
            components.append(self._create_sysadmin_briefing(context))
        elif role_key == "devops":
            components.append(self._create_devops_briefing(context))
        elif role_key == "securityops":
            components.append(self._create_securityops_briefing(context))
        else:
            components.append(self._create_generic_briefing(context))
        
        # Add modular CLAUDE knowledge base content
        try:
            role_modules = self.module_loader.load_for_role(role_key)
            if not role_modules.get('legacy_notice'):  # Only add if not in legacy mode
                module_context = self.module_loader.format_role_context(role_modules)
                if module_context:
                    components.append("📖 **Knowledge Base Context**:\n" + module_context)
            
            # Add module references for the agent
            module_refs = self.module_loader.get_module_reference(role_key)
            components.append(module_refs)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load modular knowledge base: {e}[/yellow]")
            # Fall back to suggesting CLAUDE.md
            components.append("📚 **Reference**: Read CLAUDE.md for detailed instructions (if available)")
        
        # Common footer components
        components.append(self._create_communication_channels(context))
        components.append(self._create_completion_protocol(context))
        components.append(self._create_technical_guidance(context))
        
        briefing = "\n\n".join(components)
        
        console.print(f"[green]✓ Generated {len(briefing)} character briefing for {role}[/green]")
        return briefing
    
    def _create_briefing_header(self, context: BriefingContext) -> str:
        """Create briefing header with project context."""
        role_name = context.role_config.window_name or "Agent"
        
        # MCP tools information
        mcp_info = ""
        if context.enable_mcp:
            mcp_info = self.mcp_manager.get_mcp_tools_info(role_name.lower())
        
        # Check for context-prime support and add guidance
        context_prime_guidance = ""
        context_prime_path = Path(context.project_spec.path) / '.claude' / 'commands' / 'context-prime.md'
        if context_prime_path.exists():
            context_prime_guidance = """
📚 **Project Context Loading**:
Run `/context-prime` to load full project context into your session.
This provides comprehensive understanding of the codebase structure and conventions.
"""
        else:
            context_prime_guidance = """
📚 **Project Context Loading**:
Since context-prime.md is not available, please familiarize yourself with the project by:

1. **Read essential documentation** (use the Read tool):
   - README.md - Project overview and setup instructions
   - docs/claude_modules/index.md - Modular knowledge base index
   - Any docs/ directory content
   
2. **Understand project structure**:
   ```bash
   # List main directories
   ls -la
   
   # Check for dependency files
   find . -maxdepth 2 -name "package.json" -o -name "requirements.txt" -o -name "pyproject.toml" -o -name "go.mod" 2>/dev/null
   
   # Identify main source directories
   ls -la src/ app/ lib/ pkg/ 2>/dev/null
   ```

3. **Review existing code patterns**:
   - Check a few existing files to understand coding style
   - Look for configuration files (.env.example, config/, settings/)
   - Identify testing patterns (test/, tests/, __tests__/)

⚠️ Take 2-3 minutes to understand the project before starting implementation.
"""
        
        return f"""📋 **{role_name} Briefing - {context.project_spec.name}**

🎯 **Project Context**:
- Name: {context.project_spec.name}
- Type: {context.project_spec.type}
- Technologies: {', '.join(context.project_spec.main_tech)}
- Path: {context.project_spec.path}

🏢 **Your Workspace**:
- Worktree: {context.worktree_path}
- Session: {context.session_name}
- Branch: {context.git_branch}
{context_prime_guidance}
{mcp_info}

📋 **Your Responsibilities**:
{chr(10).join(f'- {r}' for r in context.role_config.responsibilities)}"""
    
    def _create_orchestrator_briefing(self, context: BriefingContext) -> str:
        """Create orchestrator-specific briefing."""
        return f"""🚀 **ORCHESTRATOR ROLE ACTIVATION**

**DUAL DIRECTORY OPERATION**:
- **Project Work**: Create project files in your worktree: `{context.worktree_path}`
- **Tool Operations**: Run orchestrator tools from: `{self.tmux_orchestrator_path}`

**CRITICAL ORCHESTRATOR TASKS**:
1. **Agent Management**: Monitor and coordinate all team members
2. **Quality Oversight**: Ensure project standards are maintained
3. **Resource Allocation**: Manage system resources and priorities
4. **Architecture Decisions**: Make high-level technical decisions
5. **Problem Resolution**: Resolve blockers and conflicts

**TOOL ACCESS**:
```bash
# Switch to tool directory for orchestrator operations
cd {self.tmux_orchestrator_path}

# Example tool usage
./send-claude-message.sh {context.session_name}:1 "Status update please"
./schedule_with_note.sh 30 "Team check-in" "{context.session_name}:0"

# Return to project worktree for project work
cd {context.worktree_path}
```

**⚡ IMMEDIATE PRIORITIES**:
1. Create team overview and project documentation
2. Set up monitoring for all agents
3. Establish regular check-in schedule
4. Begin high-level project coordination"""
    
    def _create_pm_briefing(self, context: BriefingContext) -> str:
        """Create project manager-specific briefing."""
        return f"""📊 **PROJECT MANAGER ROLE ACTIVATION**

🎯 **COORDINATE WITHOUT BLOCKING**: Assume teams are authorized to start; focus on collecting reports, not granting permissions

**CORE RESPONSIBILITIES**:
1. **Quality Standards**: Maintain exceptionally high quality without compromising speed
2. **Team Coordination**: Collect status reports and coordinate between agents
3. **Git Workflow**: Manage branch integration and merge coordination
4. **Progress Tracking**: Monitor project velocity and identify blockers
5. **Risk Management**: Proactively identify and mitigate risks

**GIT INTEGRATION PROTOCOL**:
```bash
# Daily integration workflow
git fetch --all
git checkout integration
git merge origin/developer-branch --no-ff
git merge origin/tester-branch --no-ff

# After successful integration
git push origin integration
```

**⚡ IMMEDIATE TASKS**:
1. Set up project tracking and quality metrics
2. Establish team communication protocols
3. Begin collecting initial status reports
4. Create integration branch for team coordination"""
    
    def _create_developer_briefing(self, context: BriefingContext) -> str:
        """Create developer-specific briefing."""
        return f"""💻 **DEVELOPER ROLE ACTIVATION**

🚀 **AUTONOMY FIRST**: Begin implementation IMMEDIATELY without waiting for approvals

**DEVELOPMENT PROTOCOL**:
1. **Immediate Start**: Begin coding within 2 minutes of reading this briefing
2. **Autonomous Implementation**: Full authorization to write production code
3. **Regular Commits**: Commit progress every 30 minutes
4. **Quality Focus**: Follow best practices and existing code patterns
5. **Test Integration**: Work closely with Tester for quality assurance

**TECHNICAL SETUP**:
```bash
# Verify project setup
pwd  # Should be in: {context.worktree_path}
git status
git branch --show-current

# Check project dependencies
ls -la package.json requirements.txt pyproject.toml 2>/dev/null || echo "No standard dependency files found"
```

**⚡ IMMEDIATE TASKS**:
1. Analyze existing codebase and architecture
2. Identify highest priority implementation tasks
3. Begin feature implementation following project patterns
4. Set up development environment and tools"""
    
    def _create_tester_briefing(self, context: BriefingContext) -> str:
        """Create tester-specific briefing."""
        return f"""🧪 **TESTER ROLE ACTIVATION**

⚡ **START TESTING NOW**: Begin test creation within 2 minutes of reading this briefing

**TESTING PROTOCOL**:
1. **Autonomous Testing**: Full authorization to create and execute tests
2. **Comprehensive Coverage**: Unit, integration, and E2E testing
3. **Quality Assurance**: Verify all success criteria are met
4. **Collaboration**: Work directly with Developer through git
5. **Continuous Testing**: Run tests after each development iteration

**TESTING SETUP**:
```bash
# Test environment setup
pwd  # Should be in: {context.worktree_path}
mkdir -p tests/{{unit,integration,e2e}}

# Check existing test infrastructure
find . -name "*test*" -type f | head -10
ls -la test/ tests/ __tests__/ spec/ 2>/dev/null || echo "No existing test directories"
```

**⚡ IMMEDIATE TASKS**:
1. Analyze existing test structure and coverage
2. Create comprehensive test plan
3. Begin writing test suites for core functionality
4. Set up automated test execution pipeline"""
    
    def _create_testrunner_briefing(self, context: BriefingContext) -> str:
        """Create test runner-specific briefing."""
        return f"""⚙️ **TEST RUNNER ROLE ACTIVATION**

**TEST EXECUTION FOCUS**:
1. **Automated Execution**: Run test suites continuously and efficiently
2. **Result Analysis**: Analyze test results and identify patterns
3. **Performance Monitoring**: Track test execution performance
4. **Infrastructure Management**: Maintain test execution environment
5. **Reporting**: Provide detailed test result reports to team

**EXECUTION SETUP**:
```bash
# Test execution environment
pwd  # Should be in: {context.worktree_path}

# Set up parallel test execution
# Check for test frameworks
which pytest jest npm mocha 2>/dev/null || echo "Test frameworks not found"
```

**⚡ IMMEDIATE TASKS**:
1. Set up automated test execution framework
2. Configure parallel test runners for efficiency
3. Establish baseline test metrics
4. Create test result reporting system"""
    
    def _create_sysadmin_briefing(self, context: BriefingContext) -> str:
        """Create system administrator-specific briefing."""
        return f"""🔧 **SYSTEM ADMINISTRATOR ROLE ACTIVATION**

**SYSTEM MANAGEMENT FOCUS**:
1. **System Configuration**: Set up and configure target systems
2. **User Management**: Create and manage system users and groups
3. **Service Management**: Configure and deploy system services
4. **Security Implementation**: Apply system-level security measures
5. **Resource Management**: Monitor and optimize system resources

**SYSTEM SETUP**:
```bash
# System verification
whoami
sudo -l  # Check sudo privileges
systemctl --version  # Check systemd availability
```

**⚡ IMMEDIATE TASKS**:
1. Verify system prerequisites and access
2. Review deployment specifications and requirements
3. Begin base system configuration
4. Coordinate with SecurityOps for hardening requirements"""
    
    def _create_devops_briefing(self, context: BriefingContext) -> str:
        """Create DevOps-specific briefing."""
        return f"""🚀 **DEVOPS ROLE ACTIVATION**

**DEPLOYMENT AUTOMATION FOCUS**:
1. **Infrastructure Management**: Set up and manage deployment infrastructure
2. **CI/CD Pipelines**: Create automated deployment pipelines
3. **Container Orchestration**: Manage Docker/Kubernetes deployments
4. **Environment Management**: Configure staging and production environments
5. **Monitoring Integration**: Set up deployment monitoring and alerting

**DEVOPS SETUP**:
```bash
# Infrastructure verification
docker --version 2>/dev/null || echo "Docker not available"
kubectl version --client 2>/dev/null || echo "Kubernetes not available"
terraform --version 2>/dev/null || echo "Terraform not available"
```

**⚡ IMMEDIATE TASKS**:
1. Analyze deployment requirements and infrastructure needs
2. Set up deployment automation tools
3. Create environment-specific configurations
4. Coordinate with SysAdmin for system-level requirements"""
    
    def _create_securityops_briefing(self, context: BriefingContext) -> str:
        """Create SecurityOps-specific briefing."""
        return f"""🔒 **SECURITY OPERATIONS ROLE ACTIVATION**

**SECURITY HARDENING FOCUS**:
1. **System Hardening**: Implement security best practices
2. **Access Control**: Configure authentication and authorization
3. **Network Security**: Set up firewall and network policies
4. **Monitoring**: Implement security monitoring and alerting
5. **Compliance**: Ensure security standards compliance

**SECURITY SETUP**:
```bash
# Security tool verification
ufw --version 2>/dev/null || echo "UFW not available"
fail2ban-client version 2>/dev/null || echo "Fail2ban not available"
aa-status 2>/dev/null || echo "AppArmor not available"
```

**⚡ IMMEDIATE TASKS**:
1. Assess current security posture
2. Implement baseline security hardening
3. Configure access controls and policies
4. Set up security monitoring and alerting"""
    
    def _create_generic_briefing(self, context: BriefingContext) -> str:
        """Create generic briefing for unknown roles."""
        return f"""⚡ **ROLE ACTIVATION**

**GENERAL PROTOCOL**:
1. **Autonomous Operation**: Begin work immediately without waiting for approvals
2. **Regular Communication**: Report progress and blockers to team
3. **Quality Focus**: Maintain high standards in all work
4. **Collaboration**: Coordinate with team members as needed
5. **Documentation**: Document decisions and progress

**⚡ IMMEDIATE TASKS**:
1. Analyze role requirements and project context
2. Set up necessary tools and environment
3. Begin primary role responsibilities
4. Establish communication with team members"""
    
    def _create_communication_channels(self, context: BriefingContext) -> str:
        """Create communication channels reference."""
        if not context.team_members:
            return "📡 **Team Communication**: Single-agent setup, no team coordination needed."
        
        channels = "📡 **CRITICAL: Team Communication Channels**\n\n"
        channels += "| Role | Window | Command |\n"
        channels += "|------|--------|----------|\n"
        
        for role, window_idx in context.team_members:
            role_name = role.title().replace('_', '-')
            channels += f"| {role_name} | {window_idx} | `scm {context.session_name}:{window_idx} \"message\"` |\n"
        
        channels += "\n**Communication Rules**:\n"
        channels += "- ✅ Use `scm` command for all inter-agent messaging\n"
        channels += "- ✅ Report all completions to Orchestrator immediately\n"
        channels += "- ✅ Coordinate through Project Manager for complex integration\n"
        
        return channels
    
    def _create_completion_protocol(self, context: BriefingContext) -> str:
        """Create completion reporting protocol."""
        return f"""🎯 **COMPLETION PROTOCOL (MANDATORY)**

**When you complete any significant task:**
1. **Create marker file**: `echo "TASK COMPLETED\\nRole: {context.role_config.window_name}\\nTime: $(date)\\nDetails: [task description]" > COMPLETED`
2. **Commit marker**: `git add COMPLETED && git commit -m "completion: task complete"`  
3. **Report to team**: Use communication channels to notify relevant team members
4. **Update status**: Document completion in your progress tracking

**⚠️ CRITICAL**: Completion reporting is MANDATORY - unreported work doesn't count toward project success."""
    
    def _create_technical_guidance(self, context: BriefingContext) -> str:
        """Create technical guidance and best practices."""
        return f"""🛠️ **Technical Guidance**

**Git Workflow**:
```bash
# Regular workflow
git add -A
git commit -m "descriptive commit message" 
git push origin {context.git_branch}

# Check status
git status
git log --oneline -5
```

**File Operations**:
- Work in your worktree: `{context.worktree_path}`
- Access main project via: `./shared/main-project/` (if available)
- Create role-specific directories for organization

**Check-in Schedule**:
- Regular check-ins every {context.role_config.check_in_interval} minutes
- Report blockers immediately
- Update progress continuously

**Quality Standards**:
- Follow existing code patterns and conventions
- Test all changes thoroughly
- Document important decisions
- Maintain clean, readable code"""
#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click",
#     "rich",
#     "pydantic",
# ]
# ///

"""
Auto-Orchestrate: Automated Tmux Orchestrator Setup
Analyzes a specification file and automatically sets up a complete
tmux orchestration environment with Orchestrator, PM, Developer, and Tester.
"""

import subprocess
import json
import sys
import os
import time
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import tempfile

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.json import JSON
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from pydantic import BaseModel, Field

console = Console()

# Pydantic models for structured data
class Phase(BaseModel):
    name: str
    duration_hours: float
    tasks: List[str]

class ImplementationPlan(BaseModel):
    phases: List[Phase]
    total_estimated_hours: float

class RoleConfig(BaseModel):
    responsibilities: List[str]
    check_in_interval: int
    initial_commands: List[str]

class Project(BaseModel):
    name: str
    path: str
    type: str
    main_tech: List[str]

class GitWorkflow(BaseModel):
    parent_branch: str = "main"  # The branch we started from
    branch_name: str
    commit_interval: int
    pr_title: str

class ProjectSize(BaseModel):
    size: str = Field(default="medium", description="small|medium|large")
    estimated_loc: int = Field(default=1000)
    complexity: str = Field(default="medium")

class ImplementationSpec(BaseModel):
    project: Project
    implementation_plan: ImplementationPlan
    roles: Dict[str, RoleConfig]
    git_workflow: GitWorkflow
    success_criteria: List[str]
    project_size: ProjectSize = Field(default_factory=ProjectSize)


class AutoOrchestrator:
    def __init__(self, project_path: str, spec_path: str):
        self.project_path = Path(project_path).resolve()
        self.spec_path = Path(spec_path).resolve()
        self.tmux_orchestrator_path = Path(__file__).parent
        self.implementation_spec: Optional[ImplementationSpec] = None
        self.manual_size: Optional[str] = None
        self.additional_roles: List[str] = []
        self.force: bool = False
        self.plan_type: str = 'max20'  # Default to Max 20x plan
        
    def ensure_setup(self):
        """Ensure Tmux Orchestrator is properly set up"""
        console.print("[cyan]Checking Tmux Orchestrator setup...[/cyan]")
        
        # Check if config.local.sh exists
        config_local = self.tmux_orchestrator_path / 'config.local.sh'
        if not config_local.exists():
            console.print("[yellow]Running initial setup...[/yellow]")
            
            # Run setup.sh
            setup_script = self.tmux_orchestrator_path / 'setup.sh'
            if setup_script.exists():
                # Make it executable
                os.chmod(setup_script, 0o755)
                
                # Run setup non-interactively
                env = os.environ.copy()
                env['PROJECTS_DIR'] = str(Path.home() / 'projects')
                
                result = subprocess.run(
                    ['bash', '-c', f'cd "{self.tmux_orchestrator_path}" && echo -e "y\\n" | ./setup.sh'],
                    capture_output=True,
                    text=True,
                    env=env
                )
                
                if result.returncode != 0:
                    console.print(f"[yellow]Setup had warnings: {result.stderr}[/yellow]")
            else:
                # Create config.local.sh manually
                config_sh = self.tmux_orchestrator_path / 'config.sh'
                if config_sh.exists():
                    import shutil
                    shutil.copy(config_sh, config_local)
                    console.print("[green]✓ Created config.local.sh[/green]")
        
        # Ensure registry directories exist
        registry_dir = self.tmux_orchestrator_path / 'registry'
        for subdir in ['logs', 'notes', 'projects']:
            (registry_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        # Make all scripts executable
        for script in self.tmux_orchestrator_path.glob('*.sh'):
            os.chmod(script, 0o755)
        for script in self.tmux_orchestrator_path.glob('*.py'):
            os.chmod(script, 0o755)
        
        console.print("[green]✓ Tmux Orchestrator setup complete[/green]")
    
    def check_dependencies(self):
        """Check that all required dependencies are available"""
        errors = []
        warnings = []
        
        # Check tmux
        tmux_result = subprocess.run(['which', 'tmux'], capture_output=True)
        if tmux_result.returncode != 0:
            errors.append("tmux is not installed. Install with: sudo apt install tmux (Linux) or brew install tmux (macOS)")
        
        # Check Claude CLI - use full path
        claude_path = '/usr/bin/claude'
        if not Path(claude_path).exists():
            # Fallback to which
            claude_result = subprocess.run(['which', 'claude'], capture_output=True, text=True)
            if claude_result.returncode != 0:
                errors.append("Claude Code is not installed. Visit https://claude.ai/code for installation instructions")
            else:
                claude_path = claude_result.stdout.strip()
        
        # Check Python
        python_result = subprocess.run(['which', 'python3'], capture_output=True)
        if python_result.returncode != 0:
            warnings.append("Python 3 is not installed. Some features may not work")
        
        # Check UV (optional but recommended)
        uv_result = subprocess.run(['which', 'uv'], capture_output=True)
        if uv_result.returncode != 0:
            warnings.append("UV is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh")
        
        # Check if send-claude-message.sh exists
        if not (self.tmux_orchestrator_path / 'send-claude-message.sh').exists():
            errors.append("send-claude-message.sh not found in Tmux Orchestrator directory")
        
        # Check if schedule_with_note.sh exists
        if not (self.tmux_orchestrator_path / 'schedule_with_note.sh').exists():
            errors.append("schedule_with_note.sh not found in Tmux Orchestrator directory")
        
        # Display results
        if errors:
            console.print("\n[red]❌ Critical dependencies missing:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            console.print("\n[red]Please install missing dependencies before continuing.[/red]")
            sys.exit(1)
        
        if warnings:
            console.print("\n[yellow]⚠️  Optional dependencies:[/yellow]")
            for warning in warnings:
                console.print(f"  • {warning}")
        
        console.print("\n[green]✓ All required dependencies are installed[/green]")
    
    def ensure_tmux_server(self):
        """Ensure tmux is ready to use"""
        console.print("[cyan]Checking tmux availability...[/cyan]")
        
        # Check if tmux server is running by trying to list sessions
        result = subprocess.run(['tmux', 'list-sessions'], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            # Server not running - this is fine, it will start when we create a session
            if "no server running" in result.stderr.lower() or "error connecting" in result.stderr.lower():
                console.print("[yellow]Tmux server not currently running (will start automatically)[/yellow]")
            else:
                # Some other error - this might be a problem
                console.print(f"[yellow]Tmux returned an error: {result.stderr}[/yellow]")
                
            # Start tmux server by creating a persistent background session
            console.print("[cyan]Starting tmux server...[/cyan]")
            
            # Check if our background session already exists
            check_result = subprocess.run([
                'tmux', 'has-session', '-t', 'tmux-orchestrator-server'
            ], capture_output=True)
            
            if check_result.returncode != 0:
                # Create a persistent background session to keep server running
                start_result = subprocess.run([
                    'tmux', 'new-session', '-d', '-s', 'tmux-orchestrator-server', 
                    '-n', 'server', 'echo "Tmux Orchestrator Server - Keep this session running"; sleep infinity'
                ], capture_output=True, text=True)
                
                if start_result.returncode == 0:
                    console.print("[green]✓ Tmux server started with persistent session 'tmux-orchestrator-server'[/green]")
                else:
                    console.print(f"[red]Failed to start tmux server: {start_result.stderr}[/red]")
                    console.print("[red]Please ensure tmux is properly installed and configured[/red]")
                    sys.exit(1)
            else:
                console.print("[green]✓ Tmux server already has orchestrator session[/green]")
        else:
            console.print("[green]✓ Tmux server is running with existing sessions[/green]")
            if result.stdout.strip():
                # Show first few sessions
                sessions = result.stdout.strip().split('\n')[:3]
                for session in sessions:
                    console.print(f"   • {session}")
                if len(result.stdout.strip().split('\n')) > 3:
                    console.print(f"   • ... and {len(result.stdout.strip().split('\n')) - 3} more sessions")
    
    def get_current_git_branch(self) -> Optional[str]:
        """Get the current git branch of the project"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=str(self.project_path)
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except:
            return None
    
    def get_claude_version(self) -> Optional[str]:
        """Get the Claude CLI version"""
        try:
            # Use full path to avoid Python packages
            result = subprocess.run(['/usr/bin/claude', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                # Parse version from output like "1.0.56 (Claude Code)" or "claude version 1.0.22"
                version_line = result.stdout.strip()
                
                # Try to extract version number using regex
                import re
                version_match = re.search(r'(\d+\.\d+\.\d+)', version_line)
                if version_match:
                    return version_match.group(1)
                
                # Fallback to old parsing method
                parts = version_line.split()
                if len(parts) >= 3:
                    return parts[2]
            return None
        except:
            return None
    
    def check_claude_version(self) -> bool:
        """Check if Claude version supports context priming"""
        version = self.get_claude_version()
        if not version:
            return False
        
        try:
            # Parse version string like "1.0.22"
            parts = version.split('.')
            if len(parts) >= 3:
                major = int(parts[0])
                minor = int(parts[1])
                patch = int(parts[2])
                
                # Context priming requires 1.0.24 or higher
                if major > 1:
                    return True
                if major == 1 and minor > 0:
                    return True
                if major == 1 and minor == 0 and patch >= 24:
                    return True
            
            return False
        except:
            return False
        
    def analyze_spec_with_claude(self) -> Dict[str, Any]:
        """Use Claude to analyze the spec and generate implementation plan"""
        
        # Read the spec file
        spec_content = self.spec_path.read_text()
        
        # Try context priming - we'll attempt it and fall back if it fails
        supports_context_prime = True  # Assume it works and let it fail gracefully
        claude_version = self.get_claude_version()
        
        if claude_version:
            console.print(f"[cyan]Claude version detected: {claude_version}[/cyan]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            # Check if the project has a context-prime command
            context_prime_path = self.project_path / '.claude' / 'commands' / 'context-prime.md'
            supports_context_prime = context_prime_path.exists()
            
            if supports_context_prime:
                task = progress.add_task("Context priming and analyzing specification with Claude...", total=None)
            else:
                task = progress.add_task("Analyzing specification with Claude...", total=None)
                if self.project_path.exists():
                    console.print(f"[yellow]Note: No context-prime command found. To enable, create {context_prime_path.relative_to(Path.home()) if context_prime_path.is_relative_to(Path.home()) else context_prime_path}[/yellow]")
        
        # Detect current git branch
        current_branch = self.get_current_git_branch()
        if current_branch:
            console.print(f"[cyan]Current git branch: {current_branch}[/cyan]")
        else:
            current_branch = "main"  # Default if not in git repo
            console.print("[yellow]Not in a git repository, defaulting to 'main' branch[/yellow]")
        
        # Create a prompt for Claude
        if supports_context_prime:
            # Include context priming in the same session
            prompt = f"""/context-prime "Analyze the project at {self.project_path} to understand its structure, technologies, and conventions"

After analyzing the project context above, now analyze the following specification and create a detailed implementation plan in JSON format."""
        else:
            prompt = f"""You are an AI project planning assistant. Analyze the following specification for the project at {self.project_path} and create a detailed implementation plan in JSON format."""
        
        prompt += f"""

PROJECT PATH: {self.project_path}
CURRENT GIT BRANCH: {current_branch}
SPECIFICATION:
{spec_content}

Generate a JSON implementation plan with this EXACT structure:
{{
  "project": {{
    "name": "Project name from spec",
    "path": "{self.project_path}",
    "type": "python|javascript|go|etc",
    "main_tech": ["list", "of", "main", "technologies"]
  }},
  "implementation_plan": {{
    "phases": [
      {{
        "name": "Phase name",
        "duration_hours": 2.0,
        "tasks": ["Task 1", "Task 2", "Task 3"]
      }}
    ],
    "total_estimated_hours": 12.0
  }},
  "project_size": {{
    "size": "small|medium|large",
    "estimated_loc": 1000,
    "complexity": "low|medium|high"
  }},
  "roles": {{
    "orchestrator": {{
      "responsibilities": ["Monitor progress", "Coordinate roles", "Handle blockers"],
      "check_in_interval": 20,  # Reduced for better progression
      "initial_commands": ["cd {self.tmux_orchestrator_path}", "python3 claude_control.py status detailed"]
    }},
    "project_manager": {{
      "responsibilities": ["Ensure quality", "Track completion", "Review coverage"],
      "check_in_interval": 25,  # Reduced for better coordination
      "initial_commands": ["cd {self.project_path}", "cat {self.spec_path.relative_to(self.project_path) if self.spec_path.is_relative_to(self.project_path) else self.spec_path}"]
    }},
    "developer": {{
      "responsibilities": ["Implement features", "Write tests", "Fix bugs"],
      "check_in_interval": 30,  # Reduced for faster development cycles
      "initial_commands": ["cd {self.project_path}", "git status"]
    }},
    "tester": {{
      "responsibilities": ["Run tests", "Report failures", "Verify coverage"],
      "check_in_interval": 30,  # Reduced to match developer pace
      "initial_commands": ["cd {self.project_path}", "echo 'Ready to test'"]
    }},
    "testrunner": {{
      "responsibilities": ["Execute test suites", "Parallel test management", "Performance testing", "Test infrastructure", "Results analysis"],
      "check_in_interval": 30,  # Same as tester for coordination
      "initial_commands": ["cd {self.project_path}", "echo 'Setting up test execution framework'"]
    }},
    "logtracker": {{
      "responsibilities": ["Monitor logs real-time", "Track errors", "Alert critical issues", "Use project monitoring tools", "Generate error reports"],
      "check_in_interval": 15,  # Frequent checks for real-time monitoring
      "initial_commands": ["cd {self.project_path}", "mkdir -p monitoring/logs monitoring/reports", "echo 'Reading CLAUDE.md for monitoring instructions'"]
    }},
    "devops": {{
      "responsibilities": ["Infrastructure setup", "Deployment pipelines", "Monitor performance"],
      "check_in_interval": 45,  # Reduced but still longer as infra work is less frequent
      "initial_commands": ["cd {self.project_path}", "echo 'Checking deployment configuration'"]
    }},
    "code_reviewer": {{
      "responsibilities": ["Review code quality", "Security audit", "Best practices enforcement"],
      "check_in_interval": 40,  # Reduced to review code more frequently
      "initial_commands": ["cd {self.project_path}", "git log --oneline -10"]
    }},
    "researcher": {{
      "responsibilities": ["MCP tool discovery and utilization", "Research best practices", "Security vulnerability analysis", "Performance optimization research", "Document actionable findings"],
      "check_in_interval": 25,  # Reduced for timely research support
      "initial_commands": ["cd {self.project_path}", "mkdir -p research", "echo 'Type @ to discover MCP resources, / to discover MCP commands'", "echo 'Look for /mcp__ prefixed commands for MCP tools'"]
    }},
    "documentation_writer": {{
      "responsibilities": ["Write technical docs", "Update README", "Create API documentation"],
      "check_in_interval": 60,  # Still longer as docs are updated less frequently
      "initial_commands": ["cd {self.project_path}", "ls -la *.md"]
    }}
  }},
  "git_workflow": {{
    "parent_branch": "{current_branch}",
    "branch_name": "feature/implementation-branch",
    "commit_interval": 30,
    "pr_title": "Implementation title"
  }},
  "success_criteria": [
    "Criterion 1",
    "Criterion 2",
    "Criterion 3"
  ]
}}

IMPORTANT: 
- Analyze the spec carefully to understand what needs to be implemented
- Create realistic time estimates based on complexity
- Include specific, actionable tasks for each phase
- Determine project size based on scope and complexity:
  - Small: < 500 LOC, simple features, 1-2 days work
  - Medium: 500-5000 LOC, moderate complexity, 3-7 days work  
  - Large: > 5000 LOC, complex features, > 1 week work
- Include ALL roles in the JSON, but the orchestrator will decide which ones to actually deploy based on project size
- Ensure role responsibilities align with the implementation needs
- IMPORTANT: The parent_branch field MUST be set to "{current_branch}" as this is the branch we're currently on
- The feature branch will be created FROM this parent branch, not from main
- Output ONLY valid JSON, no other text"""

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing specification with Claude...", total=None)
            
            # Create a temporary file for the prompt
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                prompt_file = f.name
            
            try:
                # Use Claude Code with -p flag for non-interactive output
                # Read the prompt from file
                with open(prompt_file, 'r') as f:
                    prompt_content = f.read()
                
                # Try a simpler approach without -p flag
                # Write prompt to temporary file and use cat | claude approach
                import uuid
                prompt_script = f"""#!/bin/bash
cd "{self.project_path}"
cat << 'CLAUDE_EOF' | /usr/bin/claude --dangerously-skip-permissions
{prompt_content}

Please provide ONLY the JSON response, no other text.
CLAUDE_EOF
"""
                
                script_file = f"/tmp/claude_prompt_{uuid.uuid4().hex}.sh"
                with open(script_file, 'w') as f:
                    f.write(prompt_script)
                os.chmod(script_file, 0o755)
                
                try:
                    result = subprocess.run(
                        ['bash', script_file],
                        capture_output=True,
                        text=True,
                        timeout=360  # Increased timeout for combined context prime + analysis
                    )
                finally:
                    if os.path.exists(script_file):
                        os.unlink(script_file)
                
                if result.returncode != 0:
                    console.print(f"[red]Error running Claude: {result.stderr}[/red]")
                    console.print("\n[yellow]Debug info:[/yellow]")
                    console.print(f"Script file: {script_file}")
                    console.print(f"Exit code: {result.returncode}")
                    console.print("\n[yellow]You can try running the script manually to debug:[/yellow]")
                    console.print(f"   bash {script_file}")
                    sys.exit(1)
                
                # Extract JSON from Claude's response
                response = result.stdout.strip()
                
                # Try to find JSON in the response
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    return json.loads(json_str)
                else:
                    console.print("[red]Could not find valid JSON in Claude's response[/red]")
                    console.print(f"Response: {response}")
                    sys.exit(1)
                    
            finally:
                # Clean up temp file
                os.unlink(prompt_file)
    
    def display_implementation_plan(self, spec: ImplementationSpec) -> bool:
        """Display the implementation plan and get user approval"""
        
        # Project overview
        console.print(Panel.fit(
            f"[bold cyan]{spec.project.name}[/bold cyan]\n"
            f"Path: {spec.project.path}\n"
            f"Type: {spec.project.type}\n"
            f"Technologies: {', '.join(spec.project.main_tech)}",
            title="📋 Project Overview"
        ))
        
        # Implementation phases
        phases_table = Table(title="Implementation Phases")
        phases_table.add_column("Phase", style="cyan")
        phases_table.add_column("Duration", style="green")
        phases_table.add_column("Tasks", style="yellow")
        
        for phase in spec.implementation_plan.phases:
            tasks_str = "\n".join(f"• {task}" for task in phase.tasks)
            phases_table.add_row(
                phase.name,
                f"{phase.duration_hours}h",
                tasks_str
            )
        
        console.print(phases_table)
        console.print(f"\n[bold]Total Estimated Time:[/bold] {spec.implementation_plan.total_estimated_hours} hours\n")
        
        # Project size info
        size_info = f"Project Size: [yellow]{spec.project_size.size}[/yellow]"
        if self.manual_size and self.manual_size != spec.project_size.size:
            size_info += f" (overridden from auto-detected: {spec.project_size.size})"
        console.print(size_info)
        
        if self.additional_roles:
            console.print(f"Additional Roles Requested: [cyan]{', '.join(self.additional_roles)}[/cyan]")
        
        console.print()
        
        # Roles and responsibilities
        roles_table = Table(title="Role Assignments")
        roles_table.add_column("Role", style="cyan")
        roles_table.add_column("Check-in", style="green")
        roles_table.add_column("Responsibilities", style="yellow")
        
        for role_name, role_config in spec.roles.items():
            resp_str = "\n".join(f"• {resp}" for resp in role_config.responsibilities[:3])
            if len(role_config.responsibilities) > 3:
                resp_str += f"\n• ... and {len(role_config.responsibilities) - 3} more"
            roles_table.add_row(
                role_name.title(),
                f"{role_config.check_in_interval}m",
                resp_str
            )
        
        console.print(roles_table)
        
        # Success criteria
        console.print(Panel(
            "\n".join(f"✓ {criterion}" for criterion in spec.success_criteria),
            title="🎯 Success Criteria",
            border_style="green"
        ))
        
        # Git workflow
        console.print(Panel(
            f"Parent Branch: [yellow]{spec.git_workflow.parent_branch}[/yellow] (current branch)\n"
            f"Feature Branch: [cyan]{spec.git_workflow.branch_name}[/cyan]\n"
            f"Commit Interval: Every {spec.git_workflow.commit_interval} minutes\n"
            f"PR Title: {spec.git_workflow.pr_title}\n"
            f"[bold red]⚠️  Will merge back to {spec.git_workflow.parent_branch}, NOT main![/bold red]" if spec.git_workflow.parent_branch != "main" else "",
            title="🔀 Git Workflow"
        ))
        
        # Show which roles will actually be deployed
        roles_to_deploy = self.get_roles_for_project_size(spec)
        console.print(f"\n[bold]Roles to be deployed:[/bold] {', '.join([r[0] for r in roles_to_deploy])}")
        
        # Token usage warning
        team_size = len(roles_to_deploy)
        if team_size >= 4:
            console.print(f"\n[yellow]⚠️  Token Usage Warning[/yellow]")
            console.print(f"[yellow]Running {team_size} agents concurrently will use ~{team_size * 15}x normal token consumption[/yellow]")
            console.print(f"[yellow]On {self.plan_type} plan, this provides approximately {225 // (team_size * 15)} messages per 5-hour session[/yellow]")
            
            if team_size >= 5 and self.plan_type == 'max5':
                console.print(f"[red]Consider using fewer agents or upgrading to max20 plan for extended sessions[/red]")
        
        return Confirm.ask("\n[bold]Proceed with automated setup?[/bold]", default=False)
    
    def get_plan_constraints(self) -> int:
        """Get maximum recommended team size based on subscription plan
        
        Returns maximum number of concurrent agents for sustainable token usage
        """
        plan_limits = {
            'pro': 3,      # Pro plan: Max 3 agents (limited tokens)
            'max5': 5,     # Max 5x plan: Max 5 agents (balanced)
            'max20': 8,    # Max 20x plan: Max 8 agents (more headroom)
            'console': 10  # Console/Enterprise: Higher limits
        }
        
        return plan_limits.get(self.plan_type, 5)
    
    def get_roles_for_project_size(self, spec: ImplementationSpec) -> List[Tuple[str, str]]:
        """Determine which roles to deploy based on project size
        
        OPTIMIZED FOR CLAUDE CODE MAX 5X PLAN:
        - Reduced team sizes to conserve tokens (multi-agent uses ~15x normal)
        - Max 5 concurrent agents recommended for sustainable usage
        - Prioritizes essential roles for each project size
        """
        # Use manual size override if provided
        size = self.manual_size if self.manual_size else spec.project_size.size
        
        if size == "small":
            # Small projects: 7 agents (Core team with testing, infrastructure, and monitoring)
            core_roles = [
                ('Orchestrator', 'orchestrator'),
                ('Developer', 'developer'),
                ('Researcher', 'researcher'),
                ('Tester', 'tester'),
                ('TestRunner', 'testrunner'),
                ('LogTracker', 'logtracker'),
                ('DevOps', 'devops')
            ]
        elif size == "medium":
            # Medium projects: 8 agents (+ Project Manager)
            core_roles = [
                ('Orchestrator', 'orchestrator'),
                ('Project-Manager', 'project_manager'),
                ('Developer', 'developer'),
                ('Researcher', 'researcher'),
                ('Tester', 'tester'),
                ('TestRunner', 'testrunner'),
                ('LogTracker', 'logtracker'),
                ('DevOps', 'devops')
            ]
        else:  # large
            # Large projects: 9 agents (full team with all core roles)
            core_roles = [
                ('Orchestrator', 'orchestrator'),
                ('Project-Manager', 'project_manager'),
                ('Developer', 'developer'),
                ('Researcher', 'researcher'),
                ('Tester', 'tester'),
                ('TestRunner', 'testrunner'),
                ('LogTracker', 'logtracker'),
                ('DevOps', 'devops'),
                ('Code-Reviewer', 'code_reviewer')
            ]
        
        # Add any additional requested roles
        role_mapping = {
            'researcher': ('Researcher', 'researcher'),
            'documentation_writer': ('Documentation', 'documentation_writer'),
            'documentation': ('Documentation', 'documentation_writer'),
            'docs': ('Documentation', 'documentation_writer'),
            'devops': ('DevOps', 'devops'),
            'code_reviewer': ('Code-Reviewer', 'code_reviewer'),
            'tester': ('Tester', 'tester'),
            'testrunner': ('TestRunner', 'testrunner'),
            'logtracker': ('LogTracker', 'logtracker')
        }
        
        for role in self.additional_roles:
            if role.lower() in role_mapping:
                core_roles.append(role_mapping[role.lower()])
        
        # Enforce plan constraints
        max_agents = self.get_plan_constraints()
        if len(core_roles) > max_agents:
            console.print(f"\n[yellow]⚠️  Warning: {len(core_roles)} agents requested but {self.plan_type} plan recommends max {max_agents}[/yellow]")
            console.print(f"[yellow]Team will be limited to {max_agents} agents to prevent token exhaustion[/yellow]")
            console.print(f"[yellow]Multi-agent systems use ~15x more tokens than standard usage[/yellow]\n")
            
            # Prioritize roles based on importance
            priority_order = ['orchestrator', 'developer', 'researcher', 'project_manager', 'tester', 'testrunner', 'logtracker', 'devops', 'code_reviewer', 'documentation_writer']
            
            # Sort roles by priority
            core_roles.sort(key=lambda x: priority_order.index(x[1]) if x[1] in priority_order else 999)
            
            # Trim to max agents
            core_roles = core_roles[:max_agents]
            console.print(f"[yellow]Selected roles: {', '.join([r[0] for r in core_roles])}[/yellow]")
        
        return core_roles
    
    def check_existing_worktrees(self, project_name: str, roles_to_deploy: List[Tuple[str, str]]) -> List[str]:
        """Check if worktrees already exist for this project"""
        worktrees_base = self.tmux_orchestrator_path / 'registry' / 'projects' / project_name / 'worktrees'
        existing_worktrees = []
        
        if worktrees_base.exists():
            for window_name, role_key in roles_to_deploy:
                worktree_path = worktrees_base / role_key
                if worktree_path.exists() and any(worktree_path.iterdir()):
                    existing_worktrees.append(role_key)
        
        return existing_worktrees
    
    def check_existing_session(self, session_name: str) -> bool:
        """Check if tmux session already exists"""
        result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                              capture_output=True)
        return result.returncode == 0
    
    def setup_worktrees(self, spec: ImplementationSpec, roles_to_deploy: List[Tuple[str, str]]) -> Dict[str, Path]:
        """Create git worktrees for each agent"""
        # Verify project is a git repo
        if not (self.project_path / '.git').exists():
            console.print("[red]Error: Project must be a git repository to use orchestration[/red]")
            console.print("[yellow]Please initialize git in your project: cd {self.project_path} && git init[/yellow]")
            sys.exit(1)
        
        # First, prune any stale worktree entries globally
        console.print("[cyan]Pruning stale worktree entries...[/cyan]")
        subprocess.run(
            ['git', 'worktree', 'prune'], 
            cwd=str(self.project_path),
            capture_output=True
        )
        
        # Create worktrees directory
        project_name = spec.project.name.lower().replace(' ', '-')
        worktrees_base = self.tmux_orchestrator_path / 'registry' / 'projects' / project_name / 'worktrees'
        worktrees_base.mkdir(parents=True, exist_ok=True)
        
        # Get current branch from project
        current_branch = self.get_current_git_branch()
        if not current_branch:
            console.print("[red]Error: Could not determine current git branch[/red]")
            sys.exit(1)
        
        worktree_paths = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Setting up git worktrees...", total=len(roles_to_deploy))
            
            for window_name, role_key in roles_to_deploy:
                # Create worktree for this role (including orchestrator)
                worktree_path = worktrees_base / role_key
                
                # Store the tool directory path for orchestrator
                if role_key == 'orchestrator':
                    # Orchestrator needs both paths
                    self.orchestrator_tool_path = self.tmux_orchestrator_path
                    
                # Create worktree for this role
                worktree_path = worktrees_base / role_key
                
                # Handle existing or stale worktree entries
                if worktree_path.exists():
                    # Directory exists, remove it properly
                    subprocess.run(['rm', '-rf', str(worktree_path)], capture_output=True)
                
                # Check if this worktree is registered in git
                list_result = subprocess.run(
                    ['git', 'worktree', 'list'], 
                    cwd=str(self.project_path), 
                    capture_output=True, 
                    text=True
                )
                
                if str(worktree_path) in list_result.stdout:
                    # Worktree is registered, try to remove it properly
                    remove_result = subprocess.run(
                        ['git', 'worktree', 'remove', str(worktree_path), '--force'],
                        cwd=str(self.project_path),
                        capture_output=True,
                        text=True
                    )
                    
                    if remove_result.returncode != 0:
                        # If remove fails, it might be because directory is missing
                        # Force prune to clean up stale entries
                        subprocess.run(
                            ['git', 'worktree', 'prune'], 
                            cwd=str(self.project_path), 
                            capture_output=True
                        )
                
                # Create new worktree with multiple fallback strategies
                worktree_created = False
                
                # Strategy 1: Try normal worktree creation
                result = subprocess.run([
                    'git', 'worktree', 'add', 
                    str(worktree_path), 
                    current_branch
                ], cwd=str(self.project_path), capture_output=True, text=True)
                
                if result.returncode == 0:
                    worktree_created = True
                else:
                    console.print(f"[yellow]Normal worktree creation failed for {role_key}[/yellow]")
                    
                    # Check for specific "already registered" error
                    if "already registered" in result.stderr and "use 'add -f' to override" in result.stderr:
                        console.print(f"[yellow]Worktree already registered but missing, using -f flag[/yellow]")
                        result = subprocess.run([
                            'git', 'worktree', 'add', 
                            '-f',  # Force flag to override registration
                            str(worktree_path), 
                            current_branch
                        ], cwd=str(self.project_path), capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            worktree_created = True
                    
                    # Strategy 2: Try with --force flag
                    if "already checked out" in result.stderr:
                        console.print(f"[yellow]Branch '{current_branch}' already checked out, trying --force[/yellow]")
                        result = subprocess.run([
                            'git', 'worktree', 'add', 
                            '--force',
                            str(worktree_path), 
                            current_branch
                        ], cwd=str(self.project_path), capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            worktree_created = True
                    
                    # Strategy 3: Create agent-specific branch
                    if not worktree_created:
                        agent_branch = f"{current_branch}-{role_key}"
                        console.print(f"[yellow]Creating agent-specific branch: {agent_branch}[/yellow]")
                        
                        # Check if branch already exists
                        check_result = subprocess.run([
                            'git', 'rev-parse', '--verify', agent_branch
                        ], cwd=str(self.project_path), capture_output=True, text=True)
                        
                        if check_result.returncode == 0:
                            # Branch exists, just use it
                            result = subprocess.run([
                                'git', 'worktree', 'add', 
                                str(worktree_path),
                                agent_branch
                            ], cwd=str(self.project_path), capture_output=True, text=True)
                        else:
                            # Create new branch in worktree
                            result = subprocess.run([
                                'git', 'worktree', 'add', 
                                '-b', agent_branch,
                                str(worktree_path),
                                current_branch
                            ], cwd=str(self.project_path), capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            worktree_created = True
                    
                    # Strategy 4: Skip orphan (not supported in older git versions)
                    # Orphan branches in worktrees require git 2.23+
                    # We'll skip directly to detached HEAD strategy
                    
                    # Strategy 5: Detached HEAD with specific commit
                    if not worktree_created:
                        console.print(f"[yellow]Creating detached worktree at HEAD[/yellow]")
                        
                        # Get current commit hash
                        commit_result = subprocess.run([
                            'git', 'rev-parse', 'HEAD'
                        ], cwd=str(self.project_path), capture_output=True, text=True)
                        
                        if commit_result.returncode == 0:
                            commit_hash = commit_result.stdout.strip()
                            result = subprocess.run([
                                'git', 'worktree', 'add', 
                                '--detach',
                                str(worktree_path),
                                commit_hash
                            ], cwd=str(self.project_path), capture_output=True, text=True)
                            
                            if result.returncode == 0:
                                worktree_created = True
                            elif "already registered" in result.stderr:
                                # Try with -f flag
                                console.print(f"[yellow]Detached worktree already registered, using -f flag[/yellow]")
                                result = subprocess.run([
                                    'git', 'worktree', 'add', 
                                    '--detach', '-f',
                                    str(worktree_path),
                                    commit_hash
                                ], cwd=str(self.project_path), capture_output=True, text=True)
                                
                                if result.returncode == 0:
                                    worktree_created = True
                
                if not worktree_created:
                    console.print(f"[red]Failed to create worktree for {role_key} after all strategies[/red]")
                    console.print(f"[red]Error: {result.stderr}[/red]")
                    sys.exit(1)
                    
                worktree_paths[role_key] = worktree_path
                
                # Copy .mcp.json file if it exists in the project
                project_mcp = self.project_path / '.mcp.json'
                if project_mcp.exists():
                    worktree_mcp = worktree_path / '.mcp.json'
                    try:
                        import shutil
                        shutil.copy2(project_mcp, worktree_mcp)
                        console.print(f"[green]✓ Copied .mcp.json to {role_key}'s worktree[/green]")
                    except Exception as e:
                        console.print(f"[yellow]Warning: Could not copy .mcp.json to {role_key}: {e}[/yellow]")
                
                # Always merge parent project's MCP configuration into worktree's .mcp.json
                # This handles both cases: when .mcp.json was copied and when it doesn't exist
                self.setup_mcp_for_worktree(worktree_path)
                
                # Enable MCP servers in Claude configuration for this worktree
                self.enable_mcp_servers_in_claude_config(worktree_path)
                
                progress.update(task, advance=1, description=f"Created worktree for {role_key}")
        
        # Display worktree summary
        console.print("\n[green]✓ Git worktrees created:[/green]")
        for role, path in worktree_paths.items():
            console.print(f"  {role}: {path.relative_to(self.tmux_orchestrator_path)}")
        
        return worktree_paths
    
    def create_worktree_map(self, worktree_paths: Dict[str, Path], roles_deployed: List[Tuple[str, str]]) -> str:
        """Create a visual map of worktree locations for better clarity"""
        if not worktree_paths or not roles_deployed:
            return ""
            
        map_str = "\n📍 **Quick Reference - Team Locations Map**:\n```\n"
        map_str += f"Main Project: {self.project_path}/\n"
        map_str += "├── mcp-inventory.md (shared by all)\n"
        map_str += "├── docs/ (shared documentation)\n"
        map_str += "└── [project files]\n\n"
        
        map_str += "Team Worktrees:\n"
        for window_name, role_key in roles_deployed:
            if role_key in worktree_paths:
                path = worktree_paths[role_key]
                map_str += f"├── {window_name}: {path}/\n"
        
        map_str += "```\n"
        return map_str
    
    def get_worktree_branch_info(self, worktree_path: Path) -> str:
        """Get information about the worktree's branch status"""
        result = subprocess.run([
            'git', 'branch', '--show-current'
        ], cwd=str(worktree_path), capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            return f"Working on branch: {result.stdout.strip()}"
        else:
            # Check if detached
            result = subprocess.run([
                'git', 'rev-parse', 'HEAD'
            ], cwd=str(worktree_path), capture_output=True, text=True)
            if result.returncode == 0:
                return f"Working in detached HEAD at: {result.stdout.strip()[:8]}"
        return "Unknown branch status"
    
    def cleanup_worktrees(self, project_name: str):
        """Clean up worktrees and any agent-specific branches"""
        worktrees_base = self.tmux_orchestrator_path / 'registry' / 'projects' / project_name / 'worktrees'
        if worktrees_base.exists():
            console.print("\n[yellow]Cleaning up worktrees...[/yellow]")
            # Remove all worktrees
            for worktree in worktrees_base.iterdir():
                if worktree.is_dir():
                    subprocess.run(['rm', '-rf', str(worktree)], capture_output=True)
            # Prune git worktree list
            subprocess.run(['git', 'worktree', 'prune'], 
                         cwd=str(self.project_path), capture_output=True)
            
            # Clean up any agent-specific branches
            result = subprocess.run([
                'git', 'branch', '--list', '*-orchestrator', '*-project_manager', 
                '*-developer*', '*-tester', '*-devops', '*-code_reviewer', 
                '*-researcher', '*-documentation_writer', 'orphan-*'
            ], cwd=str(self.project_path), capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                branches_to_delete = result.stdout.strip().split('\n')
                for branch in branches_to_delete:
                    branch = branch.strip().lstrip('* ')
                    if branch:
                        subprocess.run([
                            'git', 'branch', '-D', branch
                        ], cwd=str(self.project_path), capture_output=True)
            
            console.print("[green]✓ Worktrees and agent branches cleaned up[/green]")
    
    def ensure_orchestrator_reference(self, worktree_paths: Dict[str, Path]):
        """Ensure each worktree's CLAUDE.md references the Tmux-Orchestrator rules"""
        orchestrator_claude_path = self.tmux_orchestrator_path / "CLAUDE.md"
        
        if not orchestrator_claude_path.exists():
            console.print("[red]Warning: Tmux-Orchestrator/CLAUDE.md not found![/red]")
            return
        
        for role_key, worktree_path in worktree_paths.items():
                
            project_claude_md = worktree_path / "CLAUDE.md"
            
            orchestrator_section = f"""

# MANDATORY: Tmux Orchestrator Rules

**CRITICAL**: You MUST read and follow ALL instructions in:
`{orchestrator_claude_path}`

**Your worktree location**: `{worktree_path}`
**Original project location**: `{self.project_path}`

The orchestrator rules file contains MANDATORY instructions for:
- 🚨 Git discipline and branch protection (NEVER merge to main unless you started on main)
- 💬 Communication protocols between agents
- ✅ Quality standards and verification procedures  
- 🔄 Self-scheduling requirements
- 🌳 Git worktree collaboration guidelines

**IMMEDIATE ACTION REQUIRED**: Use the Read tool to read {orchestrator_claude_path} before doing ANY work.

Failure to follow these rules will result in:
- Lost work due to improper git usage
- Conflicts between agents
- Failed project delivery
"""
            
            try:
                if project_claude_md.exists():
                    content = project_claude_md.read_text()
                    # Check if reference already exists
                    if str(orchestrator_claude_path) not in content:
                        # Append the reference
                        with open(project_claude_md, 'a') as f:
                            f.write(orchestrator_section)
                        console.print(f"[green]✓ Added orchestrator rules to {role_key}'s CLAUDE.md[/green]")
                else:
                    # Create new CLAUDE.md with the reference
                    project_claude_md.write_text(f"""# Project Instructions

This file is automatically read by Claude Code when working in this directory.
{orchestrator_section}
""")
                    console.print(f"[green]✓ Created CLAUDE.md for {role_key} with orchestrator rules[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not update CLAUDE.md for {role_key}: {e}[/yellow]")
    
    def setup_tmux_session(self, spec: ImplementationSpec):
        """Set up the tmux session with roles based on project size using git worktrees"""
        session_name = spec.project.name.lower().replace(' ', '-')[:20] + "-impl"
        
        # Determine which roles to deploy
        roles_to_deploy = self.get_roles_for_project_size(spec)
        
        # Set up git worktrees for isolation
        worktree_paths = self.setup_worktrees(spec, roles_to_deploy)
        
        # Store worktree paths for later use
        self.worktree_paths = worktree_paths
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            # Create tmux session
            task = progress.add_task("Creating tmux session...", total=len(roles_to_deploy))
            
            # Kill existing session if it exists
            subprocess.run(['tmux', 'kill-session', '-t', session_name], 
                         capture_output=True)
            
            # Create new session with first role
            first_window, first_role = roles_to_deploy[0]
            working_dir = str(worktree_paths[first_role])
            
            subprocess.run([
                'tmux', 'new-session', '-d', '-s', session_name,
                '-n', first_window, '-c', working_dir
            ], check=True)
            
            progress.update(task, advance=1, description=f"Created {first_window} window...")
            
            # Create other role windows with their worktree paths
            for window_name, role_key in roles_to_deploy[1:]:
                working_dir = str(worktree_paths[role_key])
                subprocess.run([
                    'tmux', 'new-window', '-t', session_name,
                    '-n', window_name, '-c', working_dir
                ], check=True)
                progress.update(task, advance=1, description=f"Created {window_name} window...")
            
            # Ensure each worktree has orchestrator reference in CLAUDE.md
            self.ensure_orchestrator_reference(worktree_paths)
            
            # Start Claude in each window and send initial briefings
            self.brief_all_roles(session_name, spec, roles_to_deploy, worktree_paths)
            
            console.print(f"\n[green]✓ Tmux session '{session_name}' created with {len(roles_to_deploy)} roles![/green]")
            console.print(f"\nProject size: [yellow]{spec.project_size.size}[/yellow]")
            console.print(f"Deployed roles: {', '.join([r[0] for r in roles_to_deploy])}")
            console.print(f"\nTo attach: [cyan]tmux attach -t {session_name}[/cyan]")
            console.print(f"\n[yellow]Note: Each agent works in their own git worktree to prevent conflicts[/yellow]")
    
    def brief_all_roles(self, session_name: str, spec: ImplementationSpec, roles_to_deploy: List[Tuple[str, str]], worktree_paths: Dict[str, Path]):
        """Start Claude in each window and provide role-specific briefings"""
        
        # Check if Claude version supports context priming
        supports_context_prime = self.check_claude_version()
        
        # Convert roles_to_deploy to include window indices
        roles = [(name, idx, role) for idx, (name, role) in enumerate(roles_to_deploy)]
        
        for window_name, window_idx, role_key in roles:
            # Pre-initialize Claude if worktree has .mcp.json
            worktree_path = worktree_paths.get(role_key)
            if worktree_path and (worktree_path / '.mcp.json').exists():
                # Pre-initialize Claude to approve MCP servers
                self.pre_initialize_claude_in_worktree(session_name, window_idx, role_key, worktree_path)
                
                # Kill the window (since it only has one pane)
                subprocess.run([
                    'tmux', 'kill-window', '-t', f'{session_name}:{window_idx}'
                ], capture_output=True)
                
                # Create a new window at the same index
                # Using -a flag to insert at specific index
                subprocess.run([
                    'tmux', 'new-window', '-t', f'{session_name}:{window_idx}',
                    '-n', window_name, '-c', str(worktree_path),
                    '-d'  # Don't switch to it
                ], capture_output=True)
                
                console.print(f"[green]✓ Recreated window for {role_key} after MCP approval[/green]")
                
                # Small delay to ensure window is ready
                time.sleep(1)
            
            # Start Claude with dangerous skip permissions
            subprocess.run([
                'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
                'claude --dangerously-skip-permissions', 'Enter'
            ])
            
            # Wait for Claude to start
            time.sleep(5)
            
            # Send context priming command if the project supports it
            context_prime_path = spec.project.path.replace('~', str(Path.home()))
            context_prime_file = Path(context_prime_path) / '.claude' / 'commands' / 'context-prime.md'
            
            if role_key != 'orchestrator' and context_prime_file.exists():
                send_script = self.tmux_orchestrator_path / 'send-claude-message.sh'
                context_prime_msg = f'/context-prime "You are about to work on {spec.project.name} at {spec.project.path}. Understand the project structure, dependencies, and conventions."'
                try:
                    subprocess.run([
                        str(send_script),
                        f'{session_name}:{window_idx}',
                        context_prime_msg
                    ])
                    # Wait for context priming to complete
                    time.sleep(8)
                except Exception as e:
                    console.print(f"[yellow]Context priming skipped for {window_name}: {str(e)}[/yellow]")
            
            # Get role config
            role_config = spec.roles[role_key]
            
            # Create briefing
            briefing = self.create_role_briefing(role_key, spec, role_config, 
                                                context_primed=supports_context_prime,
                                                roles_deployed=roles_to_deploy,
                                                worktree_paths=worktree_paths,
                                                mcp_categories=getattr(self, 'mcp_categories', {}))
            
            # Send briefing using send-claude-message.sh
            send_script = self.tmux_orchestrator_path / 'send-claude-message.sh'
            subprocess.run([
                str(send_script),
                f'{session_name}:{window_idx}',
                briefing
            ])
            
            # Run initial commands
            for cmd in role_config.initial_commands:
                time.sleep(2)
                subprocess.run([
                    str(send_script),
                    f'{session_name}:{window_idx}',
                    f"Please run: {cmd}"
                ])
            
            # Schedule check-ins
            if role_key != 'orchestrator':  # Orchestrator schedules its own
                # Use credit-aware scheduling if available
                credit_schedule_script = self.tmux_orchestrator_path / 'credit_management' / 'schedule_credit_aware.sh'
                regular_schedule_script = self.tmux_orchestrator_path / 'schedule_with_note.sh'
                
                schedule_script = credit_schedule_script if credit_schedule_script.exists() else regular_schedule_script
                
                subprocess.run([
                    str(schedule_script),
                    str(role_config.check_in_interval),
                    f"{window_name} regular check-in",
                    f"{session_name}:{window_idx}"
                ])
    
    def get_available_mcp_tools(self, worktree_path: Path) -> str:
        """Parse .mcp.json in worktree and return list of available MCP tools"""
        mcp_json_path = worktree_path / '.mcp.json'
        if not mcp_json_path.exists():
            return ""
        
        try:
            with open(mcp_json_path, 'r') as f:
                mcp_config = json.load(f)
                if 'mcpServers' in mcp_config and mcp_config['mcpServers']:
                    tools = list(mcp_config['mcpServers'].keys())
                    tool_list = '\n'.join(f'  - {tool}' for tool in tools)
                    return f"\n🔧 **MCP Tools Available** (from your local .mcp.json):\n{tool_list}\n"
                else:
                    return ""
        except Exception as e:
            return f"\n⚠️ Error reading .mcp.json: {str(e)}\n"
    
    def create_role_briefing(self, role: str, spec: ImplementationSpec, role_config: RoleConfig, 
                           context_primed: bool = True, roles_deployed: List[Tuple[str, str]] = None,
                           worktree_paths: Dict[str, Path] = None, mcp_categories: Dict[str, List[str]] = None) -> str:
        """Create a role-specific briefing message"""
        
        # Get available MCP tools for this agent's worktree
        mcp_tools_info = ""
        if worktree_paths and role in worktree_paths:
            mcp_tools_info = self.get_available_mcp_tools(worktree_paths[role])
        
        # MANDATORY reading instruction for all non-orchestrator roles
        mandatory_reading = ""
        if role != 'orchestrator' and worktree_paths:
            orchestrator_claude_path = self.tmux_orchestrator_path / "CLAUDE.md"
            mandatory_reading = f"""🚨 **MANDATORY FIRST STEP** 🚨

Before doing ANYTHING else, you MUST read the orchestrator rules:
`{orchestrator_claude_path}`

Use the Read tool NOW to read this file. It contains CRITICAL instructions for:
- Git discipline (NEVER merge to main unless you started there)
- Communication protocols
- Quality standards
- Self-scheduling requirements

Your worktree location: `{worktree_paths.get(role, 'N/A')}`

---\n\n"""
        
        # Team worktree locations for all agents
        team_locations = ""
        if worktree_paths and roles_deployed:
            team_locations = "\n📂 **Team Worktree Locations & Cross-Worktree Collaboration**:\n\n"
            team_locations += "**Your Team's Worktrees**:\n"
            for window_name, role_key in roles_deployed:
                if role_key in worktree_paths:
                    team_locations += f"- **{window_name}** ({role_key}): `{worktree_paths[role_key]}`\n"
            team_locations += f"\n**Main Project Directory** (shared resources): `{self.project_path}`\n"
            team_locations += "  - Use for shared files (mcp-inventory.md, project docs, etc.)\n"
            team_locations += "  - All agents can read/write here\n"
            
            # Add cross-worktree collaboration guide
            team_locations += "\n🔄 **Cross-Worktree Collaboration Guide**:\n\n"
            team_locations += "**To review another agent's code**:\n"
            team_locations += "```bash\n"
            team_locations += "# Read files from another agent's worktree\n"
            team_locations += "# Example: PM reviewing Developer's code\n"
            if 'developer' in worktree_paths:
                team_locations += f"cat {worktree_paths['developer']}/src/main.py\n"
            team_locations += "\n"
            team_locations += "# List files in another agent's worktree\n"
            if 'tester' in worktree_paths:
                team_locations += f"ls -la {worktree_paths['tester']}/tests/\n"
            team_locations += "```\n\n"
            
            team_locations += "**To get another agent's changes**:\n"
            team_locations += "```bash\n"
            team_locations += "# Fetch and merge changes from another agent's branch\n"
            team_locations += "git fetch origin\n"
            team_locations += "git branch -r  # See all remote branches\n"
            team_locations += "git merge origin/feature-developer  # Merge developer's branch\n"
            team_locations += "```\n\n"
            
            team_locations += "**To share your changes**:\n"
            team_locations += "```bash\n"
            team_locations += "# Push your branch so others can access it\n"
            team_locations += "git add -A && git commit -m \"Your changes\"\n"
            team_locations += "git push -u origin your-branch-name\n"
            team_locations += "```\n"
            
            # Add visual map
            team_locations += self.create_worktree_map(worktree_paths, roles_deployed)
            team_locations += "\n"
        
        # Get the actual team composition
        if roles_deployed:
            team_windows = [f"- {name} (window {idx})" for idx, (name, role_type) in enumerate(roles_deployed) if role_type != 'orchestrator']
            team_description = "\n".join(team_windows)
        else:
            team_description = "- Check 'tmux list-windows' to see your team"
        
        # Add note about context priming if not available
        context_note = ""
        if not context_primed and role != 'orchestrator':
            context_note = """
NOTE: Context priming was not available. Please take a moment to:
1. Explore the project structure: ls -la
2. Check for README or documentation files
3. Identify the main technologies and frameworks used
4. Understand the project conventions

"""
        
        # Get MCP guidance for this role
        mcp_guidance = ""
        if mcp_categories:
            mcp_guidance = "\n\n" + self.get_role_mcp_guidance(role, mcp_categories) + "\n"
        
        if role == 'orchestrator':
            tool_path = self.tmux_orchestrator_path
            return f"""{mandatory_reading}{team_locations}You are the Orchestrator for {spec.project.name}.

📂 **CRITICAL: You work from TWO locations:**
1. **Project Worktree**: `{worktree_paths.get(role, 'N/A')}`
   - Create ALL project files here (reports, documentation, tracking)
   - This is your primary working directory
   - Start here: You're already in this directory
   - {self.get_worktree_branch_info(worktree_paths.get(role, Path('.'))) if worktree_paths else 'Branch status unknown'}

2. **Tool Directory**: `{tool_path}`
   - Run orchestrator tools from here:
     - `./send-claude-message.sh`
     - `./schedule_with_note.sh`
     - `python3 claude_control.py`
   - Use: `cd {tool_path}` when running tools

🚫 **NEVER create project files in the tool directory!**

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Project Overview:
- Type: {spec.project.type}
- Technologies: {', '.join(spec.project.main_tech)}
- Total estimated time: {spec.implementation_plan.total_estimated_hours} hours

Project size: {spec.project_size.size}
Estimated complexity: {spec.project_size.complexity}
{mcp_guidance}
Your team composition:
{team_description}

Workflow Example:
```bash
# You start in project worktree - create project files here
pwd  # Should show: {worktree_paths.get(role, 'N/A')}
mkdir -p project_management/docs
echo "# Project Status" > project_management/status.md

# Switch to tool directory for orchestrator commands
cd {tool_path}
./send-claude-message.sh project-manager:1 "What's your status?"
./schedule_with_note.sh 30 "Check team progress" "session:0"
python3 claude_control.py status detailed

# Switch back to project worktree for more project work
cd {worktree_paths.get(role, 'N/A')}
```

Schedule your first check-in for {role_config.check_in_interval} minutes from the tool directory.

**IMMEDIATE TASKS**:
1. Create `{self.project_path}/mcp-inventory.md` in the MAIN project directory (not your worktree!)
   - This ensures ALL agents can access it
   - Document available MCP tools for the team
2. Inform all agents where to find team resources:
   - MCP inventory: `{self.project_path}/mcp-inventory.md`
   - Shared docs: `{self.project_path}/docs/`
   - Team worktrees: See locations above

## 💳 Credit Management
Monitor team credit status to ensure continuous operation:
```bash
cd {tool_path}
# Quick health check
./credit_management/check_agent_health.sh

# Start continuous monitoring (run in background)
nohup ./credit_management/credit_monitor.py > /dev/null 2>&1 &
```

**Credit Exhaustion Handling**:
- Agents automatically pause when credits exhausted
- System detects UI reset times and schedules resume
- Fallback 5-hour cycle calculation if UI parsing fails
- Check `~/.claude/credit_schedule.json` for status

📊 **Context Window Management - Don't Worry About Low Context!**

IMPORTANT: You can continue sending tasks to agents reporting low context (3%, 6%, etc):
- **Agents self-manage**: They know to checkpoint and /compact when needed
- **Work continues**: After compacting, they reload context and keep working
- **No intervention needed**: Don't avoid or "save" low-context agents
- **Keep delegating**: Send tasks normally - they'll handle context themselves

When an agent mentions low context:
1. Acknowledge: "Thanks for the context update"
2. Continue normally: Assign tasks as planned
3. They'll auto-compact when ready
4. If confused after compact, remind them: "Check your checkpoint document"

This means context exhaustion is NOT a crisis - it's a routine, self-managed event!"""

        elif role == 'project_manager':
            # Build PM-specific worktree paths for examples
            dev_path = worktree_paths.get('developer', '/path/to/developer')
            test_path = worktree_paths.get('tester', '/path/to/tester')
            
            return f"""{mandatory_reading}{context_note}{team_locations}You are the Project Manager for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

🔍 **CODE REVIEW WORKFLOWS**:

**Daily Code Review Process**:
```bash
# 1. Review Developer's changes
cd {dev_path}
git status  # Check their current work
git log --oneline -10  # Review recent commits
git diff HEAD~1  # Review latest changes

# 2. Review test coverage
cd {test_path}
ls -la tests/  # Check test structure
grep -r "test_" tests/  # Find all test functions

# 3. Cross-reference implementation with tests
# Use Read tool for detailed review:
# Read {dev_path}/src/feature.py
# Read {test_path}/tests/test_feature.py
```

**Quality Verification Checklist**:
- [ ] Code follows project conventions (check against existing code)
- [ ] All new functions have tests
- [ ] Error handling is comprehensive
- [ ] Documentation is updated
- [ ] No hardcoded values or secrets
- [ ] Performance implications considered

**Coordinating Merges Between Worktrees**:
```bash
# When Developer is ready to share:
# Tell Developer: "Please push your branch: git push -u origin feature-dev"

# Then in your worktree:
git fetch origin
git checkout -b review-feature
git merge origin/feature-dev
# Review merged code
# If approved, coordinate merge to parent branch
```

Implementation Phases:
{chr(10).join(f'{i+1}. {p.name} ({p.duration_hours}h)' for i, p in enumerate(spec.implementation_plan.phases))}

Success Criteria:
{chr(10).join(f'- {c}' for c in spec.success_criteria)}
{mcp_guidance}
Git Workflow:
- CRITICAL: Project started on branch '{spec.git_workflow.parent_branch}'
- Feature branch: {spec.git_workflow.branch_name} (created from {spec.git_workflow.parent_branch})
- MERGE ONLY TO: {spec.git_workflow.parent_branch} (NOT main unless parent is main!)
- Commit every {spec.git_workflow.commit_interval} minutes
- PR Title: {spec.git_workflow.pr_title}

Your Team (based on project size: {spec.project_size.size}):
{team_description}

🔍 **Researcher Available**: Check with the Researcher for best practices, security analysis, and performance recommendations before making critical decisions.

**Communication Protocol**:
- Check each team member's worktree every 30 minutes
- Use specific file paths when discussing code
- Always report blockers to Orchestrator immediately

Maintain EXCEPTIONAL quality standards. No compromises.

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_context_management_instructions(role)}"""

        elif role == 'developer':
            return f"""{mandatory_reading}{context_note}{team_locations}You are the Developer for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Project Details:
- Path: {spec.project.path}
- Type: {spec.project.type}
- Technologies: {', '.join(spec.project.main_tech)}

Implementation Phases:
{chr(10).join(f'{i+1}. {p.name}: {", ".join(p.tasks[:2])}...' for i, p in enumerate(spec.implementation_plan.phases))}
{mcp_guidance}
Git Worktree Information:
- You are working in an isolated git worktree
- Your worktree path: {worktree_paths.get(role, 'N/A')}
- {self.get_worktree_branch_info(worktree_paths.get(role, Path('.'))) if worktree_paths else 'Branch status unknown'}
- This prevents conflicts with other agents
- You can create branches without affecting others

Git Requirements:
- CRITICAL: Current branch is '{spec.git_workflow.parent_branch}' - ALL work must merge back here!
- Create feature branch: {spec.git_workflow.branch_name} FROM {spec.git_workflow.parent_branch}
- NEVER merge to main unless {spec.git_workflow.parent_branch} is main
- Commit every {spec.git_workflow.commit_interval} minutes with clear messages
- Follow existing code patterns and conventions

Git Commands for Worktrees:
```bash
# You're already in your worktree at {worktree_paths.get(role, 'N/A')}
# Record starting branch
echo "{spec.git_workflow.parent_branch}" > .git/STARTING_BRANCH
# Create feature branch FROM current branch
git checkout -b {spec.git_workflow.branch_name}
# When ready to share with other agents:
git push -u origin {spec.git_workflow.branch_name}
# To get updates from another agent's worktree:
git fetch origin
git merge origin/their-branch-name
```

**Making Your Code Reviewable**:
```bash
# 1. Commit frequently with clear messages
git add -A
git commit -m "feat: implement user authentication endpoint"

# 2. Push your branch for PM review
git push -u origin {spec.git_workflow.branch_name}

# 3. Notify PM when ready for review
# "Ready for review: authentication module in src/auth/"
# "Tests added in tests/test_auth.py"
```

Start by:
1. Reading the spec at: {self.spec_path}
2. 🔍 **Check with Researcher** for best practices and security considerations
3. Setting up your development environment
4. Creating the feature branch
5. Beginning implementation of Phase 1

Collaborate with:
- PM for code reviews (push branches regularly)
- Researcher for technical guidance and best practices
- Tester for early testing feedback

**Remember**: Your code is in `{worktree_paths.get(role, 'your-worktree')}` - PM will review it there!

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_context_management_instructions(role)}"""

        elif role == 'tester':
            return f"""{mandatory_reading}{context_note}{team_locations}You are the Tester for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Testing Focus:
- Technologies: {', '.join(spec.project.main_tech)}
- Ensure all success criteria are met:
{chr(10).join(f'  - {c}' for c in spec.success_criteria)}
{mcp_guidance}
**Testing Across Worktrees**:
```bash
# 1. Get Developer's latest code
git fetch origin
git merge origin/{spec.git_workflow.branch_name}

# 2. Or directly test files from Developer's worktree
python -m pytest {worktree_paths.get('developer', '/dev/worktree')}/tests/

# 3. Create tests based on Developer's implementation
# Read their code: cat {worktree_paths.get('developer', '/dev/worktree')}/src/module.py
# Write corresponding tests in your worktree
```

Your workflow:
1. Monitor Developer's worktree for new code
2. Run tests after each Developer commit
3. Report failures immediately to PM and Developer
4. Track test coverage metrics
5. Verify no regressions occur

**Test Results Sharing**:
```bash
# Push your test branch for team visibility
git add tests/
git commit -m "test: add integration tests for auth module"
git push -u origin tests-{spec.git_workflow.branch_name}

# Notify team: "New tests added: 95% coverage on auth module"
```

Start by:
1. Understanding the existing test structure
2. 🔍 **Consult Researcher** for security testing strategies and performance benchmarks
3. Setting up test environment
4. Running current test suite as baseline

Collaborate with:
- Developer (access code at: `{worktree_paths.get('developer', 'dev-worktree')}`)
- Researcher for security vulnerabilities and testing best practices
- PM for quality standards

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_context_management_instructions(role)}"""

        elif role == 'testrunner':
            return f"""{mandatory_reading}{context_note}{team_locations}You are the Test Runner for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

**Test Execution Focus**:
- Continuous test execution and monitoring
- Parallel test suite management
- Performance and load testing
- Test infrastructure optimization
- Regression test automation
- Test result analysis and reporting

**Your Workflow**:
```bash
# 1. Set up test infrastructure
cd {worktree_paths.get(role, 'your-worktree')}
# Configure test runners (pytest, jest, etc.)

# 2. Execute test suites from Tester
git fetch origin
git merge origin/tests-{spec.git_workflow.branch_name}

# 3. Run tests with various configurations
# Unit tests, integration tests, E2E tests
# Performance tests, load tests
```

**Test Execution Strategies**:
1. Parallel test execution for speed
2. Isolated test environments
3. Continuous integration hooks
4. Test result aggregation
5. Failure analysis and reporting

**Collaboration**:
- Tester (get new test suites from: `{worktree_paths.get('tester', 'tester-worktree')}`)
- Developer (verify fixes at: `{worktree_paths.get('developer', 'dev-worktree')}`)
- DevOps for CI/CD integration
- PM for test coverage reports

Start by:
1. Setting up test execution framework
2. Configuring parallel test runners
3. Creating test execution pipelines
4. Establishing baseline metrics

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_context_management_instructions(role)}"""

        elif role == 'logtracker':
            return f"""{mandatory_reading}{context_note}{team_locations}You are the Log Tracker for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

**CRITICAL FIRST TASK**: Read the project's CLAUDE.md for logging/monitoring instructions
```bash
# Check for project-specific monitoring guidance
cat {self.project_path}/CLAUDE.md | grep -i -E "(log|monitor|error|track|alert)"
cat {self.project_path}/.claude/CLAUDE.md | grep -i -E "(log|monitor|error|track|alert)"
```

**Log Monitoring Focus**:
- Real-time log tracking and analysis
- Error pattern detection and classification
- Critical issue alerting
- Performance anomaly detection
- Security event monitoring
- Log aggregation and filtering
- Historical error trending

**Project-Specific Tools**:
1. First check CLAUDE.md for recommended tools/scripts
2. Look for monitoring scripts in project:
   ```bash
   find {self.project_path} -name "*.sh" -o -name "*.py" | grep -E "(log|monitor|check)"
   ls -la {self.project_path}/scripts/ | grep -E "(log|monitor|check)"
   ```

**Your Workflow**:
```bash
# 1. Set up monitoring workspace
cd {worktree_paths.get(role, 'your-worktree')}
mkdir -p monitoring/logs monitoring/reports

# 2. Identify all log sources
# Application logs, server logs, build logs, test logs

# 3. Set up log tailing
# Use project-recommended tools or standard tools like:
# tail -f, journalctl, docker logs, kubectl logs

# 4. Create error tracking dashboard
```

**Error Reporting Protocol**:
- **CRITICAL**: Immediate alert to Orchestrator and PM
- **HIGH**: Report within 5 minutes to Developer and DevOps
- **MEDIUM**: Include in hourly summary
- **LOW**: Track for daily report

**Integration Points**:
- DevOps: Access log infrastructure (`{worktree_paths.get('devops', 'devops-worktree')}`)
- Developer: Provide error context for debugging
- Tester: Share error patterns for test creation
- PM: Regular error summaries and trends

**Key Deliverables**:
1. Real-time error alerts
2. Hourly error summaries
3. Daily trend reports
4. Performance anomaly detection
5. Security event notifications

Start by:
1. Reading project CLAUDE.md for monitoring instructions
2. Identifying all log sources in the project
3. Setting up log aggregation infrastructure
4. Creating initial error tracking dashboard
5. Establishing baseline error rates

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_context_management_instructions(role)}"""

        elif role == 'devops':
            return f"""{mandatory_reading}{context_note}{team_locations}You are the DevOps Engineer for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Project Infrastructure:
- Type: {spec.project.type}
- Technologies: {', '.join(spec.project.main_tech)}
- Path: {spec.project.path}
{mcp_guidance}
Key Tasks:
1. Analyze current deployment configuration
2. Set up CI/CD pipelines if needed
3. Optimize build and deployment processes
4. Monitor performance and resource usage
5. Ensure security best practices

Start by:
1. Check for existing deployment configs (Dockerfile, docker-compose.yml, etc.)
2. Review any CI/CD configuration (.github/workflows, .gitlab-ci.yml, etc.)
3. Identify infrastructure requirements
4. Document deployment procedures

Coordinate with:
- Developer on build requirements
- PM on deployment timelines
- Tester on staging environments
- 🔍 **Researcher** for infrastructure best practices and security hardening

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_context_management_instructions(role)}"""

        elif role == 'code_reviewer':
            return f"""{mandatory_reading}{context_note}{team_locations}You are the Code Reviewer for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Review Focus:
- Code quality and maintainability
- Security vulnerabilities
- Performance implications
- Adherence to project conventions
- Test coverage
{mcp_guidance}
Git Workflow:
- Review feature branch: {spec.git_workflow.branch_name}
- Ensure commits follow project standards
- Check for sensitive data in commits

Review Process:
1. Monitor commits from Developer
2. Review code changes for:
   - Logic errors
   - Security issues
   - Performance problems
   - Code smells
   - Missing tests
3. Provide constructive feedback
4. Approve only high-quality code

Start by:
1. Understanding project coding standards
2. Reviewing recent commit history
3. Setting up security scanning tools if available

Work with Developer to maintain code excellence."""

        elif role == 'researcher':
            return f"""{mandatory_reading}{context_note}{team_locations}You are the Technical Researcher for {spec.project.name}.
{mcp_tools_info}
📋 **Pre-Session Note**: 
- **IMPORTANT**: Check `{self.project_path}/mcp-inventory.md` (in MAIN project, not your worktree!)
- This file is created by the Orchestrator and lists all available MCP tools
- Your worktree: `{worktree_paths.get(role, 'N/A')}`
- Main project with shared resources: `{self.project_path}`

**Accessing Shared Resources**:
```bash
# Read the MCP inventory from main project
cat {self.project_path}/mcp-inventory.md

# Your research outputs go in YOUR worktree
cd {worktree_paths.get(role, 'your-worktree')}
mkdir -p research
echo "# Available Tools" > research/available-tools.md
```

🔍 **CRITICAL MCP TOOL DISCOVERY WORKFLOW**:

1. **Your Available MCP Tools**:
   - Check the MCP tools list above (parsed from your local .mcp.json)
   - These tools are automatically available in Claude Code
   - Common tool names indicate their purpose:
     - `websearch` - For web searches
     - `firecrawl` - For web scraping  
     - `puppeteer` - For browser automation
     - `context7` - For knowledge queries
   
2. **Document Available Tools**:
   Create `research/available-tools.md` listing:
   - Which MCP tools you have available (from the list above)
   - What capabilities each provides
   - Your research strategy based on available tools

3. **Tool-Specific Research Strategies**:
   
   🌐 **If web search tools available** (websearch, tavily, etc.):
   - Best practices for {', '.join(spec.project.main_tech)}
   - Security vulnerabilities (CVEs) for all dependencies
   - Performance benchmarks and optimization techniques
   - Latest API documentation and updates
   - Similar project implementations and case studies
   
   🔥 **If firecrawl/scraping tools available**:
   - Comprehensive documentation extraction
   - Code examples from official sources
   - Implementation patterns and tutorials
   - Stack Overflow solutions for common issues
   
   🧠 **If context/knowledge tools available** (context7, etc.):
   - Deep technical architecture patterns
   - Advanced optimization techniques
   - Edge cases and gotchas
   - Historical context and evolution

4. **Proactive Research Areas**:
   - 🔒 **Security**: All CVEs, OWASP risks, auth best practices
   - ⚡ **Performance**: Benchmarks, bottlenecks, optimization
   - 📚 **Best Practices**: Industry standards, style guides, patterns
   - 📦 **Libraries**: Alternatives, comparisons, compatibility
   - 🏗️ **Architecture**: Scalability, maintainability, testing

5. **Research Outputs** (in your worktree):
   ```
   research/
   ├── available-tools.md         # MCP tools inventory
   ├── security-analysis.md       # CVEs, vulnerabilities
   ├── performance-guide.md       # Optimization strategies
   ├── best-practices.md          # Coding standards
   ├── library-comparison.md      # Tech stack analysis
   └── phase-{{n}}-research.md      # Phase-specific findings
   ```

6. **Team Communication Protocol**:
   - Create actionable recommendations, not info dumps
   - Tag findings: [CRITICAL], [RECOMMENDED], [OPTIONAL]
   - Proactively share with relevant team members
   - Update research based on implementation feedback

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Project Technologies: {', '.join(spec.project.main_tech)}
Project Type: {spec.project.type}

**IMMEDIATE ACTIONS**:
1. Type `@` to discover available MCP resources
2. Type `/` to discover available MCP commands (look for /mcp__ prefixed commands)
3. Document discovered tools in `research/available-tools.md`
4. Create research strategy based on available tools
5. Begin Phase 1 research aligned with implementation

Report findings to:
- Developer (implementation guidance)
- PM (risk assessment)
- Tester (security/performance testing)
- DevOps (infrastructure decisions)

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_context_management_instructions(role)}"""

        elif role == 'documentation_writer':
            return f"""{mandatory_reading}{context_note}{team_locations}You are the Documentation Writer for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Documentation Priorities:
- API documentation
- Setup and installation guides
- Architecture documentation
- User guides
- Code comments and docstrings

Project Context:
- Technologies: {', '.join(spec.project.main_tech)}
- Type: {spec.project.type}
{mcp_guidance}
Documentation Standards:
1. Clear and concise writing
2. Code examples where helpful
3. Diagrams for complex concepts
4. Keep docs in sync with code
5. Version documentation with releases

Start by:
1. Reviewing existing documentation
2. Identifying documentation gaps
3. Creating a documentation plan
4. Beginning with setup/installation docs

Coordinate with:
- Developer on implementation details
- PM on documentation priorities
- Tester on testing procedures"""

        else:
            # Fallback for any undefined roles
            return f"""{mandatory_reading}{context_note}{team_locations}You are a team member for {spec.project.name}.

Your role: {role}

General responsibilities:
- Support the team's goals
- Communicate progress regularly
- Maintain high quality standards
- Follow project conventions

Start by:
1. Understanding the project and your role
2. Reviewing the specification
3. Coordinating with the Project Manager

Report to PM (window 1) for specific task assignments."""

    def discover_mcp_servers(self) -> Dict[str, Any]:
        """Discover MCP servers from ~/.claude.json and project .mcp.json
        
        Returns a dict with:
        - servers: Dict of server name -> config
        - project_has_mcp: bool indicating if project has .mcp.json
        """
        mcp_info = {
            'servers': {},
            'project_has_mcp': False
        }
        
        # Check global ~/.claude.json
        global_claude = Path.home() / '.claude.json'
        if global_claude.exists():
            try:
                with open(global_claude, 'r') as f:
                    claude_config = json.load(f)
                    
                # Extract MCP servers
                if 'mcpServers' in claude_config:
                    mcp_info['servers'].update(claude_config['mcpServers'])
                    console.print(f"[green]✓ Found {len(claude_config['mcpServers'])} MCP servers in global config[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not parse ~/.claude.json: {e}[/yellow]")
        
        # Check project-local .mcp.json
        project_mcp = self.project_path / '.mcp.json'
        if project_mcp.exists():
            mcp_info['project_has_mcp'] = True
            try:
                with open(project_mcp, 'r') as f:
                    project_config = json.load(f)
                    
                # Extract MCP servers (could be in different format)
                if 'mcpServers' in project_config:
                    mcp_info['servers'].update(project_config['mcpServers'])
                elif isinstance(project_config, dict):
                    # Assume top-level keys are server configs
                    mcp_info['servers'].update(project_config)
                    
                console.print(f"[green]✓ Found project-specific MCP config[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not parse project .mcp.json: {e}[/yellow]")
        
        return mcp_info
    
    def categorize_mcp_tools(self, servers: Dict[str, Any]) -> Dict[str, List[str]]:
        """Categorize MCP servers by their likely purpose based on name and config
        
        Returns dict with categories like:
        - filesystem: Local file operations
        - web_search: Web search capabilities  
        - web_scraping: Content extraction
        - database: Database operations
        - knowledge: Knowledge bases
        - automation: Browser/task automation
        """
        categories = {
            'filesystem': [],
            'web_search': [],
            'web_scraping': [],
            'database': [],
            'knowledge': [],
            'automation': [],
            'other': []
        }
        
        # Categorize based on server names and commands
        for server_name, config in servers.items():
            lower_name = server_name.lower()
            
            # Check command if available
            command = ''
            if isinstance(config, dict) and 'command' in config:
                command = config['command'].lower()
            
            # Categorize based on name patterns
            if any(term in lower_name for term in ['filesystem', 'file', 'fs']):
                categories['filesystem'].append(server_name)
            elif any(term in lower_name for term in ['search', 'tavily', 'perplexity', 'google']):
                categories['web_search'].append(server_name)
            elif any(term in lower_name for term in ['firecrawl', 'scrape', 'crawl', 'fetch']):
                categories['web_scraping'].append(server_name)
            elif any(term in lower_name for term in ['sqlite', 'postgres', 'mysql', 'mongodb', 'database', 'db']):
                categories['database'].append(server_name)
            elif any(term in lower_name for term in ['context', 'knowledge', 'kb', 'rag']):
                categories['knowledge'].append(server_name)
            elif any(term in lower_name for term in ['puppeteer', 'playwright', 'selenium', 'browser']):
                categories['automation'].append(server_name)
            elif 'mcp-server-' in command:
                # Try to categorize by the mcp-server-X pattern in command
                if 'fetch' in command or 'http' in command:
                    categories['web_scraping'].append(server_name)
                elif 'sqlite' in command:
                    categories['database'].append(server_name)
                else:
                    categories['other'].append(server_name)
            else:
                categories['other'].append(server_name)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}
    
    def get_role_mcp_guidance(self, role: str, mcp_categories: Dict[str, List[str]]) -> str:
        """Get role-specific MCP tool recommendations
        
        Returns formatted guidance string for the role's briefing
        """
        if not mcp_categories:
            return "No MCP tools detected. Proceed with standard development practices."
        
        # Format available tools
        tools_summary = []
        for category, servers in mcp_categories.items():
            tools_summary.append(f"**{category.replace('_', ' ').title()}**: {', '.join(servers)}")
        
        tools_list = '\n   - '.join([''] + tools_summary)
        
        # Role-specific guidance
        if role == 'researcher':
            return f"""🔧 **Available MCP Tools Detected**:{tools_list}

**Research Strategy Based on Available Tools**:
{self._get_researcher_strategy(mcp_categories)}

Remember: Use `@` to see resources and `/` to see commands in Claude Code."""
        
        elif role == 'developer':
            guidance = f"""🔧 **Available MCP Tools**:{tools_list}

**Development Recommendations**:"""
            if 'filesystem' in mcp_categories:
                guidance += "\n- Use filesystem MCP for advanced file operations"
            if 'database' in mcp_categories:
                guidance += "\n- Leverage database MCP for schema exploration and testing"
            if 'knowledge' in mcp_categories:
                guidance += "\n- Query knowledge base for implementation patterns"
            return guidance
        
        elif role == 'tester':
            guidance = f"""🔧 **Available MCP Tools**:{tools_list}

**Testing Recommendations**:"""
            if 'web_scraping' in mcp_categories:
                guidance += "\n- Use web scraping tools to verify external integrations"
            if 'automation' in mcp_categories:
                guidance += "\n- Leverage browser automation for E2E testing"
            if 'database' in mcp_categories:
                guidance += "\n- Use database tools for test data management"
            return guidance
        
        elif role == 'orchestrator':
            return f"""🔧 **MCP Tools Inventory** (share with team):{tools_list}

**IMMEDIATE ACTION**: Create `mcp-inventory.md` in the MAIN PROJECT directory (not your worktree) at:
`{self.project_path}/mcp-inventory.md`

This ensures all agents can access it. Create with:
```markdown
# MCP Tools Inventory

## Available Tools
{chr(10).join(f'### {cat.replace("_", " ").title()}{chr(10)}- ' + chr(10).join(f'- {s}' for s in servers) for cat, servers in mcp_categories.items())}

## Role Recommendations
- **Developer**: {', '.join(mcp_categories.get('filesystem', []) + mcp_categories.get('database', [])[:1])}
- **Researcher**: {', '.join(mcp_categories.get('web_search', []) + mcp_categories.get('web_scraping', [])[:2])}
- **Tester**: {', '.join(mcp_categories.get('automation', []) + mcp_categories.get('database', [])[:1])}

## Usage Notes
- Type `@` in Claude Code to see available resources
- Type `/` to see available commands (look for /mcp__ prefixed commands)
```

Share this inventory with all team members by telling them:
"I've created the MCP tools inventory at {self.project_path}/mcp-inventory.md - please review it for available tools."

This file is in the main project directory, accessible to all agents."""
        
        else:
            return f"""🔧 **Available MCP Tools**:{tools_list}

Leverage these tools as appropriate for your role."""
    
    def _get_researcher_strategy(self, categories: Dict[str, List[str]]) -> str:
        """Get specific research strategy based on available MCP tools"""
        strategies = []
        
        if 'web_search' in categories:
            strategies.append("""
**Web Search Strategy** (using {0}):
- Search for "[technology] best practices 2024"
- Look for "[technology] security vulnerabilities CVE"
- Find "[technology] performance optimization"
- Research "[technology] vs alternatives comparison"
- Query latest framework updates and breaking changes
""".format(', '.join(categories['web_search'])))
        
        if 'web_scraping' in categories:
            strategies.append("""
**Documentation Extraction** (using {0}):
- Scrape official documentation for latest API changes
- Extract code examples from tutorials
- Gather benchmarks and case studies
- Compile migration guides
""".format(', '.join(categories['web_scraping'])))
        
        if 'knowledge' in categories:
            strategies.append("""
**Knowledge Base Queries** (using {0}):
- Query architectural patterns
- Research edge cases and gotchas
- Find historical context
- Discover advanced techniques
""".format(', '.join(categories['knowledge'])))
        
        if 'database' in categories:
            strategies.append("""
**Database Analysis** (using {0}):
- Analyze schema best practices
- Research indexing strategies
- Find optimization patterns
- Query performance tips
""".format(', '.join(categories['database'])))
        
        return '\n'.join(strategies) if strategies else "Focus on code analysis and standard research methods."
    
    def setup_mcp_for_worktree(self, worktree_path: Path):
        """Merge parent project's MCP config into worktree's .mcp.json"""
        
        # Read parent project's MCP config from ~/.claude.json
        claude_json_path = Path.home() / '.claude.json'
        parent_mcp_servers = {}
        
        if claude_json_path.exists():
            try:
                with open(claude_json_path, 'r') as f:
                    claude_config = json.load(f)
                    project_key = str(self.project_path)
                    if project_key in claude_config.get('projects', {}):
                        parent_mcp_servers = claude_config['projects'][project_key].get('mcpServers', {})
                        if parent_mcp_servers:
                            console.print(f"[cyan]Found {len(parent_mcp_servers)} MCP servers in parent project config[/cyan]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not read parent MCP config: {e}[/yellow]")
        
        # Read existing .mcp.json from worktree
        worktree_mcp_path = worktree_path / '.mcp.json'
        existing_config = {}
        
        if worktree_mcp_path.exists():
            try:
                with open(worktree_mcp_path, 'r') as f:
                    existing_config = json.load(f)
                    if 'mcpServers' in existing_config:
                        console.print(f"[cyan]Found {len(existing_config.get('mcpServers', {}))} MCP servers in existing .mcp.json[/cyan]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not read existing .mcp.json: {e}[/yellow]")
        
        # If no parent MCP servers and no existing config, nothing to do
        if not parent_mcp_servers and not existing_config:
            return
        
        # Merge configurations
        merged_config = existing_config.copy() if existing_config else {"mcpServers": {}}
        
        # Ensure mcpServers key exists
        if "mcpServers" not in merged_config:
            merged_config["mcpServers"] = {}
        
        # Add parent's servers that don't conflict
        added_count = 0
        for server_name, server_config in parent_mcp_servers.items():
            if server_name not in merged_config["mcpServers"]:
                merged_config["mcpServers"][server_name] = server_config
                added_count += 1
        
        # Write the merged configuration
        if merged_config["mcpServers"] or existing_config:
            try:
                with open(worktree_mcp_path, 'w') as f:
                    json.dump(merged_config, f, indent=2)
                
                if added_count > 0:
                    console.print(f"[green]✓ Added {added_count} MCP servers from parent project[/green]")
                console.print(f"[green]  Total MCP servers in worktree: {len(merged_config['mcpServers'])}[/green]")
            except Exception as e:
                console.print(f"[red]Error writing merged .mcp.json: {e}[/red]")

    def enable_mcp_servers_in_claude_config(self, worktree_path: Path):
        """Enable MCP servers in Claude configuration for auto-approval"""
        
        # Read the worktree's .mcp.json to get server names
        worktree_mcp_path = worktree_path / '.mcp.json'
        server_names = []
        
        if worktree_mcp_path.exists():
            try:
                with open(worktree_mcp_path, 'r') as f:
                    mcp_config = json.load(f)
                    server_names = list(mcp_config.get('mcpServers', {}).keys())
            except Exception as e:
                console.print(f"[yellow]Warning: Could not read worktree .mcp.json: {e}[/yellow]")
                return
        
        if not server_names:
            return
        
        # Read current ~/.claude.json
        claude_json_path = Path.home() / '.claude.json'
        claude_config = {}
        
        if claude_json_path.exists():
            try:
                with open(claude_json_path, 'r') as f:
                    claude_config = json.load(f)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not read ~/.claude.json: {e}[/yellow]")
                return
        
        # Ensure projects section exists
        if 'projects' not in claude_config:
            claude_config['projects'] = {}
        
        # Add or update the worktree project entry
        worktree_key = str(worktree_path)
        
        if worktree_key not in claude_config['projects']:
            claude_config['projects'][worktree_key] = {
                "allowedTools": [],
                "history": [],
                "mcpContextUris": [],
                "mcpServers": {},
                "enabledMcpjsonServers": [],
                "disabledMcpjsonServers": [],
                "hasTrustDialogAccepted": True,
                "projectOnboardingSeenCount": 0,
                "hasClaudeMdExternalIncludesApproved": False,
                "hasClaudeMdExternalIncludesWarningShown": False
            }
        
        # Update enabledMcpjsonServers with all server names
        project_config = claude_config['projects'][worktree_key]
        project_config['enabledMcpjsonServers'] = server_names
        project_config['hasTrustDialogAccepted'] = True
        
        # Backup original file
        backup_path = claude_json_path.with_suffix('.json.bak')
        try:
            if claude_json_path.exists():
                import shutil
                shutil.copy2(claude_json_path, backup_path)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not create backup: {e}[/yellow]")
        
        # Write updated configuration
        try:
            with open(claude_json_path, 'w') as f:
                json.dump(claude_config, f, indent=2)
            
            console.print(f"[green]✓ Auto-enabled {len(server_names)} MCP servers for worktree[/green]")
            console.print(f"[green]  Servers: {', '.join(server_names)}[/green]")
        except Exception as e:
            console.print(f"[red]Error updating ~/.claude.json: {e}[/red]")
            # Try to restore backup
            if backup_path.exists():
                try:
                    import shutil
                    shutil.copy2(backup_path, claude_json_path)
                    console.print("[yellow]Restored backup file[/yellow]")
                except:
                    pass

    def create_git_sync_instructions(self, role: str, spec: ImplementationSpec, worktree_paths: Dict[str, Path] = None) -> str:
        """Create role-specific git synchronization instructions
        
        Returns formatted instructions for keeping in sync with other team members
        """
        
        # Base sync instructions for all roles
        base_instructions = f"""
🔄 **Git Synchronization Protocol**

Working in isolated worktrees with **agent-specific branches** means you MUST regularly sync with your teammates' changes:

**Branch Structure**:
- Each agent works on their own branch to prevent conflicts
- Developer: `{spec.git_workflow.branch_name}`
- Tester: `{spec.git_workflow.branch_name}-tester`  
- PM: `pm-{spec.git_workflow.branch_name}`
- TestRunner: `{spec.git_workflow.branch_name}-testrunner`
- Other agents: `{spec.git_workflow.branch_name}-{{role}}`

**When to Sync**:
- 🌅 Start of each work session
- 📋 Before starting new features/tests
- ⏰ Every hour during active development
- 🔍 Before code reviews or testing
- 📢 When teammates announce pushes via PM/Orchestrator

**Cross-Branch Sync Commands**:
```bash
# Check for updates from all agent branches
git fetch origin

# See what agent branches exist
git branch -r | grep -E "{spec.git_workflow.branch_name}|pm-{spec.git_workflow.branch_name}"

# Merge specific agent's work into your branch
git merge origin/[agent-branch-name]

# Example: Tester getting Developer's changes
git merge origin/{spec.git_workflow.branch_name}
```

**Communication Flow**:
- Report pushes to PM → PM tells Orchestrator → Orchestrator notifies affected agents
- Never assume other agents see your terminal announcements
"""
        
        # Role-specific sync instructions
        if role == 'developer':
            role_specific = f"""
**Developer Sync Strategy**:
1. **Before Starting Work**:
   ```bash
   # Pull PM's review feedback
   git fetch origin
   git merge origin/pm-{spec.git_workflow.branch_name} 2>/dev/null || true
   
   # Check for test updates from Tester
   git merge origin/{spec.git_workflow.branch_name}-tester 2>/dev/null || true
   ```

2. **After Major Commits**:
   ```bash
   # Push your work for others
   git push -u origin {spec.git_workflow.branch_name}
   
   # Report to PM for distribution
   # "PM: Pushed authentication module to {spec.git_workflow.branch_name} - ready for testing"
   ```

3. **Collaboration Tips**:
   - Your branch is the main implementation branch
   - Other agents will merge FROM your branch
   - Always push after completing a module
   - Tag stable points: `git tag dev-stable-$(date +%Y%m%d-%H%M)`
"""
        
        elif role == 'tester':
            role_specific = f"""
**Tester Sync Strategy**:
1. **Before Writing Tests**:
   ```bash
   # ALWAYS pull Developer's latest code first
   git fetch origin
   git merge origin/{spec.git_workflow.branch_name}
   
   # Check TestRunner's execution results if available
   git merge origin/{spec.git_workflow.branch_name}-testrunner 2>/dev/null || true
   ```

2. **Test Development Workflow**:
   ```bash
   # Work on your agent branch
   git checkout -b {spec.git_workflow.branch_name}-tester
   
   # After writing tests, push immediately
   git add tests/
   git commit -m "test: add integration tests for [module]"
   git push -u origin {spec.git_workflow.branch_name}-tester
   
   # Report to PM: "Pushed new tests to {spec.git_workflow.branch_name}-tester"
   ```

3. **Cross-Reference Testing**:
   - Can also read directly from Developer's worktree:
     ```bash
     # View implementation without merging
     cat {worktree_paths.get('developer', '../developer')}/src/module.py
     ```
"""
        
        elif role == 'project_manager':
            role_specific = f"""
**PM Sync Orchestration**:
1. **Regular Team Sync Check** (every 30 min):
   ```bash
   # Pull from ALL team members
   git fetch origin --all
   
   # List all agent branches
   git branch -r | grep -E "{spec.git_workflow.branch_name}|pm-{spec.git_workflow.branch_name}"
   
   # Check each agent's progress
   for branch in $(git branch -r | grep -E "{spec.git_workflow.branch_name}"); do
     echo "=== Changes in $branch ==="
     git log --oneline origin/{spec.git_workflow.parent_branch}..$branch
   done
   ```

2. **Cross-Agent Merge Coordination**:
   ```bash
   # When Developer pushes important changes
   # Notify affected agents via Orchestrator:
   # "Orchestrator: Please tell Tester to merge origin/{spec.git_workflow.branch_name}"
   
   # Track merge status
   git merge origin/{spec.git_workflow.branch_name}  # Developer's work
   git merge origin/{spec.git_workflow.branch_name}-tester  # Tester's work
   ```

3. **Push Announcement Protocol**:
   - Receive push notifications from all agents
   - Determine which agents need the updates
   - Request Orchestrator to notify specific agents
   - Example: "Orchestrator: Developer pushed auth changes. Please notify Tester and TestRunner to merge origin/{spec.git_workflow.branch_name}"
   
4. **Final Integration**:
   - Eventually merge all agent branches to create unified PR
   - Resolve conflicts between agent-specific branches
"""
        
        elif role == 'testrunner':
            role_specific = f"""
**TestRunner Sync Protocol**:
1. **Before Test Execution**:
   ```bash
   # Get latest code AND tests
   git fetch origin
   git merge origin/{spec.git_workflow.branch_name}  # Developer code
   git merge origin/{spec.git_workflow.branch_name}-tester  # Test suites
   ```

2. **Working on Your Branch**:
   ```bash
   # Create/switch to your agent branch
   git checkout -b {spec.git_workflow.branch_name}-testrunner
   ```

3. **Share Results**:
   ```bash
   # After test runs, commit results
   git add test-results/
   git commit -m "test-results: [timestamp] - X passed, Y failed"
   git push -u origin {spec.git_workflow.branch_name}-testrunner
   
   # Report to PM: "Test results pushed to {spec.git_workflow.branch_name}-testrunner: X passed, Y failed"
   ```
"""
        
        elif role == 'researcher':
            role_specific = f"""
**Researcher Sync Needs**:
1. **Stay Current with Implementation**:
   ```bash
   # Regular sync to research relevant topics
   git fetch origin
   git merge origin/{spec.git_workflow.branch_name}
   ```

2. **Share Research Findings**:
   ```bash
   # Push research docs for team
   git add research/
   git commit -m "research: security analysis for auth module"
   git push -u origin research-{spec.git_workflow.branch_name}
   ```
"""
        
        else:
            # Generic role-specific instructions
            role_specific = f"""
**{role.title()} Sync Guidelines**:
1. Fetch updates at session start: `git fetch origin`
2. Merge relevant branches based on your dependencies
3. Push your work regularly for team visibility
4. Coordinate with PM for merge timing
"""
        
        # Communication integration
        communication = f"""
**🔔 Sync Communication**:
When you pull important updates, notify relevant teammates:
```bash
# After pulling critical updates
cd {self.tmux_orchestrator_path}
./send-claude-message.sh pm:1 "Merged latest auth module changes, found 3 test failures"
./send-claude-message.sh developer:1 "Pulled your changes - the API endpoints look good!"
```

**⚠️ Merge Conflict Resolution**:
If you encounter conflicts:
1. Don't panic - conflicts are normal in parallel development
2. Notify PM immediately for coordination
3. Preserve both changes when unclear
4. Test thoroughly after resolution
"""
        
        return base_instructions + role_specific + communication

    def create_context_management_instructions(self, role: str) -> str:
        """Create context management instructions for agents to self-recover"""
        
        return f"""
📊 **Context Management Protocol**

Working in multi-agent systems uses ~15x more tokens than normal. You MUST actively manage your context:

**Signs of Context Degradation**:
- Feeling confused or repeating questions
- Forgetting earlier work or decisions  
- Working continuously for 2+ hours
- Making similar files multiple times

**Self-Recovery Process**:
1. **Create Checkpoint** (BEFORE /compact):
   ```bash
   cat > {role.upper()}_CHECKPOINT_$(date +%Y%m%d_%H%M).md << 'EOF'
   ## Context Checkpoint - {role.title()}
   - Current task: [what you're working on]
   - Branch: $(git branch --show-current)
   - Recent work: [what you just completed]
   - Next steps: [specific next actions]
   - Key context: [important facts to remember]
   EOF
   ```

2. **Clear Context**:
   Type the following and press Enter:
   ```
   /compact
   ```

3. **Reload Essential Context**:
   ```
   # Option A: If available
   /context-prime
   
   # Option B: Manual reload
   Read {self.tmux_orchestrator_path}/CLAUDE.md
   Read README.md  
   Read {role.upper()}_CHECKPOINT_*.md  # Your checkpoint
   git status && git log --oneline -5
   ```

4. **Verify & Continue**:
   - Confirm understanding of current task
   - Check git branch is correct
   - Continue from checkpoint next steps

**Proactive Context Health**:
- Create checkpoints every 2 hours
- Run /compact at natural break points (phase transitions, major commits)
- Always checkpoint before starting new phases
- If you notice confusion, compact immediately

**Emergency Recovery**:
If confused after /compact, read in order:
1. CLAUDE.md (your role and git rules)
2. Your latest checkpoint/handoff document
3. Recent git commits
4. Ask orchestrator for clarification

Remember: It's better to compact proactively than to hit context exhaustion!"""

    def pre_initialize_claude_in_worktree(self, session_name: str, window_idx: int, role_key: str, worktree_path: Path):
        """Pre-initialize Claude to auto-approve MCP servers"""
        
        # Check if worktree has .mcp.json
        mcp_json_path = worktree_path / '.mcp.json'
        if not mcp_json_path.exists():
            return False
        
        console.print(f"[cyan]Pre-initializing Claude for {role_key} to approve MCP servers...[/cyan]")
        
        # Start Claude normally (without --dangerously-skip-permissions)
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            'claude', 'Enter'
        ])
        
        # Wait for MCP server prompt to appear
        time.sleep(2)
        
        # Press Enter to accept default selections (all servers selected by default)
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            'Enter'
        ])
        
        # Wait for Claude to fully start
        time.sleep(2)
        
        # Press Escape to ensure we're not in any input mode
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            'Escape'
        ])
        
        # Small delay
        time.sleep(0.5)
        
        # Exit Claude
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            '/exit', 'Enter'
        ])
        
        # Wait for Claude to process the exit command
        time.sleep(1)
        
        # Don't print completion since we'll kill the pane
        return True

    def run(self):
        """Main execution flow"""
        console.print(Panel.fit(
            "[bold]Auto-Orchestrate[/bold]\n"
            "Automated Tmux Orchestrator Setup",
            border_style="cyan"
        ))
        
        # Ensure Tmux Orchestrator is set up
        self.ensure_setup()
        
        # Check dependencies
        self.check_dependencies()
        
        # Ensure tmux server is running
        self.ensure_tmux_server()
        
        # Validate inputs
        if not self.project_path.exists():
            console.print(f"[red]Error: Project path does not exist: {self.project_path}[/red]")
            console.print("[yellow]Please provide a valid path to your project directory.[/yellow]")
            sys.exit(1)
            
        if not self.spec_path.exists():
            console.print(f"[red]Error: Spec file does not exist: {self.spec_path}[/red]")
            console.print("[yellow]Please provide a valid path to your specification markdown file.[/yellow]")
            sys.exit(1)
        
        # Analyze spec with Claude
        console.print("\n[cyan]Step 1:[/cyan] Analyzing specification with Claude...")
        spec_dict = self.analyze_spec_with_claude()
        
        # Parse into Pydantic model
        try:
            self.implementation_spec = ImplementationSpec(**spec_dict)
        except Exception as e:
            console.print(f"[red]Error parsing implementation spec: {e}[/red]")
            console.print("[yellow]Raw response:[/yellow]")
            console.print(JSON(json.dumps(spec_dict, indent=2)))
            console.print("\n[yellow]This usually means Claude's response wasn't in the expected JSON format.[/yellow]")
            console.print("Try simplifying your specification or breaking it into smaller parts.")
            sys.exit(1)
        
        # Display plan and get approval
        console.print("\n[cyan]Step 2:[/cyan] Review implementation plan...")
        if not self.display_implementation_plan(self.implementation_spec):
            console.print("[yellow]Setup cancelled by user.[/yellow]")
            sys.exit(0)
        
        # Discover MCP servers
        console.print("\n[cyan]Step 3:[/cyan] Discovering MCP servers...")
        mcp_info = self.discover_mcp_servers()
        mcp_categories = self.categorize_mcp_tools(mcp_info['servers']) if mcp_info['servers'] else {}
        
        if mcp_categories:
            console.print("[green]✓ MCP tools available for enhanced capabilities[/green]")
        else:
            console.print("[yellow]No MCP servers configured - agents will use standard tools[/yellow]")
        
        # Store for later use
        self.mcp_categories = mcp_categories
        
        # Set up tmux session
        console.print("\n[cyan]Step 4:[/cyan] Setting up tmux orchestration...")
        
        # Check for existing session and worktrees
        session_name = self.implementation_spec.project.name.lower().replace(' ', '-')[:20] + "-impl"
        project_name = self.implementation_spec.project.name.lower().replace(' ', '-')
        roles_to_deploy = self.get_roles_for_project_size(self.implementation_spec)
        
        existing_session = self.check_existing_session(session_name)
        existing_worktrees = self.check_existing_worktrees(project_name, roles_to_deploy)
        
        if existing_session or existing_worktrees:
            if self.force:
                # Force mode - automatically overwrite
                console.print("\n[yellow]⚠️  Force mode: Overwriting existing orchestration[/yellow]")
                if existing_session:
                    console.print(f"[yellow]Killing existing session '{session_name}'...[/yellow]")
                    subprocess.run(['tmux', 'kill-session', '-t', session_name], capture_output=True)
            else:
                # Interactive mode - prompt user
                console.print("\n[yellow]⚠️  Existing orchestration detected![/yellow]")
                
                if existing_session:
                    console.print(f"[yellow]• Tmux session '{session_name}' already exists[/yellow]")
                    
                if existing_worktrees:
                    console.print(f"[yellow]• Found existing worktrees for: {', '.join(existing_worktrees)}[/yellow]")
                
                console.print("\n[bold]What would you like to do?[/bold]")
                console.print("1. [red]Overwrite[/red] - Remove existing session/worktrees and start fresh")
                console.print("2. [green]Resume[/green] - Attach to existing session (keep worktrees)")
                console.print("3. [yellow]Cancel[/yellow] - Exit without changes")
                
                while True:
                    choice = click.prompt("\nYour choice", type=click.Choice(['1', '2', '3']), default='3')
                    
                    if choice == '1':
                        # Overwrite
                        if existing_session:
                            console.print(f"[yellow]Killing existing session '{session_name}'...[/yellow]")
                            subprocess.run(['tmux', 'kill-session', '-t', session_name], capture_output=True)
                        break
                        
                    elif choice == '2':
                        # Resume
                        if existing_session:
                            console.print(f"\n[green]✓ Resuming existing session![/green]")
                            console.print(f"To attach: [cyan]tmux attach -t {session_name}[/cyan]")
                            sys.exit(0)
                        else:
                            console.print("[red]No existing session to resume. Creating new session...[/red]")
                            break
                            
                    elif choice == '3':
                        # Cancel
                        console.print("[yellow]Operation cancelled.[/yellow]")
                        sys.exit(0)
        
        self.setup_tmux_session(self.implementation_spec)
        
        # Save implementation spec for reference
        registry_dir = self.tmux_orchestrator_path / 'registry' / 'projects' / self.implementation_spec.project.name.lower().replace(' ', '-')
        registry_dir.mkdir(parents=True, exist_ok=True)
        
        spec_file = registry_dir / 'implementation_spec.json'
        spec_file.write_text(json.dumps(spec_dict, indent=2))
        
        console.print(f"\n[green]✓ Setup complete![/green]")
        console.print(f"Implementation spec saved to: {spec_file}")


@click.command()
@click.option('--project', '-p', required=True, type=click.Path(exists=True), 
              help='Path to the GitHub project')
@click.option('--spec', '-s', required=True, type=click.Path(exists=True),
              help='Path to the specification markdown file')
@click.option('--size', type=click.Choice(['auto', 'small', 'medium', 'large']), 
              default='auto', help='Project size (auto-detect by default)')
@click.option('--roles', multiple=True, 
              help='Additional roles to include (e.g., --roles researcher --roles documentation_writer)')
@click.option('--force', '-f', is_flag=True,
              help='Force overwrite existing session/worktrees without prompting')
@click.option('--plan', type=click.Choice(['auto', 'pro', 'max5', 'max20', 'console']), 
              default='auto', help='Claude subscription plan (affects team size limits)')
def main(project: str, spec: str, size: str, roles: tuple, force: bool, plan: str):
    """Automatically set up a Tmux Orchestrator environment from a specification.
    
    The script will analyze your specification and set up a complete tmux
    orchestration environment with AI agents based on project size:
    
    OPTIMIZED FOR CLAUDE CODE MAX 5X PLAN:
    - Small projects: 3 agents (Orchestrator + Developer + Researcher)
    - Medium projects: 4 agents (+ Project Manager)
    - Large projects: 5 agents (+ Tester or DevOps)
    
    Multi-agent systems use ~15x more tokens than standard usage.
    Use --plan to specify your subscription for appropriate team sizing.
    
    You can manually specify project size with --size or add specific roles
    with --roles (e.g., --roles documentation_writer)
    """
    orchestrator = AutoOrchestrator(project, spec)
    orchestrator.manual_size = size if size != 'auto' else None
    orchestrator.additional_roles = list(roles) if roles else []
    orchestrator.force = force
    orchestrator.plan_type = plan if plan != 'auto' else 'max20'  # Default to max20
    orchestrator.run()


if __name__ == '__main__':
    main()
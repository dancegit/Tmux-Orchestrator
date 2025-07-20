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
      "check_in_interval": 30,
      "initial_commands": ["cd {self.tmux_orchestrator_path}", "python3 claude_control.py status detailed"]
    }},
    "project_manager": {{
      "responsibilities": ["Ensure quality", "Track completion", "Review coverage"],
      "check_in_interval": 30,
      "initial_commands": ["cd {self.project_path}", "cat {self.spec_path.relative_to(self.project_path) if self.spec_path.is_relative_to(self.project_path) else self.spec_path}"]
    }},
    "developer": {{
      "responsibilities": ["Implement features", "Write tests", "Fix bugs"],
      "check_in_interval": 60,
      "initial_commands": ["cd {self.project_path}", "git status"]
    }},
    "tester": {{
      "responsibilities": ["Run tests", "Report failures", "Verify coverage"],
      "check_in_interval": 45,
      "initial_commands": ["cd {self.project_path}", "echo 'Ready to test'"]
    }},
    "devops": {{
      "responsibilities": ["Infrastructure setup", "Deployment pipelines", "Monitor performance"],
      "check_in_interval": 90,
      "initial_commands": ["cd {self.project_path}", "echo 'Checking deployment configuration'"]
    }},
    "code_reviewer": {{
      "responsibilities": ["Review code quality", "Security audit", "Best practices enforcement"],
      "check_in_interval": 120,
      "initial_commands": ["cd {self.project_path}", "git log --oneline -10"]
    }},
    "researcher": {{
      "responsibilities": ["MCP tool discovery and utilization", "Research best practices", "Security vulnerability analysis", "Performance optimization research", "Document actionable findings"],
      "check_in_interval": 45,
      "initial_commands": ["cd {self.project_path}", "echo 'Discovering available MCP tools...'", "echo 'Run /mcp to see available research tools'"]
    }},
    "documentation_writer": {{
      "responsibilities": ["Write technical docs", "Update README", "Create API documentation"],
      "check_in_interval": 120,
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
        
        return Confirm.ask("\n[bold]Proceed with automated setup?[/bold]", default=False)
    
    def get_roles_for_project_size(self, spec: ImplementationSpec) -> List[Tuple[str, str]]:
        """Determine which roles to deploy based on project size"""
        # Always include orchestrator and project manager
        base_roles = [
            ('Orchestrator', 'orchestrator'),
            ('Project-Manager', 'project_manager')
        ]
        
        # Use manual size override if provided
        size = self.manual_size if self.manual_size else spec.project_size.size
        
        if size == "small":
            # Small projects: PM + Developer + Researcher
            core_roles = base_roles + [
                ('Developer', 'developer'),
                ('Researcher', 'researcher')
            ]
        elif size == "medium":
            # Medium projects: PM + 2 Developers + Researcher + QA
            core_roles = base_roles + [
                ('Developer', 'developer'),
                ('Developer-2', 'developer'),  # Second developer
                ('Researcher', 'researcher'),
                ('Tester', 'tester')
            ]
        else:  # large
            # Large projects: Full team including specialized roles
            core_roles = base_roles + [
                ('Lead-Developer', 'developer'),
                ('Developer-2', 'developer'),
                ('Researcher', 'researcher'),
                ('Tester', 'tester'),
                ('DevOps', 'devops'),
                ('Code-Reviewer', 'code_reviewer')
            ]
        
        # Add any additional requested roles
        role_mapping = {
            'researcher': ('Researcher', 'researcher'),
            'documentation_writer': ('Documentation', 'documentation_writer'),
            'documentation': ('Documentation', 'documentation_writer'),
            'docs': ('Documentation', 'documentation_writer')
        }
        
        for role in self.additional_roles:
            if role.lower() in role_mapping:
                core_roles.append(role_mapping[role.lower()])
        
        return core_roles
    
    def setup_worktrees(self, spec: ImplementationSpec, roles_to_deploy: List[Tuple[str, str]]) -> Dict[str, Path]:
        """Create git worktrees for each agent"""
        # Verify project is a git repo
        if not (self.project_path / '.git').exists():
            console.print("[red]Error: Project must be a git repository to use orchestration[/red]")
            console.print("[yellow]Please initialize git in your project: cd {self.project_path} && git init[/yellow]")
            sys.exit(1)
        
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
                
                # Remove existing worktree if it exists
                if worktree_path.exists():
                    subprocess.run(['rm', '-rf', str(worktree_path)], capture_output=True)
                    # Also remove from git worktree list
                    subprocess.run(['git', 'worktree', 'prune'], 
                                 cwd=str(self.project_path), capture_output=True)
                
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
                
                if not worktree_created:
                    console.print(f"[red]Failed to create worktree for {role_key} after all strategies[/red]")
                    console.print(f"[red]Error: {result.stderr}[/red]")
                    sys.exit(1)
                    
                worktree_paths[role_key] = worktree_path
                progress.update(task, advance=1, description=f"Created worktree for {role_key}")
        
        # Display worktree summary
        console.print("\n[green]✓ Git worktrees created:[/green]")
        for role, path in worktree_paths.items():
            console.print(f"  {role}: {path.relative_to(self.tmux_orchestrator_path)}")
        
        return worktree_paths
    
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
            # Start Claude
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
                                                worktree_paths=worktree_paths)
            
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
                schedule_script = self.tmux_orchestrator_path / 'schedule_with_note.sh'
                subprocess.run([
                    str(schedule_script),
                    str(role_config.check_in_interval),
                    f"{window_name} regular check-in",
                    f"{session_name}:{window_idx}"
                ])
    
    def create_role_briefing(self, role: str, spec: ImplementationSpec, role_config: RoleConfig, 
                           context_primed: bool = True, roles_deployed: List[Tuple[str, str]] = None,
                           worktree_paths: Dict[str, Path] = None) -> str:
        """Create a role-specific briefing message"""
        
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
        
        if role == 'orchestrator':
            tool_path = self.tmux_orchestrator_path
            return f"""{mandatory_reading}You are the Orchestrator for {spec.project.name}.

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

Schedule your first check-in for {role_config.check_in_interval} minutes from the tool directory."""

        elif role == 'project_manager':
            return f"""{mandatory_reading}{context_note}You are the Project Manager for {spec.project.name}.

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Implementation Phases:
{chr(10).join(f'{i+1}. {p.name} ({p.duration_hours}h)' for i, p in enumerate(spec.implementation_plan.phases))}

Success Criteria:
{chr(10).join(f'- {c}' for c in spec.success_criteria)}

Git Workflow:
- CRITICAL: Project started on branch '{spec.git_workflow.parent_branch}'
- Feature branch: {spec.git_workflow.branch_name} (created from {spec.git_workflow.parent_branch})
- MERGE ONLY TO: {spec.git_workflow.parent_branch} (NOT main unless parent is main!)
- Commit every {spec.git_workflow.commit_interval} minutes
- PR Title: {spec.git_workflow.pr_title}

Your Team (based on project size: {spec.project_size.size}):
{team_description}

🔍 **Researcher Available**: Check with the Researcher for best practices, security analysis, and performance recommendations before making critical decisions.

Always report to Orchestrator (window 0)

Maintain EXCEPTIONAL quality standards. No compromises."""

        elif role == 'developer':
            return f"""{mandatory_reading}{context_note}You are the Developer for {spec.project.name}.

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Project Details:
- Path: {spec.project.path}
- Type: {spec.project.type}
- Technologies: {', '.join(spec.project.main_tech)}

Implementation Phases:
{chr(10).join(f'{i+1}. {p.name}: {", ".join(p.tasks[:2])}...' for i, p in enumerate(spec.implementation_plan.phases))}

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

Start by:
1. Reading the spec at: {self.spec_path}
2. 🔍 **Check with Researcher** for best practices and security considerations
3. Setting up your development environment
4. Creating the feature branch
5. Beginning implementation of Phase 1

Collaborate with:
- PM (window 1) for progress updates
- Researcher for technical guidance and best practices
- Tester for early testing feedback"""

        elif role == 'tester':
            return f"""{mandatory_reading}{context_note}You are the Tester for {spec.project.name}.

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Testing Focus:
- Technologies: {', '.join(spec.project.main_tech)}
- Ensure all success criteria are met:
{chr(10).join(f'  - {c}' for c in spec.success_criteria)}

Your workflow:
1. Monitor Developer (window 2) progress
2. Run tests after each commit
3. Report failures immediately to PM and Developer
4. Track test coverage metrics
5. Verify no regressions occur

Start by:
1. Understanding the existing test structure
2. 🔍 **Consult Researcher** for security testing strategies and performance benchmarks
3. Setting up test environment
4. Running current test suite as baseline

Collaborate with:
- Developer for implementation details
- Researcher for security vulnerabilities and testing best practices
- PM for quality standards"""

        elif role == 'devops':
            return f"""{mandatory_reading}{context_note}You are the DevOps Engineer for {spec.project.name}.

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Project Infrastructure:
- Type: {spec.project.type}
- Technologies: {', '.join(spec.project.main_tech)}
- Path: {spec.project.path}

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
- 🔍 **Researcher** for infrastructure best practices and security hardening"""

        elif role == 'code_reviewer':
            return f"""{mandatory_reading}{context_note}You are the Code Reviewer for {spec.project.name}.

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Review Focus:
- Code quality and maintainability
- Security vulnerabilities
- Performance implications
- Adherence to project conventions
- Test coverage

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
            return f"""{mandatory_reading}{context_note}You are the Technical Researcher for {spec.project.name}.

🔍 **CRITICAL MCP TOOL DISCOVERY WORKFLOW**:

1. **Initialize Research Environment**:
   ```
   /context-prime  # If available, to understand the project
   /mcp           # ESSENTIAL: Discover available MCP tools
   ```
   
2. **Document Available Tools**:
   After running `/mcp`, create `research/available-tools.md` listing:
   - Which MCP servers are connected
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
   └── phase-{n}-research.md      # Phase-specific findings
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
1. Run `/mcp` to discover tools
2. Create research strategy based on available tools
3. Begin Phase 1 research aligned with implementation

Report findings to:
- Developer (implementation guidance)
- PM (risk assessment)
- Tester (security/performance testing)
- DevOps (infrastructure decisions)"""

        elif role == 'documentation_writer':
            return f"""{mandatory_reading}{context_note}You are the Documentation Writer for {spec.project.name}.

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
            return f"""{mandatory_reading}{context_note}You are a team member for {spec.project.name}.

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
        
        # Set up tmux session
        console.print("\n[cyan]Step 3:[/cyan] Setting up tmux orchestration...")
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
def main(project: str, spec: str, size: str, roles: tuple):
    """Automatically set up a Tmux Orchestrator environment from a specification.
    
    The script will analyze your specification and set up a complete tmux
    orchestration environment with AI agents based on project size:
    
    - Small projects: Orchestrator + PM + Developer + Researcher
    - Medium projects: + Second Developer + Tester
    - Large projects: + DevOps + Code Reviewer
    
    You can manually specify project size with --size or add specific roles
    with --roles (e.g., --roles documentation_writer)
    """
    orchestrator = AutoOrchestrator(project, spec)
    orchestrator.manual_size = size if size != 'auto' else None
    orchestrator.additional_roles = list(roles) if roles else []
    orchestrator.run()


if __name__ == '__main__':
    main()
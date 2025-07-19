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
from pathlib import Path
from typing import Dict, List, Optional, Any
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
    branch_name: str
    commit_interval: int
    pr_title: str

class ImplementationSpec(BaseModel):
    project: Project
    implementation_plan: ImplementationPlan
    roles: Dict[str, RoleConfig]
    git_workflow: GitWorkflow
    success_criteria: List[str]


class AutoOrchestrator:
    def __init__(self, project_path: str, spec_path: str):
        self.project_path = Path(project_path).resolve()
        self.spec_path = Path(spec_path).resolve()
        self.tmux_orchestrator_path = Path(__file__).parent
        self.implementation_spec: Optional[ImplementationSpec] = None
        
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
        
        # Check Claude CLI
        claude_result = subprocess.run(['which', 'claude'], capture_output=True)
        if claude_result.returncode != 0:
            errors.append("Claude CLI is not installed. Visit https://claude.ai/cli for installation instructions")
        
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
    
    def get_claude_version(self) -> Optional[str]:
        """Get the Claude CLI version"""
        try:
            result = subprocess.run(['claude', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                # Parse version from output like "claude version 1.0.22"
                version_line = result.stdout.strip()
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
        
        # Check if Claude version supports context priming
        supports_context_prime = self.check_claude_version()
        claude_version = self.get_claude_version()
        
        if not supports_context_prime and claude_version:
            console.print(f"[yellow]Note: Claude CLI v{claude_version} detected. Context priming requires v1.0.24+[/yellow]")
            console.print("[yellow]Continuing without context priming. Consider running: claude update[/yellow]\n")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            # Try context priming if supported
            if supports_context_prime:
                task = progress.add_task("Context priming Claude for project understanding...", total=None)
                
                # First, context prime Claude with the project
                context_prime_cmd = f'/context-prime "Analyze the project at {self.project_path} to understand its structure, technologies, and conventions"'
                
                # Create a script to run Claude with context priming
                context_script = f'''#!/bin/bash
cd "{self.project_path}"
echo "{context_prime_cmd}" | claude -c /dev/stdin
'''
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                    f.write(context_script)
                    context_script_file = f.name
                
                os.chmod(context_script_file, 0o755)
                
                try:
                    # Run context priming
                    result = subprocess.run(
                        ['bash', context_script_file],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    
                    if result.returncode != 0:
                        console.print(f"[yellow]Context priming skipped due to error[/yellow]")
                        supports_context_prime = False  # Disable for this run
                    
                except Exception as e:
                    console.print(f"[yellow]Context priming skipped: {str(e)}[/yellow]")
                    supports_context_prime = False
                finally:
                    os.unlink(context_script_file)
                
                progress.update(task, description="Analyzing specification with Claude...")
            else:
                task = progress.add_task("Analyzing specification with Claude...", total=None)
        
        # Create a prompt for Claude
        if supports_context_prime:
            prompt = f"""You are an AI project planning assistant. You have just analyzed the project at {self.project_path}. Now analyze the following specification and create a detailed implementation plan in JSON format."""
        else:
            prompt = f"""You are an AI project planning assistant. Analyze the following specification for the project at {self.project_path} and create a detailed implementation plan in JSON format."""
        
        prompt += f"""

PROJECT PATH: {self.project_path}
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
    }}
  }},
  "git_workflow": {{
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
- Ensure role responsibilities align with the implementation needs
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
                # Use claude CLI to analyze with the project as working directory
                result = subprocess.run(
                    ['claude', '-c', prompt_file],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(self.project_path)
                )
                
                if result.returncode != 0:
                    console.print(f"[red]Error running Claude: {result.stderr}[/red]")
                    console.print("\n[yellow]Troubleshooting tips:[/yellow]")
                    console.print("1. Ensure Claude CLI is installed: https://claude.ai/cli")
                    console.print("2. Check that you're logged in: claude auth status")
                    console.print("3. Try running manually: claude --help")
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
            f"Branch: [cyan]{spec.git_workflow.branch_name}[/cyan]\n"
            f"Commit Interval: Every {spec.git_workflow.commit_interval} minutes\n"
            f"PR Title: {spec.git_workflow.pr_title}",
            title="🔀 Git Workflow"
        ))
        
        return Confirm.ask("\n[bold]Proceed with automated setup?[/bold]", default=False)
    
    def setup_tmux_session(self, spec: ImplementationSpec):
        """Set up the tmux session with all roles"""
        session_name = spec.project.name.lower().replace(' ', '-')[:20] + "-impl"
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            # Create tmux session
            task = progress.add_task("Creating tmux session...", total=4)
            
            # Kill existing session if it exists
            subprocess.run(['tmux', 'kill-session', '-t', session_name], 
                         capture_output=True)
            
            # Create new session with orchestrator window
            subprocess.run([
                'tmux', 'new-session', '-d', '-s', session_name,
                '-n', 'Orchestrator', '-c', str(self.tmux_orchestrator_path)
            ], check=True)
            
            progress.update(task, advance=1, description="Created Orchestrator window...")
            
            # Create other role windows
            roles = [
                ('Project-Manager', 'project_manager'),
                ('Developer', 'developer'),
                ('Tester', 'tester')
            ]
            
            for window_name, role_key in roles:
                subprocess.run([
                    'tmux', 'new-window', '-t', session_name,
                    '-n', window_name, '-c', str(self.project_path)
                ], check=True)
                progress.update(task, advance=1, description=f"Created {window_name} window...")
            
            # Start Claude in each window and send initial briefings
            self.brief_all_roles(session_name, spec)
            
            console.print(f"\n[green]✓ Tmux session '{session_name}' created successfully![/green]")
            console.print(f"\nTo attach: [cyan]tmux attach -t {session_name}[/cyan]")
    
    def brief_all_roles(self, session_name: str, spec: ImplementationSpec):
        """Start Claude in each window and provide role-specific briefings"""
        
        # Check if Claude version supports context priming
        supports_context_prime = self.check_claude_version()
        
        roles = [
            ('Orchestrator', 0, 'orchestrator'),
            ('Project-Manager', 1, 'project_manager'),
            ('Developer', 2, 'developer'),
            ('Tester', 3, 'tester')
        ]
        
        for window_name, window_idx, role_key in roles:
            # Start Claude
            subprocess.run([
                'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
                'claude', 'Enter'
            ])
            
            # Wait for Claude to start
            time.sleep(5)
            
            # Send context priming command first (except for orchestrator who doesn't need project context)
            if role_key != 'orchestrator' and supports_context_prime:
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
                                                context_primed=supports_context_prime)
            
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
                           context_primed: bool = True) -> str:
        """Create a role-specific briefing message"""
        
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
            return f"""You are the Orchestrator for {spec.project.name}.

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Project Overview:
- Type: {spec.project.type}
- Technologies: {', '.join(spec.project.main_tech)}
- Total estimated time: {spec.implementation_plan.total_estimated_hours} hours

You have a team of:
- Project Manager (window 1) - Quality and progress tracking
- Developer (window 2) - Implementation
- Tester (window 3) - Testing and verification

Use these commands:
- Check status: python3 claude_control.py status detailed
- Send messages: ./send-claude-message.sh session:window "message"
- Schedule check-ins: ./schedule_with_note.sh minutes "note" target

Schedule your first check-in for {role_config.check_in_interval} minutes."""

        elif role == 'project_manager':
            return f"""{context_note}You are the Project Manager for {spec.project.name}.

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Implementation Phases:
{chr(10).join(f'{i+1}. {p.name} ({p.duration_hours}h)' for i, p in enumerate(spec.implementation_plan.phases))}

Success Criteria:
{chr(10).join(f'- {c}' for c in spec.success_criteria)}

Git Workflow:
- Branch: {spec.git_workflow.branch_name}
- Commit every {spec.git_workflow.commit_interval} minutes
- PR Title: {spec.git_workflow.pr_title}

Coordinate with:
- Developer (window 2) for implementation
- Tester (window 3) for quality assurance
- Report to Orchestrator (window 0)

Maintain EXCEPTIONAL quality standards. No compromises."""

        elif role == 'developer':
            return f"""{context_note}You are the Developer for {spec.project.name}.

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Project Details:
- Path: {spec.project.path}
- Type: {spec.project.type}
- Technologies: {', '.join(spec.project.main_tech)}

Implementation Phases:
{chr(10).join(f'{i+1}. {p.name}: {", ".join(p.tasks[:2])}...' for i, p in enumerate(spec.implementation_plan.phases))}

Git Requirements:
- Create branch: {spec.git_workflow.branch_name}
- Commit every {spec.git_workflow.commit_interval} minutes with clear messages
- Follow existing code patterns and conventions

Start by:
1. Reading the spec at: {self.spec_path}
2. Setting up your development environment
3. Creating the feature branch
4. Beginning implementation of Phase 1

Report progress to PM (window 1) regularly."""

        else:  # tester
            return f"""{context_note}You are the Tester for {spec.project.name}.

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
2. Setting up test environment
3. Running current test suite as baseline

Work closely with Developer to ensure quality."""

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
def main(project: str, spec: str):
    """Automatically set up a Tmux Orchestrator environment from a specification."""
    orchestrator = AutoOrchestrator(project, spec)
    orchestrator.run()


if __name__ == '__main__':
    main()
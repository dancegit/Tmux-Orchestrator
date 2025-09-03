"""
Specification Analyzer Module

Handles analysis of specification files with Claude to generate detailed implementation plans.
This module provides advanced spec analysis capabilities that were previously embedded in
the monolithic auto_orchestrate.py system.

Key features:
- Context-aware specification analysis
- Claude-powered implementation plan generation
- Git branch and project context detection
- Robust retry logic and error handling
- JSON-structured output with comprehensive role configurations
"""

import os
import subprocess
import tempfile
import json
import uuid
import time
import threading
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
logger = logging.getLogger(__name__)


class SpecificationAnalyzer:
    """
    Analyzes project specifications using Claude to generate comprehensive implementation plans.
    
    This class provides sophisticated spec analysis capabilities including:
    - Context-aware project analysis (git branch, context-prime support)
    - Claude-powered implementation plan generation
    - Robust subprocess execution with retry logic
    - JSON-structured output with role configurations
    - Error handling and cleanup
    """
    
    def __init__(self, tmux_orchestrator_path: Path):
        """
        Initialize the specification analyzer.
        
        Args:
            tmux_orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.tmux_orchestrator_path = tmux_orchestrator_path
        
    def analyze_specification(self, spec_file: Path, project_path: Path) -> Optional[Dict[str, Any]]:
        """
        Analyze specification file with Claude to create comprehensive implementation plan.
        
        Args:
            spec_file: Path to specification file
            project_path: Path to project directory
            
        Returns:
            Dict containing parsed implementation spec or None if failed
        """
        console.print(f"[cyan]📋 Analyzing specification: {spec_file.name}[/cyan]")
        
        try:
            # Read the specification file
            if not spec_file.exists():
                console.print(f"[red]Specification file not found: {spec_file}[/red]")
                return None
                
            spec_content = spec_file.read_text()
            console.print(f"[green]✓ Loaded specification ({len(spec_content)} chars)[/green]")
            
            # Detect project context
            current_branch = self._get_current_git_branch(project_path)
            supports_context_prime = self._check_context_prime_support(project_path)
            claude_version = self._get_claude_version()
            
            if claude_version:
                console.print(f"[cyan]Claude version detected: {claude_version}[/cyan]")
            
            if current_branch:
                console.print(f"[cyan]Current git branch: {current_branch}[/cyan]")
            else:
                current_branch = "main"  # Default if not in git repo
                console.print("[yellow]Not in a git repository, defaulting to 'main' branch[/yellow]")
            
            # Generate comprehensive prompt
            prompt = self._generate_analysis_prompt(
                spec_content, project_path, current_branch, supports_context_prime
            )
            
            # Execute Claude analysis with progress tracking
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing specification with Claude (may take 5-20 minutes)...", total=None)
                
                # Execute Claude analysis with retry logic
                spec_dict = self._execute_claude_analysis(prompt, project_path, progress, task)
                
                if spec_dict:
                    console.print("[green]✓ Specification analysis completed successfully[/green]")
                    return spec_dict
                else:
                    console.print("[red]❌ Specification analysis failed[/red]")
                    return None
                    
        except Exception as e:
            console.print(f"[red]Failed to analyze specification: {e}[/red]")
            logger.exception("Specification analysis error")
            return None
    
    def _get_current_git_branch(self, project_path: Path) -> Optional[str]:
        """Get the current git branch of the project."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=str(project_path)
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None
    
    def _get_claude_version(self) -> Optional[str]:
        """Get the Claude CLI version."""
        try:
            # Use full path to avoid Python packages
            result = subprocess.run(['/usr/bin/claude', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                # Parse version from output like "1.0.56 (Claude Code)" or "claude version 1.0.22"
                version_line = result.stdout.strip()
                
                # Try to extract version number using regex
                version_match = re.search(r'(\d+\.\d+\.\d+)', version_line)
                if version_match:
                    return version_match.group(1)
                    
                # Fallback to first word if regex fails
                return version_line.split()[0]
            return None
        except Exception:
            return None
    
    def _check_context_prime_support(self, project_path: Path) -> bool:
        """Check if the project supports context-prime command."""
        context_prime_path = project_path / '.claude' / 'commands' / 'context-prime.md'
        return context_prime_path.exists()
    
    def _generate_analysis_prompt(self, spec_content: str, project_path: Path, 
                                current_branch: str, supports_context_prime: bool) -> str:
        """Generate comprehensive analysis prompt for Claude."""
        
        # Base prompt with context priming support
        if supports_context_prime:
            prompt = f"""/context-prime "first: run context prime like normal, then: Analyze the project at {project_path} to understand its structure, technologies, and conventions"

After analyzing the project context above, now analyze the following specification and create a detailed implementation plan in JSON format."""
        else:
            prompt = f"""You are an AI project planning assistant. Analyze the following specification for the project at {project_path} and create a detailed implementation plan in JSON format."""
            
            if project_path.exists():
                context_prime_path = project_path / '.claude' / 'commands' / 'context-prime.md'
                console.print(f"[yellow]Note: No context-prime command found. To enable, create {context_prime_path}[/yellow]")
        
        # Add comprehensive prompt template
        prompt += f"""

PROJECT PATH: {project_path}
CURRENT GIT BRANCH: {current_branch}
SPECIFICATION:
{spec_content}

Generate a JSON implementation plan with this EXACT structure:
{{
  "project": {{
    "name": "Project name from spec",
    "path": "{project_path}",
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
      "check_in_interval": 20,
      "initial_commands": ["cd {self.tmux_orchestrator_path}", "python3 claude_control.py status detailed"]
    }},
    "project_manager": {{
      "responsibilities": ["Ensure quality", "Track completion", "Review coverage"],
      "check_in_interval": 25,
      "initial_commands": ["# Access project files using absolute paths with Read/Bash tools", "cat {spec_content[:50]}..."]
    }},
    "developer": {{
      "responsibilities": ["Implement features", "Write tests", "Fix bugs"],
      "check_in_interval": 30,
      "initial_commands": ["pwd", "# Use absolute paths with git -C instead of cd", "git -C {project_path} status"]
    }},
    "tester": {{
      "responsibilities": ["Run tests", "Report failures", "Verify coverage"],
      "check_in_interval": 30,
      "initial_commands": ["pwd", "echo 'Ready to test - will use absolute paths with test commands'"]
    }},
    "testrunner": {{
      "responsibilities": ["Execute test suites", "Parallel test management", "Performance testing", "Test infrastructure", "Results analysis"],
      "check_in_interval": 30,
      "initial_commands": ["pwd", "echo 'Setting up test execution framework - will use absolute paths'"]
    }},
    "researcher": {{
      "responsibilities": ["MCP tool discovery and utilization", "Research best practices", "Security vulnerability analysis", "Performance optimization research", "Document actionable findings"],
      "check_in_interval": 25,
      "initial_commands": ["pwd", "mkdir -p research", "echo 'Type @ to discover MCP resources, / to discover MCP commands'", "echo 'Look for /mcp__ prefixed commands for MCP tools'"]
    }},
    "devops": {{
      "responsibilities": ["Infrastructure setup", "Deployment pipelines", "Monitor performance"],
      "check_in_interval": 45,
      "initial_commands": ["pwd", "echo 'Checking deployment configuration in {project_path}'"]
    }},
    "sysadmin": {{
      "responsibilities": ["System setup", "User management", "Service configuration", "Package management", "System hardening"],
      "check_in_interval": 30,
      "initial_commands": ["pwd", "sudo -n true && echo 'sudo available' || echo 'need sudo password'", "uname -a"]
    }},
    "securityops": {{
      "responsibilities": ["Security hardening", "Firewall configuration", "Access control", "SSL/TLS setup", "Security monitoring"],
      "check_in_interval": 30,
      "initial_commands": ["pwd", "sudo iptables -L -n 2>/dev/null || echo 'checking firewall status'"]
    }},
    "networkops": {{
      "responsibilities": ["Network configuration", "Load balancing", "Reverse proxy setup", "DNS management", "Performance optimization"],
      "check_in_interval": 30,
      "initial_commands": ["pwd", "ip addr show", "netstat -tlnp 2>/dev/null || ss -tlnp"]
    }},
    "monitoringops": {{
      "responsibilities": ["Monitoring stack setup", "Metrics collection", "Alert configuration", "Dashboard creation", "Log aggregation"],
      "check_in_interval": 20,
      "initial_commands": ["pwd", "mkdir -p monitoring/dashboards monitoring/alerts", "echo 'Setting up monitoring infrastructure'"]
    }},
    "databaseops": {{
      "responsibilities": ["Database setup", "Performance tuning", "Replication", "Backup strategies", "Schema management"],
      "check_in_interval": 30,
      "initial_commands": ["pwd", "echo 'Checking database requirements'", "which psql mysql mongod redis-server 2>/dev/null || echo 'No databases installed yet'"]
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

        return prompt
    
    def _execute_claude_analysis(self, prompt: str, project_path: Path, 
                                progress: Progress, task) -> Optional[Dict[str, Any]]:
        """Execute Claude analysis with retry logic and error handling."""
        
        # Create temporary script file
        prompt_script = f"""#!/bin/bash
cd "{project_path}"
cat << 'CLAUDE_EOF' | /usr/bin/claude --dangerously-skip-permissions
{prompt}

Please provide ONLY the JSON response, no other text.
CLAUDE_EOF
"""
        
        script_file = f"/tmp/claude_prompt_{uuid.uuid4().hex}.sh"
        try:
            with open(script_file, 'w') as f:
                f.write(prompt_script)
            os.chmod(script_file, 0o755)
            
            # Pre-check Claude CLI responsiveness
            try:
                logger.debug("Pre-checking Claude CLI availability...")
                claude_check = subprocess.run(['/usr/bin/claude', '--version'], 
                                            capture_output=True, text=True, timeout=10)
                if claude_check.returncode != 0:
                    raise RuntimeError(f"Claude CLI not responsive: {claude_check.stderr}")
                logger.debug(f"Claude CLI check passed: {claude_check.stdout.strip()}")
            except subprocess.TimeoutExpired:
                raise RuntimeError("Claude CLI pre-check timed out - Claude may be unresponsive")
            except Exception as e:
                raise RuntimeError(f"Claude CLI pre-check failed: {e}")

            # Execute Claude analysis with retry logic
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                result_container = {}
                error_container = {}
                
                def run_claude():
                    try:
                        logger.info(f"Starting Claude analysis with script: {script_file}")
                        result = subprocess.run(
                            ['bash', script_file],
                            capture_output=True,
                            text=True,
                            timeout=300  # 5 minutes per attempt
                        )
                        logger.info(f"Claude analysis completed with exit code: {result.returncode}")
                        if result.stderr:
                            logger.warning(f"Claude stderr: {result.stderr}")
                        if result.returncode != 0:
                            logger.error(f"Claude failed with exit code {result.returncode}")
                        result_container['result'] = result
                    except Exception as e:
                        logger.error(f"Claude subprocess exception: {e}")
                        # Kill any child processes on timeout/error
                        try:
                            import psutil
                            parent = psutil.Process(os.getpid())
                            for child in parent.children(recursive=True):
                                logger.warning(f"Killing child process {child.pid}")
                                child.kill()
                        except Exception as kill_e:
                            logger.warning(f"Failed to kill child processes: {kill_e}")
                        error_container['error'] = e

                claude_thread = threading.Thread(target=run_claude)
                claude_thread.start()
                
                # Update progress with elapsed time while Claude runs
                start_time = time.time()
                while claude_thread.is_alive():
                    elapsed = time.time() - start_time
                    progress.update(task, description=f"Analyzing with Claude (attempt {retry_count+1}/{max_retries}, {elapsed:.0f}s elapsed, est. 5min)...")
                    time.sleep(5)  # Update every 5 seconds
                
                claude_thread.join()
                
                if 'result' in result_container and result_container['result'].returncode == 0:
                    # Successfully got response - parse JSON
                    try:
                        result = result_container['result']
                        response = result.stdout.strip()
                        
                        # Try to find JSON in the response
                        json_start = response.find('{')
                        json_end = response.rfind('}') + 1
                        
                        if json_start >= 0 and json_end > json_start:
                            json_str = response[json_start:json_end]
                            parsed_json = json.loads(json_str)
                            return parsed_json
                        else:
                            console.print("[red]Could not find valid JSON in Claude's response[/red]")
                            console.print(f"Response: {response[:500]}...")
                            
                    except json.JSONDecodeError as e:
                        console.print(f"[red]Failed to parse JSON from Claude response: {e}[/red]")
                        if retry_count < max_retries - 1:
                            console.print(f"[yellow]Retrying analysis (attempt {retry_count + 2}/{max_retries})...[/yellow]")
                
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"Claude analysis failed (attempt {retry_count}/{max_retries}) - retrying in 3 seconds...")
                    time.sleep(3)  # Brief pause before retry
                    
            # All retries failed
            if 'error' in error_container:
                raise error_container['error']
            else:
                raise RuntimeError(f"Claude analysis failed after {max_retries} attempts")
                
        except Exception as e:
            console.print(f"[red]Error during Claude analysis: {e}[/red]")
            logger.exception("Claude analysis execution error")
            return None
        finally:
            # Clean up script file
            if os.path.exists(script_file):
                try:
                    os.unlink(script_file)
                except Exception as e:
                    logger.warning(f"Failed to clean up script file {script_file}: {e}")
                    
        return None
#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click",
#     "rich",
#     "pydantic",
#     "pyyaml",
#     "python-dotenv",
#     "gitpython",
#     "psutil",
# ]
# ///

"""
Auto-Orchestrate: Automated Tmux Orchestrator Setup
Analyzes a specification file and automatically sets up a complete
tmux orchestration environment with Orchestrator, PM, Developer, and Tester.
"""

# Set UV_NO_WORKSPACE environment variable for all subprocess calls
import os
os.environ['UV_NO_WORKSPACE'] = '1'

import subprocess
import json
import sys
import os
import time
import re
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import tempfile
import shutil
import glob
from collections import OrderedDict

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.json import JSON
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from pydantic import BaseModel, Field

# Import session state management
from session_state import SessionStateManager, create_initial_session_state, SessionState, AgentState

# Import concurrent orchestration support
from concurrent_orchestration import ConcurrentOrchestrationManager

# Import dynamic team composition
from dynamic_team import DynamicTeamComposer

# Import email notification system
from email_notifier import get_email_notifier
# Import completion monitoring
from completion_manager import CompletionManager
# Import git commit manager
from git_commit_manager import GitCommitManager
# Import hooks-based messaging system
from tmux_messenger_hooks import TmuxMessenger
from setup_agent_hooks import setup_agent_hooks

console = Console()
logger = logging.getLogger(__name__)

# Import git for local remote setup
try:
    from git import Repo, GitCommandError
except ImportError:
    Repo = None
    GitCommandError = None
    logger.warning("GitPython not available - local remote setup will be skipped")

def find_git_root(start_path: Path) -> Optional[Path]:
    """Find the nearest parent directory containing a .git folder"""
    current = start_path.resolve()
    max_depth = 10  # Prevent infinite traversal in deep hierarchies
    depth = 0
    while current != current.parent and depth < max_depth:
        if (current / '.git').exists():
            return current
        current = current.parent
        depth += 1
    return None  # No git root found

def setup_new_project(spec_path: Path, force: bool = False) -> Tuple[str, str]:
    """Create and initialize a new git project based on the spec file. Returns (new_project_path, new_spec_path)."""
    if spec_path.suffix.lower() != '.md':
        raise ValueError("Spec file must be a .md file")
    
    # Find git root of spec's parent
    git_root = find_git_root(spec_path.parent)
    if not git_root:
        raise ValueError(f"No git repository found containing {spec_path}")
    
    # Derive new project name from spec stem (e.g., 'new_feature')
    new_project_name = spec_path.stem.lower().replace(' ', '-')
    new_project_path = git_root.parent / new_project_name
    
    # Check if exists and handle overwrite
    if new_project_path.exists():
        if force:
            shutil.rmtree(new_project_path)
            console.print(f"[yellow]Removed existing project: {new_project_path}[/yellow]")
        else:
            raise RuntimeError(f"{new_project_path} already exists. Use --force to overwrite or choose a different spec name.")
    
    new_project_path.mkdir(parents=True, exist_ok=True)
    
    # Copy spec
    dest_spec = new_project_path / spec_path.name
    shutil.copy(spec_path, dest_spec)
    console.print(f"[green]Copied spec to {dest_spec}[/green]")
    
    # Git init and initial commit (required for worktrees)
    try:
        subprocess.run(['git', 'init', str(new_project_path)], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(new_project_path), 'add', spec_path.name], check=True)
        subprocess.run(['git', '-C', str(new_project_path), 'commit', '-m', 'Initial commit: Add specification file'], check=True)
        console.print(f"[green]Initialized new git repo at {new_project_path}[/green]")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        raise RuntimeError(f"Git initialization failed: {error_msg}")
    
    return str(new_project_path), str(dest_spec)

def expand_specs(spec_args: List[str]) -> List[Path]:
    """Expand spec arguments, including globs and directories, to a list of unique .md files."""
    expanded = []
    for arg in spec_args:
        path = Path(arg)
        if path.is_dir():
            # If directory, glob *.md inside it
            expanded.extend([Path(p) for p in glob.glob(str(path / '*.md'))])
        elif '*' in arg or '?' in arg:  # Treat as glob pattern
            expanded.extend([Path(p) for p in glob.glob(arg)])
        else:
            expanded.append(path)
    
    # Deduplicate while preserving order
    unique_specs = list(OrderedDict.fromkeys(expanded))
    
    # Validate
    invalid = [p for p in unique_specs if not p.exists() or p.suffix.lower() != '.md']
    if invalid:
        raise ValueError(f"Invalid specs (must be existing .md files): {invalid}")
    
    return unique_specs

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


class AgentIdManager:
    """Manages agent identification using session:window format for multi-window tmux architecture."""
    
    def __init__(self, session_name: str):
        self.session_name = session_name
        self.id_cache = {}  # role -> 'session:window'
        self.window_cache = {}  # window_index -> role
        
    def get_agent_id(self, role: str, window_index: Optional[int] = None) -> str:
        """Get agent ID as session:window for a given role."""
        if role not in self.id_cache:
            if window_index is None:
                window_index = self._query_window_index(role)
                if window_index == -1:
                    raise ValueError(f"Window not found for role: {role}")
            
            agent_id = f"{self.session_name}:{window_index}"
            self.id_cache[role] = agent_id
            self.window_cache[window_index] = role
            
        return self.id_cache[role]
    
    def get_role_from_window(self, window_index: int) -> Optional[str]:
        """Get role name from window index."""
        return self.window_cache.get(window_index)
    
    def _query_window_index(self, role: str) -> int:
        """Query tmux to get window index for a role (assumes windows are named by role)."""
        try:
            # First try with exact role match
            result = subprocess.getoutput(
                f"tmux list-windows -t {self.session_name} -F '#{{window_index}} #{{window_name}}' | grep -w {role} | head -1 | cut -d' ' -f1"
            ).strip()
            
            if result and result.isdigit():
                return int(result)
            
            # Fallback: try case-insensitive match
            result = subprocess.getoutput(
                f"tmux list-windows -t {self.session_name} -F '#{{window_index}} #{{window_name}}' | grep -i {role} | head -1 | cut -d' ' -f1"
            ).strip()
            
            if result and result.isdigit():
                return int(result)
                
            return -1  # Not found
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to query window index for role {role}: {e}")
            return -1
    
    def register_agent(self, role: str, window_index: int):
        """Manually register an agent ID without querying tmux."""
        agent_id = f"{self.session_name}:{window_index}"
        self.id_cache[role] = agent_id
        self.window_cache[window_index] = role
        return agent_id
    
    def get_all_agent_ids(self) -> Dict[str, str]:
        """Get all cached agent IDs."""
        return self.id_cache.copy()
    
    def clear_cache(self):
        """Clear the ID cache (useful for session resets)."""
        self.id_cache.clear()
        self.window_cache.clear()


class PathManager:
    """Centralized path management for consistent worktree and metadata handling"""
    def __init__(self, project_path: Path, orchestrator_root: Path):
        self.project_path = project_path.resolve()
        self.orchestrator_root = orchestrator_root.resolve()
        self.project_name = self.project_path.name
        
        # Use WorktreeManager for spec-specific worktree paths
        from worktree_manager import WorktreeManager
        self.worktree_manager = WorktreeManager(self.project_path)
        
        # Generate spec-specific worktree path
        session_name = getattr(self, 'unique_session_name', 'unknown')
        self.worktree_root = self.worktree_manager.get_or_create_worktree_path(
            str(self.spec_path), session_name
        )
        
        # Metadata is also a sibling (migrating from registry)
        self.metadata_root = self.project_path.parent / f"{self.project_name}-tmux-metadata"
        
        # Legacy registry path (for migration)
        self.legacy_registry = self.orchestrator_root / 'registry' / 'projects' / self.project_name
        
        self._ensure_dirs()
        self._migrate_legacy_if_exists()
    
    def _ensure_dirs(self):
        """Ensure all required directories exist"""
        for dir_path in [self.worktree_root, self.metadata_root]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _migrate_legacy_if_exists(self):
        """One-time migration from legacy registry to sibling structure"""
        if self.legacy_registry.exists() and not (self.metadata_root / 'migrated.flag').exists():
            console.print(f"[yellow]Migrating legacy registry data to sibling structure...[/yellow]")
            try:
                # Copy session state and other metadata
                import shutil
                for item in self.legacy_registry.iterdir():
                    if item.name != 'worktrees':  # Skip worktrees, they're created fresh
                        if item.is_file():
                            shutil.copy2(item, self.metadata_root / item.name)
                        elif item.is_dir():
                            shutil.copytree(item, self.metadata_root / item.name, dirs_exist_ok=True)
                
                # Mark as migrated
                (self.metadata_root / 'migrated.flag').touch()
                console.print(f"[green]✓ Legacy data migrated to {self.metadata_root}[/green]")
            except Exception as e:
                console.print(f"[red]Migration failed: {e}. Continuing with fresh metadata.[/red]")
    
    def get_worktree_path(self, role: str) -> Path:
        """Get the worktree path for a specific role"""
        return self.worktree_root / role.lower().replace('_', '-')
    
    def get_session_state_path(self) -> Path:
        """Get the session state file path"""
        return self.metadata_root / 'session_state.json'
    
    def get_implementation_spec_path(self) -> Path:
        """Get the implementation spec file path"""
        return self.metadata_root / 'implementation_spec.json'
    
    def get_logs_dir(self) -> Path:
        """Get the logs directory"""
        logs_dir = self.metadata_root / 'logs'
        logs_dir.mkdir(exist_ok=True)
        return logs_dir
    
    def get_notes_dir(self) -> Path:
        """Get the notes directory"""
        notes_dir = self.metadata_root / 'notes'
        notes_dir.mkdir(exist_ok=True)
        return notes_dir
    
    def cleanup_legacy(self):
        """Remove legacy registry after successful migration"""
        if self.legacy_registry.exists() and (self.metadata_root / 'migrated.flag').exists():
            console.print(f"[yellow]Removing legacy registry at {self.legacy_registry}...[/yellow]")
            import shutil
            shutil.rmtree(self.legacy_registry)
            console.print(f"[green]✓ Legacy registry cleaned up[/green]")
    
    def setup_sandbox_for_role(self, role: str, active_roles: List[str] = None) -> bool:
        """Set up sandbox symlinks and essential files for a role's worktree.
        Returns True if successful, False otherwise (for fallback handling).
        """
        worktree_path = self.get_worktree_path(role)
        worktree_path.mkdir(parents=True, exist_ok=True)
        
        success = True
        
        # Create shared directory for all symlinks
        shared_dir = worktree_path / 'shared'
        shared_dir.mkdir(exist_ok=True)
        
        # Create relative symlink to main project
        if not self._create_relative_symlink(
            shared_dir / 'main-project', 
            self.project_path, 
            worktree_path
        ):
            success = False
        
        # Create symlinks to other agent worktrees (excluding self)
        if active_roles:
            for other_role in active_roles:
                if other_role != role and other_role != 'orchestrator':  # Skip self and orchestrator
                    other_path = self.get_worktree_path(other_role)
                    if other_path.exists():
                        if not self._create_relative_symlink(
                            shared_dir / other_role, 
                            other_path, 
                            worktree_path
                        ):
                            logger.warning(f"Failed to create symlink to {other_role} worktree")
        
        # Ensure essential files are present
        for file_name in ['.mcp.json', 'CLAUDE.md']:
            src = self.orchestrator_root / file_name
            dest = worktree_path / file_name
            if src.exists() and not dest.exists():
                try:
                    import shutil
                    shutil.copy(src, dest)
                    logger.info(f"Copied {file_name} to {worktree_path}")
                except (OSError, PermissionError) as e:
                    logger.error(f"Failed to copy {file_name} for {role}: {e}")
                    success = False
        
        # Generate .claude configuration if AgentIdManager is available
        self._setup_claude_config_for_role(role, worktree_path)
        
        return success
    
    def _setup_claude_config_for_role(self, role: str, worktree_path: Path):
        """Generate .claude/settings.local.json with agent_id for hooks-based messaging."""
        try:
            # Check if we have access to orchestrator's AgentIdManager
            orchestrator = getattr(self, '_orchestrator_ref', None)
            if not orchestrator or not hasattr(orchestrator, 'agent_id_manager'):
                return  # Skip if AgentIdManager not available
                
            agent_id = orchestrator.agent_id_manager.get_agent_id(role)
            
            # Create .claude directory
            claude_dir = worktree_path / '.claude'
            claude_dir.mkdir(exist_ok=True)
            
            # Generate settings.local.json
            config_path = claude_dir / 'settings.local.json'
            config = {
                "agent_id": agent_id,
                "session_name": orchestrator.unique_session_name,
                "db_path": str(orchestrator.tmux_orchestrator_path / 'task_queue.db'),
                "ready_flag_timeout": 30,
                "direct_delivery_enabled": True
            }
            
            # Merge with existing config if it exists
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        existing = json.load(f)
                    config.update(existing)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in {config_path}, overwriting")
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
                
            logger.info(f"Generated .claude/settings.local.json with agent_id: {agent_id}")
            
        except Exception as e:
            logger.warning(f"Failed to setup Claude config for {role}: {e}")
    
    def _create_relative_symlink(self, link_path: Path, target_path: Path, base_path: Path) -> bool:
        """Create a relative symlink from link_path to target_path, relative to base_path."""
        if link_path.exists():
            return True  # Already exists
        
        try:
            import platform
            relative_target = os.path.relpath(str(target_path), str(link_path.parent))
            
            if platform.system() == 'Windows':
                # Windows-specific symlink handling
                try:
                    # Try directory symlink first
                    subprocess.run(['cmd', '/c', 'mklink', '/D', str(link_path), relative_target], 
                                 check=True, capture_output=True)
                    logger.info(f"Created Windows symlink: {link_path} -> {target_path}")
                except subprocess.CalledProcessError:
                    # Fall back to junction for absolute path
                    try:
                        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link_path), str(target_path)], 
                                     check=True, capture_output=True)
                        logger.info(f"Created Windows junction: {link_path} -> {target_path}")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to create Windows link {link_path}: {e}")
                        return False
            else:
                # Unix-like systems
                os.symlink(relative_target, str(link_path), target_is_directory=True)
                logger.info(f"Created symlink: {link_path} -> {target_path}")
            
            return True
        except (OSError, PermissionError) as e:
            logger.error(f"Failed to create symlink {link_path}: {e}")
            return False
    
    def migrate_sandboxes(self):
        """Migrate existing worktrees to have sandbox symlinks."""
        if (self.metadata_root / 'sandbox_migrated.flag').exists():
            return
        
        # Get all existing worktree directories
        if self.worktree_root.exists():
            worktree_dirs = [d for d in self.worktree_root.iterdir() if d.is_dir()]
            role_names = [d.name.replace('-', '_') for d in worktree_dirs]
            
            for worktree_dir in worktree_dirs:
                role = worktree_dir.name.replace('-', '_')
                self.setup_sandbox_for_role(role, active_roles=role_names)
        
        (self.metadata_root / 'sandbox_migrated.flag').touch()
        logger.info("Sandbox migration complete")
    
    def reconcile_session_state(self, session_state: dict) -> dict:
        """Reconcile missing paths in session state"""
        # Fill in missing project_path
        if not session_state.get('project_path'):
            session_state['project_path'] = str(self.project_path)
        
        # Fill in missing worktree_base_path
        if not session_state.get('worktree_base_path'):
            session_state['worktree_base_path'] = str(self.worktree_root)
        
        # Update agent worktree paths
        if 'agents' in session_state:
            for role, agent in session_state['agents'].items():
                if not agent.get('worktree_path'):
                    role_worktree = self.get_role_worktree(role)
                    if role_worktree.exists():
                        agent['worktree_path'] = str(role_worktree)
        
        return session_state


class TmuxMessenger:
    """Unified tmux messaging system with MCP wrapper prevention and guaranteed Enter key"""
    
    def __init__(self, orchestrator_path: Path):
        self.orchestrator_path = orchestrator_path
        self.send_script = orchestrator_path / 'send-claude-message.sh'
        
    def clean_message_from_mcp_wrappers(self, message: str) -> str:
        """Enhanced MCP wrapper removal to handle all contamination patterns"""
        import re
        
        original = message
        
        # Comprehensive MCP wrapper patterns
        patterns = [
            # Common MCP wrappers
            r'^echo\s+[\'"]TMUX_MCP_START[\'"];\s*',
            r';\s*echo\s+[\'"]TMUX_MCP_DONE_\$\?[\'"]$',
            r'echo\s+[\'"]TMUX_MCP_START[\'"];\s*',
            r';\s*echo\s+[\'"]TMUX_MCP_DONE_\$\?[\'"]',
            
            # Alternative wrapper patterns  
            r'echo\s+TMUX_MCP_START;\s*',
            r';\s*echo\s+TMUX_MCP_DONE_\$\?',
            r'echo\s+[\'"]MCP_EXECUTE_START[\'"];\s*',
            r';\s*echo\s+[\'"]MCP_EXECUTE_END_\$\?[\'"]',
            
            # Shell execution wrappers
            r'bash\s+-c\s+[\'"]echo\s+[\'"]?TMUX_MCP_START[\'"]?;\s*',
            r';\s*echo\s+[\'"]?TMUX_MCP_DONE_\$\?[\'"]?[\'"]',
            
            # Command substitution patterns
            r'\$\(\s*echo\s+[\'"]TMUX_MCP_START[\'"];\s*',
            r';\s*echo\s+[\'"]TMUX_MCP_DONE_\$\?[\'"]?\s*\)',
            
            # Inline wrapper remnants
            r'TMUX_MCP_START\s*;?\s*',
            r';\s*TMUX_MCP_DONE_\$\?\s*',
        ]
        
        # Apply patterns iteratively
        for _ in range(3):
            before = message
            for pattern in patterns:
                message = re.sub(pattern, '', message)
            if message == before:
                break
        
        # Clean up artifacts
        message = re.sub(r';\s*;', ';', message)  # Double semicolons
        message = re.sub(r'^\s*;\s*', '', message)  # Leading semicolon
        message = re.sub(r'\s*;\s*$', '', message)  # Trailing semicolon
        message = re.sub(r'\s+', ' ', message)  # Multiple spaces
        message = message.strip()
        
        if len(original) > len(message) + 20:
            console.print(f"[dim]🧹 Cleaned MCP wrappers: {len(original)} → {len(message)} chars[/dim]")
        
        return message
        
    def send_message(self, target: str, message: str, retries: int = 3) -> bool:
        """Send message with guaranteed Enter key and MCP wrapper prevention"""
        # Clean message first
        clean_message = self.clean_message_from_mcp_wrappers(message)
        
        if not clean_message:
            console.print(f"[yellow]⚠️ Message was empty after cleaning, skipping send to {target}[/yellow]")
            return True  # Don't fail on empty messages
        
        # Use enhanced send script with proper Enter handling
        try:
            result = subprocess.run([
                str(self.send_script),
                target,
                clean_message
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                console.print(f"[dim]📤 Message sent to {target}: {clean_message[:50]}{'...' if len(clean_message) > 50 else ''}[/dim]")
                return True
            else:
                console.print(f"[red]❌ Failed to send to {target}: {result.stderr}[/red]")
                return False
                
        except subprocess.TimeoutExpired:
            console.print(f"[red]⏰ Message send timeout to {target}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]💥 Exception sending to {target}: {e}[/red]")
            return False
    
    def send_command(self, target: str, command: str) -> bool:
        """Send a command with 'Please run:' prefix"""
        return self.send_message(target, f"Please run: {command}")
        
    def send_briefing(self, target: str, briefing: str) -> bool:
        """Send a role briefing with enhanced cleaning"""
        return self.send_message(target, briefing)


class AutoOrchestrator:
    def __init__(self, project_path: str, spec_path: str, batch_mode: bool = False, overwrite: bool = False, daemon: bool = False):
        self.spec_path = Path(spec_path).resolve()
        
        # Non-interactive mode detection
        self.daemon_mode = daemon or (not sys.stdin.isatty()) or os.getenv('DAEMON_MODE', 'false').lower() == 'true'
        
        # Batch mode settings  
        self.batch_mode = batch_mode or self.daemon_mode  # Daemon mode implies batch mode
        self.overwrite = overwrite
        
        # New flags for bug fixes
        self.enable_orchestrator_scheduling = True  # Default enabled for reliability
        self.global_mcp_init = False  # Will be set from CLI
        
        # Auto-detect project path if not provided or set to 'auto'
        if not project_path or project_path.lower() == 'auto':
            detected = find_git_root(self.spec_path.parent)
            if detected:
                self.project_path = detected
                console.print(f"[green]✓ Detected project root: {detected}[/green]")
            else:
                raise ValueError("No .git directory found in parent paths. Specify --project explicitly.")
        else:
            self.project_path = Path(project_path).resolve()
            
        self.tmux_orchestrator_path = Path(__file__).parent
        self.implementation_spec: Optional[ImplementationSpec] = None
        
        # Initialize TmuxMessenger for standardized messaging
        self.messenger = TmuxMessenger(self.tmux_orchestrator_path)
        
        # Initialize PathManager for unified path handling
        self.path_manager = PathManager(self.project_path, self.tmux_orchestrator_path)
        self.path_manager._orchestrator_ref = self  # Reference for AgentIdManager access
        
        # Set project_name from path
        self.project_name = self.project_path.name
        
        # Track start time for duration calculation
        self.start_time = time.time()
        
        # Initialize email notifier
        self.email_notifier = get_email_notifier()
        self.manual_size: Optional[str] = None
        self.additional_roles: List[str] = []
        self.force: bool = False
        self.plan_type: str = 'max20'  # Default to Max 20x plan
        self.session_state_manager = SessionStateManager(self.tmux_orchestrator_path)
        # Initialize completion manager
        self.completion_manager = CompletionManager(self.session_state_manager)
        self.concurrent_manager = ConcurrentOrchestrationManager(self.tmux_orchestrator_path)
        self.worktree_paths: Dict[str, Path] = {}
        self.unique_session_name: Optional[str] = None
        self.unique_registry_dir: Optional[Path] = None
        self.team_type: Optional[str] = None  # Force specific team type
        self.dynamic_team_composer = DynamicTeamComposer()
        
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
    
    def pre_flight_checks(self) -> bool:
        """
        Comprehensive pre-flight checks before tmux session creation.
        
        Returns:
            True if all checks pass, False otherwise
        """
        console.print("\n[cyan]🚀 Running pre-flight checks...[/cyan]")
        
        checks = [
            ("tmux availability", self._check_tmux_available),
            ("git repository validity", self._check_git_repo_valid),
            ("disk space sufficiency", self._check_disk_space_sufficient),
            ("session conflicts", self._check_no_session_conflicts),
            ("resource availability", self._check_resources_available)
        ]
        
        all_passed = True
        
        for check_name, check_func in checks:
            try:
                console.print(f"  Checking {check_name}...", end="")
                if check_func():
                    console.print(" [green]✓[/green]")
                else:
                    console.print(" [red]✗[/red]")
                    all_passed = False
            except Exception as e:
                console.print(f" [red]✗ Error: {e}[/red]")
                all_passed = False
        
        if all_passed:
            console.print("[green]✅ All pre-flight checks passed[/green]")
        else:
            console.print("[red]❌ Pre-flight checks failed - aborting[/red]")
        
        return all_passed
    
    def _check_tmux_available(self) -> bool:
        """Check if tmux is available and responsive"""
        try:
            # Test tmux version
            result = subprocess.run(['tmux', '-V'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                console.print(f"\n[red]Error: tmux command failed: {result.stderr}[/red]")
                return False
            
            # Test if we can create a temporary session
            test_session = f"preflight-test-{int(time.time())}"
            result = subprocess.run(['tmux', 'new-session', '-d', '-s', test_session], capture_output=True)
            if result.returncode == 0:
                # Clean up test session
                subprocess.run(['tmux', 'kill-session', '-t', test_session], capture_output=True)
                return True
            else:
                console.print(f"\n[red]Error: Cannot create tmux sessions: {result.stderr.decode()}[/red]")
                return False
                
        except subprocess.TimeoutExpired:
            console.print("\n[red]Error: tmux command timed out[/red]")
            return False
        except FileNotFoundError:
            console.print("\n[red]Error: tmux not found in PATH[/red]")
            return False
        except Exception as e:
            console.print(f"\n[red]Error testing tmux: {e}[/red]")
            return False
    
    def _check_git_repo_valid(self) -> bool:
        """Check if the project is a valid git repository"""
        try:
            if not (self.project_path / '.git').exists():
                console.print(f"\n[red]Error: {self.project_path} is not a git repository[/red]")
                return False
            
            # Test git operations
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  cwd=self.project_path, capture_output=True, text=True)
            if result.returncode != 0:
                console.print(f"\n[red]Error: Git repository appears corrupted: {result.stderr}[/red]")
                return False
            
            return True
            
        except Exception as e:
            console.print(f"\n[red]Error checking git repository: {e}[/red]")
            return False
    
    def _check_disk_space_sufficient(self) -> bool:
        """Check if sufficient disk space is available"""
        try:
            # Check disk space for project directory
            statvfs = os.statvfs(self.project_path)
            free_space_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
            
            # Require at least 1GB free space
            min_space_gb = 1.0
            if free_space_gb < min_space_gb:
                console.print(f"\n[red]Error: Insufficient disk space. Available: {free_space_gb:.1f}GB, Required: {min_space_gb}GB[/red]")
                return False
                
            return True
            
        except Exception as e:
            console.print(f"\n[red]Error checking disk space: {e}[/red]")
            return False
    
    def _check_no_session_conflicts(self) -> bool:
        """Check for potential tmux session name conflicts"""
        try:
            # Get list of existing sessions
            result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'], 
                                  capture_output=True, text=True)
            
            existing_sessions = set()
            if result.returncode == 0:
                existing_sessions = set(line.strip() for line in result.stdout.split('\n') if line.strip())
            
            # Check for common conflict patterns
            project_name = self.project_path.name.lower()
            potential_conflicts = [
                f"{project_name}-impl",
                f"{project_name}-orchestrator", 
                f"{project_name}-dev",
                project_name
            ]
            
            conflicts = []
            for session_name in potential_conflicts:
                if session_name in existing_sessions:
                    conflicts.append(session_name)
            
            if conflicts and not self.force:
                console.print(f"\n[yellow]Warning: Potential session name conflicts detected: {', '.join(conflicts)}[/yellow]")
                console.print("[yellow]Use --force to override, or manually resolve conflicts[/yellow]")
                # For now, warn but don't fail - conflict resolution is handled separately
            
            return True
            
        except Exception as e:
            console.print(f"\n[red]Error checking session conflicts: {e}[/red]")
            return False
    
    def _check_resources_available(self) -> bool:
        """Check if system resources are sufficient"""
        try:
            # Check available memory (require at least 1GB available)
            try:
                import psutil
                memory = psutil.virtual_memory()
                available_gb = memory.available / (1024**3)
                
                if available_gb < 1.0:
                    console.print(f"\n[yellow]Warning: Low memory available: {available_gb:.1f}GB[/yellow]")
                    # Don't fail, just warn
                    
            except ImportError:
                # psutil not available, skip memory check
                pass
            
            # Check if we can create files in the project directory
            test_file = self.project_path / '.preflight_test'
            try:
                test_file.write_text('test')
                test_file.unlink()
            except Exception:
                console.print(f"\n[red]Error: Cannot write to project directory: {self.project_path}[/red]")
                return False
            
            return True
            
        except Exception as e:
            console.print(f"\n[red]Error checking resources: {e}[/red]")
            return False
    
    def setup_git_locals(self):
        """Automatically set up local remotes, role-specific branches, and integration branch for all agents."""
        if not Repo:
            console.print("[yellow]GitPython not available - skipping local remote setup[/yellow]")
            return
            
        if not self.implementation_spec:
            console.print("[yellow]No implementation spec available - skipping local remote setup[/yellow]")
            return
            
        try:
            repo = Repo(str(self.project_path))
            
            # Get roles that have been deployed
            roles_to_setup = []
            if hasattr(self, 'worktree_paths') and self.worktree_paths:
                # Use actual deployed roles from worktree_paths
                roles_to_setup = list(self.worktree_paths.keys())
            else:
                # Fallback to roles from spec
                roles_to_setup = list(self.implementation_spec.roles.keys())
            
            console.print(f"[cyan]Setting up local remotes for {len(roles_to_setup)} roles...[/cyan]")
            
            for role in roles_to_setup:
                remote_name = role.lower().replace('_', '-')  # Normalize role name
                
                # Use actual worktree path if available, otherwise fallback to default structure
                if hasattr(self, 'worktree_paths') and self.worktree_paths and role in self.worktree_paths:
                    worktree_path = Path(self.worktree_paths[role])
                else:
                    # Fallback to default structure
                    worktree_dir = self.project_path / 'worktrees'
                    worktree_dir.mkdir(exist_ok=True)
                    worktree_path = worktree_dir / remote_name
                    
                branch_name = remote_name  # Role-specific branch
                
                # Only process if worktree exists
                if worktree_path.exists():
                    # Ensure worktree is on correct branch
                    try:
                        wt_repo = Repo(str(worktree_path))
                        if not wt_repo.head.is_detached and wt_repo.active_branch.name != branch_name:
                            # Try to create branch if it doesn't exist
                            if branch_name not in [b.name for b in wt_repo.branches]:
                                wt_repo.git.checkout('-b', branch_name)
                                console.print(f"[green]Created branch {branch_name} for {role}[/green]")
                            else:
                                wt_repo.git.checkout(branch_name)
                                console.print(f"[yellow]Switched {role} to branch {branch_name}[/yellow]")
                    except Exception as e:
                        console.print(f"[yellow]Could not ensure branch for {role}: {e}[/yellow]")
                    
                    # Add/update local remote
                    try:
                        repo.git.remote('add', remote_name, str(worktree_path))
                        console.print(f"[green]Added local remote '{remote_name}' → {worktree_path}[/green]")
                    except GitCommandError as e:
                        if 'already exists' in str(e):
                            repo.git.remote('set-url', remote_name, str(worktree_path))
                            console.print(f"[yellow]Updated remote '{remote_name}' → {worktree_path}[/yellow]")
                        else:
                            console.print(f"[red]Failed to add remote {remote_name}: {e}[/red]")
                else:
                    console.print(f"[yellow]Worktree not found for {role} at {worktree_path}[/yellow]")
            
            # Create integration branch if not exists
            integration_branch = 'integration'
            if hasattr(self.implementation_spec, 'git_workflow') and self.implementation_spec.git_workflow:
                integration_branch = self.implementation_spec.git_workflow.parent_branch or 'integration'
                
            if integration_branch not in [head.name for head in repo.heads]:
                # Determine base branch
                base_branch = 'main' if 'main' in [head.name for head in repo.heads] else 'master'
                repo.git.branch(integration_branch, base_branch)
                console.print(f"[green]Created integration branch: {integration_branch} (based on {base_branch})[/green]")
            else:
                console.print(f"[cyan]Integration branch '{integration_branch}' already exists[/cyan]")
            
            # Initial fetch for all local remotes
            console.print("[cyan]Fetching from all local remotes...[/cyan]")
            for role in roles_to_setup:
                remote_name = role.lower().replace('_', '-')
                if remote_name in [r.name for r in repo.remotes]:
                    try:
                        repo.git.fetch(remote_name)
                        console.print(f"[green]Fetched from {remote_name}[/green]")
                    except Exception as e:
                        console.print(f"[yellow]Could not fetch from {remote_name}: {e}[/yellow]")
                        
            console.print("[green]✓ Local remotes setup complete[/green]")
            
        except Exception as e:
            console.print(f"[red]Error setting up local remotes: {e}[/red]")
            logger.error(f"Failed to setup git locals: {e}")
    
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
                all_sessions = result.stdout.strip().split('\n')
                sessions = all_sessions[:3]
                for session in sessions:
                    console.print(f"   • {session}")
                if len(all_sessions) > 3:
                    remaining_count = len(all_sessions) - 3
                    console.print(f"   • ... and {remaining_count} more sessions")

    def ensure_queue_daemon(self):
        """Ensure queue daemon service is running"""
        console.print("[cyan]Checking queue daemon...[/cyan]")
        
        # Check if systemd service is active
        result = subprocess.run(['systemctl', 'is-active', '--quiet', 'tmux-orchestrator-queue'],
                              capture_output=True)
        
        if result.returncode == 0:
            console.print("[green]✓ Queue daemon service running[/green]")
        else:
            console.print("[yellow]Queue daemon not running - attempting to start...[/yellow]")
            
            # Try to start the service
            start_result = subprocess.run(['sudo', 'systemctl', 'start', 'tmux-orchestrator-queue'],
                                        capture_output=True, text=True)
            
            if start_result.returncode == 0:
                console.print("[green]✓ Queue daemon started successfully[/green]")
            else:
                console.print("[yellow]Warning: Could not start queue daemon service[/yellow]")
                console.print("[yellow]Projects may need to be run individually[/yellow]")
                if start_result.stderr:
                    console.print(f"[red]Error: {start_result.stderr.strip()}[/red]")
    
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
            prompt = f"""/context-prime "first: run context prime like normal, then: Analyze the project at {self.project_path} to understand its structure, technologies, and conventions"

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
      "initial_commands": ["cd ./shared/main-project || cd {self.project_path}", "cat {self.spec_path.name}"]
    }},
    "developer": {{
      "responsibilities": ["Implement features", "Write tests", "Fix bugs"],
      "check_in_interval": 30,  # Reduced for faster development cycles
      "initial_commands": ["pwd", "ls -la shared/ || echo 'No shared directory'", "cd ./shared/main-project && git status || cd {self.project_path} && git status"]
    }},
    "tester": {{
      "responsibilities": ["Run tests", "Report failures", "Verify coverage"],
      "check_in_interval": 30,  # Reduced to match developer pace
      "initial_commands": ["pwd", "ls -la shared/ || echo 'No shared directory'", "cd ./shared/main-project && echo 'Ready to test' || cd {self.project_path} && echo 'Ready to test'"]
    }},
    "testrunner": {{
      "responsibilities": ["Execute test suites", "Parallel test management", "Performance testing", "Test infrastructure", "Results analysis"],
      "check_in_interval": 30,  # Same as tester for coordination
      "initial_commands": ["pwd", "ls -la shared/ || echo 'No shared directory'", "cd ./shared/main-project && echo 'Setting up test execution framework' || cd {self.project_path} && echo 'Setting up test execution framework'"]
    }},
    "logtracker": {{
      "responsibilities": ["Monitor logs real-time", "Track errors", "Alert critical issues", "Use project monitoring tools", "Generate error reports"],
      "check_in_interval": 15,  # Frequent checks for real-time monitoring
      "initial_commands": ["pwd", "mkdir -p monitoring/logs monitoring/reports", "cd ./shared/main-project && echo 'Reading CLAUDE.md for monitoring instructions' || cd {self.project_path} && echo 'Reading CLAUDE.md for monitoring instructions'"]
    }},
    "devops": {{
      "responsibilities": ["Infrastructure setup", "Deployment pipelines", "Monitor performance"],
      "check_in_interval": 45,  # Reduced but still longer as infra work is less frequent
      "initial_commands": ["pwd", "ls -la shared/ || echo 'No shared directory'", "cd ./shared/main-project && echo 'Checking deployment configuration' || cd {self.project_path} && echo 'Checking deployment configuration'"]
    }},
    "code_reviewer": {{
      "responsibilities": ["Review code quality", "Security audit", "Best practices enforcement"],
      "check_in_interval": 40,  # Reduced to review code more frequently
      "initial_commands": ["pwd", "ls -la shared/ || echo 'No shared directory'", "cd ./shared/main-project && git log --oneline -10 || cd {self.project_path} && git log --oneline -10"]
    }},
    "researcher": {{
      "responsibilities": ["MCP tool discovery and utilization", "Research best practices", "Security vulnerability analysis", "Performance optimization research", "Document actionable findings"],
      "check_in_interval": 25,  # Reduced for timely research support
      "initial_commands": ["pwd", "mkdir -p research", "echo 'Type @ to discover MCP resources, / to discover MCP commands'", "echo 'Look for /mcp__ prefixed commands for MCP tools'"]
    }},
    "documentation_writer": {{
      "responsibilities": ["Write technical docs", "Update README", "Create API documentation"],
      "check_in_interval": 60,  # Still longer as docs are updated less frequently
      "initial_commands": ["pwd", "ls -la shared/ || echo 'No shared directory'", "cd ./shared/main-project && ls -la *.md || cd {self.project_path} && ls -la *.md"]
    }},
    "sysadmin": {{
      "responsibilities": ["System setup", "User management", "Service configuration", "Package management", "System hardening"],
      "check_in_interval": 30,
      "initial_commands": ["pwd", "sudo -n true && echo 'sudo available' || echo 'need sudo password'", "uname -a", "lsb_release -a 2>/dev/null || cat /etc/os-release"]
    }},
    "securityops": {{
      "responsibilities": ["Security hardening", "Firewall configuration", "Access control", "SSL/TLS setup", "Security monitoring"],
      "check_in_interval": 30,
      "initial_commands": ["pwd", "sudo iptables -L -n 2>/dev/null || echo 'checking firewall status'", "sestatus 2>/dev/null || echo 'SELinux not available'"]
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

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing specification with Claude (may take 5-20 minutes)...", total=None)
            
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
                import threading
                import time
                
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
                
                # Run subprocess in background with progress updates
                result_container = {}
                error_container = {}
                
                def run_claude():
                    try:
                        logger.info(f"Starting Claude analysis with script: {script_file}")
                        result = subprocess.run(
                            ['bash', script_file],
                            capture_output=True,
                            text=True,
                            timeout=1200  # Increased timeout to 20 minutes for complex Claude analysis
                        )
                        logger.info(f"Claude analysis completed with exit code: {result.returncode}")
                        if result.stderr:
                            logger.warning(f"Claude stderr: {result.stderr}")
                        if result.returncode != 0:
                            logger.error(f"Claude failed with exit code {result.returncode}")
                        result_container['result'] = result
                    except Exception as e:
                        logger.error(f"Claude subprocess exception: {e}")
                        error_container['error'] = e
                
                claude_thread = threading.Thread(target=run_claude)
                claude_thread.start()
                
                # Update progress with elapsed time while Claude runs
                start_time = time.time()
                while claude_thread.is_alive():
                    elapsed = time.time() - start_time
                    progress.update(task, description=f"Analyzing with Claude ({elapsed:.0f}s elapsed, est. 5-20min)...")
                    time.sleep(5)  # Update every 5 seconds
                
                claude_thread.join()
                
                if 'error' in error_container:
                    raise error_container['error']
                
                result = result_container['result']
                
                try:
                    pass  # Cleanup happens in finally block below
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
    
    def _analyze_tasks_for_dev(self) -> bool:
        """
        Analyzes all tasks in the implementation plan to detect if development (coding) is needed.
        Uses keyword/regex matching for indicators like file creation, implementation, or testing.
        """
        if not self.implementation_spec:
            return False
            
        dev_indicators = [
            r'implement', r'create.*\.py', r'write.*(test|code)', r'integrate', r'develop', r'build',
            r'coding', r'function', r'class', r'module', r'api', r'endpoint'
        ]
        pattern = re.compile('|'.join(dev_indicators), re.IGNORECASE)
        
        # Check all tasks in all phases
        for phase in self.implementation_spec.implementation_plan.phases:
            for task in phase.tasks:
                if pattern.search(task):
                    return True
        
        # Also check project type
        if self.implementation_spec.project.type in ['python', 'javascript', 'go', 'java']:
            return True
            
        return False
    
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
        
        # Show if development was detected
        if self._analyze_tasks_for_dev():
            console.print("[green]✓ Development tasks detected - Developer and Tester roles enforced[/green]")
        
        # Token usage warning
        team_size = len(roles_to_deploy)
        if team_size >= 4:
            console.print(f"\n[yellow]⚠️  Token Usage Warning[/yellow]")
            console.print(f"[yellow]Running {team_size} agents concurrently will use ~{team_size * 15}x normal token consumption[/yellow]")
            console.print(f"[yellow]On {self.plan_type} plan, this provides approximately {225 // (team_size * 15)} messages per 5-hour session[/yellow]")
            
            if team_size >= 5 and self.plan_type == 'max5':
                console.print(f"[red]Consider using fewer agents or upgrading to max20 plan for extended sessions[/red]")
        
        # Auto-approve setup - no manual confirmation needed
        console.print("\n[green]✓ Proceeding with automated setup...[/green]")
        return True
    
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
        """Determine which roles to deploy using dynamic team composition
        
        DYNAMIC TEAM DEPLOYMENT:
        - Analyzes project type and automatically selects appropriate roles
        - Supports custom role selection via --roles
        - Enforces plan constraints for token management
        - Can be overridden with --team-type
        """
        # Role mapping for display names
        role_mapping = {
            'orchestrator': ('Orchestrator', 'orchestrator'),
            'project_manager': ('Project-Manager', 'project_manager'),
            'developer': ('Developer', 'developer'),
            'tester': ('Tester', 'tester'),
            'testrunner': ('TestRunner', 'testrunner'),
            'researcher': ('Researcher', 'researcher'),
            'documentation_writer': ('Documentation', 'documentation_writer'),
            'devops': ('DevOps', 'devops'),
            'code_reviewer': ('Code-Reviewer', 'code_reviewer'),
            'logtracker': ('LogTracker', 'logtracker'),
            # System operations roles
            'sysadmin': ('SysAdmin', 'sysadmin'),
            'securityops': ('SecurityOps', 'securityops'),
            'networkops': ('NetworkOps', 'networkops'),
            'monitoringops': ('MonitoringOps', 'monitoringops'),
            'databaseops': ('DatabaseOps', 'databaseops')
        }
        
        # If custom roles are specified via --roles, use them
        if self.additional_roles:
            console.print(f"\n[bold]Using custom role selection[/bold]")
            selected_roles = []
            
            # Always include orchestrator if not explicitly added
            if 'orchestrator' not in [r.lower() for r in self.additional_roles]:
                selected_roles.append(role_mapping['orchestrator'])
            
            # Add requested roles
            for role in self.additional_roles:
                role_lower = role.lower()
                if role_lower in role_mapping:
                    if role_mapping[role_lower] not in selected_roles:
                        selected_roles.append(role_mapping[role_lower])
                else:
                    console.print(f"[yellow]Warning: Unknown role '{role}' - skipping[/yellow]")
            
            # CRITICAL FIX: Even with custom roles, ensure Developer/Tester if coding detected
            needs_dev = self._analyze_tasks_for_dev()
            if needs_dev:
                has_developer = any(role[1] == 'developer' for role in selected_roles)
                has_tester = any(role[1] == 'tester' for role in selected_roles)
                
                if not has_developer:
                    selected_roles.append(role_mapping['developer'])
                    console.print(f"[yellow]⚠️  Detected coding tasks - Adding Developer role (required)[/yellow]")
                
                if not has_tester:
                    selected_roles.append(role_mapping['tester'])
                    console.print(f"[yellow]⚠️  Detected coding tasks - Adding Tester role (required)[/yellow]")
        else:
            # Use dynamic team composition
            console.print(f"\n[bold]Analyzing project for optimal team composition...[/bold]")
            
            # Get team recommendation
            team_recommendation = self.dynamic_team_composer.recommend_team_size(
                str(self.project_path),
                subscription_plan=self.plan_type
            )
            
            # Compose the team
            team_comp = self.dynamic_team_composer.compose_team(
                str(self.project_path),
                force_type=self.team_type,
                include_optional=False  # Don't include optional by default
            )
            
            # Display analysis results
            console.print(f"Project Type: [cyan]{team_comp['project_type']}[/cyan]")
            console.print(f"Detection Confidence: [cyan]{team_comp['confidence']:.1%}[/cyan]")
            console.print(f"Complexity Score: [cyan]{team_recommendation['complexity']['complexity_score']:.1f}[/cyan]")
            console.print(f"Reasoning: {team_comp['reasoning']}")
            
            # Get the recommended roles
            roles_to_use = team_recommendation['selected_roles']
            
            # Convert to display format
            selected_roles = []
            for role in roles_to_use:
                if role in role_mapping:
                    selected_roles.append(role_mapping[role])
        
        # CRITICAL FIX: Detect if development is needed and enforce core roles
        needs_dev = self._analyze_tasks_for_dev()
        if needs_dev:
            # Check if Developer and Tester are already in the team
            has_developer = any(role[1] == 'developer' for role in selected_roles)
            has_tester = any(role[1] == 'tester' for role in selected_roles)
            
            if not has_developer:
                selected_roles.append(role_mapping['developer'])
                console.print(f"[yellow]⚠️  Detected coding tasks - Adding Developer role (required)[/yellow]")
            
            if not has_tester:
                selected_roles.append(role_mapping['tester'])
                console.print(f"[yellow]⚠️  Detected coding tasks - Adding Tester role (required)[/yellow]")
        
        # Enforce plan constraints
        max_agents = self.get_plan_constraints()
        if len(selected_roles) > max_agents:
            console.print(f"\n[yellow]⚠️  Warning: {len(selected_roles)} agents recommended but {self.plan_type} plan supports max {max_agents}[/yellow]")
            console.print(f"[yellow]Team will be limited to {max_agents} agents to prevent token exhaustion[/yellow]")
            console.print(f"[yellow]Multi-agent systems use ~15x more tokens than standard usage[/yellow]\n")
            
            # Prioritize roles based on importance and project type
            if self.team_type == 'system_deployment' or (hasattr(team_comp, 'project_type') and team_comp['project_type'] == 'system_deployment'):
                priority_order = ['orchestrator', 'sysadmin', 'devops', 'securityops', 'project_manager', 'networkops', 'monitoringops', 'databaseops']
            else:
                priority_order = ['orchestrator', 'developer', 'project_manager', 'tester', 'testrunner', 'researcher', 'devops', 'logtracker', 'code_reviewer', 'documentation_writer']
            
            # Sort roles by priority
            selected_roles.sort(key=lambda x: priority_order.index(x[1]) if x[1] in priority_order else 999)
            
            # Trim to max agents
            selected_roles = selected_roles[:max_agents]
        
        console.print(f"\n[green]Selected roles ({len(selected_roles)}): {', '.join([r[0] for r in selected_roles])}[/green]")
        
        return selected_roles
    
    def check_existing_worktrees(self, project_name: str, roles_to_deploy: List[Tuple[str, str]]) -> List[str]:
        """Check if worktrees already exist for this project"""
        # Use the new worktree location in the project repository
        worktrees_base = self.get_worktrees_base_dir(project_name)
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
        
    def detect_existing_orchestration(self, project_name: str) -> Optional[SessionState]:
        """Detect existing orchestration and load its state"""
        return self.session_state_manager.load_session_state(project_name)
    
    def validate_and_recover_session(self, session_state: SessionState) -> bool:
        """Validate session state and recover broken sessions in daemon mode
        
        Returns True if session is valid or successfully recovered, False otherwise
        """
        try:
            from tmux_utils import session_exists, kill_session, recreate_session
            
            # Check if main session exists
            if not session_exists(session_state.session_name):
                console.print(f"[yellow]Session {session_state.session_name} not found, will be recreated[/yellow]")
                return True  # Let resume_orchestration handle recreation
            
            # Validate agents have valid tmux windows
            valid_agents = []
            for agent in session_state.agents:
                target = f"{session_state.session_name}:{agent.window_index}"
                result = subprocess.run(['tmux', 'display-message', '-t', target], 
                                      capture_output=True, stderr=subprocess.DEVNULL)
                if result.returncode == 0:
                    valid_agents.append(agent)
                else:
                    console.print(f"[yellow]Agent {agent.role} window {agent.window_index} not found[/yellow]")
            
            if len(valid_agents) == 0:
                console.print("[yellow]No valid agent windows found - session needs recreation[/yellow]")
                # Kill the broken session
                kill_session(session_state.session_name)
                return True  # Let resume_orchestration handle recreation
            
            # Update session state with valid agents only
            session_state.agents = valid_agents
            
            console.print(f"[green]Session validation passed: {len(valid_agents)} valid agents[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]Session validation failed: {e}[/red]")
            return False
        
    def resume_orchestration(self, session_state: SessionState, resume_mode: str = 'full') -> bool:
        """Resume an existing orchestration session
        
        Args:
            session_state: The loaded session state
            resume_mode: One of 'full', 'selective', 'status'
            
        Returns:
            True if resume was successful
        """
        console.print(Panel.fit(
            f"[bold cyan]Resuming Orchestration Session[/bold cyan]\n"
            f"Project: {session_state.project_name}\n"
            f"Session: {session_state.session_name}\n"
            f"Created: {session_state.created_at}",
            title="📋 Resume Details"
        ))
        
        # Migrate existing worktrees to have sandbox symlinks
        console.print("\n[cyan]Checking sandbox setup for existing worktrees...[/cyan]")
        self.path_manager.migrate_sandboxes()
        
        # Update agent status
        console.print("\n[cyan]Checking agent status...[/cyan]")
        session_state = self.session_state_manager.update_agent_status(
            session_state, session_state.session_name
        )
        
        # Display summary
        summary = self.session_state_manager.get_session_summary(session_state)
        
        table = Table(title="Agent Status")
        table.add_column("Role", style="cyan")
        table.add_column("Window", style="yellow")
        table.add_column("Status", style="green")
        table.add_column("Branch", style="blue")
        table.add_column("Worktree", style="white")
        
        for role, info in summary['agents'].items():
            status = "✓ Active" if info['alive'] else "✗ Dead"
            if info['exhausted']:
                status = "⚠️ Exhausted"
            table.add_row(
                role,
                str(info['window']),
                status,
                info['branch'] or "unknown",
                Path(info['worktree']).name if info['worktree'] else "none"
            )
            
        console.print(table)
        
        # Load implementation spec
        if not Path(session_state.implementation_spec_path).exists():
            console.print(f"[red]Error: Implementation spec not found at {session_state.implementation_spec_path}[/red]")
            return False
            
        with open(session_state.implementation_spec_path, 'r') as f:
            spec_dict = json.load(f)
            
        # Reconstruct implementation spec
        self.implementation_spec = ImplementationSpec(**spec_dict)
        self.project_path = Path(session_state.project_path)
        
        # Handle different resume modes
        if resume_mode == 'status':
            console.print("\n[green]Status check complete. No changes made.[/green]")
            console.print(f"To attach: [cyan]tmux attach -t {session_state.session_name}[/cyan]")
            return True
            
        elif resume_mode == 'full':
            # Check if --rebrief-all was used
            if hasattr(self, 'rebrief_all') and self.rebrief_all:
                choice = '2'  # Force re-brief all
            else:
                console.print("\n[bold]Full Resume Options:[/bold]")
                console.print("1. [green]Restart dead agents[/green] - Restart any non-responsive agents")
                console.print("2. [cyan]Re-brief all agents[/cyan] - Send context restoration to all agents")
                console.print("3. [yellow]Both[/yellow] - Restart dead and re-brief all")
                console.print("4. [red]Cancel[/red] - Exit without changes")
                
                choice = click.prompt("\nYour choice", type=click.Choice(['1', '2', '3', '4']), default='3')
            
            if choice == '4':
                console.print("[yellow]Resume cancelled.[/yellow]")
                return False
                
            # Restart dead agents
            restarted_agents = []
            if choice in ['1', '3']:
                for role, agent in session_state.agents.items():
                    if not agent.is_alive:
                        console.print(f"\n[yellow]Restarting {role} agent...[/yellow]")
                        self.restart_agent(session_state, agent)
                        restarted_agents.append(role)
                        
            # Re-brief all agents
            if choice in ['2', '3']:
                for role, agent in session_state.agents.items():
                    # For option 2, try to rebrief all agents regardless of status
                    # For option 3, only rebrief if alive or just restarted
                    if choice == '2' or (choice == '3' and (agent.is_alive or role in restarted_agents)):
                        console.print(f"\n[cyan]Re-briefing {role} agent...[/cyan]")
                        self.rebrief_agent(session_state, agent)
                        
        # Save updated state
        self.session_state_manager.save_session_state(session_state)
        
        console.print(f"\n[green]✓ Resume complete![/green]")
        console.print(f"To attach: [cyan]tmux attach -t {session_state.session_name}[/cyan]")
        
        # Restart completion monitoring if not already completed
        if hasattr(session_state, 'completion_status') and session_state.completion_status == 'pending':
            console.print(f"\n[cyan]Restarting project completion monitoring...[/cyan]")
            
            # Reconstruct worktree paths from agent states
            worktree_paths = {}
            for role, agent in session_state.agents.items():
                if agent.worktree_path:
                    worktree_paths[role] = Path(agent.worktree_path)
            
            # Start monitoring
            self.completion_manager.monitor(
                session_name=session_state.session_name,
                project_name=session_state.project_name,
                spec=self.implementation_spec,
                worktree_paths=worktree_paths,
                spec_path=session_state.spec_path or str(self.spec_path),
                batch_mode=False
            )
            console.print(f"[green]✓ Completion monitoring restarted (checks every 5 minutes)[/green]")
        elif hasattr(session_state, 'completion_status'):
            console.print(f"\n[cyan]Project already marked as: {session_state.completion_status}[/cyan]")
        
        # Schedule credit-exhausted agents for auto-resume
        exhausted_agents = [a for a in session_state.agents.values() if a.is_exhausted]
        if exhausted_agents:
            console.print(f"\n[yellow]Note: {len(exhausted_agents)} agents are credit-exhausted.[/yellow]")
            self.schedule_exhausted_agents(session_state, exhausted_agents)
            
        return True
        
    def setup_single_agent_worktree(self, agent: AgentState, project_path: Path) -> bool:
        """Create a worktree for a single agent if it doesn't exist"""
        worktree_path = Path(agent.worktree_path)
        
        # Check if worktree already exists
        if worktree_path.exists() and (worktree_path / '.git').exists():
            console.print(f"[green]✓ Worktree already exists for {agent.role}[/green]")
            return True
        
        console.print(f"[yellow]Creating missing worktree for {agent.role}...[/yellow]")
        
        # Ensure parent directory exists
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use the same robust worktree creation strategies as setup_worktrees()
        worktree_created = False
        current_branch = "main"  # Default fallback
        
        # Get current branch
        branch_result = subprocess.run([
            'git', 'rev-parse', '--abbrev-ref', 'HEAD'
        ], cwd=str(project_path), capture_output=True, text=True)
        
        if branch_result.returncode == 0:
            current_branch = branch_result.stdout.strip()
        
        # Strategy 1: Try normal worktree with current branch
        agent_branch = f"{current_branch}-{agent.role}"
        result = subprocess.run([
            'git', 'worktree', 'add', 
            '-b', agent_branch,
            str(worktree_path),
            current_branch
        ], cwd=str(project_path), capture_output=True, text=True)
        
        if result.returncode == 0:
            worktree_created = True
        
        # Strategy 2: Force with existing branch
        if not worktree_created and "already exists" in result.stderr:
            console.print(f"[yellow]Branch {agent_branch} exists, using force flag[/yellow]")
            result = subprocess.run([
                'git', 'worktree', 'add', '--force',
                str(worktree_path),
                agent_branch
            ], cwd=str(project_path), capture_output=True, text=True)
            
            if result.returncode == 0:
                worktree_created = True
        
        # Strategy 3: Detached HEAD fallback
        if not worktree_created:
            console.print(f"[yellow]Creating detached worktree at HEAD[/yellow]")
            
            # Get current commit hash
            commit_result = subprocess.run([
                'git', 'rev-parse', 'HEAD'
            ], cwd=str(project_path), capture_output=True, text=True)
            
            if commit_result.returncode == 0:
                commit_hash = commit_result.stdout.strip()
                result = subprocess.run([
                    'git', 'worktree', 'add', 
                    '--detach',
                    str(worktree_path),
                    commit_hash
                ], cwd=str(project_path), capture_output=True, text=True)
                
                if result.returncode == 0:
                    worktree_created = True
        
        if not worktree_created:
            console.print(f"[red]Failed to create worktree for {agent.role}[/red]")
            console.print(f"[red]Error: {result.stderr}[/red]")
            return False
        
        # Copy .mcp.json if it exists
        project_mcp = project_path / '.mcp.json'
        if project_mcp.exists():
            worktree_mcp = worktree_path / '.mcp.json'
            try:
                import shutil
                shutil.copy2(project_mcp, worktree_mcp)
                console.print(f"[green]✓ Copied .mcp.json to {agent.role}'s worktree[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not copy .mcp.json to {agent.role}: {e}[/yellow]")
        
        # Setup MCP configuration
        self.setup_mcp_for_worktree(worktree_path)
        self.enable_mcp_servers_in_claude_config(worktree_path)
        
        # Set up hooks for the restarted agent
        agent_id = f"{session_state.session_name}:{agent.window_index}"
        try:
            setup_agent_hooks(
                worktree_path=worktree_path,
                agent_id=agent_id,
                orchestrator_path=self.tmux_orchestrator_path,
                db_path=self.tmux_orchestrator_path / 'task_queue.db'
            )
            console.print(f"[green]✓ Set up hooks for {agent.role} agent[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not set up hooks for {agent.role}: {e}[/yellow]")
        
        console.print(f"[green]✓ Created worktree for {agent.role} at {worktree_path}[/green]")
        return True

    def restart_agent(self, session_state: SessionState, agent: AgentState):
        """Restart a dead agent by recreating its window and briefing"""
        # Ensure the agent has a valid worktree before proceeding
        project_path = Path(session_state.project_path)
        if not self.setup_single_agent_worktree(agent, project_path):
            console.print(f"[red]Cannot restart {agent.role} - worktree creation failed[/red]")
            return
        
        # Kill the existing window if it exists
        subprocess.run([
            'tmux', 'kill-window', '-t', f'{session_state.session_name}:{agent.window_index}'
        ], capture_output=True)
        
        # Recreate the window
        subprocess.run([
            'tmux', 'new-window', '-t', f'{session_state.session_name}:{agent.window_index}',
            '-n', agent.window_name, '-c', agent.worktree_path
        ], capture_output=True)
        
        # Start Claude and send briefing
        # Note: We don't have role_config here, but it's only used for briefing
        # which we handle separately in create_role_briefing
        
        # Check MCP pre-initialization
        worktree_path = Path(agent.worktree_path)
        if (worktree_path / '.mcp.json').exists():
            self.pre_initialize_claude_in_worktree(
                session_state.session_name, agent.window_index, 
                agent.role, worktree_path
            )
            
            # No additional wait needed - pre_initialize_claude_in_worktree now waits 10 seconds total
            # for OAuth server cleanup to avoid port conflicts
            
            # Kill and recreate window after MCP approval
            subprocess.run([
                'tmux', 'kill-window', '-t', f'{session_state.session_name}:{agent.window_index}'
            ], capture_output=True)
            
            # Wait for OAuth port to be released after killing the window
            oauth_port = int(os.environ.get('CLAUDE_OAUTH_PORT', '3000'))
            self.wait_for_port_free(oauth_port, max_wait=10)
            
            subprocess.run([
                'tmux', 'new-window', '-t', f'{session_state.session_name}:{agent.window_index}',
                '-n', agent.window_name, '-c', agent.worktree_path
            ], capture_output=True)
            
        # Start Claude with --dangerously-skip-permissions
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_state.session_name}:{agent.window_index}',
            'claude --dangerously-skip-permissions', 'Enter'
        ])
        time.sleep(5)
        
        # Send briefing
        # For restart, we'll use a simplified briefing since we don't have the full role config
        briefing = f"""🔄 **Agent Restart**

You are the {agent.window_name} for the {session_state.project_name} project.

Your worktree is at: {agent.worktree_path}

Please:
1. Check your current status with `git status`
2. Review recent work with `git log --oneline -10`
3. Report to the Project Manager with your current status
4. Continue with your assigned tasks"""
        
        # Use unified messenger for standardized communication
        self.messenger.send_briefing(
            f'{session_state.session_name}:{agent.window_index}',
            briefing
        )
        
        # Update agent state
        agent.is_alive = True
        agent.last_briefing_time = datetime.now().isoformat()
        
    def rebrief_agent(self, session_state: SessionState, agent: AgentState):
        """Send a context restoration message to an existing agent"""
        # Get role description based on role
        role_descriptions = {
            'orchestrator': 'High-level oversight and coordination',
            'project_manager': 'Quality assurance and team coordination',
            'developer': 'Implementation and technical execution',
            'researcher': 'Research best practices and utilize MCP tools',
            'tester': 'Test execution and quality verification',
            'testrunner': 'Automated test coordination',
            'devops': 'Infrastructure and deployment',
            'logtracker': 'Monitoring and log analysis',
            'code_reviewer': 'Code quality and security review'
        }
        
        role_desc = role_descriptions.get(agent.role, 'Team member')
        
        # Create a shorter re-briefing focused on context restoration
        rebrief_msg = f"""🔄 **Context Restoration**

You are the {agent.window_name} for the {session_state.project_name} project.

**Current Status**:
- Working directory: {agent.worktree_path}
- Current branch: {agent.current_branch or 'unknown'}
- Project continues from where you left off

**Quick Reminders**:
1. Check your recent work with `git log --oneline -10`
2. Review uncommitted changes with `git status`
3. Your role: {role_desc}
4. Report to PM for coordination

Please provide a brief status update on your current work and any blockers."""
        
        # Use unified messenger for standardized communication
        self.messenger.send_message(
            f'{session_state.session_name}:{agent.window_index}',
            rebrief_msg
        )
        
        agent.last_briefing_time = datetime.now().isoformat()
        
    def schedule_exhausted_agents(self, session_state: SessionState, exhausted_agents: List[AgentState]):
        """Schedule exhausted agents for auto-resume when credits reset"""
        # Check if credit monitoring is available
        credit_schedule_path = Path.home() / '.claude' / 'credit_schedule.json'
        if not credit_schedule_path.exists():
            console.print("[yellow]Credit monitoring not available. Manual resume required.[/yellow]")
            return
            
        # Get reset time from first exhausted agent
        reset_time = None
        for agent in exhausted_agents:
            if agent.credit_reset_time:
                reset_time = agent.credit_reset_time
                break
                
        if reset_time:
            console.print(f"[cyan]Credits expected to reset at: {reset_time}[/cyan]")
            console.print("[cyan]Consider using credit_monitor.py for automatic resume[/cyan]")
    
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
        
        # Create external worktrees directory following Grok's best practices
        # EXTERNAL LOCATION: Avoids nested worktree issues and git clean risks
        project_name = self.sanitize_project_name(spec.project.name)
        worktrees_base = self.get_worktrees_base_dir(project_name)
        worktrees_base.mkdir(parents=True, exist_ok=True)
        
        console.print(f"[cyan]Creating worktrees in external directory: {worktrees_base}[/cyan]")
        
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
                    # Check if it's a locked worktree issue
                    if "missing but locked" in result.stderr:
                        console.print(f"[yellow]Worktree is locked, attempting to unlock and retry...[/yellow]")
                        
                        # Try to unlock the worktree
                        unlock_result = subprocess.run([
                            'git', 'worktree', 'unlock', str(worktree_path)
                        ], cwd=str(self.project_path), capture_output=True, text=True)
                        
                        # Try to remove it
                        remove_result = subprocess.run([
                            'git', 'worktree', 'remove', str(worktree_path), '--force'
                        ], cwd=str(self.project_path), capture_output=True, text=True)
                        
                        # Prune to clean up
                        subprocess.run([
                            'git', 'worktree', 'prune'
                        ], cwd=str(self.project_path), capture_output=True)
                        
                        # Try one more time with -f -f as suggested
                        console.print(f"[yellow]Retrying with force flags...[/yellow]")
                        result = subprocess.run([
                            'git', 'worktree', 'add', 
                            '-f', '-f',  # Double force as suggested in error message
                            str(worktree_path),
                            current_branch
                        ], cwd=str(self.project_path), capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            worktree_created = True
                    
                    if not worktree_created:
                        console.print(f"[red]Failed to create worktree for {role_key} after all strategies[/red]")
                        console.print(f"[red]Error: {result.stderr}[/red]")
                        sys.exit(1)
                    
                worktree_paths[role_key] = worktree_path
                
                # Apply Grok's safety recommendations: lock worktree
                self.setup_worktree_safety(worktree_path)
                
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
                
                # Set up hooks for this agent
                # Note: We don't have the session name yet since we're setting up worktrees
                # before creating the tmux session. Hooks will be configured after session creation.
                # This is just preparation for when the session is created.
                
                # Set up sandbox symlinks for this role
                active_roles = [role for _, role in roles_to_deploy]
                if not self.path_manager.setup_sandbox_for_role(role_key, active_roles):
                    console.print(f"[yellow]Warning: Sandbox setup failed for {role_key}. Agent will use cd-free fallback.[/yellow]")
                    # Store fallback state in session if available
                    if hasattr(self, 'session_state_manager') and self.session_state_manager:
                        state = self.session_state_manager.load_session_state(self.project_name)
                        if state and role_key in state.agents:
                            self.session_state_manager.update_agent_state(
                                self.project_name, 
                                role_key, 
                                {'sandbox_mode': 'cd_free'}
                            )
                
                progress.update(task, advance=1, description=f"Created worktree for {role_key}")
        
        # Display worktree summary
        console.print("\n[green]✓ Git worktrees created:[/green]")
        for role, path in worktree_paths.items():
            # Show path relative to project parent directory for external worktrees
            try:
                # Try to show relative to project parent for cleaner display
                relative_path = path.relative_to(self.project_path.parent)
                console.print(f"  {role}: {relative_path}")
            except ValueError:
                # If that fails, just show the absolute path
                console.print(f"  {role}: {path}")
        
        # Setup fast lane coordination for eligible roles
        # Pass the actual directory name (with UUID if using unique registry)
        if self.unique_registry_dir:
            # Extract the directory name with UUID from the path
            actual_project_dir = self.unique_registry_dir.name
        else:
            actual_project_dir = project_name
        self.setup_fast_lane_coordination(actual_project_dir, roles_to_deploy)
        
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
        # Use the new worktree location in the project repository
        worktrees_base = self.get_worktrees_base_dir(project_name)
        if worktrees_base.exists():
            console.print("\n[yellow]Cleaning up worktrees...[/yellow]")
            
            # First, try to properly remove each worktree through git
            for worktree in worktrees_base.iterdir():
                if worktree.is_dir():
                    # Try to unlock first (in case it's locked)
                    subprocess.run([
                        'git', 'worktree', 'unlock', str(worktree)
                    ], cwd=str(self.project_path), capture_output=True)
                    
                    # Try to remove through git
                    subprocess.run([
                        'git', 'worktree', 'remove', str(worktree), '--force'
                    ], cwd=str(self.project_path), capture_output=True)
            
            # Prune any stale entries
            subprocess.run(['git', 'worktree', 'prune'], 
                         cwd=str(self.project_path), capture_output=True)
            
            # Finally, remove the physical directories if they still exist
            for worktree in worktrees_base.iterdir():
                if worktree.is_dir():
                    subprocess.run(['rm', '-rf', str(worktree)], capture_output=True)
            
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
    
    def setup_agent_uv_environment(self, session_name: str, window_idx: int, role_key: str):
        """Set up UV environment for an agent's tmux window to work in worktrees"""
        try:
            # Set UV_NO_WORKSPACE for this specific tmux window
            subprocess.run([
                'tmux', 'set-environment', '-t', f'{session_name}:{window_idx}', 
                'UV_NO_WORKSPACE', '1'
            ], check=True, capture_output=True)
            
            # Optional: Set a custom cache dir to avoid polluting target
            cache_dir = f"/tmp/tmux-orchestrator-uv-cache-{session_name}-{role_key}"
            subprocess.run([
                'tmux', 'set-environment', '-t', f'{session_name}:{window_idx}',
                'UV_CACHE_DIR', cache_dir
            ], check=True, capture_output=True)
            
            console.print(f"[green]✓ Set UV environment for {role_key} in window {window_idx}[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[yellow]Warning: Could not set UV environment for {role_key}: {e}[/yellow]")
        
        # Set up hooks for this agent now that we have the session info
        if role_key in self.worktree_paths:
            agent_id = f"{session_name}:{window_idx}"
            try:
                setup_agent_hooks(
                    worktree_path=self.worktree_paths[role_key],
                    agent_id=agent_id,
                    orchestrator_path=self.tmux_orchestrator_path,
                    db_path=self.tmux_orchestrator_path / 'task_queue.db'
                )
                console.print(f"[green]✓ Set up hooks for {role_key} agent[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not set up hooks for {role_key}: {e}[/yellow]")
    
    def sanitize_session_name(self, name: str) -> str:
        """Sanitize a name to be safe for tmux session names"""
        # Replace spaces and special characters with hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '-', name.lower())
        # Remove multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        return sanitized[:20]
    
    def sanitize_project_name(self, name: str) -> str:
        """Sanitize a name to be safe for directory names"""
        # Replace spaces and special characters with hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '-', name.lower())
        # Remove multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        return sanitized
    
    def get_worktrees_base_dir(self, project_name: str) -> Path:
        """Get the base directory for worktrees - EXTERNAL to project to avoid Git issues"""
        # Check if custom worktree base path is set (for --new-project mode)
        if hasattr(self, 'custom_worktree_base') and self.custom_worktree_base:
            return Path(self.custom_worktree_base)
        
        # BEST PRACTICE: Following Grok's recommendation to place worktrees outside project
        # This avoids nested worktree issues, git clean risks, and repository bloat
        # Format: /path/to/project-name-worktrees/ (sibling to project directory)
        project_dir_name = self.project_path.name
        return self.project_path.parent / f"{project_dir_name}-tmux-worktrees"
    
    def setup_worktree_safety(self, worktree_path: Path):
        """Configure worktree safety measures following Grok's recommendations"""
        # Lock worktree to prevent accidental deletion from git worktree prune
        try:
            subprocess.run(['git', 'worktree', 'lock', str(worktree_path)], 
                         cwd=str(self.project_path), capture_output=True, check=True)
            console.print(f"[green]✓ Locked worktree {worktree_path.name} for safety[/green]")
        except subprocess.CalledProcessError:
            console.print(f"[yellow]⚠️  Could not lock worktree {worktree_path.name}[/yellow]")
    
    def resolve_session_conflicts(self, session_name: str) -> bool:
        """
        Resolve tmux session conflicts with sophisticated strategies.
        
        Args:
            session_name: The session name to check for conflicts
            
        Returns:
            True if conflicts were resolved or no conflicts exist, False if unresolvable
        """
        try:
            # In batch/daemon mode, clean up similar sessions first
            if self.daemon_mode or self.batch_mode:
                self._cleanup_similar_sessions(session_name)
            
            # Check if session exists
            result = subprocess.run(['tmux', 'has-session', '-t', session_name], capture_output=True)
            if result.returncode != 0:
                # No conflict - session doesn't exist
                return True
            
            console.print(f"[yellow]Session conflict detected: '{session_name}' already exists[/yellow]")
            
            # Get session details for analysis
            session_info = self._get_session_info(session_name)
            
            if self.daemon_mode or self.batch_mode:
                # In non-interactive mode, use automatic resolution
                return self._auto_resolve_conflict(session_name, session_info)
            else:
                # In interactive mode, prompt user for resolution strategy
                return self._interactive_resolve_conflict(session_name, session_info)
                
        except Exception as e:
            console.print(f"[red]Error resolving session conflicts: {e}[/red]")
            return False
    
    def _get_session_info(self, session_name: str) -> dict:
        """Get detailed information about an existing tmux session"""
        info = {
            'windows': [],
            'created': None,
            'last_activity': None,
            'has_active_processes': False
        }
        
        try:
            # Get session creation time and activity
            result = subprocess.run(['tmux', 'display-message', '-t', session_name, 
                                   '-p', '#{session_created} #{session_activity}'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    info['created'] = int(parts[0])
                    info['last_activity'] = int(parts[1])
            
            # Get windows and their processes
            result = subprocess.run(['tmux', 'list-windows', '-t', session_name,
                                   '-F', '#{window_name}:#{window_active}'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        name, active = line.strip().split(':', 1)
                        info['windows'].append({'name': name, 'active': active == '1'})
            
            # Check for active processes (non-shell)
            result = subprocess.run(['tmux', 'list-panes', '-t', session_name, '-a',
                                   '-F', '#{pane_current_command}'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                commands = result.stdout.strip().split('\n')
                for cmd in commands:
                    if cmd.strip() and cmd.strip() not in ['bash', 'zsh', 'sh', 'fish']:
                        info['has_active_processes'] = True
                        break
                        
        except Exception as e:
            console.print(f"[yellow]Warning: Could not get full session info: {e}[/yellow]")
        
        return info
    
    def _auto_resolve_conflict(self, session_name: str, session_info: dict) -> bool:
        """Automatically resolve session conflicts in non-interactive mode"""
        try:
            # In batch/daemon mode, be more aggressive
            if self.batch_mode or self.daemon_mode:
                # Strategy 1: If session has been inactive for >30 minutes, kill it
                if session_info.get('last_activity'):
                    inactive_time = time.time() - session_info['last_activity']
                    if inactive_time > 1800:  # 30 minutes (reduced from 1 hour)
                        console.print(f"[yellow]Auto-resolving: Session inactive for {inactive_time/60:.0f} minutes, terminating[/yellow]")
                        return self._kill_session_safely(session_name)
                
                # Strategy 2: If no active processes, kill it immediately
                if not session_info.get('has_active_processes', True):
                    console.print(f"[yellow]Auto-resolving: No active processes detected, terminating session[/yellow]")
                    return self._kill_session_safely(session_name)
                
                # Strategy 3: In batch mode, kill conflicting session anyway
                console.print(f"[yellow]Auto-resolving: Batch mode - terminating conflicting session[/yellow]")
                return self._kill_session_safely(session_name)
            
            # Normal mode strategies (not batch/daemon)
            # Strategy 1: If session has been inactive for >1 hour, kill it
            if session_info.get('last_activity'):
                inactive_time = time.time() - session_info['last_activity']
                if inactive_time > 3600:  # 1 hour
                    console.print(f"[yellow]Auto-resolving: Session inactive for {inactive_time/3600:.1f}h, terminating[/yellow]")
                    return self._kill_session_safely(session_name)
            
            # Strategy 2: If no active processes, kill it
            if not session_info.get('has_active_processes', True):
                console.print(f"[yellow]Auto-resolving: No active processes detected, terminating session[/yellow]")
                return self._kill_session_safely(session_name)
            
            # Strategy 3: If --force flag is used, kill regardless
            if self.force:
                console.print(f"[yellow]Auto-resolving: Force flag enabled, terminating session[/yellow]")
                return self._kill_session_safely(session_name)
            
            # Strategy 4: Try to rename the existing session
            backup_name = f"{session_name}-backup-{int(time.time())}"
            result = subprocess.run(['tmux', 'rename-session', '-t', session_name, backup_name],
                                  capture_output=True)
            if result.returncode == 0:
                console.print(f"[green]Auto-resolved: Renamed conflicting session to '{backup_name}'[/green]")
                return True
            
            # Strategy 5: Give up - cannot resolve automatically
            console.print(f"[red]Cannot auto-resolve conflict for session '{session_name}'[/red]")
            console.print("[yellow]Use --force to override, or manually resolve the conflict[/yellow]")
            return False
            
        except Exception as e:
            console.print(f"[red]Error in auto-resolution: {e}[/red]")
            return False
    
    def _interactive_resolve_conflict(self, session_name: str, session_info: dict) -> bool:
        """Interactively resolve session conflicts with user prompts"""
        console.print(f"\n[bold]Session Conflict Resolution[/bold]")
        console.print(f"Session: {session_name}")
        
        if session_info.get('windows'):
            console.print(f"Windows: {len(session_info['windows'])}")
            for window in session_info['windows'][:3]:  # Show first 3 windows
                console.print(f"  - {window['name']}")
        
        if session_info.get('has_active_processes'):
            console.print("[yellow]⚠️  Session has active processes[/yellow]")
        
        console.print("\nResolution options:")
        console.print("1. Kill existing session (may lose work)")
        console.print("2. Rename existing session (safe)")
        console.print("3. Cancel orchestration")
        
        while True:
            try:
                choice = input("\nEnter choice (1-3): ").strip()
                if choice == '1':
                    return self._kill_session_safely(session_name)
                elif choice == '2':
                    backup_name = f"{session_name}-backup-{int(time.time())}"
                    result = subprocess.run(['tmux', 'rename-session', '-t', session_name, backup_name],
                                          capture_output=True)
                    if result.returncode == 0:
                        console.print(f"[green]Renamed session to '{backup_name}'[/green]")
                        return True
                    else:
                        console.print("[red]Failed to rename session[/red]")
                        return False
                elif choice == '3':
                    console.print("[yellow]Orchestration cancelled[/yellow]")
                    return False
                else:
                    console.print("[red]Invalid choice. Please enter 1, 2, or 3.[/red]")
            except KeyboardInterrupt:
                console.print("\n[yellow]Cancelled[/yellow]")
                return False
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                return False
    
    def _kill_session_safely(self, session_name: str) -> bool:
        """Safely kill a tmux session with proper cleanup"""
        try:
            # First attempt graceful kill
            result = subprocess.run(['tmux', 'kill-session', '-t', session_name], 
                                  capture_output=True)
            
            if result.returncode == 0:
                # Verify session is gone
                time.sleep(0.5)
                check_result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                                            capture_output=True)
                if check_result.returncode != 0:
                    console.print(f"[green]Successfully terminated session '{session_name}'[/green]")
                    return True
            
            # If graceful kill failed, try force kill
            console.print(f"[yellow]Attempting force termination of session '{session_name}'[/yellow]")
            result = subprocess.run(['tmux', 'kill-session', '-t', session_name, '-f'], 
                                  capture_output=True)
            
            time.sleep(0.5)
            check_result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                                        capture_output=True)
            if check_result.returncode != 0:
                console.print(f"[green]Force terminated session '{session_name}'[/green]")
                return True
            else:
                console.print(f"[red]Failed to terminate session '{session_name}'[/red]")
                return False
                
        except Exception as e:
            console.print(f"[red]Error killing session '{session_name}': {e}[/red]")
            return False
    
    def _cleanup_similar_sessions(self, target_session_name: str) -> None:
        """
        Clean up similar or related tmux sessions in batch/daemon mode.
        This is more aggressive than normal conflict resolution.
        """
        try:
            # Get all existing sessions
            result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return  # No sessions exist
            
            existing_sessions = result.stdout.strip().split('\n')
            if not existing_sessions:
                return
            
            # Extract base name from target session (remove -impl, -dev, etc suffixes)
            base_name = target_session_name.split('-impl')[0].split('-dev')[0]
            
            # Find similar sessions
            similar_sessions = []
            for session in existing_sessions:
                if session and session != target_session_name:
                    # Check if session is similar
                    if any([
                        session.startswith(base_name),
                        f"{base_name}-" in session,
                        session.endswith(f"-{base_name}"),
                        # Also check for backup sessions
                        session.startswith(f"{target_session_name}-backup"),
                        # Check for numbered variants
                        any(session == f"{target_session_name}-{i}" for i in range(10))
                    ]):
                        similar_sessions.append(session)
            
            if similar_sessions:
                console.print(f"[yellow]Found {len(similar_sessions)} similar sessions to clean up[/yellow]")
                
            # Kill similar sessions
            for session in similar_sessions:
                session_info = self._get_session_info(session)
                
                # Be aggressive in batch mode - kill if:
                # 1. No active processes
                # 2. Inactive for more than 30 minutes
                # 3. Is a backup session
                should_kill = False
                kill_reason = ""
                
                if not session_info.get('has_active_processes', True):
                    should_kill = True
                    kill_reason = "no active processes"
                elif 'backup' in session:
                    should_kill = True
                    kill_reason = "backup session"
                elif session_info.get('last_activity'):
                    inactive_time = time.time() - session_info['last_activity']
                    if inactive_time > 1800:  # 30 minutes
                        should_kill = True
                        kill_reason = f"inactive for {inactive_time/60:.0f} minutes"
                
                if should_kill:
                    console.print(f"[yellow]Cleaning up similar session '{session}' ({kill_reason})[/yellow]")
                    self._kill_session_safely(session)
                    
        except Exception as e:
            console.print(f"[yellow]Warning: Error during similar session cleanup: {e}[/yellow]")
            # Don't fail - this is best effort cleanup
    
    def setup_tmux_session(self, spec: ImplementationSpec):
        """Set up the tmux session with roles based on project size using git worktrees"""
        # Use concurrent orchestration manager for unique naming
        if not self.unique_session_name:
            try:
                self.unique_session_name, self.unique_registry_dir = self.concurrent_manager.start_orchestration(
                    spec.project.name, timeout=30
                )
            except Exception as e:
                console.print(f"[red]Error starting orchestration: {e}[/red]")
                raise
        
        session_name = self.unique_session_name
        
        # Initialize AgentIdManager for session:window identification
        self.agent_id_manager = AgentIdManager(session_name)
        
        # Determine which roles to deploy
        roles_to_deploy = self.get_roles_for_project_size(spec)
        
        # Set up git worktrees for isolation
        worktree_paths = self.setup_worktrees(spec, roles_to_deploy)
        
        # Store worktree paths for later use
        self.worktree_paths = worktree_paths
        
        # Set up local remotes for fast coordination
        self.setup_git_locals()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            # Create tmux session
            task = progress.add_task("Creating tmux session...", total=len(roles_to_deploy))
            
            # Handle session conflicts using proper conflict resolution
            if not self.resolve_session_conflicts(session_name):
                raise RuntimeError(f"Could not resolve session conflicts for {session_name}")
            
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
            
            # Update database with session name if called from queue daemon
            if hasattr(self, 'project_id') and self.project_id:
                try:
                    from scheduler import TmuxOrchestratorScheduler
                    scheduler = TmuxOrchestratorScheduler()
                    scheduler.update_session_name(self.project_id, session_name)
                    console.print(f"[blue]Updated queue database with session name: {session_name}[/blue]")
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to update session name in database: {e}[/yellow]")
    
    def brief_all_roles(self, session_name: str, spec: ImplementationSpec, roles_to_deploy: List[Tuple[str, str]], worktree_paths: Dict[str, Path]):
        """Start Claude in each window and provide role-specific briefings"""
        
        # Check if Claude version supports context priming
        supports_context_prime = self.check_claude_version()
        
        # Convert roles_to_deploy to include window indices
        roles = [(name, idx, role) for idx, (name, role) in enumerate(roles_to_deploy)]
        
        # Register all agents with AgentIdManager
        for window_name, window_idx, role_key in roles:
            self.agent_id_manager.register_agent(role_key, window_idx)
        
        for window_name, window_idx, role_key in roles:
            # Set up UV environment BEFORE starting Claude
            self.setup_agent_uv_environment(session_name, window_idx, role_key)
            
            # Pre-initialize Claude for MCP servers
            worktree_path = worktree_paths.get(role_key)
            
            # Modified for robustness: Check global/system paths first, then worktree
            mcp_exists = False
            if self.global_mcp_init:
                # Check global paths first
                global_paths = [
                    Path.home() / '.mcp.json',  # User-level
                    Path('/etc/mcp.json'),       # System-level (adjust if needed)
                ]
                for global_path in global_paths:
                    if global_path.exists():
                        mcp_exists = True
                        console.print(f"[cyan]Global MCP config found at {global_path} for {role_key}[/cyan]")
                        break
            
            # Fallback to worktree if no global or flag is off
            if not mcp_exists and worktree_path:
                mcp_exists = (worktree_path / '.mcp.json').exists()
                if mcp_exists:
                    console.print(f"[cyan]Worktree MCP config found for {role_key}[/cyan]")
            
            if mcp_exists and worktree_path:
                # Pre-initialize Claude to approve MCP servers
                self.pre_initialize_claude_in_worktree(session_name, window_idx, role_key, worktree_path)
                
                # No additional wait needed - pre_initialize_claude_in_worktree now waits 10 seconds total
                # for OAuth server cleanup
                
                # Kill the window (since it only has one pane)
                kill_result = subprocess.run([
                    'tmux', 'kill-window', '-t', f'{session_name}:{window_idx}'
                ], capture_output=True)
                
                # Wait for OAuth port to be released after killing the window
                oauth_port = int(os.environ.get('CLAUDE_OAUTH_PORT', '3000'))
                self.wait_for_port_free(oauth_port, max_wait=10)
                
                # Create a new window at the same index
                # Using -a flag to insert at specific index
                create_result = subprocess.run([
                    'tmux', 'new-window', '-t', f'{session_name}:{window_idx}',
                    '-n', window_name, '-c', str(worktree_path),
                    '-d'  # Don't switch to it
                ], capture_output=True)
                
                if create_result.returncode != 0:
                    # Window might still exist, try without index
                    subprocess.run([
                        'tmux', 'new-window', '-t', session_name,
                        '-n', window_name, '-c', str(worktree_path),
                        '-d'
                    ], capture_output=True)
                
                console.print(f"[green]✓ Recreated window for {role_key} after MCP approval[/green]")
                
                # Longer delay to ensure window is ready
                time.sleep(2)
                
                # Start Claude with --dangerously-skip-permissions in the recreated window
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
                context_prime_msg = f'/context-prime "first: run context prime like normal, then: You are about to work on {spec.project.name} at {spec.project.path}. Understand the project structure, dependencies, and conventions."'
                try:
                    # Use unified messenger for context priming
                    self.messenger.send_message(f'{session_name}:{window_idx}', context_prime_msg)
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
            
            # Send briefing using unified messenger
            self.messenger.send_briefing(f'{session_name}:{window_idx}', briefing)
            
            # Send session name reminder to prevent communication errors
            session_reminder = f"""📍 **IMPORTANT SESSION INFO**
Your session: {session_name}
Orchestrator location: {session_name}:0

⚠️ Always use the FULL session name when reporting to the orchestrator.
DO NOT use shortened forms - use exactly: {session_name}:0
"""
            self.messenger.send_message(f'{session_name}:{window_idx}', session_reminder)
            
            # Run initial commands
            for cmd in role_config.initial_commands:
                time.sleep(2)
                self.messenger.send_command(f'{session_name}:{window_idx}', cmd)
            
            # Schedule check-ins
            # Modified to conditionally include orchestrator based on flag
            if role_key == 'orchestrator' and not self.enable_orchestrator_scheduling:
                # Skip orchestrator scheduling when flag is explicitly disabled
                console.print(f"[yellow]Skipping orchestrator scheduling (use --enable-orchestrator-scheduling to enable)[/yellow]")
                continue  # Skip to next role
            
            # Schedule for all roles (including orchestrator when enabled, which is default)
            # Use credit-aware scheduling if available
            credit_schedule_script = self.tmux_orchestrator_path / 'credit_management' / 'schedule_credit_aware.sh'
            regular_schedule_script = self.tmux_orchestrator_path / 'schedule_with_note.sh'
            
            schedule_script = credit_schedule_script if credit_schedule_script.exists() else regular_schedule_script
            
            check_in_interval = getattr(role_config, 'check_in_interval', 30)  # Default to 30 minutes
            
            subprocess.run([
                str(schedule_script),
                str(check_in_interval),
                f"{window_name} regular check-in",
                f"{session_name}:{window_idx}"
            ])
            
            console.print(f"[green]Scheduled check-in for {window_name} (window {window_idx}) every {check_in_interval} minutes[/green]")
    
    def clean_message_from_mcp_wrappers(self, message: str) -> str:
        """Enhanced MCP wrapper removal to handle all contamination patterns"""
        import re
        
        # Store original for comparison
        original = message
        
        # Remove exact MCP wrapper patterns (comprehensive)
        patterns = [
            # Common MCP wrappers
            r'^echo\s+[\'"]TMUX_MCP_START[\'"];\s*',
            r';\s*echo\s+[\'"]TMUX_MCP_DONE_\$\?[\'"]$',
            r'echo\s+[\'"]TMUX_MCP_START[\'"];\s*',
            r';\s*echo\s+[\'"]TMUX_MCP_DONE_\$\?[\'"]',
            
            # Alternative wrapper patterns
            r'echo\s+TMUX_MCP_START;\s*',
            r';\s*echo\s+TMUX_MCP_DONE_\$\?',
            r'echo\s+[\'"]MCP_EXECUTE_START[\'"];\s*',
            r';\s*echo\s+[\'"]MCP_EXECUTE_END_\$\?[\'"]',
            
            # Shell execution wrappers
            r'bash\s+-c\s+[\'"]echo\s+[\'"]?TMUX_MCP_START[\'"]?;\s*',
            r';\s*echo\s+[\'"]?TMUX_MCP_DONE_\$\?[\'"]?[\'"]',
            
            # Command substitution patterns
            r'\$\(\s*echo\s+[\'"]TMUX_MCP_START[\'"];\s*',
            r';\s*echo\s+[\'"]TMUX_MCP_DONE_\$\?[\'"]?\s*\)',
            
            # Inline wrapper remnants
            r'TMUX_MCP_START\s*;?\s*',
            r';\s*TMUX_MCP_DONE_\$\?\s*',
        ]
        
        # Apply all patterns iteratively until no more changes
        for _ in range(3):  # Maximum 3 passes to handle nested patterns
            before = message
            for pattern in patterns:
                message = re.sub(pattern, '', message)
            if message == before:
                break  # No more changes
        
        # Clean up artifacts
        message = re.sub(r';\s*;', ';', message)  # Double semicolons
        message = re.sub(r'^\s*;\s*', '', message)  # Leading semicolon
        message = re.sub(r'\s*;\s*$', '', message)  # Trailing semicolon
        message = re.sub(r'\s+', ' ', message)  # Multiple spaces
        message = message.strip()
        
        # Log significant changes for debugging
        if len(original) > len(message) + 20:  # Significant wrapper removal
            console.print(f"[dim]🧹 Cleaned MCP wrappers: {len(original)} → {len(message)} chars[/dim]")
        
        return message
    
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
    
    def create_communication_channels(self, current_role: str, roles_deployed: List[Tuple[str, str]]) -> str:
        """Create a communication channels reference table with correct window numbers"""
        if not roles_deployed:
            return ""
            
        channels = "\n📡 **CRITICAL: Team Communication Channels**\n\n"
        channels += "**ALWAYS use these exact window references for messaging:**\n\n"
        channels += "| Role | Window # | Send Message Command |\n"
        channels += "|------|----------|---------------------|\n"
        
        session_name = None
        for idx, (window_name, role_key) in enumerate(roles_deployed):
            # Highlight current role
            is_current = role_key == current_role
            prefix = "→ " if is_current else "  "
            you_marker = " (YOU)" if is_current else ""
            
            # Get session name from first window for example commands
            if session_name is None:
                result = subprocess.run(['tmux', 'display-message', '-p', '#{session_name}'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    session_name = result.stdout.strip()
                else:
                    session_name = "session"
            
            # Create the table row
            channels += f"|{prefix}{window_name}{you_marker} | {idx} | `scm {session_name}:{idx} \"message\"` |\n"
        
        channels += "\n**Examples:**\n"
        
        # Add role-specific examples
        if current_role == 'developer':
            pm_idx = next((idx for idx, (name, role) in enumerate(roles_deployed) if role == 'project_manager'), None)
            if pm_idx is not None:
                channels += f"- Report to PM: `scm {session_name}:{pm_idx} \"Pushed feature branch, ready for review\"`\n"
        elif current_role == 'project_manager':
            channels += "\n🚨 **CRITICAL FOR PROJECT MANAGERS** 🚨\n"
            channels += "**DO NOT use MCP tmux commands!** They often fail to send the Enter key.\n"
            channels += "**ALWAYS use the `scm` command for ALL messaging:**\n\n"
            
            dev_idx = next((idx for idx, (name, role) in enumerate(roles_deployed) if role == 'developer'), None)
            test_idx = next((idx for idx, (name, role) in enumerate(roles_deployed) if role == 'tester'), None)
            
            if dev_idx is not None:
                channels += f"- Coordinate with Developer: `scm {session_name}:{dev_idx} \"Please resolve merge conflicts\"`\n"
            if test_idx is not None:
                channels += f"- Update Tester: `scm {session_name}:{test_idx} \"Developer pushed updates, please verify tests\"`\n"
            
            channels += "\n**Why this matters**: MCP's tmux execute-command often requires manual Enter key pressing. The `scm` command ensures your messages are delivered properly.\n"
        elif current_role == 'tester':
            pm_idx = next((idx for idx, (name, role) in enumerate(roles_deployed) if role == 'project_manager'), None)
            if pm_idx is not None:
                channels += f"- Report test results: `scm {session_name}:{pm_idx} \"All tests passing, coverage at 95%\"`\n"
        
        channels += "\n**⚠️ Common Mistakes to Avoid:**\n"
        channels += "- ❌ Using role names like `pm:0` - roles don't have fixed numbers!\n"
        channels += "- ❌ Using `developer:0` - the developer might be in window 2!\n"
        channels += "- ❌ Using MCP tmux execute-command - it often fails to send Enter key!\n"
        channels += "- ✅ Always use the window numbers from the table above\n"
        channels += "- ✅ Always use `scm` command for messaging (not MCP tools)\n"
        channels += "- ✅ Or use full session:window format\n\n"
        
        return channels
    
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
            # Use absolute path for orchestrator CLAUDE.md to avoid relative path issues
            orchestrator_claude_path = "/home/clauderun/Tmux-Orchestrator/CLAUDE.md"
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
            team_locations += "# Push your branch so others can access it (with automatic versioning)\n"
            team_locations += "git add -A && git commit -m \"feat: your changes\"\n"
            team_locations += "git tag v1.0.1  # Increment version appropriately\n"
            team_locations += "git push -u origin your-branch-name --tags\n"
            team_locations += "# OR use automatic commit-tag-push:\n"
            team_locations += f"python3 {self.tmux_orchestrator_path}/git_commit_manager.py \"feat: your feature\" -a\n"
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
        
        # UV Configuration instructions
        uv_instructions = """
🔧 **UV CONFIGURATION (CRITICAL)**:
- `UV_NO_WORKSPACE=1` is set in your environment
- This allows UV commands to work without workspace detection
- You can run UV commands normally: `uv run`, `uv pip install`, etc.
- UV cache is isolated to prevent target project pollution

⚠️ **GIT SAFETY RULES**:
- NEVER commit `.venv`, `__pycache__`, or UV cache directories
- Before commits: `git status --porcelain | grep -E '\\.venv|__pycache__|uv-cache'`
- If temp files detected: Add them to `.gitignore` or use `git add -p`
- ALWAYS review `git status` before committing
- Use selective staging (`git add -p`) instead of `git add .` or `git add -A`

📦 **ENHANCED GIT WORKFLOW WITH AUTO-VERSIONING**:
```bash
# Option 1: Traditional workflow
git add -p  # Or specific files
git commit -m "feat: implement new feature"
git tag v1.0.1 -m "Release v1.0.1"
git push -u origin branch-name --tags

# Option 2: Automated commit-tag-push (RECOMMENDED)
cd ./shared/main-project || cd {worktree_paths.get(role, '.')}
python3 {self.tmux_orchestrator_path}/git_commit_manager.py "feat: your feature" -a
# This automatically:
# - Stages all changes (-a flag)
# - Creates commit with co-author
# - Auto-increments version based on commit type
# - Creates annotated tag
# - Pushes both commits and tags

# Commit conventions for auto-versioning:
# "feat:" or "feature:" -> minor bump (1.0.0 -> 1.1.0)
# "fix:" or "bugfix:" -> patch bump (1.0.0 -> 1.0.1)
# "breaking change:" -> major bump (1.0.0 -> 2.0.0)
```

"""
        
        # Add shared directory instructions
        sandbox_instructions = ""
        if role != 'orchestrator' and worktree_paths and role in worktree_paths:
            # Check if sandbox mode is set to cd_free (fallback)
            sandbox_mode = None
            if hasattr(self, 'session_state_manager') and self.session_state_manager:
                state = self.session_state_manager.load_session_state(self.project_name)
                if state and role in state.agents:
                    sandbox_mode = getattr(state.agents[role], 'sandbox_mode', None)
            
            if sandbox_mode == 'cd_free':
                # Fallback: cd-free commands
                sandbox_instructions = f"""
⚠️ **IMPORTANT: Symlink setup failed. Use cd-free commands:**

**Git Operations** (without cd):
- git --work-tree={self.project_path} --git-dir={self.project_path / '.git'} log --oneline -n 10
- git --work-tree={self.project_path} --git-dir={self.project_path / '.git'} status

**File Access** (use absolute paths):
- cat {self.project_path}/README.md
- grep -r "pattern" {self.project_path}/src

Report any issues to the Orchestrator.
"""
            else:
                # Primary: symlink approach
                sandbox_instructions = f"""
📁 **IMPORTANT: Access sibling directories via the 'shared' folder:**

🔍 **FIRST: Verify Your Location (Run These Commands First)**:
```bash
pwd  # Should show: {worktree_paths[role]}
ls -la shared/  # Should show symlinks to main-project and other agents
ls -la shared/main-project/  # Should show main project contents
readlink shared/main-project  # Should show relative path to main project
```
**If ANY of these fail, immediately report to Orchestrator and switch to cd-free mode.**

🔒 **WHY USE SHARED SYMLINKS:**
Claude Code security prevents direct `cd` to parent directories. This is a safety feature, not a bug.
- ❌ `cd {self.project_path}` (blocked by security)
- ✅ `cd ./shared/main-project` (allowed via symlink)

📍 **WHEN TO USE WHICH DIRECTORY:**
✅ **Your worktree** (current location): Role-specific work, commits, your directories
✅ **Main project** (cd ./shared/main-project): Project commands, shared files, main git repo
✅ **Other agents** (cd ./shared/{{role}}): Read-only access to other agents' work

**Directory Structure**:
./shared/
├── main-project/     → Main project directory
├── developer/        → Developer's worktree (if present)
├── tester/          → Tester's worktree (if present)
└── [other agents]/  → Other agent worktrees

**Examples**:
- cd ./shared/main-project && git pull origin main
- cd ./shared/main-project && npm install
- cat ./shared/developer/src/feature.py
- git log --oneline -5 ./shared/tester/

**Git Remotes** (from main-project):
- cd ./shared/main-project
- git remote add developer ../../developer
- git remote add tester ../../tester

⚠️ **If Symlinks Fail:**
1. Diagnose: ls -la shared/ || echo "shared missing"
2. Switch to cd-free mode: Use absolute paths with Read/Bash tools
3. Report immediately: "SYMLINK FAILURE: switched to cd-free mode"

**Safety Notes**:
- Use depth-limiting: find ./shared -maxdepth 2 -name "*.py"
- Always verify location with `pwd` before major operations
"""
        
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
        
        # Get communication channels table
        communication_channels = self.create_communication_channels(role, roles_deployed)
        
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

{communication_channels}

Workflow Example:
```bash
# You start in project worktree - create project files here
pwd  # Should show: {worktree_paths.get(role, 'N/A')}
mkdir -p project_management/docs
echo "# Project Status" > project_management/status.md

# Switch to tool directory for orchestrator commands
cd {tool_path}
# Use window numbers from the communication table above!
./send-claude-message.sh session:window "What's your status?"
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

{self.create_uv_configuration_instructions()}

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
- **Context management is automatic**: The system handles context management automatically
- **Work continues**: Context is managed behind the scenes without interruption
- **No intervention needed**: Don't avoid or "save" low-context agents
- **Keep delegating**: Send tasks normally - they'll handle context themselves

When an agent mentions low context:
1. Acknowledge: "Thanks for the context update"
2. Continue normally: Assign tasks as planned
3. Context management happens automatically
4. If they seem confused, remind them to read their checkpoint (if they created one)

This means context exhaustion is NOT a crisis - it's a routine, self-managed event!

🔀 **Git Integration & Parent Branch Management**

**Branch Architecture**:
- Parent Branch: `{spec.git_workflow.parent_branch}` (where we started)
- Agent Branches:
  - Developer: `{spec.git_workflow.branch_name}`
  - PM: `pm-{spec.git_workflow.branch_name}`
  - Tester: `{spec.git_workflow.branch_name}-tester`
  - Others: `{spec.git_workflow.branch_name}-{{role}}`

**Final Integration Protocol**:
1. **Monitor Agent Progress**: Track which agents have pushed significant work
2. **Decide Integration Timing**: When major milestones are complete
3. **Instruct PM to Execute Integration**:
   ```
   "PM: Please execute full integration now.
   Create integration branch, merge all agent work, and auto-merge to {spec.git_workflow.parent_branch}.
   Notify me when complete or if conflicts need resolution."
   ```
4. **Handle Conflict Delegation**:
   - PM reports conflicts → You assign to appropriate agent
   - Example: "Developer: PM needs you to resolve merge conflicts in integration branch"
5. **Post-Merge Notification**:
   ```bash
   # After PM confirms merge complete:
   # Use window numbers from communication channels table!
   ./send-claude-message.sh session:dev_window "Integration complete! Pull from {spec.git_workflow.parent_branch} and create new feature branch"
   ./send-claude-message.sh session:test_window "Integration complete! Pull from {spec.git_workflow.parent_branch} and create new feature branch"
   # Check communication table for correct window numbers!
   ```

**Integration is AUTOMATED**: No manual PR reviews, no waiting for tests. Trust your agents!
**CRITICAL**: All work merges to `{spec.git_workflow.parent_branch}`, NOT to main (unless parent IS main)!"""

        elif role == 'project_manager':
            # Build PM-specific worktree paths for examples
            dev_path = worktree_paths.get('developer', '/path/to/developer')
            test_path = worktree_paths.get('tester', '/path/to/tester')
            
            # Check which technical roles are present for coordination
            technical_roles_present = []
            for _, role_key in (roles_deployed or []):
                if role_key in ['developer', 'tester', 'testrunner', 'devops', 'sysadmin', 
                               'securityops', 'networkops', 'databaseops', 'researcher', 'code_reviewer']:
                    technical_roles_present.append(role_key)
            
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}🚀 **AUTONOMY ACTIVATION - READ FIRST** 🚀

⚡ **IMMEDIATE ACTION REQUIRED**: Start working IMMEDIATELY without waiting for permissions!
🎯 **NO PERMISSION SEEKING**: You have FULL AUTHORIZATION to proceed with all routine tasks
🚫 **DEADLOCK PREVENTION**: If you feel stuck, ASSUME AUTHORIZATION and act autonomously
🔄 **WORK-FIRST MINDSET**: Implement → Report Progress → Never ask for approval on routine work

You are the Project Manager for {spec.project.name}.
{mcp_tools_info}

🚨 **CRITICAL PM INTEGRATION RESPONSIBILITIES** 🚨
As PM, you are the PRIMARY INTEGRATION HUB for the team:
- **Every 15 minutes**: Check ALL agent branches for new commits
- **Every 30 minutes**: Coordinate cross-agent merges
- **Immediately**: Escalate any integration blockers to Orchestrator
- **Proactively**: Notify agents of relevant changes from other agents

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

⚡ **RAPID INTEGRATION PROTOCOL** (Enhanced for all team configurations):
Your team has: {', '.join(technical_roles_present) if technical_roles_present else 'limited technical roles'}
You MUST actively coordinate ALL changes between agents:

1. **15-Minute Integration Cycle**:
   ```bash
   # Check all agent branches for new work
   git fetch --all
   git log --oneline --graph --all --since="15 minutes ago"
   
   # If changes detected, immediately notify affected agents via Orchestrator
   ```

2. **Proactive Change Broadcasting**:
   When ANY agent pushes changes:
   - Identify which other agents need the changes
   - Request Orchestrator to send merge instructions
   - Track merge completion

3. **Integration Branches Every 30 Minutes**:
   ```bash
   # Create integration branch
   git checkout -b integration/$(date +%Y%m%d-%H%M)
   # Merge all agent work in dependency order
   # Push to origin for all agents to pull
   ```

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

{communication_channels}

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

**🚨 MANDATORY HUB-AND-SPOKE REPORTING 🚨**:
- **ALL TASK COMPLETIONS MUST BE REPORTED TO ORCHESTRATOR**
- When you complete ANY significant task, immediately report:
  ```
  STATUS UPDATE: [Your Role]
  COMPLETED: [Specific tasks completed]
  READY FOR: [Next steps/review]
  ```
- Use ./report-completion.sh when available
- **NEVER** assume other agents know about your work
- **FAILURE TO REPORT = WORK DOESN'T EXIST**
- This is MANDATORY for project success

Maintain EXCEPTIONAL quality standards. No compromises.

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_uv_configuration_instructions()}

{self.create_context_management_instructions(role)}"""

        elif role == 'developer':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}🚀 **AUTONOMY ACTIVATION - START CODING NOW** 🚀

⚡ **BEGIN IMPLEMENTATION IMMEDIATELY**: Start coding within 2 minutes of reading this briefing!
🎯 **NO APPROVAL NEEDED**: You have FULL AUTHORIZATION to implement all features in the spec
🚫 **NEVER WAIT FOR PERMISSIONS**: Create branches, write code, commit every 30 minutes autonomously
🔄 **AUTONOMOUS DEVELOPMENT**: Code → Test → Commit → Push → Report Progress (NO approvals needed)

You are the Developer for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

Project Details:
- Path: {spec.project.path}
- Type: {spec.project.type}
- Technologies: {', '.join(spec.project.main_tech)}

{communication_channels}

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
- **ORCHESTRATOR for completion reporting** (MANDATORY)

**🚨 WHEN YOU COMPLETE IMPLEMENTATION 🚨**:
1. Commit and push all code
2. Report to Orchestrator: "Developer: Implementation COMPLETE for [features]"
3. Report to PM: "Code ready for review in [branch/location]"
4. **DO NOT** assume they will find your work - YOU MUST REPORT

**Remember**: Your code is in `{worktree_paths.get(role, 'your-worktree')}` - PM will review it there!

🚀 **Fast Lane Coordination Enabled**:
Your commits now trigger automatic notifications to downstream agents:
- Post-commit hooks are installed in your worktree
- Tester gets notified within 5 minutes of your commits (was 45 min)
- TestRunner receives updates automatically through Tester
- Your development cycle is now 9x faster (8 min vs 75 min)
- Continue normal git discipline - fast lane operates automatically
- PM maintains oversight with conflict escalation if needed

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_uv_configuration_instructions()}

{self.create_context_management_instructions(role)}"""

        elif role == 'tester':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}🚀 **AUTONOMY ACTIVATION - START TESTING NOW** 🚀

⚡ **BEGIN TEST CREATION IMMEDIATELY**: Start writing tests within 2 minutes of reading this briefing!
🎯 **NO APPROVAL NEEDED**: You have FULL AUTHORIZATION to write and execute all tests
🚫 **NEVER WAIT FOR PERMISSIONS**: Create test files, write test cases, run tests autonomously
🔄 **AUTONOMOUS TESTING**: Write Tests → Execute → Report Results → Fix Issues (NO approvals needed)

You are the Tester for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

{communication_channels}

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
- **ORCHESTRATOR for completion reporting** (MANDATORY)

**🚨 WHEN YOU COMPLETE TEST SUITE 🚨**:
1. Commit all test files
2. Report to Orchestrator: "Tester: Test suite COMPLETE with [X] tests"
3. Report to PM: "Tests ready for review, [X]% coverage achieved"
4. **MANDATORY**: Report completions or work doesn't count

🚀 **Fast Lane Coordination Enabled**:
You now receive Developer updates automatically:
- Auto-sync from Developer every 5 minutes (was 45 min manual coordination)
- Post-commit hooks installed to trigger TestRunner notifications
- Automatic merge handling with conflict escalation to PM
- Your test feedback reaches the team 9x faster
- Use `./scripts/fast_lane_sync.sh` for manual sync if needed
- Continue normal testing workflow - fast lane operates automatically

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_uv_configuration_instructions()}

{self.create_context_management_instructions(role)}"""

        elif role == 'testrunner':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the Test Runner for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

{communication_channels}

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

🚀 **Fast Lane Coordination Enabled**:
You now receive Tester updates automatically:
- Auto-sync from Tester every 3 minutes (was 30+ min manual coordination)
- Immediate test execution after Tester commits
- Event-driven test execution instead of polling
- Results reach Developer and PM 5-8x faster
- Use `./scripts/fast_lane_sync.sh` for manual sync if needed
- Focus on test execution - fast lane handles coordination automatically

{self.create_git_sync_instructions(role, spec, worktree_paths)}

{self.create_uv_configuration_instructions()}

{self.create_context_management_instructions(role)}"""

        elif role == 'logtracker':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the Log Tracker for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

{communication_channels}

**CRITICAL FIRST TASK**: Read the project's CLAUDE.md for logging/monitoring instructions
```bash
# Check for project-specific monitoring guidance
cat ./shared/main-project/CLAUDE.md 2>/dev/null | grep -i -E "(log|monitor|error|track|alert)" || echo "No CLAUDE.md in main project"
cat ./shared/main-project/.claude/CLAUDE.md 2>/dev/null | grep -i -E "(log|monitor|error|track|alert)" || echo "No .claude/CLAUDE.md"
# If shared directory doesn't exist, fall back to absolute paths
cat {self.project_path}/CLAUDE.md 2>/dev/null | grep -i -E "(log|monitor|error|track|alert)" || echo "No CLAUDE.md found"
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

{self.create_uv_configuration_instructions()}

{self.create_context_management_instructions(role)}"""

        elif role == 'devops':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the DevOps Engineer for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

{communication_channels}

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

{self.create_uv_configuration_instructions()}

{self.create_context_management_instructions(role)}"""

        elif role == 'code_reviewer':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the Code Reviewer for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

{communication_channels}

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
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the Technical Researcher for {spec.project.name}.
{mcp_tools_info}

{communication_channels}
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

{self.create_uv_configuration_instructions()}

{self.create_context_management_instructions(role)}"""

        elif role == 'documentation_writer':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the Documentation Writer for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
{chr(10).join(f'- {r}' for r in role_config.responsibilities)}

{communication_channels}

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

        elif role == 'sysadmin':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the System Administrator for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
- System setup and configuration
- User and permission management
- Package installation and updates
- Service management (systemd/init)
- System security hardening
- Resource monitoring and optimization
- Backup and recovery procedures

{communication_channels}

**System Operations Focus**:
- Server provisioning and configuration
- System user and group management
- File permissions and ownership
- System service configuration
- Package management (apt/yum)
- System monitoring and logging
- Disk and storage management

Git Worktree Information:
- Your worktree path: {worktree_paths.get(role, 'N/A')}
- {self.get_worktree_branch_info(worktree_paths.get(role, Path('.'))) if worktree_paths else 'Branch status unknown'}

Start by:
1. Reviewing deployment specifications
2. Checking system prerequisites
3. Setting up base system configuration
4. Coordinating with SecurityOps on hardening

{self.create_context_management_instructions(role)}"""

        elif role == 'securityops':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the Security Operations specialist for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
- System security hardening
- Firewall configuration
- Access control implementation
- SSL/TLS certificate management
- Security monitoring and auditing
- Compliance enforcement
- Incident response planning

{communication_channels}

**Security Focus**:
- AppArmor/SELinux policy implementation
- Firewall rules (iptables/ufw)
- SSH hardening and key management
- Intrusion detection (fail2ban)
- Security scanning and vulnerability assessment
- Secrets management
- Audit logging

Git Worktree Information:
- Your worktree path: {worktree_paths.get(role, 'N/A')}
- {self.get_worktree_branch_info(worktree_paths.get(role, Path('.'))) if worktree_paths else 'Branch status unknown'}

Start by:
1. Security assessment of current setup
2. Implementing baseline security policies
3. Configuring firewall rules
4. Setting up security monitoring

Coordinate with:
- SysAdmin for system access
- NetworkOps for network security
- MonitoringOps for security alerts

{self.create_context_management_instructions(role)}"""

        elif role == 'networkops':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the Network Operations specialist for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
- Network configuration and routing
- Load balancer setup
- Reverse proxy configuration (Nginx/HAProxy)
- DNS configuration
- Port management
- Network performance optimization
- CDN and edge configuration

{communication_channels}

**Network Operations Focus**:
- Network interface configuration
- Routing table management
- NAT and port forwarding
- Load balancing strategies
- SSL termination
- Network segmentation (VLANs)
- Traffic monitoring and analysis

Git Worktree Information:
- Your worktree path: {worktree_paths.get(role, 'N/A')}
- {self.get_worktree_branch_info(worktree_paths.get(role, Path('.'))) if worktree_paths else 'Branch status unknown'}

Start by:
1. Analyzing network requirements
2. Configuring network interfaces
3. Setting up reverse proxy/load balancer
4. Implementing network security policies

Coordinate with:
- SecurityOps for firewall rules
- SysAdmin for system network access
- MonitoringOps for network monitoring

{self.create_context_management_instructions(role)}"""

        elif role == 'monitoringops':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the Monitoring Operations specialist for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
- Monitoring stack setup (Prometheus/Grafana)
- Metrics collection and aggregation
- Alert rule configuration
- Dashboard creation
- Log aggregation (ELK/Loki)
- Performance monitoring
- Incident response automation

{communication_channels}

**Monitoring Focus**:
- Service health monitoring
- Resource utilization tracking
- Application performance metrics
- Log analysis and correlation
- Alert threshold tuning
- SLI/SLO implementation
- Runbook creation

Git Worktree Information:
- Your worktree path: {worktree_paths.get(role, 'N/A')}
- {self.get_worktree_branch_info(worktree_paths.get(role, Path('.'))) if worktree_paths else 'Branch status unknown'}

Start by:
1. Setting up monitoring infrastructure
2. Configuring metric collection
3. Creating essential dashboards
4. Implementing critical alerts

Coordinate with:
- All technical roles for metric requirements
- SecurityOps for security monitoring
- SysAdmin for system metrics

{self.create_context_management_instructions(role)}"""

        elif role == 'databaseops':
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are the Database Operations specialist for {spec.project.name}.
{mcp_tools_info}

Your responsibilities:
- Database server installation and configuration
- Performance optimization
- Replication and clustering setup
- Backup and recovery strategies
- Schema migration management
- Database security
- Monitoring and diagnostics

{communication_channels}

**Database Operations Focus**:
- Database engine selection and setup
- Query optimization
- Index management
- Replication configuration
- Backup automation
- Disaster recovery planning
- Database user management

Git Worktree Information:
- Your worktree path: {worktree_paths.get(role, 'N/A')}
- {self.get_worktree_branch_info(worktree_paths.get(role, Path('.'))) if worktree_paths else 'Branch status unknown'}

Start by:
1. Analyzing database requirements
2. Installing and configuring database servers
3. Setting up backup procedures
4. Implementing security policies

Coordinate with:
- Developer for schema requirements
- SysAdmin for system resources
- MonitoringOps for database monitoring

{self.create_context_management_instructions(role)}"""

        else:
            # Fallback for any undefined roles
            return f"""{mandatory_reading}{context_note}{team_locations}{sandbox_instructions}You are a team member for {spec.project.name}.

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

    def setup_fast_lane_coordination(self, project_name: str, roles_to_deploy: List[Tuple[str, str]]):
        """Setup fast lane coordination for the project using the setup script"""
        
        # Extended fast lane eligible roles - now includes more combinations
        fast_lane_roles = []
        technical_roles = []
        has_pm = False
        
        for window_name, role_key in roles_to_deploy:
            # Check for PM
            if role_key == 'project_manager':
                has_pm = True
            # Extended list of roles that benefit from fast coordination
            elif role_key in ['developer', 'tester', 'testrunner', 'devops', 'sysadmin', 
                             'securityops', 'networkops', 'databaseops', 'researcher', 'code_reviewer']:
                fast_lane_roles.append(role_key)
                technical_roles.append(role_key)
        
        # If we have a PM but no traditional fast-lane roles, enable PM-based coordination
        if has_pm and len(technical_roles) >= 1:
            console.print("[cyan]🎯 Enabling PM-Enhanced Coordination for rapid integration[/cyan]")
            # Continue with setup even without traditional fast-lane roles
        elif len(fast_lane_roles) < 2:
            console.print("[yellow]⚠️  Insufficient roles for fast lane (need 2+ technical roles or PM + 1 technical)[/yellow]")
            return
        
        # Run the fast lane setup script
        setup_script = self.tmux_orchestrator_path / 'scripts' / 'setup_fast_lane.sh'
        
        if not setup_script.exists():
            console.print("[yellow]⚠️  Fast lane setup script not found, skipping fast lane configuration[/yellow]")
            return
        
        try:
            console.print("[cyan]🚀 Setting up Fast Lane Coordination...[/cyan]")
            
            result = subprocess.run([
                str(setup_script), project_name
            ], cwd=str(self.tmux_orchestrator_path), capture_output=True, text=True)
            
            if result.returncode == 0:
                # Parse successful setup output to show which roles got fast lanes
                output_lines = result.stdout.strip().split('\n')
                success_lines = [line for line in output_lines if '✅' in line]
                
                console.print("[green]✓ Fast Lane Coordination enabled![/green]")
                for line in success_lines:
                    console.print(f"  {line}")
                
                # Show the benefits based on roles present
                console.print("\n[cyan]Fast Lane Benefits:[/cyan]")
                if 'developer' in fast_lane_roles and 'tester' in fast_lane_roles:
                    console.print("  • Developer → Tester sync: 5 minutes (was 45 min)")
                    console.print("  • Tester → TestRunner sync: 3 minutes (was 30 min)")
                elif has_pm:
                    console.print("  • PM-coordinated integration every 15 minutes")
                    console.print("  • All technical roles synchronized via PM hub")
                    console.print("  • Rapid change propagation across team")
                
                console.print("  • Event-driven triggers instead of polling")
                console.print("  • Automatic conflict escalation to PM")
                console.print("  • Full audit logging enabled")
                
            else:
                console.print(f"[yellow]⚠️  Fast lane setup completed with warnings:[/yellow]")
                if result.stderr:
                    console.print(f"  {result.stderr.strip()}")
                if result.stdout:
                    console.print(f"  {result.stdout.strip()}")
                    
        except Exception as e:
            console.print(f"[red]✗ Failed to setup fast lane coordination: {e}[/red]")
            console.print("[yellow]  Teams can still coordinate manually via PM[/yellow]")

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

**Post-Integration Sync** (CRITICAL):
When Orchestrator announces "Integration complete! All agents please pull from {spec.git_workflow.parent_branch}":
```bash
# ALL agents MUST do this immediately:
git fetch origin
git checkout {spec.git_workflow.parent_branch}
git pull origin {spec.git_workflow.parent_branch}

# Then recreate your agent branch from the updated parent
git checkout -b {spec.git_workflow.branch_name}-{{role}}-v2
```
This ensures everyone works from the same integrated codebase!
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
   
4. **Automated Final Integration to Parent Branch ({spec.git_workflow.parent_branch})**:
   ```bash
   # Step 1: Create integration branch from parent
   git checkout {spec.git_workflow.parent_branch}
   git pull origin {spec.git_workflow.parent_branch}
   git checkout -b integration/{spec.git_workflow.branch_name}
   
   # Step 2: Merge all agent branches in order
   git merge origin/{spec.git_workflow.branch_name}  # Developer (main implementation)
   
   # IF CONFLICTS: Delegate to Developer
   # "Developer: Merge conflict in integration branch. Please resolve conflicts between your branch and parent."
   
   git merge origin/{spec.git_workflow.branch_name}-tester  # Tests
   git merge origin/{spec.git_workflow.branch_name}-testrunner  # Test results
   git merge origin/pm-{spec.git_workflow.branch_name}  # PM docs/reviews
   
   # Step 3: Push integration branch
   git push -u origin integration/{spec.git_workflow.branch_name}
   
   # Step 4: Create and AUTO-MERGE PR (skip tests, we trust our agents)
   gh pr create --base {spec.git_workflow.parent_branch} \\
     --head integration/{spec.git_workflow.branch_name} \\
     --title "{spec.git_workflow.pr_title}" \\
     --body "Integrated work from all agents on {spec.git_workflow.branch_name}\\n\\nAuto-merging after integration."
   
   # Step 5: Auto-merge immediately (admin merge, skip checks)
   gh pr merge --admin --merge
   
   # Step 6: Notify all agents to sync
   # "Orchestrator: Integration complete! All agents please pull from {spec.git_workflow.parent_branch}"
   ```
   
   **Conflict Resolution Protocol**:
   - Developer: Resolves code/implementation conflicts
   - Tester: Resolves test file conflicts
   - PM: Resolves documentation conflicts
   - First merger: Helps resolve cross-agent conflicts
   
   **Post-Merge Sync**: ALL agents must pull the merged parent branch!
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

    def create_uv_configuration_instructions(self) -> str:
        """Create UV configuration instructions for agents working in worktrees"""
        
        return """
🔧 **UV CONFIGURATION (CRITICAL)**:
- `UV_NO_WORKSPACE=1` is set in your environment
- This allows UV commands to work without workspace detection
- You can run UV commands normally: `uv run`, `uv pip install`, etc.
- UV cache is isolated to prevent target project pollution

⚠️ **GIT SAFETY RULES**:
- NEVER commit `.venv`, `__pycache__`, or UV cache directories
- Before commits: `git status --porcelain | grep -E '\\.venv|__pycache__|uv-cache'`
- If temp files detected: Add them to `.gitignore` or use `git add -p`
- ALWAYS review `git status` before committing
- Use selective staging (`git add -p`) instead of `git add .` or `git add -A`

📦 **QUICK GIT COMMIT-TAG-PUSH**:
Use the automated tool for consistent versioning:
`python3 /home/clauderun/Tmux-Orchestrator/git_commit_manager.py "feat: your message" -a`
"""

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

**Checkpoint Creation (Optional)**:
1. **Create Checkpoint** at natural breaks:
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

2. **Context Management is Automatic**: Context is handled automatically by the system

3. **Recovery Context** (if needed):
   ```
   # Option A: If available
   /context-prime
   
   # Option B: Manual reload
   Read /home/clauderun/Tmux-Orchestrator/CLAUDE.md
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
- Context management happens automatically at natural break points
- Always checkpoint before starting new phases
- Context is managed automatically when needed

**Emergency Recovery**:
If confused, read in order:
1. CLAUDE.md (your role and git rules)
2. Your latest checkpoint/handoff document
3. Recent git commits
4. Ask orchestrator for clarification

Remember: Context management is automatic - focus on creating good checkpoints to track progress!"""

    def is_port_free(self, port: int = 3000) -> bool:
        """Check if TCP port is free (works on Linux/macOS)."""
        try:
            # Try lsof first (most reliable)
            result = subprocess.run(['lsof', '-i', f'TCP:{port}'], 
                                  capture_output=True, text=True, timeout=2)
            return not result.stdout.strip()  # Empty output means port is free
        except (FileNotFoundError, subprocess.TimeoutExpired):
            try:
                # Fallback to ss for Linux systems without lsof
                result = subprocess.run(['ss', '-tuln'], 
                                      capture_output=True, text=True, timeout=2)
                return f":{port}" not in result.stdout
            except (FileNotFoundError, subprocess.TimeoutExpired):
                try:
                    # Final fallback to netstat
                    result = subprocess.run(['netstat', '-an'], 
                                          capture_output=True, text=True, timeout=2)
                    return f":{port}" not in result.stdout
                except Exception:
                    # If all commands fail, assume port is free (optimistic)
                    return True

    def wait_for_port_free(self, port: int = 3000, max_wait: int = 60) -> bool:
        """Wait for a port to become free with timeout."""
        start_time = time.time()
        last_check_time = 0
        
        while time.time() - start_time < max_wait:
            if self.is_port_free(port):
                if time.time() - start_time > 2:  # Only print if we actually waited
                    console.print(f"[green]✓ OAuth port {port} is now free[/green]")
                return True
            
            # Print status every 5 seconds
            if time.time() - last_check_time > 5:
                console.print(f"[yellow]Waiting for OAuth port {port} to free up... ({int(time.time() - start_time)}s)[/yellow]")
                last_check_time = time.time()
            
            time.sleep(2)
        
        console.print(f"[red]Warning: OAuth port {port} did not become free after {max_wait}s[/red]")
        return False

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
        
        # Press 'y' to accept MCP servers
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            'y'
        ])
        
        time.sleep(0.5)
        
        # Press Enter to confirm
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
        
        # Initial wait for Claude to process the exit command
        time.sleep(2)
        
        # Send additional Enter in case there's a confirmation prompt
        subprocess.run([
            'tmux', 'send-keys', '-t', f'{session_name}:{window_idx}',
            'Enter'
        ])
        
        # Wait for OAuth server port to be released
        # Use adaptive polling instead of fixed wait times
        oauth_port = int(os.environ.get('CLAUDE_OAUTH_PORT', '3000'))
        if not self.wait_for_port_free(oauth_port, max_wait=30):
            console.print(f"[yellow]Warning: OAuth port {oauth_port} may still be in use[/yellow]")
            # Continue anyway - the port might be used by something else
        
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
        
        # NEW: Comprehensive pre-flight checks
        if not self.pre_flight_checks():
            console.print("[red]Pre-flight checks failed - aborting orchestration[/red]")
            sys.exit(1)
        
        # Ensure tmux server is running
        self.ensure_tmux_server()
        
        # Ensure queue daemon is running
        self.ensure_queue_daemon()
        
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
        # First, start the orchestration to get unique names
        try:
            self.unique_session_name, self.unique_registry_dir = self.concurrent_manager.start_orchestration(
                self.implementation_spec.project.name, timeout=30
            )
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[yellow]Another orchestration may be starting for this project.[/yellow]")
            console.print("[yellow]Use --list to see active orchestrations.[/yellow]")
            sys.exit(1)
            
        session_name = self.unique_session_name
        project_name = self.sanitize_project_name(self.implementation_spec.project.name)
        roles_to_deploy = self.get_roles_for_project_size(self.implementation_spec)
        
        existing_session = self.check_existing_session(session_name)
        existing_worktrees = self.check_existing_worktrees(project_name, roles_to_deploy)
        
        if existing_session or existing_worktrees:
            if self.force or (self.batch_mode and self.overwrite):
                # Force mode or batch mode with overwrite - automatically overwrite
                if self.batch_mode:
                    console.print("\n[yellow]⚠️  Batch mode with --overwrite: Overwriting existing orchestration[/yellow]")
                else:
                    console.print("\n[yellow]⚠️  Force mode: Overwriting existing orchestration[/yellow]")
                if existing_session:
                    console.print(f"[yellow]Killing existing session '{session_name}'...[/yellow]")
                    subprocess.run(['tmux', 'kill-session', '-t', session_name], capture_output=True)
            elif self.batch_mode:
                # Batch mode without overwrite - default to resume
                if self.daemon_mode:
                    console.print("\n[cyan]📋 Daemon mode: Detected existing orchestration[/cyan]")
                    console.print("[green]✓ Daemon mode: Auto-resuming existing session (unattended)[/green]")
                else:
                    console.print("\n[cyan]📋 Batch mode: Detected existing orchestration[/cyan]")
                
                if existing_session:
                    console.print(f"[cyan]• Tmux session '{session_name}' already exists[/cyan]")
                    
                if existing_worktrees:
                    console.print(f"[cyan]• Found existing worktrees for: {', '.join(existing_worktrees)}[/cyan]")
                
                if not self.daemon_mode:
                    console.print("[green]✓ Batch mode default: Resuming existing session[/green]")
                
                # Try to resume
                if existing_session:
                    session_state = self.detect_existing_orchestration(
                        self.implementation_spec.project.name
                    )
                    
                    if session_state:
                        # Use smart resume with enhanced validation in daemon mode
                        if self.daemon_mode:
                            # Validate and recover broken sessions before resuming
                            if not self.validate_and_recover_session(session_state):
                                console.print("[yellow]Daemon mode: Session recovery failed. Creating new session...[/yellow]")
                            elif self.resume_orchestration(session_state, resume_mode='full'):
                                sys.exit(0)
                            else:
                                console.print("[yellow]Daemon mode: Resume failed. Creating new session...[/yellow]")
                        else:
                            # Regular resume attempt
                            if self.resume_orchestration(session_state, resume_mode='full'):
                                sys.exit(0)
                            else:
                                console.print("[yellow]Resume failed. Creating new session...[/yellow]")
                    else:
                        # No state but session exists
                        if self.daemon_mode:
                            console.print(f"[yellow]Daemon mode: Session exists but no state found. Recreating...[/yellow]")
                            # In daemon mode, kill and recreate if state is missing
                            subprocess.run(['tmux', 'kill-session', '-t', session_name], capture_output=True)
                        else:
                            console.print(f"[green]Session '{session_name}' exists, continuing...[/green]")
                            sys.exit(0)
                else:
                    if self.daemon_mode:
                        console.print("[green]Daemon mode: No existing session found. Creating new session...[/green]")
                    else:
                        console.print("[yellow]No existing session to resume. Creating new session...[/yellow]")
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
                            # Try to load session state
                            session_state = self.detect_existing_orchestration(
                                self.implementation_spec.project.name
                            )
                            
                            if session_state:
                                # Use smart resume
                                if self.resume_orchestration(session_state, resume_mode='full'):
                                    sys.exit(0)
                                else:
                                    console.print("[yellow]Resume failed. Creating new session...[/yellow]")
                                    break
                            else:
                                # Fallback to simple attach
                                console.print(f"\n[yellow]Warning: No session state found. Simple attach only.[/yellow]")
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
        # Use the unique registry directory from concurrent manager
        registry_dir = self.unique_registry_dir
        if not registry_dir:
            registry_dir = self.tmux_orchestrator_path / 'registry' / 'projects' / self.sanitize_project_name(self.implementation_spec.project.name)
        registry_dir.mkdir(parents=True, exist_ok=True)
        
        spec_file = registry_dir / 'implementation_spec.json'
        spec_file.write_text(json.dumps(spec_dict, indent=2))
        
        console.print(f"\n[green]✓ Setup complete![/green]")
        console.print(f"Implementation spec saved to: {spec_file}")
        
        # Save session state for resume capability
        session_name = self.unique_session_name or self.sanitize_session_name(self.implementation_spec.project.name) + "-impl"
        roles_deployed = self.get_roles_for_project_size(self.implementation_spec)
        
        # Get current branch as parent branch
        try:
            result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                  cwd=self.project_path,
                                  capture_output=True, text=True)
            parent_branch = result.stdout.strip() if result.returncode == 0 else None
        except:
            parent_branch = None
            
        session_state = create_initial_session_state(
            session_name=session_name,
            project_path=str(self.project_path),
            project_name=self.implementation_spec.project.name,
            implementation_spec_path=str(spec_file),
            agents=[(name, idx, role) for idx, (name, role) in enumerate(roles_deployed)],
            worktree_paths=self.worktree_paths,
            project_size=self.implementation_spec.project_size.size,
            parent_branch=parent_branch,
            spec_path=str(self.spec_path),
            worktree_base_path=getattr(self, 'custom_worktree_base', None)
        )
        
        self.session_state_manager.save_session_state(session_state)
        console.print(f"[green]✓ Session state saved for resume capability[/green]")
        
        # Start completion monitoring in background
        console.print(f"[cyan]Starting project completion monitoring...[/cyan]")
        self.completion_manager.monitor(
            session_name=session_name,
            project_name=self.implementation_spec.project.name,
            spec=self.implementation_spec,
            worktree_paths=self.worktree_paths,
            spec_path=str(self.spec_path),
            batch_mode=False  # Will be True when called from batch processing
        )
        console.print(f"[green]✓ Completion monitoring active (checks every 5 minutes)[/green]")
        
        # Email notification will be sent by CompletionManager when the project work is actually completed


@click.command()
@click.option('--project', '-p', type=str, default=None,
              help='Path to the GitHub project (use "auto" for automatic detection)')
@click.option('--spec', '-s', type=str, multiple=True,
              help='Path to specification file(s). Multiple specs will be queued for batch processing')
@click.option('--batch', is_flag=True, default=False, 
              help='Force batch mode even for single spec')
@click.option('--size', type=click.Choice(['auto', 'small', 'medium', 'large']), 
              default='auto', help='Project size (auto-detect by default)')
@click.option('--team-type', type=click.Choice(['auto', 'code_project', 'system_deployment', 'data_pipeline', 'infrastructure_as_code']),
              default='auto', help='Force specific team type (auto-detect by default)')
@click.option('--roles', multiple=True, 
              help='Additional roles to include (e.g., --roles researcher --roles documentation_writer)')
@click.option('--force', '-f', is_flag=True,
              help='Force overwrite existing session/worktrees without prompting')
@click.option('--overwrite', is_flag=True,
              help='In batch mode, overwrite existing sessions instead of resuming (default: resume)')
@click.option('--plan', type=click.Choice(['auto', 'pro', 'max5', 'max20', 'console']), 
              default='auto', help='Claude subscription plan (affects team size limits)')
@click.option('--resume', '-r', is_flag=True,
              help='Resume an existing orchestration session')
@click.option('--status-only', is_flag=True,
              help='Check status of existing session without making changes')
@click.option('--rebrief-all', is_flag=True,
              help='When resuming, re-brief all agents with context')
@click.option('--list', '-l', 'list_orchestrations', is_flag=True,
              help='List all active orchestrations')
@click.option('--new-project', is_flag=True,
              help='Create new git repositories for each spec file as siblings to the spec location')
@click.option('--research', type=str, 
              help='Run research agent on failed projects (JSON data)')
@click.option('--restore', type=str,
              help='Restore and retry failed projects from batch_id')
@click.option('--continue', 'continue_batch', is_flag=True,
              help='Continue last incomplete batch with intelligent retries')
@click.option('--git-mode', type=click.Choice(['local', 'github']), default='local',
              help='Git workflow mode: local (worktree optimization) or github (legacy)')
@click.option('--project-id', type=int, default=None,
              help='Project ID for queue completion callback (used by scheduler)')
@click.option('--daemon', is_flag=True,
              help='Run in daemon mode: non-interactive with auto-defaults for all prompts')
@click.option('--enable-orchestrator-scheduling/--disable-orchestrator-scheduling', 
              default=True,
              help='Enable self-scheduling for orchestrator window 0 (default: enabled)')
@click.option('--global-mcp-init', is_flag=True, default=False,
              help='Enable global/system-level MCP initialization for all roles')
def main(project: Optional[str], spec: Tuple[str, ...], batch: bool, size: str, team_type: str, roles: tuple, force: bool, overwrite: bool, plan: str, 
         resume: bool, status_only: bool, rebrief_all: bool, list_orchestrations: bool, new_project: bool,
         research: Optional[str], restore: Optional[str], continue_batch: bool, git_mode: str, project_id: Optional[int], daemon: bool,
         enable_orchestrator_scheduling: bool, global_mcp_init: bool):
    """Automatically set up a Tmux Orchestrator environment from a specification.
    
    The script will analyze your specification and set up a complete tmux
    orchestration environment with AI agents based on project size:
    
    SIMPLIFIED ROLE DEPLOYMENT:
    - All projects: 5 agents (Orchestrator + Project Manager + Developer + Tester + TestRunner)
    - Consistent team structure regardless of project size
    - Optimized for reduced token consumption
    
    Multi-agent systems use ~15x more tokens than standard usage.
    Use --plan to specify your subscription for appropriate team sizing.
    
    You can manually specify project size with --size or add specific roles
    with --roles (e.g., --roles documentation_writer)
    """
    # Handle list option first
    if list_orchestrations:
        # Create a temporary manager to list orchestrations
        tmux_orchestrator_path = Path(__file__).parent
        manager = ConcurrentOrchestrationManager(tmux_orchestrator_path)
        orchestrations = manager.list_active_orchestrations()
        
        if orchestrations:
            console.print("\n[cyan]Active Orchestrations:[/cyan]")
            table = Table(show_header=True)
            table.add_column("Project", style="bright_blue")
            table.add_column("Session", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Created", style="magenta")
            table.add_column("Agents", style="cyan")
            
            for orch in orchestrations:
                status = "[green]ACTIVE[/green]" if orch.get('active') else "[red]INACTIVE[/red]"
                created = orch['created_at'].split('T')[0]  # Just date
                agents = str(orch.get('agents', 'N/A'))
                
                table.add_row(
                    orch['project_name'],
                    orch['session_name'],
                    status,
                    created,
                    agents
                )
                
            console.print(table)
            console.print("\n[cyan]To attach to a session:[/cyan] tmux attach -t <session-name>")
        else:
            console.print("[yellow]No active orchestrations found[/yellow]")
        
        return
    
    # Handle research agent mode
    if research:
        return run_research_agent(research)
    
    # Handle restore/continue operations
    if restore or continue_batch:
        return handle_batch_retry(restore, continue_batch)
    
    # AUTOMATIC BATCH MODE: Check for ongoing orchestrations and force batch mode
    if not resume and not batch and spec:
        tmux_orchestrator_path = Path(__file__).parent
        manager = ConcurrentOrchestrationManager(tmux_orchestrator_path)
        active_orchestrations = [orch for orch in manager.list_active_orchestrations() if orch.get('active')]
        
        if active_orchestrations:
            console.print(f"\n[yellow]⚠️  Detected {len(active_orchestrations)} active orchestration(s):[/yellow]")
            for orch in active_orchestrations:
                console.print(f"[yellow]  • {orch['project_name']} ({orch['session_name']})[/yellow]")
            
            console.print(f"\n[blue]🎯 Auto-enabling batch mode to prevent conflicts[/blue]")
            console.print(f"[blue]Your spec(s) will be queued for sequential processing[/blue]")
            batch = True  # Force batch mode
    
    # Handle new-project mode - create new projects for specs
    if new_project:
        if not spec:
            console.print("[red]Error: --new-project requires at least one --spec[/red]")
            return
        if project:
            console.print("[yellow]Warning: --project ignored when --new-project is used[/yellow]")
        
        # AUTOMATIC BATCH MODE: Check for ongoing orchestrations in new-project mode too
        if not batch:
            tmux_orchestrator_path = Path(__file__).parent
            manager = ConcurrentOrchestrationManager(tmux_orchestrator_path)
            active_orchestrations = [orch for orch in manager.list_active_orchestrations() if orch.get('active')]
            
            if active_orchestrations:
                console.print(f"\n[yellow]⚠️  Detected {len(active_orchestrations)} active orchestration(s) during new-project creation[/yellow]")
                console.print(f"[blue]🎯 Auto-enabling batch mode for new projects to prevent conflicts[/blue]")
                batch = True  # Force batch mode for new projects too
        
        # Expand spec patterns (globs, directories)
        try:
            spec_paths = expand_specs(list(spec))
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            return
        
        if not spec_paths:
            console.print("[red]Error: No valid .md specs found[/red]")
            return
        
        console.print(f"[blue]Creating new projects for {len(spec_paths)} spec(s)...[/blue]")
        
        created_projects = []
        failed_projects = []
        
        for idx, spec_path in enumerate(spec_paths, 1):
            try:
                console.print(f"[blue]Processing spec {idx}/{len(spec_paths)}: {spec_path}[/blue]")
                
                # Create new project for this spec
                new_project_path, new_spec_path = setup_new_project(spec_path, force)
                
                # Store for batch processing if multiple specs
                created_projects.append({
                    'project_path': new_project_path,
                    'spec_path': new_spec_path,
                    'original_spec': str(spec_path)
                })
                
                console.print(f"[green]✓ Created project: {new_project_path}[/green]")
                
            except Exception as e:
                console.print(f"[red]Error creating project for {spec_path}: {str(e)}[/red]")
                logger.error(f"New project creation failed: {e}", exc_info=True)
                failed_projects.append(str(spec_path))
                continue
        
        if not created_projects:
            console.print("[red]No projects were created successfully[/red]")
            return
        
        console.print(f"[green]Successfully created {len(created_projects)} project(s)[/green]")
        if failed_projects:
            console.print(f"[yellow]Failed to create {len(failed_projects)} project(s): {', '.join(failed_projects)}[/yellow]")
        
        # If multiple projects or batch mode, use scheduler for sequential processing
        # UNLESS called from daemon (project_id present - indicates we're already processing from queue)
        if (len(created_projects) > 1 or batch) and not project_id:
            from scheduler import TmuxOrchestratorScheduler
            scheduler = TmuxOrchestratorScheduler()
            
            console.print(f"[cyan]Enqueuing {len(created_projects)} projects for batch orchestration...[/cyan]")
            
            for project_info in created_projects:
                new_id = scheduler.enqueue_project(
                    project_info['spec_path'], 
                    project_info['project_path']
                )
                console.print(f"[green]✓ Enqueued: {project_info['project_path']} (ID: {new_id})[/green]")
            
            console.print("\n[yellow]Projects enqueued for batch processing.[/yellow]")
            console.print("[cyan]To start processing:[/cyan] uv run scheduler.py --queue-daemon")
            console.print("[cyan]To view queue status:[/cyan] uv run scheduler.py --queue-list")
            return
        elif project_id and len(created_projects) > 1:
            # Safeguard: Daemon calls should be single-project
            raise ValueError("Daemon-initiated orchestration supports single projects only (multiple specs detected)")
        
        # Log daemon detection for debugging
        if project_id:
            console.print(f"[cyan]Queue daemon call detected (project ID: {project_id}) - proceeding to full orchestration...[/cyan]")
        
        else:
            # Single project - process immediately
            project_info = created_projects[0]
            console.print(f"[blue]Starting immediate orchestration for {Path(project_info['project_path']).name}...[/blue]")
            
            # Override spec and project for immediate processing
            spec = (project_info['spec_path'],)
            project = project_info['project_path']
            
            # Continue with normal single-project orchestration below
    
    # Handle batch mode - enqueue multiple specs
    # UNLESS called from daemon (project_id present)
    if (len(spec) > 1 or batch) and not project_id:
        # Import scheduler
        from scheduler import TmuxOrchestratorScheduler
        import uuid
        
        scheduler = TmuxOrchestratorScheduler()
        
        if not spec:
            console.print("[red]Error: No spec files provided for batch mode[/red]")
            return
            
        # Generate batch ID for this batch
        batch_id = str(uuid.uuid4())
        console.print(f"[cyan]Batch mode: Enqueuing {len(spec)} project(s) with batch ID: {batch_id}[/cyan]")
        
        for spec_path in spec:
            # Validate spec exists
            if not Path(spec_path).exists():
                console.print(f"[red]Error: Spec file not found: {spec_path}[/red]")
                continue
                
            project_id = scheduler.enqueue_project(spec_path, project, batch_id)
            console.print(f"[green]✓ Enqueued: {spec_path} (ID: {project_id}, Batch: {batch_id})[/green]")
        
        console.print("\n[yellow]Projects enqueued for batch processing.[/yellow]")
        console.print("[cyan]To start processing:[/cyan] uv run scheduler.py --queue-daemon")
        console.print("[cyan]To view queue status:[/cyan] uv run scheduler.py --queue-list")
        return
    
    # Single spec mode - require at least one spec for non-resume operations
    if not resume and not spec:
        console.print("[red]Error: --spec is required unless using --resume[/red]")
        return
    
    # Handle resume operation
    if resume:
        # For resume, we need to detect the project from the path
        if not project:
            console.print("[red]Error: --project is required when using --resume[/red]")
            sys.exit(1)
        project_path = Path(project).resolve()
        project_name = project_path.name
        
        # Create orchestrator with dummy spec path for now
        orchestrator = AutoOrchestrator(project, spec[0] if spec else "dummy.md", batch_mode=batch, overwrite=overwrite, daemon=daemon)
        orchestrator.rebrief_all = rebrief_all
        orchestrator.team_type = team_type if team_type != 'auto' else None
        orchestrator.project_id = project_id  # Store for database update if from queue
        # Set new flags
        orchestrator.enable_orchestrator_scheduling = enable_orchestrator_scheduling
        orchestrator.global_mcp_init = global_mcp_init
        
        # Try to load session state - first by exact name
        session_state = orchestrator.session_state_manager.load_session_state(project_name)
        
        # If not found, try to find by matching project path
        if not session_state:
            # Search through all projects in registry
            registry_projects = orchestrator.tmux_orchestrator_path / 'registry' / 'projects'
            if registry_projects.exists():
                for proj_dir in registry_projects.iterdir():
                    if proj_dir.is_dir():
                        state_file = proj_dir / 'session_state.json'
                        if state_file.exists():
                            # Try to load and check if project path matches
                            try:
                                with open(state_file, 'r') as f:
                                    state_data = json.load(f)
                                if Path(state_data.get('project_path', '')).resolve() == project_path:
                                    session_state = orchestrator.session_state_manager.load_session_state(proj_dir.name)
                                    break
                            except:
                                continue
        
        if not session_state:
            console.print(f"[red]Error: No existing orchestration found for project path '{project_path}'[/red]")
            console.print("[yellow]Hint: Make sure you're in the same project directory used during setup[/yellow]")
            
            # Show available projects
            if registry_projects.exists():
                console.print("\n[cyan]Available orchestrated projects:[/cyan]")
                for proj_dir in registry_projects.iterdir():
                    if proj_dir.is_dir():
                        state_exists = (proj_dir / 'session_state.json').exists()
                        spec_exists = (proj_dir / 'implementation_spec.json').exists()
                        if state_exists:
                            console.print(f"  - {proj_dir.name} (with session state)")
                        elif spec_exists:
                            # Try to guess session name
                            likely_session = proj_dir.name[:20] + "-impl"
                            console.print(f"  - {proj_dir.name} (legacy - no session state)")
                            console.print(f"    Try: tmux attach -t {likely_session}")
                            
                if not any((proj_dir / 'session_state.json').exists() for proj_dir in registry_projects.iterdir() if proj_dir.is_dir()):
                    console.print("\n[yellow]Note: Existing projects were created before session state tracking was added.[/yellow]")
                    console.print("[yellow]You'll need to use simple tmux attach or recreate the orchestration.[/yellow]")
            sys.exit(1)
            
        # Determine resume mode
        resume_mode = 'status' if status_only else 'full'
        
        # Resume the orchestration
        if orchestrator.resume_orchestration(session_state, resume_mode):
            sys.exit(0)
        else:
            sys.exit(1)
    
    # Normal setup flow
    if not spec:
        console.print("[red]Error: --spec is required when not using --resume[/red]")
        sys.exit(1)
        
    orchestrator = AutoOrchestrator(project or 'auto', spec[0], batch_mode=batch, overwrite=overwrite, daemon=daemon)
    orchestrator.manual_size = size if size != 'auto' else None
    orchestrator.team_type = team_type if team_type != 'auto' else None
    orchestrator.additional_roles = list(roles) if roles else []
    orchestrator.force = force
    orchestrator.plan_type = plan if plan != 'auto' else 'max20'  # Default to max20
    # Set new flags
    orchestrator.enable_orchestrator_scheduling = enable_orchestrator_scheduling
    orchestrator.global_mcp_init = global_mcp_init
    orchestrator.project_id = project_id  # Store for database update if from queue
    
    # Set custom worktree path for new projects (from --new-project processing above)
    if new_project and project:
        project_name = Path(project).name
        custom_worktree_base = str(Path(project).parent / f"{project_name}_worktrees")
        orchestrator.custom_worktree_base = custom_worktree_base
        console.print(f"[blue]Using custom worktree location: {custom_worktree_base}[/blue]")
    orchestrator.run()


def setup_local_worktrees(project_path: Path, agents: List[str], git_mode: str = 'local') -> Dict[str, str]:
    """Create worktrees and local remotes for agents if in local mode"""
    if git_mode != 'local':
        return {}
    
    try:
        worktrees_dir = project_path / 'worktrees'
        worktrees_dir.mkdir(exist_ok=True)
        worktrees = {}
        
        console.print(f"[blue]🌳 Setting up local worktrees for {len(agents)} agents...[/blue]")
        
        # Create worktrees for each agent
        for agent in agents:
            wt_path = worktrees_dir / agent
            if not wt_path.exists():
                # Create worktree (from main or current branch)
                result = subprocess.run([
                    'git', 'worktree', 'add', str(wt_path), 'main'
                ], cwd=project_path, capture_output=True, text=True)
                
                if result.returncode != 0:
                    # Try with current branch if main doesn't exist
                    current_branch = subprocess.run([
                        'git', 'rev-parse', '--abbrev-ref', 'HEAD'
                    ], cwd=project_path, capture_output=True, text=True).stdout.strip()
                    
                    subprocess.run([
                        'git', 'worktree', 'add', str(wt_path), current_branch
                    ], cwd=project_path, check=True)
                
                console.print(f"[green]✓ Created worktree for {agent}[/green]")
            else:
                console.print(f"[yellow]⚠ Worktree exists for {agent}[/yellow]")
                
            worktrees[agent] = str(wt_path)
        
        # Add local remotes in each worktree
        for agent in agents:
            wt_path = Path(worktrees[agent])
            
            for other_agent in agents:
                if other_agent != agent:
                    other_path = Path(worktrees[other_agent])
                    remote_path = other_path / '.git'
                    
                    # Check if remote already exists
                    check_remote = subprocess.run([
                        'git', 'remote', 'get-url', other_agent
                    ], cwd=wt_path, capture_output=True)
                    
                    if check_remote.returncode != 0:
                        # Add remote
                        subprocess.run([
                            'git', 'remote', 'add', other_agent, str(remote_path)
                        ], cwd=wt_path, check=True)
            
            # Initial fetch of all remotes
            subprocess.run(['git', 'fetch', '--all'], cwd=wt_path, capture_output=True)
        
        console.print(f"[green]✅ Local worktree setup complete - {len(agents)} agents configured[/green]")
        return worktrees
        
    except Exception as e:
        console.print(f"[yellow]⚠ Local worktree setup failed, falling back to GitHub mode: {e}[/yellow]")
        return {}


def create_pm_coordination_scripts(project_path: Path, worktrees: Dict[str, str]):
    """Create PM coordination scripts for local git operations"""
    if not worktrees:
        return
        
    tools_dir = project_path / 'tools'
    tools_dir.mkdir(exist_ok=True)
    
    # Create pm_fetch_all.py script
    fetch_all_script = tools_dir / 'pm_fetch_all.py'
    fetch_all_content = f'''#!/usr/bin/env python3
"""PM coordination script - fetch all agent changes"""
import subprocess
import sys
from pathlib import Path

def main():
    pm_worktree = Path("{worktrees.get('project_manager', worktrees.get('pm', ''))}")
    if not pm_worktree.exists():
        print("PM worktree not found")
        return 1
    
    agents = {list(worktrees.keys())}
    success_count = 0
    
    for agent in agents:
        if agent in ['project_manager', 'pm']:
            continue
            
        try:
            result = subprocess.run(['git', 'fetch', agent], 
                                  cwd=pm_worktree, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✓ Fetched from {{agent}}")
                success_count += 1
            else:
                print(f"⚠ Failed to fetch from {{agent}}: {{result.stderr}}")
        except Exception as e:
            print(f"✗ Error fetching from {{agent}}: {{e}}")
    
    print(f"Fetched from {{success_count}}/{len(agents)-1} agents")
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''
    
    fetch_all_script.write_text(fetch_all_content)
    fetch_all_script.chmod(0o755)
    
    # Create pm_status.py script
    status_script = tools_dir / 'pm_status.py'
    status_content = f'''#!/usr/bin/env python3
"""PM coordination script - check git status across worktrees"""
import subprocess
from pathlib import Path

def main():
    worktrees = {worktrees}
    
    for agent, path in worktrees.items():
        wt_path = Path(path)
        if not wt_path.exists():
            continue
            
        print(f"\\n=== {{agent.upper()}} ===")
        
        # Get current branch
        try:
            branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                  cwd=wt_path, capture_output=True, text=True).stdout.strip()
            print(f"Branch: {{branch}}")
        except:
            print("Branch: unknown")
        
        # Get status
        try:
            status = subprocess.run(['git', 'status', '--porcelain'], 
                                  cwd=wt_path, capture_output=True, text=True).stdout
            if status:
                print("Modified files:")
                for line in status.strip().split('\\n'):
                    print(f"  {{line}}")
            else:
                print("Working tree clean")
        except:
            print("Status: unavailable")
        
        # Get recent commits
        try:
            commits = subprocess.run(['git', 'log', '--oneline', '-3'], 
                                   cwd=wt_path, capture_output=True, text=True).stdout
            if commits:
                print("Recent commits:")
                for line in commits.strip().split('\\n'):
                    print(f"  {{line}}")
        except:
            pass

if __name__ == "__main__":
    main()
'''
    
    status_script.write_text(status_content)
    status_script.chmod(0o755)
    
    console.print(f"[green]✅ Created PM coordination scripts in {tools_dir}[/green]")


def run_research_agent(research_data_json: str):
    """Run research agent to analyze failed projects and provide enhancement recommendations"""
    import json
    from pathlib import Path
    
    try:
        # Parse input data
        research_data = json.loads(research_data_json)
        failed_projects = research_data.get('failed_projects', [])
        session_id = research_data.get('session_id', 'unknown')
        
        console.print(f"[blue]🔬 Research Agent analyzing {len(failed_projects)} failed projects...[/blue]")
        
        # Collect failure data for analysis
        analysis_data = collect_failure_data(failed_projects)
        
        # Run pattern analysis
        patterns = analyze_failure_patterns(analysis_data)
        
        # Generate recommendations using Grok MCP
        recommendations = generate_recommendations_with_grok(patterns, analysis_data)
        
        # Create enhanced specs
        enhanced_projects = create_enhanced_specs(failed_projects, recommendations)
        
        # Output results as JSON for scheduler
        result = {
            'session_id': session_id,
            'enhanced_projects': enhanced_projects,
            'analysis_summary': {
                'patterns_found': len(patterns),
                'recommendations_generated': len(recommendations),
                'projects_enhanced': len(enhanced_projects)
            }
        }
        
        print(json.dumps(result))
        console.print(f"[green]✅ Research analysis complete - {len(enhanced_projects)} projects enhanced[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Research agent failed: {e}[/red]")
        # Return original data as fallback
        fallback_result = {
            'session_id': research_data.get('session_id', 'unknown'),
            'enhanced_projects': research_data.get('failed_projects', []),
            'error': str(e)
        }
        print(json.dumps(fallback_result))
        return 1


def collect_failure_data(failed_projects: List[Dict]) -> Dict:
    """Collect comprehensive failure data for analysis"""
    analysis_data = {
        'error_messages': [],
        'retry_counts': [],
        'spec_paths': [],
        'failure_reports': [],
        'common_patterns': []
    }
    
    for project in failed_projects:
        analysis_data['error_messages'].append(project.get('error_message', ''))
        analysis_data['retry_counts'].append(project.get('retry_count', 0))
        analysis_data['spec_paths'].append(project.get('spec_path', ''))
        
        # Try to load failure reports if available
        try:
            # Look for failure reports in project directories
            project_path = Path(project.get('project_path', ''))
            if project_path.exists():
                report_files = list(project_path.glob('failure_report_*.md'))
                for report_file in report_files[-1:]:  # Get most recent
                    analysis_data['failure_reports'].append(report_file.read_text())
        except Exception:
            pass  # Skip if can't read reports
    
    return analysis_data


def analyze_failure_patterns(analysis_data: Dict) -> List[Dict]:
    """Analyze failure data to identify patterns"""
    patterns = []
    
    # Analyze error messages for common patterns
    error_messages = [msg for msg in analysis_data['error_messages'] if msg]
    
    # Pattern 1: Timeout failures
    timeout_count = sum(1 for msg in error_messages if 'timeout' in msg.lower())
    if timeout_count > 0:
        patterns.append({
            'type': 'timeout',
            'count': timeout_count,
            'severity': 'high' if timeout_count > len(error_messages) * 0.5 else 'medium',
            'description': f'{timeout_count}/{len(error_messages)} projects failed due to timeouts'
        })
    
    # Pattern 2: Credit exhaustion  
    credit_count = sum(1 for msg in error_messages if 'credit' in msg.lower())
    if credit_count > 0:
        patterns.append({
            'type': 'credit_exhaustion',
            'count': credit_count, 
            'severity': 'medium',
            'description': f'{credit_count}/{len(error_messages)} projects failed due to credit issues'
        })
    
    # Pattern 3: High retry counts
    avg_retries = sum(analysis_data['retry_counts']) / len(analysis_data['retry_counts']) if analysis_data['retry_counts'] else 0
    if avg_retries > 1:
        patterns.append({
            'type': 'high_retry_rate',
            'count': len([r for r in analysis_data['retry_counts'] if r > 1]),
            'severity': 'high',
            'description': f'Average retry count: {avg_retries:.1f} - indicates systematic issues'
        })
    
    return patterns


def generate_recommendations_with_grok(patterns: List[Dict], analysis_data: Dict) -> List[Dict]:
    """Generate actionable recommendations using Grok MCP"""
    recommendations = []
    
    try:
        # Import MCP tools
        import sys
        sys.path.append(str(Path(__file__).parent))
        
        # Prepare context for Grok
        context = {
            'patterns': patterns,
            'total_failures': len(analysis_data['error_messages']),
            'error_samples': analysis_data['error_messages'][:5],  # First 5 errors
            'failure_reports': analysis_data['failure_reports'][:2]  # First 2 reports
        }
        
        # Use Grok MCP to analyze patterns and generate recommendations
        grok_prompt = f"""
        Analyze these project failure patterns and provide specific, actionable recommendations:
        
        Patterns Found:
        {json.dumps(patterns, indent=2)}
        
        Sample Error Messages:
        {chr(10).join(context['error_samples'])}
        
        Please provide:
        1. Root cause analysis for each pattern
        2. Specific code fixes or configuration changes  
        3. Agent instruction modifications
        4. Preventive measures for future runs
        
        Format as JSON with 'recommendations' array containing objects with:
        - pattern_type: matching pattern type
        - priority: high/medium/low
        - action_type: code_fix/agent_instruction/configuration/monitoring
        - description: what to do
        - implementation: specific code/instructions
        """
        
        # Call Grok MCP
        try:
            import subprocess
            result = subprocess.run([
                'claude', '--mcp', 'grok_ask', 
                '--question', grok_prompt,
                '--model', 'grok-4-0709'
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                response = result.stdout
            else:
                raise Exception(f"Grok MCP call failed: {result.stderr}")
        except Exception as grok_error:
            console.print(f"[yellow]Grok MCP unavailable, using basic recommendations: {grok_error}[/yellow]")
            return create_basic_recommendations(patterns)
        
        # Parse Grok response
        try:
            grok_data = json.loads(response)
            recommendations.extend(grok_data.get('recommendations', []))
        except json.JSONDecodeError:
            # Fallback: create basic recommendations from patterns
            recommendations = create_basic_recommendations(patterns)
            
    except Exception as e:
        console.print(f"[yellow]Warning: Grok analysis failed, using basic recommendations: {e}[/yellow]")
        recommendations = create_basic_recommendations(patterns)
    
    return recommendations


def create_basic_recommendations(patterns: List[Dict]) -> List[Dict]:
    """Create basic recommendations when Grok is unavailable"""
    recommendations = []
    
    for pattern in patterns:
        if pattern['type'] == 'timeout':
            recommendations.append({
                'pattern_type': 'timeout',
                'priority': 'high',
                'action_type': 'agent_instruction',
                'description': 'Add timeout handling and progress checkpoints',
                'implementation': '''
### Enhanced Instructions (Retry)
- **Timeout Prevention**: Commit progress every 30 minutes minimum
- **Progress Tracking**: Report status updates every 15 minutes  
- **Checkpoint Creation**: Save work before starting major tasks
- **Early Warning**: Alert if task exceeds 75% of expected time
'''
            })
        elif pattern['type'] == 'credit_exhaustion':
            recommendations.append({
                'pattern_type': 'credit_exhaustion', 
                'priority': 'medium',
                'action_type': 'monitoring',
                'description': 'Add credit monitoring and conservative usage',
                'implementation': '''
### Enhanced Instructions (Retry)
- **Credit Awareness**: Check credit levels before major operations
- **Conservative Mode**: Use simpler approaches when credits are low
- **Progress Optimization**: Focus on highest-impact tasks first
- **Team Coordination**: Share credit usage status between agents
'''
            })
        elif pattern['type'] == 'high_retry_rate':
            recommendations.append({
                'pattern_type': 'high_retry_rate',
                'priority': 'high', 
                'action_type': 'agent_instruction',
                'description': 'Add debugging and systematic error handling',
                'implementation': '''
### Enhanced Instructions (Retry)
- **Debug Mode**: Enable detailed logging for all operations
- **Error Analysis**: Investigate root causes before proceeding
- **Incremental Progress**: Break large tasks into smaller steps
- **Team Review**: Add project manager review before major changes
'''
            })
    
    return recommendations


def create_enhanced_specs(failed_projects: List[Dict], recommendations: List[Dict]) -> List[Dict]:
    """Create enhanced specification files with research insights"""
    enhanced_projects = []
    
    for project in failed_projects:
        try:
            spec_path = Path(project['spec_path'])
            if not spec_path.exists():
                enhanced_projects.append(project)  # Return unchanged if spec missing
                continue
                
            # Read original spec
            original_content = spec_path.read_text()
            
            # Generate enhanced spec content
            enhancement_header = "# Research Agent Analysis (Retry)\n\n"
            enhancement_header += "## Failure Patterns Detected\n\n"
            
            # Add relevant recommendations
            for rec in recommendations:
                if rec.get('priority') in ['high', 'medium']:
                    enhancement_header += f"### {rec.get('description', 'Recommendation')}\n\n"
                    enhancement_header += f"**Priority**: {rec.get('priority', 'medium').title()}\n\n"
                    implementation = rec.get('implementation', '')
                    if implementation:
                        enhancement_header += f"{implementation}\n\n"
            
            enhancement_header += "---\n\n# Original Specification\n\n"
            enhanced_content = enhancement_header + original_content
            
            # Create enhanced spec file
            enhanced_spec_path = spec_path.with_suffix('.enhanced.md')
            enhanced_spec_path.write_text(enhanced_content)
            
            # Update project with enhanced spec path
            enhanced_project = project.copy()
            enhanced_project['enhanced_spec_path'] = str(enhanced_spec_path)
            enhanced_projects.append(enhanced_project)
            
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to enhance {project.get('spec_path', 'unknown')}: {e}[/yellow]")
            enhanced_projects.append(project)  # Return unchanged on error
    
    return enhanced_projects


def handle_batch_retry(restore_batch_id: Optional[str], continue_last: bool):
    """Handle --restore and --continue operations"""
    try:
        from scheduler import TmuxOrchestratorScheduler
        
        scheduler = TmuxOrchestratorScheduler()
        
        if restore_batch_id:
            console.print(f"[blue]🔄 Restoring failed projects from batch {restore_batch_id}...[/blue]")
            scheduler._handle_batch_completion(restore_batch_id)
            console.print(f"[green]✅ Batch {restore_batch_id} retry initiated[/green]")
            
        elif continue_last:
            console.print("[blue]🔄 Continuing last incomplete batch...[/blue]")
            
            # Find last incomplete batch
            cursor = scheduler.conn.cursor()
            cursor.execute("""
                SELECT batch_id FROM project_queue 
                WHERE status IN ('queued', 'processing', 'failed') 
                ORDER BY enqueued_at DESC 
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                batch_id = row[0]
                console.print(f"[blue]Found incomplete batch: {batch_id}[/blue]")
                scheduler._handle_batch_completion(batch_id)
                console.print(f"[green]✅ Batch {batch_id} retry initiated[/green]")
            else:
                console.print("[yellow]No incomplete batches found[/yellow]")
                
    except Exception as e:
        console.print(f"[red]❌ Batch retry failed: {e}[/red]")
        return 1


if __name__ == '__main__':
    main()
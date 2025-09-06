"""
Module Loader for CLAUDE Knowledge Base

Handles loading of modularized CLAUDE.md files for agent briefings.
This replaces the monolithic CLAUDE.md with smaller, role-specific modules.
"""

from pathlib import Path
from typing import Dict, List, Optional
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class ModuleLoader:
    """
    Loads modular CLAUDE knowledge base files for agent briefings.
    
    This class manages the loading of role-specific and core modules
    from the modularized CLAUDE knowledge base, preventing token overflow
    issues with the original monolithic CLAUDE.md file.
    """
    
    def __init__(self, modules_path: Optional[Path] = None):
        """
        Initialize the module loader.
        
        Args:
            modules_path: Path to the claude_modules directory.
                         Defaults to docs/claude_modules relative to Tmux-Orchestrator.
        """
        if modules_path is None:
            # Default to docs/claude_modules relative to this file
            modules_path = Path(__file__).parent.parent.parent / 'docs' / 'claude_modules'
        
        self.modules_path = modules_path
        self._validate_modules_directory()
    
    def _validate_modules_directory(self):
        """Validate that the modules directory exists and contains expected structure."""
        if not self.modules_path.exists():
            logger.warning(f"Modules directory not found at {self.modules_path}")
            # Fall back to legacy CLAUDE.md location if modules don't exist
            legacy_path = self.modules_path.parent.parent / 'CLAUDE.md'
            if legacy_path.exists():
                logger.info("Falling back to legacy CLAUDE.md")
                self.legacy_mode = True
            else:
                logger.error("Neither modular nor legacy CLAUDE files found")
                raise FileNotFoundError(f"No CLAUDE knowledge base found")
        else:
            self.legacy_mode = False
            logger.info(f"Using modular CLAUDE files from {self.modules_path}")
    
    @lru_cache(maxsize=32)
    def _load_file(self, relative_path: str) -> str:
        """
        Load a single module file with caching.
        
        Args:
            relative_path: Path relative to modules directory (e.g., 'core/principles.md')
            
        Returns:
            File content as string, or empty string if file doesn't exist.
        """
        file_path = self.modules_path / relative_path
        if file_path.exists():
            try:
                content = file_path.read_text()
                logger.debug(f"Loaded module: {relative_path} ({len(content)} chars)")
                return content
            except Exception as e:
                logger.error(f"Error loading module {relative_path}: {e}")
                return ""
        else:
            logger.warning(f"Module not found: {relative_path}")
            return ""
    
    def _load_multiple(self, paths: List[str]) -> str:
        """
        Load multiple module files and concatenate them.
        
        Args:
            paths: List of relative paths to load
            
        Returns:
            Concatenated content with section separators.
        """
        contents = []
        for path in paths:
            content = self._load_file(path)
            if content:
                contents.append(content)
                contents.append("\n---\n")  # Section separator
        
        return '\n'.join(contents)
    
    def load_core_modules(self) -> str:
        """
        Load core modules that all agents need.
        
        Returns:
            Concatenated content of core modules.
        """
        core_files = [
            'core/principles.md',
            'core/communication.md',
            'core/completion.md'
        ]
        return self._load_multiple(core_files)
    
    def load_role_module(self, role: str) -> str:
        """
        Load the appropriate role-specific module.
        
        Args:
            role: The agent role (e.g., 'developer', 'orchestrator')
            
        Returns:
            Content of the role-specific module.
        """
        role_lower = role.lower().replace('-', '_')
        
        # Map roles to their module files
        core_roles = ['orchestrator', 'project_manager', 'developer', 'tester', 'testrunner']
        system_ops_roles = ['sysadmin', 'securityops', 'networkops', 'monitoringops', 'databaseops']
        
        if role_lower in core_roles:
            return self._load_file('roles/core_roles.md')
        elif role_lower in system_ops_roles:
            return self._load_file('roles/system_ops_roles.md')
        else:
            # Default to optional roles for unknown roles
            return self._load_file('roles/optional_roles.md')
    
    def load_workflow_modules(self, role: str) -> str:
        """
        Load workflow modules relevant to the role.
        
        Args:
            role: The agent role
            
        Returns:
            Concatenated workflow module content.
        """
        # All roles need git workflow
        workflow_files = ['workflows/git_workflow.md']
        
        # Orchestrator and PM need worktree setup
        if role.lower() in ['orchestrator', 'project_manager']:
            workflow_files.append('workflows/worktree_setup.md')
        
        return self._load_multiple(workflow_files)
    
    def load_configuration_modules(self, role: str) -> str:
        """
        Load configuration modules if relevant to the role.
        
        Args:
            role: The agent role
            
        Returns:
            Configuration module content.
        """
        config_files = []
        
        # Orchestrator and PM need team configuration
        if role.lower() in ['orchestrator', 'project_manager']:
            config_files.extend([
                'configuration/team_detection.md',
                'configuration/scaling.md'
            ])
        
        return self._load_multiple(config_files) if config_files else ""
    
    def load_for_role(self, role: str) -> Dict[str, str]:
        """
        Load all relevant modules for a specific role.
        
        Args:
            role: The agent role (e.g., 'developer', 'orchestrator')
            
        Returns:
            Dictionary with module categories as keys and content as values.
        """
        if self.legacy_mode:
            # In legacy mode, return a message about reading CLAUDE.md
            return {
                'legacy_notice': "Note: Using legacy CLAUDE.md. Please read CLAUDE.md for full instructions.",
                'core': "",
                'role': "",
                'workflows': "",
                'configuration': ""
            }
        
        modules = {
            'core': self.load_core_modules(),
            'role': self.load_role_module(role),
            'workflows': self.load_workflow_modules(role),
            'configuration': self.load_configuration_modules(role)
        }
        
        # Log total content size
        total_chars = sum(len(content) for content in modules.values())
        estimated_tokens = total_chars // 4  # Rough estimate
        logger.info(f"Loaded {total_chars} chars (~{estimated_tokens} tokens) for role: {role}")
        
        return modules
    
    def get_index(self) -> str:
        """
        Get the module index for reference.
        
        Returns:
            Content of the index.md file.
        """
        return self._load_file('index.md')
    
    def get_module_reference(self, role: str) -> str:
        """
        Get a reference list of modules for a role to include in briefings.
        
        Args:
            role: The agent role
            
        Returns:
            Formatted string with module references.
        """
        if self.legacy_mode:
            return "📚 Reference: CLAUDE.md (monolithic knowledge base)"
        
        role_lower = role.lower().replace('-', '_')
        
        references = ["📚 **Module References**:"]
        references.append("- Core: docs/claude_modules/core/")
        
        # Add role-specific reference
        if role_lower in ['orchestrator', 'project_manager', 'developer', 'tester', 'testrunner']:
            references.append("- Role: docs/claude_modules/roles/core_roles.md")
        elif role_lower in ['sysadmin', 'securityops', 'networkops', 'monitoringops', 'databaseops']:
            references.append("- Role: docs/claude_modules/roles/system_ops_roles.md")
        else:
            references.append("- Role: docs/claude_modules/roles/optional_roles.md")
        
        references.append("- Workflows: docs/claude_modules/workflows/")
        
        if role_lower in ['orchestrator', 'project_manager']:
            references.append("- Configuration: docs/claude_modules/configuration/")
        
        return '\n'.join(references)
    
    def format_role_context(self, modules: Dict[str, str]) -> str:
        """
        Format loaded modules into a complete context for an agent.
        
        Args:
            modules: Dictionary of loaded module content
            
        Returns:
            Formatted string ready for agent briefing.
        """
        if 'legacy_notice' in modules:
            return modules['legacy_notice']
        
        sections = []
        
        if modules.get('core'):
            sections.append("=== CORE PRINCIPLES ===\n" + modules['core'])
        
        if modules.get('role'):
            sections.append("=== ROLE RESPONSIBILITIES ===\n" + modules['role'])
        
        if modules.get('workflows'):
            sections.append("=== WORKFLOWS ===\n" + modules['workflows'])
        
        if modules.get('configuration'):
            sections.append("=== CONFIGURATION ===\n" + modules['configuration'])
        
        return '\n\n'.join(sections)
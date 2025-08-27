# Claude Worktree Directory Access Solution

## Problem Summary

Claude instances started via `auto_orchestrate.py` are restricted to their worktree directories and cannot `cd` into sibling directories (like the main project). This is due to Claude Code's security sandbox that only allows accessing child directories of the starting location.

Example error:
```
Error: cd to '/path/to/main-project' was blocked. For security, Claude Code may only change 
directories to child directories of the allowed working directories for this session
```

## Solution: Shared Directory Approach with Symlinks and Cd-Free Fallback

### Primary Solution: Shared Directory with Multiple Symlinks

Create a `shared` directory inside each agent's worktree containing symlinks to the main project and other agent worktrees. This provides safe, controlled access to all sibling directories while avoiding infinite loop risks.

### Implementation

#### 1. Extend PathManager

Add to `PathManager` class in `auto_orchestrate.py`:

```python
import logging
import shutil
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class PathManager:
    # ... existing code ...

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
                    shutil.copy(src, dest)
                    logger.info(f"Copied {file_name} to {worktree_path}")
                except (OSError, PermissionError) as e:
                    logger.error(f"Failed to copy {file_name} for {role}: {e}")
                    success = False
        
        return success
    
    def _create_relative_symlink(self, link_path: Path, target_path: Path, base_path: Path) -> bool:
        """Create a relative symlink from link_path to target_path, relative to base_path."""
        if link_path.exists():
            return True  # Already exists
        
        try:
            relative_target = os.path.relpath(str(target_path), str(link_path.parent))
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
        
        for worktree_dir in self.worktree_root.glob('*'):
            role = worktree_dir.name.replace('-', '_')
            self.setup_sandbox_for_role(role)
        
        (self.metadata_root / 'sandbox_migrated.flag').touch()
        logger.info("Sandbox migration complete")
```

#### 2. Integrate into AutoOrchestrator

Add worktree setup to `AutoOrchestrator`:

```python
class AutoOrchestrator:
    # ... existing code ...

    def setup_worktrees(self, roles: List[str]):
        """Setup worktrees with sandbox symlinks for all roles."""
        # Get list of role names for cross-linking
        role_names = [r for r in roles if r != 'orchestrator']  # Exclude orchestrator
        
        for role in roles:
            if not self.path_manager.setup_sandbox_for_role(role, active_roles=role_names):
                console.print(f"[yellow]Warning: Sandbox setup failed for {role}. Using cd-free fallback.[/yellow]")
                # Store fallback state in session
                if hasattr(self, 'session_state_manager'):
                    agent_state = self.session_state_manager.get_agent_state(role)
                    if agent_state:
                        agent_state['sandbox_mode'] = 'cd_free'

    def generate_briefing(self, role: str) -> str:
        """Generate role-specific briefing with sandbox instructions."""
        base_briefing = f"You are the {role} for this project.\n\n"
        
        # Check if fallback mode is needed
        agent_state = self.session_state_manager.get_agent_state(role) if hasattr(self, 'session_state_manager') else None
        
        if agent_state and agent_state.get('sandbox_mode') == 'cd_free':
            # Fallback: cd-free commands
            instructions = f"""
⚠️ IMPORTANT: Symlink setup failed. Use cd-free commands:

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
            instructions = """
📁 IMPORTANT: Access sibling directories via the 'shared' folder:

**Directory Structure**:
./shared/
├── main-project/     → Main project directory
├── developer/        → Developer's worktree
├── tester/          → Tester's worktree
└── [other agents]/  → Other agent worktrees

**Accessing Main Project**:
- Use: cd ./shared/main-project
- NOT: cd /absolute/path/to/project

**Accessing Other Agents**:
- cd ./shared/developer && git log  # View developer's work
- cd ./shared/tester && ls tests/   # Check tester's files

**Examples**:
- cd ./shared/main-project && git pull origin main
- cd ./shared/main-project && git status
- cat ./shared/developer/src/feature.py
- diff ./shared/tester/tests/test_feature.py tests/test_feature.py

**Git Remotes** (from main-project):
- cd ./shared/main-project
- git remote add developer ../../developer
- git remote add tester ../../tester

**Safety Note**: Use non-recursive commands to avoid issues:
- find ./shared -maxdepth 2 -name "*.py"  # Limit depth
- ls ./shared/*/  # List contents safely

If 'shared' directory is missing or incomplete, report to Orchestrator.
"""
        
        return base_briefing + instructions
```

#### 3. Update Agent Briefings

Modify the briefing generation in `create_role_briefing` method:

```python
def create_role_briefing(self, role: str, spec: ImplementationSpec, role_config: RoleConfig, 
                        context_primed: bool = True, roles_deployed: List[Tuple[str, str]] = None,
                        worktree_paths: Dict[str, Path] = None, mcp_categories: Dict[str, List[str]] = None) -> str:
    # ... existing code ...
    
    # Add sandbox instructions after mandatory reading
    sandbox_instructions = """
🔗 **Directory Access Instructions**:
All sibling directories are accessible via: ./shared/
This folder contains symlinks that work around Claude's security restrictions.

**Available Directories**:
- ./shared/main-project    → Main project
- ./shared/developer       → Developer's worktree
- ./shared/tester         → Tester's worktree
- ./shared/[agent]        → Other agent worktrees

**Example Commands**:
- cd ./shared/main-project && git pull origin main
- cd ./shared/developer && git log --oneline -5
- cat ./shared/main-project/src/main.py
- diff ./shared/tester/tests/test_api.py ./tests/test_api.py

**Cross-Agent Collaboration**:
- View another agent's changes: cd ./shared/developer && git diff
- Copy files from another agent: cp ./shared/tester/tests/* ./tests/
- Check all agent statuses: for d in ./shared/*/; do echo $d && cd $d && git status; done
"""
    
    # Insert after mandatory_reading but before role-specific content
    return f"{mandatory_reading}{sandbox_instructions}{context_note}{team_locations}..."
```

### Windows Compatibility

For Windows systems, add platform detection:

```python
import platform

def setup_sandbox_for_role(self, role: str) -> bool:
    # ... existing code ...
    
    if platform.system() == 'Windows':
        try:
            # Use Windows mklink for directory symlinks
            subprocess.run(['cmd', '/c', 'mklink', '/D', str(main_symlink), relative_target], 
                         check=True, capture_output=True)
            logger.info(f"Created Windows symlink for {role}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Windows symlink failed: {e}. Admin privileges may be required.")
            # Try directory junction as fallback
            try:
                subprocess.run(['cmd', '/c', 'mklink', '/J', str(main_symlink), str(self.project_path)], 
                             check=True, capture_output=True)
                logger.info(f"Created Windows junction for {role}")
            except subprocess.CalledProcessError:
                return False
```

### Migration for Existing Projects

Add migration support for `--resume` mode:

```python
def resume(self):
    """Resume an existing orchestration with migration support."""
    # Migrate existing worktrees to have symlinks
    self.path_manager.migrate_sandboxes()
    
    # Existing resume logic...
    self.reconcile_session_state()
```

### Fallback Mechanism

The implementation includes automatic fallback to cd-free commands if symlink creation fails:

1. **Detection**: `setup_sandbox_for_role` returns `False` on failure
2. **State Storage**: Sets `sandbox_mode = 'cd_free'` in agent state
3. **Briefing Adaptation**: `generate_briefing` provides cd-free instructions
4. **Examples**:
   ```bash
   # Instead of: cd /path/to/project && git status
   git --work-tree=/path/to/project --git-dir=/path/to/project/.git status
   
   # Instead of: cd /path/to/project && cat README.md
   cat /path/to/project/README.md
   ```

### Testing Checklist

1. **Fresh Project**: Run `auto_orchestrate.py` and verify symlinks are created
2. **Resume Mode**: Test `--resume` on existing projects to verify migration
3. **Windows**: Test on Windows with/without admin privileges
4. **Fallback**: Simulate permission errors to test cd-free fallback
5. **Agent Commands**: Verify agents can use `cd ./main-project` successfully

### Additional Recommendations

1. **Add CLI Flag**: `--no-symlinks` to force cd-free mode
2. **Logging**: Monitor `PathManager` logs for symlink failures
3. **Documentation**: Update CLAUDE.md with new access patterns
4. **Monitoring**: Add symlink verification to health checks

### Enhanced Solution Benefits

1. **Safer than Parent Symlink**: The `shared` directory approach avoids infinite loop risks that would occur with a direct parent symlink
2. **Better Collaboration**: Agents can directly inspect each other's work without going through git remotes
3. **Organized Structure**: All external access is clearly contained in the `shared` folder
4. **Selective Access**: Only necessary directories are exposed (no access to unrelated parent contents)
5. **Easy Discovery**: Agents can `ls ./shared/` to see available resources

### Potential Issues and Mitigations

1. **Recursive Commands**: Agents should use depth-limiting flags (e.g., `find -maxdepth 2`) to avoid traversing symlinks excessively
2. **Broken Links**: If an agent's worktree is removed, symlinks become invalid - the system logs warnings but continues
3. **Windows Compatibility**: Same handling as before with mklink/junctions
4. **Setup Overhead**: Creating multiple symlinks adds ~1-2 seconds per agent during setup

### Summary

This enhanced solution using a `shared` directory with targeted symlinks provides agents with safe, controlled access to all necessary sibling directories. It avoids the infinite loop risks of a parent symlink while enabling rich cross-agent collaboration. The approach maintains the existing worktree structure, respects Claude's security model, and includes automatic fallback to cd-free commands for edge cases.
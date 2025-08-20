#!/usr/bin/env python3
"""
Enhanced Git Conflict Resolver for Tmux Orchestrator
Implements autonomous AI-driven merge conflict resolution with safety measures
"""

import logging
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from abc import ABC, abstractmethod
from git import Repo, GitCommandError
from session_state import SessionState, AgentState

logger = logging.getLogger(__name__)

class ConflictClassifier:
    """Classifies conflicts as simple/complex based on heuristics"""
    
    @staticmethod
    def classify_conflict(repo: Repo, conflicting_files: List[str]) -> Dict[str, Any]:
        """Analyze conflicts and classify complexity"""
        classification = {
            'type': 'simple',  # simple/complex
            'confidence': 0.0,
            'files': {},
            'total_diff_lines': 0,
            'has_binary': False,
            'semantic_complexity': 'low'  # low/medium/high
        }
        
        for file_path in conflicting_files:
            try:
                # Get conflict markers
                with open(repo.working_dir / file_path, 'r') as f:
                    content = f.read()
                    conflict_blocks = content.count('<<<<<<<')
                    
                # Get diff size
                diff_output = repo.git.diff('--cached', '--', file_path)
                diff_lines = len(diff_output.split('\n'))
                
                # Classify individual file
                file_class = {
                    'conflict_blocks': conflict_blocks,
                    'diff_lines': diff_lines,
                    'is_binary': Path(file_path).suffix in ['.jpg', '.png', '.pdf', '.zip'],
                    'is_config': Path(file_path).suffix in ['.json', '.yaml', '.toml', '.ini'],
                    'is_code': Path(file_path).suffix in ['.py', '.js', '.ts', '.java', '.go']
                }
                
                classification['files'][file_path] = file_class
                classification['total_diff_lines'] += diff_lines
                
                if file_class['is_binary']:
                    classification['has_binary'] = True
                    classification['type'] = 'complex'
                    
            except Exception as e:
                logger.error(f"Error classifying {file_path}: {e}")
                classification['type'] = 'complex'
        
        # Overall classification
        if classification['has_binary']:
            classification['confidence'] = 0.0
        elif classification['total_diff_lines'] > 100:
            classification['type'] = 'complex'
            classification['confidence'] = 0.3
        elif any(f['conflict_blocks'] > 3 for f in classification['files'].values()):
            classification['type'] = 'complex'
            classification['confidence'] = 0.4
        else:
            # Simple conflicts - config files or small code changes
            classification['confidence'] = 0.8
            
        return classification


class ConflictResolver(ABC):
    """Abstract base class for conflict resolution strategies"""
    
    @abstractmethod
    def resolve(self, repo: Repo, conflict_info: Dict[str, Any], agent: AgentState) -> Tuple[bool, Dict[str, str]]:
        """Resolve conflicts and return (success, resolved_files_content)"""
        pass


class AIConflictResolver(ConflictResolver):
    """AI-powered conflict resolution using LLM reasoning"""
    
    def __init__(self, llm_endpoint: Optional[str] = None):
        self.llm_endpoint = llm_endpoint  # Future: actual LLM API
        
    def resolve(self, repo: Repo, conflict_info: Dict[str, Any], agent: AgentState) -> Tuple[bool, Dict[str, str]]:
        """Use AI to resolve conflicts"""
        resolved_files = {}
        
        for file_path, file_info in conflict_info['files'].items():
            try:
                # Read conflicted file
                with open(repo.working_dir / file_path, 'r') as f:
                    conflicted_content = f.read()
                
                # Extract conflict sections
                ours, theirs = self._extract_conflict_sections(conflicted_content)
                
                # Generate AI resolution
                prompt = f"""You are resolving a git merge conflict in {file_path} for the {agent.role} agent.
                
File type: {Path(file_path).suffix}
Conflict blocks: {file_info['conflict_blocks']}

OURS (current branch):
{ours}

THEIRS (merging branch):
{theirs}

Please provide a merged version that:
1. Preserves the intent of both changes
2. Follows the project's coding standards
3. Avoids introducing bugs
4. Maintains semantic correctness

Merged version:"""
                
                # Simulate AI response (replace with actual LLM call)
                resolved_content = self._simulate_llm_resolution(ours, theirs, file_path)
                resolved_files[file_path] = resolved_content
                
            except Exception as e:
                logger.error(f"Failed to AI-resolve {file_path}: {e}")
                return False, {}
                
        return True, resolved_files
    
    def _extract_conflict_sections(self, content: str) -> Tuple[str, str]:
        """Extract ours/theirs from conflict markers"""
        lines = content.split('\n')
        ours_lines = []
        theirs_lines = []
        
        in_ours = False
        in_theirs = False
        
        for line in lines:
            if line.startswith('<<<<<<<'):
                in_ours = True
                continue
            elif line.startswith('======='):
                in_ours = False
                in_theirs = True
                continue
            elif line.startswith('>>>>>>>'):
                in_theirs = False
                continue
                
            if in_ours:
                ours_lines.append(line)
            elif in_theirs:
                theirs_lines.append(line)
                
        return '\n'.join(ours_lines), '\n'.join(theirs_lines)
    
    def _simulate_llm_resolution(self, ours: str, theirs: str, file_path: str) -> str:
        """Simulate LLM resolution (replace with actual API call)"""
        # For now, simple heuristic: if config file, merge both
        if Path(file_path).suffix in ['.json', '.yaml']:
            # Attempt to merge JSON/YAML intelligently
            return f"{ours}\n# Merged from theirs:\n{theirs}"
        else:
            # For code, prefer theirs (incoming changes) with our additions
            return f"{theirs}\n# Preserved from ours:\n{ours}"


class GitConflictResolver:
    """Main conflict resolution coordinator"""
    
    def __init__(self, repo_path: Path, session_state: Optional[SessionState] = None):
        self.repo_path = repo_path
        self.repo = Repo(repo_path)
        self.session_state = session_state
        self.classifier = ConflictClassifier()
        self.ai_resolver = AIConflictResolver()
        self.max_attempts = 2
        
    def detect_conflicts(self) -> List[str]:
        """Detect files with merge conflicts"""
        try:
            # Get unmerged files
            unmerged = self.repo.git.diff('--name-only', '--diff-filter=U')
            return unmerged.strip().split('\n') if unmerged else []
        except Exception as e:
            logger.error(f"Error detecting conflicts: {e}")
            return []
    
    def preview_merge(self, source_branch: str) -> Tuple[bool, List[str]]:
        """Preview merge without actually merging"""
        try:
            # Use merge-tree for non-destructive preview (Git 2.23+)
            result = self.repo.git.merge_tree(source_branch, 'HEAD')
            if 'CONFLICT' in result:
                # Extract conflicting files
                conflicts = []
                for line in result.split('\n'):
                    if 'CONFLICT' in line:
                        # Parse file path from conflict line
                        parts = line.split()
                        for part in parts:
                            if '/' in part or '.' in part:
                                conflicts.append(part)
                return False, conflicts
            return True, []
        except Exception as e:
            logger.warning(f"merge-tree not available, using traditional method: {e}")
            # Fallback: attempt merge and abort
            try:
                self.repo.git.merge('--no-commit', '--no-ff', source_branch)
                # If we get here, no conflicts
                self.repo.git.merge('--abort')
                return True, []
            except GitCommandError:
                conflicts = self.detect_conflicts()
                self.repo.git.merge('--abort')
                return False, conflicts
    
    def resolve_conflicts_autonomously(self, agent: AgentState, source_branch: str) -> Dict[str, Any]:
        """Main autonomous conflict resolution workflow"""
        result = {
            'success': False,
            'attempts': 0,
            'resolved_files': [],
            'failed_files': [],
            'escalation_needed': False,
            'details': {}
        }
        
        # Create backup branch
        backup_branch = f"backup-{agent.role}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.repo.create_head(backup_branch)
        logger.info(f"Created backup branch: {backup_branch}")
        
        for attempt in range(self.max_attempts):
            result['attempts'] = attempt + 1
            
            try:
                # Attempt merge
                self.repo.git.merge('--no-commit', '--no-ff', source_branch)
                
                # Check for conflicts
                conflicts = self.detect_conflicts()
                if not conflicts:
                    # No conflicts, complete merge
                    self.repo.index.commit(f"Merged {source_branch} into {agent.current_branch}")
                    result['success'] = True
                    break
                
                # Classify conflicts
                conflict_info = self.classifier.classify_conflict(self.repo, conflicts)
                result['details']['classification'] = conflict_info
                
                if conflict_info['type'] == 'complex' or conflict_info['confidence'] < 0.7:
                    # Too complex for autonomous resolution
                    result['escalation_needed'] = True
                    logger.warning(f"Complex conflicts detected, escalation needed: {conflicts}")
                    self.repo.git.merge('--abort')
                    break
                
                # Attempt AI resolution
                success, resolved_content = self.ai_resolver.resolve(
                    self.repo, conflict_info, agent
                )
                
                if success:
                    # Apply resolutions
                    for file_path, content in resolved_content.items():
                        full_path = self.repo.working_dir / file_path
                        full_path.write_text(content)
                        self.repo.index.add([file_path])
                        result['resolved_files'].append(file_path)
                    
                    # Validate resolution
                    if self._validate_resolution(agent):
                        # Commit resolution
                        self.repo.index.commit(
                            f"AI-resolved merge conflicts from {source_branch}\n\n"
                            f"Resolved files: {', '.join(resolved_content.keys())}\n"
                            f"Agent: {agent.role}"
                        )
                        result['success'] = True
                        
                        # Update agent state
                        if agent:
                            agent.commit_hash = self.repo.head.commit.hexsha[:8]
                        
                        # Log to session state
                        if self.session_state:
                            self._log_resolution_to_state(result, agent)
                        
                        break
                    else:
                        # Validation failed, reset and retry
                        logger.warning(f"Resolution validation failed, attempt {attempt + 1}")
                        self.repo.git.reset('--hard', backup_branch)
                        
                else:
                    # AI resolution failed
                    result['failed_files'].extend(conflicts)
                    self.repo.git.merge('--abort')
                    
            except Exception as e:
                logger.error(f"Error in resolution attempt {attempt + 1}: {e}")
                try:
                    self.repo.git.merge('--abort')
                except:
                    pass
                self.repo.git.reset('--hard', backup_branch)
        
        # Clean up backup if successful
        if result['success']:
            self.repo.delete_head(backup_branch, force=True)
        else:
            result['details']['backup_branch'] = backup_branch
            
        return result
    
    def _validate_resolution(self, agent: AgentState) -> bool:
        """Validate the resolved merge"""
        try:
            # Check for conflict markers
            if self.repo.git.grep('<<<<<<<', '--', '*.py', '*.js', '*.ts', _ok_code=[0,1]):
                logger.error("Conflict markers still present")
                return False
            
            # Check git status
            if self.repo.is_dirty():
                untracked = self.repo.untracked_files
                if untracked:
                    logger.warning(f"Untracked files after resolution: {untracked}")
            
            # Run basic syntax checks
            # TODO: Add project-specific validation (tests, linting)
            
            return True
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
    
    def _log_resolution_to_state(self, result: Dict[str, Any], agent: AgentState):
        """Log resolution outcome to session state"""
        if not self.session_state:
            return
            
        report = {
            'timestamp': datetime.now().isoformat(),
            'topic': 'merge_resolution',
            'agent': agent.role,
            'status': 'SUCCESS' if result['success'] else 'FAILED',
            'details': {
                'attempts': result['attempts'],
                'resolved_files': result['resolved_files'],
                'failed_files': result['failed_files'],
                'escalation_needed': result['escalation_needed']
            }
        }
        
        # Add to agent's status reports
        if agent.role in self.session_state.agents:
            if not hasattr(self.session_state.agents[agent.role], 'status_reports'):
                self.session_state.agents[agent.role].status_reports = []
            self.session_state.agents[agent.role].status_reports.append(report)


# Wrapper functions for command-line usage
def resolve_conflicts_cli(worktree_path: str, source_branch: str, agent_role: str) -> int:
    """CLI wrapper for conflict resolution"""
    try:
        # Load session state if available
        state_manager = SessionStateManager(Path(worktree_path).parent.parent)
        state = state_manager.load_session_state("current")  # Adjust project name
        agent = state.agents.get(agent_role) if state else None
        
        # Create resolver
        resolver = GitConflictResolver(Path(worktree_path), state)
        
        # Check for conflicts
        has_conflicts, conflict_files = resolver.preview_merge(source_branch)
        if not has_conflicts:
            print("No conflicts detected, merge can proceed normally")
            return 0
        
        print(f"Detected conflicts in: {conflict_files}")
        
        # Attempt resolution
        result = resolver.resolve_conflicts_autonomously(agent or AgentState(role=agent_role), source_branch)
        
        if result['success']:
            print(f"✓ Successfully resolved conflicts in {result['attempts']} attempt(s)")
            print(f"  Resolved files: {', '.join(result['resolved_files'])}")
            return 0
        else:
            print(f"✗ Failed to resolve conflicts after {result['attempts']} attempts")
            if result['escalation_needed']:
                print("  Escalation needed: conflicts too complex for autonomous resolution")
            if result.get('details', {}).get('backup_branch'):
                print(f"  Backup branch: {result['details']['backup_branch']}")
            return 1
            
    except Exception as e:
        print(f"Error: {e}")
        return 2


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: git_conflict_resolver.py <worktree_path> <source_branch> <agent_role>")
        sys.exit(1)
    
    sys.exit(resolve_conflicts_cli(sys.argv[1], sys.argv[2], sys.argv[3]))
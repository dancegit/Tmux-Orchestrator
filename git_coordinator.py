#!/usr/bin/env python3
"""
Git Coordinator for Tmux Orchestrator - Manages worktree synchronization.
Centralizes git operations to prevent agent worktree divergence and deployment conflicts.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, List
from git import Repo, GitCommandError
from session_state import SessionState, AgentState

logger = logging.getLogger(__name__)

class GitCoordinator:
    """Coordinates git operations across agent worktrees."""
    
    def __init__(self, base_repo_path: Path):
        self.base_repo_path = base_repo_path  # Root of the shared .git repo
    
    def detect_divergence(self, state: SessionState) -> bool:
        """Check if agent worktrees have divergent commit hashes."""
        hashes = set()
        for agent in state.agents.values():
            if agent.worktree_path and Path(agent.worktree_path).exists() and agent.commit_hash:
                hashes.add(agent.commit_hash)
        return len(hashes) > 1  # True if branches have diverged
    
    def get_worktree_status(self, agent: AgentState) -> Dict[str, str]:
        """Get git status info for an agent's worktree."""
        if not agent.worktree_path or not Path(agent.worktree_path).exists():
            return {'status': 'not_found', 'branch': None, 'commit': None}
        
        try:
            repo = Repo(agent.worktree_path)
            return {
                'status': 'detached' if repo.is_detached else 'active',
                'branch': repo.active_branch.name if not repo.is_detached else 'detached',
                'commit': repo.head.commit.hexsha[:8],
                'dirty': repo.is_dirty()
            }
        except Exception as e:
            logger.error(f"Failed to get status for {agent.role}: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def sync_agent_branch(self, agent: AgentState, source_branch: str = 'main', remote: str = 'origin') -> bool:
        """Sync a single agent's worktree by fetching and merging from a source branch."""
        if not agent.worktree_path or not Path(agent.worktree_path).exists():
            logger.error(f"Worktree not found for {agent.role}: {agent.worktree_path}")
            return False
        
        try:
            repo = Repo(agent.worktree_path)
            
            # Fetch latest from remote
            logger.info(f"Fetching latest changes for {agent.role}")
            repo.git.fetch(remote)
            
            # Handle detached HEAD
            if repo.is_detached:
                target_branch = agent.current_branch or 'main'
                logger.info(f"Checking out {target_branch} from detached HEAD for {agent.role}")
                repo.git.checkout(target_branch)
            
            # Merge the source branch
            merge_ref = f'{remote}/{source_branch}'
            logger.info(f"Merging {merge_ref} into {agent.role}'s worktree")
            repo.git.merge(merge_ref, '--no-ff')
            
            # Update agent state
            agent.current_branch = repo.active_branch.name
            agent.commit_hash = repo.head.commit.hexsha[:8]
            
            logger.info(f"Successfully synced {agent.role} to {source_branch} at commit {agent.commit_hash}")
            return True
            
        except GitCommandError as e:
            logger.error(f"Git operation failed for {agent.role}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error syncing {agent.role}: {e}")
            return False
    
    def sync_all_agents(self, state: SessionState, source_role: str = 'sysadmin', 
                       target_roles: Optional[List[str]] = None) -> Dict[str, bool]:
        """Sync all (or targeted) agents from a source role's branch."""
        results = {}
        source_agent = state.agents.get(source_role)
        
        if not source_agent:
            logger.error(f"Source agent {source_role} not found in session state")
            return results
        
        # Get source branch - default to main if not set
        source_branch = source_agent.current_branch or 'main'
        logger.info(f"Syncing from {source_role}'s branch: {source_branch}")
        
        # Determine target agents
        if target_roles is None:
            target_roles = [role for role in state.agents.keys() if role != source_role]
        
        # Sync each target agent
        for role in target_roles:
            if role == source_role:
                continue  # Skip self
            
            agent = state.agents.get(role)
            if agent:
                logger.info(f"Syncing {role} from {source_role}")
                results[role] = self.sync_agent_branch(agent, source_branch=source_branch)
            else:
                logger.warning(f"Target agent {role} not found")
                results[role] = False
        
        # Log summary
        successful = [role for role, success in results.items() if success]
        failed = [role for role, success in results.items() if not success]
        
        if successful:
            logger.info(f"Successfully synced: {', '.join(successful)}")
        if failed:
            logger.error(f"Failed to sync: {', '.join(failed)}")
        
        return results
    
    def resolve_deployment_conflict(self, state: SessionState) -> bool:
        """
        Resolve deployment conflicts by syncing DevOps/SysAdmin changes to Developer/Tester.
        This addresses the specific case where SysAdmin reports success but Developer reports failure.
        """
        logger.info("Attempting to resolve deployment conflict via git sync")
        
        # Priority order: DevOps first (has deployment configs), then SysAdmin (has system changes)
        for source_role in ['devops', 'sysadmin']:
            if source_role in state.agents:
                results = self.sync_all_agents(
                    state, 
                    source_role=source_role, 
                    target_roles=['developer', 'tester']
                )
                if any(results.values()):
                    logger.info(f"Resolved conflict by syncing from {source_role}")
                    return True
        
        logger.warning("Could not resolve deployment conflict - no suitable source agent found")
        return False
    
    def force_worktree_reset(self, agent: AgentState, target_branch: str = 'main') -> bool:
        """
        Force reset a worktree to a clean state - use as last resort for stuck agents.
        """
        if not agent.worktree_path or not Path(agent.worktree_path).exists():
            logger.error(f"Worktree not found for {agent.role}: {agent.worktree_path}")
            return False
        
        try:
            repo = Repo(agent.worktree_path)
            logger.warning(f"Force resetting {agent.role} worktree to {target_branch}")
            
            # Fetch latest
            repo.git.fetch('origin')
            
            # Hard reset to target branch
            repo.git.reset('--hard', f'origin/{target_branch}')
            repo.git.clean('-fd')  # Remove untracked files
            
            # Update agent state
            agent.current_branch = target_branch
            agent.commit_hash = repo.head.commit.hexsha[:8]
            
            logger.info(f"Force reset {agent.role} to {target_branch} at {agent.commit_hash}")
            return True
            
        except Exception as e:
            logger.error(f"Force reset failed for {agent.role}: {e}")
            return False
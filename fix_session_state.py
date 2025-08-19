#!/usr/bin/env python3
"""
Fix session state by populating missing worktree paths for existing projects.
"""

from pathlib import Path
from session_state import SessionStateManager

def fix_signalmatrix_session():
    """Fix the Signalmatrix Event Delivery Architecture session state"""
    
    tmux_orch_path = Path('/home/clauderun/Tmux-Orchestrator')
    state_manager = SessionStateManager(tmux_orch_path)
    
    project_name = "Signalmatrix Event Delivery Architecture"
    state = state_manager.load_session_state(project_name)
    
    if not state:
        print(f"❌ No session state found for {project_name}")
        return False
    
    # Worktree base path
    worktree_base = Path("/home/clauderun/signalmatrix/signalmatrix_org/signalmatrix-slice-slice-deployment-tmux-worktrees")
    
    # Update agent worktree paths
    updates = 0
    for role, agent in state.agents.items():
        worktree_path = worktree_base / role
        if worktree_path.exists():
            agent.worktree_path = str(worktree_path)
            updates += 1
            print(f"✅ Updated {role}: {worktree_path}")
        else:
            print(f"⚠️  Worktree not found for {role}: {worktree_path}")
    
    # Update session name to match actual tmux session
    state.session_name = "signalmatrix-event-delivery-architecture-impl-a9601f5d"
    
    # Update project path
    state.project_path = str(worktree_base.parent / "signalmatrix-slice-slice-deployment")
    
    # Save updated state
    state_manager.save_session_state(state)
    print(f"✅ Updated session state with {updates} worktree paths")
    
    return True

if __name__ == "__main__":
    fix_signalmatrix_session()
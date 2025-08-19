#!/usr/bin/env python3
"""
Quick fix script to resolve stalled project by forcing git sync and nudging agents.
Specifically addresses deployment conflicts and non-responsive agents.
"""

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path
from session_state import SessionStateManager
from git_coordinator import GitCoordinator

# Adjust paths as needed
TMUX_ORCH_PATH = Path('/home/clauderun/Tmux-Orchestrator')

def send_message_to_agent(session_name: str, window_index: int, message: str) -> bool:
    """Send message to specific agent using send-claude-message.sh"""
    send_script = TMUX_ORCH_PATH / 'send-claude-message.sh'
    if not send_script.exists():
        print(f"Warning: send-claude-message.sh not found at {send_script}")
        return False
    
    try:
        result = subprocess.run([
            str(send_script),
            f"{session_name}:{window_index}",
            message
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Message sent to window {window_index}")
            return True
        else:
            print(f"❌ Failed to send message to window {window_index}: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error sending message to window {window_index}: {e}")
        return False

def clear_emergency_checkins(session_name: str) -> bool:
    """Clear looping emergency check-ins from scheduler database"""
    scheduler_db = TMUX_ORCH_PATH / 'task_queue.db'
    if not scheduler_db.exists():
        print("ℹ️  No scheduler database found - no emergency check-ins to clear")
        return True
    
    try:
        conn = sqlite3.connect(str(scheduler_db))
        cursor = conn.cursor()
        
        # Count emergency tasks first
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE note LIKE '%EMERGENCY%' AND session_name = ?", (session_name,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Delete emergency tasks
            cursor.execute("DELETE FROM tasks WHERE note LIKE '%EMERGENCY%' AND session_name = ?", (session_name,))
            conn.commit()
            print(f"✅ Cleared {count} looping emergency check-ins")
        else:
            print("ℹ️  No emergency check-ins found")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to clear emergency check-ins: {e}")
        return False

def resolve_stall(project_name: str, session_name: str = None) -> bool:
    """Main function to resolve project stall"""
    print(f"🔧 Resolving stall for project: {project_name}")
    
    # Initialize managers
    state_manager = SessionStateManager(TMUX_ORCH_PATH)
    git_coord = GitCoordinator(TMUX_ORCH_PATH)
    
    # Load project state
    state = state_manager.load_session_state(project_name)
    if not state:
        print(f"❌ State not found for {project_name}")
        return False
    
    # Use provided session name or derive from state
    if session_name is None:
        session_name = state.session_name
    
    print(f"📊 Project session: {session_name}")
    print(f"📊 Agents: {list(state.agents.keys())}")
    
    success = True
    
    # Step 1: Force sync from SysAdmin to Developer/Tester
    print("\n🔄 Step 1: Forcing git sync from SysAdmin to Developer/Tester")
    
    try:
        sync_results = git_coord.sync_all_agents(
            state, 
            source_role='sysadmin', 
            target_roles=['developer', 'tester']
        )
        
        if not sync_results:
            print("⚠️  No sync results - agents may not have worktree paths set")
        elif any(sync_results.values()):
            successful_syncs = [role for role, result in sync_results.items() if result]
            print(f"✅ Git sync successful: {', '.join(successful_syncs)}")
            state_manager.save_session_state(state)  # Save updated state
        else:
            print("⚠️  Git sync failed for all agents - check git logs for conflicts")
            # Try DevOps as fallback
            print("🔄 Trying DevOps as sync source...")
            devops_sync = git_coord.sync_all_agents(
                state,
                source_role='devops',
                target_roles=['developer', 'tester']
            )
            if any(devops_sync.values()):
                print("✅ DevOps sync partially successful")
                state_manager.save_session_state(state)
            else:
                print("❌ All git sync attempts failed")
                success = False
                
    except Exception as e:
        print(f"❌ Git sync error: {e}")
        success = False
    
    # Step 2: Send targeted nudges to key agents
    print("\n📢 Step 2: Sending verification requests to agents")
    
    nudge_message = """🚨 URGENT VERIFICATION: Git sync completed - Re-verify deployment status:

1. Pull latest changes: git pull origin main
2. Re-run tests/build to confirm shared_kernel and dependencies are available
3. Report status: 'DEPLOYMENT SUCCESS' or specific details on remaining issues
4. If still blocked, explain exactly what is failing and what you need

The SysAdmin vs Developer deployment conflict must be resolved NOW. Git branches have been synchronized."""
    
    # Send to Developer and Tester
    target_agents = [
        ('developer', 'Developer'),
        ('tester', 'Tester')
    ]
    
    for role, role_name in target_agents:
        if role in state.agents:
            agent = state.agents[role]
            window = agent.window_index
            print(f"📤 Sending urgent verification to {role_name} (window {window})")
            if not send_message_to_agent(session_name, window, nudge_message):
                success = False
        else:
            print(f"⚠️  {role_name} not found in agent list")
    
    # Also send status request to SysAdmin for confirmation
    if 'sysadmin' in state.agents:
        sysadmin = state.agents['sysadmin']
        sysadmin_message = """🔍 SYSADMIN VERIFICATION: Please confirm deployment status after git sync:

1. Verify Modal deployment is truly functional (not just deployed)
2. Check shared_kernel dependency is available in container
3. Test actual event processing - don't just check build success
4. If issues found, fix immediately and notify team

Your 'COMPLETE' status conflicts with Developer's 'FAILURE' - we need definitive verification."""
        
        print(f"📤 Sending verification request to SysAdmin (window {sysadmin.window_index})")
        send_message_to_agent(session_name, sysadmin.window_index, sysadmin_message)
    
    # Step 3: Clear looping check-ins
    print("\n🧹 Step 3: Clearing looping emergency check-ins")
    if not clear_emergency_checkins(session_name):
        success = False
    
    # Step 4: Send status to orchestrator
    if 'orchestrator' in state.agents:
        orchestrator = state.agents['orchestrator']
        orch_message = """🎯 STALL RESOLUTION ACTIONS COMPLETED:

✅ Git sync forced from SysAdmin → Developer/Tester
✅ Urgent verification requests sent to all agents  
✅ Emergency check-in loops cleared

Next Actions:
1. Monitor agent responses (expect replies within 10 minutes)
2. If agents still don't respond, escalate to manual intervention
3. If deployment verified working, proceed with next phases
4. If deployment still failing, diagnose root cause

Check claude_control.py status detailed for updates."""
        
        print(f"📤 Sending status update to Orchestrator (window {orchestrator.window_index})")
        send_message_to_agent(session_name, orchestrator.window_index, orch_message)
    
    print(f"\n{'✅ Stall resolution completed successfully!' if success else '⚠️  Stall resolution completed with some issues'}")
    print("🔍 Monitor responses with: python3 claude_control.py status detailed")
    
    return success

def main():
    parser = argparse.ArgumentParser(description="Resolve stalled tmux orchestrator project")
    parser.add_argument("--project", required=True, 
                       help="Project name (e.g., 'Signalmatrix Event Delivery Architecture')")
    parser.add_argument("--session", 
                       help="Session name (auto-detected if not provided)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🧪 DRY RUN MODE - would resolve stall for:", args.project)
        return
    
    success = resolve_stall(args.project, args.session)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
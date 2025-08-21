#!/usr/bin/env python3
"""
Test enhanced phantom detection system
"""

import sqlite3
import sys
import os
sys.path.append('/home/clauderun/Tmux-Orchestrator')

from scheduler import TmuxOrchestratorScheduler

def test_phantom_detection():
    """Test the enhanced phantom detection system"""
    print("🧪 Testing Enhanced Phantom Detection System")
    print("=" * 50)
    
    # Initialize scheduler
    scheduler = TmuxOrchestratorScheduler()
    
    # Test Project 60 (has tmux session but marked as failed)
    print("\n📋 Testing Project 60 detection:")
    print("  Status in DB: failed")
    print("  Session name in DB: elliott-wave-5-options-trading-report-generation-impl-4793ecde")
    print("  Tmux session active: Yes")
    
    # Test the enhanced validation
    session_name = "elliott-wave-5-options-trading-report-generation-impl-4793ecde"
    spec_path = "/home/clauderun/signalmatrix/signalmatrix_org/signalmatrix-slice-reporting/REPORTING_MVP_IMPLEMENTATION.md"
    
    is_live, reason = scheduler.validate_session_liveness(
        session_name, 
        project_id=60, 
        spec_path=spec_path
    )
    
    print(f"  📊 Direct validation result: {is_live}")
    print(f"  📝 Reason: {reason}")
    
    # Test pattern matching fallback (simulate missing session_name)
    print("\n🔍 Testing pattern matching fallback:")
    print("  Simulating missing session_name (None)")
    
    is_live_fallback, reason_fallback = scheduler.validate_session_liveness(
        None,  # No session name
        project_id=60, 
        spec_path=spec_path
    )
    
    print(f"  📊 Fallback validation result: {is_live_fallback}")
    print(f"  📝 Reason: {reason_fallback}")
    
    # Test with an invalid project to see fallback behavior
    print("\n🧪 Testing fallback with no matching sessions:")
    print("  Testing project with no active sessions")
    
    is_live_none, reason_none = scheduler.validate_session_liveness(
        None,
        project_id=999,
        spec_path="/fake/path/to/NONEXISTENT_SPEC.md"
    )
    
    print(f"  📊 No-match validation result: {is_live_none}")
    print(f"  📝 Reason: {reason_none}")
    
    print("\n✅ Enhanced phantom detection test completed!")
    print("=" * 50)

if __name__ == "__main__":
    test_phantom_detection()
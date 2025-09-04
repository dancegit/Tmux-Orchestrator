import os
import ast
import re
from pathlib import Path

def analyze_delegation_patterns():
    """Find all places where modular code delegates to legacy"""
    tmux_orchestrator_dir = Path("tmux_orchestrator")
    scheduler_modules_dir = Path("scheduler_modules") 
    
    delegation_patterns = []
    
    # Check tmux_orchestrator for delegation
    if tmux_orchestrator_dir.exists():
        for py_file in tmux_orchestrator_dir.rglob("*.py"):
            try:
                content = py_file.read_text()
                if "auto_orchestrate" in content or "subprocess" in content:
                    delegation_patterns.append({
                        "file": str(py_file),
                        "type": "tmux_orchestrator",
                        "delegates_to_legacy": True,
                        "contains_subprocess": "subprocess" in content
                    })
            except Exception as e:
                print(f"Error reading {py_file}: {e}")
    
    # Check scheduler_modules for completeness
    expected_modules = [
        "core_scheduler.py", "queue_manager.py", "session_monitor.py",
        "process_manager_wrapper.py", "state_synchronizer_wrapper.py",
        "event_dispatcher.py", "batch_processor.py", "recovery_manager.py",
        "notification_manager.py", "dependency_checker.py", "cli_handler.py",
        "config.py", "utils.py"
    ]
    
    missing_modules = []
    if scheduler_modules_dir.exists():
        existing_modules = [f.name for f in scheduler_modules_dir.glob("*.py") if f.name != "__init__.py"]
        missing_modules = [m for m in expected_modules if m not in existing_modules]
    
    return {
        "delegation_patterns": delegation_patterns,
        "missing_scheduler_modules": missing_modules,
        "tmux_orchestrator_exists": tmux_orchestrator_dir.exists(),
        "scheduler_modules_exists": scheduler_modules_dir.exists()
    }

def main():
    status = analyze_delegation_patterns()
    import json
    print(json.dumps(status, indent=2))

if __name__ == "__main__":
    main()

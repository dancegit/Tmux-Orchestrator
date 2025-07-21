#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "watchdog>=3.0.0",
# ]
# ///
"""
Watch CLAUDE.md for changes and automatically update compliance rules
"""

import os
import sys
import time
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ClaudeMdHandler(FileSystemEventHandler):
    def __init__(self, claude_md_path: Path, monitoring_dir: Path):
        self.claude_md_path = claude_md_path
        self.monitoring_dir = monitoring_dir
        self.last_hash = self._get_file_hash()
        self.last_update = datetime.now()
        
    def _get_file_hash(self) -> str:
        """Get MD5 hash of CLAUDE.md file"""
        try:
            with open(self.claude_md_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
            
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
            
        # Check if it's CLAUDE.md that changed
        if Path(event.src_path).resolve() == self.claude_md_path.resolve():
            # Debounce - ignore rapid successive changes
            now = datetime.now()
            if (now - self.last_update).total_seconds() < 2:
                return
                
            # Check if content actually changed
            new_hash = self._get_file_hash()
            if new_hash == self.last_hash:
                return
                
            print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] CLAUDE.md changed, updating rules...")
            self.last_hash = new_hash
            self.last_update = now
            
            # Run the rule extractor
            self._update_rules()
            
    def _update_rules(self):
        """Run the rule extraction script"""
        extract_script = self.monitoring_dir / "extract_rules.py"
        
        try:
            # Run the extraction script
            result = subprocess.run(
                [sys.executable, str(extract_script)],
                capture_output=True,
                text=True,
                cwd=str(self.monitoring_dir)
            )
            
            if result.returncode == 0:
                print(f"✓ Rules updated successfully")
                print(result.stdout)
                
                # Notify compliance monitor about rule update
                self._notify_monitor()
            else:
                print(f"✗ Failed to update rules:")
                print(result.stderr)
                
        except Exception as e:
            print(f"✗ Error updating rules: {e}")
            
    def _notify_monitor(self):
        """Notify the compliance monitor about rule updates"""
        log_dir = self.monitoring_dir.parent / "registry" / "logs" / "communications" / datetime.now().strftime("%Y-%m-%d")
        trigger_file = log_dir / ".rules_updated"
        
        try:
            # Create trigger file to notify monitor
            log_dir.mkdir(parents=True, exist_ok=True)
            trigger_file.touch()
            
            # Also log the update
            update_log = self.monitoring_dir / "rule_updates.log"
            with open(update_log, 'a') as f:
                f.write(f"{datetime.now().isoformat()} - Rules updated from CLAUDE.md\n")
                
        except Exception as e:
            print(f"Warning: Could not notify monitor: {e}")

def main():
    """Start watching CLAUDE.md for changes"""
    script_dir = Path(__file__).parent
    claude_md = script_dir.parent / "CLAUDE.md"
    
    if not claude_md.exists():
        print(f"Error: CLAUDE.md not found at {claude_md}")
        sys.exit(1)
        
    print(f"Watching CLAUDE.md for changes...")
    print(f"File: {claude_md}")
    print(f"Press Ctrl+C to stop")
    
    # Initial rule extraction
    handler = ClaudeMdHandler(claude_md, script_dir)
    handler._update_rules()
    
    # Set up file watcher
    observer = Observer()
    observer.schedule(handler, str(claude_md.parent), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopping watcher...")
        
    observer.join()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Migration Tool for Tmux Orchestrator Modularization

This script helps migrate from the monolithic auto_orchestrate.py system
to the new modular tmux_orchestrator package architecture.

Features:
- Validates modular system integrity
- Migrates existing session data
- Updates configuration files
- Provides rollback capabilities
- Comprehensive testing and verification
"""

import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table

console = Console()

# Add tmux_orchestrator package to path
sys.path.insert(0, str(Path(__file__).parent))

class MigrationTool:
    """
    Handles migration from monolithic to modular architecture.
    """
    
    def __init__(self, orchestrator_path: Path):
        """
        Initialize migration tool.
        
        Args:
            orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.orchestrator_path = orchestrator_path
        self.backup_dir = orchestrator_path / 'migration_backup'
        self.migration_log = orchestrator_path / 'migration.log'
        
        # Create backup directory
        self.backup_dir.mkdir(exist_ok=True)
    
    def run_migration(self) -> bool:
        """
        Run complete migration process.
        
        Returns:
            bool: True if migration successful
        """
        console.print(Panel.fit(
            "[bold blue]Tmux Orchestrator Migration to Modular System[/bold blue]",
            border_style="blue"
        ))
        
        steps = [
            ("Validating modular system", self.validate_modular_system),
            ("Creating backup", self.create_backup),
            ("Migrating session data", self.migrate_session_data),
            ("Updating configurations", self.update_configurations),
            ("Testing modular integration", self.test_modular_integration),
            ("Verifying migration", self.verify_migration)
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            for step_name, step_func in steps:
                task = progress.add_task(f"{step_name}...", total=None)
                
                try:
                    success = step_func()
                    if success:
                        progress.update(task, description=f"✅ {step_name} completed")
                        console.print(f"[green]✅ {step_name} successful[/green]")
                    else:
                        progress.update(task, description=f"❌ {step_name} failed")
                        console.print(f"[red]❌ {step_name} failed[/red]")
                        return False
                        
                except Exception as e:
                    progress.update(task, description=f"❌ {step_name} error: {e}")
                    console.print(f"[red]❌ {step_name} error: {e}[/red]")
                    return False
                finally:
                    progress.remove_task(task)
        
        console.print("[green]🎉 Migration completed successfully![/green]")
        return True
    
    def validate_modular_system(self) -> bool:
        """Validate that the modular system is properly installed."""
        try:
            # Import and test all major modules
            from tmux_orchestrator import (
                Orchestrator, SessionManager, StateManager,
                ClaudeInitializer, OAuthManager,
                AgentFactory, BriefingSystem,
                WorktreeManager, TmuxSessionController, TmuxMessenger,
                QueueManager, HealthMonitor,
                FileUtils, SystemUtils, ConfigLoader,
                EnhancedCLI
            )
            
            # Test basic instantiation
            orchestrator = Orchestrator()
            
            # Verify all subsystems are available
            required_subsystems = [
                'session_manager', 'state_manager', 'agent_factory', 'briefing_system',
                'git_manager', 'tmux_controller', 'messenger',
                'queue_manager', 'health_monitor', 'config_loader', 'cli',
                'claude_initializer', 'oauth_manager'
            ]
            
            for subsystem in required_subsystems:
                if not hasattr(orchestrator, subsystem):
                    console.print(f"[red]❌ Missing subsystem: {subsystem}[/red]")
                    return False
                
                if getattr(orchestrator, subsystem) is None:
                    console.print(f"[red]❌ Uninitialized subsystem: {subsystem}[/red]")
                    return False
            
            console.print("[green]✅ All modular subsystems validated[/green]")
            return True
            
        except ImportError as e:
            console.print(f"[red]❌ Import error in modular system: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Validation error: {e}[/red]")
            return False
    
    def create_backup(self) -> bool:
        """Create backup of existing system."""
        try:
            # Backup important files and directories
            backup_targets = [
                'registry',
                'auto_orchestrate.py',
                'send-claude-message.sh',
                'schedule_with_note.sh',
                'checkin_monitor.py'
            ]
            
            for target in backup_targets:
                source_path = self.orchestrator_path / target
                if source_path.exists():
                    backup_path = self.backup_dir / target
                    
                    if source_path.is_file():
                        shutil.copy2(source_path, backup_path)
                    elif source_path.is_dir():
                        if backup_path.exists():
                            shutil.rmtree(backup_path)
                        shutil.copytree(source_path, backup_path)
                    
                    console.print(f"[blue]📁 Backed up: {target}[/blue]")
            
            # Create backup manifest
            manifest = {
                'backup_time': __import__('time').time(),
                'backed_up_files': backup_targets,
                'orchestrator_path': str(self.orchestrator_path),
                'migration_version': '2.0.0'
            }
            
            manifest_path = self.backup_dir / 'backup_manifest.json'
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            console.print(f"[green]✅ Backup created in {self.backup_dir}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Backup creation failed: {e}[/red]")
            return False
    
    def migrate_session_data(self) -> bool:
        """Migrate existing session data to modular format."""
        try:
            from tmux_orchestrator.utils.file_utils import FileUtils
            
            registry_path = self.orchestrator_path / 'registry'
            if not registry_path.exists():
                console.print("[yellow]⚠️ No existing registry to migrate[/yellow]")
                return True
            
            # Migrate session data
            sessions_dir = registry_path / 'sessions'
            if sessions_dir.exists():
                for session_file in sessions_dir.glob('*.json'):
                    session_data = FileUtils.read_json(session_file)
                    if session_data:
                        # Convert to new format if needed
                        migrated_data = self._convert_session_format(session_data)
                        FileUtils.write_json(session_file, migrated_data)
                        console.print(f"[blue]📄 Migrated session: {session_file.name}[/blue]")
            
            # Migrate state data
            state_dir = registry_path / 'state'
            state_dir.mkdir(exist_ok=True)
            
            # Ensure global state exists
            global_state_file = state_dir / 'global_state.json'
            if not global_state_file.exists():
                from tmux_orchestrator.core.state_manager import StateManager
                state_manager = StateManager(self.orchestrator_path)
                # This will create the file with default values
            
            console.print("[green]✅ Session data migration completed[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Session data migration failed: {e}[/red]")
            return False
    
    def update_configurations(self) -> bool:
        """Update configuration files for modular system."""
        try:
            from tmux_orchestrator.utils.config_loader import ConfigLoader
            
            config_dir = self.orchestrator_path / 'config'
            config_loader = ConfigLoader(config_dir)
            
            # Create default orchestrator configuration
            orchestrator_config = {
                'oauth': {
                    'port': 3000,
                    'timeout_seconds': 45
                },
                'tmux': {
                    'session_prefix': 'tmux-orc'
                },
                'agents': {
                    'default_check_in_minutes': 45
                },
                'logging': {
                    'level': 'INFO'
                }
            }
            
            if not (config_dir / 'orchestrator.json').exists():
                config_loader.save_config('orchestrator', orchestrator_config)
                console.print("[blue]📝 Created default orchestrator config[/blue]")
            
            # Create monitoring configuration
            monitoring_config = {
                'thresholds': {
                    'cpu_warning': 80.0,
                    'memory_warning': 85.0,
                    'disk_warning': 85.0
                },
                'collection_interval': 60,
                'retention_hours': 168
            }
            
            if not (config_dir / 'monitoring.json').exists():
                config_loader.save_config('monitoring', monitoring_config)
                console.print("[blue]📝 Created monitoring config[/blue]")
            
            console.print("[green]✅ Configuration update completed[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Configuration update failed: {e}[/red]")
            return False
    
    def test_modular_integration(self) -> bool:
        """Test modular system integration."""
        try:
            # Run the comprehensive test suite
            console.print("[blue]🧪 Running modular system tests...[/blue]")
            
            # Import and run Phase 5 integration tests
            from tmux_orchestrator import create_orchestrator, get_system_info
            
            # Test orchestrator creation
            orchestrator = create_orchestrator()
            if not orchestrator:
                console.print("[red]❌ Failed to create orchestrator[/red]")
                return False
            
            # Test system info
            system_info = get_system_info()
            if not system_info or 'orchestrator_version' not in system_info:
                console.print("[red]❌ Failed to get system info[/red]")
                return False
            
            # Test OAuth functionality
            oauth_status = orchestrator.check_oauth_port_conflicts()
            if not oauth_status or 'port' not in oauth_status:
                console.print("[red]❌ OAuth functionality test failed[/red]")
                return False
            
            # Test health monitoring
            health_summary = orchestrator.health_monitor.get_system_health_summary()
            if not health_summary or 'overall_status' not in health_summary:
                console.print("[red]❌ Health monitoring test failed[/red]")
                return False
            
            console.print("[green]✅ Modular integration tests passed[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Integration testing failed: {e}[/red]")
            return False
    
    def verify_migration(self) -> bool:
        """Verify migration was successful."""
        try:
            # Check that all expected directories exist
            expected_dirs = [
                'tmux_orchestrator/core',
                'tmux_orchestrator/claude', 
                'tmux_orchestrator/agents',
                'tmux_orchestrator/git',
                'tmux_orchestrator/tmux',
                'tmux_orchestrator/database',
                'tmux_orchestrator/monitoring',
                'tmux_orchestrator/utils',
                'tmux_orchestrator/cli',
                'registry/state',
                'registry/sessions',
                'registry/queues',
                'registry/monitoring',
                'config'
            ]
            
            missing_dirs = []
            for dir_path in expected_dirs:
                full_path = self.orchestrator_path / dir_path
                if not full_path.exists():
                    missing_dirs.append(dir_path)
            
            if missing_dirs:
                console.print(f"[red]❌ Missing directories: {missing_dirs}[/red]")
                return False
            
            # Verify modular system can be imported and used
            try:
                from tmux_orchestrator import Orchestrator, get_version
                orchestrator = Orchestrator()
                version = get_version()
                
                if version != "2.0.0":
                    console.print(f"[red]❌ Version mismatch: expected 2.0.0, got {version}[/red]")
                    return False
                
            except Exception as e:
                console.print(f"[red]❌ Modular system verification failed: {e}[/red]")
                return False
            
            # Create migration completion marker
            completion_marker = self.orchestrator_path / '.migration_complete'
            completion_marker.write_text(f"Migration completed successfully at {__import__('time').ctime()}\nVersion: 2.0.0")
            
            console.print("[green]✅ Migration verification successful[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Migration verification failed: {e}[/red]")
            return False
    
    def rollback_migration(self) -> bool:
        """Rollback migration if needed."""
        try:
            console.print("[yellow]🔄 Rolling back migration...[/yellow]")
            
            # Check if backup exists
            manifest_path = self.backup_dir / 'backup_manifest.json'
            if not manifest_path.exists():
                console.print("[red]❌ No backup manifest found[/red]")
                return False
            
            with open(manifest_path) as f:
                manifest = json.load(f)
            
            # Restore backed up files
            for target in manifest['backed_up_files']:
                backup_path = self.backup_dir / target
                restore_path = self.orchestrator_path / target
                
                if backup_path.exists():
                    if restore_path.exists():
                        if restore_path.is_file():
                            restore_path.unlink()
                        elif restore_path.is_dir():
                            shutil.rmtree(restore_path)
                    
                    if backup_path.is_file():
                        shutil.copy2(backup_path, restore_path)
                    elif backup_path.is_dir():
                        shutil.copytree(backup_path, restore_path)
                    
                    console.print(f"[blue]📁 Restored: {target}[/blue]")
            
            # Remove migration marker
            completion_marker = self.orchestrator_path / '.migration_complete'
            if completion_marker.exists():
                completion_marker.unlink()
            
            console.print("[green]✅ Migration rollback completed[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Rollback failed: {e}[/red]")
            return False
    
    def _convert_session_format(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert old session format to new modular format."""
        # For now, just ensure required fields exist
        # In a real migration, this would handle format differences
        
        if 'version' not in session_data:
            session_data['version'] = '2.0.0'
        
        if 'created_with' not in session_data:
            session_data['created_with'] = 'modular_system'
        
        return session_data
    
    def show_migration_status(self) -> None:
        """Show current migration status."""
        console.print(Panel.fit(
            "[bold cyan]Migration Status[/bold cyan]",
            border_style="cyan"
        ))
        
        # Check if migration is complete
        completion_marker = self.orchestrator_path / '.migration_complete'
        
        table = Table(title="System Status")
        table.add_column("Component", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Details")
        
        # Migration status
        if completion_marker.exists():
            migration_status = "[green]✅ COMPLETED[/green]"
            migration_details = completion_marker.read_text().split('\n')[0]
        else:
            migration_status = "[yellow]⚠️ PENDING[/yellow]"
            migration_details = "Migration not yet completed"
        
        table.add_row("Migration", migration_status, migration_details)
        
        # Modular system
        try:
            from tmux_orchestrator import get_version
            version = get_version()
            modular_status = f"[green]✅ v{version}[/green]"
            modular_details = "Modular system available"
        except:
            modular_status = "[red]❌ MISSING[/red]"
            modular_details = "Modular system not available"
        
        table.add_row("Modular System", modular_status, modular_details)
        
        # Backup status
        if self.backup_dir.exists() and (self.backup_dir / 'backup_manifest.json').exists():
            backup_status = "[green]✅ AVAILABLE[/green]"
            backup_details = f"Backup in {self.backup_dir}"
        else:
            backup_status = "[yellow]⚠️ NONE[/yellow]"
            backup_details = "No backup available"
        
        table.add_row("Backup", backup_status, backup_details)
        
        console.print(table)

def main():
    """Main migration script entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate Tmux Orchestrator to modular architecture"
    )
    parser.add_argument(
        "--action",
        choices=['migrate', 'rollback', 'status'],
        default='migrate',
        help="Migration action to perform"
    )
    parser.add_argument(
        "--orchestrator-path",
        type=Path,
        default=Path(__file__).parent,
        help="Path to Tmux Orchestrator installation"
    )
    
    args = parser.parse_args()
    
    migration_tool = MigrationTool(args.orchestrator_path)
    
    if args.action == 'migrate':
        success = migration_tool.run_migration()
        sys.exit(0 if success else 1)
    elif args.action == 'rollback':
        success = migration_tool.rollback_migration()
        sys.exit(0 if success else 1)
    elif args.action == 'status':
        migration_tool.show_migration_status()
        sys.exit(0)

if __name__ == "__main__":
    main()
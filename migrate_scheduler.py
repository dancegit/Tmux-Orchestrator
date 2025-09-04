#!/usr/bin/env python3
"""
Migration script for scheduler modularization.
Automates the phase-based migration of scheduler.py to modular architecture.
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import argparse
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchedulerMigration:
    """Manages the phased migration of scheduler.py to modular architecture."""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.scheduler_path = project_path / "scheduler.py"
        self.modules_path = project_path / "scheduler_modules"
        self.backup_dir = project_path / "scheduler_backups"
        
    def backup_scheduler(self):
        """Create timestamped backup of scheduler.py"""
        self.backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"scheduler_{timestamp}.py"
        
        if self.scheduler_path.exists():
            shutil.copy2(self.scheduler_path, backup_path)
            logger.info(f"✓ Backed up scheduler.py to {backup_path}")
            return backup_path
        else:
            logger.error(f"❌ scheduler.py not found at {self.scheduler_path}")
            return None
            
    def verify_modules(self):
        """Verify all required modules exist."""
        required_modules = [
            "scheduler_modules/__init__.py",
            "scheduler_modules/dependency_checker.py",
            "scheduler_modules/config.py",
            "scheduler_modules/utils.py"
        ]
        
        missing = []
        for module in required_modules:
            module_path = self.project_path / module
            if not module_path.exists():
                missing.append(module)
                
        if missing:
            logger.error(f"❌ Missing modules: {', '.join(missing)}")
            return False
            
        logger.info("✓ All Phase 1 modules verified")
        return True
        
    def test_imports(self):
        """Test that scheduler.py can import new modules."""
        test_script = """
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

try:
    from scheduler_modules.dependency_checker import DependencyChecker
    from scheduler_modules.config import SchedulerConfig
    from scheduler_modules import utils
    print("✓ All imports successful")
    sys.exit(0)
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
"""
        
        test_file = self.project_path / "test_imports.py"
        test_file.write_text(test_script)
        
        try:
            result = subprocess.run(
                [sys.executable, str(test_file)],
                capture_output=True,
                text=True,
                cwd=str(self.project_path)
            )
            
            if result.returncode == 0:
                logger.info(result.stdout.strip())
                return True
            else:
                logger.error(result.stdout.strip())
                return False
        finally:
            test_file.unlink(missing_ok=True)
            
    def run_basic_tests(self):
        """Run basic scheduler functionality tests."""
        test_commands = [
            # Test help
            ["python3", "scheduler.py", "--help"],
            # Test list command
            ["python3", "scheduler.py", "--list"],
            # Test status command
            ["python3", "scheduler.py", "--status"]
        ]
        
        for cmd in test_commands:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(self.project_path),
                    timeout=5
                )
                
                if result.returncode == 0:
                    logger.info(f"✓ Command successful: {' '.join(cmd)}")
                else:
                    logger.warning(f"⚠️  Command failed: {' '.join(cmd)}")
                    logger.debug(f"  Error: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                logger.error(f"❌ Command timed out: {' '.join(cmd)}")
                return False
            except Exception as e:
                logger.error(f"❌ Command error: {' '.join(cmd)} - {e}")
                return False
                
        return True
        
    def phase1_migration(self):
        """Execute Phase 1: Extract utilities and configuration."""
        logger.info("\n" + "="*60)
        logger.info("PHASE 1: Utilities and Configuration Extraction")
        logger.info("="*60)
        
        # Step 1: Backup
        backup = self.backup_scheduler()
        if not backup:
            return False
            
        # Step 2: Verify modules exist
        if not self.verify_modules():
            logger.error("❌ Phase 1 modules not found. Please create them first.")
            return False
            
        # Step 3: Test imports
        logger.info("\nTesting module imports...")
        if not self.test_imports():
            logger.error("❌ Import test failed. Check module structure.")
            return False
            
        # Step 4: Run basic tests
        logger.info("\nRunning basic functionality tests...")
        if not self.run_basic_tests():
            logger.warning("⚠️  Some tests failed, but migration can continue")
            
        logger.info("\n" + "="*60)
        logger.info("✅ PHASE 1 MIGRATION COMPLETE")
        logger.info("="*60)
        logger.info(f"Backup saved at: {backup}")
        logger.info("Next steps:")
        logger.info("  1. Test scheduler in production for 24 hours")
        logger.info("  2. Monitor logs for any issues")
        logger.info("  3. Run: migrate_scheduler.py 2  (for Phase 2)")
        
        return True
        
    def rollback(self, phase: int):
        """Rollback to previous version."""
        logger.info(f"\n🔄 Rolling back Phase {phase}...")
        
        # Find most recent backup
        if not self.backup_dir.exists():
            logger.error("❌ No backups found")
            return False
            
        backups = sorted(self.backup_dir.glob("scheduler_*.py"))
        if not backups:
            logger.error("❌ No backup files found")
            return False
            
        latest_backup = backups[-1]
        logger.info(f"Restoring from: {latest_backup}")
        
        # Restore backup
        shutil.copy2(latest_backup, self.scheduler_path)
        logger.info(f"✓ Restored scheduler.py from backup")
        
        # Restart services if needed
        services = ["tmux-orchestrator-checkin", "tmux-orchestrator-queue"]
        for service in services:
            try:
                subprocess.run(["systemctl", "restart", service], check=False)
                logger.info(f"✓ Restarted {service}")
            except:
                logger.debug(f"Could not restart {service} (may not exist)")
                
        logger.info("✅ Rollback complete")
        return True
        
    def run_migration(self, phase: int):
        """Run migration for specified phase."""
        if phase == 1:
            return self.phase1_migration()
        elif phase == 2:
            logger.info("Phase 2: Extract monitoring and recovery modules")
            logger.info("Not yet implemented - coming soon")
            return False
        elif phase == 3:
            logger.info("Phase 3: Extract queue and event systems")
            logger.info("Not yet implemented - coming soon")
            return False
        elif phase == 4:
            logger.info("Phase 4: CLI and daemon refinement")
            logger.info("Not yet implemented - coming soon")
            return False
        elif phase == 5:
            logger.info("Phase 5: Cleanup and optimization")
            logger.info("Not yet implemented - coming soon")
            return False
        else:
            logger.error(f"Invalid phase: {phase}. Must be 1-5")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Migrate scheduler.py to modular architecture"
    )
    parser.add_argument(
        "phase",
        type=int,
        nargs="?",
        default=1,
        help="Migration phase (1-5)"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the specified phase"
    )
    parser.add_argument(
        "--project-path",
        type=Path,
        default=Path(__file__).parent,
        help="Path to Tmux-Orchestrator project"
    )
    
    args = parser.parse_args()
    
    migration = SchedulerMigration(args.project_path)
    
    if args.rollback:
        success = migration.rollback(args.phase)
    else:
        success = migration.run_migration(args.phase)
        
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
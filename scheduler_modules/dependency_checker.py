#!/usr/bin/env python3
"""
Dependency checker module extracted from scheduler.py
Ensures critical dependencies are available at runtime with auto-installation.
"""

import subprocess
import logging

logger = logging.getLogger(__name__)


class DependencyChecker:
    """Ensures critical dependencies are available at runtime with auto-installation."""
    
    @staticmethod
    def verify_psutil():
        """Verify psutil is available, auto-install if missing."""
        try:
            import psutil
            logger.info(f"✓ psutil verified: version {psutil.__version__}")
            return True
        except ImportError:
            logger.warning("⚠️  psutil missing - attempting auto-install")
            try:
                # Use uv to install psutil
                result = subprocess.run(['uv', 'pip', 'install', 'psutil>=5.9.0'], 
                                      check=True, capture_output=True, text=True)
                logger.info(f"✓ psutil installation output: {result.stdout}")
                
                # Verify installation worked
                import psutil
                logger.info(f"✓ psutil installed successfully: version {psutil.__version__}")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to install psutil via uv: {e}")
                logger.error(f"Command output: {e.stdout}")
                logger.error(f"Command error: {e.stderr}")
                return False
            except ImportError as e:
                logger.error(f"❌ psutil still unavailable after installation attempt: {e}")
                return False
            except Exception as e:
                logger.error(f"❌ Unexpected error during psutil installation: {e}")
                return False
    
    @staticmethod
    def verify_all_dependencies():
        """Verify all critical dependencies are available."""
        dependencies_ok = True
        
        if not DependencyChecker.verify_psutil():
            dependencies_ok = False
            
        return dependencies_ok
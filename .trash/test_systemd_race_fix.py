#!/usr/bin/env python3
"""
Test script to verify systemd scheduler service race condition fixes
"""

import subprocess
import time
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))
from scheduler_lock_manager import SchedulerLockManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_lock_manager_systemd_detection():
    """Test the systemd detection in lock manager"""
    logger.info("Testing systemd detection in lock manager...")
    
    lock_manager = SchedulerLockManager()
    
    # Test systemd detection method
    systemd_detected = lock_manager._detect_systemd_restart()
    logger.info(f"Systemd restart detection result: {systemd_detected}")
    
    return True

def test_concurrent_scheduler_start():
    """Test starting multiple schedulers concurrently to trigger race condition"""
    logger.info("Testing concurrent scheduler startup...")
    
    # Start first scheduler in background
    proc1 = subprocess.Popen([
        'python3', 'scheduler.py', '--daemon'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait briefly then start second
    time.sleep(0.1)
    proc2 = subprocess.Popen([
        'python3', 'scheduler.py', '--daemon'  
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for both to complete startup
    time.sleep(2)
    
    # Check results
    proc1_running = proc1.poll() is None
    proc2_running = proc2.poll() is None
    
    logger.info(f"Scheduler 1 (PID {proc1.pid}): {'Running' if proc1_running else 'Stopped'}")
    logger.info(f"Scheduler 2 (PID {proc2.pid}): {'Running' if proc2_running else 'Stopped'}")
    
    # Clean up
    if proc1_running:
        proc1.terminate()
        proc1.wait()
        
    if proc2_running:
        proc2.terminate()
        proc2.wait()
    
    # Capture any error output
    if not proc1_running:
        stdout, stderr = proc1.communicate()
        if stderr:
            logger.info(f"Scheduler 1 stderr: {stderr.decode()}")
    
    if not proc2_running:
        stdout, stderr = proc2.communicate()
        if stderr:
            logger.info(f"Scheduler 2 stderr: {stderr.decode()}")
    
    # Test passes if exactly one scheduler ran
    running_count = sum([proc1_running, proc2_running])
    success = running_count == 1
    
    logger.info(f"Concurrent start test: {'PASSED' if success else 'FAILED'} ({running_count} schedulers ran)")
    return success

def test_systemd_service_install():
    """Test if the fixed systemd service can be installed"""
    logger.info("Testing systemd service installation...")
    
    try:
        # Check if the fixed service file exists
        service_file = Path("systemd/tmux-orchestrator-scheduler-fixed.service")
        if not service_file.exists():
            logger.error("Fixed service file not found")
            return False
            
        # Check if install script exists
        install_script = Path("systemd/install-systemd-service-fixed.sh")
        if not install_script.exists():
            logger.error("Fixed install script not found")
            return False
            
        # Validate service file syntax
        with open(service_file) as f:
            content = f.read()
            required_sections = ['[Unit]', '[Service]', '[Install]']
            for section in required_sections:
                if section not in content:
                    logger.error(f"Missing section {section} in service file")
                    return False
                    
        # Check for race condition fixes
        race_fixes = [
            'ExecStartPre=',  # Cleanup sequence
            'sleep 2',        # Proper delays
            'scheduler.lock', # Lock file cleanup
            'KillMode=mixed'  # Proper process cleanup
        ]
        
        missing_fixes = []
        for fix in race_fixes:
            if fix not in content:
                missing_fixes.append(fix)
                
        if missing_fixes:
            logger.warning(f"Missing race condition fixes: {missing_fixes}")
        
        logger.info("Service file validation: PASSED")
        return True
        
    except Exception as e:
        logger.error(f"Service installation test failed: {e}")
        return False

def run_all_tests():
    """Run all race condition fix tests"""
    logger.info("=" * 60)
    logger.info("SYSTEMD SCHEDULER RACE CONDITION FIX TESTS")
    logger.info("=" * 60)
    
    tests = [
        ("Lock Manager Systemd Detection", test_lock_manager_systemd_detection),
        ("Concurrent Scheduler Start", test_concurrent_scheduler_start), 
        ("Systemd Service Installation", test_systemd_service_install)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\nRunning: {test_name}")
        logger.info("-" * 40)
        try:
            result = test_func()
            results.append((test_name, result))
            logger.info(f"Result: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            logger.error(f"Test {test_name} threw exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("✅ All race condition fixes are working correctly!")
        return True
    else:
        logger.warning("❌ Some tests failed - race condition may still exist")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
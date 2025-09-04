#!/usr/bin/env python3
"""
Configuration module extracted from scheduler.py
Centralizes all environment variable configuration and defaults.
"""

import os
from pathlib import Path


class SchedulerConfig:
    """Centralized configuration for the scheduler system."""
    
    # Database configuration
    DEFAULT_DB_PATH = 'task_queue.db'
    
    # Process timeouts and intervals
    POLL_INTERVAL_SEC = int(os.getenv('POLL_INTERVAL_SEC', 60))
    MAX_CONCURRENT_PROJECTS = int(os.getenv('MAX_CONCURRENT_PROJECTS', 1))
    MAX_AUTO_ORCHESTRATE_RUNTIME_SEC = int(os.getenv('MAX_AUTO_ORCHESTRATE_RUNTIME_SEC', 10800))  # 3 hours
    PROCESS_MONITOR_INTERVAL_SEC = int(os.getenv('PROCESS_MONITOR_INTERVAL_SEC', 30))
    
    # Phantom detection
    PHANTOM_GRACE_PERIOD_SEC = int(os.getenv('PHANTOM_GRACE_PERIOD_SEC', 1800))  # 30 min
    
    # State synchronization
    STATE_SYNC_INTERVAL_SEC = int(os.getenv('STATE_SYNC_INTERVAL_SEC', 600))  # 10 min
    
    # Orphaned session reconciliation
    ORPHANED_RECONCILE_INTERVAL_SEC = int(os.getenv('ORPHANED_RECONCILE_INTERVAL_SEC', 1800))  # 30 min
    
    # Reboot detection
    REBOOT_DETECTION_THRESHOLD_SEC = int(os.getenv('REBOOT_DETECTION_THRESHOLD_SEC', 900))  # 15 min
    
    # Email configuration
    EMAIL_ENABLED = os.getenv('EMAIL_NOTIFIER_ENABLED', 'false').lower() == 'true'
    SMTP_HOST = os.getenv('SMTP_HOST', 'localhost')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM = os.getenv('SMTP_FROM', 'scheduler@tmux-orchestrator.local')
    SMTP_TO = os.getenv('SMTP_TO', '').split(',') if os.getenv('SMTP_TO') else []
    
    # Batch processing
    BATCH_SUMMARY_INTERVAL_MIN = int(os.getenv('BATCH_SUMMARY_INTERVAL_MIN', 60))
    
    # Retry configuration
    DEFAULT_MAX_RETRIES = 3
    RETRY_DELAY_SEC = 60
    
    # Lock configuration
    LOCK_TIMEOUT_SEC = 30
    LOCK_DIR = 'locks'
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'scheduler.log')
    
    @classmethod
    def get_tmux_orchestrator_path(cls):
        """Get the Tmux Orchestrator installation path."""
        return Path(__file__).parent.parent
    
    @classmethod
    def get_all_config(cls):
        """Get all configuration as a dictionary."""
        return {
            key: value for key, value in cls.__dict__.items()
            if not key.startswith('_') and not callable(value)
        }
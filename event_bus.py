#!/usr/bin/env python3
"""
Event Bus for Tmux Orchestrator
Handles message routing with rate limiting and file logging.
No tmux send-keys - all monitoring to files.
"""

import queue
import threading
import time
import logging
import yaml
import json
import subprocess
from typing import Dict, List, Callable, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple leaky bucket rate limiter."""
    def __init__(self, max_events: int, period: int):
        self.max_events = max_events
        self.period = period
        self.events = []
        self.lock = threading.Lock()

    def allow(self) -> bool:
        with self.lock:
            now = time.time()
            # Remove events older than period
            self.events = [t for t in self.events if now - t < self.period]
            if len(self.events) < self.max_events:
                self.events.append(now)
                return True
            return False

class EventBus:
    def __init__(self, config_path: str = 'orchestrator_config.yaml'):
        self.config = self._load_config(config_path).get('event_bus', {})
        self.subscribers: Dict[str, List[Callable]] = {}  # event_type -> callbacks
        self.event_queue = queue.Queue(maxsize=self.config.get('queue_size', 100))
        self._stop = False
        self.lock = threading.Lock()
        self.rate_limiter = RateLimiter(
            self.config.get('rate_limit', 10),  # Default 10 events/min
            self.config.get('rate_period', 60)  # Default 60s period
        )
        self.log_dir = Path('logs/events')
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        logger.info("EventBus initialized with rate limit {}/{}s".format(
            self.rate_limiter.max_events, self.rate_limiter.period
        ))

    def _load_config(self, path: str) -> Dict:
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}  # Fallback to defaults

    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe a callback to an event type."""
        with self.lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            self.subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to '{event_type}'")

    def publish(self, event_type: str, data: Any, priority: str = 'normal') -> bool:
        """Publish an event if rate limit allows. Priority: 'critical' bypasses rate limit for urgent messages."""
        if priority != 'critical' and not self.rate_limiter.allow():
            logger.warning(f"Rate limit exceeded for '{event_type}' - event dropped")
            return False
        try:
            self.event_queue.put_nowait((event_type, data))
            self._log_event(event_type, data)
            logger.info(f"Published event '{event_type}'")
            return True
        except queue.Full:
            logger.error(f"Event queue full - dropped '{event_type}'")
            return False

    def _process_queue(self):
        """Worker thread to process queued events."""
        while not self._stop:
            try:
                event_type, data = self.event_queue.get(timeout=1)
                with self.lock:
                    callbacks = self.subscribers.get(event_type, [])
                    for callback in callbacks:
                        try:
                            callback(event_type, data)
                        except Exception as e:
                            logger.error(f"Callback error for '{event_type}': {e}")
                self.event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Queue processing error: {e}")

    def _log_event(self, event_type: str, data: Any):
        """Log event to daily JSONL file."""
        log_file = self.log_dir / f"{datetime.now().date()}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps({
                'timestamp': datetime.now().isoformat(),
                'type': event_type,
                'data': data
            }) + '\n')

    def shutdown(self):
        """Graceful shutdown."""
        self._stop = True
        self.worker_thread.join()
        logger.info("EventBus shut down")

# Example integration and usage (for testing/demonstration)
if __name__ == '__main__':
    # Setup basic logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Load config (assumes orchestrator_config.yaml exists)
    bus = EventBus()

    # Example subscriber: Logs critical events and selectively sends to tmux
    def handle_critical(event_type: str, data: Any):
        logger.critical(f"Critical event: {event_type} - {data}")
        if event_type == 'critical_violation' and data.get('severity') == 'high':
            # Selective tmux send for CRITICAL only (adheres to principles)
            target = data.get('target', 'orchestrator:0')
            msg = data.get('message', 'Critical violation detected!')
            subprocess.run(['./send-claude-message.sh', target, msg])

    bus.subscribe('violation', handle_critical)
    bus.subscribe('critical_violation', handle_critical)

    # Publish a test event (normal priority - rate limited)
    bus.publish('violation', {'severity': 'low', 'message': 'Minor issue'})

    # Publish critical (bypasses rate limit)
    bus.publish('critical_violation', {'severity': 'high', 'message': 'Major violation!'}, priority='critical')

    # Keep running for a bit to see the output
    time.sleep(2)

    # Shutdown
    bus.shutdown()
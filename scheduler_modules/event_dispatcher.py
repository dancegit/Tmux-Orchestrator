#!/usr/bin/env python3
"""
Event dispatcher module extracted from scheduler.py
Implements pub-sub pattern for system events.
"""

import logging
import threading
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class EventDispatcher:
    """Manages event subscriptions and dispatching."""
    
    def __init__(self, event_log_path: Optional[Path] = None):
        self.event_subscribers: Dict[str, List[Callable]] = {}
        self.event_lock = threading.Lock()
        self.processing_events = set()  # For re-entrance protection
        self.event_log_path = event_log_path
        self.event_history = []
        self.max_history = 1000  # Keep last N events
        
        # Pre-register common event types
        self._register_event_types()
        
    def _register_event_types(self):
        """Register common event types."""
        event_types = [
            'task_complete',
            'project_complete',
            'project_failed',
            'project_timeout',
            'phantom_detected',
            'reboot_recovery',
            'project_recovered',
            'batch_complete',
            'authorization_request',
            'authorization_response',
            'session_created',
            'session_destroyed',
            'state_transition',
            'error_occurred',
            'warning_raised'
        ]
        
        for event_type in event_types:
            self.event_subscribers.setdefault(event_type, [])
            
    def subscribe(self, event_type: str, callback: Callable[[Dict], None]) -> bool:
        """
        Subscribe to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event occurs
            
        Returns:
            True if subscription successful
        """
        try:
            with self.event_lock:
                if event_type not in self.event_subscribers:
                    self.event_subscribers[event_type] = []
                    
                if callback not in self.event_subscribers[event_type]:
                    self.event_subscribers[event_type].append(callback)
                    logger.debug(f"Subscribed {callback.__name__} to {event_type}")
                    return True
                else:
                    logger.debug(f"Callback {callback.__name__} already subscribed to {event_type}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error subscribing to {event_type}: {e}")
            return False
            
    def unsubscribe(self, event_type: str, callback: Callable) -> bool:
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            callback: Callback function to remove
            
        Returns:
            True if unsubscription successful
        """
        try:
            with self.event_lock:
                if event_type in self.event_subscribers:
                    if callback in self.event_subscribers[event_type]:
                        self.event_subscribers[event_type].remove(callback)
                        logger.debug(f"Unsubscribed {callback.__name__} from {event_type}")
                        return True
                        
            return False
            
        except Exception as e:
            logger.error(f"Error unsubscribing from {event_type}: {e}")
            return False
            
    def dispatch(self, event_type: str, data: Dict[str, Any]) -> int:
        """
        Dispatch an event to all subscribers.
        
        Args:
            event_type: Type of event
            data: Event data dictionary
            
        Returns:
            Number of subscribers notified
        """
        # Create event ID for re-entrance protection
        event_id = f"{event_type}_{id(data)}_{threading.get_ident()}"
        
        # Check for re-entrance
        with self.event_lock:
            if event_id in self.processing_events:
                logger.debug(f"Skipping re-entrant event: {event_type}")
                return 0
            self.processing_events.add(event_id)
            
        try:
            # Log event
            self._log_event(event_type, data)
            
            # Get subscribers
            with self.event_lock:
                subscribers = self.event_subscribers.get(event_type, []).copy()
                
            if not subscribers:
                logger.debug(f"No subscribers for event: {event_type}")
                return 0
                
            # Dispatch to each subscriber
            notified = 0
            for callback in subscribers:
                try:
                    logger.debug(f"Dispatching {event_type} to {callback.__name__}")
                    callback(data)
                    notified += 1
                except Exception as e:
                    logger.error(f"Error in event handler {callback.__name__} for {event_type}: {e}")
                    
            logger.info(f"Dispatched {event_type} to {notified} subscriber(s)")
            return notified
            
        finally:
            # Remove from processing set
            with self.event_lock:
                self.processing_events.discard(event_id)
                
    def dispatch_async(self, event_type: str, data: Dict[str, Any]):
        """
        Dispatch an event asynchronously in a separate thread.
        
        Args:
            event_type: Type of event
            data: Event data dictionary
        """
        thread = threading.Thread(
            target=self.dispatch,
            args=(event_type, data),
            daemon=True
        )
        thread.start()
        
    def _log_event(self, event_type: str, data: Dict[str, Any]):
        """Log event to history and optionally to file."""
        try:
            event_record = {
                'timestamp': datetime.now().isoformat(),
                'type': event_type,
                'data': data
            }
            
            # Add to history
            self.event_history.append(event_record)
            
            # Trim history if needed
            if len(self.event_history) > self.max_history:
                self.event_history = self.event_history[-self.max_history:]
                
            # Log to file if configured
            if self.event_log_path:
                try:
                    with open(self.event_log_path, 'a') as f:
                        f.write(json.dumps(event_record) + '\n')
                except Exception as e:
                    logger.debug(f"Could not write to event log: {e}")
                    
        except Exception as e:
            logger.error(f"Error logging event: {e}")
            
    def get_event_history(self, event_type: Optional[str] = None, 
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get event history.
        
        Args:
            event_type: Filter by event type (optional)
            limit: Maximum number of events to return
            
        Returns:
            List of event records
        """
        try:
            if event_type:
                filtered = [e for e in self.event_history if e['type'] == event_type]
            else:
                filtered = self.event_history
                
            return filtered[-limit:]
            
        except Exception as e:
            logger.error(f"Error getting event history: {e}")
            return []
            
    def clear_history(self):
        """Clear event history."""
        self.event_history = []
        logger.info("Event history cleared")
        
    def get_subscriber_count(self, event_type: Optional[str] = None) -> Dict[str, int]:
        """
        Get count of subscribers by event type.
        
        Args:
            event_type: Specific event type or None for all
            
        Returns:
            Dictionary of event types to subscriber counts
        """
        with self.event_lock:
            if event_type:
                count = len(self.event_subscribers.get(event_type, []))
                return {event_type: count}
            else:
                return {
                    evt: len(subs) 
                    for evt, subs in self.event_subscribers.items()
                }
                
    def emit_error(self, error_message: str, context: Optional[Dict] = None):
        """
        Convenience method to emit an error event.
        
        Args:
            error_message: Error message
            context: Optional context dictionary
        """
        data = {
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        }
        if context:
            data.update(context)
            
        self.dispatch('error_occurred', data)
        
    def emit_warning(self, warning_message: str, context: Optional[Dict] = None):
        """
        Convenience method to emit a warning event.
        
        Args:
            warning_message: Warning message
            context: Optional context dictionary
        """
        data = {
            'message': warning_message,
            'timestamp': datetime.now().isoformat()
        }
        if context:
            data.update(context)
            
        self.dispatch('warning_raised', data)
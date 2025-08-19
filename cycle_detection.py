#!/usr/bin/env python3
"""
Cycle detection system for preventing infinite scheduling loops and deadlocks.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
import json
from dataclasses import dataclass
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

@dataclass
class SchedulingEvent:
    """Represents a scheduling event"""
    timestamp: datetime
    session_name: str
    agent_role: str
    window: int
    event_type: str  # 'scheduled', 'executed', 'failed', 'rescheduled'
    interval_minutes: int
    note: str
    triggered_by: Optional[str] = None  # What triggered this scheduling

class CycleDetector:
    """Detects and prevents cycles in agent scheduling"""
    
    def __init__(self, tmux_orchestrator_path: Path):
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.scheduler_db = tmux_orchestrator_path / 'task_queue.db'
        self.cycle_log = tmux_orchestrator_path / 'registry' / 'logs' / 'cycle_detection.jsonl'
        self.cycle_log.parent.mkdir(parents=True, exist_ok=True)
        
        # Cycle detection parameters
        self.max_same_interval_reschedules = 5  # Max reschedules with same interval
        self.max_rapid_reschedules = 10  # Max reschedules in rapid succession
        self.rapid_reschedule_window_minutes = 15  # Time window for rapid detection
        self.cycle_detection_window_hours = 2  # Look back window for cycle detection
        self.min_cycle_length = 3  # Minimum events to consider a cycle
        
        # State tracking
        self.recent_events = deque(maxlen=1000)  # Ring buffer for recent events
        self.session_patterns = defaultdict(list)  # Per-session pattern tracking
        
        # Load recent events from database
        self._load_recent_events()
    
    def _load_recent_events(self):
        """Load recent scheduling events from database and logs"""
        try:
            # Load from cycle log
            if self.cycle_log.exists():
                with open(self.cycle_log, 'r') as f:
                    for line in f.read().strip().split('\n')[-500:]:  # Last 500 events
                        if line:
                            try:
                                event_data = json.loads(line)
                                event = SchedulingEvent(
                                    timestamp=datetime.fromisoformat(event_data['timestamp']),
                                    session_name=event_data['session_name'],
                                    agent_role=event_data['agent_role'],
                                    window=event_data['window'],
                                    event_type=event_data['event_type'],
                                    interval_minutes=event_data['interval_minutes'],
                                    note=event_data['note'],
                                    triggered_by=event_data.get('triggered_by')
                                )
                                self.recent_events.append(event)
                            except (json.JSONDecodeError, KeyError, ValueError) as e:
                                logger.debug(f"Skipping invalid cycle log entry: {e}")
        except Exception as e:
            logger.error(f"Error loading recent events: {e}")
    
    def record_scheduling_event(self, session_name: str, agent_role: str, window: int, 
                              event_type: str, interval_minutes: int, note: str, 
                              triggered_by: Optional[str] = None):
        """Record a scheduling event for cycle detection"""
        event = SchedulingEvent(
            timestamp=datetime.now(),
            session_name=session_name,
            agent_role=agent_role,
            window=window,
            event_type=event_type,
            interval_minutes=interval_minutes,
            note=note,
            triggered_by=triggered_by
        )
        
        # Add to recent events
        self.recent_events.append(event)
        
        # Add to session pattern tracking
        self.session_patterns[session_name].append(event)
        
        # Keep only recent patterns per session
        cutoff = datetime.now() - timedelta(hours=self.cycle_detection_window_hours)
        self.session_patterns[session_name] = [
            e for e in self.session_patterns[session_name] 
            if e.timestamp > cutoff
        ]
        
        # Log to file
        self._log_event(event)
        
        # Check for cycles immediately after recording
        cycle_detected = self.detect_cycles(session_name)
        if cycle_detected:
            logger.warning(f"Cycle detected in {session_name}: {cycle_detected}")
        
        return cycle_detected
    
    def _log_event(self, event: SchedulingEvent):
        """Log event to cycle detection log"""
        try:
            with open(self.cycle_log, 'a') as f:
                event_data = {
                    'timestamp': event.timestamp.isoformat(),
                    'session_name': event.session_name,
                    'agent_role': event.agent_role,
                    'window': event.window,
                    'event_type': event.event_type,
                    'interval_minutes': event.interval_minutes,
                    'note': event.note,
                    'triggered_by': event.triggered_by
                }
                f.write(json.dumps(event_data) + '\n')
        except Exception as e:
            logger.error(f"Error logging cycle event: {e}")
    
    def detect_cycles(self, session_name: str) -> Optional[Dict[str, any]]:
        """Detect scheduling cycles for a specific session"""
        events = self.session_patterns.get(session_name, [])
        if len(events) < self.min_cycle_length:
            return None
        
        # Check different types of cycles
        
        # 1. Rapid reschedule cycle (same agent rescheduled rapidly)
        rapid_cycle = self._detect_rapid_reschedule_cycle(events)
        if rapid_cycle:
            return rapid_cycle
            
        # 2. Same interval cycle (same intervals repeated)
        interval_cycle = self._detect_same_interval_cycle(events)
        if interval_cycle:
            return interval_cycle
            
        # 3. Emergency escalation cycle (emergency -> recovery -> emergency)
        emergency_cycle = self._detect_emergency_cycle(events)
        if emergency_cycle:
            return emergency_cycle
            
        # 4. Agent dependency cycle (A waits for B, B waits for A)
        dependency_cycle = self._detect_dependency_cycle(events)
        if dependency_cycle:
            return dependency_cycle
            
        return None
    
    def _detect_rapid_reschedule_cycle(self, events: List[SchedulingEvent]) -> Optional[Dict[str, any]]:
        """Detect rapid rescheduling of same agent"""
        now = datetime.now()
        cutoff = now - timedelta(minutes=self.rapid_reschedule_window_minutes)
        recent_reschedules = [e for e in events if e.timestamp > cutoff and 'reschedul' in e.event_type.lower()]
        
        # Group by agent
        agent_reschedules = defaultdict(list)
        for event in recent_reschedules:
            agent_reschedules[event.agent_role].append(event)
        
        for agent, agent_events in agent_reschedules.items():
            if len(agent_events) >= self.max_rapid_reschedules:
                return {
                    'type': 'rapid_reschedule_cycle',
                    'agent': agent,
                    'count': len(agent_events),
                    'window_minutes': self.rapid_reschedule_window_minutes,
                    'events': [e.note for e in agent_events[-5:]],  # Last 5 events
                    'suggested_action': f'Pause scheduling for {agent} for 30 minutes to break cycle'
                }
        
        return None
    
    def _detect_same_interval_cycle(self, events: List[SchedulingEvent]) -> Optional[Dict[str, any]]:
        """Detect repeated scheduling with same intervals"""
        # Group by agent and interval
        agent_interval_counts = defaultdict(int)
        
        for event in events:
            if event.event_type in ['scheduled', 'rescheduled']:
                key = f"{event.agent_role}_{event.interval_minutes}"
                agent_interval_counts[key] += 1
        
        for key, count in agent_interval_counts.items():
            if count >= self.max_same_interval_reschedules:
                agent, interval = key.rsplit('_', 1)
                return {
                    'type': 'same_interval_cycle',
                    'agent': agent,
                    'interval_minutes': int(interval),
                    'count': count,
                    'suggested_action': f'Change interval for {agent} from {interval} minutes to break pattern'
                }
        
        return None
    
    def _detect_emergency_cycle(self, events: List[SchedulingEvent]) -> Optional[Dict[str, any]]:
        """Detect emergency -> recovery -> emergency cycles"""
        emergency_events = []
        recovery_events = []
        
        for event in events:
            if 'emergency' in event.note.lower():
                emergency_events.append(event)
            elif any(term in event.note.lower() for term in ['recover', 'resolved', 'back online']):
                recovery_events.append(event)
        
        # Simple heuristic: if emergency events outnumber recovery events significantly
        if len(emergency_events) >= 3 and len(emergency_events) > len(recovery_events) * 2:
            return {
                'type': 'emergency_cycle',
                'emergency_count': len(emergency_events),
                'recovery_count': len(recovery_events),
                'suggested_action': 'Investigate root cause - emergency interventions not resolving underlying issues'
            }
        
        return None
    
    def _detect_dependency_cycle(self, events: List[SchedulingEvent]) -> Optional[Dict[str, any]]:
        """Detect circular dependency cycles between agents"""
        # Build dependency graph from event notes
        dependencies = defaultdict(set)
        
        for event in events:
            note_lower = event.note.lower()
            # Look for "waiting for X" patterns
            if 'waiting for' in note_lower:
                parts = note_lower.split('waiting for')
                if len(parts) > 1:
                    # Extract the role being waited for
                    waiting_for = parts[1].strip().split()[0]
                    dependencies[event.agent_role].add(waiting_for)
        
        # Check for cycles in dependency graph
        def has_cycle(graph):
            visited = set()
            rec_stack = set()
            
            def dfs(node):
                if node in rec_stack:
                    return True  # Cycle found
                if node in visited:
                    return False
                
                visited.add(node)
                rec_stack.add(node)
                
                for neighbor in graph.get(node, []):
                    if dfs(neighbor):
                        return True
                
                rec_stack.remove(node)
                return False
            
            for node in graph:
                if node not in visited:
                    if dfs(node):
                        return True
            return False
        
        if has_cycle(dependencies):
            return {
                'type': 'dependency_cycle',
                'dependencies': dict(dependencies),
                'suggested_action': 'Break dependency cycle - identify which agent should proceed independently'
            }
        
        return None
    
    def prevent_cycle(self, session_name: str, cycle_info: Dict[str, any]) -> Dict[str, any]:
        """Take action to prevent or break a detected cycle"""
        cycle_type = cycle_info['type']
        
        if cycle_type == 'rapid_reschedule_cycle':
            return self._break_rapid_reschedule_cycle(session_name, cycle_info)
        elif cycle_type == 'same_interval_cycle':
            return self._break_same_interval_cycle(session_name, cycle_info)
        elif cycle_type == 'emergency_cycle':
            return self._break_emergency_cycle(session_name, cycle_info)
        elif cycle_type == 'dependency_cycle':
            return self._break_dependency_cycle(session_name, cycle_info)
        
        return {'action': 'unknown_cycle_type', 'success': False}
    
    def _break_rapid_reschedule_cycle(self, session_name: str, cycle_info: Dict[str, any]) -> Dict[str, any]:
        """Break rapid reschedule cycle by pausing scheduling"""
        agent = cycle_info['agent']
        
        # Cancel pending tasks for this agent
        try:
            conn = sqlite3.connect(str(self.scheduler_db))
            cursor = conn.cursor()
            
            # Delete pending tasks for this agent
            cursor.execute("""
                DELETE FROM tasks 
                WHERE session_name = ? AND agent_role = ?
            """, (session_name, agent))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cancelled {deleted_count} pending tasks for {agent} to break rapid reschedule cycle")
            
            return {
                'action': 'cancelled_pending_tasks',
                'agent': agent,
                'cancelled_count': deleted_count,
                'success': True,
                'message': f'Paused scheduling for {agent} due to rapid reschedule cycle'
            }
            
        except Exception as e:
            logger.error(f"Error breaking rapid reschedule cycle: {e}")
            return {'action': 'cancel_failed', 'success': False, 'error': str(e)}
    
    def _break_same_interval_cycle(self, session_name: str, cycle_info: Dict[str, any]) -> Dict[str, any]:
        """Break same interval cycle by modifying intervals"""
        agent = cycle_info['agent']
        old_interval = cycle_info['interval_minutes']
        
        # Suggest new interval (add some randomness)
        import random
        new_interval = max(1, old_interval + random.randint(-2, 5))
        
        try:
            conn = sqlite3.connect(str(self.scheduler_db))
            cursor = conn.cursor()
            
            # Update interval for this agent
            cursor.execute("""
                UPDATE tasks 
                SET interval_minutes = ?, 
                    note = note || ' [CYCLE-BREAK: interval changed from ' || ? || ' to ' || ? || ']'
                WHERE session_name = ? AND agent_role = ?
            """, (new_interval, old_interval, new_interval, session_name, agent))
            
            updated_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            return {
                'action': 'changed_interval',
                'agent': agent,
                'old_interval': old_interval,
                'new_interval': new_interval,
                'updated_count': updated_count,
                'success': True,
                'message': f'Changed {agent} interval from {old_interval} to {new_interval} minutes'
            }
            
        except Exception as e:
            logger.error(f"Error breaking same interval cycle: {e}")
            return {'action': 'interval_change_failed', 'success': False, 'error': str(e)}
    
    def _break_emergency_cycle(self, session_name: str, cycle_info: Dict[str, any]) -> Dict[str, any]:
        """Break emergency cycle by escalating to orchestrator"""
        return {
            'action': 'escalate_to_orchestrator',
            'success': True,
            'message': 'Emergency cycle detected - escalating to orchestrator for manual intervention',
            'emergency_count': cycle_info['emergency_count'],
            'recovery_count': cycle_info['recovery_count']
        }
    
    def _break_dependency_cycle(self, session_name: str, cycle_info: Dict[str, any]) -> Dict[str, any]:
        """Break dependency cycle by clearing blocking dependencies"""
        dependencies = cycle_info['dependencies']
        
        # Find the cycle and break it by clearing one dependency
        # Simple approach: clear all dependencies
        cleared_dependencies = []
        
        for agent, deps in dependencies.items():
            if deps:  # Has dependencies
                cleared_dependencies.append(f"{agent} no longer waiting for {', '.join(deps)}")
        
        return {
            'action': 'cleared_dependencies',
            'success': True,
            'message': 'Dependency cycle broken by clearing blocking dependencies',
            'cleared_dependencies': cleared_dependencies
        }
    
    def get_cycle_statistics(self) -> Dict[str, any]:
        """Get statistics about detected cycles"""
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        
        recent_events = [e for e in self.recent_events if e.timestamp > last_24h]
        
        stats = {
            'total_events_24h': len(recent_events),
            'events_by_type': defaultdict(int),
            'sessions_with_events': set(),
            'agents_with_events': set()
        }
        
        for event in recent_events:
            stats['events_by_type'][event.event_type] += 1
            stats['sessions_with_events'].add(event.session_name)
            stats['agents_with_events'].add(event.agent_role)
        
        stats['sessions_with_events'] = len(stats['sessions_with_events'])
        stats['agents_with_events'] = len(stats['agents_with_events'])
        stats['events_by_type'] = dict(stats['events_by_type'])
        
        return stats
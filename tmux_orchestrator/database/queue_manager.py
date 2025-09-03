"""
Queue Manager Module

Handles task queuing, prioritization, and distributed work coordination
across multi-agent sessions.
"""

import json
import time
import uuid
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from rich.console import Console

console = Console()


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """
    Represents a task in the orchestration system.
    """
    id: str
    title: str
    description: str
    assigned_to: Optional[str]
    priority: TaskPriority
    status: TaskStatus
    created_at: float
    updated_at: float
    deadline: Optional[float] = None
    dependencies: List[str] = None
    metadata: Dict[str, Any] = None
    estimated_duration: Optional[int] = None  # in minutes
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for JSON serialization."""
        data = asdict(self)
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create task from dictionary."""
        data['priority'] = TaskPriority(data['priority'])
        data['status'] = TaskStatus(data['status'])
        return cls(**data)


class QueueManager:
    """
    Manages task queues for orchestration workflows.
    
    Features:
    - Task prioritization and scheduling
    - Agent workload balancing
    - Dependency tracking and resolution
    - Persistence across system restarts
    - Deadline monitoring and alerts
    """
    
    def __init__(self, tmux_orchestrator_path: Path):
        """
        Initialize queue manager.
        
        Args:
            tmux_orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.queue_dir = tmux_orchestrator_path / 'registry' / 'queues'
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory task storage
        self.tasks: Dict[str, Task] = {}
        self.agent_queues: Dict[str, List[str]] = {}  # agent -> task_ids
        self.global_queue: List[str] = []  # unassigned tasks
        
        # Load existing tasks
        self._load_tasks()
        
        # Task callbacks
        self.task_callbacks: Dict[str, List[Callable]] = {
            'on_task_created': [],
            'on_task_assigned': [],
            'on_task_completed': [],
            'on_task_failed': []
        }
    
    def create_task(self,
                   title: str,
                   description: str,
                   priority: TaskPriority = TaskPriority.MEDIUM,
                   assigned_to: Optional[str] = None,
                   deadline: Optional[float] = None,
                   dependencies: List[str] = None,
                   estimated_duration: Optional[int] = None,
                   metadata: Dict[str, Any] = None) -> str:
        """
        Create a new task.
        
        Args:
            title: Task title
            description: Detailed task description
            priority: Task priority level
            assigned_to: Agent role to assign task to
            deadline: Task deadline (Unix timestamp)
            dependencies: List of task IDs this task depends on
            estimated_duration: Estimated completion time in minutes
            metadata: Additional task metadata
            
        Returns:
            str: Task ID
        """
        task_id = str(uuid.uuid4())[:8]  # Short ID for readability
        current_time = time.time()
        
        task = Task(
            id=task_id,
            title=title,
            description=description,
            assigned_to=assigned_to,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=current_time,
            updated_at=current_time,
            deadline=deadline,
            dependencies=dependencies or [],
            metadata=metadata or {},
            estimated_duration=estimated_duration
        )
        
        self.tasks[task_id] = task
        
        # Add to appropriate queue
        if assigned_to:
            if assigned_to not in self.agent_queues:
                self.agent_queues[assigned_to] = []
            self.agent_queues[assigned_to].append(task_id)
        else:
            self.global_queue.append(task_id)
        
        # Sort queues by priority
        self._sort_queue_by_priority()
        
        # Persist changes
        self._save_tasks()
        
        # Trigger callbacks
        self._trigger_callbacks('on_task_created', task)
        
        console.print(f"[green]✅ Created task {task_id}: {title}[/green]")
        return task_id
    
    def assign_task(self, task_id: str, agent_role: str) -> bool:
        """
        Assign a task to an agent.
        
        Args:
            task_id: Task ID to assign
            agent_role: Agent role to assign to
            
        Returns:
            bool: True if assignment succeeded
        """
        if task_id not in self.tasks:
            console.print(f"[red]❌ Task {task_id} not found[/red]")
            return False
        
        task = self.tasks[task_id]
        
        # Remove from current queue
        if task.assigned_to:
            if task.assigned_to in self.agent_queues:
                try:
                    self.agent_queues[task.assigned_to].remove(task_id)
                except ValueError:
                    pass
        else:
            try:
                self.global_queue.remove(task_id)
            except ValueError:
                pass
        
        # Add to new agent queue
        if agent_role not in self.agent_queues:
            self.agent_queues[agent_role] = []
        
        self.agent_queues[agent_role].append(task_id)
        task.assigned_to = agent_role
        task.updated_at = time.time()
        
        # Sort queue by priority
        self._sort_agent_queue(agent_role)
        
        # Persist changes
        self._save_tasks()
        
        # Trigger callbacks
        self._trigger_callbacks('on_task_assigned', task)
        
        console.print(f"[green]✅ Assigned task {task_id} to {agent_role}[/green]")
        return True
    
    def start_task(self, task_id: str, agent_role: str) -> bool:
        """
        Mark a task as started by an agent.
        
        Args:
            task_id: Task ID
            agent_role: Agent starting the task
            
        Returns:
            bool: True if task was started successfully
        """
        if task_id not in self.tasks:
            console.print(f"[red]❌ Task {task_id} not found[/red]")
            return False
        
        task = self.tasks[task_id]
        
        if task.assigned_to != agent_role:
            console.print(f"[red]❌ Task {task_id} not assigned to {agent_role}[/red]")
            return False
        
        if task.status != TaskStatus.PENDING:
            console.print(f"[yellow]⚠️ Task {task_id} is already {task.status.value}[/yellow]")
            return False
        
        # Check dependencies
        if not self._are_dependencies_satisfied(task_id):
            console.print(f"[yellow]⚠️ Task {task_id} dependencies not satisfied[/yellow]")
            return False
        
        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = time.time()
        
        # Persist changes
        self._save_tasks()
        
        console.print(f"[blue]🔄 Started task {task_id}: {task.title}[/blue]")
        return True
    
    def complete_task(self, task_id: str, agent_role: str) -> bool:
        """
        Mark a task as completed.
        
        Args:
            task_id: Task ID
            agent_role: Agent completing the task
            
        Returns:
            bool: True if task was completed successfully
        """
        if task_id not in self.tasks:
            console.print(f"[red]❌ Task {task_id} not found[/red]")
            return False
        
        task = self.tasks[task_id]
        
        if task.assigned_to != agent_role:
            console.print(f"[red]❌ Task {task_id} not assigned to {agent_role}[/red]")
            return False
        
        task.status = TaskStatus.COMPLETED
        task.updated_at = time.time()
        
        # Remove from agent queue
        if agent_role in self.agent_queues:
            try:
                self.agent_queues[agent_role].remove(task_id)
            except ValueError:
                pass
        
        # Persist changes
        self._save_tasks()
        
        # Trigger callbacks
        self._trigger_callbacks('on_task_completed', task)
        
        console.print(f"[green]✅ Completed task {task_id}: {task.title}[/green]")
        return True
    
    def fail_task(self, task_id: str, reason: str = "") -> bool:
        """
        Mark a task as failed.
        
        Args:
            task_id: Task ID
            reason: Failure reason
            
        Returns:
            bool: True if task was marked as failed
        """
        if task_id not in self.tasks:
            console.print(f"[red]❌ Task {task_id} not found[/red]")
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.updated_at = time.time()
        task.metadata['failure_reason'] = reason
        
        # Persist changes
        self._save_tasks()
        
        # Trigger callbacks
        self._trigger_callbacks('on_task_failed', task)
        
        console.print(f"[red]❌ Failed task {task_id}: {reason}[/red]")
        return True
    
    def get_next_task(self, agent_role: str) -> Optional[Task]:
        """
        Get the next highest priority task for an agent.
        
        Args:
            agent_role: Agent role
            
        Returns:
            Optional[Task]: Next task or None if no tasks available
        """
        if agent_role not in self.agent_queues:
            return None
        
        agent_queue = self.agent_queues[agent_role]
        
        for task_id in agent_queue:
            task = self.tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                if self._are_dependencies_satisfied(task_id):
                    return task
        
        return None
    
    def get_agent_workload(self, agent_role: str) -> Dict[str, Any]:
        """
        Get workload statistics for an agent.
        
        Args:
            agent_role: Agent role
            
        Returns:
            Dict containing workload statistics
        """
        if agent_role not in self.agent_queues:
            return {
                'total_tasks': 0,
                'pending_tasks': 0,
                'in_progress_tasks': 0,
                'completed_tasks': 0,
                'estimated_workload_minutes': 0
            }
        
        agent_tasks = [self.tasks[tid] for tid in self.agent_queues[agent_role] 
                      if tid in self.tasks]
        
        stats = {
            'total_tasks': len(agent_tasks),
            'pending_tasks': len([t for t in agent_tasks if t.status == TaskStatus.PENDING]),
            'in_progress_tasks': len([t for t in agent_tasks if t.status == TaskStatus.IN_PROGRESS]),
            'completed_tasks': len([t for t in agent_tasks if t.status == TaskStatus.COMPLETED]),
            'failed_tasks': len([t for t in agent_tasks if t.status == TaskStatus.FAILED]),
            'estimated_workload_minutes': sum(
                t.estimated_duration for t in agent_tasks 
                if t.estimated_duration and t.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
            )
        }
        
        return stats
    
    def get_overdue_tasks(self) -> List[Task]:
        """
        Get list of overdue tasks.
        
        Returns:
            List of overdue tasks
        """
        current_time = time.time()
        overdue_tasks = []
        
        for task in self.tasks.values():
            if (task.deadline and 
                task.deadline < current_time and 
                task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]):
                overdue_tasks.append(task)
        
        return sorted(overdue_tasks, key=lambda t: t.deadline)
    
    def register_callback(self, event: str, callback: Callable) -> bool:
        """
        Register a callback for task events.
        
        Args:
            event: Event name (on_task_created, on_task_assigned, etc.)
            callback: Callback function
            
        Returns:
            bool: True if callback was registered
        """
        if event not in self.task_callbacks:
            console.print(f"[red]❌ Unknown event: {event}[/red]")
            return False
        
        self.task_callbacks[event].append(callback)
        return True
    
    def _are_dependencies_satisfied(self, task_id: str) -> bool:
        """Check if all task dependencies are satisfied."""
        task = self.tasks[task_id]
        
        for dep_id in task.dependencies:
            if dep_id not in self.tasks:
                return False
            
            dep_task = self.tasks[dep_id]
            if dep_task.status != TaskStatus.COMPLETED:
                return False
        
        return True
    
    def _sort_queue_by_priority(self):
        """Sort all queues by priority."""
        self.global_queue.sort(key=lambda tid: self.tasks[tid].priority.value, reverse=True)
        
        for agent_role in self.agent_queues:
            self._sort_agent_queue(agent_role)
    
    def _sort_agent_queue(self, agent_role: str):
        """Sort a specific agent's queue by priority."""
        if agent_role in self.agent_queues:
            self.agent_queues[agent_role].sort(
                key=lambda tid: (
                    self.tasks[tid].priority.value,
                    -self.tasks[tid].created_at  # Newer tasks first for same priority
                ),
                reverse=True
            )
    
    def _trigger_callbacks(self, event: str, task: Task):
        """Trigger callbacks for a specific event."""
        for callback in self.task_callbacks.get(event, []):
            try:
                callback(task)
            except Exception as e:
                console.print(f"[yellow]⚠️ Callback error for {event}: {e}[/yellow]")
    
    def _save_tasks(self):
        """Persist tasks to disk."""
        tasks_file = self.queue_dir / 'tasks.json'
        queues_file = self.queue_dir / 'queues.json'
        
        try:
            # Save tasks
            tasks_data = {tid: task.to_dict() for tid, task in self.tasks.items()}
            tasks_file.write_text(json.dumps(tasks_data, indent=2))
            
            # Save queue assignments
            queue_data = {
                'agent_queues': self.agent_queues,
                'global_queue': self.global_queue
            }
            queues_file.write_text(json.dumps(queue_data, indent=2))
            
        except Exception as e:
            console.print(f"[yellow]⚠️ Failed to save tasks: {e}[/yellow]")
    
    def _load_tasks(self):
        """Load tasks from disk."""
        tasks_file = self.queue_dir / 'tasks.json'
        queues_file = self.queue_dir / 'queues.json'
        
        try:
            # Load tasks
            if tasks_file.exists():
                tasks_data = json.loads(tasks_file.read_text())
                self.tasks = {tid: Task.from_dict(data) for tid, data in tasks_data.items()}
            
            # Load queue assignments
            if queues_file.exists():
                queue_data = json.loads(queues_file.read_text())
                self.agent_queues = queue_data.get('agent_queues', {})
                self.global_queue = queue_data.get('global_queue', [])
            
        except Exception as e:
            console.print(f"[yellow]⚠️ Failed to load tasks: {e}[/yellow]")
            # Initialize empty state
            self.tasks = {}
            self.agent_queues = {}
            self.global_queue = []
    
    def mark_project_complete(self, project_id: int, success: bool = True, 
                             error_message: Optional[str] = None,
                             session_name: Optional[str] = None) -> bool:
        """
        Mark a project as completed or failed in the scheduler database.
        
        This modular method replaces direct imports of TmuxOrchestratorScheduler
        and provides a clean interface for project completion callbacks.
        
        Args:
            project_id: Project ID to mark as complete
            success: True if project succeeded, False if failed
            error_message: Error message if failed
            session_name: Session name to record if available
            
        Returns:
            bool: True if update succeeded
        """
        try:
            # Connect to the scheduler database
            db_path = self.tmux_orchestrator_path / 'task_queue.db'
            
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()
                
                # Check current status to prevent re-marking
                cursor.execute("SELECT status, main_session FROM project_queue WHERE id = ?", (project_id,))
                row = cursor.fetchone()
                
                if row and row[0] in ('completed', 'failed'):
                    console.print(f"[yellow]Project {project_id} already marked as {row[0]}, skipping[/yellow]")
                    return True
                
                # Update project status
                status = 'completed' if success else 'failed'
                
                # Build update query based on available parameters
                if session_name:
                    cursor.execute("""
                        UPDATE project_queue 
                        SET status = ?, completed_at = strftime('%s', 'now'), 
                            error_message = ?, main_session = ?, session_name = ?
                        WHERE id = ?
                    """, (status, error_message, session_name, session_name, project_id))
                else:
                    cursor.execute("""
                        UPDATE project_queue 
                        SET status = ?, completed_at = strftime('%s', 'now'), error_message = ?
                        WHERE id = ?
                    """, (status, error_message, project_id))
                
                conn.commit()
                console.print(f"[green]✓ Project {project_id} marked as {status}[/green]")
                
                # Trigger completion callbacks if registered
                task_data = {
                    'project_id': project_id,
                    'status': status,
                    'session_name': session_name,
                    'error_message': error_message
                }
                self._trigger_project_callbacks('project_completed', task_data)
                
                return True
                
        except Exception as e:
            console.print(f"[red]❌ Failed to mark project {project_id} complete: {e}[/red]")
            return False
    
    def _trigger_project_callbacks(self, event: str, data: Dict[str, Any]):
        """Trigger registered callbacks for project events."""
        # Project callbacks are separate from task callbacks
        # For now, just log the event - callbacks can be added later if needed
        console.print(f"[blue]📢 Project event: {event} - {data.get('project_id', 'unknown')}[/blue]")
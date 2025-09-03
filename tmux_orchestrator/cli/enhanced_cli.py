"""
Enhanced CLI Module

Advanced command-line interface with rich output, interactive features,
and comprehensive orchestrator management commands.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.tree import Tree

console = Console()


class EnhancedCLI:
    """
    Enhanced command-line interface for Tmux Orchestrator.
    
    Features:
    - Rich console output with colors and formatting
    - Interactive prompts and confirmations
    - Progress indicators for long-running operations
    - Tabular data display
    - Command suggestions and help
    """
    
    def __init__(self, orchestrator_path: Path):
        """
        Initialize enhanced CLI.
        
        Args:
            orchestrator_path: Path to Tmux Orchestrator installation
        """
        self.orchestrator_path = orchestrator_path
        self.parser = self._create_argument_parser()
    
    def error(self, message: str) -> None:
        """Display error message."""
        console.print(f"[red]❌ {message}[/red]")
    
    def success(self, message: str) -> None:
        """Display success message."""
        console.print(f"[green]✅ {message}[/green]")
    
    def warning(self, message: str) -> None:
        """Display warning message."""
        console.print(f"[yellow]⚠️  {message}[/yellow]")
    
    def info(self, message: str) -> None:
        """Display info message."""
        console.print(f"[blue]ℹ️  {message}[/blue]")
    
    def debug(self, message: str) -> None:
        """Display debug message."""
        console.print(f"[dim]{message}[/dim]")
    
    def display_results(self, results: Dict[str, Any]) -> None:
        """Display results in a formatted way."""
        if isinstance(results, dict):
            for key, value in results.items():
                console.print(f"  [bold]{key}:[/bold] {value}")
    
    def run(self, args: Optional[List[str]] = None) -> int:
        """
        Run CLI with provided arguments.
        
        Args:
            args: Command-line arguments (defaults to sys.argv)
            
        Returns:
            Exit code (0 for success)
        """
        try:
            parsed_args = self.parser.parse_args(args)
            
            # Execute the appropriate command
            if hasattr(parsed_args, 'func'):
                return parsed_args.func(parsed_args)
            else:
                self.parser.print_help()
                return 1
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            return 130
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            return 1
    
    def _create_argument_parser(self) -> argparse.ArgumentParser:
        """Create argument parser with all commands."""
        parser = argparse.ArgumentParser(
            prog="tmux-orchestrator",
            description="Advanced multi-agent tmux session orchestration",
            epilog="Use 'tmux-orchestrator <command> --help' for command-specific help"
        )
        
        parser.add_argument(
            "--version", 
            action="version", 
            version="Tmux Orchestrator v2.0.0 (Modular)"
        )
        
        parser.add_argument(
            "--verbose", "-v",
            action="count",
            default=0,
            help="Increase verbosity (use -v, -vv, or -vvv)"
        )
        
        # Create subparsers for commands
        subparsers = parser.add_subparsers(
            title="commands",
            description="Available orchestrator commands",
            dest="command"
        )
        
        # Create orchestration command
        self._add_create_command(subparsers)
        
        # Resume orchestration command
        self._add_resume_command(subparsers)
        
        # Status commands
        self._add_status_commands(subparsers)
        
        # Agent management commands
        self._add_agent_commands(subparsers)
        
        # System management commands
        self._add_system_commands(subparsers)
        
        return parser
    
    def _add_create_command(self, subparsers) -> None:
        """Add create orchestration command."""
        create_parser = subparsers.add_parser(
            "create",
            help="Create new orchestration session",
            description="Create a new multi-agent orchestration session"
        )
        
        create_parser.add_argument(
            "--project", "-p",
            type=Path,
            required=True,
            help="Path to project directory"
        )
        
        create_parser.add_argument(
            "--spec", "-s",
            type=Path,
            required=True,
            help="Path to specification file"
        )
        
        create_parser.add_argument(
            "--team-config", "-t",
            type=Path,
            help="Path to team configuration file"
        )
        
        create_parser.add_argument(
            "--roles",
            nargs="+",
            help="Specific roles to deploy (overrides auto-detection)"
        )
        
        create_parser.add_argument(
            "--interactive", "-i",
            action="store_true",
            help="Interactive setup with prompts"
        )
        
        create_parser.set_defaults(func=self._cmd_create)
    
    def _add_resume_command(self, subparsers) -> None:
        """Add resume orchestration command."""
        resume_parser = subparsers.add_parser(
            "resume",
            help="Resume existing orchestration",
            description="Resume an existing orchestration session"
        )
        
        resume_parser.add_argument(
            "--project", "-p",
            type=Path,
            required=True,
            help="Path to project directory"
        )
        
        resume_parser.add_argument(
            "--force-restart",
            action="store_true",
            help="Force restart all agents"
        )
        
        resume_parser.add_argument(
            "--status-only",
            action="store_true",
            help="Show status without resuming"
        )
        
        resume_parser.set_defaults(func=self._cmd_resume)
    
    def _add_status_commands(self, subparsers) -> None:
        """Add status monitoring commands."""
        status_parser = subparsers.add_parser(
            "status",
            help="Show orchestration status",
            description="Display comprehensive orchestration status"
        )
        
        status_subparsers = status_parser.add_subparsers(dest="status_type")
        
        # System status
        sys_status = status_subparsers.add_parser("system", help="System health status")
        sys_status.set_defaults(func=self._cmd_status_system)
        
        # Session status
        session_status = status_subparsers.add_parser("sessions", help="Active sessions status")
        session_status.set_defaults(func=self._cmd_status_sessions)
        
        # Agent status
        agent_status = status_subparsers.add_parser("agents", help="Agent health status")
        agent_status.add_argument("--session", help="Specific session name")
        agent_status.set_defaults(func=self._cmd_status_agents)
        
        # Default status command
        status_parser.set_defaults(func=self._cmd_status_overview)
    
    def _add_agent_commands(self, subparsers) -> None:
        """Add agent management commands."""
        agent_parser = subparsers.add_parser(
            "agent",
            help="Agent management",
            description="Manage orchestrator agents"
        )
        
        agent_subparsers = agent_parser.add_subparsers(dest="agent_action")
        
        # List agents
        list_agents = agent_subparsers.add_parser("list", help="List all agents")
        list_agents.add_argument("--session", help="Filter by session")
        list_agents.set_defaults(func=self._cmd_agent_list)
        
        # Restart agent
        restart_agent = agent_subparsers.add_parser("restart", help="Restart specific agent")
        restart_agent.add_argument("session", help="Session name")
        restart_agent.add_argument("role", help="Agent role")
        restart_agent.set_defaults(func=self._cmd_agent_restart)
        
        # Send message to agent
        message_agent = agent_subparsers.add_parser("message", help="Send message to agent")
        message_agent.add_argument("target", help="Target (session:role)")
        message_agent.add_argument("message", help="Message to send")
        message_agent.set_defaults(func=self._cmd_agent_message)
    
    def _add_system_commands(self, subparsers) -> None:
        """Add system management commands."""
        system_parser = subparsers.add_parser(
            "system",
            help="System management",
            description="System-level orchestrator management"
        )
        
        system_subparsers = system_parser.add_subparsers(dest="system_action")
        
        # Cleanup command
        cleanup_sys = system_subparsers.add_parser("cleanup", help="Clean up system resources")
        cleanup_sys.add_argument("--force", action="store_true", help="Force cleanup")
        cleanup_sys.set_defaults(func=self._cmd_system_cleanup)
        
        # Health check command
        health_sys = system_subparsers.add_parser("health", help="System health check")
        health_sys.set_defaults(func=self._cmd_system_health)
        
        # Configuration command
        config_sys = system_subparsers.add_parser("config", help="Manage configuration")
        config_sys.add_argument("--list", action="store_true", help="List configurations")
        config_sys.add_argument("--edit", help="Edit specific configuration")
        config_sys.set_defaults(func=self._cmd_system_config)
    
    def _cmd_create(self, args) -> int:
        """Handle create orchestration command."""
        console.print(Panel.fit(
            "[bold blue]Creating New Orchestration[/bold blue]",
            border_style="blue"
        ))
        
        try:
            # Import orchestrator here to avoid circular imports
            from ..core.orchestrator import Orchestrator
            
            orchestrator = Orchestrator()
            
            # Interactive mode
            if args.interactive:
                return self._interactive_create(orchestrator, args)
            
            # Direct creation
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Creating orchestration...", total=None)
                
                success = orchestrator.create_project_orchestration(
                    project_path=args.project,
                    spec_file=args.spec,
                    team_config=self._load_team_config(args.team_config) if args.team_config else None
                )
                
                progress.remove_task(task)
            
            if success:
                console.print("[green]✅ Orchestration created successfully[/green]")
                return 0
            else:
                console.print("[red]❌ Failed to create orchestration[/red]")
                return 1
                
        except Exception as e:
            console.print(f"[red]❌ Error creating orchestration: {e}[/red]")
            return 1
    
    def _cmd_resume(self, args) -> int:
        """Handle resume orchestration command."""
        console.print(Panel.fit(
            "[bold yellow]Resuming Orchestration[/bold yellow]",
            border_style="yellow"
        ))
        
        try:
            from ..core.orchestrator import Orchestrator
            
            orchestrator = Orchestrator()
            
            if args.status_only:
                # Show status only
                return self._show_resume_status(orchestrator, args.project)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Resuming orchestration...", total=None)
                
                success = orchestrator.resume_project_orchestration(args.project)
                
                progress.remove_task(task)
            
            if success:
                console.print("[green]✅ Orchestration resumed successfully[/green]")
                return 0
            else:
                console.print("[red]❌ Failed to resume orchestration[/red]")
                return 1
                
        except Exception as e:
            console.print(f"[red]❌ Error resuming orchestration: {e}[/red]")
            return 1
    
    def _cmd_status_overview(self, args) -> int:
        """Handle status overview command."""
        console.print(Panel.fit(
            "[bold cyan]Orchestration Status Overview[/bold cyan]",
            border_style="cyan"
        ))
        
        try:
            from ..monitoring.health_monitor import HealthMonitor
            
            monitor = HealthMonitor(self.orchestrator_path)
            health_summary = monitor.get_system_health_summary()
            
            # Create status table
            table = Table(title="System Status")
            table.add_column("Component", style="bold")
            table.add_column("Status", justify="center")
            table.add_column("Details")
            
            # System status row
            status_color = {
                "healthy": "green",
                "warning": "yellow", 
                "critical": "red",
                "unknown": "dim"
            }.get(health_summary["overall_status"], "dim")
            
            table.add_row(
                "System",
                f"[{status_color}]{health_summary['overall_status'].upper()}[/{status_color}]",
                f"CPU: {health_summary['system_metrics']['cpu_percent']:.1f}%, "
                f"Memory: {health_summary['system_metrics']['memory_percent']:.1f}%"
            )
            
            # Agents status row
            agent_summary = health_summary["agent_summary"]
            agent_color = "green" if agent_summary["unresponsive_agents"] == 0 else "yellow"
            
            table.add_row(
                "Agents",
                f"[{agent_color}]{agent_summary['responsive_agents']}/{agent_summary['total_agents']}[/{agent_color}]",
                f"Responsive: {agent_summary['responsive_agents']}, "
                f"Unresponsive: {agent_summary['unresponsive_agents']}"
            )
            
            # Tmux sessions row
            sessions_count = health_summary["tmux_sessions"]
            table.add_row(
                "Sessions",
                f"[blue]{sessions_count}[/blue]",
                f"{sessions_count} active tmux session(s)"
            )
            
            # Alerts row
            alerts_count = health_summary["active_alerts"]
            alert_color = "green" if alerts_count == 0 else "red"
            
            table.add_row(
                "Alerts",
                f"[{alert_color}]{alerts_count}[/{alert_color}]",
                f"{alerts_count} active alert(s)"
            )
            
            console.print(table)
            return 0
            
        except Exception as e:
            console.print(f"[red]❌ Error getting status: {e}[/red]")
            return 1
    
    def _cmd_status_system(self, args) -> int:
        """Handle system status command."""
        console.print("[cyan]System Health Status[/cyan]")
        
        try:
            from ..monitoring.health_monitor import HealthMonitor
            
            monitor = HealthMonitor(self.orchestrator_path)
            current_metrics = monitor.collect_system_metrics()
            
            # System metrics table
            table = Table(title="System Metrics")
            table.add_column("Metric", style="bold")
            table.add_column("Current", justify="right")
            table.add_column("Status", justify="center")
            
            # CPU
            cpu_status = "🟢" if current_metrics.cpu_percent < 80 else "🟡" if current_metrics.cpu_percent < 95 else "🔴"
            table.add_row("CPU Usage", f"{current_metrics.cpu_percent:.1f}%", cpu_status)
            
            # Memory
            mem_status = "🟢" if current_metrics.memory_percent < 85 else "🟡" if current_metrics.memory_percent < 95 else "🔴"
            table.add_row("Memory Usage", f"{current_metrics.memory_percent:.1f}%", mem_status)
            
            # Disk
            disk_status = "🟢" if current_metrics.disk_percent < 85 else "🟡" if current_metrics.disk_percent < 95 else "🔴"
            table.add_row("Disk Usage", f"{current_metrics.disk_percent:.1f}%", disk_status)
            
            # Load Average
            load_avg = current_metrics.load_average[0]
            load_status = "🟢" if load_avg < 5.0 else "🟡" if load_avg < 10.0 else "🔴"
            table.add_row("Load Average", f"{load_avg:.2f}", load_status)
            
            # Process Count
            table.add_row("Processes", str(current_metrics.process_count), "🟢")
            
            # Tmux Sessions
            table.add_row("Tmux Sessions", str(current_metrics.tmux_session_count), "🟢")
            
            console.print(table)
            return 0
            
        except Exception as e:
            console.print(f"[red]❌ Error getting system status: {e}[/red]")
            return 1
    
    def _cmd_status_sessions(self, args) -> int:
        """Handle sessions status command."""
        console.print("[cyan]Active Sessions Status[/cyan]")
        
        try:
            from ..tmux.session_controller import TmuxSessionController
            
            controller = TmuxSessionController(self.orchestrator_path)
            sessions = controller.list_sessions()
            
            if not sessions:
                console.print("[yellow]No active tmux sessions found[/yellow]")
                return 0
            
            # Sessions table
            table = Table(title="Active Tmux Sessions")
            table.add_column("Session Name", style="bold")
            table.add_column("Status", justify="center")
            table.add_column("Created")
            table.add_column("Last Attached")
            
            for session in sessions:
                status_color = "green" if session["status"] == "attached" else "yellow"
                table.add_row(
                    session["name"],
                    f"[{status_color}]{session['status']}[/{status_color}]",
                    session["created"],
                    session["last_attached"]
                )
            
            console.print(table)
            return 0
            
        except Exception as e:
            console.print(f"[red]❌ Error getting sessions status: {e}[/red]")
            return 1
    
    def _cmd_status_agents(self, args) -> int:
        """Handle agents status command."""
        console.print("[cyan]Agent Health Status[/cyan]")
        # Implementation would check agent health across sessions
        console.print("[yellow]Agent status functionality not yet implemented in modular system[/yellow]")
        return 0
    
    def _cmd_agent_list(self, args) -> int:
        """Handle agent list command."""
        console.print("[cyan]Agent List[/cyan]")
        console.print("[yellow]Agent management functionality not yet implemented in modular system[/yellow]")
        return 0
    
    def _cmd_agent_restart(self, args) -> int:
        """Handle agent restart command."""
        console.print(f"[cyan]Restarting agent {args.role} in session {args.session}[/cyan]")
        console.print("[yellow]Agent restart functionality not yet implemented in modular system[/yellow]")
        return 0
    
    def _cmd_agent_message(self, args) -> int:
        """Handle agent message command."""
        console.print(f"[cyan]Sending message to {args.target}[/cyan]")
        
        try:
            from ..tmux.messaging import TmuxMessenger
            
            messenger = TmuxMessenger(self.orchestrator_path)
            success = messenger.send_message(args.target, args.message)
            
            if success:
                console.print("[green]✅ Message sent successfully[/green]")
                return 0
            else:
                console.print("[red]❌ Failed to send message[/red]")
                return 1
                
        except Exception as e:
            console.print(f"[red]❌ Error sending message: {e}[/red]")
            return 1
    
    def _cmd_system_cleanup(self, args) -> int:
        """Handle system cleanup command."""
        console.print("[cyan]System Cleanup[/cyan]")
        
        if not args.force and not Confirm.ask("Are you sure you want to clean up system resources?"):
            console.print("[yellow]Cleanup cancelled[/yellow]")
            return 0
        
        try:
            from ..utils.file_utils import FileUtils
            
            # Clean temp files
            temp_dir = self.orchestrator_path / 'temp'
            if temp_dir.exists():
                FileUtils.clean_directory(temp_dir, keep_patterns=['*.keep'])
            
            # Clean old logs
            logs_dir = self.orchestrator_path / 'registry' / 'logs'
            if logs_dir.exists():
                from ..utils.system_utils import SystemUtils
                SystemUtils.cleanup_temp_files(logs_dir, max_age_hours=168)  # 1 week
            
            console.print("[green]✅ System cleanup completed[/green]")
            return 0
            
        except Exception as e:
            console.print(f"[red]❌ Error during cleanup: {e}[/red]")
            return 1
    
    def _cmd_system_health(self, args) -> int:
        """Handle system health command."""
        return self._cmd_status_system(args)
    
    def _cmd_system_config(self, args) -> int:
        """Handle system config command."""
        console.print("[cyan]System Configuration[/cyan]")
        console.print("[yellow]Configuration management functionality not yet implemented in modular system[/yellow]")
        return 0
    
    def _interactive_create(self, orchestrator, args) -> int:
        """Handle interactive orchestration creation."""
        console.print("[bold]Interactive Orchestration Setup[/bold]")
        
        # Project path
        if not args.project:
            project_input = Prompt.ask("Enter project path")
            args.project = Path(project_input)
        
        # Spec file
        if not args.spec:
            spec_input = Prompt.ask("Enter specification file path")
            args.spec = Path(spec_input)
        
        # Validate inputs
        if not args.project.exists():
            console.print(f"[red]❌ Project path does not exist: {args.project}[/red]")
            return 1
        
        if not args.spec.exists():
            console.print(f"[red]❌ Spec file does not exist: {args.spec}[/red]")
            return 1
        
        # Confirmation
        console.print(f"[green]✅ Project: {args.project}[/green]")
        console.print(f"[green]✅ Spec: {args.spec}[/green]")
        
        if not Confirm.ask("Proceed with orchestration creation?"):
            console.print("[yellow]Creation cancelled[/yellow]")
            return 0
        
        # Create orchestration
        success = orchestrator.create_project_orchestration(
            project_path=args.project,
            spec_file=args.spec
        )
        
        if success:
            console.print("[green]✅ Interactive orchestration created successfully[/green]")
            return 0
        else:
            console.print("[red]❌ Failed to create orchestration[/red]")
            return 1
    
    def _show_resume_status(self, orchestrator, project_path: Path) -> int:
        """Show resume status without actually resuming."""
        console.print(f"[cyan]Resume Status for {project_path}[/cyan]")
        console.print("[yellow]Resume status functionality not yet implemented in modular system[/yellow]")
        return 0
    
    def _load_team_config(self, config_path: Path) -> Optional[Dict[str, Any]]:
        """Load team configuration file."""
        try:
            from ..utils.file_utils import FileUtils
            
            if config_path.suffix.lower() == '.json':
                return FileUtils.read_json(config_path)
            elif config_path.suffix.lower() in ['.yaml', '.yml']:
                return FileUtils.read_yaml(config_path)
            else:
                console.print(f"[red]❌ Unsupported config format: {config_path.suffix}[/red]")
                return None
                
        except Exception as e:
            console.print(f"[red]❌ Error loading team config: {e}[/red]")
            return None
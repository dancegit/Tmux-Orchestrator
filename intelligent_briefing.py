#!/usr/bin/env python3
"""
Intelligent briefing system for Tmux Orchestrator.
Creates meaningful, context-rich check-in messages for stuck agents.
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from session_state import SessionStateManager, SessionState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntelligentBriefingSystem:
    """Creates context-rich, actionable check-in messages for agents"""
    
    def __init__(self, tmux_orchestrator_path: Path):
        self.tmux_orchestrator_path = tmux_orchestrator_path
        self.state_manager = SessionStateManager(tmux_orchestrator_path)
        
    def load_implementation_spec(self, session_name: str) -> Optional[Dict]:
        """Load the implementation spec for a project"""
        try:
            # Find the implementation spec file
            registry_dir = self.tmux_orchestrator_path / 'registry' / 'projects'
            for proj_dir in registry_dir.iterdir():
                if proj_dir.is_dir():
                    state_file = proj_dir / 'session_state.json'
                    if state_file.exists():
                        state_data = json.loads(state_file.read_text())
                        if state_data.get('session_name') == session_name:
                            spec_path = state_data.get('implementation_spec_path')
                            if spec_path and Path(spec_path).exists():
                                return json.loads(Path(spec_path).read_text())
            return None
        except Exception as e:
            logger.error(f"Error loading implementation spec: {e}")
            return None
    
    def get_project_status(self, session_name: str, spec: Dict) -> Dict:
        """Analyze current project status and progress"""
        try:
            phases = spec.get('implementation_plan', {}).get('phases', [])
            total_phases = len(phases)
            
            # For now, estimate progress based on time elapsed
            # In a real system, this would check actual completion markers
            elapsed_hours = 2  # Placeholder - could calculate from session start time
            total_hours = spec.get('implementation_plan', {}).get('total_estimated_hours', 26)
            progress_percent = min(int((elapsed_hours / total_hours) * 100), 20)  # Cap at 20% for early stage
            
            current_phase = phases[0] if phases else {}
            next_tasks = current_phase.get('tasks', [])[:3]  # Next 3 tasks
            
            return {
                'progress_percent': progress_percent,
                'current_phase': current_phase.get('name', 'Phase 1'),
                'total_phases': total_phases,
                'next_tasks': next_tasks,
                'estimated_completion': f"{total_hours - elapsed_hours} hours remaining"
            }
        except Exception as e:
            logger.error(f"Error analyzing project status: {e}")
            return {
                'progress_percent': 5,
                'current_phase': 'Initial Development',
                'total_phases': 5,
                'next_tasks': ['Start development', 'Review requirements'],
                'estimated_completion': 'TBD'
            }
    
    def create_orchestrator_briefing(self, session_name: str, spec: Dict, status: Dict) -> str:
        """Create a comprehensive briefing for the orchestrator"""
        project_name = spec.get('project', {}).get('name', 'Project')
        
        return f"""🚨 ORCHESTRATOR EMERGENCY BRIEFING: Project coordination needed immediately!

**PROJECT CONTEXT: {project_name}**
Goal: Implement active event delivery architecture for SignalMatrix using Modal, Python, and Valkey/Redis
Status: {status['progress_percent']}% complete - Currently in {status['current_phase']}
Tech Stack: Modal, Python, FastAPI, asyncio, Valkey/Redis

**YOUR ROLE AS ORCHESTRATOR**: 
You coordinate the entire team across {status['total_phases']} phases of development. Monitor progress, resolve blockers, and ensure quality delivery of the event router system.

**CURRENT SITUATION ANALYSIS**:
The team appears stuck - all agents are idle at Claude prompts. This suggests either:
1. Initial briefings were unclear or lost
2. Agents need specific task assignments
3. Technical blockers preventing progress
4. Lack of clear next steps

**IMMEDIATE ACTION REQUIRED**:

1. **ASSESS TEAM STATUS** (Next 5 minutes):
   - Check which agents are responsive: Use these commands in your tool directory:
     cd ~/Tmux-Orchestrator && ./send-monitored-message.sh {session_name}:1 "PM: Report current status and blockers immediately"
     cd ~/Tmux-Orchestrator && ./send-monitored-message.sh {session_name}:5 "Developer: What are you working on right now?"
   
2. **ASSIGN IMMEDIATE TASKS** (Next 10 minutes):
   Phase 1 Priority Tasks:
   - Developer: Start creating event_router.py with EventRouter class
   - SysAdmin: Verify Modal environment and Valkey access
   - DevOps: Check deployment configuration for Modal

3. **COORDINATE WORKFLOW** (Next 15 minutes):
   - Schedule regular 30-minute team check-ins
   - Set up git workflow on branch: feature/event-router-implementation  
   - Ensure all agents have proper project directory access

**SUCCESS CRITERIA FOR THIS SESSION**:
- Event router monitoring loop implemented
- Modal decorators properly configured
- Basic event processing pipeline functional
- Team coordination restored with clear task assignments

**TOOLS AVAILABLE IN YOUR DIRECTORY**:
- ./send-monitored-message.sh - Send messages to specific agents
- ./schedule_with_note.sh - Schedule regular check-ins
- python3 claude_control.py status detailed - Check overall system status

**ESCALATION**: If any agent doesn't respond within 10 minutes, they may need manual intervention or restart.

START IMMEDIATELY: Message the PM and Developer now to get status updates, then coordinate the next steps!"""

    def create_role_specific_briefing(self, role: str, session_name: str, spec: Dict, status: Dict) -> str:
        """Create role-specific briefing messages"""
        
        project_name = spec.get('project', {}).get('name', 'Project')
        role_config = spec.get('roles', {}).get(role, {})
        responsibilities = role_config.get('responsibilities', [])
        
        base_context = f"""🚨 EMERGENCY BRIEFING: {role.upper()} - Project needs your immediate attention!

**PROJECT: {project_name}**
Goal: Build active event delivery system with Modal, Python, Valkey/Redis
Progress: {status['progress_percent']}% - {status['current_phase']}
Your Role: {', '.join(responsibilities)}

**SITUATION**: Project appears stalled - all team members idle. Time to get back on track!"""

        if role == 'project_manager':
            return f"""{base_context}

**YOUR RESPONSIBILITIES AS PM**:
- Ensure quality and track completion across {status['total_phases']} development phases
- Coordinate between Orchestrator, Developer, SysAdmin, DevOps, SecurityOps teams
- Maintain high standards for event router implementation

**IMMEDIATE TASKS** (Next 30 minutes):
1. **Status Assessment**: Read the project spec to understand requirements
   cd /home/clauderun/signalmatrix/signalmatrix_org/signalmatrix-slice-slice-deployment
   cat SPEC_EVENT_DELIVERY_ARCHITECTURE.md

2. **Team Coordination**: Report to Orchestrator on current blockers and progress
   Identify which team members need task assignments

3. **Quality Planning**: Review Phase 1 requirements for event router implementation:
   - EventRouter class with Modal decorators  
   - Monitoring loop with PluginRegistry integration
   - Feature flags for EVENT_ROUTER_ENABLED

**NEXT STEPS**: Message the Orchestrator with your assessment and recommend immediate task assignments for the development team.

**SUCCESS METRIC**: Team actively working on Phase 1 tasks within 20 minutes."""

        elif role == 'developer':
            return f"""{base_context}

**YOUR RESPONSIBILITIES AS DEVELOPER**:
- Implement the core event router system using Modal and Python
- Write tests and ensure code quality
- Work with SysAdmin/DevOps for deployment integration

**IMMEDIATE CODING TASKS** (Start NOW):
1. **Set up development environment**:
   cd /home/clauderun/signalmatrix/signalmatrix_org/signalmatrix-slice-slice-deployment
   git status
   git checkout feature/event-delivery-architecture
   
2. **Begin Phase 1 Implementation** - Create event_router.py:
   - EventRouter class with Modal decorators (@modal.web_endpoint, @modal.asgi_app)
   - Monitoring loop that discovers streams from PluginRegistry
   - Mix in EventDeliveryMixin for delivery capabilities
   
3. **Key Technical Requirements**:
   - Use Modal for container management (min_containers=1)
   - Integrate with PersistentEventBusHybrid for stream access
   - Implement feature flags: EVENT_ROUTER_ENABLED, ACTIVE_DELIVERY_ENABLED

**CURRENT PRIORITY**: Start with the basic EventRouter class structure. Aim for initial implementation within 1 hour.

**RESOURCES**: 
- Check existing event bus code for integration patterns
- Review Modal documentation for decorator usage
- Coordinate with SysAdmin for Valkey/Redis connection details

**REPORT PROGRESS**: Message PM every 30 minutes with specific code commits and progress updates."""

        elif role == 'sysadmin':
            return f"""{base_context}

**YOUR RESPONSIBILITIES AS SYSADMIN**:
- System setup for Modal deployment environment
- User management and service configuration  
- Package management for Python/Modal requirements

**IMMEDIATE INFRASTRUCTURE TASKS**:
1. **Verify System Requirements**:
   cd /home/clauderun/signalmatrix/signalmatrix_org/signalmatrix-slice-slice-deployment
   Check Modal CLI and credentials are configured
   Verify Valkey/Redis access and connectivity
   
2. **Environment Setup**:
   - Confirm Python environment with Modal dependencies
   - Check system permissions for deployment
   - Verify network access to required services
   
3. **Support Developer Needs**:
   - Ensure development environment is fully configured
   - Assist with Modal secrets setup for Valkey connections
   - Monitor system resources during development

**SUCCESS CRITERIA**: Developer can successfully run Modal commands and connect to Valkey within 30 minutes.

**COORDINATE WITH**: DevOps for deployment pipeline and Developer for environment requirements."""

        elif role == 'devops':
            return f"""{base_context}

**YOUR RESPONSIBILITIES AS DEVOPS**:
- Infrastructure setup and deployment pipelines
- Monitor performance and deployment configuration
- Modal deployment optimization

**IMMEDIATE INFRASTRUCTURE TASKS**:
1. **Review Deployment Configuration**:
   cd /home/clauderun/signalmatrix/signalmatrix_org/signalmatrix-slice-slice-deployment
   Check Modal deployment scripts and configuration
   
2. **Pipeline Preparation**:
   - Ensure Modal secrets are properly configured
   - Verify deployment environment settings
   - Check cost optimization settings (min_containers=1)
   
3. **Coordinate with Development**:
   - Support Developer with Modal integration questions
   - Prepare for event router deployment to test environment
   - Monitor resource usage during development

**SUCCESS CRITERIA**: Deployment pipeline ready for event router testing within 45 minutes.

**FOCUS**: Get the Modal deployment environment production-ready for the event router service."""

        elif role == 'securityops':
            return f"""{base_context}

**YOUR RESPONSIBILITIES AS SECURITYOPS**:
- Security hardening for Modal deployment
- Access control and firewall configuration
- Secure handling of Valkey/Redis connections

**IMMEDIATE SECURITY TASKS**:
1. **Security Assessment**:
   cd /home/clauderun/signalmatrix/signalmatrix_org/signalmatrix-slice-slice-deployment
   Review security requirements for event router
   
2. **Access Control Setup**:
   - Configure secure access to Valkey/Redis
   - Review Modal secrets management
   - Ensure proper authentication for event streams
   
3. **Security Hardening**:
   - Check firewall rules for required ports
   - Verify SSL/TLS configuration for external connections
   - Review security implications of event delivery system

**SUCCESS CRITERIA**: Security framework in place for safe event router deployment.

**COORDINATE WITH**: SysAdmin for system access and DevOps for deployment security."""

        elif role == 'tester':
            return f"""{base_context}

**YOUR RESPONSIBILITIES AS TESTER**:
- Create test plans for event router functionality
- Run tests and report failures with clear reproduction steps
- Verify Phase 1 success criteria are met

**IMMEDIATE TESTING TASKS**:
1. **Test Planning**:
   cd /home/clauderun/signalmatrix/signalmatrix_org/signalmatrix-slice-slice-deployment
   Review Phase 1 requirements for test case creation
   
2. **Prepare Test Environment**:
   - Set up test data for event streams
   - Prepare mock PluginRegistry for testing
   - Create test scenarios for event delivery
   
3. **Define Success Criteria Verification**:
   - 95% events processed within 10 seconds
   - 99.9% delivery success rate
   - Proper retry and DLQ handling

**SUCCESS CRITERIA**: Test framework ready for Phase 1 validation within 1 hour.

**COORDINATE WITH**: Developer for testable code delivery and PM for quality standards."""

        else:
            # Generic briefing for other roles
            return f"""{base_context}

**YOUR ROLE**: {', '.join(responsibilities)}

**IMMEDIATE ACTION NEEDED**:
1. Check your project directory and understand current requirements
2. Review your specific responsibilities in the implementation spec
3. Identify what you should be working on right now
4. Report status to the Project Manager or Orchestrator

**PROJECT DIRECTORY**: 
cd /home/clauderun/signalmatrix/signalmatrix_org/signalmatrix-slice-slice-deployment

**NEXT STEP**: Take immediate action on your role's responsibilities and coordinate with the team."""

    def send_intelligent_briefing(self, session_name: str, role: str, window_index: int):
        """Send an intelligent briefing to a specific agent"""
        try:
            # Load project context
            spec = self.load_implementation_spec(session_name)
            if not spec:
                logger.error(f"Could not load implementation spec for {session_name}")
                return False
            
            # Get project status
            status = self.get_project_status(session_name, spec)
            
            # Create appropriate briefing
            if role == 'orchestrator':
                message = self.create_orchestrator_briefing(session_name, spec, status)
            else:
                message = self.create_role_specific_briefing(role, session_name, spec, status)
            
            # Send the message
            send_script = self.tmux_orchestrator_path / 'send-claude-message.sh'
            if send_script.exists():
                result = subprocess.run([
                    str(send_script),
                    f"{session_name}:{window_index}",
                    message
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"Intelligent briefing sent to {role} (window {window_index})")
                    return True
                else:
                    logger.error(f"Failed to send briefing: {result.stderr}")
                    return False
            else:
                logger.error("send-claude-message.sh not found")
                return False
                
        except Exception as e:
            logger.error(f"Error sending intelligent briefing: {e}")
            return False

def main():
    """Main entry point for intelligent briefing system"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Send intelligent briefings to agents')
    parser.add_argument('session_name', help='Session name')
    parser.add_argument('role', help='Agent role')
    parser.add_argument('window_index', type=int, help='Window index')
    
    args = parser.parse_args()
    
    briefing_system = IntelligentBriefingSystem(Path(__file__).parent)
    success = briefing_system.send_intelligent_briefing(
        args.session_name, 
        args.role, 
        args.window_index
    )
    
    if success:
        print(f"Successfully sent intelligent briefing to {args.role}")
    else:
        print(f"Failed to send briefing to {args.role}")
        exit(1)

if __name__ == '__main__':
    main()
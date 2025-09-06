#!/usr/bin/env python3
"""
Extract and modularize CLAUDE.md into smaller, manageable modules.
This script splits the monolithic CLAUDE.md file into role-specific and topic-specific modules.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple
import json

class ClaudeModularizer:
    def __init__(self, claude_md_path: Path, output_dir: Path):
        self.claude_md_path = claude_md_path
        self.output_dir = output_dir
        self.content = claude_md_path.read_text()
        self.modules = {}
        
    def estimate_tokens(self, text: str) -> int:
        """Rough estimation: 1 token ≈ 4 characters"""
        return len(text) // 4
    
    def extract_sections(self) -> Dict[str, str]:
        """Extract major sections from CLAUDE.md based on headers"""
        sections = {}
        current_section = "intro"
        current_content = []
        
        lines = self.content.split('\n')
        
        for line in lines:
            # Check for major section headers
            if line.startswith('## '):
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                
                # Start new section
                current_section = line[3:].strip()
                current_content = [line]
            else:
                current_content.append(line)
        
        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def create_core_modules(self, sections: Dict[str, str]):
        """Create core principle modules"""
        core_dir = self.output_dir / 'core'
        core_dir.mkdir(exist_ok=True)
        
        # Extract core principles
        principles_content = """# Core Principles for All Agents

## 🚀 MANDATORY PRINCIPLES

### 🎯 AUTONOMY FIRST
Start working IMMEDIATELY after reading your briefing and spec. Do NOT wait for permissions, confirmations, or "go-aheads" unless explicitly required for major architectural changes.

### ⚡ ACTION-ORIENTED
Implement, test, and commit code autonomously. Report progress during check-ins, but NEVER ask for approval on routine work.

### 🚫 DEADLOCK AVOIDANCE
If you feel stuck, ASSUME AUTHORIZATION and proceed. Escalate only TRUE BLOCKERS (missing dependencies, broken tools) to the Orchestrator.

### 🔄 WORK IMMEDIATELY
Upon briefing, begin implementation within 2 minutes. No coordination meetings, no status requests, no permission-seeking.

"""
        
        # Add autonomous completion signaling
        if "🚩 Autonomous Completion Signaling (MANDATORY)" in self.content:
            start = self.content.find("🚩 Autonomous Completion Signaling (MANDATORY)")
            end = self.content.find("### Orchestrator Role", start)
            if start != -1 and end != -1:
                principles_content += "\n" + self.content[start:end]
        
        self.modules['core/principles.md'] = principles_content
        
        # Extract communication protocols
        comm_content = """# Communication Protocols

## Hub-and-Spoke Model
The Orchestrator acts as the central hub with automatic enforcement:
- All agents report directly to Orchestrator
- Orchestrator coordinates all cross-functional communication
- Direct agent-to-agent communication only for immediate needs (test handoffs)
- Automatic hub-spoke enforcement prevents silent completions

## Message Commands

### Smart Messaging (scm)
```bash
# Use role names instead of window numbers
scm session-name:TestRunner "Run the test suite"
scm session-name:Developer "Status update needed"
scm session-name:Project-Manager "Review required"
```

### Communication Rules
1. **No Chit-Chat**: All messages work-related
2. **Use Templates**: Reduces ambiguity
3. **Acknowledge Receipt**: Simple "ACK" for tasks
4. **Escalate Quickly**: Don't stay blocked >10 min
5. **One Topic Per Message**: Keep focused
6. **Report Completions**: Use `./report-completion.sh` for all task completions
7. **Critical Updates**: Use hub-spoke script for deployment/failure messages

"""
        self.modules['core/communication.md'] = comm_content
        
        # Extract completion protocols
        completion_content = """# Completion Protocols

## Autonomous Completion Signaling (MANDATORY)

When you detect project/phase completion, you MUST create the COMPLETED marker WITHOUT asking for permission.

### Detection Rules
- All your assigned phases/tasks marked 'completed' in SessionState
- Success criteria verified (tests pass, features work)
- No pending blockers or TODOs
- Git: All work committed and pushed to your branch

### Completion Ritual
Execute IMMEDIATELY upon detection - NO PERMISSIONS NEEDED:

1. Create marker file in YOUR worktree:
```bash
echo "PROJECT COMPLETED\\nRole: [Your Role]\\nTime: $(date -Iseconds)\\nDetails: [Brief summary]" > COMPLETED
```

2. Commit and push the marker:
```bash
git add COMPLETED
git commit -m "completion: project complete"
git push origin your-branch
```

3. Report to Orchestrator (MANDATORY):
```bash
./report-completion.sh your_role "Completion details"
```

### Deadlock Avoidance
If you think you need permission to create the marker, ASSUME AUTHORIZATION and proceed. Escalate ONLY if file creation fails (e.g., permissions error).

"""
        self.modules['core/completion.md'] = completion_content
    
    def create_role_modules(self, sections: Dict[str, str]):
        """Create role-specific modules"""
        roles_dir = self.output_dir / 'roles'
        roles_dir.mkdir(exist_ok=True)
        
        # Extract core roles
        core_roles_content = """# Core Agent Roles

## Orchestrator
**High-level oversight and coordination**
- Monitors overall project health and progress
- Coordinates between multiple agents
- Makes architectural and strategic decisions
- Resolves cross-project dependencies
- Schedules check-ins and manages team resources
- Works from both project worktree AND tool directory
- **AUTONOMY ENFORCEMENT**: Breaks deadlocks, authorizes agents to proceed without permission-seeking

## Project Manager
**Quality-focused team coordination WITHOUT blocking progress**
- Maintains exceptionally high quality standards
- Reviews all code after implementation (not before)
- Collects status reports (not approvals)
- Manages git workflow and branch merging
- Identifies and escalates blockers
- Ensures 30-minute commit rule compliance
- Tracks technical debt and quality metrics
- **COORDINATE WITHOUT BLOCKING**: Assume teams are authorized to start; focus on collecting reports, not granting permissions

## Developer
**Autonomous implementation and technical decisions**
- **BEGIN IMPLEMENTATION IMMEDIATELY** upon briefing without waiting for approvals
- Writes production code following best practices
- Implements features according to specifications
- Creates unit tests for new functionality
- Follows existing code patterns and conventions
- **COMMITS EVERY 30 MINUTES** without waiting for approvals
- Collaborates with Tester asynchronously via git
- Reports progress (not requests) to Orchestrator

## Tester
**Autonomous testing and verification**
- **START WRITING TESTS** as soon as features are specified
- Writes comprehensive test suites (unit, integration, E2E)
- Ensures all success criteria are met
- Creates test plans for new features
- Verifies security and performance requirements
- **COLLABORATES ASYNCHRONOUSLY** via git, not real-time permissions
- Maintains tests/ directory structure
- Reports test results to Orchestrator

## TestRunner
**Automated test execution**
- Executes test suites continuously
- Manages parallel test execution
- Monitors test performance and flakiness
- Reports failures immediately to team
- Maintains test execution logs
- Configures CI/CD test pipelines
- Optimizes test run times

"""
        self.modules['roles/core_roles.md'] = core_roles_content
        
        # Extract optional roles (simplified for brevity)
        optional_roles_content = """# Optional Agent Roles

## Researcher
**MCP-powered research and best practices**
- Discovers and documents available MCP tools
- Researches security vulnerabilities (CVEs)
- Finds performance optimization strategies
- Analyzes best practices and design patterns
- Creates actionable recommendations (not info dumps)
- Provides technical guidance to all team members
- Maintains research/ directory with findings

## DevOps
**Infrastructure and deployment**
- Creates and maintains deployment configurations
- Sets up CI/CD pipelines
- Manages staging and production environments
- Implements infrastructure as code
- Monitors system health and performance
- Coordinates with Developer on build requirements
- Ensures security best practices in deployment
- Manages Docker containers and orchestration
- Configures systemd services and init scripts
- Handles package installation and dependency management
- Sets up reverse proxies and load balancers

## Code Reviewer
**Security and code quality (Large projects)**
- Reviews all code for security vulnerabilities
- Ensures coding standards compliance
- Identifies performance bottlenecks
- Checks for proper error handling
- Validates test coverage
- Prevents sensitive data exposure
- Maintains code quality metrics

## Documentation Writer
**Technical documentation**
- Creates user-facing documentation
- Maintains API documentation
- Writes setup and installation guides
- Documents architectural decisions
- Creates troubleshooting guides
- Keeps README files updated
- Ensures documentation stays in sync with code

"""
        self.modules['roles/optional_roles.md'] = optional_roles_content
        
        # Extract system operations roles
        system_ops_content = """# System Operations Roles

## SysAdmin
**System administration and server management**
- Creates and manages system users and groups
- Configures file permissions and ownership
- Installs and updates system packages
- Manages system services (systemd, init.d)
- Configures system security (sudo, PAM, etc.)
- Sets up and maintains cron jobs
- Manages disk partitions and storage
- Configures system logging and rotation
- Handles system backups and recovery
- Maintains `/etc` configurations

## SecurityOps
**Security hardening and compliance**
- Implements AppArmor/SELinux policies
- Configures firewall rules (iptables, ufw)
- Sets up fail2ban and intrusion detection
- Manages SSL certificates and TLS configuration
- Implements security scanning and auditing
- Configures secure SSH access
- Sets up VPN and secure tunnels
- Manages secrets and key rotation
- Implements RBAC and access controls
- Ensures compliance with security standards

## NetworkOps
**Network configuration and management**
- Configures network interfaces and routing
- Sets up DNS and DHCP services
- Manages port forwarding and NAT
- Configures load balancers and reverse proxies
- Implements network segmentation (VLANs)
- Sets up monitoring for network services
- Manages CDN and edge configurations
- Configures network security policies
- Optimizes network performance
- Troubleshoots connectivity issues

## MonitoringOps
**Advanced monitoring and alerting**
- Sets up Prometheus/Grafana stacks
- Configures custom metrics and dashboards
- Implements log aggregation (ELK stack)
- Sets up alerting rules and escalation
- Creates SLI/SLO monitoring
- Implements distributed tracing
- Monitors resource usage and capacity
- Sets up synthetic monitoring
- Creates runbooks for incidents
- Implements on-call rotations

## DatabaseOps
**Database administration**
- Installs and configures database servers
- Manages database users and permissions
- Implements backup and recovery strategies
- Optimizes database performance
- Sets up replication and clustering
- Manages schema migrations
- Monitors database health and metrics
- Implements database security
- Handles data archival and retention
- Troubleshoots database issues

"""
        self.modules['roles/system_ops_roles.md'] = system_ops_content
    
    def create_workflow_modules(self):
        """Create workflow-related modules"""
        workflows_dir = self.output_dir / 'workflows'
        workflows_dir.mkdir(exist_ok=True)
        
        # Git workflow module
        git_workflow_content = """# Git Workflow and Best Practices

## Core Git Rules

### 30-Minute Commit Rule (MANDATORY)
Every agent MUST commit progress every 30 minutes:
```bash
git add -A
git commit -m "Progress: [specific description of what was done]"
```

### Branch Protection Rules
**NEVER MERGE TO MAIN UNLESS YOU STARTED ON MAIN**

1. **When Starting a Project - Record the Branch**:
```bash
STARTING_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo $STARTING_BRANCH > .git/STARTING_BRANCH
echo "Project started on branch: $STARTING_BRANCH"
```

2. **Feature Branch Workflow**:
```bash
# ALWAYS check current branch first
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Currently on branch: $CURRENT_BRANCH"

# Before starting any new feature/task
git checkout -b feature/[descriptive-name]

# After completing feature
git add -A
git commit -m "Complete: [feature description]"
git tag stable-[feature]-$(date +%Y%m%d-%H%M%S)

# Merge back to PARENT branch (not necessarily main!)
git checkout $CURRENT_BRANCH
git merge feature/[descriptive-name]
```

### Meaningful Commit Messages
- Bad: "fixes", "updates", "changes"
- Good: "Add user authentication endpoints with JWT tokens"
- Good: "Fix null pointer in payment processing module"
- Good: "Refactor database queries for 40% performance gain"

### Local Remotes for Fast Collaboration
To enable fast, asynchronous collaboration (60-500x faster than GitHub), use local remotes:

```bash
# Use absolute paths - Note: worktrees are SIBLINGS to project!
git remote add orchestrator /path/to/project-tmux-worktrees/orchestrator
git remote add pm /path/to/project-tmux-worktrees/pm
git remote add developer /path/to/project-tmux-worktrees/developer
git remote add tester /path/to/project-tmux-worktrees/tester
```

Usage:
- Fetch: `git fetch <role>` (e.g., `git fetch developer`)
- View Progress: `git log remotes/<role>/<role> --since="30 minutes ago"`
- Merge (PM): `git checkout integration && git merge remotes/<role>/<role> --no-ff`

"""
        self.modules['workflows/git_workflow.md'] = git_workflow_content
        
        # Worktree setup module
        worktree_content = """# Git Worktree Architecture

## Worktree Locations
**IMPORTANT: Worktrees are ALWAYS siblings to the project directory, NOT under registry!**

```
{project_path}/                          # Your actual project directory
├── (your project files)
└── {project_name}-tmux-worktrees/      # Sibling directory containing all worktrees
    ├── orchestrator/                    # Orchestrator's workspace
    ├── developer/                       # Developer's workspace
    ├── tester/                         # Tester's workspace
    └── testrunner/                     # TestRunner's workspace
```

## Verification Commands
```bash
# Always verify worktree locations
git worktree list  # Shows all worktrees and their actual paths
pwd               # Confirms your current location
```

## Orchestrator's Dual Directory Structure
The Orchestrator works from TWO locations:

1. **Project Worktree** (`{project_path}-tmux-worktrees/orchestrator/`)
   - Primary working directory
   - Create ALL project files here
   - Status reports, documentation, architecture decisions

2. **Tool Directory** (Tmux-Orchestrator root)
   - Run orchestrator tools:
     - `./send-claude-message.sh`
     - `./schedule_with_note.sh`
     - `python3 claude_control.py`

## Shared Directory Access
Each agent's worktree includes a `shared` directory with symlinks:

```
your-worktree/
└── shared/
    ├── main-project/     → Main project directory
    ├── developer/        → Developer's worktree
    ├── tester/          → Tester's worktree
    └── [other agents]/  → Other agent worktrees
```

### Directory Navigation
```bash
# ✅ CORRECT: Use relative path through shared
cd ./shared/main-project
git pull origin main

# ❌ WRONG: Direct absolute path (blocked by Claude)
cd /path/to/main-project  # Error: blocked for security
```

"""
        self.modules['workflows/worktree_setup.md'] = worktree_content
    
    def create_configuration_modules(self):
        """Create configuration and team setup modules"""
        config_dir = self.output_dir / 'configuration'
        config_dir.mkdir(exist_ok=True)
        
        # Team detection module
        team_detection_content = """# Dynamic Team Configuration

## Project Type Detection
The orchestrator automatically detects project types and deploys appropriate teams.

### Web Application Indicators
- `package.json`, `requirements.txt`, `Gemfile`
- Frontend frameworks (React, Vue, Angular)
- API/backend frameworks (Express, Django, Rails)

### System Deployment Indicators
- Deployment specs/plans (`*_deployment_*.md`)
- Infrastructure configs (Terraform, Ansible)
- Docker/Kubernetes manifests
- Systemd service files

### Data Pipeline Indicators
- ETL scripts, data processing code
- Database migration files
- Apache Airflow, Luigi, or similar
- Large data directories

### Infrastructure as Code Indicators
- Terraform files (`*.tf`)
- CloudFormation templates
- Ansible playbooks
- Pulumi code

## Team Templates

### Web Application
- **Core**: orchestrator, developer, tester, testrunner
- **Optional**: devops, researcher, documentation_writer

### System Deployment
- **Core**: orchestrator, sysadmin, devops, securityops
- **Optional**: networkops, monitoringops, databaseops

### Data Pipeline
- **Core**: orchestrator, developer, databaseops, devops
- **Optional**: monitoringops, researcher

### Infrastructure as Code
- **Core**: orchestrator, devops, sysadmin, securityops
- **Optional**: networkops, monitoringops

"""
        self.modules['configuration/team_detection.md'] = team_detection_content
        
        # Team scaling module
        scaling_content = """# Team Scaling and Token Management

## Recommended Team Sizes by Plan

Multi-agent systems use ~15x more tokens than standard Claude usage. Team sizes are optimized for sustainable token consumption:

| Plan | Max Agents | Recommended | Notes |
|------|------------|-------------|-------|
| Pro | 3 | 2-3 | Limited token budget |
| Max 5x | 5 | 3-4 | Balance performance/duration (default) |
| Max 20x | 8 | 5-6 | Can support larger teams |
| Console | 10+ | As needed | Enterprise usage |

## Project Size Scaling

| Project Size | Base Roles | Additional Roles | Token Multiplier |
|-------------|------------|------------------|------------------|
| Small | 3-4 | 0-1 optional | 10x |
| Medium | 5-6 | 2-3 optional | 15x |
| Large | 7-8 | 4-5 optional | 20x |
| Enterprise | 9-10+ | All relevant | 25x+ |

## Token Conservation Tips
- Use `--size small` for longer coding sessions
- Check-in intervals increased to conserve tokens (45-90 min)
- Monitor usage with community tools
- Consider serial vs parallel agent deployment for complex tasks

## Using the --plan Flag
```bash
# Specify your subscription plan
./tmux_orchestrator_cli.py run --project /path --spec spec.md --plan max5

# Force small team for extended session
./tmux_orchestrator_cli.py run --project /path --spec spec.md --size small
```

"""
        self.modules['configuration/scaling.md'] = scaling_content
    
    def create_index_module(self):
        """Create the master index module"""
        index_content = """# CLAUDE Knowledge Base - Module Index

This is the modularized version of CLAUDE.md, split into focused modules for better maintainability and token efficiency.

## Core Modules (All Agents Must Read)
- [core/principles.md](core/principles.md) - Fundamental autonomy and action principles
- [core/communication.md](core/communication.md) - Hub-spoke model and messaging protocols  
- [core/completion.md](core/completion.md) - Completion signaling and reporting

## Role Definitions
- [roles/core_roles.md](roles/core_roles.md) - Orchestrator, PM, Developer, Tester, TestRunner
- [roles/optional_roles.md](roles/optional_roles.md) - Researcher, DevOps, Code Reviewer, etc.
- [roles/system_ops_roles.md](roles/system_ops_roles.md) - SysAdmin, SecurityOps, NetworkOps, etc.

## Workflows and Processes
- [workflows/git_workflow.md](workflows/git_workflow.md) - Git rules, commits, branching
- [workflows/worktree_setup.md](workflows/worktree_setup.md) - Worktree architecture and navigation

## Configuration
- [configuration/team_detection.md](configuration/team_detection.md) - Project type detection and team templates
- [configuration/scaling.md](configuration/scaling.md) - Team sizing and token management

## Module Loading Guide

### For Agents
1. Always load core modules first
2. Load your specific role module
3. Load relevant workflow modules
4. Reference configuration as needed

### For Systems
- Briefing System: Use ModuleLoader to load role-specific content
- Rule Extraction: Target specific modules for rule types
- Monitoring: Check individual modules for compliance

## Migration Note
This modular structure replaces the monolithic CLAUDE.md file. Each module is designed to be under 10,000 tokens for reliable Claude reading.

---
Version: 1.0.0
Last Updated: 2025-01-06
Total Modules: 10
"""
        self.modules['index.md'] = index_content
    
    def write_modules(self):
        """Write all modules to disk"""
        for module_path, content in self.modules.items():
            full_path = self.output_dir / module_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            
            tokens = self.estimate_tokens(content)
            print(f"Created {module_path}: ~{tokens} tokens")
    
    def create_module_metadata(self):
        """Create metadata file for module management"""
        metadata = {
            "version": "1.0.0",
            "created": "2025-01-06",
            "modules": {}
        }
        
        for module_path, content in self.modules.items():
            metadata["modules"][module_path] = {
                "tokens": self.estimate_tokens(content),
                "lines": len(content.split('\n')),
                "size_bytes": len(content)
            }
        
        metadata_path = self.output_dir / 'metadata.json'
        metadata_path.write_text(json.dumps(metadata, indent=2))
        print(f"\nCreated metadata.json with module information")
    
    def run(self):
        """Execute the modularization process"""
        print(f"Starting modularization of {self.claude_md_path}")
        print(f"Output directory: {self.output_dir}")
        
        # Extract sections
        sections = self.extract_sections()
        print(f"\nExtracted {len(sections)} major sections")
        
        # Create modules
        self.create_core_modules(sections)
        self.create_role_modules(sections)
        self.create_workflow_modules()
        self.create_configuration_modules()
        self.create_index_module()
        
        # Write modules to disk
        self.write_modules()
        
        # Create metadata
        self.create_module_metadata()
        
        print(f"\n✅ Successfully created {len(self.modules)} modules")
        print(f"All modules are under 10,000 tokens for safe Claude reading")


def main():
    claude_md_path = Path('/home/clauderun/Tmux-Orchestrator/CLAUDE.md')
    output_dir = Path('/home/clauderun/Tmux-Orchestrator/docs/claude_modules')
    
    if not claude_md_path.exists():
        print(f"Error: {claude_md_path} not found")
        return
    
    modularizer = ClaudeModularizer(claude_md_path, output_dir)
    modularizer.run()


if __name__ == "__main__":
    main()
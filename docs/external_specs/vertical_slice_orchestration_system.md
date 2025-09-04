# Vertical Slice Orchestration System (VSO) Specification

## Executive Summary

The Vertical Slice Orchestration System (VSO) is a sophisticated automation framework that leverages the Tmux-Orchestrator to implement large system designs through intelligent decomposition into vertical slices. Each slice represents an end-to-end feature that can be independently developed, tested, and deployed using multi-agent AI teams.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Document Tree Structure](#document-tree-structure)
4. [Core Components](#core-components)
5. [Implementation Details](#implementation-details)
6. [Deployment Strategy](#deployment-strategy)
7. [Change Detection and Version Control](#change-detection-and-version-control)
8. [Testing and TDD](#testing-and-tdd)
9. [Installation and Setup](#installation-and-setup)
10. [Usage Guide](#usage-guide)

## System Overview

### Key Features

- **Automatic Vertical Slicing**: Decomposes master specifications into manageable, independent slices
- **Multi-Agent Implementation**: Each slice is implemented by a dedicated Tmux-Orchestrator team
- **Multi-Platform Deployment**: Supports Hetzner Cloud (via Terraform) and Modal.com for compute-intensive workloads
- **Bidirectional Change Propagation**: Changes flow from master to slices and vice versa
- **Test-Driven Development**: All slices are generated with TDD specifications
- **Nightly Processing**: Automated detection and processing of changes at 2 AM
- **Version Control**: Git-based document tree with comprehensive versioning

### System Flow

1. **Input**: Master system design specification (Markdown)
2. **Decomposition**: Automatic generation of vertical slice specifications
3. **Orchestration**: Tmux-Orchestrator deploys multi-agent teams per slice
4. **Implementation**: AI agents implement, test, and refine each slice
5. **Deployment**: Automated deployment to test/production environments
6. **Monitoring**: Continuous change detection and queue management
7. **Feedback**: Bidirectional propagation of changes and improvements

## Architecture

### High-Level Architecture

```
[Master Spec] → [Slice Decomposer] → [Spec Manager] → [Queue Manager] → [Orchestrator Hub] → [Deployment Engine] → [Testing Pipeline]
                    ↑               ↑              ↑                    ↑                ↑
                    └──────────────┴──────────────┴────────────────────┴────────────────┘
                              [Change Detector] (Git Hooks + Nightly Cron)
```

### Core Components

1. **Slice Decomposer**: Analyzes master specs and generates vertical slices
2. **Spec Manager**: Handles versioning and bidirectional change propagation
3. **Orchestrator Hub**: Integrates with Tmux-Orchestrator's modular system
4. **Deployment Engine**: Manages Terraform (Hetzner) and Modal deployments
5. **Queue Manager**: Extends Tmux-Orchestrator's queue for slice management
6. **Testing Pipeline**: Automated TDD implementation and validation
7. **Change Detector**: Git-based monitoring with real-time and nightly processing

## Document Tree Structure

```
project-root/
├── master-spec.md                    # Master system specification
├── vertical-slices/                  # Generated slice specifications
│   ├── slice-001-auth/
│   │   ├── spec.md                   # TDD-focused slice specification
│   │   ├── tests/                    # Test files
│   │   │   ├── unit/
│   │   │   └── integration/
│   │   ├── terraform/                # Hetzner deployment configs
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   ├── modal/                    # Modal.com deployment
│   │   │   └── app.py
│   │   └── metadata.json             # Version and dependency tracking
│   └── slice-002-api/
│       └── ... (similar structure)
├── deployments/
│   ├── test/                         # Test environment configurations
│   │   ├── terraform.tfvars
│   │   └── modal_config.json
│   └── production/                   # Production configurations
│       └── ...
└── .slice-orchestrator/
    ├── state.json                    # VSO state tracking
    ├── queue.db                      # SQLite queue database
    └── logs/                         # Operation logs
        ├── decomposition.log
        └── deployment.log
```

### Master Specification Format

```markdown
---
title: "System Name"
version: "1.0.0"
authors: ["Team"]
dependencies: []
last_updated: "2024-01-01"
---

# System Master Specification

## Overview
[System description]

## Requirements
### Functional
- [Requirement 1]
- [Requirement 2]

### Non-Functional
- Performance: [specifications]
- Availability: [specifications]
- Security: [specifications]

## Architecture
### Components
- **Component 1**: [Description]
- **Component 2**: [Description]

### Data Models
- Model1: {field1, field2}
- Model2: {field1, field2}

## API Endpoints
- METHOD /endpoint → [Description]

## Vertical Slices
<!-- Auto-generated during decomposition -->
```

### Slice Specification Format

```markdown
---
slice_id: "slice-XXX-name"
version: "1.0.0"
master_version: "1.0.0"
dependencies: []
platform: "hetzner"  # or "modal"
status: "draft"  # draft, implemented, tested, deployed
---

# Slice Name Specification

## Acceptance Criteria (TDD)
### As a user, I can:
- [User story 1]
- [User story 2]

### As a system, I must:
- [System requirement 1]
- [System requirement 2]

## API Specification
- METHOD /endpoint → Request → Response

## Tests
### Unit Tests
- test_file1.py
- test_file2.py

### Integration Tests
- test_integration.py

## Deployment
- Platform: [Hetzner/Modal]
- Resources: [Specifications]
```

## Core Components

### 1. Slice Decomposer

```python
# slice_decomposer.py
from pathlib import Path
from typing import List, Dict, Any
import networkx as nx
import yaml
import markdown
from tmux_orchestrator.claude.spec_analyzer import SpecificationAnalyzer

class SliceDecomposer:
    def __init__(self, master_spec_path: Path):
        self.master_spec_path = master_spec_path
        self.master_spec = master_spec_path.read_text()
        self.analyzer = SpecificationAnalyzer(Path.cwd())
        
    def decompose(self) -> List[Dict[str, Any]]:
        """Decompose master spec into vertical slices"""
        # Parse master spec sections
        sections = self._parse_sections(self.master_spec)
        
        # Build dependency graph
        graph = self._build_dependency_graph(sections)
        
        # Generate slices
        slices = []
        for component in nx.topological_sort(graph):
            slice_data = self._generate_slice(component, sections)
            slices.append(slice_data)
        
        # AI-assisted refinement
        refined_slices = self._refine_with_ai(slices)
        
        return refined_slices
    
    def _parse_sections(self, spec_text: str) -> Dict[str, Any]:
        """Parse markdown sections into structured data"""
        md = markdown.Markdown(extensions=['meta', 'toc'])
        html = md.convert(spec_text)
        
        sections = {
            'metadata': md.Meta,
            'requirements': self._extract_requirements(spec_text),
            'architecture': self._extract_architecture(spec_text),
            'api': self._extract_api_endpoints(spec_text),
            'data_models': self._extract_data_models(spec_text)
        }
        
        return sections
    
    def _build_dependency_graph(self, sections: Dict) -> nx.DiGraph:
        """Build dependency graph for components"""
        graph = nx.DiGraph()
        
        # Add nodes for each component
        for component in sections['architecture'].get('components', []):
            graph.add_node(component['name'])
        
        # Add edges based on dependencies
        for component in sections['architecture'].get('components', []):
            for dep in component.get('dependencies', []):
                graph.add_edge(component['name'], dep)
        
        return graph
    
    def _generate_slice(self, component: str, sections: Dict) -> Dict[str, Any]:
        """Generate a single vertical slice"""
        slice_id = f"slice-{len(self.slices)+1:03d}-{component.lower()}"
        
        slice_data = {
            'id': slice_id,
            'name': component,
            'spec': self._generate_tdd_spec(component, sections),
            'tests': self._derive_tests(component, sections),
            'terraform': self._generate_terraform_config(component),
            'modal': self._generate_modal_config(component) if self._needs_modal(component) else None,
            'metadata': {
                'version': '1.0.0',
                'dependencies': self._extract_dependencies(component, sections),
                'platform': self._determine_platform(component)
            }
        }
        
        return slice_data
    
    def _generate_tdd_spec(self, component: str, sections: Dict) -> str:
        """Generate TDD-focused specification for a slice"""
        spec = f"""---
slice_id: "slice-{component.lower()}"
version: "1.0.0"
master_version: "{sections['metadata'].get('version', '1.0.0')}"
dependencies: {self._extract_dependencies(component, sections)}
platform: "{self._determine_platform(component)}"
status: "draft"
---

# {component} Slice Specification

## Overview
Implementation of {component} functionality.

## Acceptance Criteria (TDD)
### As a user, I can:
{self._generate_user_stories(component, sections)}

### As a system, I must:
{self._generate_system_requirements(component, sections)}

## API Specification
{self._generate_api_spec(component, sections)}

## Data Models
{self._generate_data_models(component, sections)}

## Tests
### Unit Tests
{self._generate_unit_tests(component)}

### Integration Tests
{self._generate_integration_tests(component)}

## Deployment
- Platform: {self._determine_platform(component)}
- Resources: {self._generate_resource_requirements(component)}
"""
        return spec
    
    def _refine_with_ai(self, slices: List[Dict]) -> List[Dict]:
        """Use AI to refine generated slices"""
        refined = []
        for slice_data in slices:
            # Save temporary spec file
            temp_spec = Path(f"/tmp/{slice_data['id']}.md")
            temp_spec.write_text(slice_data['spec'])
            
            # Analyze with AI
            refined_spec = self.analyzer.analyze_specification(temp_spec, Path.cwd())
            
            if refined_spec:
                slice_data['spec'] = refined_spec
            
            refined.append(slice_data)
            
        return refined
```

### 2. VSO System Main Controller

```python
#!/usr/bin/env python3
# vso_system.py

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import subprocess
import sys

# Add Tmux-Orchestrator to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tmux_orchestrator.main import create_orchestrator
from tmux_orchestrator.database.queue_manager import QueueManager
from tmux_orchestrator.core.state_manager import StateManager
from slice_decomposer import SliceDecomposer
from change_detector import ChangeDetector

class VSOSystem:
    """Main controller for Vertical Slice Orchestration System"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.state_file = project_root / '.slice-orchestrator/state.json'
        self.queue_db = project_root / '.slice-orchestrator/queue.db'
        
        # Ensure directories exist
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize managers
        self.state_mgr = StateManager(project_root)
        self.queue_mgr = QueueManager(project_root)
        self.change_detector = ChangeDetector(project_root)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for slice queue"""
        conn = sqlite3.connect(self.queue_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS slice_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slice_id TEXT UNIQUE NOT NULL,
                spec TEXT NOT NULL,
                version TEXT NOT NULL,
                status TEXT DEFAULT 'queued',
                platform TEXT DEFAULT 'hetzner',
                priority INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def decompose_master_spec(self):
        """Decompose master spec into vertical slices"""
        master_spec_path = self.project_root / 'master-spec.md'
        
        if not master_spec_path.exists():
            print(f"❌ Master spec not found: {master_spec_path}")
            return
        
        print("🔄 Decomposing master specification...")
        decomposer = SliceDecomposer(master_spec_path)
        slices = decomposer.decompose()
        
        # Create slice directories and save specs
        for slice_data in slices:
            self._create_slice_structure(slice_data)
            self._queue_slice(slice_data)
            self._update_state(slice_data)
        
        print(f"✅ Decomposed into {len(slices)} vertical slices")
        return slices
    
    def _create_slice_structure(self, slice_data: Dict[str, Any]):
        """Create directory structure for a slice"""
        slice_dir = self.project_root / f"vertical-slices/{slice_data['id']}"
        
        # Create directories
        (slice_dir / 'tests/unit').mkdir(parents=True, exist_ok=True)
        (slice_dir / 'tests/integration').mkdir(parents=True, exist_ok=True)
        (slice_dir / 'terraform').mkdir(parents=True, exist_ok=True)
        
        if slice_data.get('modal'):
            (slice_dir / 'modal').mkdir(parents=True, exist_ok=True)
        
        # Save spec
        (slice_dir / 'spec.md').write_text(slice_data['spec'])
        
        # Save metadata
        metadata = slice_data['metadata']
        metadata['slice_id'] = slice_data['id']
        metadata['created_at'] = datetime.now().isoformat()
        
        with open(slice_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save Terraform config
        if slice_data.get('terraform'):
            self._save_terraform_config(slice_dir / 'terraform', slice_data['terraform'])
        
        # Save Modal config
        if slice_data.get('modal'):
            self._save_modal_config(slice_dir / 'modal', slice_data['modal'])
    
    def _save_terraform_config(self, terraform_dir: Path, config: Dict):
        """Save Terraform configuration files"""
        # main.tf
        main_tf = """terraform {
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.42"
    }
  }
}

variable "slice_id" {
  description = "Slice identifier"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "test"
}

provider "hcloud" {
  token = var.hcloud_token
}

resource "hcloud_server" "slice_server" {
  name        = "${var.slice_id}-${var.environment}"
  image       = "ubuntu-22.04"
  server_type = var.environment == "production" ? "cx31" : "cx11"
  
  user_data = templatefile("${path.module}/user-data.sh", {
    slice_id = var.slice_id
    environment = var.environment
  })
}

output "server_ip" {
  value = hcloud_server.slice_server.ipv4_address
}
"""
        (terraform_dir / 'main.tf').write_text(main_tf)
        
        # variables.tf
        variables_tf = """variable "hcloud_token" {
  description = "Hetzner Cloud API token"
  type        = string
  sensitive   = true
}

variable "slice_id" {
  description = "Slice identifier"
  type        = string
}

variable "environment" {
  description = "test or production"
  type        = string
  default     = "test"
}
"""
        (terraform_dir / 'variables.tf').write_text(variables_tf)
        
        # user-data.sh
        user_data = """#!/bin/bash
apt-get update && apt-get upgrade -y
apt-get install -y python3 python3-pip git docker.io
mkdir -p /opt/${slice_id}
cd /opt/${slice_id}
git clone https://github.com/your-org/project.git .
git checkout ${slice_id}-branch
pip3 install -r requirements.txt
python3 app.py &
"""
        (terraform_dir / 'user-data.sh').write_text(user_data)
    
    def _save_modal_config(self, modal_dir: Path, config: Dict):
        """Save Modal.com configuration"""
        modal_app = """import modal
from fastapi import FastAPI

app = modal.App("{slice_id}")
web_app = FastAPI(title="{slice_id} API")

@app.function()
@modal.web_endpoint(method="POST")
def process(data: dict):
    # Implementation here
    return {"result": "processed"}

@app.function()
@modal.asgi_app()
def serve():
    return web_app
"""
        (modal_dir / 'app.py').write_text(modal_app)
    
    def _queue_slice(self, slice_data: Dict[str, Any]):
        """Add slice to processing queue"""
        conn = sqlite3.connect(self.queue_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO slice_queue 
            (slice_id, spec, version, platform, priority)
            VALUES (?, ?, ?, ?, ?)
        """, (
            slice_data['id'],
            slice_data['spec'],
            slice_data['metadata']['version'],
            slice_data['metadata'].get('platform', 'hetzner'),
            0  # Default priority
        ))
        
        conn.commit()
        conn.close()
    
    def orchestrate_slice(self, slice_id: str):
        """Deploy Tmux-Orchestrator team for a slice"""
        slice_path = self.project_root / f'vertical-slices/{slice_id}'
        spec_path = slice_path / 'spec.md'
        
        if not spec_path.exists():
            print(f"❌ Slice spec not found: {spec_path}")
            return False
        
        print(f"🚀 Orchestrating slice: {slice_id}")
        
        # Create orchestrator with configuration
        orchestrator = create_orchestrator({
            'debug': True,
            'git_mode': 'local',
            'plan': 'max5'  # Use appropriate plan
        })
        
        # Start orchestration
        result = orchestrator.start_orchestration(
            project_path=str(slice_path),
            spec_path=str(spec_path),
            roles=['orchestrator', 'developer', 'tester', 'testrunner'],
            team_type='web_application'  # Or auto-detect
        )
        
        if result:
            print(f"✅ Slice {slice_id} orchestration started successfully")
            self._update_slice_status(slice_id, 'orchestrating')
        else:
            print(f"❌ Failed to orchestrate slice {slice_id}")
            self._update_slice_status(slice_id, 'failed')
        
        return result
    
    def deploy_slice(self, slice_id: str, platform: str, environment: str):
        """Deploy a slice to specified platform"""
        slice_path = self.project_root / f'vertical-slices/{slice_id}'
        
        if platform == 'hetzner':
            return self._deploy_to_hetzner(slice_path, environment)
        elif platform == 'modal':
            return self._deploy_to_modal(slice_path, environment)
        else:
            print(f"❌ Unknown platform: {platform}")
            return False
    
    def _deploy_to_hetzner(self, slice_path: Path, environment: str):
        """Deploy slice to Hetzner Cloud using Terraform"""
        terraform_dir = slice_path / 'terraform'
        tfvars_file = self.project_root / f'deployments/{environment}/terraform.tfvars'
        
        print(f"🌍 Deploying to Hetzner ({environment})...")
        
        # Terraform init
        result = subprocess.run(
            ['terraform', 'init'],
            cwd=terraform_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"❌ Terraform init failed: {result.stderr}")
            return False
        
        # Terraform apply
        result = subprocess.run(
            ['terraform', 'apply', '-auto-approve', f'-var-file={tfvars_file}'],
            cwd=terraform_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ Deployed to Hetzner successfully")
            return True
        else:
            print(f"❌ Terraform apply failed: {result.stderr}")
            return False
    
    def _deploy_to_modal(self, slice_path: Path, environment: str):
        """Deploy slice to Modal.com"""
        modal_dir = slice_path / 'modal'
        
        print(f"☁️ Deploying to Modal ({environment})...")
        
        result = subprocess.run(
            ['modal', 'deploy', 'app.py'],
            cwd=modal_dir,
            env={'MODAL_ENVIRONMENT': environment},
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ Deployed to Modal successfully")
            # Extract endpoint URL from output
            for line in result.stdout.split('\n'):
                if 'https://' in line and '.modal.run' in line:
                    print(f"📍 Endpoint: {line.strip()}")
            return True
        else:
            print(f"❌ Modal deployment failed: {result.stderr}")
            return False
    
    def test_slice(self, slice_id: str, environment: str = 'test'):
        """Run tests for a deployed slice"""
        slice_path = self.project_root / f'vertical-slices/{slice_id}'
        
        print(f"🧪 Testing slice: {slice_id}")
        
        # Run unit tests
        result = subprocess.run(
            ['pytest', 'tests/unit/', '-v'],
            cwd=slice_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"❌ Unit tests failed")
            return False
        
        # Run integration tests
        result = subprocess.run(
            ['pytest', 'tests/integration/', '-v'],
            cwd=slice_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ All tests passed")
            self._update_slice_status(slice_id, 'tested')
            return True
        else:
            print(f"❌ Integration tests failed")
            return False
    
    def process_nightly(self):
        """Nightly processing at 2 AM"""
        print(f"🌙 Starting nightly processing at {datetime.now()}")
        
        # Check for changes
        changes = self.change_detector.detect_changes()
        
        if changes['master_changed']:
            print("📝 Master spec changed - regenerating slices")
            self.decompose_master_spec()
        
        if changes['slices_changed']:
            print(f"🔄 {len(changes['slices_changed'])} slices changed")
            for slice_id in changes['slices_changed']:
                self._update_slice_queue(slice_id)
        
        # Process queue
        self._process_slice_queue()
        
        # Update state
        self._update_nightly_state()
        
        print(f"✅ Nightly processing completed")
    
    def _process_slice_queue(self):
        """Process pending slices in queue"""
        conn = sqlite3.connect(self.queue_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT slice_id, platform 
            FROM slice_queue 
            WHERE status = 'queued'
            ORDER BY priority DESC, created_at
            LIMIT 5
        """)
        
        pending_slices = cursor.fetchall()
        conn.close()
        
        for slice_id, platform in pending_slices:
            print(f"Processing slice: {slice_id}")
            
            # Orchestrate
            if self.orchestrate_slice(slice_id):
                # Deploy to test
                if self.deploy_slice(slice_id, platform, 'test'):
                    # Run tests
                    if self.test_slice(slice_id):
                        # Deploy to production if tests pass
                        self.deploy_slice(slice_id, platform, 'production')
    
    def _update_slice_status(self, slice_id: str, status: str):
        """Update slice status in queue"""
        conn = sqlite3.connect(self.queue_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE slice_queue 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE slice_id = ?
        """, (status, slice_id))
        
        conn.commit()
        conn.close()
    
    def _update_slice_queue(self, slice_id: str):
        """Update or replace slice in queue when changed"""
        slice_path = self.project_root / f'vertical-slices/{slice_id}'
        spec_path = slice_path / 'spec.md'
        
        if spec_path.exists():
            spec = spec_path.read_text()
            
            conn = sqlite3.connect(self.queue_db)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE slice_queue 
                SET spec = ?, status = 'queued', updated_at = CURRENT_TIMESTAMP
                WHERE slice_id = ?
            """, (spec, slice_id))
            
            conn.commit()
            conn.close()
    
    def _update_state(self, slice_data: Dict[str, Any]):
        """Update VSO state file"""
        state = self._load_state()
        
        state['slices'][slice_data['id']] = {
            'version': slice_data['metadata']['version'],
            'status': 'draft',
            'dependencies': slice_data['metadata'].get('dependencies', []),
            'platform': slice_data['metadata'].get('platform', 'hetzner'),
            'last_modified': datetime.now().isoformat()
        }
        
        self._save_state(state)
    
    def _update_nightly_state(self):
        """Update state after nightly processing"""
        state = self._load_state()
        state['nightly_last_run'] = datetime.now().isoformat()
        self._save_state(state)
    
    def _load_state(self) -> Dict[str, Any]:
        """Load VSO state from file"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        
        return {
            'version': '1.0.0',
            'slices': {},
            'deployments': {
                'test': {'slices_deployed': []},
                'production': {'slices_deployed': []}
            },
            'conflicts': [],
            'nightly_last_run': None
        }
    
    def _save_state(self, state: Dict[str, Any]):
        """Save VSO state to file"""
        state['last_updated'] = datetime.now().isoformat()
        
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description='Vertical Slice Orchestration System')
    
    parser.add_argument(
        'command',
        choices=['decompose', 'orchestrate', 'deploy', 'test', 'nightly', 'status'],
        help='Command to execute'
    )
    
    parser.add_argument('--slice-id', help='Slice identifier')
    parser.add_argument('--platform', choices=['hetzner', 'modal'], default='hetzner')
    parser.add_argument('--environment', choices=['test', 'production'], default='test')
    parser.add_argument('--project-root', type=Path, default=Path.cwd())
    
    args = parser.parse_args()
    
    # Initialize VSO system
    vso = VSOSystem(args.project_root)
    
    # Execute command
    if args.command == 'decompose':
        vso.decompose_master_spec()
    
    elif args.command == 'orchestrate':
        if not args.slice_id:
            print("❌ --slice-id required for orchestrate command")
            sys.exit(1)
        vso.orchestrate_slice(args.slice_id)
    
    elif args.command == 'deploy':
        if not args.slice_id:
            print("❌ --slice-id required for deploy command")
            sys.exit(1)
        vso.deploy_slice(args.slice_id, args.platform, args.environment)
    
    elif args.command == 'test':
        if not args.slice_id:
            print("❌ --slice-id required for test command")
            sys.exit(1)
        vso.test_slice(args.slice_id, args.environment)
    
    elif args.command == 'nightly':
        vso.process_nightly()
    
    elif args.command == 'status':
        state = vso._load_state()
        print(json.dumps(state, indent=2))

if __name__ == "__main__":
    main()
```

### 3. Change Detector

```python
# change_detector.py

import git
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

class ChangeDetector:
    """Detects and manages changes in the document tree"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.repo = git.Repo(project_root)
        self.state_file = project_root / '.slice-orchestrator/state.json'
    
    def detect_changes(self) -> Dict[str, Any]:
        """Detect changes in master spec and slices"""
        changes = {
            'master_changed': False,
            'slices_changed': [],
            'conflicts': []
        }
        
        # Get commits since last check
        last_check = self._get_last_check_time()
        commits = list(self.repo.iter_commits('main', since=last_check))
        
        for commit in commits:
            changed_files = list(commit.stats.files.keys())
            
            # Check for master spec changes
            if 'master-spec.md' in changed_files:
                changes['master_changed'] = True
                self._record_master_change(commit)
            
            # Check for slice changes
            for file_path in changed_files:
                if file_path.startswith('vertical-slices/'):
                    slice_id = self._extract_slice_id(file_path)
                    if slice_id and slice_id not in changes['slices_changed']:
                        changes['slices_changed'].append(slice_id)
                        self._record_slice_change(slice_id, commit)
        
        # Check for conflicts
        if changes['master_changed'] and changes['slices_changed']:
            conflicts = self._check_conflicts(changes['slices_changed'])
            changes['conflicts'] = conflicts
        
        return changes
    
    def _get_last_check_time(self):
        """Get timestamp of last change detection"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                state = json.load(f)
                if 'last_change_check' in state:
                    return state['last_change_check']
        
        # Default to 24 hours ago
        return '24 hours ago'
    
    def _extract_slice_id(self, file_path: str) -> str:
        """Extract slice ID from file path"""
        parts = Path(file_path).parts
        if len(parts) >= 2 and parts[0] == 'vertical-slices':
            return parts[1]
        return None
    
    def _record_master_change(self, commit):
        """Record master spec change in state"""
        state = self._load_state()
        state['master_spec'] = {
            'version': self._increment_version(state.get('master_spec', {}).get('version', '1.0.0')),
            'hash': commit.hexsha,
            'last_modified': datetime.now().isoformat()
        }
        self._save_state(state)
    
    def _record_slice_change(self, slice_id: str, commit):
        """Record slice change in state"""
        state = self._load_state()
        if 'slices' not in state:
            state['slices'] = {}
        
        if slice_id not in state['slices']:
            state['slices'][slice_id] = {}
        
        state['slices'][slice_id].update({
            'version': self._increment_version(state['slices'][slice_id].get('version', '1.0.0')),
            'hash': commit.hexsha,
            'last_modified': datetime.now().isoformat()
        })
        
        self._save_state(state)
    
    def _check_conflicts(self, changed_slices: List[str]) -> List[Dict]:
        """Check for conflicts between master and slice changes"""
        conflicts = []
        state = self._load_state()
        
        master_version = state.get('master_spec', {}).get('version', '1.0.0')
        
        for slice_id in changed_slices:
            slice_version = state.get('slices', {}).get(slice_id, {}).get('version', '1.0.0')
            
            if self._version_compare(master_version, slice_version) != 0:
                conflicts.append({
                    'slice_id': slice_id,
                    'master_version': master_version,
                    'slice_version': slice_version,
                    'resolution': 'manual'
                })
        
        return conflicts
    
    def resolve_conflicts(self, master_changes: Dict, slice_changes: Dict):
        """Resolve conflicts between master and slice changes"""
        master_ver = master_changes.get('version', '0.0.0')
        slice_ver = slice_changes.get('version', '0.0.0')
        
        if self._version_compare(master_ver, slice_ver) > 0:
            # Master is newer - regenerate slice
            return {'action': 'regenerate_slice', 'slice_id': slice_changes['slice_id']}
        elif self._version_compare(master_ver, slice_ver) < 0:
            # Slice is newer - update master
            return {'action': 'update_master', 'slice_id': slice_changes['slice_id']}
        else:
            # Same version - manual merge required
            return {'action': 'manual_merge', 'slice_id': slice_changes['slice_id']}
    
    def _increment_version(self, version: str) -> str:
        """Increment semantic version"""
        parts = version.split('.')
        parts[-1] = str(int(parts[-1]) + 1)
        return '.'.join(parts)
    
    def _version_compare(self, v1: str, v2: str) -> int:
        """Compare semantic versions"""
        v1_parts = [int(x) for x in v1.split('.')]
        v2_parts = [int(x) for x in v2.split('.')]
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1_part = v1_parts[i] if i < len(v1_parts) else 0
            v2_part = v2_parts[i] if i < len(v2_parts) else 0
            
            if v1_part > v2_part:
                return 1
            elif v1_part < v2_part:
                return -1
        
        return 0
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from file"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {}
    
    def _save_state(self, state: Dict[str, Any]):
        """Save state to file"""
        state['last_change_check'] = datetime.now().isoformat()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
```

## Deployment Strategy

### Hetzner Cloud Deployment

The system uses Terraform for Infrastructure as Code on Hetzner Cloud:

1. **Test Environment**: Smaller instances (cx11) for validation
2. **Production Environment**: Larger instances (cx31) for scale
3. **Auto-scaling**: Based on load metrics
4. **Security**: Firewall rules and SSH key management

### Modal.com Deployment

For compute-intensive Python workloads:

1. **Serverless Functions**: Auto-scaling compute
2. **REST API Endpoints**: Exposed via Modal's web endpoints
3. **Persistent Volumes**: For data storage
4. **Secrets Management**: Secure credential handling

## Change Detection and Version Control

### Git Integration

1. **Hooks**: Post-commit and pre-push hooks for real-time detection
2. **Branching**: Each slice gets its own branch (slice-XXX-vY.Y.Y)
3. **Merging**: Automated merge strategies based on version comparison

### Nightly Processing

Cron job at 2 AM:
```bash
# /etc/cron.d/vso_nightly
0 2 * * * /path/to/project/vso_system.py nightly
```

### Bidirectional Propagation

- **Master → Slices**: Regenerate affected slices when master changes
- **Slices → Master**: Update master with completed slice implementations
- **Conflict Resolution**: Version-based automatic resolution with manual fallback

## Testing and TDD

### Test Generation

Each slice includes:
- **Unit Tests**: Generated from acceptance criteria
- **Integration Tests**: End-to-end flow validation
- **Performance Tests**: Load and response time validation

### Test Execution Pipeline

1. **Pre-deployment**: Run unit tests locally
2. **Post-deployment**: Run integration tests on deployed infrastructure
3. **Continuous**: Monitor deployed slices for issues

## Installation and Setup

### Prerequisites

```bash
# System requirements
python3.11+
git
terraform
modal-client

# Python packages
pip install networkx pyyaml markdown gitpython pytest
```

### Initial Setup

```bash
# Clone repository
git clone <your-repo>
cd <your-repo>

# Create VSO structure
mkdir -p .slice-orchestrator/logs
mkdir -p vertical-slices
mkdir -p deployments/{test,production}

# Initialize VSO
python3 vso_system.py decompose

# Set up git hooks
cp hooks/post-commit .git/hooks/
cp hooks/pre-push .git/hooks/
chmod +x .git/hooks/*

# Configure cron for nightly processing
crontab -e
# Add: 0 2 * * * /path/to/vso_system.py nightly
```

### Configuration

Create deployment configurations:

```bash
# deployments/test/terraform.tfvars
cat > deployments/test/terraform.tfvars << EOF
hcloud_token = "your-test-token"
environment  = "test"
EOF

# deployments/production/terraform.tfvars
cat > deployments/production/terraform.tfvars << EOF
hcloud_token = "your-prod-token"
environment  = "production"
EOF

# Modal configuration
modal token set --token-id your-modal-token
```

## Usage Guide

### Basic Commands

```bash
# Decompose master spec into slices
python3 vso_system.py decompose

# Orchestrate a specific slice
python3 vso_system.py orchestrate --slice-id slice-001-auth

# Deploy a slice
python3 vso_system.py deploy --slice-id slice-001-auth --platform hetzner --environment test

# Run tests for a slice
python3 vso_system.py test --slice-id slice-001-auth

# Run nightly processing manually
python3 vso_system.py nightly

# Check system status
python3 vso_system.py status
```

### Workflow Example

1. **Create Master Spec**: Write your system design in `master-spec.md`
2. **Decompose**: Run `python3 vso_system.py decompose`
3. **Review Slices**: Check generated specs in `vertical-slices/`
4. **Orchestrate**: VSO automatically queues and processes slices
5. **Monitor**: Check progress via `python3 vso_system.py status`
6. **Deploy**: Slices are automatically deployed after testing

### Monitoring and Logs

- **Logs**: Check `.slice-orchestrator/logs/` for detailed logs
- **State**: View `.slice-orchestrator/state.json` for current state
- **Queue**: Monitor `.slice-orchestrator/queue.db` for pending slices

## Integration with Tmux-Orchestrator

The VSO system fully leverages the modular Tmux-Orchestrator:

1. **Orchestrator**: Each slice gets its own orchestration session
2. **SessionManager**: Manages isolated Tmux sessions per slice
3. **QueueManager**: Extended for slice prioritization
4. **StateManager**: Tracks slice implementation progress
5. **HealthMonitor**: Validates slice deployments
6. **AgentFactory**: Deploys specialized teams per slice type

## Best Practices

1. **Master Spec Quality**: Keep master spec well-structured and complete
2. **Version Management**: Use semantic versioning consistently
3. **Test Coverage**: Ensure >80% test coverage per slice
4. **Deployment Stages**: Always test before production
5. **Monitoring**: Set up alerts for failed slices
6. **Documentation**: Keep slice specs updated with implementations

## Troubleshooting

### Common Issues

1. **Decomposition Fails**: Check master spec format and structure
2. **Orchestration Hangs**: Verify Tmux-Orchestrator is properly configured
3. **Deployment Errors**: Check Terraform/Modal credentials and quotas
4. **Test Failures**: Review slice implementation against acceptance criteria
5. **Conflicts**: Use version comparison to determine resolution strategy

### Debug Commands

```bash
# Check VSO state
cat .slice-orchestrator/state.json | jq

# View queue status
sqlite3 .slice-orchestrator/queue.db "SELECT * FROM slice_queue"

# Check git changes
git log --oneline -10

# View Terraform state
cd vertical-slices/slice-XXX/terraform && terraform show

# Check Modal deployments
modal app list
```

## Conclusion

The Vertical Slice Orchestration System provides a powerful, automated approach to implementing large system designs. By combining intelligent decomposition, multi-agent AI orchestration, and multi-platform deployment, it enables rapid, high-quality system development with minimal manual intervention.

The system's integration with Tmux-Orchestrator's modular architecture ensures scalability and maintainability, while the TDD focus and automated testing guarantee quality at every stage.

---

*Document Version: 1.0.0*  
*Last Updated: 2024-01-01*  
*Authors: VSO Development Team*
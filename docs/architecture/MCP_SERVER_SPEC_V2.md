# MCP Server for Tmux Orchestrator Specification V2
## Enhanced for Claude Daemon Integration

## Overview
The MCP (Model Context Protocol) Server provides Claude Code and the Claude Daemon with specialized tools and interfaces for managing Tmux Orchestrator projects. It acts as an intelligent bridge between AI models, the Claude Daemon, and the Tmux Orchestrator system, offering enhanced automation, natural language processing, and AI-driven workflow optimization.

## Architecture Overview

### Claude Daemon Integration
The MCP Server now serves two primary clients:
1. **Claude Code** - Direct MCP tool usage for development
2. **Claude Daemon** - Persistent server-side Claude instance that:
   - Runs as `clauderun` user via systemd service
   - Maintains always-on availability for mobile app connections
   - Manages concurrent sessions and state
   - Orchestrates team communications

### Communication Flow
```
Mobile App → Claude Daemon → MCP Tools → Tmux Orchestrator
                   ↓
            Session State Management
                   ↓
            Team Agents (via tmux)
```

## Repository Structure
```
tmux-orchestrator-mcp/
├── README.md
├── pyproject.toml                    # Python project configuration
├── requirements.txt                  # Dependencies
├── Dockerfile                        # Container configuration
├── docker-compose.yml               # Development setup
├── .github/workflows/               # CI/CD pipelines
│   ├── test.yml
│   ├── build.yml
│   └── deploy.yml
├── daemon/                          # NEW: Claude Daemon Components
│   ├── __init__.py
│   ├── claude_daemon.py            # Main daemon implementation
│   ├── session_manager.py          # Multi-session handling
│   ├── websocket_server.py         # WebSocket communication layer
│   ├── auth_manager.py             # JWT authentication
│   └── systemd/
│       └── claude-daemon.service   # Systemd service file
├── src/
│   ├── tmux_orchestrator_mcp/
│   │   ├── __init__.py
│   │   ├── main.py                   # Entry point
│   │   ├── server.py                 # MCP server implementation
│   │   ├── tools/                    # MCP tools
│   │   │   ├── __init__.py
│   │   │   ├── project_management.py # Project CRUD operations
│   │   │   ├── spec_writer.py        # NEW: Spec file creation/editing
│   │   │   ├── batch_processor.py    # NEW: Batch project handling
│   │   │   ├── git_workflows.py      # AI-enhanced git operations
│   │   │   ├── agent_messaging.py    # Agent communication tools
│   │   │   ├── team_coordinator.py   # NEW: Team communication hub
│   │   │   ├── monitoring.py         # Status and health monitoring
│   │   │   ├── automation.py         # Workflow automation tools
│   │   │   └── ai_analysis.py        # AI-powered analysis tools
│   │   ├── models/                   # Data models
│   │   │   ├── __init__.py
│   │   │   ├── mcp_types.py          # MCP protocol types
│   │   │   ├── orchestrator_types.py # Orchestrator-specific types
│   │   │   ├── daemon_types.py       # NEW: Daemon session types
│   │   │   └── workflow_types.py     # Workflow definition types
│   │   ├── clients/                  # External service clients
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator_client.py # Direct orchestrator integration
│   │   │   ├── scheduler_client.py    # NEW: Scheduler integration
│   │   │   └── ai_client.py          # AI service integrations
│   │   ├── utils/                    # Utility modules
│   │   │   ├── __init__.py
│   │   │   ├── auth.py               # Authentication handling
│   │   │   ├── config.py             # Configuration management
│   │   │   ├── logging.py            # Logging utilities
│   │   │   ├── session_state.py      # NEW: Session persistence
│   │   │   └── validation.py         # Input validation
│   │   └── schemas/                  # JSON schemas for tools
│   │       ├── project_schema.json
│   │       ├── spec_schema.json      # NEW: Spec validation
│   │       ├── batch_schema.json     # NEW: Batch processing
│   │       ├── git_schema.json
│   │       └── message_schema.json
├── tests/                           # Test suite
│   ├── __init__.py
│   ├── conftest.py                  # Test configuration
│   ├── test_daemon/                 # NEW: Daemon tests
│   │   ├── test_session_manager.py
│   │   └── test_websocket.py
│   ├── test_tools/                  # Tool-specific tests
│   │   ├── test_project_management.py
│   │   ├── test_spec_writer.py
│   │   ├── test_batch_processor.py
│   │   └── test_monitoring.py
│   └── test_integration/            # Integration tests
│       ├── test_daemon_integration.py
│       └── test_orchestrator_integration.py
└── config/                         # Configuration files
    ├── mcp_config.json             # MCP server configuration
    ├── daemon_config.yaml          # NEW: Daemon configuration
    ├── logging_config.yaml         # Logging configuration
    └── tools_manifest.json         # Available tools manifest
```

## Technology Stack

### Core Technologies
- **Python 3.11+**: For consistency with Tmux Orchestrator
- **MCP SDK**: Model Context Protocol implementation
- **FastAPI**: For HTTP endpoints and WebSocket support
- **Pydantic**: Data validation and serialization
- **httpx**: Async HTTP client for orchestrator communication
- **Redis**: Session state management and pub/sub for real-time updates

### Key Dependencies
```toml
# pyproject.toml
[project]
name = "tmux-orchestrator-mcp"
version = "2.0.0"
dependencies = [
    "mcp>=1.0.0",
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "websockets>=12.0",
    "httpx>=0.25.0",
    "pydantic>=2.0.0",
    "anthropic>=0.7.0",
    "pydantic-settings>=2.0.0",
    "structlog>=23.1.0",
    "tenacity>=8.2.0",
    "jsonschema>=4.19.0",
    "python-jose[cryptography]>=3.3.0",
    "redis>=5.0.0",
    "python-dotenv>=1.0.0",
    "asyncio>=3.4.3"
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.11.0",
    "black>=23.7.0",
    "ruff>=0.0.287",
    "mypy>=1.5.0"
]
```

## Enhanced MCP Tool Specifications

### Project Management Tools

#### create_orchestration_project
```json
{
  "name": "create_orchestration_project",
  "description": "Create a new Tmux Orchestrator project from specification",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_name": {
        "type": "string",
        "description": "Name of the project"
      },
      "project_path": {
        "type": "string",
        "description": "Absolute path to the project directory (auto-detect if null)"
      },
      "specification": {
        "type": "string",
        "description": "Project specification in markdown format"
      },
      "team_composition": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional custom team roles",
        "default": []
      },
      "project_size": {
        "type": "string",
        "enum": ["small", "medium", "large"],
        "default": "medium"
      },
      "auto_start": {
        "type": "boolean",
        "description": "Whether to automatically start the orchestration",
        "default": true
      },
      "parent_directory": {
        "type": "string",
        "description": "Parent directory for new projects",
        "default": "~/projects"
      }
    },
    "required": ["project_name", "specification"]
  }
}
```

### Spec Writing Tools (NEW)

#### create_project_spec
```json
{
  "name": "create_project_spec",
  "description": "Create a new project specification file",
  "inputSchema": {
    "type": "object",
    "properties": {
      "spec_name": {
        "type": "string",
        "description": "Name for the spec file (without .md extension)"
      },
      "project_type": {
        "type": "string",
        "enum": ["web_app", "api", "cli_tool", "library", "mobile_app", "data_pipeline"],
        "description": "Type of project"
      },
      "description": {
        "type": "string",
        "description": "Natural language description of the project"
      },
      "requirements": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of requirements"
      },
      "save_path": {
        "type": "string",
        "description": "Where to save the spec file",
        "default": "./specs"
      },
      "generate_git_repo": {
        "type": "boolean",
        "description": "Initialize a git repository for the spec",
        "default": false
      }
    },
    "required": ["spec_name", "project_type", "description"]
  }
}
```

#### edit_project_spec
```json
{
  "name": "edit_project_spec",
  "description": "Edit an existing project specification",
  "inputSchema": {
    "type": "object",
    "properties": {
      "spec_path": {
        "type": "string",
        "description": "Path to the existing spec file"
      },
      "modifications": {
        "type": "object",
        "properties": {
          "add_requirements": {"type": "array", "items": {"type": "string"}},
          "remove_requirements": {"type": "array", "items": {"type": "string"}},
          "update_description": {"type": "string"},
          "change_team_size": {"type": "string", "enum": ["small", "medium", "large"]}
        }
      }
    },
    "required": ["spec_path", "modifications"]
  }
}
```

### Batch Processing Tools (NEW)

#### batch_enqueue_projects
```json
{
  "name": "batch_enqueue_projects",
  "description": "Enqueue multiple project specs for batch processing",
  "inputSchema": {
    "type": "object",
    "properties": {
      "spec_files": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of spec file paths"
      },
      "project_directory": {
        "type": "string",
        "description": "Base directory for projects",
        "default": "~/projects"
      },
      "priority": {
        "type": "string",
        "enum": ["low", "normal", "high", "urgent"],
        "default": "normal"
      },
      "schedule_time": {
        "type": "string",
        "description": "ISO 8601 timestamp to start batch (null for immediate)"
      },
      "notification_email": {
        "type": "string",
        "description": "Email for batch completion notification"
      }
    },
    "required": ["spec_files"]
  }
}
```

#### get_batch_status
```json
{
  "name": "get_batch_status",
  "description": "Get status of batch processing queue",
  "inputSchema": {
    "type": "object",
    "properties": {
      "include_completed": {
        "type": "boolean",
        "default": false
      },
      "limit": {
        "type": "integer",
        "default": 10
      }
    }
  }
}
```

### Team Communication Tools (NEW)

#### send_to_team
```json
{
  "name": "send_to_team",
  "description": "Send message to specific team or agent",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": {"type": "string"},
      "target": {
        "type": "string",
        "enum": ["orchestrator", "project_manager", "developer", "tester", "testrunner", "devops", "all_agents"],
        "description": "Target recipient"
      },
      "message": {"type": "string"},
      "context": {
        "type": "object",
        "description": "Additional context to include"
      },
      "wait_for_response": {
        "type": "boolean",
        "default": false
      },
      "timeout": {
        "type": "integer",
        "description": "Response timeout in seconds",
        "default": 30
      }
    },
    "required": ["project_id", "target", "message"]
  }
}
```

#### get_team_status
```json
{
  "name": "get_team_status",
  "description": "Get comprehensive team status for a project",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": {"type": "string"},
      "include_git_status": {"type": "boolean", "default": true},
      "include_agent_health": {"type": "boolean", "default": true},
      "include_recent_messages": {"type": "boolean", "default": false}
    },
    "required": ["project_id"]
  }
}
```

### Session Management Tools (NEW)

#### create_daemon_session
```json
{
  "name": "create_daemon_session",
  "description": "Create a new daemon session for mobile app connection",
  "inputSchema": {
    "type": "object",
    "properties": {
      "user_id": {"type": "string"},
      "device_id": {"type": "string"},
      "session_type": {
        "type": "string",
        "enum": ["mobile", "web", "api"],
        "default": "mobile"
      }
    },
    "required": ["user_id", "device_id"]
  }
}
```

## Claude Daemon Implementation

### Daemon Architecture
```python
# daemon/claude_daemon.py
import asyncio
import subprocess
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from session_manager import SessionManager
from auth_manager import AuthManager
from mcp_client import MCPClient

class ClaudeDaemon:
    def __init__(self, config_path: str = "/opt/claude-daemon/config.yaml"):
        self.config = self.load_config(config_path)
        self.claude_proc = None
        self.session_manager = SessionManager()
        self.auth_manager = AuthManager(self.config['jwt_secret'])
        self.mcp_client = MCPClient(self.config['mcp_server_url'])
        self.app = FastAPI()
        self.setup_routes()
        self.start_claude()
    
    def start_claude(self):
        """Start persistent Claude instance"""
        self.claude_proc = subprocess.Popen(
            ['claude', '--dangerously-skip-permissions'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=self.config['tmux_orchestrator_path']
        )
    
    async def handle_request(self, request: str, session_id: str) -> str:
        """Process request through Claude and MCP tools"""
        # Add session context
        context = self.session_manager.get_context(session_id)
        prompt = f"{context}\n\nUser request: {request}"
        
        # Send to Claude
        response = await self.send_to_claude(prompt)
        
        # Parse for MCP tool calls
        if "mcp__" in response:
            tool_result = await self.mcp_client.execute_tool(response)
            response = await self.send_to_claude(f"Tool result: {tool_result}")
        
        # Update session context
        self.session_manager.update_context(session_id, request, response)
        
        return response
    
    def setup_routes(self):
        @self.app.websocket("/ws/daemon")
        async def websocket_endpoint(websocket: WebSocket, token: str):
            session_id = self.auth_manager.verify_token(token)
            await websocket.accept()
            
            try:
                while True:
                    data = await websocket.receive_text()
                    response = await self.handle_request(data, session_id)
                    await websocket.send_text(response)
            except Exception as e:
                logging.error(f"WebSocket error: {e}")
            finally:
                await websocket.close()
```

### Systemd Service Configuration
```ini
# daemon/systemd/claude-daemon.service
[Unit]
Description=Claude Daemon for Tmux Orchestrator
After=network.target redis.service

[Service]
Type=notify
User=clauderun
Group=clauderun
WorkingDirectory=/opt/claude-daemon
Environment="PYTHONPATH=/home/per/gitrepos/Tmux-Orchestrator"
Environment="MCP_CONFIG_PATH=/opt/claude-daemon/config/mcp_config.json"
ExecStart=/usr/bin/python3 /opt/claude-daemon/claude_daemon.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security
PrivateTmp=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/opt/claude-daemon/logs /home/per/gitrepos/Tmux-Orchestrator/registry

[Install]
WantedBy=multi-user.target
```

### Session Management
```python
# daemon/session_manager.py
import redis
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

class SessionManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)
        self.session_ttl = 3600  # 1 hour
    
    def create_session(self, user_id: str, device_id: str) -> str:
        """Create new session with unique ID"""
        session_id = f"{user_id}_{device_id}_{datetime.now().timestamp()}"
        session_data = {
            "user_id": user_id,
            "device_id": device_id,
            "created_at": datetime.now().isoformat(),
            "context": [],
            "active_projects": []
        }
        self.redis_client.setex(
            f"session:{session_id}",
            self.session_ttl,
            json.dumps(session_data)
        )
        return session_id
    
    def get_context(self, session_id: str) -> str:
        """Get session context for Claude"""
        data = self.redis_client.get(f"session:{session_id}")
        if not data:
            return ""
        
        session = json.loads(data)
        context_items = session.get("context", [])[-10:]  # Last 10 interactions
        return "\n".join([f"User: {c['request']}\nAssistant: {c['response']}" 
                         for c in context_items])
    
    def update_context(self, session_id: str, request: str, response: str):
        """Update session context with new interaction"""
        data = self.redis_client.get(f"session:{session_id}")
        if data:
            session = json.loads(data)
            session["context"].append({
                "request": request,
                "response": response,
                "timestamp": datetime.now().isoformat()
            })
            # Keep only last 50 interactions
            session["context"] = session["context"][-50:]
            self.redis_client.setex(
                f"session:{session_id}",
                self.session_ttl,
                json.dumps(session)
            )
```

## Security Implementation

### JWT Authentication
```python
# daemon/auth_manager.py
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

class AuthManager:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_token(self, user_id: str, device_id: str) -> str:
        """Create JWT token for mobile app"""
        payload = {
            "sub": user_id,
            "device_id": device_id,
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[str]:
        """Verify JWT and return session ID"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return f"{payload['sub']}_{payload['device_id']}"
        except JWTError:
            return None
```

## Configuration

### Daemon Configuration
```yaml
# config/daemon_config.yaml
daemon:
  host: 0.0.0.0
  port: 8080
  workers: 4

claude:
  executable: /usr/local/bin/claude
  working_directory: /home/per/gitrepos/Tmux-Orchestrator
  timeout: 300  # 5 minutes per request

mcp:
  server_url: http://localhost:8081
  api_key: ${MCP_API_KEY}

redis:
  url: redis://localhost:6379
  session_ttl: 3600

security:
  jwt_secret: ${JWT_SECRET}
  allowed_origins:
    - http://localhost:3000
    - app://orchestrator.mobile

logging:
  level: INFO
  file: /opt/claude-daemon/logs/daemon.log
  max_size: 100MB
  retention: 30d
```

## Deployment

### Setup Script
```bash
#!/bin/bash
# setup_daemon.sh

# Create user
sudo useradd -m -s /bin/bash clauderun

# Create directories
sudo mkdir -p /opt/claude-daemon/{logs,config}
sudo chown -R clauderun:clauderun /opt/claude-daemon

# Install dependencies
pip install -r requirements.txt

# Copy files
sudo cp daemon/* /opt/claude-daemon/
sudo cp daemon/systemd/claude-daemon.service /etc/systemd/system/

# Start services
sudo systemctl daemon-reload
sudo systemctl enable claude-daemon
sudo systemctl start claude-daemon

echo "Claude Daemon installed and started"
```

## Testing

### Integration Test Example
```python
# tests/test_integration/test_daemon_integration.py
import pytest
import asyncio
from websockets import connect

@pytest.mark.asyncio
async def test_project_creation_via_daemon():
    """Test creating project through daemon WebSocket"""
    token = get_test_token()
    
    async with connect(f"ws://localhost:8080/ws/daemon?token={token}") as websocket:
        # Send project creation request
        await websocket.send("Create a new web app project from spec.md")
        
        # Get response
        response = await websocket.recv()
        assert "Project started" in response
        
        # Verify project exists
        await websocket.send("Show status of the project")
        status = await websocket.recv()
        assert "running" in status.lower()
```

## Monitoring and Observability

### Prometheus Metrics
```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics
daemon_requests = Counter('daemon_requests_total', 'Total daemon requests', ['method'])
daemon_response_time = Histogram('daemon_response_seconds', 'Response time')
active_sessions = Gauge('daemon_active_sessions', 'Number of active sessions')
mcp_tool_calls = Counter('mcp_tool_calls_total', 'MCP tool invocations', ['tool'])
```

### Health Check Endpoint
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "claude_running": daemon.claude_proc.poll() is None,
        "active_sessions": daemon.session_manager.count_active(),
        "mcp_connected": await daemon.mcp_client.ping()
    }
```

This enhanced MCP Server specification provides comprehensive integration between the Claude Daemon, mobile app, and Tmux Orchestrator system, enabling intelligent, always-available orchestration capabilities.
# MCP Server for Tmux Orchestrator Specification

## Overview
The MCP (Model Context Protocol) Server provides Claude Code with specialized tools and interfaces for managing Tmux Orchestrator projects. It acts as an intelligent proxy between AI models and the Tmux Orchestrator Web Server, offering enhanced automation, natural language processing, and AI-driven workflow optimization.

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
├── src/
│   ├── tmux_orchestrator_mcp/
│   │   ├── __init__.py
│   │   ├── main.py                   # Entry point
│   │   ├── server.py                 # MCP server implementation
│   │   ├── tools/                    # MCP tools
│   │   │   ├── __init__.py
│   │   │   ├── project_management.py # Project CRUD operations
│   │   │   ├── git_workflows.py      # AI-enhanced git operations
│   │   │   ├── agent_messaging.py    # Agent communication tools
│   │   │   ├── monitoring.py         # Status and health monitoring
│   │   │   ├── automation.py         # Workflow automation tools
│   │   │   └── ai_analysis.py        # AI-powered analysis tools
│   │   ├── models/                   # Data models
│   │   │   ├── __init__.py
│   │   │   ├── mcp_types.py          # MCP protocol types
│   │   │   ├── orchestrator_types.py # Orchestrator-specific types
│   │   │   └── workflow_types.py     # Workflow definition types
│   │   ├── clients/                  # External service clients
│   │   │   ├── __init__.py
│   │   │   ├── web_server_client.py  # Tmux Orchestrator Web Server client
│   │   │   └── ai_client.py          # AI service integrations
│   │   ├── utils/                    # Utility modules
│   │   │   ├── __init__.py
│   │   │   ├── auth.py               # Authentication handling
│   │   │   ├── config.py             # Configuration management
│   │   │   ├── logging.py            # Logging utilities
│   │   │   └── validation.py         # Input validation
│   │   └── schemas/                  # JSON schemas for tools
│   │       ├── project_schema.json
│   │       ├── git_schema.json
│   │       └── message_schema.json
├── tests/                           # Test suite
│   ├── __init__.py
│   ├── conftest.py                  # Test configuration
│   ├── test_tools/                  # Tool-specific tests
│   │   ├── test_project_management.py
│   │   ├── test_git_workflows.py
│   │   └── test_monitoring.py
│   ├── test_integration/            # Integration tests
│   │   └── test_web_server_integration.py
│   └── fixtures/                    # Test data
│       ├── sample_projects.json
│       └── mock_responses.json
├── docs/                           # Documentation
│   ├── api.md                      # API documentation
│   ├── tools.md                    # Tool specifications
│   ├── deployment.md               # Deployment guide
│   └── examples/                   # Usage examples
│       ├── claude_code_config.md
│       └── workflow_examples.md
└── config/                         # Configuration files
    ├── mcp_config.json             # MCP server configuration
    ├── logging_config.yaml         # Logging configuration
    └── tools_manifest.json         # Available tools manifest
```

## Technology Stack

### Core Technologies
- **Python 3.11+**: For consistency with Tmux Orchestrator
- **MCP SDK**: Model Context Protocol implementation
- **FastAPI**: For HTTP endpoints and documentation
- **Pydantic**: Data validation and serialization
- **httpx**: Async HTTP client for Web Server communication

### Key Dependencies
```toml
# pyproject.toml
[project]
name = "tmux-orchestrator-mcp"
version = "1.0.0"
dependencies = [
    "mcp>=1.0.0",
    "fastapi>=0.104.0",
    "httpx>=0.25.0",
    "pydantic>=2.0.0",
    "anthropic>=0.7.0",
    "pydantic-settings>=2.0.0",
    "structlog>=23.1.0",
    "tenacity>=8.2.0",
    "jsonschema>=4.19.0",
    "python-jose[cryptography]>=3.3.0",
    "redis>=5.0.0"
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

## MCP Tool Specifications

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
        "description": "Absolute path to the project directory"
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
      }
    },
    "required": ["project_name", "project_path", "specification"]
  }
}
```

#### list_orchestration_projects
```json
{
  "name": "list_orchestration_projects",
  "description": "List all orchestration projects with optional filtering",
  "inputSchema": {
    "type": "object",
    "properties": {
      "status_filter": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["creating", "running", "paused", "completed", "failed"]
        },
        "description": "Filter projects by status"
      },
      "limit": {
        "type": "integer",
        "minimum": 1,
        "maximum": 100,
        "default": 20
      },
      "include_metrics": {
        "type": "boolean",
        "default": false
      }
    }
  }
}
```

### Git Workflow Tools

#### ai_generate_git_workflow
```json
{
  "name": "ai_generate_git_workflow",
  "description": "Generate an optimal git workflow based on project requirements",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": {
        "type": "string",
        "description": "Target project identifier"
      },
      "workflow_description": {
        "type": "string",
        "description": "Natural language description of desired workflow"
      },
      "constraints": {
        "type": "object",
        "properties": {
          "max_branches": {"type": "integer", "default": 5},
          "require_reviews": {"type": "boolean", "default": true},
          "auto_merge": {"type": "boolean", "default": false}
        }
      }
    },
    "required": ["project_id", "workflow_description"]
  }
}
```

#### smart_conflict_resolution
```json
{
  "name": "smart_conflict_resolution",
  "description": "AI-assisted git conflict resolution with context analysis",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": {"type": "string"},
      "conflict_files": {
        "type": "array",
        "items": {"type": "string"}
      },
      "resolution_strategy": {
        "type": "string",
        "enum": ["auto", "manual", "hybrid"],
        "default": "hybrid"
      },
      "preserve_functionality": {
        "type": "boolean",
        "default": true
      }
    },
    "required": ["project_id", "conflict_files"]
  }
}
```

### Agent Communication Tools

#### send_intelligent_message
```json
{
  "name": "send_intelligent_message",
  "description": "Send context-aware message to orchestration agents",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": {"type": "string"},
      "target_agent": {
        "type": "string",
        "enum": ["orchestrator", "developer", "tester", "testrunner", "pm", "devops", "all"]
      },
      "message_intent": {
        "type": "string",
        "enum": ["status_request", "task_assignment", "guidance", "coordination", "emergency"]
      },
      "content": {"type": "string"},
      "include_context": {
        "type": "boolean",
        "description": "Whether to include current project context",
        "default": true
      },
      "priority": {
        "type": "string",
        "enum": ["low", "normal", "high", "urgent"],
        "default": "normal"
      },
      "expect_response": {
        "type": "boolean",
        "default": false
      }
    },
    "required": ["project_id", "target_agent", "content"]
  }
}
```

### Monitoring and Analysis Tools

#### analyze_project_health
```json
{
  "name": "analyze_project_health",
  "description": "Comprehensive AI analysis of project health and recommendations",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": {"type": "string"},
      "analysis_depth": {
        "type": "string",
        "enum": ["quick", "standard", "comprehensive"],
        "default": "standard"
      },
      "include_predictions": {
        "type": "boolean",
        "description": "Include completion time predictions",
        "default": true
      },
      "focus_areas": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["performance", "quality", "timeline", "team_efficiency", "blockers"]
        }
      }
    },
    "required": ["project_id"]
  }
}
```

#### generate_status_summary
```json
{
  "name": "generate_status_summary",
  "description": "Generate human-readable project status summary with insights",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_ids": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Projects to include in summary"
      },
      "summary_type": {
        "type": "string",
        "enum": ["executive", "technical", "timeline"],
        "default": "executive"
      },
      "include_recommendations": {
        "type": "boolean",
        "default": true
      }
    }
  }
}
```

### Automation Tools

#### create_automation_workflow
```json
{
  "name": "create_automation_workflow",
  "description": "Create automated workflow from natural language description",
  "inputSchema": {
    "type": "object",
    "properties": {
      "workflow_name": {"type": "string"},
      "description": {
        "type": "string",
        "description": "Natural language workflow description"
      },
      "trigger_conditions": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "event": {"type": "string"},
            "condition": {"type": "string"}
          }
        }
      },
      "target_projects": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "required": ["workflow_name", "description"]
  }
}
```

## Implementation Architecture

### MCP Server Core
```python
# src/tmux_orchestrator_mcp/server.py
import asyncio
from typing import Any, Sequence
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

from .tools import (
    ProjectManagementTools,
    GitWorkflowTools,
    AgentMessagingTools,
    MonitoringTools,
    AutomationTools
)
from .clients.web_server_client import WebServerClient
from .utils.config import Config

class TmuxOrchestratorMCPServer:
    def __init__(self, config: Config):
        self.config = config
        self.server = Server("tmux-orchestrator-mcp")
        self.web_client = WebServerClient(config.web_server_url, config.api_key)
        
        # Initialize tool handlers
        self.project_tools = ProjectManagementTools(self.web_client)
        self.git_tools = GitWorkflowTools(self.web_client)
        self.messaging_tools = AgentMessagingTools(self.web_client)
        self.monitoring_tools = MonitoringTools(self.web_client)
        self.automation_tools = AutomationTools(self.web_client)
        
        self._register_tools()
    
    def _register_tools(self):
        """Register all MCP tools with the server"""
        tools = [
            # Project management
            *self.project_tools.get_tools(),
            # Git workflows
            *self.git_tools.get_tools(),
            # Agent messaging
            *self.messaging_tools.get_tools(),
            # Monitoring
            *self.monitoring_tools.get_tools(),
            # Automation
            *self.automation_tools.get_tools(),
        ]
        
        for tool in tools:
            self.server.list_tools.append(tool)
```

### Web Server Client
```python
# src/tmux_orchestrator_mcp/clients/web_server_client.py
import httpx
from typing import Dict, Any, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

class WebServerClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new orchestration project"""
        response = await self.client.post(
            f"{self.base_url}/api/v1/projects",
            json=project_data
        )
        response.raise_for_status()
        return response.json()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def send_message(self, project_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send message to project agent"""
        response = await self.client.post(
            f"{self.base_url}/api/v1/projects/{project_id}/messages",
            json=message_data
        )
        response.raise_for_status()
        return response.json()
    
    async def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Get comprehensive project status"""
        response = await self.client.get(
            f"{self.base_url}/api/v1/projects/{project_id}/status"
        )
        response.raise_for_status()
        return response.json()
```

### AI Enhancement Layer
```python
# src/tmux_orchestrator_mcp/tools/ai_analysis.py
from anthropic import AsyncAnthropic
from typing import Dict, Any, List

class AIAnalysisTools:
    def __init__(self, anthropic_client: AsyncAnthropic):
        self.ai = anthropic_client
    
    async def analyze_project_context(self, project_data: Dict[str, Any]) -> str:
        """Generate contextual analysis of project state"""
        prompt = f"""
        Analyze this Tmux Orchestrator project and provide insights:
        
        Project: {project_data['name']}
        Status: {project_data['status']}
        Agents: {[agent['role'] for agent in project_data['agents']]}
        Progress: {project_data['progress'] * 100:.1f}%
        
        Git Info:
        - Branch: {project_data['git_info']['branch']}
        - Uncommitted changes: {project_data['git_info']['uncommitted_changes']}
        - Conflicts: {project_data['git_info']['conflicts']}
        
        Provide:
        1. Health assessment (1-10 scale)
        2. Key blockers and risks
        3. Recommended next actions
        4. Estimated completion timeline
        """
        
        response = await self.ai.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    async def generate_git_workflow(self, description: str, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Generate optimal git workflow configuration"""
        prompt = f"""
        Create a git workflow configuration for: {description}
        
        Constraints:
        - Max branches: {constraints.get('max_branches', 5)}
        - Require reviews: {constraints.get('require_reviews', True)}
        - Auto-merge: {constraints.get('auto_merge', False)}
        
        Return a JSON configuration with:
        - Branch strategy
        - Merge policies
        - Review requirements
        - Automation rules
        """
        
        response = await self.ai.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse and validate the AI response
        import json
        try:
            return json.loads(response.content[0].text)
        except json.JSONDecodeError:
            # Fallback to default configuration
            return self._default_git_workflow(constraints)
```

## Configuration and Deployment

### MCP Configuration
```json
// config/mcp_config.json
{
  "server": {
    "name": "tmux-orchestrator-mcp",
    "version": "1.0.0",
    "description": "MCP server for Tmux Orchestrator integration"
  },
  "web_server": {
    "base_url": "${TMUX_ORCHESTRATOR_URL}",
    "api_key": "${TMUX_ORCHESTRATOR_API_KEY}",
    "timeout": 30,
    "retry_attempts": 3
  },
  "ai": {
    "anthropic_api_key": "${ANTHROPIC_API_KEY}",
    "default_model": "claude-3-sonnet-20240229",
    "max_tokens": 2000
  },
  "features": {
    "enable_ai_analysis": true,
    "enable_automated_workflows": true,
    "enable_conflict_resolution": true,
    "cache_responses": true
  },
  "logging": {
    "level": "INFO",
    "format": "json",
    "file": "logs/mcp_server.log"
  }
}
```

### Claude Code Integration
```json
// .mcp.json (for Claude Code)
{
  "mcpServers": {
    "tmux-orchestrator": {
      "command": "uv",
      "args": ["run", "--", "python", "-m", "tmux_orchestrator_mcp"],
      "env": {
        "TMUX_ORCHESTRATOR_URL": "http://localhost:8000",
        "TMUX_ORCHESTRATOR_API_KEY": "your-api-key",
        "ANTHROPIC_API_KEY": "your-anthropic-key"
      }
    }
  }
}
```

### Docker Configuration
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# Create non-root user
RUN useradd -m -u 1000 mcpuser
USER mcpuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health')" || exit 1

EXPOSE 8080

CMD ["uv", "run", "python", "-m", "tmux_orchestrator_mcp"]
```

## Security Implementation

### Authentication Flow
```python
# src/tmux_orchestrator_mcp/utils/auth.py
import jwt
from datetime import datetime, timedelta
from typing import Optional

class AuthManager:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
    
    def create_service_token(self, service_name: str, expires_hours: int = 24) -> str:
        """Create JWT token for service-to-service communication"""
        payload = {
            "service": service_name,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=expires_hours),
            "type": "service"
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")
    
    def validate_token(self, token: str) -> Optional[dict]:
        """Validate and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.InvalidTokenError:
            return None
```

### Input Validation
```python
# src/tmux_orchestrator_mcp/utils/validation.py
from pydantic import BaseModel, validator
from typing import List, Optional
import re

class ProjectCreateRequest(BaseModel):
    project_name: str
    project_path: str
    specification: str
    team_composition: Optional[List[str]] = None
    
    @validator('project_name')
    def validate_project_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Project name must contain only alphanumeric characters, hyphens, and underscores')
        return v
    
    @validator('project_path')
    def validate_project_path(cls, v):
        # Prevent path traversal attacks
        if '..' in v or v.startswith('/tmp') or v.startswith('/var'):
            raise ValueError('Invalid project path')
        return v
```

## Testing Strategy

### Test Configuration
```python
# tests/conftest.py
import pytest
import asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock

@pytest.fixture
def mock_web_client():
    """Mock web server client for testing"""
    client = AsyncMock()
    client.create_project.return_value = {"id": "test-project-123", "status": "created"}
    client.send_message.return_value = {"message_id": "msg-456", "status": "sent"}
    return client

@pytest.fixture
def sample_project_data():
    return {
        "project_name": "test-webapp",
        "project_path": "/tmp/test-project",
        "specification": "# Test Project\nBuild a simple web app",
        "team_composition": ["orchestrator", "developer", "tester"]
    }
```

### Integration Tests
```python
# tests/test_integration/test_web_server_integration.py
import pytest
from tmux_orchestrator_mcp.clients.web_server_client import WebServerClient

@pytest.mark.asyncio
async def test_full_project_lifecycle():
    """Test complete project creation and management lifecycle"""
    client = WebServerClient("http://localhost:8000", "test-api-key")
    
    # Create project
    project_data = {
        "name": "integration-test",
        "path": "/tmp/integration-test",
        "specification": "# Integration Test\nTest project"
    }
    
    project = await client.create_project(project_data)
    assert project["status"] == "created"
    
    # Send message
    message_response = await client.send_message(
        project["id"],
        {"target_agent": "developer", "content": "Start implementation"}
    )
    assert message_response["status"] == "sent"
    
    # Check status
    status = await client.get_project_status(project["id"])
    assert status["id"] == project["id"]
```

## Documentation and Examples

### Usage Examples for Claude Code

#### Basic Project Creation
```markdown
# Creating a new project with MCP tools

You can create a new Tmux Orchestrator project by using the create_orchestration_project tool:

{
  "project_name": "my-webapp",
  "project_path": "/home/user/projects/my-webapp",
  "specification": "# Web Application\nCreate a FastAPI web application with user authentication and a dashboard.",
  "team_composition": ["orchestrator", "developer", "tester", "devops"],
  "project_size": "medium",
  "auto_start": true
}
```

#### AI-Powered Git Workflow Generation
```markdown
# Generate optimal git workflow

Use ai_generate_git_workflow to create a workflow based on natural language:

{
  "project_id": "my-webapp-123",
  "workflow_description": "I need a workflow that supports feature branches, requires code review, and automatically deploys to staging when merged to develop branch",
  "constraints": {
    "max_branches": 10,
    "require_reviews": true,
    "auto_merge": false
  }
}
```

## Deployment and Operations

### Production Deployment
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  mcp-server:
    build: .
    environment:
      - TMUX_ORCHESTRATOR_URL=https://orchestrator.example.com
      - TMUX_ORCHESTRATOR_API_KEY=${ORCHESTRATOR_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    ports:
      - "8080:8080"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8080/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Monitoring Configuration
```python
# Prometheus metrics for MCP server
from prometheus_client import Counter, Histogram, Gauge

tool_calls = Counter('mcp_tool_calls_total', 'Total MCP tool calls', ['tool_name', 'status'])
response_time = Histogram('mcp_response_time_seconds', 'MCP tool response time', ['tool_name'])
active_projects = Gauge('mcp_active_projects', 'Number of active projects being managed')
```

This MCP Server specification provides a comprehensive bridge between AI models like Claude and the Tmux Orchestrator system, enabling intelligent automation, natural language interfaces, and enhanced workflow management capabilities.
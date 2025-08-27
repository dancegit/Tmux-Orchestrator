# Tmux Orchestrator Web Server Specification

## Overview
The Web Server extends the existing Tmux Orchestrator with REST APIs and WebSocket support, enabling remote management of orchestration projects, git workflows, agent messaging, and real-time monitoring.

## Project Structure
```
Tmux-Orchestrator/
├── auto_orchestrate.py              # Existing
├── claude_control.py                # Existing
├── tmux_utils.py                     # Existing
├── monitoring_dashboard.py          # Existing
├── session_state.py                 # Existing
├── sync_coordinator.py              # Existing
├── concurrent_orchestration.py      # Existing
├── web_server/                       # NEW: Web Server Components
│   ├── __init__.py
│   ├── app.py                        # Main FastAPI application
│   ├── models.py                     # Pydantic models for API schemas
│   ├── routes/                       # API endpoints
│   │   ├── __init__.py
│   │   ├── projects.py               # Project creation/management
│   │   ├── git.py                    # Git workspace operations
│   │   ├── messaging.py              # Agent messaging
│   │   ├── monitoring.py             # Status and monitoring
│   │   └── auth.py                   # Authentication endpoints
│   ├── sockets/                      # WebSocket handlers
│   │   ├── __init__.py
│   │   └── updates.py                # Real-time updates
│   ├── utils/                        # Helper utilities
│   │   ├── __init__.py
│   │   ├── auth.py                   # Authentication utilities
│   │   ├── tmux_integration.py       # Wrappers for existing modules
│   │   └── security.py               # Security helpers
│   ├── config.py                     # Configuration management
│   ├── middleware.py                 # FastAPI middleware
│   └── tests/                        # Unit and integration tests
│       ├── test_projects.py
│       ├── test_git.py
│       ├── test_messaging.py
│       └── test_websockets.py
├── requirements.txt                  # Updated with web dependencies
├── Dockerfile                        # For containerization
├── docker-compose.yml               # Local development setup
└── web_server_config.yaml           # Configuration file
```

## Technology Stack

### Core Technologies
- **Python 3.11+**: Maintains compatibility with existing codebase
- **FastAPI**: Modern async web framework with automatic API documentation
- **Uvicorn**: ASGI server for production deployment
- **Pydantic**: Data validation and serialization (already in use)
- **Redis**: For WebSocket session management and pub/sub

### Key Dependencies
```
fastapi[all]==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0
redis==5.0.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
slowapi==0.1.9
prometheus-client==0.19.0
```

## API Specifications

### REST Endpoints

#### Authentication
- `POST /auth/login` - User authentication
- `POST /auth/refresh` - Token refresh
- `POST /auth/logout` - User logout

#### Project Management
- `POST /api/v1/projects` - Create new orchestration project
- `GET /api/v1/projects` - List all projects with filtering
- `GET /api/v1/projects/{project_id}` - Get project details
- `PUT /api/v1/projects/{project_id}` - Update project configuration
- `DELETE /api/v1/projects/{project_id}` - Terminate project
- `POST /api/v1/projects/{project_id}/resume` - Resume paused project

#### Git Workspace Management
- `GET /api/v1/projects/{project_id}/git/status` - Get git status
- `POST /api/v1/projects/{project_id}/git/commit` - Create commit
- `POST /api/v1/projects/{project_id}/git/push` - Push changes
- `POST /api/v1/projects/{project_id}/git/merge` - Merge branches
- `GET /api/v1/projects/{project_id}/git/log` - Get commit history
- `POST /api/v1/projects/{project_id}/git/resolve` - Resolve conflicts

#### Agent Messaging
- `POST /api/v1/projects/{project_id}/messages` - Send message to agent
- `GET /api/v1/projects/{project_id}/messages` - Get message history
- `GET /api/v1/projects/{project_id}/agents` - List project agents
- `GET /api/v1/projects/{project_id}/agents/{agent_id}/status` - Get agent status

#### Monitoring
- `GET /api/v1/projects/{project_id}/status` - Get project status
- `GET /api/v1/projects/{project_id}/metrics` - Get performance metrics
- `GET /api/v1/system/health` - System health check
- `GET /api/v1/system/metrics` - System-wide metrics

### WebSocket Endpoints

#### Real-time Updates
- `WS /ws/projects/{project_id}` - Project-specific updates
- `WS /ws/system` - System-wide notifications

#### WebSocket Message Types
```json
{
  "type": "agent_status_update",
  "data": {
    "agent_id": "developer",
    "status": "active",
    "current_task": "Implementing authentication",
    "timestamp": "2024-08-17T15:30:00Z"
  }
}

{
  "type": "git_event",
  "data": {
    "event": "commit",
    "branch": "feature/auth",
    "hash": "abc123",
    "message": "Add login endpoint",
    "author": "developer-agent"
  }
}

{
  "type": "project_status_change",
  "data": {
    "project_id": "webapp-impl",
    "status": "running",
    "progress": 0.65,
    "estimated_completion": "2024-08-17T18:00:00Z"
  }
}
```

## Data Models

### Core Pydantic Models
```python
class ProjectSpec(BaseModel):
    name: str
    description: str
    project_path: str
    spec_content: str
    team_composition: Optional[List[str]] = None
    size: str = "medium"
    priority: str = "normal"

class ProjectStatus(BaseModel):
    id: str
    name: str
    status: Literal["creating", "running", "paused", "completed", "failed"]
    progress: float
    agents: List[AgentStatus]
    git_info: GitStatus
    created_at: datetime
    updated_at: datetime

class AgentStatus(BaseModel):
    role: str
    window_id: str
    status: Literal["active", "idle", "exhausted", "failed"]
    current_task: Optional[str]
    last_check_in: Optional[datetime]
    credit_status: str

class AgentMessage(BaseModel):
    target_agent: str
    content: str
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    requires_response: bool = False

class GitStatus(BaseModel):
    branch: str
    commit_hash: str
    uncommitted_changes: bool
    conflicts: List[str]
    worktree_path: str
```

## Integration with Existing Components

### Tmux Integration
```python
# web_server/utils/tmux_integration.py
from tmux_utils import TmuxOrchestrator
from session_state import SessionStateManager

class TmuxWebIntegration:
    def __init__(self):
        self.tmux = TmuxOrchestrator()
        self.session_manager = SessionStateManager(Path.cwd())
    
    async def create_project(self, spec: ProjectSpec) -> str:
        # Use auto_orchestrate.py functionality
        # Return project_id
        
    async def send_message_to_agent(self, project_id: str, agent: str, message: str):
        # Use existing send-claude-message.sh functionality
        
    async def get_project_status(self, project_id: str) -> ProjectStatus:
        # Use session_state.py and claude_control.py
```

### Git Integration
```python
# Integration with sync_coordinator.py
from sync_coordinator import GitSyncCoordinator

class GitWebIntegration:
    def __init__(self):
        self.git_sync = GitSyncCoordinator()
    
    async def get_git_status(self, project_id: str) -> GitStatus:
        # Use existing git functionality
        
    async def create_commit(self, project_id: str, message: str) -> str:
        # Automated commit via sync_coordinator
```

## Security Implementation

### Authentication & Authorization
- **JWT Tokens**: RS256 signed tokens with 1-hour expiration
- **Role-Based Access**: Admin, Manager, Viewer roles
- **API Key Support**: For service-to-service communication
- **Rate Limiting**: Per-user and per-endpoint limits

### Security Headers
```python
# Middleware configuration
security_headers = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'"
}
```

### Input Validation
- **Pydantic Models**: Strict validation for all inputs
- **Command Injection Prevention**: Sanitize all tmux/git commands
- **Path Traversal Protection**: Validate file paths
- **XSS Prevention**: Escape HTML in responses

### Secrets Management
```python
# config.py
import os
from cryptography.fernet import Fernet

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    JWT_ALGORITHM = "RS256"
    JWT_EXPIRATION = 3600  # 1 hour
    
    # Encryption for sensitive data
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
    cipher_suite = Fernet(ENCRYPTION_KEY.encode()) if ENCRYPTION_KEY else None
```

## Deployment Architecture

### Docker Configuration
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tmux \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 orchestrator
USER orchestrator

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/system/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "web_server.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose for Development
```yaml
# docker-compose.yml
version: '3.8'

services:
  orchestrator-web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}
    volumes:
      - ./registry:/app/registry
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

volumes:
  redis_data:
```

### Production Deployment
- **Container Orchestration**: Kubernetes or Docker Swarm
- **Load Balancer**: Nginx or AWS ALB
- **SSL/TLS**: Let's Encrypt or AWS Certificate Manager
- **Monitoring**: Prometheus + Grafana for metrics
- **Logging**: ELK Stack or AWS CloudWatch
- **Backup**: Automated backup of registry data

## Monitoring & Observability

### Metrics Collection
```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# Custom metrics
active_projects = Gauge('orchestrator_active_projects', 'Number of active projects')
api_requests = Counter('orchestrator_api_requests_total', 'Total API requests', ['method', 'endpoint'])
response_time = Histogram('orchestrator_response_time_seconds', 'Response time')
```

### Health Checks
- **Liveness Probe**: `/api/v1/system/health`
- **Readiness Probe**: `/api/v1/system/ready`
- **Dependency Checks**: Tmux, Git, Redis availability

### Logging Strategy
```python
import structlog

logger = structlog.get_logger()

# Structured logging example
logger.info(
    "project_created",
    project_id=project.id,
    user_id=user.id,
    team_size=len(project.agents),
    duration=create_time
)
```

## Testing Strategy

### Test Categories
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: API endpoint testing
3. **WebSocket Tests**: Real-time communication testing
4. **Load Tests**: Performance and scalability
5. **Security Tests**: Authentication and authorization

### Test Configuration
```python
# conftest.py
import pytest
from fastapi.testclient import TestClient
from web_server.app import app

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def auth_headers(test_client):
    # Create test user and return auth headers
    response = test_client.post("/auth/login", json={
        "username": "test_user",
        "password": "test_password"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

## Migration Strategy

### Implementation Phases
1. **Phase 1**: Core API development (projects, basic messaging)
2. **Phase 2**: WebSocket implementation and real-time features
3. **Phase 3**: Advanced git workflow automation
4. **Phase 4**: Monitoring and observability enhancement
5. **Phase 5**: Production hardening and scaling

### Backward Compatibility
- Existing command-line tools remain functional
- Web API provides additional access methods
- Configuration remains file-based with API overrides
- No breaking changes to existing workflows

## Configuration Example

```yaml
# web_server_config.yaml
server:
  host: "0.0.0.0"
  port: 8000
  debug: false
  workers: 4

security:
  jwt_secret_key: "${JWT_SECRET_KEY}"
  jwt_algorithm: "RS256"
  jwt_expiration_hours: 1
  rate_limit_per_minute: 100

redis:
  url: "${REDIS_URL}"
  max_connections: 20

tmux:
  orchestrator_path: "/app"
  registry_path: "/app/registry"
  max_concurrent_projects: 10

logging:
  level: "INFO"
  format: "json"
  file: "/app/logs/web_server.log"

monitoring:
  prometheus_enabled: true
  health_check_interval: 30
```

This specification provides a comprehensive foundation for implementing the Web Server component that seamlessly integrates with the existing Tmux Orchestrator while adding powerful remote management capabilities.
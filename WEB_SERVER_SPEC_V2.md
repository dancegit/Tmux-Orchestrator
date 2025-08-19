# Tmux Orchestrator Web Server Specification V2
## Enhanced with Claude Daemon Architecture

## Overview
The Web Server V2 transforms from a direct API provider to a comprehensive platform that integrates with the Claude Daemon, providing both traditional REST APIs and daemon-mediated intelligent orchestration. This dual-mode architecture enables backward compatibility while offering enhanced AI-driven capabilities through the persistent Claude daemon.

## Architecture Evolution

### V1 Architecture (Direct)
```
Client → Web Server → Tmux Orchestrator
         ↓
      Database
```

### V2 Architecture (Daemon-Enhanced)
```
Client → Web Server → Claude Daemon → MCP Tools → Tmux Orchestrator
         ↓              ↓
      Database     Session State (Redis)
```

## Repository Structure (Enhanced)
```
Tmux-Orchestrator/
├── web_server/
│   ├── __init__.py
│   ├── app.py                          # Main FastAPI application
│   ├── daemon_integration/              # NEW: Claude Daemon integration
│   │   ├── __init__.py
│   │   ├── daemon_proxy.py             # Proxy requests to daemon
│   │   ├── session_bridge.py           # Bridge web sessions to daemon
│   │   ├── request_transformer.py      # Transform REST to daemon format
│   │   └── response_adapter.py         # Adapt daemon responses to REST
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── projects.py                 # Enhanced with daemon options
│   │   ├── daemon.py                   # NEW: Direct daemon interaction
│   │   ├── natural_language.py         # NEW: NL processing endpoints
│   │   ├── batch.py                    # NEW: Batch processing
│   │   ├── insights.py                 # NEW: AI insights endpoints
│   │   ├── git.py
│   │   ├── messaging.py
│   │   ├── monitoring.py
│   │   └── auth.py
│   ├── sockets/
│   │   ├── __init__.py
│   │   ├── updates.py                  # Real-time updates
│   │   ├── daemon_relay.py             # NEW: Relay daemon events
│   │   └── collaborative.py            # NEW: Multi-user coordination
│   ├── services/
│   │   ├── __init__.py
│   │   ├── orchestrator_service.py     # Direct orchestrator control
│   │   ├── daemon_service.py           # NEW: Daemon communication
│   │   ├── intelligence_service.py     # NEW: AI analysis
│   │   ├── session_service.py          # NEW: Session management
│   │   └── queue_service.py            # NEW: Task queueing
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base_models.py              # Existing Pydantic models
│   │   ├── daemon_models.py            # NEW: Daemon-specific models
│   │   ├── session_models.py           # NEW: Session state models
│   │   └── intelligence_models.py      # NEW: AI response models
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── daemon_auth.py              # NEW: Daemon authentication
│   │   ├── natural_language.py         # NEW: NL processing utils
│   │   └── metrics.py                  # NEW: Enhanced metrics
│   ├── config.py
│   ├── middleware.py
│   └── tests/
├── daemon_manager/                      # NEW: Daemon lifecycle management
│   ├── __init__.py
│   ├── daemon_supervisor.py            # Supervise daemon process
│   ├── health_monitor.py               # Monitor daemon health
│   ├── resource_manager.py             # Manage daemon resources
│   └── deployment.py                   # Deployment utilities
├── web_server_config.yaml
├── daemon_config.yaml                  # NEW: Daemon configuration
├── docker-compose.yml                  # Updated with daemon service
└── Dockerfile.daemon                   # NEW: Daemon container
```

## Technology Stack (Enhanced)

### Core Technologies
- **Python 3.11+**: Primary language
- **FastAPI**: Web framework with async support
- **Uvicorn**: ASGI server
- **Redis**: Session state and pub/sub
- **PostgreSQL**: Persistent storage
- **Claude SDK**: Daemon communication

### New Dependencies
```python
# requirements.txt additions
anthropic>=0.25.0           # Claude API
redis>=5.0.0                # Session management
asyncio-mqtt>=0.16.0        # Event streaming
python-multipart>=0.0.6     # File uploads
aiofiles>=23.0.0            # Async file operations
langchain>=0.1.0            # LLM utilities
tiktoken>=0.5.0             # Token counting
websocket-client>=1.6.0     # Daemon WebSocket
pydantic-settings>=2.0.0    # Configuration
```

## Enhanced API Specifications

### Daemon-Aware Endpoints

#### Natural Language Project Creation
```python
# POST /api/v2/projects/natural
{
    "prompt": "Create a React dashboard with user authentication and real-time charts",
    "context": {
        "preferred_stack": "typescript",
        "deployment_target": "vercel",
        "team_size_preference": "medium"
    },
    "use_daemon": true
}

# Response
{
    "project_id": "dashboard-2024-01",
    "interpretation": {
        "understood_requirements": [
            "React-based dashboard application",
            "User authentication system",
            "Real-time data visualization with charts"
        ],
        "suggested_team": ["orchestrator", "developer", "tester", "devops"],
        "estimated_duration": "3-5 days"
    },
    "daemon_session_id": "sess_abc123",
    "conversation_url": "/api/v2/daemon/chat/sess_abc123"
}
```

#### Batch Processing with Intelligence
```python
# POST /api/v2/batch/process
{
    "specifications": [
        {"content": "...spec1...", "priority": "high"},
        {"content": "...spec2...", "priority": "medium"},
        {"content": "...spec3...", "priority": "low"}
    ],
    "processing_mode": "intelligent",  # Uses daemon for smart scheduling
    "optimization_goals": ["minimize_time", "maximize_quality"],
    "notification_webhook": "https://example.com/webhook"
}

# Response
{
    "batch_id": "batch_2024_01_15",
    "queue_status": {
        "total": 3,
        "processing_order": ["spec1", "spec3", "spec2"],  # Daemon optimized
        "reasoning": "Prioritized based on dependencies and resource availability"
    },
    "estimated_completion": "2024-01-16T10:00:00Z",
    "monitoring_url": "/api/v2/batch/batch_2024_01_15/status"
}
```

#### Intelligent Team Communication
```python
# POST /api/v2/projects/{project_id}/communicate
{
    "intent": "request_status",  # Daemon interprets intent
    "natural_language": "How's the authentication feature coming along?",
    "target_context": "development_team",
    "include_analysis": true
}

# Response
{
    "daemon_interpretation": {
        "understood_intent": "Status check on authentication implementation",
        "relevant_agents": ["developer", "tester"],
        "context_applied": true
    },
    "responses": [
        {
            "agent": "developer",
            "message": "Authentication endpoints complete, working on JWT integration",
            "progress": 0.75,
            "blockers": []
        },
        {
            "agent": "tester",
            "message": "Writing integration tests for login flow",
            "progress": 0.40,
            "dependencies": ["developer completion"]
        }
    ],
    "ai_summary": "Authentication feature is 65% complete. Backend ready, frontend and tests in progress."
}
```

### Daemon Service Integration

```python
# services/daemon_service.py
import asyncio
from typing import Dict, Any, Optional
import aiohttp
from anthropic import AsyncAnthropic

class DaemonService:
    def __init__(self, config: DaemonConfig):
        self.config = config
        self.daemon_url = config.daemon_url
        self.anthropic = AsyncAnthropic(api_key=config.api_key)
        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        
    async def initialize(self):
        """Initialize daemon connection"""
        self.session = aiohttp.ClientSession()
        await self.connect_websocket()
        await self.verify_daemon_health()
        
    async def connect_websocket(self):
        """Establish WebSocket connection to daemon"""
        ws_url = f"{self.daemon_url}/ws/server"
        self.websocket = await self.session.ws_connect(ws_url)
        
        # Start listening for daemon events
        asyncio.create_task(self.listen_daemon_events())
        
    async def listen_daemon_events(self):
        """Listen for daemon events and relay to clients"""
        async for msg in self.websocket:
            if msg.type == aiohttp.WSMsgType.TEXT:
                event = json.loads(msg.data)
                await self.handle_daemon_event(event)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"Daemon WebSocket error: {msg.data}")
                await self.reconnect()
                
    async def process_natural_language(
        self,
        prompt: str,
        context: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> DaemonResponse:
        """Process natural language through daemon"""
        request = {
            "type": "natural_language",
            "prompt": prompt,
            "context": context,
            "session_id": session_id or self.create_session_id()
        }
        
        response = await self.send_to_daemon(request)
        
        # Enhance response with additional analysis if needed
        if context.get("include_analysis"):
            response["analysis"] = await self.analyze_response(response)
            
        return DaemonResponse(**response)
        
    async def send_to_daemon(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request to daemon and await response"""
        request_id = str(uuid.uuid4())
        request["request_id"] = request_id
        
        # Store pending request
        self.pending_requests[request_id] = asyncio.Future()
        
        # Send via WebSocket
        await self.websocket.send_json(request)
        
        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(
                self.pending_requests[request_id],
                timeout=self.config.request_timeout
            )
            return response
        except asyncio.TimeoutError:
            raise DaemonTimeoutError(f"Request {request_id} timed out")
        finally:
            self.pending_requests.pop(request_id, None)
            
    async def create_intelligent_batch(
        self,
        specifications: List[Dict[str, Any]],
        optimization_goals: List[str]
    ) -> BatchPlan:
        """Use daemon to create optimized batch processing plan"""
        request = {
            "type": "batch_planning",
            "specifications": specifications,
            "optimization_goals": optimization_goals,
            "system_state": await self.get_system_state()
        }
        
        response = await self.send_to_daemon(request)
        
        return BatchPlan(
            order=response["processing_order"],
            reasoning=response["reasoning"],
            estimated_duration=response["estimated_duration"],
            resource_allocation=response["resource_allocation"]
        )
```

### WebSocket Relay for Real-Time Updates

```python
# sockets/daemon_relay.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio

class DaemonEventRelay:
    def __init__(self, daemon_service: DaemonService):
        self.daemon_service = daemon_service
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.session_mapping: Dict[WebSocket, str] = {}
        
    async def connect(self, websocket: WebSocket, project_id: str):
        """Connect client WebSocket and subscribe to daemon events"""
        await websocket.accept()
        
        # Add to connection pool
        if project_id not in self.connections:
            self.connections[project_id] = set()
        self.connections[project_id].add(websocket)
        
        # Map WebSocket to daemon session
        daemon_session = await self.daemon_service.create_session(project_id)
        self.session_mapping[websocket] = daemon_session.id
        
        # Send initial state
        await self.send_initial_state(websocket, project_id)
        
    async def relay_daemon_event(self, event: DaemonEvent):
        """Relay daemon event to relevant clients"""
        project_id = event.project_id
        
        if project_id in self.connections:
            # Transform daemon event to client format
            client_event = self.transform_event(event)
            
            # Broadcast to all connected clients
            disconnected = set()
            for websocket in self.connections[project_id]:
                try:
                    await websocket.send_json(client_event)
                except Exception:
                    disconnected.add(websocket)
                    
            # Clean up disconnected clients
            for ws in disconnected:
                self.connections[project_id].discard(ws)
                self.session_mapping.pop(ws, None)
                
    def transform_event(self, event: DaemonEvent) -> Dict[str, Any]:
        """Transform daemon event to client-friendly format"""
        return {
            "type": event.type,
            "timestamp": event.timestamp.isoformat(),
            "data": {
                "project_id": event.project_id,
                "agent": event.agent,
                "message": event.message,
                "metadata": event.metadata
            },
            "ai_insight": event.ai_analysis  # Daemon-provided insight
        }
```

### Session Bridge for Multi-User Support

```python
# daemon_integration/session_bridge.py
class SessionBridge:
    def __init__(self, redis_client: Redis, daemon_service: DaemonService):
        self.redis = redis_client
        self.daemon = daemon_service
        self.active_sessions: Dict[str, WebSession] = {}
        
    async def create_web_session(
        self,
        user_id: str,
        project_id: Optional[str] = None
    ) -> WebSession:
        """Create web session linked to daemon session"""
        # Create daemon session
        daemon_session = await self.daemon.create_session({
            "user_id": user_id,
            "project_id": project_id,
            "interface": "web",
            "capabilities": ["full_control"]
        })
        
        # Create web session
        web_session = WebSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            daemon_session_id=daemon_session.id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        
        # Store in Redis
        await self.redis.setex(
            f"session:{web_session.id}",
            self.SESSION_TTL,
            web_session.json()
        )
        
        self.active_sessions[web_session.id] = web_session
        
        return web_session
        
    async def bridge_request(
        self,
        session_id: str,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Bridge web request to daemon with session context"""
        session = await self.get_session(session_id)
        
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")
            
        # Add session context to request
        request["daemon_session_id"] = session.daemon_session_id
        request["user_context"] = await self.get_user_context(session.user_id)
        
        # Send to daemon
        response = await self.daemon.send_to_daemon(request)
        
        # Update session activity
        await self.update_session_activity(session_id)
        
        return response
        
    async def sync_session_state(self, session_id: str):
        """Synchronize session state between web and daemon"""
        web_session = self.active_sessions.get(session_id)
        if not web_session:
            return
            
        # Get daemon session state
        daemon_state = await self.daemon.get_session_state(
            web_session.daemon_session_id
        )
        
        # Update Redis with merged state
        merged_state = {
            **web_session.dict(),
            "daemon_state": daemon_state,
            "sync_timestamp": datetime.utcnow().isoformat()
        }
        
        await self.redis.setex(
            f"session:{session_id}",
            self.SESSION_TTL,
            json.dumps(merged_state)
        )
```

### Intelligent Monitoring Dashboard

```python
# routes/monitoring.py
@router.get("/api/v2/monitoring/intelligent-dashboard")
async def get_intelligent_dashboard(
    daemon_service: DaemonService = Depends(get_daemon_service),
    session: WebSession = Depends(get_session)
):
    """Get AI-enhanced monitoring dashboard"""
    
    # Get raw metrics
    raw_metrics = await get_system_metrics()
    
    # Get daemon analysis
    analysis_request = {
        "type": "analyze_system_health",
        "metrics": raw_metrics,
        "include_predictions": True,
        "include_recommendations": True
    }
    
    daemon_response = await daemon_service.send_to_daemon(analysis_request)
    
    return {
        "metrics": raw_metrics,
        "ai_analysis": {
            "health_score": daemon_response["health_score"],
            "trend": daemon_response["trend"],
            "predictions": daemon_response["predictions"],
            "alerts": daemon_response["alerts"],
            "recommendations": daemon_response["recommendations"]
        },
        "active_projects": await get_active_projects_with_ai_status(),
        "team_efficiency": daemon_response["team_analysis"],
        "resource_utilization": daemon_response["resource_analysis"]
    }

@router.post("/api/v2/monitoring/ask-ai")
async def ask_monitoring_ai(
    question: str,
    context: Optional[str] = None,
    daemon_service: DaemonService = Depends(get_daemon_service)
):
    """Ask AI about system status"""
    
    # Prepare context
    system_context = {
        "current_metrics": await get_system_metrics(),
        "active_projects": await get_active_projects(),
        "recent_events": await get_recent_events(minutes=30)
    }
    
    if context:
        system_context["user_context"] = context
        
    # Send to daemon
    response = await daemon_service.process_natural_language(
        prompt=question,
        context=system_context,
        session_id=get_current_session_id()
    )
    
    return {
        "question": question,
        "answer": response.content,
        "supporting_data": response.metadata,
        "suggested_actions": response.suggested_actions,
        "confidence": response.confidence
    }
```

### Daemon Lifecycle Management

```python
# daemon_manager/daemon_supervisor.py
import subprocess
import psutil
from typing import Optional

class DaemonSupervisor:
    def __init__(self, config: DaemonConfig):
        self.config = config
        self.daemon_process: Optional[subprocess.Popen] = None
        self.health_monitor = HealthMonitor(config)
        self.resource_manager = ResourceManager(config)
        
    async def start_daemon(self) -> bool:
        """Start the Claude daemon process"""
        if self.is_daemon_running():
            logger.info("Daemon already running")
            return True
            
        try:
            # Start daemon with proper environment
            env = self.prepare_environment()
            
            self.daemon_process = subprocess.Popen(
                [
                    "python", "-m", "daemon.claude_daemon",
                    "--config", self.config.config_path,
                    "--port", str(self.config.daemon_port),
                    "--workers", str(self.config.worker_count)
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # Detach from parent
            )
            
            # Wait for daemon to be ready
            await self.wait_for_daemon_ready()
            
            # Start monitoring
            asyncio.create_task(self.monitor_daemon())
            
            logger.info(f"Daemon started with PID {self.daemon_process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            return False
            
    async def monitor_daemon(self):
        """Monitor daemon health and resources"""
        while self.daemon_process:
            try:
                # Check health
                health = await self.health_monitor.check_daemon_health()
                
                if not health.is_healthy:
                    logger.warning(f"Daemon unhealthy: {health.issues}")
                    await self.handle_unhealthy_daemon(health)
                    
                # Check resources
                resources = await self.resource_manager.check_resources(
                    self.daemon_process.pid
                )
                
                if resources.memory_percent > self.config.max_memory_percent:
                    logger.warning(f"Daemon using {resources.memory_percent}% memory")
                    await self.resource_manager.optimize_memory()
                    
                # Check for errors in logs
                errors = await self.check_daemon_logs()
                if errors:
                    await self.handle_daemon_errors(errors)
                    
                await asyncio.sleep(self.config.monitor_interval)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(5)
                
    async def restart_daemon(self, reason: str = "Manual restart"):
        """Gracefully restart the daemon"""
        logger.info(f"Restarting daemon: {reason}")
        
        # Notify clients
        await self.notify_clients_of_restart()
        
        # Graceful shutdown
        await self.stop_daemon(graceful=True)
        
        # Wait for cleanup
        await asyncio.sleep(5)
        
        # Start new instance
        success = await self.start_daemon()
        
        if success:
            # Restore sessions
            await self.restore_daemon_sessions()
            
        return success
```

### Security Enhancements

```python
# utils/daemon_auth.py
from jose import jwt, JWTError
import secrets

class DaemonAuthManager:
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.signing_key = config.daemon_signing_key
        self.encryption_key = config.daemon_encryption_key
        
    async def create_daemon_token(
        self,
        client_id: str,
        permissions: List[str]
    ) -> str:
        """Create JWT token for daemon communication"""
        payload = {
            "client_id": client_id,
            "permissions": permissions,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=24),
            "nonce": secrets.token_urlsafe(16)
        }
        
        token = jwt.encode(
            payload,
            self.signing_key,
            algorithm="RS256"
        )
        
        # Optionally encrypt sensitive tokens
        if self.config.encrypt_tokens:
            token = self.encrypt_token(token)
            
        return token
        
    async def validate_daemon_request(
        self,
        request: Request,
        required_permissions: List[str]
    ) -> bool:
        """Validate request from daemon"""
        # Extract token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return False
            
        token = auth_header.replace("Bearer ", "")
        
        try:
            # Decrypt if needed
            if self.config.encrypt_tokens:
                token = self.decrypt_token(token)
                
            # Verify JWT
            payload = jwt.decode(
                token,
                self.config.daemon_public_key,
                algorithms=["RS256"]
            )
            
            # Check permissions
            token_permissions = set(payload.get("permissions", []))
            required = set(required_permissions)
            
            if not required.issubset(token_permissions):
                logger.warning(f"Insufficient permissions: {token_permissions} < {required}")
                return False
                
            # Verify nonce to prevent replay
            nonce = payload.get("nonce")
            if await self.is_nonce_used(nonce):
                logger.warning(f"Nonce replay detected: {nonce}")
                return False
                
            await self.mark_nonce_used(nonce)
            
            return True
            
        except JWTError as e:
            logger.error(f"JWT validation failed: {e}")
            return False
```

## Deployment Architecture

### Docker Compose with Daemon

```yaml
# docker-compose.yml
version: '3.8'

services:
  web-server:
    build: 
      context: .
      dockerfile: Dockerfile.web
    ports:
      - "8000:8000"
    environment:
      - DAEMON_URL=http://claude-daemon:8080
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:pass@postgres:5432/orchestrator
    depends_on:
      - claude-daemon
      - redis
      - postgres
    volumes:
      - ./registry:/app/registry
      
  claude-daemon:
    build:
      context: .
      dockerfile: Dockerfile.daemon
    ports:
      - "8080:8080"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - REDIS_URL=redis://redis:6379
      - MCP_SERVER_URL=http://mcp-server:8081
      - CLAUDE_EXECUTABLE=/usr/local/bin/claude
    volumes:
      - ./daemon_data:/opt/daemon/data
      - ./registry:/app/registry
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      
  mcp-server:
    build:
      context: .
      dockerfile: Dockerfile.mcp
    ports:
      - "8081:8081"
    environment:
      - WEB_SERVER_URL=http://web-server:8000
    depends_on:
      - web-server
      
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=orchestrator
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards

volumes:
  redis_data:
  postgres_data:
  grafana_data:
```

### Production Kubernetes Deployment

```yaml
# k8s/daemon-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: claude-daemon
  namespace: orchestrator
spec:
  replicas: 3  # Multiple daemons for HA
  selector:
    matchLabels:
      app: claude-daemon
  template:
    metadata:
      labels:
        app: claude-daemon
    spec:
      containers:
      - name: daemon
        image: orchestrator/claude-daemon:v2.0
        ports:
        - containerPort: 8080
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: claude-secrets
              key: api-key
        - name: REDIS_URL
          value: redis://redis-service:6379
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - claude-daemon
            topologyKey: kubernetes.io/hostname
```

## Monitoring and Observability

### Enhanced Metrics with Daemon

```python
# utils/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info

# Daemon-specific metrics
daemon_requests = Counter(
    'daemon_requests_total',
    'Total daemon requests',
    ['request_type', 'status']
)

daemon_response_time = Histogram(
    'daemon_response_seconds',
    'Daemon response time',
    ['request_type']
)

daemon_sessions_active = Gauge(
    'daemon_sessions_active',
    'Number of active daemon sessions'
)

daemon_websocket_connections = Gauge(
    'daemon_websocket_connections',
    'Active WebSocket connections to daemon'
)

natural_language_requests = Counter(
    'natural_language_requests_total',
    'Natural language processing requests',
    ['intent', 'status']
)

batch_processing_queue = Gauge(
    'batch_processing_queue_size',
    'Number of specs in batch queue'
)

ai_insights_generated = Counter(
    'ai_insights_generated_total',
    'AI insights generated',
    ['insight_type']
)

# System info
daemon_info = Info(
    'daemon_info',
    'Claude daemon information'
)
daemon_info.info({
    'version': '2.0.0',
    'model': 'claude-3-opus',
    'capabilities': 'full'
})
```

This enhanced Web Server V2 specification integrates the Claude Daemon architecture, providing intelligent orchestration capabilities while maintaining backward compatibility with existing REST APIs. The dual-mode architecture enables both traditional API access and AI-enhanced natural language processing through the persistent daemon.
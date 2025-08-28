# Integrated Multi-Component Deployment & Testing Specification

## Project Overview
Deploy and integration-test three interconnected components of the Tmux Orchestrator ecosystem:
1. **Mobile App Spec V2** - Android app with Claude Daemon integration
2. **MCP Server Spec V2** - Enhanced MCP tools with daemon support  
3. **Web Server Spec V2** - Dual-mode web platform with daemon bridge

## Project Structure
```
/home/clauderun/
├── mobile_app_spec_v2/          # Android mobile application
├── mcp_server_spec_v2/          # MCP server with daemon support
├── web_server_spec_v2/          # Web server with daemon integration
└── Tmux-Orchestrator/           # Orchestrator tool directory
```

## Architecture Integration Overview

### Claude Daemon-Centric Architecture
```
Mobile App ──┐
             ├── Claude Daemon (systemd service) ──┐
Web Server ──┘                                     │
                                                   │
MCP Server ← ──────────────────────────────────────┤
    │                                              │
    ├── Project Queue Management                   │
    ├── Team Agent Communication                   │ 
    └── Session State Synchronization              │
                                                   │
Tmux Orchestrator ← ───────────────────────────────┘
    ├── Agent Worktrees
    ├── Git Coordination
    └── Task Scheduling
```

## Phase 1: Infrastructure Setup & MCP Server Deployment

### 1.1 MCP Server Environment
**Target**: `/home/clauderun/mcp_server_spec_v2/`
**Deployment Pattern**: Python service with systemd integration

#### Requirements
- Python 3.11+ with uv package manager
- Systemd service configuration
- MCP protocol implementation
- WebSocket server for daemon communication
- Authentication and session management

#### Deliverables
- Working MCP server accessible via stdio and WebSocket
- Claude Daemon systemd service running
- Authentication system operational
- Basic health checks and monitoring

### 1.2 Claude Daemon Integration
**Service Name**: `claude-daemon`
**User**: `clauderun`
**Port**: `8765` (WebSocket)

#### Components
- Session manager for concurrent client handling
- WebSocket server for real-time communication
- MCP tool integration layer
- Request/response queue management

## Phase 2: Web Server Deployment & Integration

### 2.1 Web Server Setup
**Target**: `/home/clauderun/web_server_spec_v2/`
**Deployment Pattern**: FastAPI with Nginx reverse proxy
**Server**: `185.177.73.38`
**Domain**: `dashboard.aboutco.ai/orchestrator-web`

#### Technical Stack
- FastAPI application server
- Nginx reverse proxy configuration
- Redis for session management
- WebSocket support for real-time updates

#### Integration Points
- Daemon proxy for intelligent requests
- Traditional REST API for compatibility
- WebSocket relay for live updates
- Session bridge between web and daemon

### 2.2 Server Configuration
```nginx
# /etc/nginx/sites-available/orchestrator-web
location /orchestrator-web/ {
    proxy_pass http://127.0.0.1:8001/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /orchestrator-web/ws/ {
    proxy_pass http://127.0.0.1:8001/ws/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
    proxy_set_header Host $host;
}
```

## Phase 3: Mobile App Build & Deployment

### 3.1 Android App Build
**Target**: `/home/clauderun/mobile_app_spec_v2/orchestrator-mobile-v2/`
**Deployment Pattern**: Similar to `aivoice_reader` deployment

#### Build Process
1. **Gradle Build**
   ```bash
   ./gradlew assembleRelease
   ```

2. **APK Signing** (using existing keystore)
   ```bash
   $ANDROID_HOME/build-tools/34.0.0/apksigner sign \
     --ks-key-alias orchestrator-mobile \
     --ks /path/to/keystore.jks \
     app/build/outputs/apk/release/app-release.apk
   ```

3. **Server Deployment**
   ```bash
   # Deploy to dashboard.aboutco.ai/apps/orchestrator-mobile/
   scp app-release.apk root@185.177.73.38:/var/www/dashboard/apps/orchestrator-mobile/
   ```

### 3.2 Mobile App Features to Test
- Claude Daemon WebSocket connection
- Natural language project creation
- Real-time status updates
- Voice input integration
- Offline command queuing
- Session persistence

### 3.3 Deploy Script Template
**File**: `/home/clauderun/mobile_app_spec_v2/deploy_simple.sh`

Based on `aivoice_reader/deploy_simple.sh` pattern:
- Version extraction from `build.gradle`
- APK signature verification
- Server upload with timestamp
- HTML download page generation
- QR code generation
- URL creation and sharing

## Phase 4: Integration Testing Framework

### 4.1 Test Scenarios

#### End-to-End User Flows
1. **Mobile-to-Daemon-to-Orchestrator**
   - User creates project via mobile app
   - Daemon processes request using MCP tools
   - Orchestrator team agents are deployed
   - Status updates flow back to mobile

2. **Web-to-Daemon Integration**
   - Web client sends intelligent request
   - Daemon processes with context awareness
   - Results returned via both REST and WebSocket
   - Session state maintained across reconnections

3. **Multi-Client Coordination**
   - Mobile and web clients connected simultaneously
   - Changes made on one client reflected on others
   - Daemon manages concurrent sessions
   - No data corruption or race conditions

#### Component Testing
1. **MCP Server Health**
   - Tool discovery and invocation
   - WebSocket stability under load
   - Authentication token handling
   - Error propagation and recovery

2. **Daemon Reliability**
   - Service restart resilience
   - Memory usage under extended operation
   - Session cleanup and garbage collection
   - Graceful error handling

3. **Cross-Component Communication**
   - Message format consistency
   - Timeout handling
   - Retry mechanisms
   - Status synchronization

### 4.2 Automated Test Suite
**Location**: `/home/clauderun/Tmux-Orchestrator/tests/integration/`

#### Test Structure
```
tests/integration/
├── conftest.py                    # Test configuration
├── test_daemon_integration.py     # Daemon + MCP tests
├── test_web_daemon_bridge.py      # Web server integration
├── test_mobile_connectivity.py    # Mobile app connection tests
├── test_end_to_end_flows.py       # Complete user scenarios
├── test_performance.py            # Load and stress tests
├── test_failure_recovery.py       # Error handling tests
└── helpers/
    ├── daemon_client.py           # Test daemon client
    ├── mock_mobile_app.py         # Mobile app simulator
    └── web_client.py              # Web API test client
```

### 4.3 Performance Benchmarks
- **Response Time**: < 500ms for typical requests
- **Concurrent Sessions**: Support 50+ simultaneous connections
- **Memory Usage**: < 512MB RAM per daemon instance
- **Uptime**: 99.9% availability target

## Phase 5: Production Deployment

### 5.1 Service Deployment Order
1. **MCP Server + Claude Daemon** (systemd services)
2. **Web Server** (FastAPI + Nginx)
3. **Mobile App** (APK distribution)

### 5.2 Health Monitoring
- **Service Status**: systemd status checks
- **Endpoint Health**: HTTP health check endpoints
- **Log Monitoring**: Centralized logging with log rotation
- **Performance Metrics**: Response times and error rates

### 5.3 Rollback Plan
- **Database Schema**: Version-controlled migrations
- **Service Configs**: Git-tracked with quick restore
- **APK Versions**: Multiple versions maintained on server
- **Traffic Routing**: Nginx can route to backup instances

## Quality Standards & Success Criteria

### Functional Requirements ✅
- [ ] All three components build and deploy successfully
- [ ] End-to-end communication functional (mobile → daemon → orchestrator)
- [ ] Web server provides both REST and daemon-mediated access
- [ ] Mobile app connects and maintains sessions
- [ ] Multi-user coordination works without conflicts

### Performance Requirements ✅
- [ ] Sub-500ms response times for standard operations
- [ ] 50+ concurrent session support
- [ ] 99.9% uptime during testing period
- [ ] Graceful degradation under load

### Integration Requirements ✅
- [ ] Claude Daemon manages MCP tools correctly
- [ ] Session state synchronized across all clients
- [ ] Real-time updates delivered reliably
- [ ] Authentication and authorization working

### Deployment Requirements ✅
- [ ] All services configured as systemd units
- [ ] Automated deployment scripts functional
- [ ] Health checks and monitoring operational
- [ ] Documentation and runbooks complete

## Risk Mitigation

### Technical Risks
- **Service Dependencies**: Comprehensive startup ordering and health checks
- **Session Management**: Redis-backed state with failover capability
- **Network Connectivity**: Retry mechanisms and offline functionality
- **Resource Limits**: Memory monitoring and automatic scaling

### Operational Risks
- **Deployment Failures**: Staged rollout with immediate rollback capability
- **Data Corruption**: Backup and restore procedures
- **Security Issues**: Authentication testing and access control verification
- **Performance Degradation**: Load testing and capacity planning

## Timeline & Milestones

### Week 1: Foundation
- MCP Server deployment and basic testing
- Claude Daemon service setup
- Initial integration testing

### Week 2: Web Integration
- Web server deployment
- Daemon bridge implementation
- Cross-component testing

### Week 3: Mobile Deployment
- Android app build and deployment
- Mobile-daemon connectivity
- End-to-end flow testing

### Week 4: Production Ready
- Performance optimization
- Comprehensive testing
- Documentation and handoff

This specification provides a comprehensive roadmap for deploying and testing the integrated Tmux Orchestrator ecosystem with robust quality assurance and production readiness criteria.
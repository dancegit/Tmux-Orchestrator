# Tmux Orchestrator Mobile App Specification

## Overview
The Tmux Orchestrator Mobile App is an Android application that provides remote management capabilities for Tmux Orchestrator projects. Built using Kotlin and Material Design, it enables users to create, monitor, and interact with orchestration projects from mobile devices, supporting both direct Web Server communication and Claude Code integration via MCP.

## Repository Structure
```
orchestrator-mobile/
├── README.md
├── CHANGELOG.md
├── app/
│   ├── build.gradle                          # App-level build configuration
│   ├── proguard-rules.pro                    # ProGuard configuration
│   └── src/
│       ├── main/
│       │   ├── AndroidManifest.xml           # App permissions and declarations
│       │   ├── java/com/orchestrator/mobile/ # Main application package
│       │   │   ├── OrchestratorApplication.kt # Application class
│       │   │   ├── ui/                        # User Interface components
│       │   │   │   ├── MainActivity.kt        # Main dashboard activity
│       │   │   │   ├── project/               # Project management screens
│       │   │   │   │   ├── ProjectListActivity.kt
│       │   │   │   │   ├── ProjectCreateActivity.kt
│       │   │   │   │   ├── ProjectDetailActivity.kt
│       │   │   │   │   └── ProjectEditActivity.kt
│       │   │   │   ├── messaging/             # Agent communication screens
│       │   │   │   │   ├── MessagingActivity.kt
│       │   │   │   │   ├── ChatActivity.kt
│       │   │   │   │   └── MessageHistoryActivity.kt
│       │   │   │   ├── monitoring/            # Status and monitoring screens
│       │   │   │   │   ├── DashboardActivity.kt
│       │   │   │   │   ├── ProjectStatusActivity.kt
│       │   │   │   │   ├── AgentStatusActivity.kt
│       │   │   │   │   └── SystemHealthActivity.kt
│       │   │   │   ├── settings/              # Configuration screens
│       │   │   │   │   ├── SettingsActivity.kt
│       │   │   │   │   ├── ConnectionActivity.kt
│       │   │   │   │   └── ProfileActivity.kt
│       │   │   │   ├── git/                   # Git workflow screens
│       │   │   │   │   ├── GitStatusActivity.kt
│       │   │   │   │   ├── GitHistoryActivity.kt
│       │   │   │   │   └── GitWorkflowActivity.kt
│       │   │   │   └── common/                # Shared UI components
│       │   │   │       ├── BaseActivity.kt
│       │   │   │       ├── LoadingDialog.kt
│       │   │   │       └── ErrorDialog.kt
│       │   │   ├── services/                  # Background services
│       │   │   │   ├── OrchestratorService.kt # Main background service
│       │   │   │   ├── NotificationService.kt # Notification handling
│       │   │   │   └── WebSocketService.kt    # Real-time communication
│       │   │   ├── models/                    # Data models
│       │   │   │   ├── Project.kt
│       │   │   │   ├── Agent.kt
│       │   │   │   ├── Message.kt
│       │   │   │   ├── GitStatus.kt
│       │   │   │   ├── ProjectSpec.kt
│       │   │   │   └── SystemHealth.kt
│       │   │   ├── adapters/                  # RecyclerView adapters
│       │   │   │   ├── ProjectListAdapter.kt
│       │   │   │   ├── MessageListAdapter.kt
│       │   │   │   ├── AgentStatusAdapter.kt
│       │   │   │   └── GitCommitAdapter.kt
│       │   │   ├── network/                   # Network layer
│       │   │   │   ├── ApiClient.kt           # REST API client
│       │   │   │   ├── WebSocketClient.kt     # WebSocket client
│       │   │   │   ├── ApiService.kt          # API interface definitions
│       │   │   │   ├── AuthInterceptor.kt     # Authentication handling
│       │   │   │   └── NetworkManager.kt      # Connection management
│       │   │   ├── utils/                     # Utility classes
│       │   │   │   ├── PreferenceManager.kt   # Settings persistence
│       │   │   │   ├── NotificationManager.kt # Notification utilities
│       │   │   │   ├── DateTimeUtils.kt       # Date/time formatting
│       │   │   │   ├── ValidationUtils.kt     # Input validation
│       │   │   │   ├── SecurityUtils.kt       # Security utilities
│       │   │   │   └── LoggingUtils.kt        # Logging framework
│       │   │   ├── receivers/                 # Broadcast receivers
│       │   │   │   ├── BootReceiver.kt        # Auto-start on boot
│       │   │   │   ├── NetworkReceiver.kt     # Network state changes
│       │   │   │   └── NotificationReceiver.kt # Notification actions
│       │   │   └── database/                  # Local database
│       │   │       ├── OrchestratorDatabase.kt
│       │   │       ├── entities/              # Room entities
│       │   │       │   ├── ProjectEntity.kt
│       │   │       │   ├── MessageEntity.kt
│       │   │       │   └── CacheEntity.kt
│       │   │       └── daos/                  # Data Access Objects
│       │   │           ├── ProjectDao.kt
│       │   │           ├── MessageDao.kt
│       │   │           └── CacheDao.kt
│       │   └── res/                           # Android resources
│       │       ├── drawable/                  # Icons and graphics
│       │       │   ├── ic_project.xml
│       │       │   ├── ic_agent.xml
│       │       │   ├── ic_message.xml
│       │       │   ├── ic_git.xml
│       │       │   ├── ic_status_active.xml
│       │       │   ├── ic_status_failed.xml
│       │       │   └── ic_notification.xml
│       │       ├── layout/                    # XML layouts
│       │       │   ├── activity_main.xml
│       │       │   ├── activity_project_list.xml
│       │       │   ├── activity_project_detail.xml
│       │       │   ├── activity_messaging.xml
│       │       │   ├── activity_dashboard.xml
│       │       │   ├── item_project.xml
│       │       │   ├── item_message.xml
│       │       │   ├── item_agent_status.xml
│       │       │   └── dialog_create_project.xml
│       │       ├── values/                    # String and style resources
│       │       │   ├── strings.xml
│       │       │   ├── colors.xml
│       │       │   ├── themes.xml
│       │       │   └── dimens.xml
│       │       ├── menu/                      # Menu definitions
│       │       │   ├── main_menu.xml
│       │       │   ├── project_menu.xml
│       │       │   └── message_menu.xml
│       │       └── xml/                       # Configuration files
│       │           ├── backup_rules.xml
│       │           ├── data_extraction_rules.xml
│       │           ├── network_security_config.xml
│       │           └── notification_channels.xml
│       ├── androidTest/                       # Instrumented tests
│       │   └── java/com/orchestrator/mobile/
│       │       ├── ui/
│       │       │   ├── MainActivityTest.kt
│       │       │   └── ProjectListTest.kt
│       │       └── database/
│       │           └── DatabaseTest.kt
│       └── test/                              # Unit tests
│           └── java/com/orchestrator/mobile/
│               ├── models/
│               │   └── ProjectTest.kt
│               ├── network/
│               │   └── ApiClientTest.kt
│               └── utils/
│                   └── ValidationUtilsTest.kt
├── gradle/                                    # Gradle wrapper
│   └── wrapper/
├── build.gradle                               # Project-level build config
├── gradle.properties                         # Gradle properties
├── settings.gradle                            # Module configuration
├── docs/                                      # Documentation
│   ├── API_INTEGRATION.md
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── USER_GUIDE.md
└── screenshots/                               # App screenshots for store
    ├── dashboard.png
    ├── project_list.png
    ├── messaging.png
    └── monitoring.png
```

## Technology Stack

### Core Technologies
- **Kotlin**: Modern Android development language
- **Android SDK**: Target API 34 (Android 14), minimum API 24 (Android 7.0)
- **Jetpack Compose**: Modern UI toolkit for declarative interfaces
- **Material Design 3**: Google's latest design system
- **Android Architecture Components**: ViewModel, LiveData, Navigation

### Key Dependencies
```gradle
// app/build.gradle
dependencies {
    // Core Android
    implementation 'androidx.core:core-ktx:1.12.0'
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'androidx.activity:activity-compose:1.8.2'
    
    // UI and Material Design
    implementation 'androidx.compose.ui:ui:1.5.4'
    implementation 'androidx.compose.ui:ui-tooling-preview:1.5.4'
    implementation 'androidx.compose.material3:material3:1.1.2'
    implementation 'androidx.compose.material:material-icons-extended:1.5.4'
    
    // Navigation
    implementation 'androidx.navigation:navigation-compose:2.7.4'
    
    // ViewModel and LiveData
    implementation 'androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0'
    implementation 'androidx.lifecycle:lifecycle-runtime-compose:2.7.0'
    
    // Network
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
    implementation 'com.squareup.okhttp3:logging-interceptor:4.12.0'
    
    // WebSocket
    implementation 'org.java-websocket:Java-WebSocket:1.5.4'
    
    // Database
    implementation 'androidx.room:room-runtime:2.6.0'
    implementation 'androidx.room:room-ktx:2.6.0'
    kapt 'androidx.room:room-compiler:2.6.0'
    
    // Dependency Injection
    implementation 'com.google.dagger:hilt-android:2.48'
    kapt 'com.google.dagger:hilt-compiler:2.48'
    implementation 'androidx.hilt:hilt-navigation-compose:1.1.0'
    
    // Async
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'
    
    // JSON
    implementation 'com.google.code.gson:gson:2.10.1'
    
    // Image Loading
    implementation 'io.coil-kt:coil-compose:2.5.0'
    
    // Preferences
    implementation 'androidx.datastore:datastore-preferences:1.0.0'
    
    // Work Manager
    implementation 'androidx.work:work-runtime-ktx:2.8.1'
    
    // Testing
    testImplementation 'junit:junit:4.13.2'
    testImplementation 'org.mockito:mockito-core:5.6.0'
    testImplementation 'org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3'
    androidTestImplementation 'androidx.test.ext:junit:1.1.5'
    androidTestImplementation 'androidx.test.espresso:espresso-core:3.5.1'
    androidTestImplementation 'androidx.compose.ui:ui-test-junit4:1.5.4'
}
```

## Core Features and Implementation

### 1. Project Management

#### Project Creation Interface
```kotlin
// ui/project/ProjectCreateActivity.kt
@Composable
fun ProjectCreateScreen(
    viewModel: ProjectCreateViewModel = hiltViewModel(),
    onNavigateBack: () -> Unit
) {
    var projectName by remember { mutableStateOf("") }
    var projectPath by remember { mutableStateOf("") }
    var specification by remember { mutableStateOf("") }
    var selectedTeam by remember { mutableStateOf<List<String>>(emptyList()) }
    
    val uiState by viewModel.uiState.collectAsState()
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        OutlinedTextField(
            value = projectName,
            onValueChange = { projectName = it },
            label = { Text("Project Name") },
            modifier = Modifier.fillMaxWidth()
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        OutlinedTextField(
            value = projectPath,
            onValueChange = { projectPath = it },
            label = { Text("Project Path") },
            modifier = Modifier.fillMaxWidth()
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        OutlinedTextField(
            value = specification,
            onValueChange = { specification = it },
            label = { Text("Project Specification") },
            modifier = Modifier
                .fillMaxWidth()
                .height(200.dp),
            maxLines = 10
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        TeamCompositionSelector(
            selectedTeam = selectedTeam,
            onTeamChanged = { selectedTeam = it }
        )
        
        Spacer(modifier = Modifier.height(24.dp))
        
        Button(
            onClick = {
                viewModel.createProject(
                    ProjectCreateRequest(
                        name = projectName,
                        path = projectPath,
                        specification = specification,
                        teamComposition = selectedTeam
                    )
                )
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = projectName.isNotEmpty() && specification.isNotEmpty()
        ) {
            if (uiState.isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = MaterialTheme.colorScheme.onPrimary
                )
            } else {
                Text("Create Project")
            }
        }
    }
}

@Composable
fun TeamCompositionSelector(
    selectedTeam: List<String>,
    onTeamChanged: (List<String>) -> Unit
) {
    val availableRoles = listOf(
        "orchestrator", "developer", "tester", "testrunner", 
        "pm", "devops", "sysadmin", "securityops"
    )
    
    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        modifier = Modifier.height(200.dp)
    ) {
        items(availableRoles) { role ->
            FilterChip(
                onClick = {
                    if (selectedTeam.contains(role)) {
                        onTeamChanged(selectedTeam - role)
                    } else {
                        onTeamChanged(selectedTeam + role)
                    }
                },
                label = { Text(role.replaceFirstChar { it.uppercase() }) },
                selected = selectedTeam.contains(role),
                modifier = Modifier.padding(4.dp)
            )
        }
    }
}
```

#### Project List and Status
```kotlin
// ui/project/ProjectListActivity.kt
@Composable
fun ProjectListScreen(
    viewModel: ProjectListViewModel = hiltViewModel(),
    onProjectClick: (String) -> Unit,
    onCreateProject: () -> Unit
) {
    val projects by viewModel.projects.collectAsState()
    val uiState by viewModel.uiState.collectAsState()
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Orchestrator Projects") },
                actions = {
                    IconButton(onClick = { viewModel.refreshProjects() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                }
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onCreateProject) {
                Icon(Icons.Default.Add, contentDescription = "Create Project")
            }
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(projects) { project ->
                ProjectCard(
                    project = project,
                    onClick = { onProjectClick(project.id) }
                )
            }
        }
    }
    
    if (uiState.isLoading) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            CircularProgressIndicator()
        }
    }
}

@Composable
fun ProjectCard(
    project: Project,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = project.name,
                    style = MaterialTheme.typography.headlineSmall,
                    modifier = Modifier.weight(1f)
                )
                ProjectStatusBadge(status = project.status)
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = project.description,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
            
            Spacer(modifier = Modifier.height(12.dp))
            
            LinearProgressIndicator(
                progress = project.progress,
                modifier = Modifier.fillMaxWidth()
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "Progress: ${(project.progress * 100).toInt()}%",
                    style = MaterialTheme.typography.bodySmall
                )
                Text(
                    text = "${project.agents.size} agents",
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}
```

### 2. Real-time Messaging System

#### Chat Interface
```kotlin
// ui/messaging/ChatActivity.kt
@Composable
fun ChatScreen(
    projectId: String,
    agentId: String,
    viewModel: ChatViewModel = hiltViewModel()
) {
    val messages by viewModel.messages.collectAsState()
    val messageText by viewModel.messageText.collectAsState()
    
    LaunchedEffect(projectId, agentId) {
        viewModel.initializeChat(projectId, agentId)
    }
    
    Column(modifier = Modifier.fillMaxSize()) {
        // Messages list
        LazyColumn(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            reverseLayout = true,
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(messages.reversed()) { message ->
                MessageBubble(message = message)
            }
        }
        
        // Message input
        Surface(
            modifier = Modifier.fillMaxWidth(),
            tonalElevation = 8.dp
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalAlignment = Alignment.Bottom
            ) {
                OutlinedTextField(
                    value = messageText,
                    onValueChange = { viewModel.updateMessageText(it) },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("Type a message...") },
                    maxLines = 4
                )
                
                Spacer(modifier = Modifier.width(8.dp))
                
                IconButton(
                    onClick = { viewModel.sendMessage() },
                    enabled = messageText.isNotBlank()
                ) {
                    Icon(Icons.Default.Send, contentDescription = "Send")
                }
            }
        }
    }
}

@Composable
fun MessageBubble(message: Message) {
    val isFromUser = message.sender == "user"
    
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isFromUser) Arrangement.End else Arrangement.Start
    ) {
        Card(
            modifier = Modifier.widthIn(max = 280.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (isFromUser) 
                    MaterialTheme.colorScheme.primary 
                else 
                    MaterialTheme.colorScheme.surfaceVariant
            )
        ) {
            Column(
                modifier = Modifier.padding(12.dp)
            ) {
                Text(
                    text = message.content,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (isFromUser) 
                        MaterialTheme.colorScheme.onPrimary 
                    else 
                        MaterialTheme.colorScheme.onSurfaceVariant
                )
                
                Spacer(modifier = Modifier.height(4.dp))
                
                Text(
                    text = DateTimeUtils.formatTime(message.timestamp),
                    style = MaterialTheme.typography.bodySmall,
                    color = if (isFromUser) 
                        MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.7f)
                    else 
                        MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f)
                )
            }
        }
    }
}
```

### 3. Real-time Dashboard and Monitoring

#### Dashboard Implementation
```kotlin
// ui/monitoring/DashboardActivity.kt
@Composable
fun DashboardScreen(
    viewModel: DashboardViewModel = hiltViewModel()
) {
    val systemHealth by viewModel.systemHealth.collectAsState()
    val activeProjects by viewModel.activeProjects.collectAsState()
    val recentActivity by viewModel.recentActivity.collectAsState()
    
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            SystemHealthCard(systemHealth = systemHealth)
        }
        
        item {
            ActiveProjectsCard(
                projects = activeProjects,
                onProjectClick = { /* Navigate to project detail */ }
            )
        }
        
        item {
            RecentActivityCard(activities = recentActivity)
        }
        
        item {
            QuickActionsCard(
                onCreateProject = { /* Navigate to create project */ },
                onViewAllProjects = { /* Navigate to project list */ }
            )
        }
    }
}

@Composable
fun SystemHealthCard(systemHealth: SystemHealth) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Text(
                text = "System Health",
                style = MaterialTheme.typography.headlineSmall
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                HealthMetric(
                    label = "CPU",
                    value = "${systemHealth.cpuUsage}%",
                    color = getHealthColor(systemHealth.cpuUsage)
                )
                HealthMetric(
                    label = "Memory",
                    value = "${systemHealth.memoryUsage}%",
                    color = getHealthColor(systemHealth.memoryUsage)
                )
                HealthMetric(
                    label = "Active Projects",
                    value = systemHealth.activeProjects.toString(),
                    color = MaterialTheme.colorScheme.primary
                )
            }
        }
    }
}

@Composable
fun HealthMetric(
    label: String,
    value: String,
    color: Color
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = value,
            style = MaterialTheme.typography.headlineMedium,
            color = color
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
```

### 4. Network Layer Implementation

#### API Client
```kotlin
// network/ApiClient.kt
@Singleton
class ApiClient @Inject constructor(
    private val okHttpClient: OkHttpClient,
    private val preferencesManager: PreferenceManager
) {
    private val gson = Gson()
    
    private val retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(preferencesManager.getServerUrl())
            .addConverterFactory(GsonConverterFactory.create(gson))
            .client(okHttpClient)
            .build()
    }
    
    val apiService: ApiService by lazy {
        retrofit.create(ApiService::class.java)
    }
    
    suspend fun createProject(request: ProjectCreateRequest): Result<Project> {
        return try {
            val response = apiService.createProject(request)
            if (response.isSuccessful) {
                response.body()?.let { project ->
                    Result.success(project)
                } ?: Result.failure(Exception("Empty response body"))
            } else {
                Result.failure(HttpException(response))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    suspend fun getProjects(
        statusFilter: List<String>? = null,
        limit: Int = 20
    ): Result<List<Project>> {
        return try {
            val response = apiService.getProjects(statusFilter, limit)
            if (response.isSuccessful) {
                response.body()?.let { projects ->
                    Result.success(projects)
                } ?: Result.failure(Exception("Empty response body"))
            } else {
                Result.failure(HttpException(response))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    suspend fun sendMessage(
        projectId: String,
        request: MessageRequest
    ): Result<MessageResponse> {
        return try {
            val response = apiService.sendMessage(projectId, request)
            if (response.isSuccessful) {
                response.body()?.let { messageResponse ->
                    Result.success(messageResponse)
                } ?: Result.failure(Exception("Empty response body"))
            } else {
                Result.failure(HttpException(response))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

// network/ApiService.kt
interface ApiService {
    @POST("api/v1/projects")
    suspend fun createProject(@Body request: ProjectCreateRequest): Response<Project>
    
    @GET("api/v1/projects")
    suspend fun getProjects(
        @Query("status_filter") statusFilter: List<String>? = null,
        @Query("limit") limit: Int = 20
    ): Response<List<Project>>
    
    @GET("api/v1/projects/{projectId}")
    suspend fun getProject(@Path("projectId") projectId: String): Response<Project>
    
    @POST("api/v1/projects/{projectId}/messages")
    suspend fun sendMessage(
        @Path("projectId") projectId: String,
        @Body request: MessageRequest
    ): Response<MessageResponse>
    
    @GET("api/v1/projects/{projectId}/messages")
    suspend fun getMessages(
        @Path("projectId") projectId: String,
        @Query("limit") limit: Int = 50
    ): Response<List<Message>>
    
    @GET("api/v1/projects/{projectId}/status")
    suspend fun getProjectStatus(@Path("projectId") projectId: String): Response<ProjectStatus>
    
    @GET("api/v1/system/health")
    suspend fun getSystemHealth(): Response<SystemHealth>
}
```

#### WebSocket Client
```kotlin
// network/WebSocketClient.kt
@Singleton
class WebSocketClient @Inject constructor(
    private val preferencesManager: PreferenceManager
) {
    private var webSocket: WebSocket? = null
    private val messageHandlers = mutableMapOf<String, (String) -> Unit>()
    
    fun connect(projectId: String) {
        val serverUrl = preferencesManager.getServerUrl()
        val wsUrl = serverUrl.replace("http", "ws") + "/ws/projects/$projectId"
        
        val request = Request.Builder()
            .url(wsUrl)
            .addHeader("Authorization", "Bearer ${preferencesManager.getApiKey()}")
            .build()
        
        webSocket = OkHttpClient().newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d("WebSocket", "Connected to project $projectId")
            }
            
            override fun onMessage(webSocket: WebSocket, text: String) {
                handleMessage(text)
            }
            
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("WebSocket", "Connection failed", t)
                // Implement reconnection logic
                scheduleReconnection(projectId)
            }
            
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d("WebSocket", "Connection closing: $reason")
            }
        })
    }
    
    private fun handleMessage(message: String) {
        try {
            val json = JSONObject(message)
            val type = json.getString("type")
            val data = json.getJSONObject("data")
            
            messageHandlers[type]?.invoke(data.toString())
        } catch (e: Exception) {
            Log.e("WebSocket", "Error parsing message", e)
        }
    }
    
    fun registerHandler(messageType: String, handler: (String) -> Unit) {
        messageHandlers[messageType] = handler
    }
    
    fun disconnect() {
        webSocket?.close(1000, "User disconnected")
        webSocket = null
    }
    
    private fun scheduleReconnection(projectId: String) {
        // Implement exponential backoff reconnection
        CoroutineScope(Dispatchers.IO).launch {
            delay(5000) // Wait 5 seconds before reconnecting
            connect(projectId)
        }
    }
}
```

### 5. Local Database and Caching

#### Room Database Setup
```kotlin
// database/OrchestratorDatabase.kt
@Database(
    entities = [
        ProjectEntity::class,
        MessageEntity::class,
        CacheEntity::class
    ],
    version = 1,
    exportSchema = false
)
@TypeConverters(Converters::class)
abstract class OrchestratorDatabase : RoomDatabase() {
    abstract fun projectDao(): ProjectDao
    abstract fun messageDao(): MessageDao
    abstract fun cacheDao(): CacheDao
    
    companion object {
        @Volatile
        private var INSTANCE: OrchestratorDatabase? = null
        
        fun getDatabase(context: Context): OrchestratorDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    OrchestratorDatabase::class.java,
                    "orchestrator_database"
                ).build()
                INSTANCE = instance
                instance
            }
        }
    }
}

// database/entities/ProjectEntity.kt
@Entity(tableName = "projects")
data class ProjectEntity(
    @PrimaryKey val id: String,
    val name: String,
    val description: String,
    val status: String,
    val progress: Float,
    val createdAt: Long,
    val updatedAt: Long,
    val agentCount: Int,
    val specification: String,
    val teamComposition: String, // JSON array as string
    val gitBranch: String?,
    val gitCommitHash: String?
)

// database/daos/ProjectDao.kt
@Dao
interface ProjectDao {
    @Query("SELECT * FROM projects ORDER BY updatedAt DESC")
    fun getAllProjects(): Flow<List<ProjectEntity>>
    
    @Query("SELECT * FROM projects WHERE id = :projectId")
    suspend fun getProject(projectId: String): ProjectEntity?
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertProject(project: ProjectEntity)
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertProjects(projects: List<ProjectEntity>)
    
    @Update
    suspend fun updateProject(project: ProjectEntity)
    
    @Delete
    suspend fun deleteProject(project: ProjectEntity)
    
    @Query("DELETE FROM projects WHERE id = :projectId")
    suspend fun deleteProjectById(projectId: String)
}
```

### 6. Background Services and Notifications

#### Orchestrator Service
```kotlin
// services/OrchestratorService.kt
@AndroidEntryPoint
class OrchestratorService : Service() {
    
    @Inject
    lateinit var apiClient: ApiClient
    
    @Inject
    lateinit var webSocketClient: WebSocketClient
    
    @Inject
    lateinit var notificationManager: NotificationManager
    
    private val binder = OrchestratorBinder()
    private var isRunning = false
    
    inner class OrchestratorBinder : Binder() {
        fun getService(): OrchestratorService = this@OrchestratorService
    }
    
    override fun onBind(intent: Intent): IBinder = binder
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!isRunning) {
            startForegroundService()
            setupWebSocketHandlers()
            startPeriodicSync()
            isRunning = true
        }
        
        return START_STICKY
    }
    
    private fun startForegroundService() {
        val notification = createForegroundNotification()
        startForeground(NOTIFICATION_ID, notification)
    }
    
    private fun createForegroundNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Orchestrator Active")
            .setContentText("Monitoring projects and maintaining connections")
            .setSmallIcon(R.drawable.ic_notification)
            .setOngoing(true)
            .build()
    }
    
    private fun setupWebSocketHandlers() {
        webSocketClient.registerHandler("agent_status_update") { data ->
            handleAgentStatusUpdate(data)
        }
        
        webSocketClient.registerHandler("project_status_change") { data ->
            handleProjectStatusChange(data)
        }
        
        webSocketClient.registerHandler("git_event") { data ->
            handleGitEvent(data)
        }
    }
    
    private fun handleAgentStatusUpdate(data: String) {
        // Parse and handle agent status updates
        // Send local broadcast or update database
        val intent = Intent(ACTION_AGENT_STATUS_UPDATE)
        intent.putExtra("data", data)
        sendBroadcast(intent)
    }
    
    private fun startPeriodicSync() {
        // Use WorkManager for reliable background sync
        val syncRequest = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
            )
            .build()
        
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "orchestrator_sync",
            ExistingPeriodicWorkPolicy.KEEP,
            syncRequest
        )
    }
    
    companion object {
        private const val NOTIFICATION_ID = 1
        private const val CHANNEL_ID = "orchestrator_service"
        const val ACTION_AGENT_STATUS_UPDATE = "com.orchestrator.mobile.AGENT_STATUS_UPDATE"
    }
}
```

#### Notification Management
```kotlin
// utils/NotificationManager.kt
@Singleton
class NotificationManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
    
    init {
        createNotificationChannels()
    }
    
    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channels = listOf(
                NotificationChannel(
                    CHANNEL_SERVICE,
                    "Service",
                    NotificationManager.IMPORTANCE_LOW
                ).apply {
                    description = "Background service notifications"
                },
                NotificationChannel(
                    CHANNEL_UPDATES,
                    "Project Updates",
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "Project status and progress updates"
                },
                NotificationChannel(
                    CHANNEL_ALERTS,
                    "Alerts",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Important alerts and errors"
                }
            )
            
            notificationManager.createNotificationChannels(channels)
        }
    }
    
    fun showProjectStatusNotification(projectName: String, status: String) {
        val notification = NotificationCompat.Builder(context, CHANNEL_UPDATES)
            .setContentTitle("Project Update")
            .setContentText("$projectName is now $status")
            .setSmallIcon(R.drawable.ic_notification)
            .setAutoCancel(true)
            .build()
        
        notificationManager.notify(generateNotificationId(), notification)
    }
    
    fun showAgentMessageNotification(projectName: String, agentName: String, message: String) {
        val notification = NotificationCompat.Builder(context, CHANNEL_UPDATES)
            .setContentTitle("Message from $agentName")
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setSmallIcon(R.drawable.ic_message)
            .setAutoCancel(true)
            .build()
        
        notificationManager.notify(generateNotificationId(), notification)
    }
    
    private fun generateNotificationId(): Int = System.currentTimeMillis().toInt()
    
    companion object {
        const val CHANNEL_SERVICE = "service"
        const val CHANNEL_UPDATES = "updates"
        const val CHANNEL_ALERTS = "alerts"
    }
}
```

## Security Implementation

### Authentication and Secure Storage
```kotlin
// utils/SecurityUtils.kt
@Singleton
class SecurityUtils @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val keyAlias = "orchestrator_key"
    
    fun encryptData(data: String): String {
        val keyGenerator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        val keyGenParameterSpec = KeyGenParameterSpec.Builder(
            keyAlias,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .build()
        
        keyGenerator.init(keyGenParameterSpec)
        val secretKey = keyGenerator.generateKey()
        
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, secretKey)
        
        val encryptedData = cipher.doFinal(data.toByteArray())
        val iv = cipher.iv
        
        return Base64.encodeToString(iv + encryptedData, Base64.DEFAULT)
    }
    
    fun decryptData(encryptedData: String): String {
        val keyStore = KeyStore.getInstance("AndroidKeyStore")
        keyStore.load(null)
        
        val secretKey = keyStore.getKey(keyAlias, null) as SecretKey
        
        val decodedData = Base64.decode(encryptedData, Base64.DEFAULT)
        val iv = decodedData.sliceArray(0..11)
        val cipherText = decodedData.sliceArray(12 until decodedData.size)
        
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        val spec = GCMParameterSpec(128, iv)
        cipher.init(Cipher.DECRYPT_MODE, secretKey, spec)
        
        return String(cipher.doFinal(cipherText))
    }
}

// network/AuthInterceptor.kt
class AuthInterceptor @Inject constructor(
    private val preferencesManager: PreferenceManager
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        
        val token = preferencesManager.getApiKey()
        if (token.isNullOrEmpty()) {
            return chain.proceed(originalRequest)
        }
        
        val authenticatedRequest = originalRequest.newBuilder()
            .header("Authorization", "Bearer $token")
            .build()
        
        return chain.proceed(authenticatedRequest)
    }
}
```

## Testing Strategy

### Unit Tests
```kotlin
// test/models/ProjectTest.kt
class ProjectTest {
    @Test
    fun `project creation with valid data should succeed`() {
        val project = Project(
            id = "test-123",
            name = "Test Project",
            description = "Test Description",
            status = "running",
            progress = 0.5f,
            agents = listOf(),
            gitInfo = GitStatus("main", "abc123", false, emptyList(), "/path"),
            createdAt = System.currentTimeMillis(),
            updatedAt = System.currentTimeMillis()
        )
        
        assertEquals("test-123", project.id)
        assertEquals("Test Project", project.name)
        assertEquals(0.5f, project.progress)
    }
    
    @Test
    fun `project progress should be between 0 and 1`() {
        val project = Project(
            id = "test-123",
            name = "Test Project",
            description = "Test Description",
            status = "running",
            progress = 1.5f, // Invalid progress
            agents = listOf(),
            gitInfo = GitStatus("main", "abc123", false, emptyList(), "/path"),
            createdAt = System.currentTimeMillis(),
            updatedAt = System.currentTimeMillis()
        )
        
        assertTrue(project.progress <= 1.0f)
    }
}
```

### UI Tests
```kotlin
// androidTest/ui/MainActivityTest.kt
@HiltAndroidTest
class MainActivityTest {
    
    @get:Rule
    val hiltRule = HiltAndroidRule(this)
    
    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()
    
    @Before
    fun init() {
        hiltRule.inject()
    }
    
    @Test
    fun dashboardScreenDisplaysCorrectly() {
        composeTestRule.setContent {
            DashboardScreen()
        }
        
        composeTestRule.onNodeWithText("System Health").assertIsDisplayed()
        composeTestRule.onNodeWithText("Active Projects").assertIsDisplayed()
    }
    
    @Test
    fun projectCreationFlowWorks() {
        composeTestRule.setContent {
            ProjectCreateScreen(onNavigateBack = {})
        }
        
        composeTestRule.onNodeWithText("Project Name").performTextInput("Test Project")
        composeTestRule.onNodeWithText("Project Path").performTextInput("/tmp/test")
        composeTestRule.onNodeWithText("Project Specification").performTextInput("Test spec")
        
        composeTestRule.onNodeWithText("Create Project").assertIsEnabled()
    }
}
```

## Deployment and Distribution

### Build Configuration
```gradle
// app/build.gradle
android {
    compileSdk 34
    
    defaultConfig {
        applicationId "com.orchestrator.mobile"
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName "1.0.0"
        
        testInstrumentationRunner "com.orchestrator.mobile.HiltTestRunner"
    }
    
    buildTypes {
        debug {
            isDebuggable = true
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            
            signingConfig = signingConfigs.getByName("release")
        }
    }
    
    flavorDimensions += "environment"
    productFlavors {
        create("development") {
            dimension = "environment"
            buildConfigField("String", "BASE_URL", "\"http://10.0.2.2:8000\"")
            applicationIdSuffix = ".dev"
        }
        
        create("staging") {
            dimension = "environment"
            buildConfigField("String", "BASE_URL", "\"https://staging.orchestrator.example.com\"")
            applicationIdSuffix = ".staging"
        }
        
        create("production") {
            dimension = "environment"
            buildConfigField("String", "BASE_URL", "\"https://orchestrator.example.com\"")
        }
    }
}
```

### CI/CD Pipeline
```yaml
# .github/workflows/android.yml
name: Android CI/CD

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up JDK 17
      uses: actions/setup-java@v3
      with:
        java-version: '17'
        distribution: 'temurin'
    
    - name: Grant execute permission for gradlew
      run: chmod +x gradlew
    
    - name: Run unit tests
      run: ./gradlew test
    
    - name: Run instrumented tests
      uses: reactivecircus/android-emulator-runner@v2
      with:
        api-level: 29
        script: ./gradlew connectedAndroidTest

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up JDK 17
      uses: actions/setup-java@v3
      with:
        java-version: '17'
        distribution: 'temurin'
    
    - name: Build release APK
      run: ./gradlew assembleRelease
    
    - name: Upload APK
      uses: actions/upload-artifact@v3
      with:
        name: release-apk
        path: app/build/outputs/apk/release/app-release.apk
```

This mobile app specification provides a comprehensive foundation for building a modern Android application that seamlessly integrates with the Tmux Orchestrator ecosystem, offering both direct server communication and Claude Code integration capabilities while maintaining a user-friendly interface and robust background functionality.
# Tmux Orchestrator Mobile App Specification V2
## Enhanced for Claude Daemon Integration

## Overview
The Tmux Orchestrator Mobile App V2 is an Android application that provides seamless interaction with the Claude Daemon server, enabling users to manage AI orchestration projects through natural language conversations. The app serves as an intelligent mobile interface that communicates exclusively through the Claude Daemon, providing always-available access to team orchestration capabilities.

## Architecture Changes from V1

### Communication Model
**V1 (Direct)**: Mobile App → Web Server API → Tmux Orchestrator
**V2 (Daemon-based)**: Mobile App → Claude Daemon → MCP Tools → Tmux Orchestrator

### Key Enhancements
1. **Natural Language Interface**: Chat-based interaction replacing form-based inputs
2. **Persistent Context**: Session management across app restarts
3. **Real-time Intelligence**: Claude processes requests and provides insights
4. **Offline Capability**: Queue commands when offline, sync when connected
5. **Voice Integration**: Speech-to-text for hands-free operation

## Repository Structure (Enhanced)
```
orchestrator-mobile-v2/
├── app/
│   └── src/
│       ├── main/
│       │   ├── java/com/orchestrator/mobile/
│       │   │   ├── OrchestratorApplication.kt
│       │   │   ├── ui/
│       │   │   │   ├── MainActivity.kt
│       │   │   │   ├── chat/                    # NEW: Primary interface
│       │   │   │   │   ├── ChatViewModel.kt
│       │   │   │   │   ├── ChatScreen.kt
│       │   │   │   │   ├── MessageComposer.kt
│       │   │   │   │   ├── MessageBubble.kt
│       │   │   │   │   └── VoiceInput.kt      # Voice commands
│       │   │   │   ├── projects/               # Simplified views
│       │   │   │   │   ├── ProjectCards.kt
│       │   │   │   │   └── ProjectTimeline.kt
│       │   │   │   ├── insights/               # NEW: AI insights
│       │   │   │   │   ├── InsightsScreen.kt
│       │   │   │   │   ├── RecommendationCard.kt
│       │   │   │   │   └── AnalyticsView.kt
│       │   │   │   └── settings/
│       │   │   │       ├── SettingsScreen.kt
│       │   │   │       └── SessionManager.kt
│       │   │   ├── daemon/                     # NEW: Daemon integration
│       │   │   │   ├── DaemonClient.kt
│       │   │   │   ├── DaemonWebSocket.kt
│       │   │   │   ├── SessionHandler.kt
│       │   │   │   ├── MessageQueue.kt        # Offline queue
│       │   │   │   └── AuthManager.kt
│       │   │   ├── services/
│       │   │   │   ├── DaemonService.kt       # Background daemon connection
│       │   │   │   ├── SyncService.kt         # Offline sync
│       │   │   │   └── NotificationService.kt
│       │   │   ├── models/
│       │   │   │   ├── ChatMessage.kt
│       │   │   │   ├── DaemonResponse.kt
│       │   │   │   ├── ProjectStatus.kt
│       │   │   │   ├── TeamUpdate.kt
│       │   │   │   └── SessionState.kt
│       │   │   └── utils/
│       │   │       ├── SpeechRecognition.kt   # NEW: Voice support
│       │   │       ├── TextToSpeech.kt        # NEW: Audio responses
│       │   │       ├── MarkdownRenderer.kt    # Rich text display
│       │   │       └── FileHandler.kt         # Spec file management
│       │   └── res/
│       │       ├── layout/
│       │       │   ├── activity_main.xml
│       │       │   ├── screen_chat.xml
│       │       │   ├── item_message.xml
│       │       │   ├── item_project_card.xml
│       │       │   └── dialog_voice_input.xml
│       │       └── raw/
│       │           ├── assistant_voice.mp3    # Audio feedback
│       │           └── notification_sound.mp3
├── daemon-sdk/                                 # NEW: Daemon SDK module
│   ├── src/
│   │   └── main/
│   │       └── java/com/orchestrator/daemon/
│   │           ├── DaemonSDK.kt
│   │           ├── WebSocketManager.kt
│   │           ├── RequestBuilder.kt
│   │           └── ResponseParser.kt
└── docs/
    ├── DAEMON_INTEGRATION.md
    ├── NATURAL_LANGUAGE_GUIDE.md
    └── VOICE_COMMANDS.md
```

## Technology Stack (Updated)

### Core Technologies
- **Kotlin**: Primary development language
- **Jetpack Compose**: Modern UI framework
- **WebSocket**: Real-time daemon communication
- **Coroutines & Flow**: Reactive programming
- **Proto DataStore**: Session persistence

### New Dependencies
```gradle
dependencies {
    // Existing dependencies...
    
    // WebSocket for daemon
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
    implementation 'org.java-websocket:Java-WebSocket:1.5.4'
    
    // Voice and speech
    implementation 'com.google.android.gms:play-services-mlkit-text-recognition:19.0.0'
    implementation 'com.google.android.gms:play-services-mlkit-language-id:17.0.0'
    
    // Markdown rendering
    implementation 'io.noties.markwon:core:4.6.2'
    implementation 'io.noties.markwon:ext-tables:4.6.2'
    implementation 'io.noties.markwon:syntax-highlight:4.6.2'
    
    // Session management
    implementation 'androidx.datastore:datastore:1.0.0'
    implementation 'androidx.datastore:datastore-preferences:1.0.0'
    
    // Offline support
    implementation 'androidx.work:work-runtime-ktx:2.9.0'
    
    // JWT for auth
    implementation 'com.auth0.android:jwtdecode:2.0.2'
}
```

## Core Features - Claude Daemon Integration

### 1. Natural Language Chat Interface

```kotlin
// ui/chat/ChatScreen.kt
@Composable
fun ChatScreen(
    viewModel: ChatViewModel = hiltViewModel()
) {
    val messages by viewModel.messages.collectAsState()
    val connectionState by viewModel.connectionState.collectAsState()
    val isTyping by viewModel.isClaudeTyping.collectAsState()
    
    Column(modifier = Modifier.fillMaxSize()) {
        // Connection status bar
        ConnectionStatusBar(state = connectionState)
        
        // Chat messages
        LazyColumn(
            modifier = Modifier.weight(1f),
            reverseLayout = true,
            contentPadding = PaddingValues(16.dp)
        ) {
            if (isTyping) {
                item { TypingIndicator() }
            }
            
            items(messages.reversed()) { message ->
                ChatMessageBubble(
                    message = message,
                    onProjectClick = { projectId ->
                        viewModel.navigateToProject(projectId)
                    },
                    onCodeBlockCopy = { code ->
                        viewModel.copyToClipboard(code)
                    }
                )
            }
        }
        
        // Message composer with voice input
        MessageComposer(
            onSendMessage = { text ->
                viewModel.sendMessage(text)
            },
            onVoiceInput = {
                viewModel.startVoiceInput()
            },
            onAttachFile = {
                viewModel.attachSpecFile()
            }
        )
    }
}

@Composable
fun ChatMessageBubble(
    message: ChatMessage,
    onProjectClick: (String) -> Unit,
    onCodeBlockCopy: (String) -> Unit
) {
    val isFromUser = message.sender == MessageSender.USER
    
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isFromUser) Arrangement.End else Arrangement.Start
    ) {
        Card(
            modifier = Modifier.widthIn(max = 320.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (isFromUser)
                    MaterialTheme.colorScheme.primary
                else
                    MaterialTheme.colorScheme.surfaceVariant
            )
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                // Render markdown content
                MarkdownContent(
                    markdown = message.content,
                    onLinkClick = { url ->
                        if (url.startsWith("project://")) {
                            onProjectClick(url.removePrefix("project://"))
                        }
                    },
                    onCodeBlockLongPress = onCodeBlockCopy
                )
                
                // Show interactive elements if present
                message.interactiveElements?.let { elements ->
                    InteractiveElements(
                        elements = elements,
                        onAction = { action ->
                            viewModel.executeAction(action)
                        }
                    )
                }
                
                // Timestamp
                Text(
                    text = formatRelativeTime(message.timestamp),
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }
    }
}
```

### 2. Daemon WebSocket Client

```kotlin
// daemon/DaemonWebSocket.kt
class DaemonWebSocket @Inject constructor(
    private val authManager: AuthManager,
    private val sessionHandler: SessionHandler,
    private val messageQueue: MessageQueue
) {
    private var webSocket: WebSocket? = null
    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState = _connectionState.asStateFlow()
    
    private val _messages = MutableSharedFlow<DaemonMessage>()
    val messages = _messages.asSharedFlow()
    
    fun connect() {
        val token = authManager.getToken() ?: return
        val wsUrl = "${DAEMON_URL}/ws/daemon?token=$token"
        
        val request = Request.Builder()
            .url(wsUrl)
            .build()
        
        webSocket = OkHttpClient().newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                _connectionState.value = ConnectionState.CONNECTED
                
                // Restore session context
                sessionHandler.getSessionId()?.let { sessionId ->
                    sendMessage(DaemonRequest.RestoreSession(sessionId))
                }
                
                // Process queued messages
                processOfflineQueue()
            }
            
            override fun onMessage(webSocket: WebSocket, text: String) {
                handleDaemonMessage(text)
            }
            
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                _connectionState.value = ConnectionState.ERROR
                scheduleReconnection()
            }
        })
    }
    
    private fun handleDaemonMessage(text: String) {
        val message = parseDaemonMessage(text)
        
        when (message) {
            is DaemonMessage.Response -> {
                // Claude's response to user query
                _messages.tryEmit(message)
            }
            is DaemonMessage.ProjectUpdate -> {
                // Real-time project status update
                updateProjectStatus(message.project)
            }
            is DaemonMessage.TeamNotification -> {
                // Agent communication
                showTeamNotification(message)
            }
            is DaemonMessage.ToolExecution -> {
                // MCP tool execution feedback
                handleToolExecution(message)
            }
        }
    }
    
    fun sendMessage(request: DaemonRequest) {
        when (_connectionState.value) {
            ConnectionState.CONNECTED -> {
                webSocket?.send(request.toJson())
            }
            else -> {
                // Queue for later
                messageQueue.enqueue(request)
            }
        }
    }
    
    private suspend fun processOfflineQueue() {
        messageQueue.getAll().forEach { request ->
            sendMessage(request)
            delay(100) // Rate limiting
        }
        messageQueue.clear()
    }
}
```

### 3. Natural Language Request Examples

```kotlin
// daemon/RequestBuilder.kt
class RequestBuilder {
    fun buildProjectCreationRequest(userInput: String): DaemonRequest {
        return DaemonRequest.NaturalLanguage(
            prompt = userInput,
            context = DaemonContext(
                intent = "create_project",
                preferredTools = listOf("create_orchestration_project"),
                sessionId = getCurrentSessionId()
            )
        )
    }
    
    fun buildStatusCheckRequest(userInput: String): DaemonRequest {
        return DaemonRequest.NaturalLanguage(
            prompt = userInput,
            context = DaemonContext(
                intent = "check_status",
                preferredTools = listOf("get_team_status", "analyze_project_health"),
                includeHistory = true
            )
        )
    }
    
    fun buildBatchProcessingRequest(specFiles: List<Uri>): DaemonRequest {
        return DaemonRequest.BatchProcess(
            prompt = "Process these specification files sequentially",
            files = specFiles.map { uri ->
                FileAttachment(
                    uri = uri,
                    content = readFileContent(uri),
                    mimeType = "text/markdown"
                )
            },
            options = BatchOptions(
                sequential = true,
                notifyOnEach = true,
                continueOnError = false
            )
        )
    }
}

// Example natural language interactions
class NaturalLanguageExamples {
    val examples = listOf(
        "Create a new web app project with authentication",
        "Show me the status of all running projects",
        "What's the developer agent doing in the frontend project?",
        "Deploy the API service to production server",
        "Run tests on the backend project",
        "Show git status for all projects",
        "Which agents need credit refills?",
        "Schedule a check-in for the mobile project in 2 hours",
        "Create a React dashboard with chart components",
        "Debug the failing tests in the e-commerce project"
    )
}
```

### 4. Voice Integration

```kotlin
// ui/chat/VoiceInput.kt
@Composable
fun VoiceInputDialog(
    onDismiss: () -> Unit,
    onTranscription: (String) -> Unit
) {
    val speechRecognizer = rememberSpeechRecognizer()
    var isListening by remember { mutableStateOf(false) }
    var transcription by remember { mutableStateOf("") }
    var partialResult by remember { mutableStateOf("") }
    
    LaunchedEffect(Unit) {
        speechRecognizer.setRecognitionListener(object : RecognitionListener {
            override fun onPartialResults(bundle: Bundle) {
                val partial = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                partialResult = partial?.firstOrNull() ?: ""
            }
            
            override fun onResults(bundle: Bundle) {
                val results = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                transcription = results?.firstOrNull() ?: ""
                isListening = false
                onTranscription(transcription)
                onDismiss()
            }
            
            override fun onError(error: Int) {
                handleSpeechError(error)
                isListening = false
            }
        })
    }
    
    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // Animated voice wave
                VoiceWaveAnimation(
                    isActive = isListening,
                    modifier = Modifier.size(120.dp)
                )
                
                Spacer(modifier = Modifier.height(16.dp))
                
                Text(
                    text = if (isListening) "Listening..." else "Tap to speak",
                    style = MaterialTheme.typography.headlineSmall
                )
                
                if (partialResult.isNotEmpty()) {
                    Text(
                        text = partialResult,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(top = 8.dp)
                    )
                }
                
                Spacer(modifier = Modifier.height(24.dp))
                
                Row(
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    OutlinedButton(onClick = onDismiss) {
                        Text("Cancel")
                    }
                    
                    Button(
                        onClick = {
                            if (isListening) {
                                speechRecognizer.stopListening()
                            } else {
                                startListening(speechRecognizer)
                                isListening = true
                            }
                        }
                    ) {
                        Icon(
                            imageVector = if (isListening) Icons.Default.Stop else Icons.Default.Mic,
                            contentDescription = null
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(if (isListening) "Stop" else "Start")
                    }
                }
            }
        }
    }
}
```

### 5. Offline Queue Management

```kotlin
// daemon/MessageQueue.kt
@Singleton
class MessageQueue @Inject constructor(
    @ApplicationContext private val context: Context,
    private val dataStore: DataStore<Preferences>
) {
    private val queuedMessages = mutableListOf<QueuedMessage>()
    
    data class QueuedMessage(
        val id: String = UUID.randomUUID().toString(),
        val request: DaemonRequest,
        val timestamp: Long = System.currentTimeMillis(),
        val retryCount: Int = 0,
        val priority: Priority = Priority.NORMAL
    )
    
    enum class Priority { LOW, NORMAL, HIGH, URGENT }
    
    suspend fun enqueue(request: DaemonRequest, priority: Priority = Priority.NORMAL) {
        val message = QueuedMessage(
            request = request,
            priority = priority
        )
        
        queuedMessages.add(message)
        queuedMessages.sortByDescending { it.priority.ordinal }
        
        // Persist to DataStore
        persistQueue()
        
        // Show notification
        showOfflineNotification(request)
    }
    
    suspend fun processQueue(connection: DaemonWebSocket): ProcessResult {
        val results = mutableListOf<Boolean>()
        val toRetry = mutableListOf<QueuedMessage>()
        
        for (message in queuedMessages.toList()) {
            try {
                connection.sendMessage(message.request)
                results.add(true)
                queuedMessages.remove(message)
                
                // Small delay to avoid overwhelming the server
                delay(100)
            } catch (e: Exception) {
                if (message.retryCount < MAX_RETRIES) {
                    toRetry.add(message.copy(retryCount = message.retryCount + 1))
                } else {
                    // Move to failed queue
                    moveToFailedQueue(message)
                }
                results.add(false)
            }
        }
        
        queuedMessages.clear()
        queuedMessages.addAll(toRetry)
        persistQueue()
        
        return ProcessResult(
            total = results.size,
            successful = results.count { it },
            failed = results.count { !it }
        )
    }
    
    private suspend fun persistQueue() {
        dataStore.edit { preferences ->
            preferences[QUEUE_KEY] = Json.encodeToString(queuedMessages)
        }
    }
    
    suspend fun loadQueue() {
        dataStore.data.first()[QUEUE_KEY]?.let { json ->
            queuedMessages.clear()
            queuedMessages.addAll(Json.decodeFromString(json))
        }
    }
    
    companion object {
        private val QUEUE_KEY = stringPreferencesKey("offline_queue")
        private const val MAX_RETRIES = 3
    }
}
```

### 6. Session Management

```kotlin
// daemon/SessionHandler.kt
@Singleton
class SessionHandler @Inject constructor(
    private val dataStore: DataStore<Preferences>,
    private val authManager: AuthManager
) {
    private var currentSession: DaemonSession? = null
    
    data class DaemonSession(
        val sessionId: String,
        val userId: String,
        val deviceId: String,
        val createdAt: Long,
        val lastActivity: Long,
        val context: SessionContext
    )
    
    data class SessionContext(
        val activeProjects: List<String> = emptyList(),
        val recentCommands: List<String> = emptyList(),
        val preferences: Map<String, Any> = emptyMap()
    )
    
    suspend fun createSession(): DaemonSession {
        val session = DaemonSession(
            sessionId = UUID.randomUUID().toString(),
            userId = authManager.getUserId(),
            deviceId = getDeviceId(),
            createdAt = System.currentTimeMillis(),
            lastActivity = System.currentTimeMillis(),
            context = SessionContext()
        )
        
        currentSession = session
        persistSession(session)
        
        return session
    }
    
    suspend fun restoreSession(): DaemonSession? {
        return dataStore.data.first()[SESSION_KEY]?.let { json ->
            try {
                val session = Json.decodeFromString<DaemonSession>(json)
                
                // Check if session is still valid (not expired)
                if (isSessionValid(session)) {
                    currentSession = session
                    session
                } else {
                    null
                }
            } catch (e: Exception) {
                null
            }
        }
    }
    
    fun updateContext(update: (SessionContext) -> SessionContext) {
        currentSession?.let { session ->
            currentSession = session.copy(
                lastActivity = System.currentTimeMillis(),
                context = update(session.context)
            )
            
            CoroutineScope(Dispatchers.IO).launch {
                persistSession(currentSession!!)
            }
        }
    }
    
    private suspend fun persistSession(session: DaemonSession) {
        dataStore.edit { preferences ->
            preferences[SESSION_KEY] = Json.encodeToString(session)
        }
    }
    
    private fun isSessionValid(session: DaemonSession): Boolean {
        val hoursSinceLastActivity = 
            (System.currentTimeMillis() - session.lastActivity) / (1000 * 60 * 60)
        return hoursSinceLastActivity < 24 // Session valid for 24 hours
    }
    
    companion object {
        private val SESSION_KEY = stringPreferencesKey("daemon_session")
    }
}
```

### 7. Rich Notifications

```kotlin
// services/NotificationService.kt
class EnhancedNotificationService @Inject constructor(
    @ApplicationContext private val context: Context
) {
    fun showDaemonNotification(message: DaemonMessage) {
        when (message) {
            is DaemonMessage.ProjectComplete -> {
                showProjectCompleteNotification(message)
            }
            is DaemonMessage.AgentMessage -> {
                showAgentMessageNotification(message)
            }
            is DaemonMessage.ErrorAlert -> {
                showErrorNotification(message)
            }
        }
    }
    
    private fun showProjectCompleteNotification(message: DaemonMessage.ProjectComplete) {
        val notification = NotificationCompat.Builder(context, CHANNEL_SUCCESS)
            .setContentTitle("Project Complete! 🎉")
            .setContentText("${message.projectName} finished successfully")
            .setStyle(NotificationCompat.BigTextStyle().bigText(
                """
                Project: ${message.projectName}
                Duration: ${formatDuration(message.duration)}
                Tasks Completed: ${message.tasksCompleted}
                Test Coverage: ${message.testCoverage}%
                
                Tap to view full report
                """.trimIndent()
            ))
            .setSmallIcon(R.drawable.ic_check_circle)
            .setColor(Color.GREEN)
            .addAction(
                R.drawable.ic_view,
                "View Report",
                createViewReportIntent(message.projectId)
            )
            .addAction(
                R.drawable.ic_share,
                "Share",
                createShareIntent(message)
            )
            .setAutoCancel(true)
            .build()
        
        notificationManager.notify(message.projectId.hashCode(), notification)
    }
}
```

## Security Enhancements

### JWT Authentication with Daemon

```kotlin
// daemon/AuthManager.kt
@Singleton
class DaemonAuthManager @Inject constructor(
    private val secureStorage: SecureStorage,
    private val biometricManager: BiometricManager
) {
    private var currentToken: String? = null
    
    suspend fun authenticate(): Result<String> {
        // Try biometric first
        if (biometricManager.canAuthenticate()) {
            val biometricResult = biometricManager.authenticate()
            if (biometricResult.isFailure) {
                return Result.failure(biometricResult.exceptionOrNull()!!)
            }
        }
        
        // Get stored credentials
        val credentials = secureStorage.getCredentials()
            ?: return Result.failure(Exception("No stored credentials"))
        
        // Request token from daemon
        val tokenRequest = TokenRequest(
            userId = credentials.userId,
            deviceId = getDeviceId(),
            deviceName = getDeviceName()
        )
        
        return try {
            val response = daemonApi.requestToken(tokenRequest)
            currentToken = response.token
            secureStorage.saveToken(response.token)
            Result.success(response.token)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    fun refreshToken() {
        // Implement token refresh logic
    }
}
```

## Testing Strategy

### Daemon Integration Tests

```kotlin
@Test
fun testDaemonConnection() = runTest {
    val daemon = DaemonWebSocket(mockAuth, mockSession, mockQueue)
    
    daemon.connect()
    advanceUntilIdle()
    
    assertEquals(ConnectionState.CONNECTED, daemon.connectionState.value)
}

@Test
fun testNaturalLanguageProcessing() = runTest {
    val daemon = createConnectedDaemon()
    
    daemon.sendMessage(
        DaemonRequest.NaturalLanguage("Create a new React project with TypeScript")
    )
    
    val response = daemon.messages.first()
    assertTrue(response is DaemonMessage.Response)
    assertTrue(response.content.contains("project"))
}

@Test
fun testOfflineQueueing() = runTest {
    val queue = MessageQueue(context, dataStore)
    
    // Queue messages while offline
    queue.enqueue(DaemonRequest.NaturalLanguage("Check project status"))
    queue.enqueue(DaemonRequest.NaturalLanguage("Run tests"))
    
    assertEquals(2, queue.size())
    
    // Process when connected
    val daemon = createConnectedDaemon()
    val result = queue.processQueue(daemon)
    
    assertEquals(2, result.successful)
    assertEquals(0, queue.size())
}
```

## Deployment Configuration

### Build Variants for Daemon Environments

```gradle
android {
    flavorDimensions += "daemon"
    productFlavors {
        create("localDaemon") {
            dimension = "daemon"
            buildConfigField("String", "DAEMON_URL", "\"ws://10.0.2.2:8080\"")
            buildConfigField("String", "DAEMON_API", "\"http://10.0.2.2:8080\"")
        }
        
        create("cloudDaemon") {
            dimension = "daemon"
            buildConfigField("String", "DAEMON_URL", "\"wss://daemon.orchestrator.cloud\"")
            buildConfigField("String", "DAEMON_API", "\"https://api.orchestrator.cloud\"")
        }
        
        create("enterpriseDaemon") {
            dimension = "daemon"
            buildConfigField("String", "DAEMON_URL", "\"wss://daemon.company.internal\"")
            buildConfigField("String", "DAEMON_API", "\"https://api.company.internal\"")
        }
    }
}
```

## User Experience Enhancements

### Intelligent Suggestions

```kotlin
// ui/chat/SuggestionChips.kt
@Composable
fun SuggestionChips(
    projectContext: ProjectContext?,
    onSuggestionClick: (String) -> Unit
) {
    val suggestions = remember(projectContext) {
        generateSmartSuggestions(projectContext)
    }
    
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(horizontal = 16.dp)
    ) {
        items(suggestions) { suggestion ->
            SuggestionChip(
                onClick = { onSuggestionClick(suggestion.command) },
                label = { Text(suggestion.label) },
                leadingIcon = {
                    Icon(
                        imageVector = suggestion.icon,
                        contentDescription = null
                    )
                }
            )
        }
    }
}

fun generateSmartSuggestions(context: ProjectContext?): List<Suggestion> {
    return when {
        context == null -> listOf(
            Suggestion("Create new project", Icons.Default.Add, "Create a new project"),
            Suggestion("Show all projects", Icons.Default.List, "Show me all projects"),
            Suggestion("Check system health", Icons.Default.Monitor, "How's the system doing?")
        )
        context.hasFailingTests -> listOf(
            Suggestion("Debug tests", Icons.Default.BugReport, "Help me debug the failing tests"),
            Suggestion("Run tests again", Icons.Default.Refresh, "Run the test suite again")
        )
        context.hasUncommittedChanges -> listOf(
            Suggestion("Commit changes", Icons.Default.Save, "Commit the current changes"),
            Suggestion("Show diff", Icons.Default.Compare, "Show me what changed")
        )
        else -> listOf(
            Suggestion("Status update", Icons.Default.Info, "What's the current status?"),
            Suggestion("Next task", Icons.Default.ArrowForward, "What should we work on next?")
        )
    }
}
```

### Interactive Tutorial

```kotlin
// ui/onboarding/InteractiveTutorial.kt
@Composable
fun InteractiveTutorial(
    onComplete: () -> Unit
) {
    var currentStep by remember { mutableStateOf(0) }
    
    val steps = listOf(
        TutorialStep(
            title = "Welcome to Orchestrator",
            content = "I'm Claude, your AI orchestration assistant. I can help you manage development projects with teams of AI agents.",
            action = "Try saying: 'Show me an example project'"
        ),
        TutorialStep(
            title = "Natural Language Commands",
            content = "Just tell me what you want in plain English. I'll understand and execute the right commands.",
            action = "Try: 'Create a simple web app with authentication'"
        ),
        TutorialStep(
            title = "Voice Commands",
            content = "Tap the microphone button to use voice commands. Perfect for hands-free operation.",
            action = "Tap the mic and say: 'Check project status'"
        ),
        TutorialStep(
            title = "Offline Mode",
            content = "Your commands are queued when offline and automatically sent when you reconnect.",
            action = "Try turning off WiFi and sending a message"
        )
    )
    
    // Tutorial UI implementation...
}
```

This enhanced mobile app specification transforms the application into an intelligent, conversational interface for the Claude Daemon, providing natural language interaction, offline capabilities, voice commands, and seamless session management while maintaining the core orchestration functionality.
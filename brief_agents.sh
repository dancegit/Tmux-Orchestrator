#!/bin/bash
SESSION="MOBILE-APP-SPEC-V2-416343a3"

echo "Briefing agents for Mobile App Spec V2 project..."

# Brief Orchestrator
echo "Briefing Orchestrator..."
./send-claude-message.sh "$SESSION:0" "You are the Orchestrator for the Mobile App Spec V2 project. This is an Android application that integrates with Claude Daemon server for AI orchestration. Your team will build a Kotlin-based mobile app with WebSocket communication to the daemon. 

Key responsibilities:
- Coordinate between Developer, Tester, PM and TestRunner
- Monitor implementation of chat interface, daemon integration, and voice features
- Ensure offline capability and session persistence are properly implemented
- Track progress on all app components

The spec is at /home/clauderun/mobile_app_spec_v2/MOBILE_APP_SPEC_V2.md. Start by reviewing the spec and coordinating team tasks."

sleep 3

# Brief Project Manager
echo "Briefing Project Manager..."
./send-claude-message.sh "$SESSION:1" "You are the Project Manager for the Mobile App Spec V2 project. This is an Android Kotlin app with Claude Daemon integration.

Your responsibilities:
- Maintain exceptionally high quality standards for the mobile app
- Review all code implementations (Kotlin, Compose UI, WebSocket)
- Coordinate git workflow between team members
- Track progress on chat interface, daemon SDK, and voice features
- Ensure proper testing of offline queue and session management

Review the spec at /home/clauderun/mobile_app_spec_v2/MOBILE_APP_SPEC_V2.md and start coordinating with the team."

sleep 3

# Brief Developer
echo "Briefing Developer..."
./send-claude-message.sh "$SESSION:2" "You are the Developer for the Mobile App Spec V2 project. Your task is to implement an Android app in Kotlin with Jetpack Compose that communicates with Claude Daemon via WebSocket.

Key implementation areas:
- Chat interface with MessageComposer and MessageBubble components
- DaemonClient with WebSocket real-time communication
- Offline message queue for resilience
- Voice input/output integration
- Session persistence with Proto DataStore
- Daemon SDK module for reusable components

The full spec is at /home/clauderun/mobile_app_spec_v2/MOBILE_APP_SPEC_V2.md. Begin implementation focusing on the core daemon integration first."

sleep 3

# Brief Tester
echo "Briefing Tester..."
./send-claude-message.sh "$SESSION:3" "You are the Tester for the Mobile App Spec V2 project. Your role is to create comprehensive tests for this Android Kotlin application.

Test coverage needed:
- Unit tests for DaemonClient and WebSocket communication
- UI tests for chat interface with Compose testing
- Integration tests for offline queue and sync
- Voice recognition and TTS testing
- Session persistence and state management tests
- End-to-end daemon communication scenarios

Review the spec at /home/clauderun/mobile_app_spec_v2/MOBILE_APP_SPEC_V2.md and begin creating test plans."

sleep 3

# Brief TestRunner
echo "Briefing TestRunner..."
./send-claude-message.sh "$SESSION:4" "You are the TestRunner for the Mobile App Spec V2 project. Your job is to execute all tests for this Android Kotlin application.

Your responsibilities:
- Run unit tests for daemon integration components
- Execute Compose UI tests
- Perform integration tests with mock daemon
- Monitor test coverage metrics
- Report failures to Developer and Tester
- Set up CI/CD test pipelines for Android

Work with the Tester to get test suites and ensure comprehensive coverage. The spec is at /home/clauderun/mobile_app_spec_v2/MOBILE_APP_SPEC_V2.md."

echo "All agents briefed successfully!"

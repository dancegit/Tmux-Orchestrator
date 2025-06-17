# Claude.md - Tmux Orchestrator Project Knowledge Base

## Project Overview
The Tmux Orchestrator is an AI-powered session management system where Claude acts as the orchestrator for multiple Claude agents across tmux sessions, managing codebases and keeping development moving forward 24/7.

## Critical Lessons Learned

### Tmux Window Management Mistakes and Solutions

#### Mistake 1: Wrong Directory When Creating Windows
**What Went Wrong**: Created server window without specifying directory, causing uvicorn to run in wrong location (Tmux orchestrator instead of Glacier-Analytics)

**Root Cause**: New tmux windows inherit the working directory from where tmux was originally started, NOT from the current session's active window

**Solution**: 
```bash
# Always use -c flag when creating windows
tmux new-window -t session -n "window-name" -c "/correct/path"

# Or immediately cd after creating
tmux new-window -t session -n "window-name"
tmux send-keys -t session:window-name "cd /correct/path" Enter
```

#### Mistake 2: Not Reading Actual Command Output
**What Went Wrong**: Assumed commands like `uvicorn app.main:app` succeeded without checking output

**Root Cause**: Not using `tmux capture-pane` to verify command results

**Solution**:
```bash
# Always check output after running commands
tmux send-keys -t session:window "command" Enter
sleep 2  # Give command time to execute
tmux capture-pane -t session:window -p | tail -50
```

#### Mistake 3: Typing Commands in Already Active Sessions
**What Went Wrong**: Typed "claude" in a window that already had Claude running

**Root Cause**: Not checking window contents before sending commands

**Solution**:
```bash
# Check window contents first
tmux capture-pane -t session:window -S -100 -p
# Look for prompts or active sessions before sending commands
```

#### Mistake 4: Incorrect Message Sending to Claude Agents
**What Went Wrong**: Initially sent Enter key with the message text instead of as separate command

**Root Cause**: Using `tmux send-keys -t session:window "message" Enter` combines them

**Solution**:
```bash
# Send message and Enter separately
tmux send-keys -t session:window "Your message here"
tmux send-keys -t session:window Enter
```

## Best Practices for Tmux Orchestration

### Pre-Command Checks
1. **Verify Working Directory**
   ```bash
   tmux send-keys -t session:window "pwd" Enter
   tmux capture-pane -t session:window -p | tail -5
   ```

2. **Check Command Availability**
   ```bash
   tmux send-keys -t session:window "which command_name" Enter
   tmux capture-pane -t session:window -p | tail -5
   ```

3. **Check for Virtual Environments**
   ```bash
   tmux send-keys -t session:window "ls -la | grep -E 'venv|env|virtualenv'" Enter
   ```

### Window Creation Workflow
```bash
# 1. Create window with correct directory
tmux new-window -t session -n "descriptive-name" -c "/path/to/project"

# 2. Verify you're in the right place
tmux send-keys -t session:descriptive-name "pwd" Enter
sleep 1
tmux capture-pane -t session:descriptive-name -p | tail -3

# 3. Activate virtual environment if needed
tmux send-keys -t session:descriptive-name "source venv/bin/activate" Enter

# 4. Run your command
tmux send-keys -t session:descriptive-name "your-command" Enter

# 5. Verify it started correctly
sleep 3
tmux capture-pane -t session:descriptive-name -p | tail -20
```

### Debugging Failed Commands
When a command fails:
1. Capture full window output: `tmux capture-pane -t session:window -S -200 -p`
2. Check for common issues:
   - Wrong directory
   - Missing dependencies
   - Virtual environment not activated
   - Permission issues
   - Port already in use

### Communication with Claude Agents
1. **Starting Claude in a Window**
   ```bash
   # First check if Claude is already running
   tmux capture-pane -t session:window -p | grep -E "Claude|>"
   
   # If not running, start it
   tmux send-keys -t session:window "claude" Enter
   
   # Wait for it to start
   sleep 5
   
   # Verify it's ready
   tmux capture-pane -t session:window -p | tail -20
   ```

2. **Sending Messages to Claude**
   ```bash
   # Send your message (WITHOUT Enter)
   tmux send-keys -t session:window "Your detailed message here"
   
   # CRITICAL: Wait for Claude's UI to register the text
   sleep 1
   
   # Send Enter separately
   tmux send-keys -t session:window Enter
   
   # Wait for processing
   sleep 5
   
   # Check response
   tmux capture-pane -t session:window -p | tail -50
   ```
   
   **Why the sleep is critical**: Claude's interface needs time to register text input before Enter can be processed. Sending Enter too quickly after text will cause it to be ignored. Always add at least 1 second delay between sending text and Enter.

## Common Project-Specific Issues

### Glacier Backend Server
- **Location**: `/Users/jasonedward/Coding/Glacier-Analytics`
- **Server Command**: `uvicorn app.main:app --reload`
- **Common Issues**:
  - Needs virtual environment activated first
  - Check for `.env` file with required variables
  - Default port is 8000

### Glacier Frontend
- **Location**: `/Users/jasonedward/Coding/glacier-frontend`
- **Dev Server**: `npm run dev`
- **Default Port**: Usually 3000 or specified in package.json

## Orchestrator-Specific Patterns

### Agent Communication & Assistance

**Critical Insight**: You can send messages to agents even when they're busy! Messages will be queued and the agent will see them after their current task.

#### When to Send Queued Messages:
1. **Cross-Window Intelligence**: You see errors or important info in one window that the agent needs
2. **Steering Guidance**: Agent seems stuck or heading in wrong direction
3. **Resource Sharing**: You have access to information from other sessions/windows
4. **Proactive Assistance**: Preventing issues before they become blockers

#### Examples of Helpful Interventions:
```bash
# Frontend agent struggling with port issues, but you see in npm window:
"I see in your npm-run-dev window that the server is running on port 3002, not 3001"

# Backend agent looking for files, but you checked another window:
"The frontend is using /api/v1/public/* endpoints - I confirmed this from their window"

# Agent getting errors you can see in server logs:
"Check the server window - seeing 'module not found' errors for uvicorn"

# Sharing cross-session insights:
"The ai-chat session has auth working with Clerk - might help with your implementation"
```

#### Your Orchestrator Advantages:
1. **Multi-Window Vision**: See all windows across all sessions
2. **Cross-Project Knowledge**: Connect solutions from different codebases
3. **Real-Time Monitoring**: Spot issues as they happen in logs/servers
4. **Pattern Recognition**: Notice similar problems across projects

#### Best Practices:
- Always specify WHERE you saw the information ("in your server window", "from the frontend agent")
- Be specific about errors/issues you observe
- Suggest concrete next steps based on what you see
- Use your bird's-eye view to prevent agents from duplicating work

### Checking All Sessions Status
```python
# Use the orchestrator tools
python3 claude_control.py summary

# Or manually check each session
for session in $(tmux list-sessions -F "#{session_name}"); do
    echo "=== Session: $session ==="
    tmux list-windows -t $session
done
```

### Coordinating Between Agents
1. Always verify both agents are ready before cross-communication
2. Use clear, specific messages about what you need
3. Wait for responses before proceeding
4. Document any dependencies between projects

## Remember: Always Learn from Mistakes
When something goes wrong:
1. Document it immediately in this file
2. Include the specific error
3. Explain why it happened
4. Document how to prevent it
5. Add any commands that would have caught it earlier

This creates a growing knowledge base that prevents repeated mistakes and improves orchestration efficiency.

## CRITICAL: Always Schedule Next Check-in Before Ending

**NEVER end a conversation without scheduling your return!**

### Using schedule_with_note.sh
```bash
# Schedule check-in with practical note about what to check
./schedule_with_note.sh <minutes> "<practical note about what to check>"

# Examples of GOOD notes:
./schedule_with_note.sh 5 "Check if frontend agent finished identifying used endpoints"
./schedule_with_note.sh 10 "Verify backend cleanup completed and no endpoints are broken"
./schedule_with_note.sh 3 "Check server logs for errors, review agent progress on migrations"
./schedule_with_note.sh 15 "Review if DuckDB data load completed, check for any errors"
./schedule_with_note.sh 0.5 "Quick check on agent response to endpoint question"

# Examples of BAD notes (too vague/motivational):
# "Victory awaits!" 
# "Continue the great work!"
# "Legendary progress incoming!"
```

**Technical Note**: The script now properly sends Enter as a separate command after a 1-second delay, following our tmux communication best practices.

### When to Schedule Check-ins
- **Quick tasks (2-5 min)**: Check back in 5 minutes
- **Medium tasks (5-15 min)**: Check back in 10-15 minutes  
- **Long tasks (15+ min)**: Check back in 20-30 minutes
- **Overnight tasks**: Check back in 1-2 hours

### What to Include in Notes
1. **Specific tasks to check**: "Verify frontend test results"
2. **Agent coordination**: "Check if backend agent responded about directory structure"
3. **Error monitoring**: "Review server logs for connection errors"
4. **Progress tracking**: "Check if data migration completed"
5. **Next steps**: "Ready to start endpoint cleanup after getting used endpoints list"

### Check-in Workflow
When you return from a scheduled check-in:
1. First run `python3 claude_control.py summary` to get overall status
2. Check specific windows mentioned in your note
3. Address any errors or blockers
4. Coordinate next steps between agents
5. Schedule your next check-in before leaving

### Example End-of-Session Pattern
```bash
# Before ending any orchestrator session:
# 1. Keep the note SHORT (what to check)
./schedule_with_note.sh 1 "Check frontend endpoint analysis"

# 2. Provide detailed status summary separately
```

Then provide a **Current Status Summary** with:
- ✅ Completed tasks
- ⏳ In-progress work  
- 📅 Next steps
- Any important context (ports, file paths, etc.)

This ensures continuous orchestration without gaps or forgotten tasks.

**Note**: schedule_with_note.sh accepts decimal minutes (0.17 for 10 seconds, 0.5 for 30 seconds, 1.5 for 90 seconds, etc.)
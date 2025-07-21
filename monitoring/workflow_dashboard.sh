#!/bin/bash
# Workflow Dashboard - Combined view of all monitoring data

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REGISTRY_DIR="$(dirname "$SCRIPT_DIR")/registry"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get current project
find_active_project() {
    local latest_project=""
    local latest_time=0
    
    if [ -d "$REGISTRY_DIR/projects" ]; then
        for project in "$REGISTRY_DIR/projects"/*; do
            if [ -d "$project/worktrees" ]; then
                mtime=$(stat -c %Y "$project" 2>/dev/null || stat -f %m "$project" 2>/dev/null)
                if [ "$mtime" -gt "$latest_time" ]; then
                    latest_time=$mtime
                    latest_project=$(basename "$project")
                fi
            fi
        done
    fi
    
    echo "$latest_project"
}

PROJECT=$(find_active_project)
TODAY=$(date +%Y-%m-%d)

echo "=== TMUX ORCHESTRATOR WORKFLOW STATUS ==="
echo "Updated: $(date '+%Y-%m-%d %H:%M:%S') | Project: ${PROJECT:-unknown}"
echo ""

# Communication Compliance
echo "COMMUNICATION COMPLIANCE:"
COMM_LOG="$REGISTRY_DIR/logs/communications/$TODAY/messages.jsonl"
VIOLATIONS_LOG="$REGISTRY_DIR/logs/communications/$TODAY/violations.jsonl"

if [ -f "$COMM_LOG" ]; then
    MSG_COUNT=$(wc -l < "$COMM_LOG")
    echo -e "${GREEN}✓${NC} Monitored messaging active ($MSG_COUNT messages today)"
    
    if [ -f "$VIOLATIONS_LOG" ]; then
        VIOLATION_COUNT=$(wc -l < "$VIOLATIONS_LOG")
        if [ "$VIOLATION_COUNT" -gt 0 ]; then
            echo -e "${YELLOW}⚠${NC} $VIOLATION_COUNT violations detected today"
            # Show last violation
            LAST_VIOLATION=$(tail -1 "$VIOLATIONS_LOG" | jq -r '.rule + ": " + .details' 2>/dev/null || echo "Parse error")
            echo "    Last: $LAST_VIOLATION"
        fi
    else
        echo -e "${GREEN}✓${NC} No violations detected"
    fi
else
    echo -e "${RED}❌${NC} No communication logs found"
fi

echo ""

# Git Activity
echo "GIT ACTIVITY (30-min rule):"
if [ -x "$SCRIPT_DIR/git_activity_monitor.py" ]; then
    # Run git monitor and parse output
    GIT_OUTPUT=$("$SCRIPT_DIR/git_activity_monitor.py" --json 2>/dev/null)
    
    if [ -n "$GIT_OUTPUT" ]; then
        # Parse agents and their status
        echo "$GIT_OUTPUT" | jq -r '.agents | to_entries[] | 
            .key as $agent | .value as $data |
            if $data.minutes_since_commit != null and $data.uncommitted_changes > 0 and $data.minutes_since_commit > 30 then
                "❌ " + $agent + ": " + ($data.minutes_since_commit|tostring) + "m ago | " + ($data.uncommitted_changes|tostring) + " changes | " + $data.current_branch
            elif $data.unpushed_commits > 0 then
                "⚠ " + $agent + ": " + ($data.unpushed_commits|tostring) + " unpushed | " + $data.current_branch
            else
                "✓ " + $agent + ": " + ($data.minutes_since_commit // 0|tostring) + "m ago | " + $data.current_branch
            end' 2>/dev/null || echo "Git data parsing error"
    else
        echo "No git activity data available"
    fi
else
    echo "Git monitor not found"
fi

echo ""

# GitHub Status
echo "GITHUB STATUS:"
if [ -x "$SCRIPT_DIR/github_activity_monitor.py" ]; then
    GITHUB_OUTPUT=$("$SCRIPT_DIR/github_activity_monitor.py" --json 2>/dev/null)
    
    if [ -n "$GITHUB_OUTPUT" ]; then
        # Check for errors first
        ERROR=$(echo "$GITHUB_OUTPUT" | jq -r '.error // empty' 2>/dev/null)
        if [ -n "$ERROR" ]; then
            echo -e "${YELLOW}⚠${NC} $ERROR"
        else
            # Parse PR counts
            OPEN_PRS=$(echo "$GITHUB_OUTPUT" | jq -r '.open_prs // 0' 2>/dev/null)
            echo "Open PRs: $OPEN_PRS"
            
            # Show PR age distribution
            echo "$GITHUB_OUTPUT" | jq -r '.pr_summary.by_age | to_entries[] | 
                if .value > 0 then
                    "  " + (if .key == ">4h" then "❌" elif .key == "2h-4h" then "⚠" else "✓" end) + " " + .key + ": " + (.value|tostring)
                else empty end' 2>/dev/null
            
            # Show stale PRs
            STALE_COUNT=$(echo "$GITHUB_OUTPUT" | jq '.pr_summary.stale_prs | length' 2>/dev/null || echo 0)
            if [ "$STALE_COUNT" -gt 0 ]; then
                echo -e "  ${RED}❌${NC} $STALE_COUNT stale PRs requiring attention"
            fi
        fi
    else
        echo "No GitHub data available"
    fi
else
    echo "GitHub monitor not found"
fi

echo ""

# Integration Workflow
echo "INTEGRATION WORKFLOW:"
if [ -n "$GITHUB_OUTPUT" ]; then
    HOURS_SINCE=$(echo "$GITHUB_OUTPUT" | jq -r '.integration_status.hours_since_last_integration // "unknown"' 2>/dev/null)
    if [ "$HOURS_SINCE" != "unknown" ] && [ "$HOURS_SINCE" != "null" ]; then
        HOURS_INT=$(echo "$HOURS_SINCE" | cut -d. -f1)
        if [ "$HOURS_INT" -lt 2 ]; then
            echo -e "${GREEN}✓${NC} Last integration: ${HOURS_SINCE}h ago"
        elif [ "$HOURS_INT" -lt 4 ]; then
            echo -e "${YELLOW}⚠${NC} Last integration: ${HOURS_SINCE}h ago"
        else
            echo -e "${RED}❌${NC} Last integration: ${HOURS_SINCE}h ago [VIOLATION]"
        fi
    else
        echo -e "${YELLOW}⚠${NC} No recent integration data"
    fi
fi

echo ""

# Workflow Bottlenecks
echo "WORKFLOW HEALTH:"
if [ -x "$SCRIPT_DIR/workflow_bottleneck_detector.py" ]; then
    BOTTLENECK_OUTPUT=$("$SCRIPT_DIR/workflow_bottleneck_detector.py" --json 2>/dev/null)
    
    if [ -n "$BOTTLENECK_OUTPUT" ]; then
        HEALTH=$(echo "$BOTTLENECK_OUTPUT" | jq -r '.workflow_health' 2>/dev/null || echo "unknown")
        BOTTLENECK_COUNT=$(echo "$BOTTLENECK_OUTPUT" | jq '.bottlenecks | length' 2>/dev/null || echo 0)
        
        case "$HEALTH" in
            "healthy")
                echo -e "${GREEN}✓${NC} Healthy - No bottlenecks detected"
                ;;
            "warning")
                echo -e "${YELLOW}⚠${NC} Warning - $BOTTLENECK_COUNT minor issues"
                ;;
            "degraded")
                echo -e "${YELLOW}⚠${NC} Degraded - $BOTTLENECK_COUNT bottlenecks detected"
                ;;
            "critical")
                echo -e "${RED}❌${NC} Critical - $BOTTLENECK_COUNT severe bottlenecks!"
                ;;
            *)
                echo "Unknown health status"
                ;;
        esac
        
        # Show top recommendations
        if [ "$BOTTLENECK_COUNT" -gt 0 ]; then
            echo ""
            echo "ACTIONS NEEDED:"
            echo "$BOTTLENECK_OUTPUT" | jq -r '.recommendations[]' 2>/dev/null | head -3 | while IFS= read -r rec; do
                echo "  $rec"
            done
        fi
    else
        echo "No bottleneck data available"
    fi
else
    echo "Bottleneck detector not found"
fi

echo ""

# Quick Commands
echo "QUICK COMMANDS:"
echo "  Monitor violations:    cat $REGISTRY_DIR/logs/communications/$TODAY/violations.jsonl | jq ."
echo "  Check git activity:    $SCRIPT_DIR/git_activity_monitor.py"
echo "  View open PRs:         gh pr list"
echo "  Start monitoring:      $SCRIPT_DIR/start_monitoring.sh"
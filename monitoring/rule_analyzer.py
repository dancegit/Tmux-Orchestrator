#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Claude-based rule analyzer for compliance checking
Uses claude --dangerously-skip-permissions to analyze messages against rules
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

class RuleAnalyzer:
    def __init__(self, rules_file: Path):
        self.rules = self._load_rules(rules_file)
        
    def _load_rules(self, rules_file: Path) -> Dict[str, Any]:
        """Load compliance rules from JSON file"""
        with open(rules_file, 'r') as f:
            return json.load(f)
            
    def analyze_message(self, message_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single message for compliance violations"""
        
        # Prepare prompt for Claude
        prompt = self._create_analysis_prompt(message_entry)
        
        # Call Claude with the prompt
        result = self._call_claude(prompt)
        
        # Parse Claude's response
        analysis = self._parse_claude_response(result)
        
        # Add metadata
        analysis['message_id'] = f"{message_entry['timestamp']}_{message_entry['sender']['pane']}"
        analysis['analyzed_at'] = datetime.utcnow().isoformat() + 'Z'
        
        return analysis
        
    def _create_analysis_prompt(self, message: Dict[str, Any]) -> str:
        """Create a structured prompt for Claude to analyze compliance"""
        
        prompt = f"""You are a compliance analyzer for the Tmux Orchestrator system. Analyze the following message against the compliance rules and return ONLY a JSON response.

MESSAGE TO ANALYZE:
{json.dumps(message, indent=2)}

COMPLIANCE RULES:
{json.dumps(self.rules['rules'], indent=2)}

ANALYSIS REQUIREMENTS:
1. Check if the message violates any of the listed rules
2. Consider the sender's role and recipient's role
3. Evaluate the message content and context
4. Return structured JSON with your analysis

EXPECTED JSON FORMAT:
{{
  "compliant": true/false,
  "violations": [
    {{
      "rule_id": "comm-001",
      "rule_description": "Brief description of violated rule",
      "severity": "high/medium/low/critical",
      "explanation": "Why this specific message violates the rule",
      "correction": "How the sender should have communicated instead"
    }}
  ],
  "warnings": [
    {{
      "issue": "Potential issue that's not a clear violation",
      "recommendation": "How to improve"
    }}
  ],
  "positive_notes": ["Any good practices observed"]
}}

Return ONLY the JSON, no other text."""
        
        return prompt
        
    def _call_claude(self, prompt: str) -> str:
        """Call Claude using the CLI with --dangerously-skip-permissions"""
        try:
            # Use echo to pipe the prompt to Claude
            process = subprocess.Popen(
                ['claude', '--dangerously-skip-permissions'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=prompt)
            
            if process.returncode != 0:
                raise RuntimeError(f"Claude returned error: {stderr}")
                
            return stdout
            
        except Exception as e:
            # Fallback to basic rule matching if Claude fails
            return self._fallback_analysis(prompt)
            
    def _parse_claude_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's JSON response"""
        try:
            # Extract JSON from response (Claude might add some text)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")
        except Exception as e:
            # Return error analysis if parsing fails
            return {
                "compliant": None,
                "error": f"Failed to parse Claude response: {str(e)}",
                "raw_response": response[:200]
            }
            
    def _fallback_analysis(self, prompt: str) -> str:
        """Basic rule matching when Claude is unavailable"""
        # Extract message from prompt
        try:
            message_start = prompt.find("MESSAGE TO ANALYZE:")
            message_end = prompt.find("COMPLIANCE RULES:")
            message_json = prompt[message_start:message_end].replace("MESSAGE TO ANALYZE:", "").strip()
            message = json.loads(message_json)
            
            violations = []
            
            # Check communication hierarchy
            sender_role = self._extract_role(message['sender']['session'])
            recipient_role = self._extract_role(message['recipient']['session'])
            
            if sender_role == 'developer' and recipient_role in ['tester', 'testrunner', 'devops']:
                violations.append({
                    "rule_id": "comm-001",
                    "rule_description": "Developers must report to PM only",
                    "severity": "high",
                    "explanation": f"Developer directly messaged {recipient_role} instead of PM",
                    "correction": "Send message to PM for coordination"
                })
                
            # Check for manual tmux commands
            if 'tmux send-keys' in message.get('message', '').lower():
                violations.append({
                    "rule_id": "comm-005",
                    "rule_description": "Always use send-claude-message.sh script",
                    "severity": "high",
                    "explanation": "Manual tmux send-keys detected",
                    "correction": "Use ./send-claude-message.sh instead"
                })
                
            result = {
                "compliant": len(violations) == 0,
                "violations": violations,
                "warnings": [],
                "positive_notes": []
            }
            
            return json.dumps(result)
            
        except Exception as e:
            return json.dumps({
                "compliant": None,
                "error": f"Fallback analysis failed: {str(e)}"
            })
            
    def _extract_role(self, session_name: str) -> str:
        """Extract role from session name"""
        session_lower = session_name.lower()
        
        if 'pm' in session_lower or 'project-manager' in session_lower:
            return 'pm'
        elif 'dev' in session_lower and 'devops' not in session_lower:
            return 'developer'
        elif 'test' in session_lower and 'testrunner' not in session_lower:
            return 'tester'
        elif 'testrunner' in session_lower:
            return 'testrunner'
        elif 'devops' in session_lower:
            return 'devops'
        elif 'orchestrator' in session_lower or 'orc' in session_lower:
            return 'orchestrator'
        elif 'researcher' in session_lower:
            return 'researcher'
        else:
            return 'unknown'
            
def main():
    """Analyze a message log file for compliance"""
    if len(sys.argv) < 2:
        print("Usage: rule_analyzer.py <message_log.jsonl> [--rules <rules.json>]")
        sys.exit(1)
        
    script_dir = Path(__file__).parent
    log_file = Path(sys.argv[1])
    
    # Check for custom rules file
    if "--rules" in sys.argv and sys.argv.index("--rules") + 1 < len(sys.argv):
        rules_file = Path(sys.argv[sys.argv.index("--rules") + 1])
    else:
        rules_file = script_dir / "compliance_rules.json"
    
    if not rules_file.exists():
        print(f"Error: Rules file not found: {rules_file}")
        print(f"Run extract_rules.py first or specify --rules")
        sys.exit(1)
        
    if not log_file.exists():
        print(f"Error: Log file not found: {log_file}")
        sys.exit(1)
        
    analyzer = RuleAnalyzer(rules_file)
    
    # Process each message in the log
    violations_found = 0
    with open(log_file, 'r') as f:
        for line in f:
            if not line.strip():
                continue
                
            try:
                message = json.loads(line)
                if message.get('compliance_checked', False):
                    continue
                    
                print(f"Analyzing message from {message['sender']['pane']} to {message['recipient']['pane']}...")
                analysis = analyzer.analyze_message(message)
                
                if not analysis.get('compliant', True):
                    violations_found += 1
                    print(f"  ❌ Violations found: {len(analysis.get('violations', []))}")
                    for v in analysis.get('violations', []):
                        print(f"     - {v['rule_description']} ({v['severity']})")
                else:
                    print(f"  ✅ Compliant")
                    
                # Save analysis result
                output_file = log_file.parent / "compliance_analysis.jsonl"
                with open(output_file, 'a') as out:
                    json.dump(analysis, out)
                    out.write('\n')
                    
            except Exception as e:
                print(f"  ⚠️  Error analyzing message: {e}")
                
    print(f"\nAnalysis complete. Found {violations_found} messages with violations.")

if __name__ == "__main__":
    main()
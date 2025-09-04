"""
AI-powered semantic validation using Claude/Grok CLI.
Complements programmatic validation with deep semantic understanding.
"""

import subprocess
import json
import re
import logging
import os
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class AIValidator:
    """
    AI-powered semantic validation using Claude/Grok via CLI.
    This provides a simpler, more direct approach to validation.
    """
    
    def __init__(self, enable_ai: bool = True, use_grok: bool = False):
        """
        Initialize AI validator.
        
        Args:
            enable_ai: Whether to enable AI validation
            use_grok: Use Grok instead of Claude (via MCP)
        """
        self.enable_ai = enable_ai and self._check_cli_available()
        self.use_grok = use_grok
        self.cache_dir = Path.home() / '.tmux-orchestrator' / 'ai_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _check_cli_available(self) -> bool:
        """Check if Claude CLI is available."""
        try:
            result = subprocess.run(['which', 'claude'], capture_output=True, text=True)
            available = result.returncode == 0
            if not available:
                logger.warning("Claude CLI not found - AI validation disabled")
            return available
        except Exception:
            return False
    
    def validate_with_ai_simple(self, spec_content: str, 
                                implementation_files: List[str],
                                test_results: str) -> Dict[str, Any]:
        """
        Simple AI validation by piping content through Claude/Grok.
        
        This is the simpler approach suggested - just pipe everything through AI
        and let it determine if implementation matches spec.
        
        Args:
            spec_content: The specification content
            implementation_files: List of implementation file contents
            test_results: Test execution results
            
        Returns:
            Validation results from AI
        """
        if not self.enable_ai:
            return {'enabled': False, 'score': None}
        
        # Create prompt for validation
        prompt = self._create_validation_prompt(spec_content, implementation_files, test_results)
        
        # Call AI for validation
        try:
            if self.use_grok:
                result = self._call_grok_validation(prompt)
            else:
                result = self._call_claude_validation(prompt)
            
            # Parse response
            return self._parse_validation_response(result)
            
        except Exception as e:
            logger.error(f"AI validation failed: {e}")
            return {
                'enabled': True,
                'score': None,
                'error': str(e)
            }
    
    def _create_validation_prompt(self, spec_content: str, 
                                 implementation_files: List[str],
                                 test_results: str) -> str:
        """Create a focused validation prompt."""
        # Limit content size to avoid token limits
        max_spec_size = 10000
        max_impl_size = 20000
        max_test_size = 5000
        
        spec_trimmed = spec_content[:max_spec_size] if len(spec_content) > max_spec_size else spec_content
        impl_combined = '\n\n'.join(implementation_files)[:max_impl_size]
        test_trimmed = test_results[:max_test_size] if len(test_results) > max_test_size else test_results
        
        prompt = f"""You are a software validation expert. Analyze if this implementation correctly fulfills the specification.

=== SPECIFICATION ===
{spec_trimmed}

=== IMPLEMENTATION CODE ===
{impl_combined}

=== TEST RESULTS ===
{test_trimmed}

VALIDATION QUESTIONS:
1. Does the implementation fulfill all user stories mentioned in the spec?
2. Are all acceptance criteria met?
3. Are API endpoints correctly implemented as specified?
4. Do the tests adequately validate the requirements?
5. Are there any critical gaps between spec and implementation?

Respond with a JSON object containing:
{{
    "validation_score": <0-100>,
    "user_stories_fulfilled": <true/false>,
    "acceptance_criteria_met": <percentage>,
    "api_compliance": <percentage>,
    "test_coverage_adequate": <true/false>,
    "critical_gaps": ["list of gaps"],
    "verdict": "PASS|FAIL|NEEDS_WORK",
    "confidence": "HIGH|MEDIUM|LOW"
}}

JSON Response:"""
        
        return prompt
    
    def _call_claude_validation(self, prompt: str) -> str:
        """Call Claude CLI for validation."""
        cmd = [
            'claude', '-p', '--dangerously-skip-permissions',
            prompt
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                raise RuntimeError(f"Claude CLI failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude CLI timeout")
    
    def _call_grok_validation(self, prompt: str) -> str:
        """Call Grok via pipe for validation."""
        # This would use the grok MCP tool or similar approach
        # For now, fallback to Claude
        logger.info("Grok validation requested, using Claude as fallback")
        return self._call_claude_validation(prompt)
    
    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """Parse AI validation response."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    'enabled': True,
                    'score': data.get('validation_score', 0),
                    'user_stories_fulfilled': data.get('user_stories_fulfilled', False),
                    'acceptance_criteria_met': data.get('acceptance_criteria_met', 0),
                    'api_compliance': data.get('api_compliance', 0),
                    'test_coverage_adequate': data.get('test_coverage_adequate', False),
                    'critical_gaps': data.get('critical_gaps', []),
                    'verdict': data.get('verdict', 'UNKNOWN'),
                    'confidence': data.get('confidence', 'LOW')
                }
            else:
                # Try to extract key information from text
                score_match = re.search(r'(\d+)\s*(?:%|/100|out of 100)', response, re.IGNORECASE)
                verdict_match = re.search(r'(PASS|FAIL|NEEDS_WORK)', response, re.IGNORECASE)
                
                return {
                    'enabled': True,
                    'score': int(score_match.group(1)) if score_match else None,
                    'verdict': verdict_match.group(1) if verdict_match else 'UNKNOWN',
                    'raw_response': response[:500]  # Keep partial response for debugging
                }
                
        except Exception as e:
            logger.warning(f"Failed to parse AI response: {e}")
            return {
                'enabled': True,
                'score': None,
                'error': f'Parse error: {str(e)}',
                'raw_response': response[:500]
            }
    
    def validate_project_simple(self, project_path: Path, spec_path: Path) -> Dict[str, Any]:
        """
        Simple all-in-one validation of a project using AI.
        
        This is the simplified approach - gather everything and let AI decide.
        
        Args:
            project_path: Path to the project
            spec_path: Path to the specification
            
        Returns:
            AI validation results
        """
        if not self.enable_ai:
            return {'enabled': False}
        
        try:
            # Read spec
            spec_content = spec_path.read_text() if spec_path.exists() else ""
            
            # Gather implementation files
            implementation_files = []
            src_dir = project_path / 'src'
            if src_dir.exists():
                for py_file in src_dir.rglob('*.py'):
                    try:
                        if py_file.stat().st_size < 50000:  # Skip huge files
                            content = py_file.read_text()
                            implementation_files.append(f"# {py_file.name}\n{content}")
                    except Exception:
                        pass
            
            # Get test results
            test_results = self._get_test_results(project_path)
            
            # Validate with AI
            return self.validate_with_ai_simple(spec_content, implementation_files, test_results)
            
        except Exception as e:
            logger.error(f"Project validation error: {e}")
            return {
                'enabled': True,
                'score': None,
                'error': str(e)
            }
    
    def _get_test_results(self, project_path: Path) -> str:
        """Get test results from project."""
        test_results = []
        
        # Look for test report files
        for report_name in ['test_report.json', 'test_report.xml', '.test_report.json']:
            report_path = project_path / report_name
            if report_path.exists():
                try:
                    content = report_path.read_text()
                    test_results.append(f"# {report_name}\n{content[:5000]}")  # Limit size
                except Exception:
                    pass
        
        # Try running tests if no reports found
        if not test_results:
            test_dir = project_path / 'tests'
            if test_dir.exists():
                try:
                    result = subprocess.run(
                        ['python', '-m', 'pytest', '--tb=short', '-q'],
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    test_results.append(f"# pytest output\n{result.stdout[:5000]}")
                except Exception:
                    test_results.append("# No test results available")
        
        return '\n\n'.join(test_results) if test_results else "No test results found"


class HybridValidator:
    """
    Combines programmatic and AI validation for comprehensive assessment.
    """
    
    def __init__(self):
        self.ai_validator = AIValidator(
            enable_ai=os.getenv('ENABLE_AI_VALIDATION', 'false').lower() == 'true'
        )
    
    def combine_validation_scores(self, programmatic_result: Dict[str, Any],
                                 ai_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligently combine programmatic and AI validation results.
        
        Args:
            programmatic_result: Results from code/test verification
            ai_result: Results from AI validation
            
        Returns:
            Combined validation result
        """
        prog_score = programmatic_result.get('overall_score', 0)
        ai_score = ai_result.get('score')
        
        # Determine final score based on confidence
        if not ai_result.get('enabled'):
            # AI validation not enabled
            final_score = prog_score
            method = 'programmatic_only'
        elif ai_score is None:
            # AI validation failed
            final_score = prog_score
            method = 'programmatic_fallback'
        else:
            # Combine scores based on AI confidence
            confidence = ai_result.get('confidence', 'MEDIUM')
            
            if confidence == 'HIGH':
                # Trust AI more
                final_score = (prog_score * 0.3) + (ai_score * 0.7)
                method = 'ai_weighted'
            elif confidence == 'LOW':
                # Trust programmatic more
                final_score = (prog_score * 0.7) + (ai_score * 0.3)
                method = 'programmatic_weighted'
            else:  # MEDIUM
                # Equal weight
                final_score = (prog_score * 0.5) + (ai_score * 0.5)
                method = 'balanced'
        
        # Determine pass/fail with nuance
        if ai_result.get('verdict') == 'FAIL' and ai_result.get('confidence') == 'HIGH':
            # AI is confident it fails
            passed = False
        elif final_score >= 70:
            # Score-based pass
            passed = True
        else:
            passed = False
        
        return {
            'final_score': final_score,
            'programmatic_score': prog_score,
            'ai_score': ai_score,
            'passed': passed,
            'method': method,
            'confidence': ai_result.get('confidence', 'N/A'),
            'ai_verdict': ai_result.get('verdict', 'N/A'),
            'critical_gaps': ai_result.get('critical_gaps', []),
            'all_issues': programmatic_result.get('issues', []) + ai_result.get('critical_gaps', [])
        }


# Convenience function for simple usage
def validate_with_ai(spec_path: Path, project_path: Path) -> bool:
    """
    Simple function to validate a project against its spec using AI.
    
    Args:
        spec_path: Path to specification
        project_path: Path to project
        
    Returns:
        True if validation passes, False otherwise
    """
    validator = AIValidator(enable_ai=True)
    result = validator.validate_project_simple(project_path, spec_path)
    
    if result.get('score') is not None:
        return result['score'] >= 70
    else:
        # Fallback to verdict
        return result.get('verdict') == 'PASS'
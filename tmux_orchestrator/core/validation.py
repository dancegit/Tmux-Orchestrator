"""
Validation module for project completion checks.
Centralizes all validation logic to prevent premature completion marking.
Now includes spec-aware validation for ensuring implementation matches requirements.
"""

import os
import subprocess
from pathlib import Path
import logging
import json
from typing import Dict, Any, Optional

# Setup logging first
logger = logging.getLogger(__name__)

# Import spec-aware validation modules
try:
    from .spec_parser import SpecParser
    from .code_verifier import CodeVerifier
    from .test_verifier import TestVerifier
    from .ai_validator import AIValidator, HybridValidator
    spec_validation_available = True
    ai_validation_available = True
except ImportError as e:
    spec_validation_available = False
    ai_validation_available = False
    logger.warning(f"Spec-aware validation modules not available: {e}")


class ProjectValidator:
    """
    Validates project completion criteria to ensure meaningful implementation exists.
    Used before marking projects as COMPLETED in batch or interactive modes.
    Now includes spec-aware validation to verify implementation matches requirements.
    """
    
    def __init__(self):
        """Initialize validator with spec-aware components if available."""
        if spec_validation_available:
            self.spec_parser = SpecParser()
            self.code_verifier = CodeVerifier()
            self.test_verifier = TestVerifier()
            if ai_validation_available:
                self.ai_validator = AIValidator(
                    enable_ai=os.getenv('ENABLE_AI_VALIDATION', 'false').lower() == 'true'
                )
                self.hybrid_validator = HybridValidator()
            else:
                self.ai_validator = None
                self.hybrid_validator = None
        else:
            self.spec_parser = None
            self.code_verifier = None
            self.test_verifier = None
            self.ai_validator = None
            self.hybrid_validator = None
    
    @staticmethod
    def validate_completion(project_path: Path, enable_spec_validation: bool = True) -> bool:
        """
        Comprehensive validation for project completion.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            True if all criteria pass, False otherwise
        """
        if not project_path.exists():
            logger.warning(f"Project path does not exist: {project_path}")
            return False
        
        checks = [
            ProjectValidator._check_src_files(project_path),
            ProjectValidator._check_git_commits(project_path),
            ProjectValidator._check_tests(project_path),
            ProjectValidator._check_agent_logs(project_path)
        ]
        
        # Log basic validation summary
        passed = sum(checks)
        logger.info(f"Basic validation for {project_path.name}: {passed}/4 checks passed")
        
        # If basic checks fail, no need for spec validation
        if not all(checks):
            return False
        
        # Perform spec-aware validation if enabled and available
        if enable_spec_validation and spec_validation_available:
            validator = ProjectValidator()
            spec_result = validator.validate_against_spec(project_path)
            if spec_result:
                logger.info(f"Spec validation for {project_path.name}: Score {spec_result.get('overall_score', 0):.1f}%")
                return spec_result.get('passed', False)
        
        return all(checks)
    
    @staticmethod
    def _check_src_files(project_path: Path) -> bool:
        """Check that src/ directory exists and contains implementation files."""
        src_dir = project_path / 'src'
        if not src_dir.exists():
            logger.warning(f"No src/ directory found in {project_path}")
            return False
        
        # Check for meaningful Python files (not just __init__.py)
        py_files = list(src_dir.rglob('*.py'))
        meaningful_files = [f for f in py_files if '__init__' not in f.name and f.stat().st_size > 100]  # >100 bytes
        
        # Also check for other implementation files
        js_files = list(src_dir.rglob('*.js'))
        ts_files = list(src_dir.rglob('*.ts'))
        other_files = meaningful_files + js_files + ts_files
        
        if len(other_files) < 1:  # Require at least 1 substantial file
            logger.warning(f"Insufficient implementation files in src/: {len(other_files)}")
            return False
        
        logger.debug(f"✓ Found {len(other_files)} implementation files in src/")
        return True
    
    @staticmethod
    def _check_git_commits(project_path: Path) -> bool:
        """Check for at least 3+ meaningful git commits (beyond initial and merge)."""
        try:
            # Get commit count
            result = subprocess.run(
                ['git', 'rev-list', '--count', 'HEAD'],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning(f"Git repo check failed: {result.stderr}")
                return False
            
            commit_count = int(result.stdout.strip())
            
            # Get commit messages to filter out auto-generated ones
            result = subprocess.run(
                ['git', 'log', '--oneline', '-20'],  # Get more commits for better analysis
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                messages = result.stdout.strip().split('\n') if result.stdout.strip() else []
                meaningful_commits = [
                    msg for msg in messages 
                    if not any(auto in msg.lower() for auto in ['initial commit', 'merge', 'prepare for merge', 'auto-'])
                ]
                
                if len(meaningful_commits) < 3:  # Require at least 3 non-auto commits
                    logger.warning(f"Insufficient meaningful commits: {len(meaningful_commits)} (need 3+)")
                    return False
                    
                logger.debug(f"✓ Found {commit_count} total commits, {len(meaningful_commits)} meaningful")
                return True
            
            return False
            
        except (subprocess.TimeoutExpired, ValueError) as e:
            logger.warning(f"Git check failed: {e}")
            return False
    
    @staticmethod
    def _check_tests(project_path: Path) -> bool:
        """Check that tests directory has actual test files."""
        tests_dir = project_path / 'tests'
        if not tests_dir.exists():
            logger.warning(f"No tests/ directory found in {project_path}")
            return False
        
        # Look for test files (e.g., test_*.py, *_test.py)
        test_files = list(tests_dir.rglob('test_*.py')) + list(tests_dir.rglob('*_test.py'))
        
        if len(test_files) < 1:  # Require at least 1 test file
            logger.warning(f"No test files found in tests/: {len(test_files)}")
            return False
        
        # Check that test files have content (not empty)
        empty_tests = [f for f in test_files if f.stat().st_size < 50]  # <50 bytes likely empty
        if len(empty_tests) == len(test_files):  # All tests are empty
            logger.warning(f"All {len(empty_tests)} test files are empty or trivial")
            return False
        
        logger.debug(f"✓ Found {len(test_files)} valid test files")
        return True
    
    @staticmethod
    def _check_agent_logs(project_path: Path) -> bool:
        """Check that agent logs show activity (e.g., from worktrees or sessions)."""
        # Look for common log locations
        log_paths = [
            project_path / 'logs',
            project_path / '.claude' / 'logs',
            project_path.parent / f"{project_path.name}-worktrees",  # Worktree logs
            project_path.parent / f"{project_path.name}-impl"  # Implementation logs
        ]
        
        total_log_size = 0
        found_activity = False
        
        for log_path in log_paths:
            if log_path.exists():
                log_files = list(log_path.rglob('*.log'))
                for log_file in log_files:
                    try:
                        size = log_file.stat().st_size
                        total_log_size += size
                        
                        # Check for activity indicators in log content
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(5000)  # First 5KB
                            activity_indicators = [
                                'agent', 'task', 'implementation', 'completed',
                                'writing', 'created', 'function', 'class', 'test'
                            ]
                            if any(indicator in content.lower() for indicator in activity_indicators):
                                found_activity = True
                                break
                    except Exception as e:
                        logger.debug(f"Could not read log {log_file}: {e}")
                        
                if found_activity:
                    break
        
        # More lenient for logs - they might not always exist
        if total_log_size < 500 and not found_activity:  # Require >500 bytes logs with activity
            logger.warning(f"Minimal agent activity in logs: {total_log_size} bytes, activity={found_activity}")
            return False
        
        logger.debug(f"✓ Found agent logs with activity ({total_log_size} bytes)")
        return True
    
    def validate_against_spec(self, project_path: Path) -> Optional[Dict[str, Any]]:
        """
        Validate project implementation against its specification.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            Dict with validation results including overall_score and passed status
        """
        if not spec_validation_available:
            return None
        
        # Find spec file
        spec_path = project_path / 'spec.md'
        if not spec_path.exists():
            # Try parent directory
            spec_path = project_path.parent / f"{project_path.name}.md"
            if not spec_path.exists():
                logger.warning(f"No spec file found for {project_path}")
                return None
        
        try:
            # Parse spec
            logger.info(f"Parsing spec for {project_path.name}")
            parsed_spec = self.spec_parser.parse_spec(spec_path)
            if not parsed_spec:
                logger.warning(f"Failed to parse spec for {project_path}")
                return None
            
            # Verify code against spec
            logger.info(f"Verifying code implementation for {project_path.name}")
            code_results = self.code_verifier.verify_requirements(project_path, parsed_spec)
            
            # Verify tests
            logger.info(f"Verifying tests for {project_path.name}")
            test_results = self.test_verifier.verify_tests(project_path, parsed_spec)
            
            # Combine scores
            code_score = code_results.get('overall_score', 0)
            test_score = test_results.get('score', 0)
            
            # Weighted average (60% code, 40% tests)
            programmatic_score = code_score * 0.6 + test_score * 0.4
            
            # Collect all issues
            all_issues = []
            all_issues.extend(code_results.get('issues', []))
            all_issues.extend(test_results.get('issues', []))
            
            # AI validation if enabled
            ai_result = {}
            final_score = programmatic_score
            
            if self.ai_validator and self.ai_validator.enable_ai:
                logger.info(f"Running AI validation for {project_path.name}")
                ai_result = self.ai_validator.validate_project_simple(project_path, spec_path)
                
                # Combine scores using hybrid validator
                if self.hybrid_validator and ai_result.get('enabled'):
                    hybrid_result = self.hybrid_validator.combine_validation_scores(
                        {'overall_score': programmatic_score, 'issues': all_issues},
                        ai_result
                    )
                    final_score = hybrid_result.get('final_score', programmatic_score)
                    all_issues.extend(hybrid_result.get('critical_gaps', []))
                    
                    logger.info(f"  - AI score: {ai_result.get('score', 'N/A')}")
                    logger.info(f"  - Combined score: {final_score:.1f}%")
                    logger.info(f"  - AI verdict: {ai_result.get('verdict', 'N/A')}")
            
            result = {
                'overall_score': final_score,
                'programmatic_score': programmatic_score,
                'code_score': code_score,
                'test_score': test_score,
                'ai_score': ai_result.get('score'),
                'ai_verdict': ai_result.get('verdict', 'N/A'),
                'ai_confidence': ai_result.get('confidence', 'N/A'),
                'passed': final_score >= 70,  # 70% threshold
                'issues': all_issues,
                'code_details': code_results.get('details', {}),
                'test_details': test_results.get('details', {}),
                'ai_details': ai_result,
                'spec_version': parsed_spec.get('version', 'unknown')
            }
            
            # Log detailed results
            logger.info(f"Spec validation results for {project_path.name}:")
            logger.info(f"  - Code score: {code_score:.1f}%")
            logger.info(f"  - Test score: {test_score:.1f}%")
            logger.info(f"  - Programmatic score: {programmatic_score:.1f}%")
            if ai_result.get('enabled'):
                logger.info(f"  - AI score: {ai_result.get('score', 'N/A')}")
            logger.info(f"  - Final score: {final_score:.1f}%")
            if all_issues:
                logger.warning(f"  - Issues found: {len(all_issues)}")
                for issue in all_issues[:3]:  # Log first 3 issues
                    logger.warning(f"    • {issue}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error during spec validation for {project_path}: {e}")
            return None
    
    def get_validation_report(self, project_path: Path) -> Dict[str, Any]:
        """
        Generate a detailed validation report for a project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            Comprehensive validation report
        """
        report = {
            'project': str(project_path),
            'basic_checks': {},
            'spec_validation': None
        }
        
        # Run basic checks
        report['basic_checks']['src_files'] = self._check_src_files(project_path)
        report['basic_checks']['git_commits'] = self._check_git_commits(project_path)
        report['basic_checks']['tests'] = self._check_tests(project_path)
        report['basic_checks']['agent_logs'] = self._check_agent_logs(project_path)
        
        # Run spec validation
        if spec_validation_available:
            report['spec_validation'] = self.validate_against_spec(project_path)
        
        # Overall status
        basic_passed = all(report['basic_checks'].values())
        spec_passed = report['spec_validation'].get('passed', True) if report['spec_validation'] else True
        report['passed'] = basic_passed and spec_passed
        
        return report
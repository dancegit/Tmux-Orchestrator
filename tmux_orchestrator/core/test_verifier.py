"""
Test verification module for spec-aware validation.
Verifies tests pass and map to user stories/requirements.
"""

import json
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class TestVerifier:
    """
    Verifies tests pass and map to user stories from specs.
    """
    
    def __init__(self):
        self.test_frameworks = {
            'pytest': self._run_pytest,
            'unittest': self._run_unittest,
            'jest': self._run_jest,
            'mocha': self._run_mocha
        }
    
    def verify_tests(self, project_path: Path, parsed_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run tests and verify they cover spec requirements.
        
        Args:
            project_path: Project directory
            parsed_spec: Parsed spec from SpecParser
            
        Returns:
            Dict with test verification results
        """
        # Detect test framework
        framework = self._detect_test_framework(project_path)
        if not framework:
            return {
                'score': 0,
                'framework': 'none',
                'issues': ['No test framework detected'],
                'passed': False
            }
        
        # Run tests
        logger.info(f"Running {framework} tests for {project_path}")
        test_results = self.test_frameworks[framework](project_path)
        
        if not test_results['success']:
            return {
                'score': 0,
                'framework': framework,
                'issues': test_results.get('errors', ['Test execution failed']),
                'passed': False
            }
        
        # Map tests to user stories
        user_stories = parsed_spec.get('user_stories', [])
        test_scenarios = parsed_spec.get('test_scenarios', [])
        acceptance_criteria = parsed_spec.get('acceptance_criteria', [])
        
        mapping_results = self._map_tests_to_requirements(
            test_results['tests'],
            user_stories,
            test_scenarios,
            acceptance_criteria
        )
        
        # Calculate scores
        test_pass_rate = test_results.get('pass_rate', 0)
        story_coverage = mapping_results.get('story_coverage', 0)
        scenario_coverage = mapping_results.get('scenario_coverage', 0)
        
        # Weighted score calculation
        overall_score = (
            test_pass_rate * 0.4 +  # 40% weight for passing tests
            story_coverage * 0.35 +  # 35% weight for story coverage
            scenario_coverage * 0.25  # 25% weight for scenario coverage
        )
        
        issues = []
        if test_pass_rate < 100:
            issues.append(f"Test pass rate: {test_pass_rate:.1f}%")
        if story_coverage < 80:
            issues.append(f"Story coverage: {story_coverage:.1f}%")
        if scenario_coverage < 70:
            issues.append(f"Scenario coverage: {scenario_coverage:.1f}%")
        
        # Add specific missing coverage
        if mapping_results['unmapped_stories']:
            issues.append(f"Uncovered stories: {len(mapping_results['unmapped_stories'])}")
            for story in mapping_results['unmapped_stories'][:2]:
                issues.append(f"  - {story.get('full_text', story.get('action', 'Unknown'))[:80]}...")
        
        return {
            'score': overall_score,
            'framework': framework,
            'test_results': test_results,
            'mapping': mapping_results,
            'issues': issues,
            'passed': overall_score >= 70,  # 70% threshold for tests
            'details': {
                'total_tests': test_results.get('total', 0),
                'passed_tests': test_results.get('passed', 0),
                'failed_tests': test_results.get('failed', 0),
                'test_pass_rate': test_pass_rate,
                'story_coverage': story_coverage,
                'scenario_coverage': scenario_coverage
            }
        }
    
    def _detect_test_framework(self, project_path: Path) -> Optional[str]:
        """Detect which test framework is being used."""
        # Check for Python test frameworks
        if (project_path / 'pytest.ini').exists() or (project_path / 'pyproject.toml').exists():
            # Check if pytest is installed
            if self._check_package_installed(project_path, 'pytest'):
                return 'pytest'
        
        # Check for test directories with Python files
        test_dirs = ['tests', 'test', 'test_*']
        for pattern in test_dirs:
            for test_dir in project_path.glob(pattern):
                if test_dir.is_dir() and list(test_dir.glob('*.py')):
                    # Default to pytest for Python projects
                    return 'pytest'
        
        # Check for JavaScript test frameworks
        package_json = project_path / 'package.json'
        if package_json.exists():
            try:
                with open(package_json) as f:
                    package = json.load(f)
                    deps = {**package.get('dependencies', {}), **package.get('devDependencies', {})}
                    
                    if 'jest' in deps:
                        return 'jest'
                    elif 'mocha' in deps:
                        return 'mocha'
            except Exception:
                pass
        
        return None
    
    def _check_package_installed(self, project_path: Path, package: str) -> bool:
        """Check if a Python package is installed."""
        requirements = project_path / 'requirements.txt'
        if requirements.exists():
            try:
                content = requirements.read_text().lower()
                if package.lower() in content:
                    return True
            except Exception:
                pass
        
        pyproject = project_path / 'pyproject.toml'
        if pyproject.exists():
            try:
                content = pyproject.read_text().lower()
                if package.lower() in content:
                    return True
            except Exception:
                pass
        
        return False
    
    def _run_pytest(self, project_path: Path) -> Dict[str, Any]:
        """Run pytest and parse results."""
        try:
            # Try different output formats
            json_report = project_path / '.test_report.json'
            xml_report = project_path / '.test_report.xml'
            
            # First try with JSON report
            cmd = [
                'python', '-m', 'pytest',
                '--tb=short',
                '--json-report',
                f'--json-report-file={json_report}',
                '-v'
            ]
            
            # Find test directory
            test_dir = None
            for name in ['tests', 'test']:
                if (project_path / name).exists():
                    test_dir = project_path / name
                    break
            
            if test_dir:
                cmd.append(str(test_dir))
            
            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # Try to parse JSON report first
            if json_report.exists():
                try:
                    with open(json_report) as f:
                        report = json.load(f)
                    
                    tests = report.get('tests', [])
                    passed = len([t for t in tests if t.get('outcome') == 'passed'])
                    failed = len([t for t in tests if t.get('outcome') == 'failed'])
                    total = len(tests)
                    
                    return {
                        'success': True,
                        'tests': tests,
                        'passed': passed,
                        'failed': failed,
                        'total': total,
                        'pass_rate': (passed / total * 100) if total else 0,
                        'raw_output': result.stdout
                    }
                except Exception as e:
                    logger.debug(f"Failed to parse JSON report: {e}")
            
            # Fallback to JUnit XML format
            cmd = [
                'python', '-m', 'pytest',
                '--tb=short',
                f'--junit-xml={xml_report}',
                '-v'
            ]
            
            if test_dir:
                cmd.append(str(test_dir))
            
            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if xml_report.exists():
                return self._parse_junit_xml(xml_report, result.stdout)
            
            # Fallback to parsing stdout
            return self._parse_pytest_stdout(result.stdout, result.returncode)
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'errors': ['Test execution timeout (120s)']
            }
        except Exception as e:
            return {
                'success': False,
                'errors': [f'Test execution error: {str(e)}']
            }
    
    def _parse_junit_xml(self, xml_path: Path, stdout: str) -> Dict[str, Any]:
        """Parse JUnit XML test report."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            tests = []
            for testcase in root.findall('.//testcase'):
                name = testcase.get('name', '')
                classname = testcase.get('classname', '')
                
                # Check for failure or error
                failure = testcase.find('failure')
                error = testcase.find('error')
                
                outcome = 'passed'
                if failure is not None or error is not None:
                    outcome = 'failed'
                
                tests.append({
                    'name': name,
                    'classname': classname,
                    'outcome': outcome
                })
            
            # Get summary from root attributes
            total = int(root.get('tests', 0))
            failures = int(root.get('failures', 0))
            errors = int(root.get('errors', 0))
            passed = total - failures - errors
            
            return {
                'success': True,
                'tests': tests,
                'passed': passed,
                'failed': failures + errors,
                'total': total,
                'pass_rate': (passed / total * 100) if total else 0,
                'raw_output': stdout
            }
        except Exception as e:
            logger.debug(f"Failed to parse JUnit XML: {e}")
            return self._parse_pytest_stdout(stdout, 0)
    
    def _parse_pytest_stdout(self, stdout: str, returncode: int) -> Dict[str, Any]:
        """Parse pytest stdout as fallback."""
        tests = []
        
        # Parse individual test results
        test_pattern = r'(test_\S+)\s+(\S+)'
        matches = re.findall(test_pattern, stdout)
        
        for test_name, status in matches:
            outcome = 'passed' if status in ['PASSED', 'OK', '.'] else 'failed'
            tests.append({
                'name': test_name,
                'outcome': outcome
            })
        
        # Parse summary line
        summary_pattern = r'(\d+) passed(?:,\s*(\d+) failed)?'
        summary_match = re.search(summary_pattern, stdout)
        
        if summary_match:
            passed = int(summary_match.group(1))
            failed = int(summary_match.group(2)) if summary_match.group(2) else 0
            total = passed + failed
        else:
            # Fallback counting
            passed = len([t for t in tests if t['outcome'] == 'passed'])
            failed = len([t for t in tests if t['outcome'] == 'failed'])
            total = len(tests)
        
        return {
            'success': returncode == 0 or passed > 0,
            'tests': tests,
            'passed': passed,
            'failed': failed,
            'total': total,
            'pass_rate': (passed / total * 100) if total else 0,
            'raw_output': stdout
        }
    
    def _run_unittest(self, project_path: Path) -> Dict[str, Any]:
        """Run unittest and parse results."""
        # Similar to pytest but using unittest discover
        try:
            cmd = ['python', '-m', 'unittest', 'discover', '-v']
            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return self._parse_unittest_stdout(result.stdout, result.returncode)
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'errors': ['Test execution timeout']
            }
        except Exception as e:
            return {
                'success': False,
                'errors': [str(e)]
            }
    
    def _parse_unittest_stdout(self, stdout: str, returncode: int) -> Dict[str, Any]:
        """Parse unittest stdout."""
        tests = []
        
        # Parse test results
        test_pattern = r'(test_\S+)\s+\(([^)]+)\)\s+\.\.\.\s+(\S+)'
        matches = re.findall(test_pattern, stdout)
        
        for test_name, module, status in matches:
            outcome = 'passed' if status in ['ok', 'OK'] else 'failed'
            tests.append({
                'name': test_name,
                'classname': module,
                'outcome': outcome
            })
        
        # Parse summary
        summary_pattern = r'Ran (\d+) tests?.*?(?:FAILED \(failures=(\d+)\))?'
        summary_match = re.search(summary_pattern, stdout, re.DOTALL)
        
        if summary_match:
            total = int(summary_match.group(1))
            failed = int(summary_match.group(2)) if summary_match.group(2) else 0
            passed = total - failed
        else:
            passed = len([t for t in tests if t['outcome'] == 'passed'])
            failed = len([t for t in tests if t['outcome'] == 'failed'])
            total = len(tests)
        
        return {
            'success': returncode == 0,
            'tests': tests,
            'passed': passed,
            'failed': failed,
            'total': total,
            'pass_rate': (passed / total * 100) if total else 0,
            'raw_output': stdout
        }
    
    def _run_jest(self, project_path: Path) -> Dict[str, Any]:
        """Run Jest tests."""
        try:
            cmd = ['npm', 'test', '--', '--json']
            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # Parse Jest JSON output
            try:
                # Jest outputs JSON to stdout
                json_str = result.stdout
                # Find the JSON part (Jest may output other text)
                json_start = json_str.find('{')
                if json_start != -1:
                    json_data = json.loads(json_str[json_start:])
                    
                    tests = []
                    passed = 0
                    failed = 0
                    
                    for test_result in json_data.get('testResults', []):
                        for assertion in test_result.get('assertionResults', []):
                            tests.append({
                                'name': assertion.get('title', ''),
                                'outcome': 'passed' if assertion.get('status') == 'passed' else 'failed'
                            })
                            if assertion.get('status') == 'passed':
                                passed += 1
                            else:
                                failed += 1
                    
                    total = passed + failed
                    
                    return {
                        'success': json_data.get('success', False),
                        'tests': tests,
                        'passed': passed,
                        'failed': failed,
                        'total': total,
                        'pass_rate': (passed / total * 100) if total else 0,
                        'raw_output': result.stdout
                    }
            except Exception:
                pass
            
            # Fallback to basic parsing
            return {
                'success': result.returncode == 0,
                'tests': [],
                'passed': 0,
                'failed': 0,
                'total': 0,
                'pass_rate': 0,
                'raw_output': result.stdout
            }
            
        except Exception as e:
            return {
                'success': False,
                'errors': [str(e)]
            }
    
    def _run_mocha(self, project_path: Path) -> Dict[str, Any]:
        """Run Mocha tests."""
        try:
            cmd = ['npm', 'test']
            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # Parse Mocha output
            tests = []
            test_pattern = r'✓\s+(.+)|✗\s+(.+)'
            matches = re.findall(test_pattern, result.stdout)
            
            for passed_test, failed_test in matches:
                if passed_test:
                    tests.append({
                        'name': passed_test.strip(),
                        'outcome': 'passed'
                    })
                elif failed_test:
                    tests.append({
                        'name': failed_test.strip(),
                        'outcome': 'failed'
                    })
            
            passed = len([t for t in tests if t['outcome'] == 'passed'])
            failed = len([t for t in tests if t['outcome'] == 'failed'])
            total = len(tests)
            
            return {
                'success': result.returncode == 0,
                'tests': tests,
                'passed': passed,
                'failed': failed,
                'total': total,
                'pass_rate': (passed / total * 100) if total else 0,
                'raw_output': result.stdout
            }
            
        except Exception as e:
            return {
                'success': False,
                'errors': [str(e)]
            }
    
    def _map_tests_to_requirements(self, tests: List[Dict], user_stories: List[Dict],
                                  test_scenarios: List[Dict], acceptance_criteria: List[str]) -> Dict[str, Any]:
        """Map test names to requirements."""
        mapped_stories = set()
        mapped_scenarios = set()
        unmapped_stories = []
        unmapped_scenarios = []
        
        # Extract test names
        test_names = [t.get('name', '').lower() for t in tests]
        test_names_str = ' '.join(test_names)
        
        # Map user stories
        for i, story in enumerate(user_stories):
            story_text = story.get('full_text', story.get('action', '')).lower()
            keywords = self._extract_keywords_from_text(story_text)
            
            # Check if any keywords appear in test names
            matched = False
            for keyword in keywords:
                if keyword in test_names_str:
                    mapped_stories.add(i)
                    matched = True
                    break
            
            if not matched:
                unmapped_stories.append(story)
        
        # Map test scenarios
        for i, scenario in enumerate(test_scenarios):
            scenario_text = scenario.get('scenario', '').lower()
            keywords = self._extract_keywords_from_text(scenario_text)
            
            matched = False
            for keyword in keywords:
                if keyword in test_names_str:
                    mapped_scenarios.add(i)
                    matched = True
                    break
            
            if not matched:
                unmapped_scenarios.append(scenario)
        
        story_coverage = (len(mapped_stories) / len(user_stories) * 100) if user_stories else 100
        scenario_coverage = (len(mapped_scenarios) / len(test_scenarios) * 100) if test_scenarios else 100
        
        return {
            'mapped_stories': len(mapped_stories),
            'total_stories': len(user_stories),
            'story_coverage': story_coverage,
            'unmapped_stories': unmapped_stories,
            'mapped_scenarios': len(mapped_scenarios),
            'total_scenarios': len(test_scenarios),
            'scenario_coverage': scenario_coverage,
            'unmapped_scenarios': unmapped_scenarios
        }
    
    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        stop_words = {
            'a', 'an', 'the', 'to', 'from', 'with', 'can', 'be', 'able',
            'should', 'must', 'will', 'would', 'could', 'may', 'might',
            'and', 'or', 'but', 'if', 'then', 'when', 'where', 'how',
            'as', 'user', 'i', 'want', 'need', 'that', 'so'
        }
        
        words = re.findall(r'\b[a-z]+\b', text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        
        # Prioritize domain-specific terms
        priority_terms = []
        for word in keywords:
            if any(term in word for term in ['data', 'api', 'user', 'create', 'update', 
                                             'delete', 'get', 'post', 'auth', 'test']):
                priority_terms.append(word)
        
        return priority_terms[:5] if priority_terms else keywords[:5]
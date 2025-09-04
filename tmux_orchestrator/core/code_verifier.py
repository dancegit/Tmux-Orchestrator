"""
Code verification module for spec-aware validation.
Maps spec requirements to actual code implementation.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class CodeVerifier:
    """
    Verifies that code implements extracted requirements from specs.
    """
    
    def __init__(self):
        self.framework_patterns = {
            'fastapi': ['from fastapi', 'import FastAPI', '@app.', '@router.'],
            'flask': ['from flask', 'import Flask', '@app.route'],
            'django': ['from django', 'import django', 'django.'],
            'express': ['express()', 'app.get(', 'app.post(', 'router.get('],
        }
    
    def verify_requirements(self, project_path: Path, parsed_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if code matches spec requirements.
        
        Args:
            project_path: Project directory
            parsed_spec: Parsed spec from SpecParser
            
        Returns:
            Dict with verification results and score
        """
        src_dir = project_path / 'src'
        if not src_dir.exists():
            # Try alternative source directories
            for alt in ['app', 'lib', project_path.name]:
                alt_dir = project_path / alt
                if alt_dir.exists() and any(alt_dir.glob('*.py')):
                    src_dir = alt_dir
                    break
            else:
                return {
                    'overall_score': 0,
                    'issues': ['No source directory found (checked src/, app/, lib/)'],
                    'passed': False
                }
        
        results = {
            'api_endpoints': self._verify_api_endpoints(src_dir, parsed_spec.get('api_endpoints', [])),
            'user_stories': self._verify_user_stories(src_dir, parsed_spec.get('user_stories', [])),
            'acceptance_criteria': self._verify_acceptance_criteria(src_dir, parsed_spec.get('acceptance_criteria', [])),
            'implementation_requirements': self._verify_implementation_requirements(
                project_path, parsed_spec.get('implementation_requirements', [])
            )
        }
        
        # Calculate weighted score
        weights = {
            'api_endpoints': 0.35,  # APIs are critical
            'user_stories': 0.25,
            'acceptance_criteria': 0.25,
            'implementation_requirements': 0.15
        }
        
        overall_score = 0
        for key, weight in weights.items():
            if key in results and isinstance(results[key], dict):
                overall_score += results[key].get('score', 0) * weight
        
        # Collect all issues
        all_issues = []
        for result in results.values():
            if isinstance(result, dict) and 'issues' in result:
                all_issues.extend(result['issues'])
        
        return {
            'overall_score': overall_score,
            'details': results,
            'issues': all_issues,
            'passed': overall_score >= 70  # Slightly lower threshold for initial implementation
        }
    
    def _verify_api_endpoints(self, src_dir: Path, endpoints: List[Dict[str, str]]) -> Dict[str, Any]:
        """Verify API endpoints exist in code."""
        if not endpoints:
            return {'score': 100, 'issues': [], 'found': [], 'missing': []}
        
        found_endpoints = self._scan_for_endpoints(src_dir)
        
        # Normalize endpoints for comparison
        required_endpoints = set()
        for endpoint in endpoints:
            method = endpoint['method'].upper()
            path = endpoint['path']
            # Normalize path (remove trailing slash, lowercase)
            path = path.rstrip('/').lower()
            required_endpoints.add((method, path))
        
        # Check each required endpoint
        verified = []
        missing = []
        
        for endpoint in endpoints:
            method = endpoint['method'].upper()
            path = endpoint['path'].rstrip('/').lower()
            
            # Check for exact match or pattern match
            matched = False
            for found_method, found_path in found_endpoints:
                if method == found_method:
                    # Exact match
                    if path == found_path:
                        matched = True
                        break
                    # Pattern match (e.g., /users/{id} matches /users/:id)
                    if self._paths_match(path, found_path):
                        matched = True
                        break
            
            if matched:
                verified.append(f"{method} {endpoint['path']}")
            else:
                missing.append(f"{method} {endpoint['path']}")
        
        score = (len(verified) / len(endpoints)) * 100 if endpoints else 100
        
        issues = []
        if missing:
            issues.append(f"Missing {len(missing)} endpoints: {', '.join(missing[:3])}" + 
                         ("..." if len(missing) > 3 else ""))
        
        return {
            'score': score,
            'issues': issues,
            'found': verified,
            'missing': missing,
            'total_required': len(endpoints),
            'total_found': len(verified)
        }
    
    def _scan_for_endpoints(self, src_dir: Path) -> Set[Tuple[str, str]]:
        """Scan directory for API endpoint definitions."""
        endpoints = set()
        
        # Scan Python files
        for py_file in src_dir.rglob('*.py'):
            try:
                content = py_file.read_text()
                
                # FastAPI/Flask style decorators
                decorator_patterns = [
                    r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                    r'@(?:app|router)\.route\s*\(\s*["\']([^"\']+)["\'].*methods=\[["\']([A-Z]+)["\']',
                ]
                
                for pattern in decorator_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if len(match) == 2:
                            method, path = match
                            endpoints.add((method.upper(), path.lower()))
                        else:
                            path, method = match
                            endpoints.add((method.upper(), path.lower()))
                
                # Express.js style (in comments or strings for reference)
                express_patterns = [
                    r'app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                    r'router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                ]
                
                for pattern in express_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for method, path in matches:
                        endpoints.add((method.upper(), path.lower()))
                
            except Exception as e:
                logger.debug(f"Error scanning {py_file}: {e}")
        
        # Scan JavaScript/TypeScript files if present
        for js_file in src_dir.rglob('*.js'):
            try:
                content = js_file.read_text()
                matches = re.findall(
                    r'(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                    content, re.IGNORECASE
                )
                for method, path in matches:
                    endpoints.add((method.upper(), path.lower()))
            except Exception:
                pass
        
        return endpoints
    
    def _paths_match(self, required: str, found: str) -> bool:
        """Check if two API paths match (considering parameters)."""
        # Convert path parameters to regex
        # /users/{id} -> /users/[^/]+
        # /users/:id -> /users/[^/]+
        
        # Normalize required path
        pattern = required
        pattern = re.sub(r'\{[^}]+\}', r'[^/]+', pattern)  # {param} -> [^/]+
        pattern = re.sub(r':[^/]+', r'[^/]+', pattern)     # :param -> [^/]+
        pattern = f"^{pattern}$"
        
        # Normalize found path
        found_normalized = found
        found_normalized = re.sub(r'\{[^}]+\}', r'[^/]+', found_normalized)
        found_normalized = re.sub(r':[^/]+', r'[^/]+', found_normalized)
        
        return bool(re.match(pattern, found_normalized))
    
    def _verify_user_stories(self, src_dir: Path, stories: List[Dict[str, str]]) -> Dict[str, Any]:
        """Verify user stories via code patterns and keywords."""
        if not stories:
            return {'score': 100, 'issues': [], 'verified': [], 'unverified': []}
        
        verified = []
        unverified = []
        
        # Build keyword map from stories
        story_keywords = {}
        for i, story in enumerate(stories):
            # Extract action keywords
            action = story.get('action', '')
            keywords = self._extract_action_keywords(action)
            story_keywords[i] = {
                'keywords': keywords,
                'story': story.get('full_text', action)
            }
        
        # Scan code for story implementations
        code_content = self._get_all_code_content(src_dir)
        
        for idx, info in story_keywords.items():
            keywords = info['keywords']
            story_text = info['story']
            
            # Check if keywords appear in code
            found_keywords = sum(1 for kw in keywords if kw.lower() in code_content.lower())
            
            # Consider story implemented if >50% keywords found
            if keywords and found_keywords >= len(keywords) * 0.5:
                verified.append(story_text)
            else:
                unverified.append(story_text)
        
        score = (len(verified) / len(stories)) * 100 if stories else 100
        
        issues = []
        if unverified:
            issues.append(f"Unverified stories: {len(unverified)} of {len(stories)}")
            for story in unverified[:2]:  # Show first 2
                issues.append(f"  - {story[:100]}...")
        
        return {
            'score': score,
            'issues': issues,
            'verified': verified,
            'unverified': unverified,
            'total': len(stories)
        }
    
    def _verify_acceptance_criteria(self, src_dir: Path, criteria: List[str]) -> Dict[str, Any]:
        """Verify acceptance criteria are met."""
        if not criteria:
            return {'score': 100, 'issues': [], 'met': [], 'unmet': []}
        
        met_criteria = []
        unmet_criteria = []
        
        code_content = self._get_all_code_content(src_dir)
        test_content = self._get_test_content(src_dir.parent)
        
        for criterion in criteria:
            # Extract key requirements from criterion
            keywords = self._extract_requirement_keywords(criterion)
            
            # Check in both code and tests
            found_in_code = sum(1 for kw in keywords if kw.lower() in code_content.lower())
            found_in_tests = sum(1 for kw in keywords if kw.lower() in test_content.lower())
            
            # Criterion is met if keywords found in either code or tests
            total_found = found_in_code + found_in_tests
            if keywords and total_found >= len(keywords) * 0.4:  # 40% threshold
                met_criteria.append(criterion)
            else:
                unmet_criteria.append(criterion)
        
        score = (len(met_criteria) / len(criteria)) * 100 if criteria else 100
        
        issues = []
        if unmet_criteria:
            issues.append(f"Unmet criteria: {len(unmet_criteria)} of {len(criteria)}")
        
        return {
            'score': score,
            'issues': issues,
            'met': met_criteria,
            'unmet': unmet_criteria,
            'total': len(criteria)
        }
    
    def _verify_implementation_requirements(self, project_path: Path, requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Verify specific implementation requirements."""
        if not requirements:
            return {'score': 100, 'issues': [], 'verified': [], 'missing': []}
        
        verified = []
        missing = []
        
        # Check various requirement types
        for req in requirements:
            req_type = req.get('type', '')
            req_text = req.get('requirement', '')
            
            if req_type == 'technology' or req_type == 'framework':
                if self._check_technology_requirement(project_path, req_text):
                    verified.append(f"{req_type}: {req_text}")
                else:
                    missing.append(f"{req_type}: {req_text}")
            
            elif req_type == 'database':
                if self._check_database_requirement(project_path, req_text):
                    verified.append(f"{req_type}: {req_text}")
                else:
                    missing.append(f"{req_type}: {req_text}")
            
            elif req_type == 'performance':
                # Performance requirements need test verification
                verified.append(f"{req_type}: {req_text} (needs test verification)")
            
            elif req_type == 'security':
                if self._check_security_requirement(project_path, req_text):
                    verified.append(f"{req_type}: {req_text}")
                else:
                    missing.append(f"{req_type}: {req_text}")
        
        score = (len(verified) / len(requirements)) * 100 if requirements else 100
        
        issues = []
        if missing:
            issues.append(f"Missing requirements: {', '.join(missing[:3])}")
        
        return {
            'score': score,
            'issues': issues,
            'verified': verified,
            'missing': missing,
            'total': len(requirements)
        }
    
    def _extract_action_keywords(self, action: str) -> List[str]:
        """Extract meaningful keywords from user story actions."""
        # Remove common words
        stop_words = {
            'a', 'an', 'the', 'to', 'from', 'with', 'can', 'be', 'able',
            'should', 'must', 'will', 'would', 'could', 'may', 'might',
            'and', 'or', 'but', 'if', 'then', 'when', 'where', 'how'
        }
        
        # Extract words
        words = re.findall(r'\b[a-z]+\b', action.lower())
        
        # Filter stop words and short words
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Prioritize verbs and nouns (simple heuristic)
        priority_words = []
        for word in keywords:
            # Common action verbs
            if word in ['create', 'read', 'update', 'delete', 'get', 'post', 'put', 
                       'fetch', 'save', 'load', 'upload', 'download', 'view', 'edit',
                       'submit', 'validate', 'authenticate', 'authorize']:
                priority_words.append(word)
            # Common nouns
            elif word in ['user', 'data', 'file', 'report', 'dashboard', 'api',
                         'database', 'record', 'item', 'list', 'form', 'page']:
                priority_words.append(word)
        
        return priority_words if priority_words else keywords[:5]
    
    def _extract_requirement_keywords(self, requirement: str) -> List[str]:
        """Extract keywords from acceptance criteria."""
        # Similar to action keywords but includes technical terms
        technical_terms = {
            'api', 'rest', 'graphql', 'websocket', 'http', 'https',
            'database', 'sql', 'nosql', 'cache', 'redis', 'postgres',
            'authentication', 'authorization', 'jwt', 'oauth', 'token',
            'validation', 'sanitization', 'encryption', 'hash',
            'async', 'sync', 'queue', 'worker', 'cron', 'scheduler'
        }
        
        words = re.findall(r'\b[a-z]+\b', requirement.lower())
        keywords = []
        
        for word in words:
            if word in technical_terms or len(word) > 4:
                keywords.append(word)
        
        return keywords[:8]  # Limit to 8 most relevant
    
    def _get_all_code_content(self, src_dir: Path) -> str:
        """Get concatenated content of all code files."""
        content = []
        
        for ext in ['*.py', '*.js', '*.ts', '*.java', '*.go', '*.rs']:
            for file in src_dir.rglob(ext):
                try:
                    content.append(file.read_text())
                except Exception:
                    pass
        
        return '\n'.join(content)
    
    def _get_test_content(self, project_path: Path) -> str:
        """Get concatenated content of all test files."""
        content = []
        test_dirs = ['tests', 'test', 'spec', '__tests__']
        
        for test_dir_name in test_dirs:
            test_dir = project_path / test_dir_name
            if test_dir.exists():
                for ext in ['*.py', '*.js', '*.ts']:
                    for file in test_dir.rglob(ext):
                        try:
                            content.append(file.read_text())
                        except Exception:
                            pass
        
        return '\n'.join(content)
    
    def _check_technology_requirement(self, project_path: Path, tech: str) -> bool:
        """Check if a technology/framework is used."""
        tech_lower = tech.lower()
        
        # Check package files
        package_files = [
            'requirements.txt', 'pyproject.toml', 'package.json',
            'Gemfile', 'go.mod', 'Cargo.toml', 'pom.xml'
        ]
        
        for pkg_file in package_files:
            pkg_path = project_path / pkg_file
            if pkg_path.exists():
                try:
                    content = pkg_path.read_text().lower()
                    if tech_lower in content:
                        return True
                    # Check common aliases
                    if tech_lower == 'fastapi' and 'fastapi' in content:
                        return True
                    if tech_lower == 'postgresql' and ('psycopg' in content or 'postgres' in content):
                        return True
                except Exception:
                    pass
        
        # Check imports in code
        src_dirs = ['src', 'app', 'lib', project_path.name]
        for src_name in src_dirs:
            src_dir = project_path / src_name
            if src_dir.exists():
                for py_file in src_dir.rglob('*.py'):
                    try:
                        content = py_file.read_text().lower()
                        if f"import {tech_lower}" in content or f"from {tech_lower}" in content:
                            return True
                    except Exception:
                        pass
        
        return False
    
    def _check_database_requirement(self, project_path: Path, db_req: str) -> bool:
        """Check if database requirement is met."""
        db_lower = db_req.lower()
        
        # Check for database configuration files
        config_indicators = {
            'postgres': ['psycopg', 'postgresql', 'pg_', 'postgres'],
            'mysql': ['pymysql', 'mysql-connector', 'mysqldb'],
            'mongodb': ['pymongo', 'mongodb', 'mongoose'],
            'sqlite': ['sqlite3', 'sqlite'],
            'redis': ['redis', 'redis-py']
        }
        
        for db_type, indicators in config_indicators.items():
            if db_type in db_lower:
                # Check if any indicator is present
                for indicator in indicators:
                    if self._check_technology_requirement(project_path, indicator):
                        return True
        
        return False
    
    def _check_security_requirement(self, project_path: Path, sec_req: str) -> bool:
        """Check if security requirement is implemented."""
        sec_lower = sec_req.lower()
        
        # Security-related imports and patterns
        security_patterns = {
            'authentication': ['authenticate', 'login', 'jwt', 'oauth', 'auth'],
            'authorization': ['authorize', 'permission', 'role', 'access_control'],
            'encryption': ['encrypt', 'decrypt', 'bcrypt', 'hash', 'crypto'],
            'validation': ['validate', 'sanitize', 'clean', 'escape', 'safe']
        }
        
        for sec_type, patterns in security_patterns.items():
            if sec_type in sec_lower:
                code_content = self._get_all_code_content(project_path / 'src')
                for pattern in patterns:
                    if pattern in code_content.lower():
                        return True
        
        return False
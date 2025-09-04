"""
Spec parser for extracting testable requirements from specification files.
Part of the spec-aware validation system.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
import json
from functools import lru_cache

logger = logging.getLogger(__name__)


class SpecParser:
    """
    Parses Markdown specs to extract user stories, acceptance criteria, and other requirements.
    Supports YAML frontmatter and structured sections.
    """
    
    def __init__(self):
        self.cache = {}  # Simple in-memory cache for parsed specs
        self.cache_dir = Path.home() / '.tmux-orchestrator' / 'spec_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    @lru_cache(maxsize=128)
    def parse_spec(self, spec_path: Path) -> Dict[str, Any]:
        """
        Parse a spec.md file into structured requirements.
        
        Args:
            spec_path: Path to the spec.md file
            
        Returns:
            Dict with keys: user_stories, acceptance_criteria, test_scenarios, api_endpoints, etc.
        """
        # Check file-based cache first
        cache_file = self.cache_dir / f"{spec_path.name}.json"
        if cache_file.exists():
            try:
                mtime = spec_path.stat().st_mtime if spec_path.exists() else 0
                cache_mtime = cache_file.stat().st_mtime
                if cache_mtime > mtime:  # Cache is newer than spec
                    with open(cache_file, 'r') as f:
                        return json.load(f)
            except Exception:
                pass  # Fall through to parse
        
        if not spec_path.exists():
            logger.warning(f"Spec file not found: {spec_path}")
            return {}
        
        try:
            content = spec_path.read_text(encoding='utf-8')
            
            # Extract YAML frontmatter
            frontmatter = self._extract_frontmatter(content)
            
            # Remove frontmatter from content for parsing
            if content.startswith('---'):
                end_idx = content.find('---', 3)
                if end_idx != -1:
                    content = content[end_idx + 3:].strip()
            
            # Extract sections directly from markdown (simpler than HTML parsing)
            user_stories = self._extract_user_stories(content)
            acceptance_criteria = self._extract_acceptance_criteria(content)
            test_scenarios = self._extract_test_scenarios(content)
            api_endpoints = self._extract_api_endpoints(content)
            implementation_requirements = self._extract_implementation_requirements(content)
            
            parsed = {
                'frontmatter': frontmatter,
                'user_stories': user_stories,
                'acceptance_criteria': acceptance_criteria,
                'test_scenarios': test_scenarios,
                'api_endpoints': api_endpoints,
                'implementation_requirements': implementation_requirements,
                'version': frontmatter.get('version', 'unknown'),
                'spec_path': str(spec_path)
            }
            
            # Save to cache
            try:
                with open(cache_file, 'w') as f:
                    json.dump(parsed, f, indent=2)
            except Exception as e:
                logger.debug(f"Could not cache parsed spec: {e}")
            
            return parsed
            
        except Exception as e:
            logger.error(f"Failed to parse spec {spec_path}: {e}")
            return {}
    
    def _extract_frontmatter(self, content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter from Markdown."""
        if not content.startswith('---'):
            return {}
        
        end_idx = content.find('---', 3)
        if end_idx == -1:
            return {}
        
        frontmatter_str = content[3:end_idx].strip()
        try:
            return yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML frontmatter: {e}")
            return {}
    
    def _extract_user_stories(self, content: str) -> List[Dict[str, str]]:
        """Extract user stories from 'As a...' patterns."""
        stories = []
        
        # Pattern 1: "As a [role], I want/can [action] so that [benefit]"
        pattern1 = r"As a[n]?\s+([^,]+),\s*I\s+(?:want|can|need|should be able to)\s+([^\.]+)(?:\s+so that\s+([^\.]+))?"
        matches = re.findall(pattern1, content, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            role, action, benefit = match
            stories.append({
                'role': role.strip(),
                'action': action.strip(),
                'benefit': benefit.strip() if benefit else "",
                'full_text': f"As a {role.strip()}, I want {action.strip()}" + 
                            (f" so that {benefit.strip()}" if benefit else "")
            })
        
        # Pattern 2: User story sections with bullet points
        story_sections = re.findall(
            r"#+\s*User Stor(?:y|ies)[^\n]*\n+((?:[-*]\s+[^\n]+\n?)+)",
            content, re.IGNORECASE
        )
        
        for section in story_sections:
            bullets = re.findall(r"[-*]\s+(.+)", section)
            for bullet in bullets:
                # Check if it's a user story format
                if re.search(r"As a", bullet, re.IGNORECASE):
                    # Try to parse it
                    match = re.search(pattern1, bullet, re.IGNORECASE)
                    if match:
                        role, action, benefit = match.groups()
                        stories.append({
                            'role': role.strip(),
                            'action': action.strip(),
                            'benefit': benefit.strip() if benefit else "",
                            'full_text': bullet.strip()
                        })
                else:
                    # Generic story format
                    stories.append({
                        'role': 'user',
                        'action': bullet.strip(),
                        'benefit': '',
                        'full_text': bullet.strip()
                    })
        
        return stories
    
    def _extract_acceptance_criteria(self, content: str) -> List[str]:
        """Extract acceptance criteria from bullet-point sections."""
        criteria = []
        
        # Find acceptance criteria sections
        sections = re.findall(
            r"#+\s*Acceptance Criteria[^\n]*\n+((?:[-*]\s+[^\n]+\n?)+)",
            content, re.IGNORECASE
        )
        
        for section in sections:
            bullets = re.findall(r"[-*]\s+(.+)", section)
            criteria.extend([b.strip() for b in bullets])
        
        # Also look for "Must have", "Should have" patterns
        must_have = re.findall(r"(?:Must|Should)\s+(?:have|support|include)[:\s]+([^\n\.]+)", content, re.IGNORECASE)
        criteria.extend([m.strip() for m in must_have])
        
        return list(set(criteria))  # Remove duplicates
    
    def _extract_test_scenarios(self, content: str) -> List[Dict[str, str]]:
        """Extract test scenarios from narrative sections."""
        scenarios = []
        
        # Find test scenario sections
        test_sections = re.findall(
            r"#+\s*(?:Test|Testing|Scenario)[^\n]*\n+((?:[^\n]+\n?)+?)(?=\n#|\Z)",
            content, re.IGNORECASE | re.DOTALL
        )
        
        for section in test_sections:
            # Look for Given/When/Then patterns (BDD style)
            bdd_patterns = re.findall(
                r"(Given[^\n]+When[^\n]+Then[^\n]+)",
                section, re.IGNORECASE
            )
            for pattern in bdd_patterns:
                scenarios.append({
                    'type': 'bdd',
                    'scenario': pattern.strip()
                })
            
            # Look for numbered scenarios
            numbered = re.findall(r"\d+\.\s+([^\n]+)", section)
            for scenario in numbered:
                if scenario and len(scenario) > 10:  # Skip very short items
                    scenarios.append({
                        'type': 'numbered',
                        'scenario': scenario.strip()
                    })
            
            # Look for bullet point scenarios
            bullets = re.findall(r"[-*]\s+([^\n]+)", section)
            for bullet in bullets:
                if bullet and len(bullet) > 10:
                    scenarios.append({
                        'type': 'bullet',
                        'scenario': bullet.strip()
                    })
        
        return scenarios
    
    def _extract_api_endpoints(self, content: str) -> List[Dict[str, str]]:
        """Extract API endpoints from documentation sections."""
        endpoints = []
        
        # Pattern for REST API endpoints
        # Matches: GET /api/v1/users, POST /api/users/{id}, etc.
        api_pattern = r"(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s\n]+)(?:\s*[-–]\s*([^\n]+))?"
        matches = re.findall(api_pattern, content, re.IGNORECASE)
        
        for method, path, desc in matches:
            endpoints.append({
                'method': method.upper(),
                'path': path.strip(),
                'description': desc.strip() if desc else ""
            })
        
        # Also look for API sections with code blocks
        code_blocks = re.findall(r"```(?:json|javascript|python)?\n([^`]+)\n```", content)
        for block in code_blocks:
            # Check if it looks like API definition
            if re.search(r"(GET|POST|PUT|DELETE)", block, re.IGNORECASE):
                block_endpoints = re.findall(api_pattern, block, re.IGNORECASE)
                for method, path, desc in block_endpoints:
                    endpoints.append({
                        'method': method.upper(),
                        'path': path.strip(),
                        'description': desc.strip() if desc else ""
                    })
        
        return endpoints
    
    def _extract_implementation_requirements(self, content: str) -> List[Dict[str, Any]]:
        """Extract specific implementation requirements."""
        requirements = []
        
        # Look for technology requirements
        tech_patterns = [
            (r"(?:Use|Implement with|Built? with)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", 'technology'),
            (r"(?:Database|Storage):\s*([^\n]+)", 'database'),
            (r"(?:Framework|Library):\s*([^\n]+)", 'framework'),
            (r"(?:Language|Programming Language):\s*([^\n]+)", 'language')
        ]
        
        for pattern, req_type in tech_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                requirements.append({
                    'type': req_type,
                    'requirement': match.strip()
                })
        
        # Look for performance requirements
        perf_patterns = re.findall(
            r"(?:Response time|Latency|Performance)[:\s]+([^\n\.]+)",
            content, re.IGNORECASE
        )
        for req in perf_patterns:
            requirements.append({
                'type': 'performance',
                'requirement': req.strip()
            })
        
        # Look for security requirements
        sec_patterns = re.findall(
            r"(?:Security|Authentication|Authorization)[:\s]+([^\n\.]+)",
            content, re.IGNORECASE
        )
        for req in sec_patterns:
            requirements.append({
                'type': 'security',
                'requirement': req.strip()
            })
        
        return requirements
    
    def invalidate_cache(self, spec_path: Path):
        """Invalidate cached spec parsing."""
        cache_file = self.cache_dir / f"{spec_path.name}.json"
        if cache_file.exists():
            cache_file.unlink()
        
        # Clear from LRU cache
        self.parse_spec.cache_clear()
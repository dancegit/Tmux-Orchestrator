#!/usr/bin/env python3
"""
Implementation validation system to ensure projects have actual code before marking complete.
Prevents empty projects from being marked as complete.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class ImplementationValidator:
    """Validates that actual implementation exists before allowing completion"""
    
    # Minimum thresholds for valid implementation
    MIN_SOURCE_FILES = 2  # At least 2 Python files
    MIN_LINES_OF_CODE = 50  # At least 50 lines of actual code
    MIN_FUNCTIONS = 2  # At least 2 functions/classes defined
    MIN_TEST_FILES = 1  # At least 1 test file
    MIN_COMMITS = 3  # At least 3 git commits (initial + 2 implementation)
    
    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.src_path = self.project_path / 'src'
        self.tests_path = self.project_path / 'tests'
    
    def validate_implementation(self) -> Tuple[bool, List[str], Dict[str, int]]:
        """
        Validate that the project has actual implementation.
        Returns: (is_valid, reasons, metrics)
        """
        reasons = []
        metrics = {}
        
        # Check source files exist
        source_files = self._count_source_files()
        metrics['source_files'] = source_files
        if source_files < self.MIN_SOURCE_FILES:
            reasons.append(f"Insufficient source files: {source_files} < {self.MIN_SOURCE_FILES}")
        
        # Check lines of code
        loc = self._count_lines_of_code()
        metrics['lines_of_code'] = loc
        if loc < self.MIN_LINES_OF_CODE:
            reasons.append(f"Insufficient lines of code: {loc} < {self.MIN_LINES_OF_CODE}")
        
        # Check for functions/classes
        functions = self._count_functions_and_classes()
        metrics['functions_classes'] = functions
        if functions < self.MIN_FUNCTIONS:
            reasons.append(f"Insufficient functions/classes: {functions} < {self.MIN_FUNCTIONS}")
        
        # Check test files
        test_files = self._count_test_files()
        metrics['test_files'] = test_files
        if test_files < self.MIN_TEST_FILES:
            reasons.append(f"Insufficient test files: {test_files} < {self.MIN_TEST_FILES}")
        
        # Check git commits
        commits = self._count_git_commits()
        metrics['git_commits'] = commits
        if commits < self.MIN_COMMITS:
            reasons.append(f"Insufficient git commits: {commits} < {self.MIN_COMMITS}")
        
        # Check for empty directories
        if self.src_path.exists() and not any(self.src_path.iterdir()):
            reasons.append("src/ directory is empty")
        
        # Check for actual implementation patterns
        has_implementation = self._check_implementation_patterns()
        metrics['has_implementation_patterns'] = 1 if has_implementation else 0
        if not has_implementation:
            reasons.append("No implementation patterns found (no functions, classes, or meaningful code)")
        
        is_valid = len(reasons) == 0
        
        if is_valid:
            logger.info(f"Implementation validation PASSED for {self.project_path}")
            logger.info(f"Metrics: {metrics}")
        else:
            logger.warning(f"Implementation validation FAILED for {self.project_path}")
            logger.warning(f"Reasons: {reasons}")
            logger.warning(f"Metrics: {metrics}")
        
        return is_valid, reasons, metrics
    
    def _count_source_files(self) -> int:
        """Count Python source files in src directory"""
        if not self.src_path.exists():
            return 0
        
        count = 0
        for file in self.src_path.rglob('*.py'):
            # Skip __pycache__ and empty __init__ files
            if '__pycache__' not in str(file):
                if file.name != '__init__.py' or file.stat().st_size > 10:
                    count += 1
        return count
    
    def _count_lines_of_code(self) -> int:
        """Count actual lines of code (excluding comments and blank lines)"""
        if not self.src_path.exists():
            return 0
        
        total_lines = 0
        for file in self.src_path.rglob('*.py'):
            if '__pycache__' in str(file):
                continue
            try:
                with open(file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Count non-empty, non-comment lines
                        if line and not line.startswith('#'):
                            total_lines += 1
            except Exception as e:
                logger.debug(f"Error reading {file}: {e}")
        
        return total_lines
    
    def _count_functions_and_classes(self) -> int:
        """Count function and class definitions"""
        if not self.src_path.exists():
            return 0
        
        count = 0
        for file in self.src_path.rglob('*.py'):
            if '__pycache__' in str(file):
                continue
            try:
                with open(file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('def ') or line.startswith('class '):
                            count += 1
            except Exception as e:
                logger.debug(f"Error reading {file}: {e}")
        
        return count
    
    def _count_test_files(self) -> int:
        """Count test files"""
        count = 0
        
        # Check tests directory
        if self.tests_path.exists():
            for file in self.tests_path.rglob('test_*.py'):
                if '__pycache__' not in str(file):
                    count += 1
        
        # Also check for tests in src
        if self.src_path.exists():
            for file in self.src_path.rglob('test_*.py'):
                if '__pycache__' not in str(file):
                    count += 1
        
        return count
    
    def _count_git_commits(self) -> int:
        """Count git commits in the repository"""
        try:
            result = subprocess.run(
                ['git', 'rev-list', '--count', 'HEAD'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception as e:
            logger.debug(f"Error counting git commits: {e}")
        
        return 0
    
    def _check_implementation_patterns(self) -> bool:
        """Check for actual implementation patterns in the code"""
        if not self.src_path.exists():
            return False
        
        patterns_found = {
            'imports': False,
            'functions': False,
            'classes': False,
            'logic': False
        }
        
        for file in self.src_path.rglob('*.py'):
            if '__pycache__' in str(file):
                continue
            
            try:
                with open(file, 'r') as f:
                    content = f.read()
                    
                    # Check for imports (real implementation needs dependencies)
                    if 'import ' in content or 'from ' in content:
                        patterns_found['imports'] = True
                    
                    # Check for function definitions
                    if 'def ' in content:
                        patterns_found['functions'] = True
                    
                    # Check for class definitions
                    if 'class ' in content:
                        patterns_found['classes'] = True
                    
                    # Check for logic patterns (if/for/while/try)
                    if any(pattern in content for pattern in ['if ', 'for ', 'while ', 'try:']):
                        patterns_found['logic'] = True
                    
                    # If we found enough patterns, it's likely real implementation
                    if sum(patterns_found.values()) >= 3:
                        return True
            except Exception as e:
                logger.debug(f"Error checking patterns in {file}: {e}")
        
        return sum(patterns_found.values()) >= 2  # At least 2 patterns for minimal implementation


def validate_project_implementation(project_path: str) -> bool:
    """
    Simple interface to validate a project has actual implementation.
    Returns True if valid, False otherwise.
    """
    validator = ImplementationValidator(Path(project_path))
    is_valid, reasons, metrics = validator.validate_implementation()
    
    if not is_valid:
        logger.error(f"Project {project_path} FAILED validation:")
        for reason in reasons:
            logger.error(f"  - {reason}")
    
    return is_valid


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
        is_valid = validate_project_implementation(project_path)
        sys.exit(0 if is_valid else 1)
    else:
        print("Usage: implementation_validator.py <project_path>")
        sys.exit(1)
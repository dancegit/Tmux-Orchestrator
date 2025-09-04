#!/usr/bin/env python3
"""
Simple AI-powered validation script using Claude CLI.
This implements the user's suggestion of piping spec, code, and tests through Claude
for semantic validation of implementation against specification.
"""

import sys
import subprocess
import json
from pathlib import Path
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def validate_with_claude(spec_file: Path, project_dir: Path, use_grok: bool = False) -> dict:
    """
    Simple validation by piping everything through Claude/Grok.
    
    This is the simpler approach - just gather spec, code, and test results,
    then ask AI if implementation matches specification.
    """
    
    # Gather content
    content_parts = []
    
    # 1. Read specification
    if spec_file.exists():
        logger.info(f"Reading spec: {spec_file}")
        spec_content = spec_file.read_text()
        content_parts.append(f"=== SPECIFICATION ===\n{spec_content[:20000]}")  # Limit size
    else:
        logger.error(f"Spec file not found: {spec_file}")
        return {"error": "Spec not found", "passed": False}
    
    # 2. Gather implementation files
    logger.info(f"Reading implementation from: {project_dir}")
    src_dir = project_dir / 'src'
    if not src_dir.exists():
        # Try alternative directories
        for alt in ['app', 'lib', project_dir.name]:
            alt_dir = project_dir / alt
            if alt_dir.exists():
                src_dir = alt_dir
                break
    
    if src_dir.exists():
        impl_files = []
        for py_file in src_dir.rglob('*.py'):
            if py_file.stat().st_size < 50000:  # Skip huge files
                try:
                    content = py_file.read_text()
                    impl_files.append(f"### {py_file.relative_to(project_dir)}\n{content}")
                except Exception as e:
                    logger.warning(f"Could not read {py_file}: {e}")
        
        if impl_files:
            content_parts.append(f"=== IMPLEMENTATION CODE ===\n" + "\n\n".join(impl_files[:10]))  # Max 10 files
        else:
            content_parts.append("=== IMPLEMENTATION CODE ===\nNo implementation files found")
    else:
        content_parts.append("=== IMPLEMENTATION CODE ===\nNo source directory found")
    
    # 3. Get test results
    logger.info("Checking test results...")
    test_results = []
    
    # Look for test report files
    for report_name in ['test_report.json', 'test_report.xml', '.test_report.json']:
        report_path = project_dir / report_name
        if report_path.exists():
            try:
                content = report_path.read_text()[:5000]  # Limit size
                test_results.append(f"### {report_name}\n{content}")
            except Exception:
                pass
    
    # Try running tests if no reports found
    if not test_results:
        tests_dir = project_dir / 'tests'
        if tests_dir.exists():
            logger.info("Running tests...")
            try:
                result = subprocess.run(
                    ['python', '-m', 'pytest', '--tb=short', '-q', '--no-header'],
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                test_results.append(f"### pytest output\nReturn code: {result.returncode}\n{result.stdout[:5000]}")
            except subprocess.TimeoutExpired:
                test_results.append("### pytest output\nTest execution timeout")
            except Exception as e:
                test_results.append(f"### pytest output\nCould not run tests: {e}")
        else:
            test_results.append("No tests directory found")
    
    if test_results:
        content_parts.append(f"=== TEST RESULTS ===\n" + "\n\n".join(test_results))
    else:
        content_parts.append("=== TEST RESULTS ===\nNo test results available")
    
    # Combine all content
    full_content = "\n\n".join(content_parts)
    
    # Create validation prompt
    prompt = """You are validating if a software implementation correctly fulfills its specification.

Analyze the provided specification, implementation code, and test results to determine:
1. Are all user stories from the spec implemented?
2. Are acceptance criteria met?
3. Are API endpoints correctly implemented?
4. Do tests adequately validate the requirements?
5. Are there critical gaps between spec and implementation?

Provide a CONCISE response with:
- Validation score (0-100)
- Pass/Fail verdict
- Key issues found (if any)
- Critical gaps (if any)

Format your response as JSON:
{
    "score": <0-100>,
    "verdict": "PASS|FAIL",
    "confidence": "HIGH|MEDIUM|LOW",
    "issues": ["issue1", "issue2"],
    "gaps": ["gap1", "gap2"],
    "summary": "brief explanation"
}

Content to analyze:
"""
    
    # Call Claude
    logger.info("Calling Claude for validation...")
    
    if use_grok:
        # Would use Grok MCP here
        cmd = ['claude', '-p', '--dangerously-skip-permissions']
    else:
        cmd = ['claude', '-p', '--dangerously-skip-permissions']
    
    try:
        # Combine prompt and content
        full_input = prompt + "\n" + full_content
        
        # Limit total size to avoid token limits
        if len(full_input) > 100000:
            full_input = full_input[:100000] + "\n[Content truncated due to size]"
        
        result = subprocess.run(
            cmd + [full_input],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"Claude returned error: {result.stderr}")
            return {"error": result.stderr, "passed": False}
        
        # Parse response
        response = result.stdout
        logger.debug(f"Claude response: {response[:500]}")
        
        # Try to extract JSON
        import re
        json_match = re.search(r'\{[^}]*\}', response, re.DOTALL)
        if json_match:
            try:
                validation_result = json.loads(json_match.group())
                return {
                    "score": validation_result.get("score", 0),
                    "verdict": validation_result.get("verdict", "UNKNOWN"),
                    "confidence": validation_result.get("confidence", "LOW"),
                    "issues": validation_result.get("issues", []),
                    "gaps": validation_result.get("gaps", []),
                    "summary": validation_result.get("summary", ""),
                    "passed": validation_result.get("verdict") == "PASS" or validation_result.get("score", 0) >= 70
                }
            except json.JSONDecodeError:
                logger.warning("Could not parse JSON from response")
        
        # Fallback: look for score and verdict in text
        score_match = re.search(r'(\d+)\s*(?:%|/100|out of 100)', response, re.IGNORECASE)
        verdict_match = re.search(r'\b(PASS|FAIL)\b', response, re.IGNORECASE)
        
        score = int(score_match.group(1)) if score_match else 50
        verdict = verdict_match.group(1) if verdict_match else "UNKNOWN"
        
        return {
            "score": score,
            "verdict": verdict,
            "confidence": "LOW",
            "raw_response": response[:1000],
            "passed": verdict == "PASS" or score >= 70
        }
        
    except subprocess.TimeoutExpired:
        logger.error("Claude timeout")
        return {"error": "Timeout", "passed": False}
    except Exception as e:
        logger.error(f"Error calling Claude: {e}")
        return {"error": str(e), "passed": False}


def main():
    parser = argparse.ArgumentParser(
        description='Validate project implementation against spec using AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a project
  %(prog)s --spec specs/project.md --project /path/to/project
  
  # Validate with Grok instead of Claude
  %(prog)s --spec specs/project.md --project /path/to/project --use-grok
  
  # Validate projects 83 and 84 from database
  %(prog)s --project-id 83
  %(prog)s --project-id 84
        """
    )
    
    parser.add_argument('--spec', type=Path, help='Path to specification file')
    parser.add_argument('--project', type=Path, help='Path to project directory')
    parser.add_argument('--project-id', type=int, help='Project ID from database')
    parser.add_argument('--use-grok', action='store_true', help='Use Grok instead of Claude')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle project ID lookup
    if args.project_id:
        # Look up project from database
        import sqlite3
        db_path = Path('task_queue.db')
        if not db_path.exists():
            logger.error(f"Database not found: {db_path}")
            sys.exit(1)
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT spec_path, project_path FROM project_queue WHERE id = ?",
            (args.project_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            logger.error(f"Project {args.project_id} not found")
            sys.exit(1)
        
        spec_path = Path(row[0]) if row[0] else None
        project_path = Path(row[1]) if row[1] else None
        
        if not spec_path or not spec_path.exists():
            logger.error(f"Spec not found for project {args.project_id}")
            sys.exit(1)
        
        if not project_path or not project_path.exists():
            logger.error(f"Project path not found for project {args.project_id}")
            sys.exit(1)
        
        logger.info(f"Validating project {args.project_id}")
        logger.info(f"  Spec: {spec_path}")
        logger.info(f"  Project: {project_path}")
        
    else:
        # Use provided paths
        if not args.spec or not args.project:
            parser.error("Either --project-id or both --spec and --project are required")
        
        spec_path = args.spec
        project_path = args.project
    
    # Validate
    logger.info("=" * 60)
    logger.info("AI-POWERED VALIDATION")
    logger.info("=" * 60)
    
    result = validate_with_claude(spec_path, project_path, args.use_grok)
    
    # Display results
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION RESULTS")
    logger.info("=" * 60)
    
    if "error" in result:
        logger.error(f"Validation failed: {result['error']}")
        sys.exit(1)
    
    logger.info(f"Score: {result.get('score', 'N/A')}/100")
    logger.info(f"Verdict: {result.get('verdict', 'UNKNOWN')}")
    logger.info(f"Confidence: {result.get('confidence', 'N/A')}")
    
    if result.get('issues'):
        logger.info("\nIssues found:")
        for issue in result['issues']:
            logger.info(f"  - {issue}")
    
    if result.get('gaps'):
        logger.info("\nCritical gaps:")
        for gap in result['gaps']:
            logger.info(f"  - {gap}")
    
    if result.get('summary'):
        logger.info(f"\nSummary: {result['summary']}")
    
    # Exit code based on pass/fail
    if result.get('passed', False):
        logger.info("\n✅ VALIDATION PASSED")
        sys.exit(0)
    else:
        logger.info("\n❌ VALIDATION FAILED")
        sys.exit(1)


if __name__ == '__main__':
    main()
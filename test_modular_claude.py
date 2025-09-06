#!/usr/bin/env python3
"""
Test script for the modularized CLAUDE knowledge base system.

This script tests:
1. Module extraction and creation
2. Token limits for each module
3. ModuleLoader functionality
4. BriefingSystem integration
5. Rule extraction from modules
"""

import sys
from pathlib import Path
from typing import Dict, List
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from tmux_orchestrator.agents.module_loader import ModuleLoader
from tmux_orchestrator.agents.briefing_system import BriefingSystem, BriefingContext, ProjectSpec, RoleConfig
from monitoring.extract_rules_modular import ModularRuleExtractor


def estimate_tokens(text: str) -> int:
    """Rough estimation: 1 token ≈ 4 characters"""
    return len(text) // 4


def test_module_creation():
    """Test that modules were created correctly"""
    print("=" * 60)
    print("TEST 1: Module Creation and Structure")
    print("=" * 60)
    
    modules_dir = Path(__file__).parent / 'docs' / 'claude_modules'
    
    if not modules_dir.exists():
        print("❌ FAIL: Modules directory does not exist")
        return False
    
    expected_structure = {
        'index.md': None,
        'metadata.json': None,
        'core': ['principles.md', 'communication.md', 'completion.md'],
        'roles': ['core_roles.md', 'optional_roles.md', 'system_ops_roles.md'],
        'workflows': ['git_workflow.md', 'worktree_setup.md'],
        'configuration': ['team_detection.md', 'scaling.md']
    }
    
    all_exist = True
    for item, children in expected_structure.items():
        if children is None:
            # It's a file
            file_path = modules_dir / item
            if file_path.exists():
                print(f"✅ Found: {item}")
            else:
                print(f"❌ Missing: {item}")
                all_exist = False
        else:
            # It's a directory with files
            dir_path = modules_dir / item
            if not dir_path.exists():
                print(f"❌ Missing directory: {item}/")
                all_exist = False
            else:
                for child in children:
                    child_path = dir_path / child
                    if child_path.exists():
                        print(f"✅ Found: {item}/{child}")
                    else:
                        print(f"❌ Missing: {item}/{child}")
                        all_exist = False
    
    return all_exist


def test_token_limits():
    """Test that all modules are under 10,000 tokens"""
    print("\n" + "=" * 60)
    print("TEST 2: Token Limits")
    print("=" * 60)
    
    modules_dir = Path(__file__).parent / 'docs' / 'claude_modules'
    all_under_limit = True
    
    for module_file in modules_dir.rglob('*.md'):
        content = module_file.read_text()
        tokens = estimate_tokens(content)
        relative_path = module_file.relative_to(modules_dir)
        
        if tokens < 10000:
            print(f"✅ {relative_path}: ~{tokens} tokens")
        else:
            print(f"❌ {relative_path}: ~{tokens} tokens (EXCEEDS LIMIT)")
            all_under_limit = False
    
    # Check metadata
    metadata_path = modules_dir / 'metadata.json'
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())
        print(f"\n📊 Total modules: {len(metadata.get('modules', {}))}")
    
    return all_under_limit


def test_module_loader():
    """Test the ModuleLoader class"""
    print("\n" + "=" * 60)
    print("TEST 3: ModuleLoader Functionality")
    print("=" * 60)
    
    modules_path = Path(__file__).parent / 'docs' / 'claude_modules'
    
    try:
        loader = ModuleLoader(modules_path)
        print("✅ ModuleLoader initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize ModuleLoader: {e}")
        return False
    
    # Test loading for different roles
    test_roles = ['orchestrator', 'developer', 'sysadmin', 'researcher']
    
    for role in test_roles:
        print(f"\nTesting role: {role}")
        try:
            modules = loader.load_for_role(role)
            
            # Check that we got the expected keys
            expected_keys = ['core', 'role', 'workflows', 'configuration']
            for key in expected_keys:
                if key in modules:
                    content_len = len(modules[key])
                    if content_len > 0:
                        print(f"  ✅ {key}: {content_len} chars")
                    else:
                        # Configuration might be empty for some roles
                        if key == 'configuration' and role not in ['orchestrator', 'project_manager']:
                            print(f"  ⚠️  {key}: empty (expected for this role)")
                        else:
                            print(f"  ⚠️  {key}: empty")
                else:
                    print(f"  ❌ {key}: missing")
            
            # Test formatted output
            formatted = loader.format_role_context(modules)
            print(f"  📄 Formatted context: {len(formatted)} chars (~{estimate_tokens(formatted)} tokens)")
            
        except Exception as e:
            print(f"  ❌ Error loading modules for {role}: {e}")
            return False
    
    return True


def test_briefing_integration():
    """Test integration with BriefingSystem"""
    print("\n" + "=" * 60)
    print("TEST 4: BriefingSystem Integration")
    print("=" * 60)
    
    tmux_path = Path(__file__).parent
    
    try:
        briefing_system = BriefingSystem(tmux_path)
        print("✅ BriefingSystem initialized with ModuleLoader")
    except Exception as e:
        print(f"❌ Failed to initialize BriefingSystem: {e}")
        return False
    
    # Create test context
    project_spec = ProjectSpec(
        name="Test Project",
        path="/tmp/test_project",
        type="web_application",
        main_tech=["Python", "FastAPI"],
        description="Test project for modular CLAUDE"
    )
    
    role_config = RoleConfig(
        window_name="Developer",
        initial_commands=["claude"],
        check_in_interval=30,
        responsibilities=["Write code", "Create tests"]
    )
    
    context = BriefingContext(
        project_spec=project_spec,
        role_config=role_config,
        session_name="test-session",
        worktree_path=Path("/tmp/test-worktree"),
        team_members=[("orchestrator", 0), ("developer", 1)],
        git_branch="main"
    )
    
    try:
        briefing = briefing_system.generate_role_briefing(context)
        print(f"✅ Generated briefing: {len(briefing)} chars (~{estimate_tokens(briefing)} tokens)")
        
        # Check that modular content is included
        if "Knowledge Base Context" in briefing or "Module References" in briefing:
            print("✅ Modular content included in briefing")
        else:
            print("⚠️  Modular content may not be included (check if in legacy mode)")
        
    except Exception as e:
        print(f"❌ Failed to generate briefing: {e}")
        return False
    
    return True


def test_rule_extraction():
    """Test rule extraction from modular files"""
    print("\n" + "=" * 60)
    print("TEST 5: Rule Extraction from Modules")
    print("=" * 60)
    
    modules_dir = Path(__file__).parent / 'docs' / 'claude_modules'
    
    try:
        extractor = ModularRuleExtractor(modules_dir)
        print("✅ ModularRuleExtractor initialized")
    except Exception as e:
        print(f"❌ Failed to initialize ModularRuleExtractor: {e}")
        return False
    
    try:
        rules = extractor.extract_all_rules()
        print(f"✅ Extracted {len(rules)} rules")
        
        # Check rule categories
        categories = {}
        for rule in rules:
            cat = rule.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        print("\nRules by category:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count}")
        
        # Verify essential rules exist
        essential_rules = [
            'comm_hub_spoke',
            'git_30min_commit',
            'principle_autonomy',
            'completion_autonomous'
        ]
        
        rule_ids = [r['id'] for r in rules]
        for essential in essential_rules:
            if essential in rule_ids:
                print(f"  ✅ Essential rule found: {essential}")
            else:
                print(f"  ❌ Missing essential rule: {essential}")
        
    except Exception as e:
        print(f"❌ Failed to extract rules: {e}")
        return False
    
    return True


def run_all_tests():
    """Run all tests and report results"""
    print("\n" + "🧪" * 30)
    print("MODULAR CLAUDE KNOWLEDGE BASE TEST SUITE")
    print("🧪" * 30)
    
    tests = [
        ("Module Creation", test_module_creation),
        ("Token Limits", test_token_limits),
        ("ModuleLoader", test_module_loader),
        ("Briefing Integration", test_briefing_integration),
        ("Rule Extraction", test_rule_extraction)
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! The modular system is ready for use.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review and fix issues.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic tests for permissions checking functionality.
Run with: python test_permissions.py
"""

import os
import tempfile
import shutil
from pathlib import Path

def test_permissions_checker():
    """Test the PermissionsChecker class."""
    try:
        from permissions_checker import PermissionsChecker
        
        print("🧪 Testing PermissionsChecker...")
        
        # Test with temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            checker = PermissionsChecker(temp_path)
            
            # Test directory permissions
            dir_perms = checker.check_directory_permissions(temp_path)
            assert dir_perms['exists'], "Temp directory should exist"
            assert dir_perms['writable'], "Temp directory should be writable"
            print("✓ Directory permission check passed")
            
            # Test write permission
            success, error = checker.test_write_permission(temp_path)
            assert success, f"Write test should succeed: {error}"
            print("✓ Write permission test passed")
            
            # Test full vault check
            report = checker.run_full_permissions_check()
            assert report['overall_status'] == 'PASS', "Full check should pass"
            assert report['summary']['success_rate'] == 1.0, "Success rate should be 100%"
            print("✓ Full permissions check passed")
            
        print("🎉 PermissionsChecker tests passed!\n")
        return True
        
    except ImportError:
        print("❌ Cannot import permissions_checker\n")
        return False
    except Exception as e:
        print(f"❌ PermissionsChecker test failed: {e}\n")
        return False


def test_permissions_utils():
    """Test the permissions utility functions."""
    try:
        from permissions_utils import ensure_directory_writable, preflight_check
        
        print("🧪 Testing permissions utilities...")
        
        # Test with temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test ensure_directory_writable
            test_dir = temp_path / "test_subdir"
            result = ensure_directory_writable(test_dir, create_if_missing=True)
            assert result, "Should be able to create and write to directory"
            assert test_dir.exists(), "Directory should have been created"
            print("✓ ensure_directory_writable test passed")
            
            # Test preflight_check
            result = preflight_check(temp_path, required_dirs=["test_subdir"])
            assert result, "Preflight check should pass"
            print("✓ preflight_check test passed")
            
        print("🎉 Permissions utilities tests passed!\n")
        return True
        
    except ImportError as e:
        print(f"❌ Cannot import permissions utilities: {e}\n")
        return False
    except Exception as e:
        print(f"❌ Permissions utilities test failed: {e}\n")
        return False


def test_agent_integration():
    """Test that agents can import and use permissions checking."""
    print("🧪 Testing agent integration...")
    
    try:
        # Test that modules can be imported without errors
        import sys
        import subprocess
        
        # Test permissions_checker CLI
        result = subprocess.run(
            [sys.executable, "permissions_checker.py", "--help"], 
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, "permissions_checker CLI should work"
        assert "Check file system permissions" in result.stdout, "Help text should be present"
        print("✓ permissions_checker CLI test passed")
        
        # Test that enhanced agents can load without errors  
        with tempfile.TemporaryDirectory() as temp_dir:
            env = os.environ.copy()
            env['VAULT_PATH'] = temp_dir
            
            result = subprocess.run(
                [sys.executable, "-c", "import pitch_agent_v4; print('Import successful')"],
                capture_output=True, text=True, timeout=10, env=env
            )
            assert result.returncode == 0, f"pitch_agent_v4 import failed: {result.stderr}"
            print("✓ Enhanced pitch agent import test passed")
            
        print("🎉 Agent integration tests passed!\n")
        return True
        
    except Exception as e:
        print(f"❌ Agent integration test failed: {e}\n")
        return False


def test_batch_file_syntax():
    """Test that batch files have valid syntax."""
    print("🧪 Testing batch file syntax...")
    
    try:
        batch_files = [
            "prep_summarizer_dirs.bat",
            "run_permissions_check.bat"
        ]
        
        for batch_file in batch_files:
            if Path(batch_file).exists():
                # Basic syntax check - look for common issues
                content = Path(batch_file).read_text(encoding='utf-8', errors='ignore')
                
                # Check for basic structure
                assert "@echo off" in content, f"{batch_file} should start with @echo off"
                assert "pause" in content, f"{batch_file} should end with pause"
                print(f"✓ {batch_file} syntax check passed")
            else:
                print(f"⚠️  {batch_file} not found, skipping")
                
        print("🎉 Batch file syntax tests passed!\n")
        return True
        
    except Exception as e:
        print(f"❌ Batch file syntax test failed: {e}\n")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("🔍 Obsidian Agent - Permissions Testing Suite")
    print("=" * 50)
    
    tests = [
        ("PermissionsChecker", test_permissions_checker),
        ("Permissions Utilities", test_permissions_utils),
        ("Agent Integration", test_agent_integration),
        ("Batch File Syntax", test_batch_file_syntax),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Running {test_name} tests...")
        if test_func():
            passed += 1
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("🎉 All tests passed! Permissions checking is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    exit(main())
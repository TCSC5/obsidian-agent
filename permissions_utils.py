#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Permissions Integration Utilities
Simple utilities for integrating permissions checking into existing agents.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Union

# Import the main permissions checker
try:
    from permissions_checker import PermissionsChecker
except ImportError:
    # Fallback if permissions_checker is not available
    PermissionsChecker = None


def validate_vault_permissions(vault_path: Optional[Union[str, Path]] = None, 
                              critical_only: bool = True,
                              exit_on_failure: bool = True) -> bool:
    """
    Validate permissions for vault operations.
    
    Args:
        vault_path: Path to vault (uses VAULT_PATH env var if None)
        critical_only: Only check critical paths vs all paths
        exit_on_failure: Exit program if validation fails
        
    Returns:
        True if all permissions are valid, False otherwise
    """
    if not PermissionsChecker:
        print("Warning: permissions_checker module not available, skipping validation")
        return True
    
    # Determine vault path
    if not vault_path:
        vault_path = os.environ.get("VAULT_PATH") or r"C:\Users\top2e\Sync"
    
    vault_path = Path(vault_path)
    
    try:
        checker = PermissionsChecker(vault_path)
        
        if critical_only:
            # Quick check of just a few critical paths
            critical_paths = [
                vault_path,
                vault_path / "Summaries", 
                vault_path / "data",
                vault_path / "logs"
            ]
            results = checker.validate_critical_paths(critical_paths)
            
            failures = [path for path, result in results.items() 
                       if not result['write_test_passed']]
                       
            if failures:
                print(f"Permission validation failed for {len(failures)} paths:")
                for path in failures:
                    error = results[path]['write_test_error']
                    print(f"  - {path}: {error}")
                
                if exit_on_failure:
                    print("\nExiting due to permission failures. Run prep_summarizer_dirs.bat or fix permissions manually.")
                    sys.exit(1)
                return False
            else:
                print(f"✓ Permissions validated for {len(critical_paths)} critical paths")
                return True
                
        else:
            # Full vault check
            report = checker.run_full_permissions_check()
            
            if report['overall_status'] != 'PASS':
                print(f"Permission validation failed:")
                print(f"  Vault: {report['vault_path']}")
                print(f"  Issues: {len(report['issues'])}")
                for issue in report['issues'][:5]:  # Show first 5 issues
                    print(f"    - {issue}")
                if len(report['issues']) > 5:
                    print(f"    ... and {len(report['issues']) - 5} more")
                
                if exit_on_failure:
                    print(f"\nExiting due to permission failures. Run: python permissions_checker.py --vault-path \"{vault_path}\"")
                    sys.exit(1)
                return False
            else:
                print(f"✓ Full permissions validated - {report['summary']['success_rate']:.1%} success rate")
                return True
                
    except Exception as e:
        print(f"Warning: Permission validation failed with error: {e}")
        if exit_on_failure:
            return True  # Don't exit on validation errors, just warn
        return False


def ensure_directory_writable(directory: Union[str, Path], 
                             create_if_missing: bool = True) -> bool:
    """
    Ensure a directory exists and is writable.
    
    Args:
        directory: Directory path
        create_if_missing: Create directory if it doesn't exist
        
    Returns:
        True if directory is writable, False otherwise
    """
    directory = Path(directory)
    
    try:
        if not directory.exists() and create_if_missing:
            directory.mkdir(parents=True, exist_ok=True)
        
        if not directory.exists():
            return False
        
        # Test write permission
        if PermissionsChecker:
            checker = PermissionsChecker()
            success, error = checker.test_write_permission(directory, cleanup=True)
            return success
        else:
            # Fallback test
            import tempfile
            test_file = directory / f"_temp_write_test_{os.getpid()}.tmp"
            try:
                test_file.write_text("test")
                test_file.unlink()
                return True
            except OSError:
                return False
                
    except Exception:
        return False


def preflight_check(vault_path: Optional[Union[str, Path]] = None,
                   required_dirs: Optional[List[str]] = None) -> bool:
    """
    Perform pre-flight permission check before agent execution.
    
    Args:
        vault_path: Vault path (uses env var if None)
        required_dirs: Additional required directories beyond defaults
        
    Returns:
        True if all checks pass, False otherwise
    """
    # Default required directories
    if required_dirs is None:
        required_dirs = ["Summaries", "data", "logs"]
    
    # Determine vault path
    if not vault_path:
        vault_path = os.environ.get("VAULT_PATH") or r"C:\Users\top2e\Sync"
    
    vault_path = Path(vault_path)
    
    print(f"🔍 Pre-flight permission check for: {vault_path}")
    
    # Check vault root
    if not vault_path.exists():
        print(f"❌ Vault root does not exist: {vault_path}")
        return False
    
    if not ensure_directory_writable(vault_path, create_if_missing=False):
        print(f"❌ Vault root is not writable: {vault_path}")
        return False
    
    print(f"✓ Vault root accessible")
    
    # Check required directories
    all_good = True
    for dir_name in required_dirs:
        dir_path = vault_path / dir_name
        if not ensure_directory_writable(dir_path, create_if_missing=True):
            print(f"❌ Cannot access/create: {dir_name}")
            all_good = False
        else:
            print(f"✓ {dir_name} accessible")
    
    if all_good:
        print(f"🎉 Pre-flight check passed!")
    else:
        print(f"🚫 Pre-flight check failed!")
    
    return all_good


# Decorator for adding permission checks to functions
def require_permissions(vault_path: Optional[Union[str, Path]] = None,
                       required_dirs: Optional[List[str]] = None):
    """
    Decorator to add permission checking to agent functions.
    
    Usage:
        @require_permissions(required_dirs=["Summaries", "data"])
        def my_agent_function():
            # Agent code here
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not preflight_check(vault_path, required_dirs):
                print(f"Permission check failed for {func.__name__}, aborting.")
                return None
            return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # Quick test
    print("Testing permissions integration...")
    result = validate_vault_permissions("/tmp/test_integration", exit_on_failure=False)
    print(f"Test result: {result}")
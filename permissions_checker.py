#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Permissions Checker Module
Provides comprehensive file system permission validation for Obsidian Agent operations.
"""

import os
import stat
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime


class PermissionError(Exception):
    """Custom exception for permission-related failures."""
    pass


class PermissionsChecker:
    """Centralized permissions checking utility for file system operations."""
    
    def __init__(self, vault_path: Optional[Union[str, Path]] = None):
        """Initialize with optional vault path."""
        self.vault_path = Path(vault_path) if vault_path else None
        self._test_files_created = []
    
    def check_directory_permissions(self, path: Union[str, Path]) -> Dict[str, bool]:
        """
        Check read/write/execute permissions for a directory.
        
        Args:
            path: Directory path to check
            
        Returns:
            Dict with permission status: {'exists': bool, 'readable': bool, 'writable': bool, 'executable': bool}
        """
        path = Path(path)
        result = {
            'exists': False,
            'readable': False,
            'writable': False,
            'executable': False
        }
        
        if not path.exists():
            return result
        
        result['exists'] = True
        
        try:
            # Check if directory is readable
            result['readable'] = os.access(path, os.R_OK)
            
            # Check if directory is writable
            result['writable'] = os.access(path, os.W_OK)
            
            # Check if directory is executable (can enter)
            result['executable'] = os.access(path, os.X_OK)
            
        except OSError:
            # If os.access fails, assume no permissions
            pass
            
        return result
    
    def check_file_permissions(self, path: Union[str, Path]) -> Dict[str, bool]:
        """
        Check read/write permissions for a file.
        
        Args:
            path: File path to check
            
        Returns:
            Dict with permission status: {'exists': bool, 'readable': bool, 'writable': bool}
        """
        path = Path(path)
        result = {
            'exists': False,
            'readable': False,
            'writable': False
        }
        
        if not path.exists():
            return result
        
        result['exists'] = True
        
        try:
            result['readable'] = os.access(path, os.R_OK)
            result['writable'] = os.access(path, os.W_OK)
        except OSError:
            pass
            
        return result
    
    def test_write_permission(self, directory: Union[str, Path], cleanup: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Test write permission by attempting to create a temporary file.
        
        Args:
            directory: Directory to test write permission in
            cleanup: Whether to remove test file after creation
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        directory = Path(directory)
        
        if not directory.exists():
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return False, f"Cannot create directory: {e}"
        
        # Generate unique test filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        test_file = directory / f"_perm_test_{timestamp}.tmp"
        
        try:
            # Attempt to write test file
            test_file.write_text("permission test", encoding="utf-8")
            
            if cleanup:
                test_file.unlink()
            else:
                self._test_files_created.append(test_file)
                
            return True, None
            
        except OSError as e:
            return False, f"Write permission test failed: {e}"
    
    def validate_critical_paths(self, paths: List[Union[str, Path]]) -> Dict[str, Dict[str, Union[bool, str]]]:
        """
        Validate permissions for a list of critical paths.
        
        Args:
            paths: List of paths to validate
            
        Returns:
            Dict mapping each path to its permission status and any errors
        """
        results = {}
        
        for path in paths:
            path = Path(path)
            path_str = str(path)
            
            if path.is_file() or (not path.exists() and path.suffix):
                # Handle as file
                perms = self.check_file_permissions(path)
                write_test = (True, None) if perms['exists'] and perms['writable'] else (False, "File not writable")
                
            else:
                # Handle as directory
                perms = self.check_directory_permissions(path)
                write_test = self.test_write_permission(path) if perms['exists'] or not path.exists() else (False, "Directory not accessible")
            
            results[path_str] = {
                'permissions': perms,
                'write_test_passed': write_test[0],
                'write_test_error': write_test[1]
            }
            
        return results
    
    def get_vault_critical_paths(self) -> List[Path]:
        """Get list of critical paths for vault operations."""
        if not self.vault_path:
            return []
        
        critical_paths = [
            self.vault_path,
            self.vault_path / "Summaries",
            self.vault_path / "data", 
            self.vault_path / "logs",
            self.vault_path / "Express" / "pitch",
            self.vault_path / "Express" / "insights",
            self.vault_path / "Resources",
            self.vault_path / "Areas",
            self.vault_path / "Projects",
            self.vault_path / "Archives"
        ]
        
        return critical_paths
    
    def run_full_permissions_check(self) -> Dict[str, any]:
        """
        Run comprehensive permissions check for vault.
        
        Returns:
            Dict with complete permission report
        """
        if not self.vault_path:
            return {"error": "No vault path specified"}
        
        critical_paths = self.get_vault_critical_paths()
        path_results = self.validate_critical_paths(critical_paths)
        
        # Summary statistics
        total_paths = len(path_results)
        writable_paths = sum(1 for r in path_results.values() if r['write_test_passed'])
        existing_paths = sum(1 for r in path_results.values() if r['permissions']['exists'])
        
        issues = []
        for path, result in path_results.items():
            if not result['write_test_passed']:
                issues.append(f"{path}: {result['write_test_error']}")
        
        return {
            "vault_path": str(self.vault_path),
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_paths": total_paths,
                "existing_paths": existing_paths,
                "writable_paths": writable_paths,
                "success_rate": writable_paths / total_paths if total_paths > 0 else 0
            },
            "path_details": path_results,
            "issues": issues,
            "overall_status": "PASS" if len(issues) == 0 else "FAIL"
        }
    
    def cleanup_test_files(self):
        """Remove any test files that weren't cleaned up automatically."""
        for test_file in self._test_files_created:
            try:
                if test_file.exists():
                    test_file.unlink()
            except OSError:
                pass
        self._test_files_created.clear()


def main():
    """CLI interface for permissions checking."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check file system permissions for Obsidian Agent")
    parser.add_argument("--vault-path", type=str, help="Path to Obsidian vault")
    parser.add_argument("--check-path", type=str, help="Check specific path")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    # Determine vault path
    vault_path = args.vault_path or os.environ.get("VAULT_PATH") or r"C:\Users\top2e\Sync"
    
    checker = PermissionsChecker(vault_path)
    
    try:
        if args.check_path:
            # Check specific path
            result = checker.validate_critical_paths([args.check_path])
            if args.json:
                import json
                print(json.dumps(result, indent=2))
            else:
                for path, details in result.items():
                    print(f"\n{path}:")
                    print(f"  Exists: {details['permissions']['exists']}")
                    print(f"  Writable: {details['write_test_passed']}")
                    if details['write_test_error']:
                        print(f"  Error: {details['write_test_error']}")
        else:
            # Full vault check
            result = checker.run_full_permissions_check()
            if args.json:
                import json
                print(json.dumps(result, indent=2))
            else:
                print(f"Permissions Check Report - {result['timestamp']}")
                print(f"Vault Path: {result['vault_path']}")
                print(f"Overall Status: {result['overall_status']}")
                print(f"\nSummary:")
                print(f"  Total paths checked: {result['summary']['total_paths']}")
                print(f"  Existing paths: {result['summary']['existing_paths']}")
                print(f"  Writable paths: {result['summary']['writable_paths']}")
                print(f"  Success rate: {result['summary']['success_rate']:.1%}")
                
                if result['issues']:
                    print(f"\nIssues found:")
                    for issue in result['issues']:
                        print(f"  - {issue}")
                else:
                    print(f"\nNo issues found - all paths accessible!")
                    
    finally:
        checker.cleanup_test_files()


if __name__ == "__main__":
    main()
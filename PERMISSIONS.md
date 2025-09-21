# Permissions Checking

This document describes the enhanced permissions checking functionality added to the Obsidian Agent system.

## Overview

The permissions checking system validates that the Obsidian Agent has proper read/write access to all required directories and files before executing operations. This helps prevent runtime failures and provides clear guidance when access issues occur.

## Components

### 1. `permissions_checker.py`
The core permissions validation module that provides:
- Comprehensive directory and file permission checking
- Write permission testing with temporary files
- Vault-specific critical path validation
- CLI interface for manual checking
- JSON output support for integration

**Usage:**
```bash
# Check all vault permissions
python permissions_checker.py --vault-path "C:\Users\youruser\vault"

# Check specific path
python permissions_checker.py --check-path "C:\Users\youruser\vault\Summaries"

# Get JSON output for automation
python permissions_checker.py --vault-path "C:\Users\youruser\vault" --json
```

### 2. `permissions_utils.py`
Integration utilities for embedding permissions checks into existing agents:
- `preflight_check()` - Quick validation before agent execution
- `ensure_directory_writable()` - Ensure directory exists and is writable
- `validate_vault_permissions()` - Comprehensive vault validation
- `@require_permissions` decorator for functions

### 3. Enhanced Batch Files

#### `prep_summarizer_dirs.bat`
Enhanced version of the original permissions checking script:
- Tests vault root accessibility
- Validates all critical directories
- Creates missing directories automatically
- Provides clear success/failure reporting
- Environment variable support (`VAULT_PATH`)

#### `run_permissions_check.bat`
New convenience script for running comprehensive permissions analysis:
- Python-based detailed checking
- Clear error reporting
- Usage examples for different checking modes

## Agent Integration

### Enhanced Agents
The following agents now include pre-flight permissions checking:
- `pitch_agent_v4.py` - Checks pitch directories and logging paths
- `summarizer_agent_v4.py` - Validates summary processing directories

### Integration Pattern
```python
try:
    from permissions_utils import preflight_check
    required_dirs = ["Summaries", "Express/pitch", "data", "logs"]
    if not preflight_check(vault_path, required_dirs):
        print("❌ Permission check failed. Please run prep_summarizer_dirs.bat")
        return
except ImportError:
    print("⚠️  Permissions utilities not available, proceeding...")
```

## Critical Paths Checked

The system validates access to these vault directories:
- Vault root directory
- `Summaries/` - Summary files
- `data/` - Index and data files  
- `logs/` - Log files and reports
- `Express/pitch/` - Generated pitch files
- `Express/insights/` - Insight files
- `Resources/` - Resource files
- `Areas/` - Area files
- `Projects/` - Project files
- `Archives/` - Archive files

## Error Handling

### Common Issues and Solutions

**Vault root doesn't exist:**
```
❌ Vault root does not exist: C:\Users\youruser\vault
```
Solution: Update `VAULT_PATH` environment variable or create the directory

**No write permissions:**
```
❌ Cannot write to vault root: C:\Users\youruser\vault
```
Solution: Check folder permissions or run as administrator

**Directory creation fails:**
```
❌ Cannot create directory: Summaries
```
Solution: Check parent directory permissions

### Success Indicators
```
🎉 Pre-flight check passed!
✓ Vault root accessible
✓ Summaries accessible
✓ data accessible
```

## Testing

Run the test suite to validate permissions functionality:
```bash
python test_permissions.py
```

Tests cover:
- PermissionsChecker class functionality
- Utility function integration
- Agent import and integration
- Batch file syntax validation

## Environment Variables

- `VAULT_PATH` - Override default vault location
- Standard agent environment variables are respected

## Future Enhancements

Potential improvements:
- Network path validation for shared vaults
- Detailed file-level permission analysis
- Integration with Windows ACL checking
- Automated permission repair suggestions

## Migration Guide

For existing installations:
1. No breaking changes - agents fallback gracefully if permissions utilities unavailable
2. Run `prep_summarizer_dirs.bat` to validate current setup
3. Consider setting `VAULT_PATH` environment variable for consistency
4. Optional: Run `test_permissions.py` to validate system compatibility
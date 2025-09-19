"""
TOML Round-Trip Utilities - Comment and Formatting Preservation

Provides utilities for round-trip TOML editing while preserving comments,
formatting, and structure. Uses tomlkit for comment-preserving operations
while maintaining compatibility with existing Pydantic validation.

Key Features:
- Load TOML files with comments and formatting preserved
- Convert TOMLDocument to plain dictionaries for UI editing
- Apply changes from UI back to TOMLDocument structure
- Save TOML with all comments and formatting intact
- Integration with existing Pydantic validation pipeline

Usage:
    # Load TOML with comments
    doc = await load_toml_with_comments(config_path)
    
    # Convert to plain dict for UI
    plain_dict = doc_to_plain_dict(doc)
    
    # Apply changes from UI
    apply_changes(doc, updated_dict)
    
    # Save with comments preserved
    await save_doc(doc, config_path)
"""

import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

import tomlkit
from tomlkit import TOMLDocument
from pydantic import ValidationError

from .models import CoreConfig

logger = logging.getLogger(__name__)


class TomlRoundTripError(Exception):
    """Raised when TOML round-trip operations fail"""
    pass


async def load_toml_with_comments(path: Union[Path, str]) -> TOMLDocument:
    """
    Load TOML file with comments and formatting preserved.
    
    Args:
        path: Path to TOML configuration file
        
    Returns:
        TOMLDocument with comments and formatting preserved
        
    Raises:
        TomlRoundTripError: If file cannot be loaded or parsed
    """
    try:
        path = Path(path)
        if not path.exists():
            raise TomlRoundTripError(f"TOML file not found: {path}")
            
        # Read file content asynchronously
        content = await asyncio.to_thread(path.read_text, encoding='utf-8')
        
        # Parse with tomlkit to preserve comments
        doc = tomlkit.parse(content)
        
        logger.debug(f"Loaded TOML with comments from: {path}")
        return doc
        
    except Exception as e:
        logger.error(f"Failed to load TOML with comments from {path}: {e}")
        raise TomlRoundTripError(f"Failed to load TOML file: {e}") from e


def doc_to_plain_dict(doc: TOMLDocument) -> Dict[str, Any]:
    """
    Convert TOMLDocument to plain dictionary for UI editing.
    
    Recursively converts tomlkit objects to standard Python types
    while preserving the data structure for frontend consumption.
    
    Args:
        doc: TOMLDocument with comments and formatting
        
    Returns:
        Plain dictionary suitable for JSON serialization and UI editing
    """
    try:
        # Convert to plain Python dict recursively
        def _convert_value(value: Any) -> Any:
            """Recursively convert tomlkit objects to plain Python types"""
            if hasattr(value, 'unwrap'):
                # tomlkit wrapped values (strings, integers, etc.)
                return value.unwrap()
            elif isinstance(value, dict):
                # Nested dictionaries (tables)
                return {k: _convert_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                # Arrays
                return [_convert_value(item) for item in value]
            else:
                # Already plain Python types
                return value
                
        result = _convert_value(dict(doc))
        logger.debug(f"Converted TOMLDocument to plain dict with {len(result)} top-level keys")
        return result
        
    except Exception as e:
        logger.error(f"Failed to convert TOMLDocument to plain dict: {e}")
        raise TomlRoundTripError(f"Failed to convert document: {e}") from e


def apply_changes(doc: TOMLDocument, new_state: Dict[str, Any]) -> None:
    """
    Apply changes from UI back to TOMLDocument while preserving comments.
    
    Merges the new configuration state into the existing TOMLDocument,
    preserving all comments, formatting, and structure. Only updates
    values that have actually changed.
    
    Args:
        doc: Original TOMLDocument with comments
        new_state: Updated configuration data from UI
        
    Raises:
        TomlRoundTripError: If changes cannot be applied
    """
    try:
        def _apply_recursive(target: Any, source: Dict[str, Any], path: str = "") -> None:
            """Recursively apply changes to nested structures"""
            for key, new_value in source.items():
                current_path = f"{path}.{key}" if path else key
                
                if key not in target:
                    # New key - add it
                    target[key] = new_value
                    logger.debug(f"Added new key: {current_path}")
                    continue
                    
                current_value = target[key]
                
                if isinstance(new_value, dict) and isinstance(current_value, dict):
                    # Nested dictionary - recurse
                    _apply_recursive(current_value, new_value, current_path)
                elif new_value != current_value:
                    # Value changed - update it
                    target[key] = new_value
                    logger.debug(f"Updated {current_path}: {current_value} -> {new_value}")
                # else: Value unchanged, preserve as-is with comments
                    
        _apply_recursive(doc, new_state)
        logger.debug("Successfully applied changes to TOMLDocument")
        
    except Exception as e:
        logger.error(f"Failed to apply changes to TOMLDocument: {e}")
        raise TomlRoundTripError(f"Failed to apply changes: {e}") from e


async def save_doc(doc: TOMLDocument, path: Union[Path, str], create_backup: bool = True) -> Optional[Path]:
    """
    Save TOMLDocument to file with all formatting preserved.
    
    Args:
        doc: TOMLDocument with comments and formatting
        path: Target file path
        create_backup: Whether to create timestamped backup before saving
        
    Returns:
        Path to backup file if created, None otherwise
        
    Raises:
        TomlRoundTripError: If file cannot be saved
    """
    try:
        path = Path(path)
        backup_path = None
        
        # Create backup if requested and file exists
        if create_backup and path.exists():
            backup_path = await _create_backup(path)
            
        # Convert document to string
        content = tomlkit.dumps(doc)
        
        # Write file asynchronously
        await asyncio.to_thread(path.write_text, content, encoding='utf-8')
        
        logger.info(f"Saved TOML with comments to: {path}")
        if backup_path:
            logger.info(f"Created backup: {backup_path}")
            
        return backup_path
        
    except Exception as e:
        logger.error(f"Failed to save TOMLDocument to {path}: {e}")
        raise TomlRoundTripError(f"Failed to save TOML file: {e}") from e


async def validate_toml_with_pydantic(doc: TOMLDocument) -> Dict[str, Any]:
    """
    Validate TOMLDocument against Pydantic CoreConfig model.
    
    Converts the document to a plain dict and validates it using
    the existing Pydantic models to ensure configuration integrity.
    
    Args:
        doc: TOMLDocument to validate
        
    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "data": dict | None,
            "errors": list | None
        }
    """
    try:
        # Convert to plain dict for Pydantic validation
        plain_dict = doc_to_plain_dict(doc)
        
        # Validate with CoreConfig Pydantic model
        try:
            config = CoreConfig(**plain_dict)
            return {
                "valid": True,
                "data": config.model_dump(),
                "errors": None
            }
        except ValidationError as e:
            return {
                "valid": False,
                "data": None,
                "errors": [
                    {
                        "loc": error["loc"],
                        "msg": error["msg"],
                        "type": error["type"]
                    }
                    for error in e.errors()
                ]
            }
            
    except Exception as e:
        logger.error(f"Failed to validate TOMLDocument: {e}")
        return {
            "valid": False,
            "data": None,
            "errors": [{"msg": f"Validation error: {e}", "type": "validation_error"}]
        }


async def _create_backup(original_path: Path) -> Path:
    """
    Create timestamped backup of configuration file.
    
    Args:
        original_path: Path to original configuration file
        
    Returns:
        Path to created backup file
        
    Raises:
        TomlRoundTripError: If backup cannot be created
    """
    try:
        # Create backups directory if it doesn't exist
        backups_dir = original_path.parent / "backups"
        await asyncio.to_thread(backups_dir.mkdir, parents=True, exist_ok=True)
        
        # Generate timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{original_path.stem}_backup_{timestamp}{original_path.suffix}"
        backup_path = backups_dir / backup_filename
        
        # Copy file with metadata preservation
        await asyncio.to_thread(shutil.copy2, original_path, backup_path)
        
        return backup_path
        
    except Exception as e:
        logger.error(f"Failed to create backup of {original_path}: {e}")
        raise TomlRoundTripError(f"Failed to create backup: {e}") from e


# Utility functions for integration testing

async def test_round_trip_fidelity(config_path: Union[Path, str]) -> Dict[str, Any]:
    """
    Test round-trip fidelity for TOML comment preservation.
    
    Loads a TOML file, converts to dict, applies a simple change,
    and verifies that all comments are preserved exactly.
    
    Args:
        config_path: Path to configuration file to test
        
    Returns:
        Test results dictionary with fidelity metrics
    """
    try:
        config_path = Path(config_path)
        
        # Load original content for comparison
        original_content = await asyncio.to_thread(config_path.read_text, encoding='utf-8')
        
        # Load with tomlkit
        doc = await load_toml_with_comments(config_path)
        
        # Convert to plain dict and back
        plain_dict = doc_to_plain_dict(doc)
        
        # Make a simple change (toggle debug if it exists)
        if 'debug' in plain_dict:
            plain_dict['debug'] = not plain_dict['debug']
        else:
            plain_dict['debug'] = True
            
        # Apply changes
        apply_changes(doc, plain_dict)
        
        # Convert back to string
        result_content = tomlkit.dumps(doc)
        
        # Analyze fidelity
        original_lines = original_content.splitlines()
        result_lines = result_content.splitlines()
        
        comment_lines_original = [line for line in original_lines if line.strip().startswith('#')]
        comment_lines_result = [line for line in result_lines if line.strip().startswith('#')]
        
        return {
            "success": True,
            "original_comments": len(comment_lines_original),
            "preserved_comments": len(comment_lines_result),
            "comment_preservation_rate": len(comment_lines_result) / max(len(comment_lines_original), 1),
            "total_lines_original": len(original_lines),
            "total_lines_result": len(result_lines),
            "comments_preserved": comment_lines_original == comment_lines_result
        }
        
    except Exception as e:
        logger.error(f"Round-trip fidelity test failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }

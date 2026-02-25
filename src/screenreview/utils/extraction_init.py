# -*- coding: utf-8 -*-
"""Initialize and validate extraction directory structure."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExtractionInitializer:
    """Ensure extraction directories and files exist."""

    # Required directories (relative paths, no leading dot)
    REQUIRED_DIRS = [
        "frames",
        "gesture_regions",
    ]

    # Required files with default content
    REQUIRED_FILES = {
        "analysis.json": {
            "status": "pending",
            "frames_extracted": 0,
            "gestures_detected": 0,
            "ocr_processed": 0,
            "triggers_detected": [],
            "timestamp_created": None,
        }
    }

    @staticmethod
    def ensure_structure(extraction_dir: Path | str) -> bool:
        """
        Ensure all required directories and files exist in extraction directory.
        
        Creates missing directories and initializes missing JSON files with defaults.
        
        Args:
            extraction_dir: Path to the extraction directory
            
        Returns:
            True if structure is valid/created, False if failed
        """
        extraction_dir = Path(extraction_dir) if isinstance(extraction_dir, str) else extraction_dir
        
        try:
            # Create all required directories
            for rel_path in ExtractionInitializer.REQUIRED_DIRS:
                dir_path = extraction_dir / rel_path
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {dir_path}")
            
            # Initialize all required files with defaults
            for rel_path, default_content in ExtractionInitializer.REQUIRED_FILES.items():
                file_path = extraction_dir / rel_path
                
                # Only create if doesn't exist or is empty
                if not file_path.exists():
                    content = default_content.copy() if isinstance(default_content, dict) else default_content
                    
                    if isinstance(content, dict):
                        # Add timestamp
                        if "timestamp_created" in content:
                            from datetime import datetime
                            content["timestamp_created"] = datetime.utcnow().isoformat()
                        
                        file_path.write_text(
                            json.dumps(content, indent=2, ensure_ascii=False),
                            encoding="utf-8"
                        )
                    else:
                        file_path.write_text(str(content), encoding="utf-8")
                    
                    logger.info(f"Created initial file: {file_path}")
                elif file_path.stat().st_size == 0:
                    # Re-initialize if empty
                    content = default_content.copy() if isinstance(default_content, dict) else default_content
                    
                    if isinstance(content, dict):
                        from datetime import datetime
                        if "timestamp_created" in content:
                            content["timestamp_created"] = datetime.utcnow().isoformat()
                        
                        file_path.write_text(
                            json.dumps(content, indent=2, ensure_ascii=False),
                            encoding="utf-8"
                        )
                    else:
                        file_path.write_text(str(content), encoding="utf-8")
                    
                    logger.info(f"Re-initialized empty file: {file_path}")
            
            logger.info(f"✓ Extraction structure initialized: {extraction_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize extraction structure: {e}")
            return False

    @staticmethod
    def validate_structure(extraction_dir: Path | str) -> dict[str, Any]:
        """
        Validate extraction directory structure and report status.
        
        Args:
            extraction_dir: Path to the extraction directory
            
        Returns:
            Dictionary with validation results
        """
        extraction_dir = Path(extraction_dir) if isinstance(extraction_dir, str) else extraction_dir
        
        status = {
            "is_valid": True,
            "extraction_dir_exists": extraction_dir.exists(),
            "directories": {},
            "files": {},
            "issues": [],
        }
        
        # Check directories
        for rel_path in ExtractionInitializer.REQUIRED_DIRS:
            dir_path = extraction_dir / rel_path
            exists = dir_path.exists()
            status["directories"][rel_path] = {
                "exists": exists,
                "path": str(dir_path),
            }
            if not exists:
                status["issues"].append(f"Missing directory: {rel_path}")
                status["is_valid"] = False
        
        # Check files
        for rel_path in ExtractionInitializer.REQUIRED_FILES.keys():
            file_path = extraction_dir / rel_path
            exists = file_path.exists()
            is_empty = exists and file_path.stat().st_size == 0
            
            status["files"][rel_path] = {
                "exists": exists,
                "is_empty": is_empty,
"path": str(file_path),
            }
            
            if not exists:
                status["issues"].append(f"Missing file: {rel_path}")
                status["is_valid"] = False
            elif is_empty:
                status["issues"].append(f"Empty file: {rel_path}")
        
        if status["is_valid"]:
            logger.info(f"✓ Extraction structure is valid: {extraction_dir}")
        else:
            logger.warning(f"✗ Extraction structure issues found: {status['issues']}")
        
        return status

    @staticmethod
    def repair_structure(extraction_dir: Path | str) -> bool:
        """
        Detect and fix issues in extraction directory structure.
        
        Args:
            extraction_dir: Path to the extraction directory
            
        Returns:
            True if repaired successfully, False if failed
        """
        extraction_dir = Path(extraction_dir) if isinstance(extraction_dir, str) else extraction_dir
        
        # Validate first
        status = ExtractionInitializer.validate_structure(extraction_dir)
        
        if status["is_valid"]:
            logger.info(f"No repairs needed: {extraction_dir}")
            return True
        
        logger.info(f"Repairing extraction structure: {extraction_dir}")
        logger.info(f"Issues found: {status['issues']}")
        
        # Re-initialize to fix all issues
        return ExtractionInitializer.ensure_structure(extraction_dir)

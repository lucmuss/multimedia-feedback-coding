# -*- coding: utf-8 -*-
"""Analyze brush tool annotations to extract UI elements."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class AnnotationAnalyzer:
    """Extract bounding boxes and content from annotation overlays."""

    def analyze_overlay(self, image_path: Path, overlay_path: Path) -> list[dict[str, Any]]:
        """Find marked regions in the overlay and crop corresponding parts of the image."""
        if not overlay_path.exists() or not image_path.exists():
            return []

        try:
            # Load overlay and find non-transparent pixels
            overlay = Image.open(overlay_path).convert("RGBA")
            ov_data = np.array(overlay)
            
            # Find pixels with alpha > 0 (marked areas)
            alpha = ov_data[:, :, 3]
            marked_coords = np.argwhere(alpha > 0)
            
            if marked_coords.size == 0:
                return []

            # We use a simple clustering to separate multiple markings.
            # Since we don't want to depend on cv2 here if not needed, 
            # we'll use a simple distance-based clustering.
            
            regions = []
            remaining_coords = marked_coords.tolist()
            # Sort by y then x to have a stable starting point
            remaining_coords.sort()
            
            while remaining_coords:
                # Start a new cluster
                current_cluster = [remaining_coords.pop(0)]
                changed = True
                
                # Expand cluster by proximity (using a bounding box check for efficiency)
                # This separates markings that are at least 50 pixels apart
                while changed:
                    changed = False
                    to_remove = []
                    for i, coord in enumerate(remaining_coords):
                        c_y, c_x = coord
                        is_close = False
                        # Optimization: check last added ones
                        for cluster_coord in current_cluster[-50:]:
                            cc_y, cc_x = cluster_coord
                            if abs(c_y - cc_y) < 50 and abs(c_x - cc_x) < 50:
                                is_close = True
                                break
                        
                        if is_close:
                            current_cluster.append(coord)
                            to_remove.append(i)
                            changed = True
                    
                    for i in reversed(to_remove):
                        remaining_coords.pop(i)

                # Process cluster into bounding box
                cluster_arr = np.array(current_cluster)
                y_min, x_min = cluster_arr.min(axis=0)
                y_max, x_max = cluster_arr.max(axis=0)
                
                padding = 15
                x_min = max(0, x_min - padding)
                y_min = max(0, y_min - padding)
                x_max = min(ov_data.shape[1], x_max + padding)
                y_max = min(ov_data.shape[0], y_max + padding)

                regions.append({
                    "bbox": {
                        "top_left": {"x": int(x_min), "y": int(y_min)},
                        "bottom_right": {"x": int(x_max), "y": int(y_max)},
                    },
                    "type": "brush_marking",
                })
            
            logger.info("AnnotationAnalyzer: Found %d markings", len(regions))
            return regions

        except Exception as e:
            logger.error("AnnotationAnalyzer failed: %s", e)
            return []

    def get_crop_path(self, image_path: Path, region: dict[str, Any], output_dir: Path, index: int) -> Path | None:
        """Save a crop of the marked region."""
        try:
            img = Image.open(image_path)
            bbox = region["bbox"]
            box = (
                bbox["top_left"]["x"],
                bbox["top_left"]["y"],
                bbox["bottom_right"]["x"],
                bbox["bottom_right"]["y"],
            )
            crop = img.crop(box)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            crop_path = output_dir / f"marked_region_{index:03d}.png"
            crop.save(crop_path)
            return crop_path
        except Exception as e:
            logger.error("AnnotationAnalyzer crop failed: %s", e)
            return None

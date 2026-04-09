"""
STL File Service for 3D Model Export
"""
import os
import random
from pathlib import Path
from typing import Optional, Tuple
from config import settings


def get_stl_file_path() -> Path:
    """Get the path to the global STL file."""
    return settings.STL_FILE_PATH


def get_stl_file_size() -> str:
    """
    Get the file size of the global STL file.
    
    Returns:
        Human-readable file size string
    """
    stl_path = get_stl_file_path()
    
    if stl_path.exists():
        size_bytes = stl_path.stat().st_size
        # Convert to MB
        size_mb = size_bytes / (1024 * 1024)
        return f"{size_mb:.1f} MB"
    
    return "0 MB"


def estimate_selection_stats(district_id: str) -> Tuple[int, str]:
    """
    Estimate the building count and file size for a district selection.
    
    In a real implementation, this would:
    1. Query a spatial database for buildings in the viewport
    2. Calculate actual mesh sizes based on LOD settings
    
    Args:
        district_id: The district identifier
        
    Returns:
        Tuple of (building_count, estimated_file_size)
    """
    # District-based estimations (simulated)
    # In production, this would query actual building data
    district_estimates = {
        "1": (120, 28.5),  # Marina Bay - High density, tall buildings
        "2": (95, 22.3),   # Orchard - Commercial district
        "3": (75, 18.7),   # Jurong West - Mixed residential
        "4": (68, 16.2),   # Tampines - HDB estates
        "5": (52, 14.8),   # Woodlands - Lower density
    }
    
    if district_id in district_estimates:
        buildings, size = district_estimates[district_id]
        # Add some randomness to simulate viewport changes
        buildings = buildings + random.randint(-10, 10)
        size = size + random.uniform(-2, 2)
    else:
        buildings = random.randint(40, 120)
        size = random.uniform(10, 35)
    
    return max(buildings, 20), f"{max(size, 5):.1f} MB"


def validate_stl_file() -> bool:
    """
    Validate that the STL file exists and is readable.
    
    Returns:
        True if file is valid, False otherwise
    """
    stl_path = get_stl_file_path()
    return stl_path.exists() and stl_path.is_file()


async def get_stl_file_info() -> dict:
    """
    Get information about the STL file.
    
    Returns:
        Dictionary with file metadata
    """
    stl_path = get_stl_file_path()
    
    if not stl_path.exists():
        return {
            "exists": False,
            "path": str(stl_path),
            "size": "0 MB",
            "filename": stl_path.name
        }
    
    stat = stl_path.stat()
    size_mb = stat.st_size / (1024 * 1024)
    
    return {
        "exists": True,
        "path": str(stl_path),
        "size": f"{size_mb:.1f} MB",
        "size_bytes": stat.st_size,
        "filename": stl_path.name,
        "modified": stat.st_mtime
    }

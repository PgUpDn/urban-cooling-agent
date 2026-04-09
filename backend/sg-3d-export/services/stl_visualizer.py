"""
STL Visualizer - Generate 2D projections for coordinate verification
"""
import numpy as np
from stl import mesh
from pathlib import Path
from typing import Optional, Tuple, List
import base64
import io

# Try to import PIL for image generation
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from config import settings


def generate_topdown_image(
    stl_path: Optional[Path] = None,
    width: int = 800,
    height: int = 600,
    mark_points: Optional[List[Tuple[float, float, str]]] = None
) -> Optional[bytes]:
    """
    Generate a top-down (XY plane) projection of the STL file.
    
    Args:
        stl_path: Path to STL file
        width: Image width
        height: Image height
        mark_points: List of (x, y, label) tuples to mark on the image
    
    Returns:
        PNG image as bytes
    """
    if not HAS_PIL:
        print("PIL not available, cannot generate image")
        return None
    
    stl_path = stl_path or settings.STL_FILE_PATH
    
    if not stl_path.exists():
        return None
    
    # Load mesh
    stl_mesh = mesh.Mesh.from_file(str(stl_path))
    
    # Get all vertices
    vertices = stl_mesh.vectors.reshape(-1, 3)
    
    # Get bounds
    min_x, max_x = np.min(vertices[:, 0]), np.max(vertices[:, 0])
    min_y, max_y = np.min(vertices[:, 1]), np.max(vertices[:, 1])
    
    # Create image
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Calculate scale
    margin = 40
    scale_x = (width - 2 * margin) / (max_x - min_x)
    scale_y = (height - 2 * margin) / (max_y - min_y)
    scale = min(scale_x, scale_y)
    
    # Offset to center
    offset_x = margin + (width - 2 * margin - (max_x - min_x) * scale) / 2
    offset_y = margin + (height - 2 * margin - (max_y - min_y) * scale) / 2
    
    def to_image_coords(x, y):
        ix = offset_x + (x - min_x) * scale
        iy = height - (offset_y + (y - min_y) * scale)  # Flip Y
        return int(ix), int(iy)
    
    # Draw triangles (simplified - just draw points for speed)
    # Sample every Nth point for performance
    sample_rate = max(1, len(vertices) // 50000)
    sampled = vertices[::sample_rate]
    
    for v in sampled:
        ix, iy = to_image_coords(v[0], v[1])
        if 0 <= ix < width and 0 <= iy < height:
            draw.point((ix, iy), fill='gray')
    
    # Draw boundary
    draw.rectangle([margin-5, margin-5, width-margin+5, height-margin+5], outline='black', width=2)
    
    # Mark points if provided
    if mark_points:
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'cyan', 'magenta', 'brown']
        for i, (x, y, label) in enumerate(mark_points):
            ix, iy = to_image_coords(x, y)
            color = colors[i % len(colors)]
            # Draw circle
            r = 8
            draw.ellipse([ix-r, iy-r, ix+r, iy+r], fill=color, outline='white', width=2)
            # Draw label
            draw.text((ix + 12, iy - 8), label, fill=color)
    
    # Add axis labels
    draw.text((width//2, height - 15), f"X: {min_x:.0f} - {max_x:.0f}", fill='black', anchor='mm')
    draw.text((10, height//2), f"Y: {min_y:.0f} - {max_y:.0f}", fill='black')
    
    # Save to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def generate_density_heatmap(
    stl_path: Optional[Path] = None,
    width: int = 800,
    height: int = 600,
    grid_size: int = 50
) -> Optional[bytes]:
    """
    Generate a density heatmap showing building concentration.
    """
    if not HAS_PIL:
        return None
    
    stl_path = stl_path or settings.STL_FILE_PATH
    
    if not stl_path.exists():
        return None
    
    # Load mesh
    stl_mesh = mesh.Mesh.from_file(str(stl_path))
    
    # Get triangle centroids
    triangles = stl_mesh.vectors
    centroids = np.mean(triangles, axis=1)
    
    # Get bounds
    min_x, max_x = np.min(centroids[:, 0]), np.max(centroids[:, 0])
    min_y, max_y = np.min(centroids[:, 1]), np.max(centroids[:, 1])
    
    # Create density grid
    density = np.zeros((grid_size, grid_size))
    
    for c in centroids:
        gx = int((c[0] - min_x) / (max_x - min_x) * (grid_size - 1))
        gy = int((c[1] - min_y) / (max_y - min_y) * (grid_size - 1))
        gx = max(0, min(grid_size - 1, gx))
        gy = max(0, min(grid_size - 1, gy))
        density[gy, gx] += 1
    
    # Normalize
    density = density / np.max(density) if np.max(density) > 0 else density
    
    # Create heatmap image
    img = Image.new('RGB', (width, height), color='white')
    
    cell_w = (width - 80) // grid_size
    cell_h = (height - 80) // grid_size
    
    for gy in range(grid_size):
        for gx in range(grid_size):
            val = density[gy, gx]
            # Color from white to red
            r = 255
            g = int(255 * (1 - val))
            b = int(255 * (1 - val))
            
            x1 = 40 + gx * cell_w
            y1 = 40 + (grid_size - 1 - gy) * cell_h  # Flip Y
            x2 = x1 + cell_w
            y2 = y1 + cell_h
            
            draw = ImageDraw.Draw(img)
            draw.rectangle([x1, y1, x2, y2], fill=(r, g, b))
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()

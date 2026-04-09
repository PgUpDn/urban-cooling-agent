"""
STL Processor Service - Handles STL file parsing, clipping, and conversion
"""
import numpy as np
from stl import mesh
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import struct
import base64
import io

from config import settings


class STLProcessor:
    """Process STL files for clipping and preview generation"""
    
    def __init__(self, stl_path: Optional[Path] = None):
        self.stl_path = stl_path or settings.STL_FILE_PATH
        self._mesh: Optional[mesh.Mesh] = None
        self._bounds: Optional[Dict[str, float]] = None
    
    def load_mesh(self) -> bool:
        """Load the STL mesh file"""
        if not self.stl_path.exists():
            return False
        
        try:
            self._mesh = mesh.Mesh.from_file(str(self.stl_path))
            self._calculate_bounds()
            return True
        except Exception as e:
            print(f"Error loading STL: {e}")
            return False
    
    def _calculate_bounds(self):
        """Calculate the bounding box of the mesh"""
        if self._mesh is None:
            return
        
        # Get all vertices
        vertices = self._mesh.vectors.reshape(-1, 3)
        
        self._bounds = {
            'min_x': float(np.min(vertices[:, 0])),
            'max_x': float(np.max(vertices[:, 0])),
            'min_y': float(np.min(vertices[:, 1])),
            'max_y': float(np.max(vertices[:, 1])),
            'min_z': float(np.min(vertices[:, 2])),
            'max_z': float(np.max(vertices[:, 2])),
        }
    
    def get_bounds(self) -> Optional[Dict[str, float]]:
        """Get mesh bounding box"""
        if self._mesh is None:
            self.load_mesh()
        return self._bounds
    
    def get_mesh_info(self) -> Dict[str, Any]:
        """Get information about the loaded mesh"""
        if self._mesh is None:
            if not self.load_mesh():
                return {"error": "Failed to load mesh"}
        
        return {
            "triangle_count": len(self._mesh.vectors),
            "vertex_count": len(self._mesh.vectors) * 3,
            "bounds": self._bounds,
            "file_size_mb": self.stl_path.stat().st_size / (1024 * 1024) if self.stl_path.exists() else 0
        }
    
    def clip_by_bounds(
        self, 
        min_x: float, max_x: float,
        min_y: float, max_y: float,
        min_z: Optional[float] = None, 
        max_z: Optional[float] = None
    ) -> Optional[mesh.Mesh]:
        """
        Clip the mesh to only include triangles within the specified bounds.
        
        Args:
            min_x, max_x: X-axis bounds
            min_y, max_y: Y-axis bounds  
            min_z, max_z: Z-axis bounds (optional)
        
        Returns:
            Clipped mesh or None if failed
        """
        if self._mesh is None:
            if not self.load_mesh():
                return None
        
        # Get all triangles
        triangles = self._mesh.vectors  # Shape: (n, 3, 3)
        
        # Calculate centroid of each triangle
        centroids = np.mean(triangles, axis=1)  # Shape: (n, 3)
        
        # Create mask for triangles within bounds
        mask = (
            (centroids[:, 0] >= min_x) & (centroids[:, 0] <= max_x) &
            (centroids[:, 1] >= min_y) & (centroids[:, 1] <= max_y)
        )
        
        if min_z is not None and max_z is not None:
            mask &= (centroids[:, 2] >= min_z) & (centroids[:, 2] <= max_z)
        
        # Filter triangles
        filtered_triangles = triangles[mask]
        
        if len(filtered_triangles) == 0:
            return None
        
        # Create new mesh from filtered triangles
        clipped_mesh = mesh.Mesh(np.zeros(len(filtered_triangles), dtype=mesh.Mesh.dtype))
        clipped_mesh.vectors = filtered_triangles
        
        return clipped_mesh
    
    def wgs84_to_local(self, lat: float, lng: float) -> Tuple[float, float]:
        """
        Convert WGS84 coordinates (lat/lng) to local STL coordinates.
        
        Uses parameters calibrated by matching STL building footprint 
        with OpenStreetMap tiles using OpenCV.
        """
        # Calibrated parameters from OpenCV map matching
        # Scale factors (STL units per degree)
        SCALE_X = 79491.5625
        SCALE_Y = 68407.5859
        
        # Offsets (calculated from centroid alignment)
        OFFSET_X = -8226234.5000
        OFFSET_Y = -77697.3594
        
        # Linear transformation: 
        # stl_x = SCALE_X * longitude + OFFSET_X
        # stl_y = SCALE_Y * latitude + OFFSET_Y
        x = SCALE_X * lng + OFFSET_X
        y = SCALE_Y * lat + OFFSET_Y
        
        return x, y
    
    def clip_by_geo_bounds(
        self,
        lat_min: float, lat_max: float,
        lng_min: float, lng_max: float,
        center_lat: float, center_lng: float
    ) -> Optional[mesh.Mesh]:
        """
        Clip mesh using geographic coordinates (WGS84).
        
        Converts lat/lng to local STL coordinates.
        """
        if self._mesh is None:
            if not self.load_mesh():
                return None
        
        if self._bounds is None:
            return None
        
        # Convert geographic bounds to local coordinates
        min_x, min_y = self.wgs84_to_local(lat_min, lng_min)
        max_x, max_y = self.wgs84_to_local(lat_max, lng_max)
        
        # Ensure min < max
        if min_x > max_x:
            min_x, max_x = max_x, min_x
        if min_y > max_y:
            min_y, max_y = max_y, min_y
        
        print(f"Clipping bounds: X({min_x:.1f}, {max_x:.1f}), Y({min_y:.1f}, {max_y:.1f})")
        print(f"STL bounds: X({self._bounds['min_x']:.1f}, {self._bounds['max_x']:.1f}), Y({self._bounds['min_y']:.1f}, {self._bounds['max_y']:.1f})")
        
        return self.clip_by_bounds(min_x, max_x, min_y, max_y)
    
    def clip_by_district(
        self,
        center_lat: float, 
        center_lng: float,
        radius_meters: float = 500
    ) -> Optional[mesh.Mesh]:
        """
        Clip mesh around a district center point with given radius.
        
        Args:
            center_lat: District center latitude
            center_lng: District center longitude  
            radius_meters: Radius in meters around the center
        """
        if self._mesh is None:
            if not self.load_mesh():
                return None
        
        if self._bounds is None:
            return None
        
        # Convert center to local coordinates
        center_x, center_y = self.wgs84_to_local(center_lat, center_lng)
        
        # Scale factors from OpenCV calibration (STL units per degree)
        SCALE_X = 79491.5625
        SCALE_Y = 68407.5859
        
        # Meters per degree at Singapore's latitude
        meters_per_deg_lng = 111320 * np.cos(np.radians(center_lat))
        meters_per_deg_lat = 111320
        
        # STL units per meter (derived from scale factors)
        stl_per_meter_x = SCALE_X / meters_per_deg_lng
        stl_per_meter_y = SCALE_Y / meters_per_deg_lat
        
        # Average scale factor
        stl_per_meter = (stl_per_meter_x + stl_per_meter_y) / 2
        
        # Convert radius
        radius_stl = radius_meters * stl_per_meter
        
        # Calculate bounds
        min_x = center_x - radius_stl
        max_x = center_x + radius_stl
        min_y = center_y - radius_stl
        max_y = center_y + radius_stl
        
        print(f"District clip center: ({center_x:.1f}, {center_y:.1f})")
        print(f"Radius: {radius_meters}m = {radius_stl:.1f} STL units")
        print(f"Clip bounds: X({min_x:.1f}, {max_x:.1f}), Y({min_y:.1f}, {max_y:.1f})")
        print(f"STL bounds: X({self._bounds['min_x']:.1f}, {self._bounds['max_x']:.1f}), Y({self._bounds['min_y']:.1f}, {self._bounds['max_y']:.1f})")
        
        return self.clip_by_bounds(min_x, max_x, min_y, max_y)
    
    def clip_by_percentage(
        self,
        x_start: float, x_end: float,
        y_start: float, y_end: float
    ) -> Optional[mesh.Mesh]:
        """
        Clip mesh using percentage of total bounds (0.0 to 1.0).
        
        Useful for viewport-based selection.
        """
        if self._mesh is None:
            if not self.load_mesh():
                return None
        
        if self._bounds is None:
            return None
        
        mesh_width = self._bounds['max_x'] - self._bounds['min_x']
        mesh_height = self._bounds['max_y'] - self._bounds['min_y']
        
        min_x = self._bounds['min_x'] + mesh_width * x_start
        max_x = self._bounds['min_x'] + mesh_width * x_end
        min_y = self._bounds['min_y'] + mesh_height * y_start
        max_y = self._bounds['min_y'] + mesh_height * y_end
        
        return self.clip_by_bounds(min_x, max_x, min_y, max_y)
    
    def mesh_to_json(self, target_mesh: Optional[mesh.Mesh] = None, simplify: bool = True, max_triangles: int = 5000) -> Dict[str, Any]:
        """
        Convert mesh to JSON format for Three.js rendering.
        
        Returns vertices, normals, and indices for BufferGeometry.
        """
        m = target_mesh if target_mesh is not None else self._mesh
        
        if m is None:
            return {"error": "No mesh loaded"}
        
        triangles = m.vectors
        
        # Simplify if too many triangles (for preview)
        if simplify and len(triangles) > max_triangles:
            # Simple decimation: take every nth triangle
            step = len(triangles) // max_triangles
            triangles = triangles[::step]
        
        # Flatten vertices
        vertices = triangles.reshape(-1, 3)
        
        # Calculate normals for each triangle
        v0 = triangles[:, 0]
        v1 = triangles[:, 1]
        v2 = triangles[:, 2]
        
        edge1 = v1 - v0
        edge2 = v2 - v0
        normals = np.cross(edge1, edge2)
        # Normalize
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normals = normals / norms
        
        # Repeat normal for each vertex of triangle
        normals = np.repeat(normals, 3, axis=0)
        
        # Center the mesh for preview
        center = np.mean(vertices, axis=0)
        vertices = vertices - center
        
        # Scale to fit in a unit cube
        max_extent = np.max(np.abs(vertices))
        if max_extent > 0:
            vertices = vertices / max_extent * 0.8
        
        return {
            "vertices": vertices.flatten().tolist(),
            "normals": normals.flatten().tolist(),
            "triangleCount": len(triangles),
            "originalTriangles": len(m.vectors),
            "center": center.tolist(),
            "scale": float(max_extent) if max_extent > 0 else 1.0
        }
    
    def mesh_to_binary_stl(self, target_mesh: Optional[mesh.Mesh] = None) -> bytes:
        """Convert mesh to binary STL format"""
        m = target_mesh if target_mesh is not None else self._mesh
        
        if m is None:
            return b''
        
        # Create binary STL
        buffer = io.BytesIO()
        
        # Header (80 bytes) - must be exactly 80 bytes
        header_text = b'Binary STL exported from SG 3D Export'
        header = header_text + b'\0' * (80 - len(header_text))
        buffer.write(header)
        
        # Number of triangles
        buffer.write(struct.pack('<I', len(m.vectors)))
        
        # Write each triangle
        for i, triangle in enumerate(m.vectors):
            # Calculate normal
            v0, v1, v2 = triangle
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            norm = np.linalg.norm(normal)
            if norm > 0:
                normal = normal / norm
            
            # Write normal
            buffer.write(struct.pack('<3f', *normal))
            
            # Write vertices
            for vertex in triangle:
                buffer.write(struct.pack('<3f', *vertex))
            
            # Attribute byte count (unused)
            buffer.write(struct.pack('<H', 0))
        
        return buffer.getvalue()


# Singleton instance
_processor: Optional[STLProcessor] = None


def get_processor() -> STLProcessor:
    """Get or create the STL processor singleton"""
    global _processor
    if _processor is None:
        _processor = STLProcessor()
    return _processor

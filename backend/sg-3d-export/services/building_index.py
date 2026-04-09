"""
Building Index Service - Index and query individual building STL files
Uses CSV file for accurate lat/lon coordinates
"""
import os
import csv
import math
import struct
import io
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class Building:
    """Represents a single building with its location"""
    way_code: str  # filename without .stl
    lat: float  # WGS84 latitude
    lon: float  # WGS84 longitude
    blender_x: float
    blender_y: float
    height_m: float
    file_path: Path


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance in meters between two points 
    on the earth (specified in decimal degrees).
    """
    R = 6371000  # Radius of earth in meters
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


class BuildingIndex:
    """Index and query building STL files using CSV data"""
    
    def __init__(self, buildings_dir: Path, csv_path: Path):
        self.buildings_dir = buildings_dir
        self.csv_path = csv_path
        self.buildings: List[Building] = []
        self._indexed = False
    
    def _parse_height_from_filename(self, way_code: str) -> float:
        """
        Parse the Z (height) value from the filename.
        Filename format: building_000001_X_10141.59_Y_-6098.70_Z_66.93
        The Z value represents the building height.
        """
        import re
        match = re.search(r'_Z_([-\d.]+)', way_code)
        if match:
            return float(match.group(1))
        return 10.0  # Default height if not found
    
    def build_index(self) -> int:
        """
        Load building index from CSV file.
        
        Returns the number of buildings indexed.
        """
        if not self.csv_path.exists():
            print(f"CSV file not found: {self.csv_path}")
            return 0
        
        if not self.buildings_dir.exists():
            print(f"Buildings directory not found: {self.buildings_dir}")
            return 0
        
        self.buildings = []
        
        with open(self.csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                way_code = row['way_code']
                file_path = self.buildings_dir / f"{way_code}.stl"
                
                # Only add if file exists
                if file_path.exists():
                    # Parse height from filename (Z value), not from CSV
                    height = self._parse_height_from_filename(way_code)
                    
                    building = Building(
                        way_code=way_code,
                        lat=float(row['lat']),
                        lon=float(row['lon']),
                        blender_x=float(row['blender_x']),
                        blender_y=float(row['blender_y']),
                        height_m=height,
                        file_path=file_path
                    )
                    self.buildings.append(building)
        
        self._indexed = True
        print(f"Indexed {len(self.buildings)} buildings")
        
        # Print some stats
        if self.buildings:
            lats = [b.lat for b in self.buildings]
            lons = [b.lon for b in self.buildings]
            print(f"Lat range: {min(lats):.6f} to {max(lats):.6f}")
            print(f"Lon range: {min(lons):.6f} to {max(lons):.6f}")
        
        return len(self.buildings)
    
    def ensure_indexed(self):
        """Make sure the index is built"""
        if not self._indexed:
            self.build_index()
    
    def find_buildings_in_radius(
        self, 
        center_lat: float, 
        center_lon: float, 
        radius_meters: float
    ) -> List[Building]:
        """
        Find all buildings within a given radius of a center point.
        
        Args:
            center_lat: Center latitude
            center_lon: Center longitude
            radius_meters: Search radius in meters
            
        Returns:
            List of Building objects within the radius
        """
        self.ensure_indexed()
        
        results = []
        for building in self.buildings:
            distance = haversine_distance(center_lat, center_lon, building.lat, building.lon)
            if distance <= radius_meters:
                results.append(building)
        
        return results
    
    def find_buildings_in_bounds(
        self,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float
    ) -> List[Building]:
        """
        Find all buildings within rectangular bounds.
        """
        self.ensure_indexed()
        
        results = []
        for building in self.buildings:
            if (lat_min <= building.lat <= lat_max and 
                lon_min <= building.lon <= lon_max):
                results.append(building)
        
        return results
    
    def merge_buildings_to_stl(self, buildings: List[Building]) -> bytes:
        """
        Merge multiple building STL files into a single binary STL.
        """
        if not buildings:
            return b''
        
        all_triangles = []
        
        for building in buildings:
            try:
                triangles = self._read_stl_triangles(building.file_path)
                all_triangles.extend(triangles)
            except Exception as e:
                print(f"Error reading {building.way_code}: {e}")
                continue
        
        if not all_triangles:
            return b''
        
        return self._write_binary_stl(all_triangles)
    
    def _read_stl_triangles(self, stl_path: Path) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Read triangles from an STL file (binary or ASCII).
        """
        with open(stl_path, 'rb') as f:
            header = f.read(80)
            
            # Check if it's ASCII STL
            f.seek(0)
            first_line = f.read(5)
            f.seek(0)
            
            if first_line == b'solid':
                # Could be ASCII, try to parse
                content = f.read().decode('utf-8', errors='ignore')
                if 'facet normal' in content:
                    return self._parse_ascii_stl(content)
            
            # Binary STL
            f.seek(80)
            num_triangles = struct.unpack('<I', f.read(4))[0]
            
            triangles = []
            for _ in range(num_triangles):
                data = f.read(50)
                if len(data) < 50:
                    break
                    
                normal = struct.unpack('<3f', data[0:12])
                v1 = struct.unpack('<3f', data[12:24])
                v2 = struct.unpack('<3f', data[24:36])
                v3 = struct.unpack('<3f', data[36:48])
                
                triangles.append((
                    np.array(normal),
                    np.array([v1, v2, v3])
                ))
            
            return triangles
    
    def _parse_ascii_stl(self, content: str) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Parse ASCII STL content"""
        import re
        triangles = []
        
        facet_pattern = re.compile(
            r'facet\s+normal\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+'
            r'outer\s+loop\s+'
            r'vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+'
            r'vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+'
            r'vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+'
            r'endloop\s+endfacet',
            re.IGNORECASE
        )
        
        for match in facet_pattern.finditer(content):
            normal = np.array([float(match.group(1)), float(match.group(2)), float(match.group(3))])
            v1 = np.array([float(match.group(4)), float(match.group(5)), float(match.group(6))])
            v2 = np.array([float(match.group(7)), float(match.group(8)), float(match.group(9))])
            v3 = np.array([float(match.group(10)), float(match.group(11)), float(match.group(12))])
            
            triangles.append((normal, np.array([v1, v2, v3])))
        
        return triangles
    
    def _write_binary_stl(self, triangles: List[Tuple[np.ndarray, np.ndarray]]) -> bytes:
        """Write triangles to binary STL format"""
        buffer = io.BytesIO()
        
        # Header (80 bytes)
        header = b'Binary STL - SG Buildings Export'
        header = header + b'\0' * (80 - len(header))
        buffer.write(header)
        
        # Number of triangles
        buffer.write(struct.pack('<I', len(triangles)))
        
        # Write each triangle
        for normal, vertices in triangles:
            buffer.write(struct.pack('<3f', *normal))
            for v in vertices:
                buffer.write(struct.pack('<3f', *v))
            buffer.write(struct.pack('<H', 0))
        
        return buffer.getvalue()
    
    def get_buildings_preview_data(
        self, 
        buildings: List[Building],
        max_triangles: int = 5000
    ) -> Dict:
        """
        Get mesh preview data for Three.js rendering.
        """
        if not buildings:
            return {
                "vertices": [],
                "normals": [],
                "triangleCount": 0,
                "buildingCount": 0,
                "center": [0, 0, 0],
                "scale": 1.0
            }
        
        all_triangles = []
        
        for building in buildings:
            try:
                triangles = self._read_stl_triangles(building.file_path)
                all_triangles.extend(triangles)
            except Exception as e:
                continue
        
        if not all_triangles:
            return {
                "vertices": [],
                "normals": [],
                "triangleCount": 0,
                "buildingCount": len(buildings),
                "center": [0, 0, 0],
                "scale": 1.0
            }
        
        # Simplify if needed
        if len(all_triangles) > max_triangles:
            step = len(all_triangles) // max_triangles
            all_triangles = all_triangles[::step]
        
        # Convert to arrays
        vertices = []
        normals = []
        
        for normal, verts in all_triangles:
            for v in verts:
                vertices.extend(v.tolist())
                normals.extend(normal.tolist())
        
        vertices = np.array(vertices).reshape(-1, 3)
        
        # Center the mesh
        center = np.mean(vertices, axis=0)
        vertices = vertices - center
        
        # Scale to fit
        max_extent = np.max(np.abs(vertices))
        if max_extent > 0:
            vertices = vertices / max_extent * 0.8
        
        return {
            "vertices": vertices.flatten().tolist(),
            "normals": normals,
            "triangleCount": len(all_triangles),
            "buildingCount": len(buildings),
            "center": center.tolist(),
            "scale": float(max_extent) if max_extent > 0 else 1.0
        }
    
    def get_stats(self) -> Dict:
        """Get index statistics"""
        self.ensure_indexed()
        
        if not self.buildings:
            return {"total_buildings": 0}
        
        lats = [b.lat for b in self.buildings]
        lons = [b.lon for b in self.buildings]
        
        return {
            "total_buildings": len(self.buildings),
            "lat_range": [min(lats), max(lats)],
            "lon_range": [min(lons), max(lons)],
            "center": [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]
        }


# Singleton instance
_building_index: Optional[BuildingIndex] = None


def get_building_index() -> BuildingIndex:
    """Get or create the building index singleton"""
    global _building_index
    if _building_index is None:
        buildings_dir = Path("/home/ubuntu/sg-3d-export/exported_stls_blender_coords")
        csv_path = Path("/home/ubuntu/sg-3d-export/building_data_final.csv")
        _building_index = BuildingIndex(buildings_dir, csv_path)
    return _building_index

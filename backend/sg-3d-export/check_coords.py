#!/usr/bin/env python3
"""Check STL coordinate system and calibrate mapping"""
import numpy as np
from stl import mesh
import math

# Load STL
print("Loading STL file...")
stl_mesh = mesh.Mesh.from_file('../sg-building-binary.stl')
vertices = stl_mesh.vectors.reshape(-1, 3)

min_x, max_x = np.min(vertices[:, 0]), np.max(vertices[:, 0])
min_y, max_y = np.min(vertices[:, 1]), np.max(vertices[:, 1])
min_z, max_z = np.min(vertices[:, 2]), np.max(vertices[:, 2])

print("\n=== STL Bounds ===")
print(f"  X: {min_x:.1f} to {max_x:.1f} (range: {max_x - min_x:.1f})")
print(f"  Y: {min_y:.1f} to {max_y:.1f} (range: {max_y - min_y:.1f})")
print(f"  Z: {min_z:.1f} to {max_z:.1f} (range: {max_z - min_z:.1f})")

# SVY21 to WGS84 conversion (reverse)
def svy21_to_wgs84(easting, northing):
    """Convert SVY21 coordinates to WGS84 lat/lng"""
    # SVY21 parameters
    a = 6378137.0
    f = 1 / 298.257223563
    
    # SVY21 origin
    lat0 = math.radians(1.366666666666667)  # 1°22'N
    lng0 = math.radians(103.833333333333333)  # 103°50'E
    
    # False origin
    N0 = 38744.572
    E0 = 28001.642
    k0 = 1.0
    
    e2 = 2 * f - f * f
    n = f / (2 - f)
    A = a / (1 + n) * (1 + n**2/4 + n**4/64)
    
    # Beta coefficients for inverse
    beta1 = n/2 - 2*n**2/3 + 37*n**3/96
    beta2 = n**2/48 + n**3/15
    beta3 = 17*n**3/480
    
    xi = (northing - N0) / (k0 * A)
    eta = (easting - E0) / (k0 * A)
    
    xi_prime = xi - beta1*math.sin(2*xi)*math.cosh(2*eta) - \
               beta2*math.sin(4*xi)*math.cosh(4*eta) - \
               beta3*math.sin(6*xi)*math.cosh(6*eta)
    eta_prime = eta - beta1*math.cos(2*xi)*math.sinh(2*eta) - \
                beta2*math.cos(4*xi)*math.sinh(4*eta) - \
                beta3*math.cos(6*xi)*math.sinh(6*eta)
    
    chi = math.asin(math.sin(xi_prime) / math.cosh(eta_prime))
    
    # Delta coefficients
    delta1 = 2*n - 2*n**2/3
    delta2 = 7*n**2/3 - 8*n**3/5
    delta3 = 56*n**3/15
    
    lat = chi + delta1*math.sin(2*chi) + delta2*math.sin(4*chi) + delta3*math.sin(6*chi)
    lng = lng0 + math.atan(math.sinh(eta_prime) / math.cos(xi_prime))
    
    return math.degrees(lat), math.degrees(lng)

print("\n=== Testing if STL uses SVY21 ===")
# Try converting corners
corners = [
    (min_x, min_y, "SW corner"),
    (max_x, min_y, "SE corner"),
    (min_x, max_y, "NW corner"),
    (max_x, max_y, "NE corner"),
    ((min_x + max_x)/2, (min_y + max_y)/2, "Center"),
]

print("\nIf STL X=Easting, Y=Northing (SVY21):")
for x, y, name in corners:
    try:
        lat, lng = svy21_to_wgs84(x, y)
        print(f"  {name}: ({x:.0f}, {y:.0f}) -> lat={lat:.4f}, lng={lng:.4f}")
    except Exception as e:
        print(f"  {name}: Error - {e}")

print("\n=== Known Singapore Locations (WGS84) ===")
known_locations = [
    ("Marina Bay Sands", 1.2847, 103.8610),
    ("Orchard Road", 1.3048, 103.8318),
    ("NUS", 1.2966, 103.7764),
    ("NTU", 1.3483, 103.6831),
    ("Changi Airport", 1.3644, 103.9915),
    ("Woodlands", 1.4382, 103.7890),
]

for name, lat, lng in known_locations:
    print(f"  {name}: lat={lat}, lng={lng}")

# Test the simple linear mapping I was using
print("\n=== Testing Linear Mapping ===")
sg_lat_min, sg_lat_max = 1.156, 1.472
sg_lng_min, sg_lng_max = 103.605, 104.044

def wgs84_to_stl_linear(lat, lng):
    x = min_x + (lng - sg_lng_min) / (sg_lng_max - sg_lng_min) * (max_x - min_x)
    y = min_y + (lat - sg_lat_min) / (sg_lat_max - sg_lat_min) * (max_y - min_y)
    return x, y

print("Linear mapping results:")
for name, lat, lng in known_locations:
    x, y = wgs84_to_stl_linear(lat, lng)
    in_bounds = min_x <= x <= max_x and min_y <= y <= max_y
    status = "✓" if in_bounds else "✗ OUT OF BOUNDS"
    print(f"  {name}: ({x:.0f}, {y:.0f}) {status}")

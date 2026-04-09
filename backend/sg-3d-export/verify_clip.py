#!/usr/bin/env python3
"""Verify clipping by generating a visualization of clipped area"""
import numpy as np
from stl import mesh
from PIL import Image, ImageDraw

# Load STL
print("Loading STL file...")
stl_mesh = mesh.Mesh.from_file('../sg-building-binary.stl')
vertices = stl_mesh.vectors.reshape(-1, 3)
triangles = stl_mesh.vectors

min_x, max_x = np.min(vertices[:, 0]), np.max(vertices[:, 0])
min_y, max_y = np.min(vertices[:, 1]), np.max(vertices[:, 1])

print(f"STL bounds: X({min_x:.1f}, {max_x:.1f}), Y({min_y:.1f}, {max_y:.1f})")

# OpenCV calibrated parameters (from map matching)
SCALE_X = 79491.5625
SCALE_Y = 68407.5859
OFFSET_X = -8226234.5000
OFFSET_Y = -77697.3594

def wgs84_to_stl(lat, lng):
    """Convert WGS84 to STL using OpenCV calibrated parameters"""
    x = SCALE_X * lng + OFFSET_X
    y = SCALE_Y * lat + OFFSET_Y
    return x, y

# Test locations (using updated Marina Bay/CBD coordinates)
locations = {
    "Marina Bay/CBD": (1.2838, 103.8515),  # Moved to Raffles Place CBD
    "One North": (1.2995, 103.7872),
    "NUS": (1.2966, 103.7764),
    "NTU": (1.3483, 103.6831),
}

# Create visualization
width, height = 1200, 900
img = Image.new('RGB', (width, height), 'white')
draw = ImageDraw.Draw(img)

margin = 50
scale_x = (width - 2 * margin) / (max_x - min_x)
scale_y = (height - 2 * margin) / (max_y - min_y)
scale = min(scale_x, scale_y)

def to_img(x, y):
    ix = margin + (x - min_x) * scale
    iy = height - margin - (y - min_y) * scale
    return int(ix), int(iy)

# Draw all triangles (sampled)
print("Drawing triangles...")
centroids = np.mean(triangles, axis=1)
sample_rate = max(1, len(centroids) // 30000)
for c in centroids[::sample_rate]:
    ix, iy = to_img(c[0], c[1])
    if 0 <= ix < width and 0 <= iy < height:
        draw.point((ix, iy), fill='lightgray')

# Draw clip regions for each location
colors = {'Marina Bay/CBD': 'red', 'One North': 'cyan', 'NUS': 'magenta', 'NTU': 'brown'}
radii = {'Marina Bay/CBD': 800, 'One North': 600, 'NUS': 1200, 'NTU': 2000}

print("\nClip regions:")
for name, (lat, lng) in locations.items():
    cx, cy = wgs84_to_stl(lat, lng)
    
    # Calculate radius in STL units using OpenCV calibrated scale
    meters_per_deg_lng = 111320 * np.cos(np.radians(lat))
    meters_per_deg_lat = 111320
    stl_per_meter_x = SCALE_X / meters_per_deg_lng
    stl_per_meter_y = SCALE_Y / meters_per_deg_lat
    stl_per_meter = (stl_per_meter_x + stl_per_meter_y) / 2
    
    radius_m = radii.get(name, 600)
    radius_stl = radius_m * stl_per_meter
    
    print(f"  {name}: center=({cx:.0f}, {cy:.0f}), radius={radius_stl:.0f} STL units")
    
    # Count triangles in region
    in_region = ((centroids[:, 0] >= cx - radius_stl) & 
                 (centroids[:, 0] <= cx + radius_stl) &
                 (centroids[:, 1] >= cy - radius_stl) & 
                 (centroids[:, 1] <= cy + radius_stl))
    count = np.sum(in_region)
    print(f"         triangles in region: {count}")
    
    # Draw clip region
    color = colors.get(name, 'blue')
    ix1, iy1 = to_img(cx - radius_stl, cy - radius_stl)
    ix2, iy2 = to_img(cx + radius_stl, cy + radius_stl)
    draw.rectangle([ix1, iy2, ix2, iy1], outline=color, width=3)
    
    # Draw center point
    icx, icy = to_img(cx, cy)
    r = 8
    draw.ellipse([icx-r, icy-r, icx+r, icy+r], fill=color, outline='white', width=2)
    draw.text((icx + 12, icy - 8), name, fill=color)

# Save
output_path = '../clip_verification.png'
img.save(output_path)
print(f"\nSaved to {output_path}")

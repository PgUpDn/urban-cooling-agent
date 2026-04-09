#!/usr/bin/env python3
"""Analyze STL to find correct WGS84 mapping"""
import numpy as np
from stl import mesh

print("Loading STL...")
stl_mesh = mesh.Mesh.from_file('../sg-building-binary.stl')
vertices = stl_mesh.vectors.reshape(-1, 3)
triangles = stl_mesh.vectors
centroids = np.mean(triangles, axis=1)

print(f"\nSTL Statistics:")
print(f"  Total triangles: {len(triangles)}")
print(f"  X range: {np.min(vertices[:,0]):.1f} to {np.max(vertices[:,0]):.1f}")
print(f"  Y range: {np.min(vertices[:,1]):.1f} to {np.max(vertices[:,1]):.1f}")
print(f"  Z range: {np.min(vertices[:,2]):.1f} to {np.max(vertices[:,2]):.1f}")

# Find building density hotspots
print("\n=== Finding Building Density Hotspots ===")

# Divide into grid
grid_size = 20
min_x, max_x = np.min(centroids[:,0]), np.max(centroids[:,0])
min_y, max_y = np.min(centroids[:,1]), np.max(centroids[:,1])

x_edges = np.linspace(min_x, max_x, grid_size + 1)
y_edges = np.linspace(min_y, max_y, grid_size + 1)

density_grid = np.zeros((grid_size, grid_size))
for i in range(grid_size):
    for j in range(grid_size):
        mask = ((centroids[:,0] >= x_edges[i]) & (centroids[:,0] < x_edges[i+1]) &
                (centroids[:,1] >= y_edges[j]) & (centroids[:,1] < y_edges[j+1]))
        density_grid[j, i] = np.sum(mask)

# Find top 5 density cells
flat_indices = np.argsort(density_grid.flatten())[::-1][:5]
print("\nTop 5 building density hotspots (STL coords):")
for rank, idx in enumerate(flat_indices, 1):
    j, i = divmod(idx, grid_size)
    center_x = (x_edges[i] + x_edges[i+1]) / 2
    center_y = (y_edges[j] + y_edges[j+1]) / 2
    count = density_grid[j, i]
    print(f"  {rank}. STL ({center_x:.0f}, {center_y:.0f}) - {int(count)} triangles")

# Current mapping parameters
print("\n=== Current WGS84 Mapping ===")
sg_lat_min, sg_lat_max = 1.156, 1.472  
sg_lng_min, sg_lng_max = 103.605, 104.044

def stl_to_wgs84(x, y):
    lng = sg_lng_min + (x - min_x) / (max_x - min_x) * (sg_lng_max - sg_lng_min)
    lat = sg_lat_min + (y - min_y) / (max_y - min_y) * (sg_lat_max - sg_lat_min)
    return lat, lng

print("\nHotspots in WGS84 (current mapping):")
for rank, idx in enumerate(flat_indices, 1):
    j, i = divmod(idx, grid_size)
    center_x = (x_edges[i] + x_edges[i+1]) / 2
    center_y = (y_edges[j] + y_edges[j+1]) / 2
    lat, lng = stl_to_wgs84(center_x, center_y)
    print(f"  {rank}. WGS84 ({lat:.4f}, {lng:.4f})")

# What we expect: CBD/Downtown should be a hotspot
print("\n=== Expected Locations ===")
print("CBD/Downtown Core: ~1.2850, 103.8520")
print("Orchard: ~1.3048, 103.8318")
print("Jurong: ~1.3400, 103.7090")

# Check what STL coords correspond to these locations
print("\n=== Testing Known Locations ===")
def wgs84_to_stl(lat, lng):
    x = min_x + (lng - sg_lng_min) / (sg_lng_max - sg_lng_min) * (max_x - min_x)
    y = min_y + (lat - sg_lat_min) / (sg_lat_max - sg_lat_min) * (max_y - min_y)
    return x, y

locations = {
    "CBD/Downtown": (1.2850, 103.8520),
    "Orchard": (1.3048, 103.8318),
    "NUS": (1.2966, 103.7764),
    "NTU": (1.3483, 103.6831),
}

for name, (lat, lng) in locations.items():
    x, y = wgs84_to_stl(lat, lng)
    # Count triangles in 800m radius (~740 STL units)
    radius = 740
    mask = ((centroids[:,0] >= x - radius) & (centroids[:,0] <= x + radius) &
            (centroids[:,1] >= y - radius) & (centroids[:,1] <= y + radius))
    count = np.sum(mask)
    print(f"  {name}: STL ({x:.0f}, {y:.0f}) -> {count} triangles")

print("\n=== Suggested Fix ===")
# Compare the highest density location with expected CBD location
highest_idx = flat_indices[0]
j, i = divmod(highest_idx, grid_size)
hotspot_x = (x_edges[i] + x_edges[i+1]) / 2
hotspot_y = (y_edges[j] + y_edges[j+1]) / 2
hotspot_lat, hotspot_lng = stl_to_wgs84(hotspot_x, hotspot_y)

# Expected CBD location
cbd_lat, cbd_lng = 1.2850, 103.8520
cbd_x, cbd_y = wgs84_to_stl(cbd_lat, cbd_lng)

print(f"Highest density at STL ({hotspot_x:.0f}, {hotspot_y:.0f}) = WGS84 ({hotspot_lat:.4f}, {hotspot_lng:.4f})")
print(f"Expected CBD at WGS84 ({cbd_lat}, {cbd_lng}) = STL ({cbd_x:.0f}, {cbd_y:.0f})")
print(f"\nOffset: STL delta_x = {hotspot_x - cbd_x:.0f}, delta_y = {hotspot_y - cbd_y:.0f}")

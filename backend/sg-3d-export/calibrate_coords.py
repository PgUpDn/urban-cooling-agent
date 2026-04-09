"""
Coordinate calibration using contour matching
"""
import numpy as np
from stl import mesh
import cv2
from PIL import Image
import os

# Load STL
print("=" * 60)
print("Step 1: Loading STL and analyzing bounds...")
print("=" * 60)

stl_path = os.path.join(os.path.dirname(__file__), '..', 'sg-building-binary.stl')
stl_mesh = mesh.Mesh.from_file(stl_path)
vectors = stl_mesh.vectors

# Get all vertices
all_points = vectors.reshape(-1, 3)
x_min, y_min, z_min = all_points.min(axis=0)
x_max, y_max, z_max = all_points.max(axis=0)

print(f"STL bounds:")
print(f"  X: {x_min:.1f} to {x_max:.1f} (range: {x_max-x_min:.1f})")
print(f"  Y: {y_min:.1f} to {y_max:.1f} (range: {y_max-y_min:.1f})")
print(f"  Z: {z_min:.1f} to {z_max:.1f}")

# Generate STL density map (higher resolution)
print("\n" + "=" * 60)
print("Step 2: Generating high-resolution density map...")
print("=" * 60)

img_size = 1024
density = np.zeros((img_size, img_size), dtype=np.float32)

# Sample centroids
centroids = vectors.mean(axis=1)
x_coords = centroids[:, 0]
y_coords = centroids[:, 1]

# Normalize to image coordinates
# Note: Y is flipped for image coordinates (origin at top-left)
px = ((x_coords - x_min) / (x_max - x_min) * (img_size - 1)).astype(int)
py = ((y_max - y_coords) / (y_max - y_min) * (img_size - 1)).astype(int)  # Flip Y

px = np.clip(px, 0, img_size - 1)
py = np.clip(py, 0, img_size - 1)

for i in range(len(px)):
    density[py[i], px[i]] += 1

# Normalize and convert
density = np.clip(density, 0, np.percentile(density[density > 0], 95))
density = (density / density.max() * 255).astype(np.uint8)

# Apply slight blur
density = cv2.GaussianBlur(density, (3, 3), 0)

# Create binary image
_, binary = cv2.threshold(density, 10, 255, cv2.THRESH_BINARY)

# Save
Image.fromarray(binary).save('stl_density.png')
print(f"Saved STL density map")

# Find contours
contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
largest_contour = max(contours, key=cv2.contourArea)
print(f"Found {len(contours)} contours, largest has {len(largest_contour)} points")

# Calculate contour centroid and bounds
M = cv2.moments(largest_contour)
if M["m00"] != 0:
    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])
    print(f"STL contour centroid (image coords): ({cx}, {cy})")

# Get bounding rect of the main landmass
x, y, w, h = cv2.boundingRect(largest_contour)
print(f"STL bounding rect: x={x}, y={y}, w={w}, h={h}")

# Convert centroid back to STL coordinates
stl_center_x = x_min + (cx / img_size) * (x_max - x_min)
stl_center_y = y_max - (cy / img_size) * (y_max - y_min)  # Flip Y back
print(f"STL contour centroid (STL coords): ({stl_center_x:.1f}, {stl_center_y:.1f})")

print("\n" + "=" * 60)
print("Step 3: Singapore reference points analysis...")
print("=" * 60)

# Known Singapore landmarks with WGS84 coordinates
# These are well-known locations that should be easy to identify
LANDMARKS = {
    "Marina Bay Sands": (1.2847, 103.8597),
    "Changi Airport": (1.3644, 103.9915),
    "Jurong Island": (1.2660, 103.6800),
    "Woodlands": (1.4370, 103.7865),
    "Singapore Center": (1.3521, 103.8198),  # Approximate geographic center
}

# Singapore geographic bounds (WGS84)
SG_LAT_MIN = 1.1500  # Southernmost
SG_LAT_MAX = 1.4700  # Northernmost  
SG_LNG_MIN = 103.6000  # Westernmost
SG_LNG_MAX = 104.0500  # Easternmost

print(f"Singapore WGS84 bounds:")
print(f"  Lat: {SG_LAT_MIN} to {SG_LAT_MAX} (range: {SG_LAT_MAX-SG_LAT_MIN:.4f})")
print(f"  Lng: {SG_LNG_MIN} to {SG_LNG_MAX} (range: {SG_LNG_MAX-SG_LNG_MIN:.4f})")

# Calculate linear mapping parameters
# STL uses SVY21 projection which is approximately linear for small areas
# We need to find: stl_x = a * lng + b, stl_y = c * lat + d

# Method: Use geographic bounds to map to STL bounds
# X (east-west) corresponds to longitude
# Y (north-south) corresponds to latitude

# Linear mapping coefficients
scale_x = (x_max - x_min) / (SG_LNG_MAX - SG_LNG_MIN)
scale_y = (y_max - y_min) / (SG_LAT_MAX - SG_LAT_MIN)

offset_x = x_min - scale_x * SG_LNG_MIN
offset_y = y_min - scale_y * SG_LAT_MIN

print(f"\nLinear mapping parameters:")
print(f"  scale_x = {scale_x:.4f} (STL units per degree longitude)")
print(f"  scale_y = {scale_y:.4f} (STL units per degree latitude)")
print(f"  offset_x = {offset_x:.4f}")
print(f"  offset_y = {offset_y:.4f}")

def wgs84_to_stl_linear(lat, lng):
    """Convert WGS84 to STL using linear mapping"""
    stl_x = scale_x * lng + offset_x
    stl_y = scale_y * lat + offset_y
    return stl_x, stl_y

print("\nTesting linear mapping on landmarks:")
for name, (lat, lng) in LANDMARKS.items():
    stl_x, stl_y = wgs84_to_stl_linear(lat, lng)
    in_bounds = (x_min <= stl_x <= x_max) and (y_min <= stl_y <= y_max)
    print(f"  {name}: ({lat:.4f}, {lng:.4f}) -> STL ({stl_x:.0f}, {stl_y:.0f}) {'✓' if in_bounds else '✗'}")

print("\n" + "=" * 60)
print("Step 4: Refined calibration using contour analysis...")  
print("=" * 60)

# Find the actual geographic extent of the STL data by analyzing the contour shape
# Singapore is roughly rectangular, elongated east-west

# The STL data appears to cover a specific area
# Let's analyze where the density is highest

# Create a more detailed analysis
row_density = density.sum(axis=1)
col_density = density.sum(axis=0)

# Find the vertical (Y) extent of significant density
row_threshold = row_density.max() * 0.1
valid_rows = np.where(row_density > row_threshold)[0]
if len(valid_rows) > 0:
    density_y_min = valid_rows[0]
    density_y_max = valid_rows[-1]
else:
    density_y_min, density_y_max = 0, img_size - 1

# Find the horizontal (X) extent of significant density
col_threshold = col_density.max() * 0.1
valid_cols = np.where(col_density > col_threshold)[0]
if len(valid_cols) > 0:
    density_x_min = valid_cols[0]
    density_x_max = valid_cols[-1]
else:
    density_x_min, density_x_max = 0, img_size - 1

print(f"Density extent in image coords:")
print(f"  X: {density_x_min} to {density_x_max}")
print(f"  Y: {density_y_min} to {density_y_max}")

# Convert back to STL coordinates
actual_stl_x_min = x_min + (density_x_min / img_size) * (x_max - x_min)
actual_stl_x_max = x_min + (density_x_max / img_size) * (x_max - x_min)
actual_stl_y_min = y_max - (density_y_max / img_size) * (y_max - y_min)  # Flip Y
actual_stl_y_max = y_max - (density_y_min / img_size) * (y_max - y_min)  # Flip Y

print(f"Actual STL extent (where buildings exist):")
print(f"  X: {actual_stl_x_min:.1f} to {actual_stl_x_max:.1f}")
print(f"  Y: {actual_stl_y_min:.1f} to {actual_stl_y_max:.1f}")

# Refined mapping using actual data extent
# Assume the actual data covers Singapore's built-up area
# Singapore built-up area roughly: lat 1.22-1.45, lng 103.62-104.02
ACTUAL_LAT_MIN = 1.22
ACTUAL_LAT_MAX = 1.45  
ACTUAL_LNG_MIN = 103.62
ACTUAL_LNG_MAX = 104.02

refined_scale_x = (actual_stl_x_max - actual_stl_x_min) / (ACTUAL_LNG_MAX - ACTUAL_LNG_MIN)
refined_scale_y = (actual_stl_y_max - actual_stl_y_min) / (ACTUAL_LAT_MAX - ACTUAL_LAT_MIN)

refined_offset_x = actual_stl_x_min - refined_scale_x * ACTUAL_LNG_MIN
refined_offset_y = actual_stl_y_min - refined_scale_y * ACTUAL_LAT_MIN

print(f"\nRefined mapping parameters:")
print(f"  scale_x = {refined_scale_x:.4f}")
print(f"  scale_y = {refined_scale_y:.4f}")
print(f"  offset_x = {refined_offset_x:.4f}")
print(f"  offset_y = {refined_offset_y:.4f}")

def wgs84_to_stl_refined(lat, lng):
    """Convert WGS84 to STL using refined mapping"""
    stl_x = refined_scale_x * lng + refined_offset_x
    stl_y = refined_scale_y * lat + refined_offset_y
    return stl_x, stl_y

print("\nTesting refined mapping on landmarks:")
for name, (lat, lng) in LANDMARKS.items():
    stl_x, stl_y = wgs84_to_stl_refined(lat, lng)
    in_bounds = (x_min <= stl_x <= x_max) and (y_min <= stl_y <= y_max)
    print(f"  {name}: ({lat:.4f}, {lng:.4f}) -> STL ({stl_x:.0f}, {stl_y:.0f}) {'✓' if in_bounds else '✗'}")

print("\n" + "=" * 60)
print("Step 5: Generating calibrated overlay visualization...")
print("=" * 60)

# Create visualization with landmarks marked
vis_img = cv2.cvtColor(density, cv2.COLOR_GRAY2BGR)

# Mark each landmark on the density map
for name, (lat, lng) in LANDMARKS.items():
    stl_x, stl_y = wgs84_to_stl_refined(lat, lng)
    
    # Convert STL to image coordinates
    img_x = int((stl_x - x_min) / (x_max - x_min) * img_size)
    img_y = int((y_max - stl_y) / (y_max - y_min) * img_size)  # Flip Y
    
    if 0 <= img_x < img_size and 0 <= img_y < img_size:
        cv2.circle(vis_img, (img_x, img_y), 8, (0, 255, 0), -1)
        cv2.putText(vis_img, name[:15], (img_x + 10, img_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

cv2.imwrite('calibrated_landmarks.png', vis_img)
print("Saved calibrated_landmarks.png")

print("\n" + "=" * 60)
print("FINAL RECOMMENDED PARAMETERS FOR stl_processor.py:")
print("=" * 60)
print(f"""
# In wgs84_to_local function, use these parameters:
SG_LAT_MIN = {ACTUAL_LAT_MIN}
SG_LAT_MAX = {ACTUAL_LAT_MAX}
SG_LNG_MIN = {ACTUAL_LNG_MIN}
SG_LNG_MAX = {ACTUAL_LNG_MAX}

STL_X_MIN = {actual_stl_x_min:.1f}
STL_X_MAX = {actual_stl_x_max:.1f}
STL_Y_MIN = {actual_stl_y_min:.1f}
STL_Y_MAX = {actual_stl_y_max:.1f}

def wgs84_to_local(lat, lng):
    # Linear interpolation
    norm_lng = (lng - SG_LNG_MIN) / (SG_LNG_MAX - SG_LNG_MIN)
    norm_lat = (lat - SG_LAT_MIN) / (SG_LAT_MAX - SG_LAT_MIN)
    
    local_x = STL_X_MIN + norm_lng * (STL_X_MAX - STL_X_MIN)
    local_y = STL_Y_MIN + norm_lat * (STL_Y_MAX - STL_Y_MIN)
    
    return local_x, local_y
""")

print("\n" + "=" * 60)
print("Calibration complete!")
print("=" * 60)

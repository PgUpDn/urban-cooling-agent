"""
Calibrate STL coordinates with OpenStreetMap tiles using OpenCV
Match the STL building footprint with the actual map used in frontend
"""
import numpy as np
from stl import mesh
import cv2
from PIL import Image
import requests
import io
import os
import math

# ============================================================
# Step 1: Generate STL top-down view (building footprint)
# ============================================================
print("=" * 60)
print("Step 1: Loading STL and generating building footprint...")
print("=" * 60)

stl_path = os.path.join(os.path.dirname(__file__), '..', 'sg-building-binary.stl')
stl_mesh = mesh.Mesh.from_file(stl_path)
vectors = stl_mesh.vectors

# Get bounds
all_points = vectors.reshape(-1, 3)
x_min, y_min, z_min = all_points.min(axis=0)
x_max, y_max, z_max = all_points.max(axis=0)

print(f"STL bounds: X({x_min:.1f}, {x_max:.1f}), Y({y_min:.1f}, {y_max:.1f})")

# Create high-resolution density map
img_size = 2048
density = np.zeros((img_size, img_size), dtype=np.float32)

centroids = vectors.mean(axis=1)
x_coords = centroids[:, 0]
y_coords = centroids[:, 1]

# Map to image coordinates (flip Y for image)
px = ((x_coords - x_min) / (x_max - x_min) * (img_size - 1)).astype(int)
py = ((y_max - y_coords) / (y_max - y_min) * (img_size - 1)).astype(int)

px = np.clip(px, 0, img_size - 1)
py = np.clip(py, 0, img_size - 1)

for i in range(len(px)):
    density[py[i], px[i]] += 1

# Normalize
density = np.clip(density, 0, np.percentile(density[density > 0], 98))
density = (density / density.max() * 255).astype(np.uint8)

# Apply morphological operations to get cleaner building shapes
kernel = np.ones((3, 3), np.uint8)
density = cv2.dilate(density, kernel, iterations=2)
density = cv2.GaussianBlur(density, (5, 5), 0)

stl_img = density.copy()
cv2.imwrite('../stl_footprint.png', stl_img)
print(f"Saved STL footprint ({img_size}x{img_size})")

# ============================================================
# Step 2: Download OpenStreetMap tiles (same as frontend uses)
# ============================================================
print("\n" + "=" * 60)
print("Step 2: Downloading OpenStreetMap tiles...")
print("=" * 60)

def lat_lng_to_tile(lat, lng, zoom):
    """Convert lat/lng to tile coordinates"""
    n = 2 ** zoom
    x = int((lng + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y

def tile_to_lat_lng(x, y, zoom):
    """Convert tile coordinates to lat/lng (NW corner of tile)"""
    n = 2 ** zoom
    lng = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lng

# Singapore bounds for tile download
# Match the area visible in frontend
SG_LAT_MIN = 1.15
SG_LAT_MAX = 1.50
SG_LNG_MIN = 103.55
SG_LNG_MAX = 104.10

zoom = 12  # Same zoom level as frontend default

# Get tile range
x_min_tile, y_max_tile = lat_lng_to_tile(SG_LAT_MIN, SG_LNG_MIN, zoom)
x_max_tile, y_min_tile = lat_lng_to_tile(SG_LAT_MAX, SG_LNG_MAX, zoom)

print(f"Tile range: X({x_min_tile}-{x_max_tile}), Y({y_min_tile}-{y_max_tile})")

# Download tiles and stitch
tile_size = 256
width = (x_max_tile - x_min_tile + 1) * tile_size
height = (y_max_tile - y_min_tile + 1) * tile_size

map_img = Image.new('RGB', (width, height))

# Use CartoDB dark matter style (same as frontend)
tile_url = "https://cartodb-basemaps-a.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png"

print(f"Downloading {(x_max_tile - x_min_tile + 1) * (y_max_tile - y_min_tile + 1)} tiles...")

for tx in range(x_min_tile, x_max_tile + 1):
    for ty in range(y_min_tile, y_max_tile + 1):
        url = tile_url.format(z=zoom, x=tx, y=ty)
        try:
            resp = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Calibration Script)'
            })
            if resp.status_code == 200:
                tile = Image.open(io.BytesIO(resp.content))
                px = (tx - x_min_tile) * tile_size
                py = (ty - y_min_tile) * tile_size
                map_img.paste(tile, (px, py))
        except Exception as e:
            print(f"  Failed tile ({tx},{ty}): {e}")

# Convert to grayscale numpy array
map_array = np.array(map_img.convert('L'))
cv2.imwrite('../osm_map.png', map_array)

# Calculate map bounds in lat/lng
map_lat_max, map_lng_min = tile_to_lat_lng(x_min_tile, y_min_tile, zoom)
map_lat_min, map_lng_max = tile_to_lat_lng(x_max_tile + 1, y_max_tile + 1, zoom)

print(f"Map image: {width}x{height}")
print(f"Map bounds: lat({map_lat_min:.4f}, {map_lat_max:.4f}), lng({map_lng_min:.4f}, {map_lng_max:.4f})")

# ============================================================
# Step 3: Preprocess images for matching
# ============================================================
print("\n" + "=" * 60)
print("Step 3: Preprocessing images for matching...")
print("=" * 60)

# Resize STL image to similar size as map
stl_resized = cv2.resize(stl_img, (width, height))

# Enhance map - extract building footprints from dark map
# In CartoDB dark style, buildings are slightly lighter than background
map_enhanced = cv2.adaptiveThreshold(
    map_array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, -5
)

# Invert map (buildings should be white)
map_enhanced = 255 - map_enhanced

# Clean up
kernel = np.ones((2, 2), np.uint8)
map_enhanced = cv2.morphologyEx(map_enhanced, cv2.MORPH_CLOSE, kernel)

cv2.imwrite('../map_enhanced.png', map_enhanced)
cv2.imwrite('../stl_resized.png', stl_resized)

print("Saved preprocessed images")

# ============================================================
# Step 4: Feature matching with ORB
# ============================================================
print("\n" + "=" * 60)
print("Step 4: Feature matching...")
print("=" * 60)

# Create ORB detector
orb = cv2.ORB_create(nfeatures=10000)

# Detect keypoints and compute descriptors
kp1, des1 = orb.detectAndCompute(stl_resized, None)
kp2, des2 = orb.detectAndCompute(map_enhanced, None)

print(f"STL keypoints: {len(kp1)}")
print(f"Map keypoints: {len(kp2)}")

if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
    print("Not enough keypoints for matching!")
else:
    # Match using BFMatcher
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = bf.knnMatch(des1, des2, k=2)
    
    # Apply ratio test
    good_matches = []
    for m, n in matches:
        if m.distance < 0.75 * n.distance:
            good_matches.append(m)
    
    print(f"Good matches: {len(good_matches)}")
    
    if len(good_matches) >= 4:
        # Get matched points
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        # Find homography
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        
        if H is not None:
            print(f"\nHomography matrix found!")
            print(H)
            
            # Draw matches
            match_img = cv2.drawMatches(stl_resized, kp1, map_enhanced, kp2, 
                                        good_matches[:100], None,
                                        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
            cv2.imwrite('../feature_matches_osm.png', match_img)
            print("Saved feature matches visualization")

# ============================================================
# Step 5: Alternative - Use contour-based registration
# ============================================================
print("\n" + "=" * 60)
print("Step 5: Contour-based registration...")
print("=" * 60)

# Find main landmass contour in STL
_, stl_binary = cv2.threshold(stl_resized, 20, 255, cv2.THRESH_BINARY)
stl_contours, _ = cv2.findContours(stl_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Get largest contour (Singapore main island)
stl_main = max(stl_contours, key=cv2.contourArea)
stl_hull = cv2.convexHull(stl_main)

# Get bounding rect
stl_rect = cv2.boundingRect(stl_main)
print(f"STL main contour bounding rect: {stl_rect}")

# Find contours in map
_, map_binary = cv2.threshold(map_enhanced, 30, 255, cv2.THRESH_BINARY)
map_contours, _ = cv2.findContours(map_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Get largest contours
map_contours_sorted = sorted(map_contours, key=cv2.contourArea, reverse=True)

print(f"Found {len(map_contours_sorted)} contours in map")

# Visualize contours
vis_img = np.zeros((height, width, 3), dtype=np.uint8)
cv2.drawContours(vis_img, [stl_main], -1, (0, 255, 0), 2)  # STL in green
if len(map_contours_sorted) > 0:
    cv2.drawContours(vis_img, map_contours_sorted[:5], -1, (255, 0, 0), 2)  # Map in blue

cv2.imwrite('../contour_comparison.png', vis_img)

# ============================================================
# Step 6: Manual calibration using known reference points
# ============================================================
print("\n" + "=" * 60)
print("Step 6: Reference point calibration...")
print("=" * 60)

# Since automatic matching is unreliable, use known reference points
# These are visually identifiable landmarks

# STL image coordinates (from density map analysis)
# We need to find where Singapore's distinctive features appear

# Find the centroid and extent of the main landmass in STL
M = cv2.moments(stl_main)
stl_cx = int(M['m10'] / M['m00'])
stl_cy = int(M['m01'] / M['m00'])
print(f"STL centroid (image): ({stl_cx}, {stl_cy})")

# Convert to original STL coordinates
stl_center_x = x_min + (stl_cx / width) * (x_max - x_min)
stl_center_y = y_max - (stl_cy / height) * (y_max - y_min)
print(f"STL centroid (STL coords): ({stl_center_x:.1f}, {stl_center_y:.1f})")

# Singapore's geographic center is approximately:
SG_CENTER_LAT = 1.3521
SG_CENTER_LNG = 103.8198

# Map image coordinates for Singapore center
map_center_x = int((SG_CENTER_LNG - map_lng_min) / (map_lng_max - map_lng_min) * width)
map_center_y = int((map_lat_max - SG_CENTER_LAT) / (map_lat_max - map_lat_min) * height)
print(f"Map center (image): ({map_center_x}, {map_center_y})")

# Calculate transformation: STL coords <-> Map coords <-> Lat/Lng
# 
# STL image pixel -> STL coord:
#   stl_x = x_min + (px / width) * (x_max - x_min)
#   stl_y = y_max - (py / height) * (y_max - y_min)
#
# Map image pixel -> Lat/Lng:
#   lng = map_lng_min + (px / width) * (map_lng_max - map_lng_min)
#   lat = map_lat_max - (py / height) * (map_lat_max - map_lat_min)

# So STL coord -> Lat/Lng via image coordinates:
# First find scale and offset to align the images

# Assume the STL represents Singapore with some offset
# We use the centroid alignment

# Image scale (pixels in STL image to map image)
# Both are now the same size (width x height)

# Find the offset between STL centroid and Singapore center in image coords
offset_x = map_center_x - stl_cx
offset_y = map_center_y - stl_cy
print(f"Image offset: ({offset_x}, {offset_y})")

# Create aligned visualization
aligned_vis = np.zeros((height, width, 3), dtype=np.uint8)
aligned_vis[:, :, 1] = stl_resized  # STL in green channel

# Shift map to align with STL
M_translate = np.float32([[1, 0, -offset_x], [0, 1, -offset_y]])
map_shifted = cv2.warpAffine(map_enhanced, M_translate, (width, height))
aligned_vis[:, :, 2] = map_shifted  # Shifted map in red channel

cv2.imwrite('../aligned_overlay.png', aligned_vis)
print("Saved aligned overlay (Green=STL, Red=Map)")

# ============================================================
# Step 7: Calculate final mapping parameters
# ============================================================
print("\n" + "=" * 60)
print("Step 7: Calculating mapping parameters...")
print("=" * 60)

# Method: Align STL center with Singapore center, then scale

# STL coordinate for Singapore center (using offset)
# When we shift the map by offset, the Singapore center aligns with STL centroid
# So: Singapore center (1.3521, 103.8198) corresponds to STL (stl_center_x, stl_center_y)

# Now we need the scale
# In the STL, the width represents a certain geographic distance
# We can estimate this from the bounding rect

stl_x_range = x_max - x_min
stl_y_range = y_max - y_min

# The map covers:
map_lng_range = map_lng_max - map_lng_min
map_lat_range = map_lat_max - map_lat_min

# Estimate the geographic coverage of STL
# Based on the main contour extent in the image
x_start_frac = stl_rect[0] / width
x_end_frac = (stl_rect[0] + stl_rect[2]) / width
y_start_frac = stl_rect[1] / height
y_end_frac = (stl_rect[1] + stl_rect[3]) / height

stl_data_x_min = x_min + x_start_frac * stl_x_range
stl_data_x_max = x_min + x_end_frac * stl_x_range
stl_data_y_max = y_max - y_start_frac * stl_y_range
stl_data_y_min = y_max - y_end_frac * stl_y_range

print(f"STL data extent:")
print(f"  X: {stl_data_x_min:.1f} to {stl_data_x_max:.1f}")
print(f"  Y: {stl_data_y_min:.1f} to {stl_data_y_max:.1f}")

# Singapore's built area approximately covers:
SG_DATA_LAT_MIN = 1.22
SG_DATA_LAT_MAX = 1.47
SG_DATA_LNG_MIN = 103.62
SG_DATA_LNG_MAX = 104.05

# Calculate scale factors
scale_x = (stl_data_x_max - stl_data_x_min) / (SG_DATA_LNG_MAX - SG_DATA_LNG_MIN)
scale_y = (stl_data_y_max - stl_data_y_min) / (SG_DATA_LAT_MAX - SG_DATA_LAT_MIN)

print(f"\nScale factors:")
print(f"  X: {scale_x:.2f} STL units per degree longitude")
print(f"  Y: {scale_y:.2f} STL units per degree latitude")

# Calculate offsets using centroid alignment
# STL center = (stl_center_x, stl_center_y)
# SG center = (SG_CENTER_LAT, SG_CENTER_LNG)

offset_x_final = stl_center_x - scale_x * SG_CENTER_LNG
offset_y_final = stl_center_y - scale_y * SG_CENTER_LAT

print(f"  Offset X: {offset_x_final:.2f}")
print(f"  Offset Y: {offset_y_final:.2f}")

def wgs84_to_stl(lat, lng):
    """Convert WGS84 to STL coordinates"""
    x = scale_x * lng + offset_x_final
    y = scale_y * lat + offset_y_final
    return x, y

# Test landmarks
LANDMARKS = {
    "Marina Bay Sands": (1.2847, 103.8597),
    "Changi Airport": (1.3644, 103.9915),
    "Jurong Island": (1.2660, 103.6800),
    "Woodlands": (1.4370, 103.7865),
    "NUS": (1.2966, 103.7764),
    "NTU": (1.3483, 103.6831),
    "Singapore Center": (1.3521, 103.8198),
}

print("\nLandmark test:")
for name, (lat, lng) in LANDMARKS.items():
    stl_x, stl_y = wgs84_to_stl(lat, lng)
    in_bounds = (x_min <= stl_x <= x_max) and (y_min <= stl_y <= y_max)
    print(f"  {name}: ({lat:.4f}, {lng:.4f}) -> STL ({stl_x:.0f}, {stl_y:.0f}) {'✓' if in_bounds else '✗'}")

# ============================================================
# Step 8: Output final parameters
# ============================================================
print("\n" + "=" * 60)
print("FINAL MAPPING PARAMETERS:")
print("=" * 60)

print(f"""
# Add to stl_processor.py wgs84_to_local function:

# Scale factors (STL units per degree)
SCALE_X = {scale_x:.4f}
SCALE_Y = {scale_y:.4f}

# Offsets
OFFSET_X = {offset_x_final:.4f}
OFFSET_Y = {offset_y_final:.4f}

def wgs84_to_local(lat, lng):
    x = SCALE_X * lng + OFFSET_X
    y = SCALE_Y * lat + OFFSET_Y
    return x, y
""")

# Save parameters to file
with open('../calibration_params.txt', 'w') as f:
    f.write(f"SCALE_X = {scale_x:.4f}\n")
    f.write(f"SCALE_Y = {scale_y:.4f}\n")
    f.write(f"OFFSET_X = {offset_x_final:.4f}\n")
    f.write(f"OFFSET_Y = {offset_y_final:.4f}\n")

print("\nCalibration complete! Check the output images to verify alignment.")

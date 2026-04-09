"""
SG 3D Export Professional - Backend API

FastAPI backend for Singapore 3D building model export system.
Provides APIs for:
- District information and statistics
- AI-powered urban insights (Gemini)
- STL file export and download
"""
import asyncio
import uuid
import io
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import aiofiles

from config import settings
from models import (
    District, 
    SelectionStats, 
    SelectionStatus,
    UrbanInsightResponse,
    ExportJobStatus,
    SINGAPORE_DISTRICTS
)
from services.gemini_service import get_urban_insight, get_building_analysis
from services.stl_service import (
    get_stl_file_path, 
    get_stl_file_size, 
    estimate_selection_stats,
    validate_stl_file,
    get_stl_file_info
)
from services.stl_processor import get_processor, STLProcessor
from services.stl_visualizer import generate_topdown_image, generate_density_heatmap
from services.building_index import get_building_index, BuildingIndex


# Initialize FastAPI app
app = FastAPI(
    title="SG 3D Export API",
    description="Backend API for Singapore 3D Building Model Export System",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure CORS
# Simple approach: allow all origins for production
# This is safe for read-only APIs or when authentication is handled separately
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage (use Redis in production)
export_jobs: dict[str, ExportJobStatus] = {}


# ============================================
# Startup Event - Preload mesh for faster responses
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize building index on startup."""
    print("🚀 Starting SG 3D Export API...")
    try:
        # Initialize building index (primary method)
        building_index = get_building_index()
        count = building_index.build_index()
        print(f"✅ Building index ready: {count:,} buildings")
        
        stats = building_index.get_stats()
        if stats.get("lat_range"):
            print(f"   Lat range: {stats['lat_range'][0]:.6f} to {stats['lat_range'][1]:.6f}")
            print(f"   Lon range: {stats['lon_range'][0]:.6f} to {stats['lon_range'][1]:.6f}")
    except Exception as e:
        print(f"❌ Error during startup: {e}")
        import traceback
        traceback.print_exc()


# ============================================
# Health Check
# ============================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    stl_info = await get_stl_file_info()
    return {
        "status": "healthy",
        "service": "SG 3D Export API",
        "version": "2.0.0",
        "stl_file": stl_info
    }


# ============================================
# 3D Explorer API - All Buildings
# ============================================

@app.get("/api/buildings/all")
async def get_all_buildings(
    limit: Optional[int] = Query(None, description="Limit number of buildings returned"),
    lat_min: Optional[float] = Query(None, description="Min latitude"),
    lat_max: Optional[float] = Query(None, description="Max latitude"),
    lon_min: Optional[float] = Query(None, description="Min longitude"),
    lon_max: Optional[float] = Query(None, description="Max longitude")
):
    """
    Get all building data for 3D visualization.
    
    Returns lat, lon, and height for each building.
    Can filter by bounds for viewport-based loading.
    """
    building_index = get_building_index()
    building_index.ensure_indexed()
    
    buildings = building_index.buildings
    
    # Filter by bounds if provided
    if all([lat_min, lat_max, lon_min, lon_max]):
        buildings = [b for b in buildings 
                    if lat_min <= b.lat <= lat_max and lon_min <= b.lon <= lon_max]
    
    # Apply limit if provided
    if limit and len(buildings) > limit:
        # Sample evenly
        step = len(buildings) // limit
        buildings = buildings[::step][:limit]
    
    return {
        "count": len(buildings),
        "buildings": [
            {
                "lat": b.lat,
                "lon": b.lon,
                "height": b.height_m,
                "id": b.way_code
            }
            for b in buildings
        ]
    }


@app.get("/api/buildings/geojson")
async def get_buildings_geojson(
    limit: Optional[int] = Query(50000, description="Limit number of buildings"),
    lat_min: Optional[float] = Query(None),
    lat_max: Optional[float] = Query(None),
    lon_min: Optional[float] = Query(None),
    lon_max: Optional[float] = Query(None)
):
    """
    Get buildings as GeoJSON for deck.gl visualization.
    """
    building_index = get_building_index()
    building_index.ensure_indexed()
    
    buildings = building_index.buildings
    
    # Filter by bounds if provided
    if all([lat_min, lat_max, lon_min, lon_max]):
        buildings = [b for b in buildings 
                    if lat_min <= b.lat <= lat_max and lon_min <= b.lon <= lon_max]
    
    # Apply limit
    if limit and len(buildings) > limit:
        step = len(buildings) // limit
        buildings = buildings[::step][:limit]
    
    features = []
    for b in buildings:
        # Create a small polygon for each building (approximate footprint)
        # Using ~10m offset for building size
        offset = 0.00005  # roughly 5m
        features.append({
            "type": "Feature",
            "properties": {
                "height": b.height_m,  # Height from Z value in filename (meters)
                "id": b.way_code
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [b.lon - offset, b.lat - offset],
                    [b.lon + offset, b.lat - offset],
                    [b.lon + offset, b.lat + offset],
                    [b.lon - offset, b.lat + offset],
                    [b.lon - offset, b.lat - offset]
                ]]
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


# ============================================
# District APIs
# ============================================

@app.get("/api/districts", response_model=list[District])
async def get_districts():
    """
    Get all available Singapore districts.
    
    Returns a list of districts with their coordinates and region information.
    """
    return SINGAPORE_DISTRICTS


@app.get("/api/districts/{district_id}", response_model=District)
async def get_district(district_id: str):
    """
    Get a specific district by ID.
    
    Args:
        district_id: The district identifier (1-5)
    """
    district = next((d for d in SINGAPORE_DISTRICTS if d.id == district_id), None)
    if not district:
        raise HTTPException(status_code=404, detail=f"District {district_id} not found")
    return district


@app.get("/api/districts/{district_id}/stats", response_model=SelectionStats)
async def get_district_stats(district_id: str):
    """
    Get selection statistics for a district using building index.
    
    Returns actual building count based on indexed buildings.
    
    Args:
        district_id: The district identifier
    """
    # Validate district exists
    district = next((d for d in SINGAPORE_DISTRICTS if d.id == district_id), None)
    if not district:
        raise HTTPException(status_code=404, detail=f"District {district_id} not found")
    
    # Use default radius for the district
    radius = DISTRICT_RADIUS.get(district_id, 600)
    
    # Calculate rectangular bounds (matches frontend)
    bounds = calculate_bounds(district.lat, district.lng, radius)
    
    # Use building index to find buildings in rectangular bounds
    building_index = get_building_index()
    buildings = building_index.find_buildings_in_bounds(
        bounds['lat_min'], bounds['lat_max'],
        bounds['lon_min'], bounds['lon_max']
    )
    
    if not buildings:
        return SelectionStats(
            buildings=0,
            file_size="0 MB",
            status=SelectionStatus.READY,
            progress=100
        )
    
    # Calculate actual statistics
    building_count = len(buildings)
    
    # Estimate file size based on building count and average size
    # Average building STL is about 1-2 KB
    estimated_size_bytes = building_count * 1500
    estimated_size_mb = estimated_size_bytes / (1024 * 1024)
    
    return SelectionStats(
        buildings=building_count,
        file_size=f"{estimated_size_mb:.1f} MB",
        status=SelectionStatus.READY,
        progress=100
    )


# ============================================
# AI Urban Insights
# ============================================

@app.get("/api/districts/{district_id}/insight", response_model=UrbanInsightResponse)
async def get_district_insight(district_id: str):
    """
    Get AI-generated urban planning insight for a district.
    
    Uses Gemini AI to provide contextual information about
    the architectural and historical significance of the area.
    
    Args:
        district_id: The district identifier
    """
    district = next((d for d in SINGAPORE_DISTRICTS if d.id == district_id), None)
    if not district:
        raise HTTPException(status_code=404, detail=f"District {district_id} not found")
    
    insight = await get_urban_insight(district.name)
    
    return UrbanInsightResponse(
        district_name=district.name,
        insight=insight
    )


@app.get("/api/insight")
async def get_insight_by_name(district_name: str = Query(..., description="Name of the district")):
    """
    Get AI-generated urban insight by district name.
    
    Alternative endpoint that accepts district name directly.
    
    Args:
        district_name: Name of the Singapore district
    """
    insight = await get_urban_insight(district_name)
    return {
        "district_name": district_name,
        "insight": insight
    }


# ============================================
# STL Export APIs
# ============================================

@app.get("/api/stl/info")
async def get_stl_info():
    """
    Get information about the available STL file.
    
    Returns metadata about the global Singapore building model.
    """
    return await get_stl_file_info()


@app.get("/api/stl/download")
async def download_stl(
    district_id: Optional[str] = Query(None, description="Optional district ID for naming")
):
    """
    Download the global STL file.
    
    Returns the sg-building-binary.stl file as a downloadable attachment.
    
    Args:
        district_id: Optional district ID for custom filename
    """
    stl_path = get_stl_file_path()
    
    if not stl_path.exists():
        raise HTTPException(
            status_code=404, 
            detail="STL file not found. Please ensure sg-building-binary.stl exists."
        )
    
    # Determine filename
    if district_id:
        district = next((d for d in SINGAPORE_DISTRICTS if d.id == district_id), None)
        if district:
            filename = f"{district.name.replace(' ', '_')}_SG_3D.stl"
        else:
            filename = f"Singapore_3D_{district_id}.stl"
    else:
        filename = "Singapore_Building_Model.stl"
    
    return FileResponse(
        path=stl_path,
        filename=filename,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


def calculate_bounds(lat: float, lng: float, radius_meters: float):
    """
    Calculate rectangular bounds from center + radius.
    Matches frontend calculation for consistent selection.
    """
    import math
    # 1 degree latitude ≈ 111,320 meters
    # 1 degree longitude ≈ 111,320 * cos(lat) meters
    lat_offset = radius_meters / 111320
    lng_offset = radius_meters / (111320 * math.cos(math.radians(lat)))
    
    return {
        'lat_min': lat - lat_offset,
        'lat_max': lat + lat_offset,
        'lon_min': lng - lng_offset,
        'lon_max': lng + lng_offset
    }


@app.get("/api/districts/{district_id}/stl")
async def download_district_stl(district_id: str):
    """
    Download STL file for a specific district using building index.
    
    Finds all buildings within the district rectangular bounds and merges them.
    Uses rectangular selection to match frontend display.
    
    Args:
        district_id: The district identifier
    """
    district = next((d for d in SINGAPORE_DISTRICTS if d.id == district_id), None)
    if not district:
        raise HTTPException(status_code=404, detail=f"District {district_id} not found")
    
    # Get radius for district
    radius = DISTRICT_RADIUS.get(district_id, 600)
    
    # Calculate rectangular bounds (matches frontend)
    bounds = calculate_bounds(district.lat, district.lng, radius)
    
    # Use building index to find buildings in rectangular bounds
    building_index = get_building_index()
    buildings = building_index.find_buildings_in_bounds(
        bounds['lat_min'], bounds['lat_max'],
        bounds['lon_min'], bounds['lon_max']
    )
    
    print(f"District {district.name}: found {len(buildings)} buildings in bounds")
    
    if not buildings:
        raise HTTPException(status_code=404, detail=f"No buildings found in {district.name}")
    
    # Merge buildings to STL
    stl_bytes = building_index.merge_buildings_to_stl(buildings)
    
    if not stl_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate STL")
    
    filename = f"{district.name.replace(' ', '_')}_SG_3D.stl"
    
    return StreamingResponse(
        io.BytesIO(stl_bytes),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ============================================
# Export Job APIs (Async Processing)
# ============================================

async def process_export_job(job_id: str, district_id: str):
    """Background task to process export and calculate actual statistics."""
    district = next((d for d in SINGAPORE_DISTRICTS if d.id == district_id), None)
    if not district:
        if job_id in export_jobs:
            export_jobs[job_id].status = SelectionStatus.ERROR
        return
    
    processor = get_processor()
    if not processor.load_mesh():
        if job_id in export_jobs:
            export_jobs[job_id].status = SelectionStatus.ERROR
        return
    
    # Get radius for district
    radius = DISTRICT_RADIUS.get(district_id, 600)
    
    # Simulate processing progress
    for progress in [25, 50, 75]:
        await asyncio.sleep(0.3)
        if job_id in export_jobs:
            export_jobs[job_id].progress = progress
    
    # Clip the mesh
    clipped = processor.clip_by_district(district.lat, district.lng, radius)
    
    if clipped is None or len(clipped.vectors) == 0:
        # Try larger radius
        clipped = processor.clip_by_district(district.lat, district.lng, radius * 2)
    
    if job_id in export_jobs:
        if clipped is None or len(clipped.vectors) == 0:
            export_jobs[job_id].status = SelectionStatus.ERROR
            export_jobs[job_id].progress = 100
        else:
            # Calculate actual file size
            stl_bytes = processor.mesh_to_binary_stl(clipped)
            file_size_mb = len(stl_bytes) / (1024 * 1024)
            
            export_jobs[job_id].status = SelectionStatus.READY
            export_jobs[job_id].progress = 100
            export_jobs[job_id].file_size = f"{file_size_mb:.1f} MB"
            export_jobs[job_id].download_url = f"/api/stl/download?district_id={district_id}"


@app.post("/api/export/start", response_model=ExportJobStatus)
async def start_export(
    district_id: str = Query(..., description="District ID to export"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Start an export job for a district.
    
    Creates a background job to process the export and returns
    a job ID for status tracking.
    
    Args:
        district_id: The district identifier
    """
    import traceback
    
    try:
        district = next((d for d in SINGAPORE_DISTRICTS if d.id == district_id), None)
        if not district:
            raise HTTPException(status_code=404, detail=f"District {district_id} not found")
        
        job_id = str(uuid.uuid4())
        
        export_jobs[job_id] = ExportJobStatus(
            job_id=job_id,
            district_id=district_id,
            status=SelectionStatus.PROCESSING,
            progress=0
        )
        
        # Always add background task
        background_tasks.add_task(process_export_job, job_id, district_id)
        
        return export_jobs[job_id]
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in start_export: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/{job_id}", response_model=ExportJobStatus)
async def get_export_status(job_id: str):
    """
    Get the status of an export job.
    
    Args:
        job_id: The export job identifier
    """
    if job_id not in export_jobs:
        raise HTTPException(status_code=404, detail=f"Export job {job_id} not found")
    
    return export_jobs[job_id]


# ============================================
# 3D Preview & Clipping APIs
# ============================================

@app.get("/api/mesh/info")
async def get_mesh_info():
    """
    Get information about the loaded STL mesh.
    
    Returns triangle count, vertex count, and bounding box.
    """
    processor = get_processor()
    return processor.get_mesh_info()


@app.get("/api/mesh/bounds")
async def get_mesh_bounds():
    """
    Get the bounding box of the STL mesh.
    """
    processor = get_processor()
    bounds = processor.get_bounds()
    if bounds is None:
        raise HTTPException(status_code=404, detail="Could not load mesh bounds")
    return bounds


@app.get("/api/mesh/preview")
async def get_mesh_preview(
    x_start: float = Query(0.0, description="Start X percentage (0-1)"),
    x_end: float = Query(1.0, description="End X percentage (0-1)"),
    y_start: float = Query(0.0, description="Start Y percentage (0-1)"),
    y_end: float = Query(1.0, description="End Y percentage (0-1)"),
    max_triangles: int = Query(5000, description="Max triangles for preview")
):
    """
    Get a clipped mesh preview for Three.js rendering.
    
    Uses percentage-based bounds (0.0 to 1.0) to select a portion of the mesh.
    Returns vertices and normals in JSON format.
    """
    processor = get_processor()
    
    # Clip the mesh
    clipped = processor.clip_by_percentage(x_start, x_end, y_start, y_end)
    
    if clipped is None:
        # If no triangles in selection, return full mesh preview
        processor.load_mesh()
        return processor.mesh_to_json(simplify=True, max_triangles=max_triangles)
    
    return processor.mesh_to_json(clipped, simplify=True, max_triangles=max_triangles)


# Default radius for each district (in meters)
DISTRICT_RADIUS = {
    "1": 600,   # Marina Bay
    "2": 500,   # Orchard
    "3": 800,   # Jurong West
    "4": 700,   # Tampines
    "5": 800,   # Woodlands
    "6": 600,   # One North
    "7": 1200,  # NUS
    "8": 2000,  # NTU
}


@app.get("/api/mesh/preview/district/{district_id}")
async def get_district_mesh_preview(
    district_id: str,
    radius: Optional[float] = Query(None, description="Radius in meters (auto if not specified)"),
    max_triangles: int = Query(5000, description="Max triangles for preview")
):
    """
    Get mesh preview for a specific district using building index.
    
    Finds buildings within the specified radius around the district center.
    Uses correct Blender->WGS84 coordinate transformation.
    
    Default radius varies by district (e.g., NTU campus needs larger radius).
    """
    import traceback
    
    try:
        district = next((d for d in SINGAPORE_DISTRICTS if d.id == district_id), None)
        if not district:
            raise HTTPException(status_code=404, detail=f"District {district_id} not found")
        
        # Use default radius if not specified
        if radius is None:
            radius = DISTRICT_RADIUS.get(district_id, 600)
        
        # Calculate rectangular bounds (matches frontend)
        bounds = calculate_bounds(district.lat, district.lng, radius)
        
        # Use building index to find buildings in rectangular bounds
        building_index = get_building_index()
        buildings = building_index.find_buildings_in_bounds(
            bounds['lat_min'], bounds['lat_max'],
            bounds['lon_min'], bounds['lon_max']
        )
        
        print(f"Preview for {district.name}: found {len(buildings)} buildings in bounds")
        
        if not buildings:
            return {
                "error": f"No buildings found near {district.name}",
                "vertices": [],
                "normals": [],
                "triangleCount": 0,
                "buildingCount": 0,
                "center": [0, 0, 0],
                "scale": 1.0
            }
        
        return building_index.get_buildings_preview_data(buildings, max_triangles=max_triangles)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_district_mesh_preview: {e}")
        print(traceback.format_exc())
        return {
            "error": str(e),
            "vertices": [],
            "normals": [],
            "triangleCount": 0,
            "buildingCount": 0,
            "center": [0, 0, 0],
            "scale": 1.0
        }


@app.get("/api/mesh/clip/download")
async def download_clipped_stl(
    x_start: float = Query(0.0),
    x_end: float = Query(1.0),
    y_start: float = Query(0.0),
    y_end: float = Query(1.0),
    district_id: Optional[str] = Query(None)
):
    """
    Download a clipped portion of the STL file.
    """
    processor = get_processor()
    clipped = processor.clip_by_percentage(x_start, x_end, y_start, y_end)
    
    if clipped is None:
        raise HTTPException(status_code=404, detail="No geometry in selection")
    
    stl_bytes = processor.mesh_to_binary_stl(clipped)
    
    if district_id:
        district = next((d for d in SINGAPORE_DISTRICTS if d.id == district_id), None)
        filename = f"{district.name.replace(' ', '_')}_clipped.stl" if district else f"clipped_{district_id}.stl"
    else:
        filename = "clipped_model.stl"
    
    return StreamingResponse(
        io.BytesIO(stl_bytes),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ============================================
# Visualization APIs for Coordinate Verification
# ============================================

@app.get("/api/visualize/topdown")
async def get_topdown_visualization(
    width: int = Query(1000, description="Image width"),
    height: int = Query(800, description="Image height"),
    show_districts: bool = Query(True, description="Mark district locations")
):
    """
    Generate a top-down 2D projection of the STL model.
    
    Useful for verifying coordinate mapping against real maps.
    """
    processor = get_processor()
    if not processor.load_mesh():
        raise HTTPException(status_code=500, detail="Could not load mesh")
    
    # Prepare district markers
    mark_points = []
    if show_districts:
        for district in SINGAPORE_DISTRICTS:
            x, y = processor.wgs84_to_local(district.lat, district.lng)
            mark_points.append((x, y, district.name))
    
    img_bytes = generate_topdown_image(
        width=width, 
        height=height, 
        mark_points=mark_points if mark_points else None
    )
    
    if img_bytes is None:
        raise HTTPException(status_code=500, detail="Could not generate image")
    
    return StreamingResponse(
        io.BytesIO(img_bytes),
        media_type="image/png",
        headers={"Content-Disposition": "inline; filename=stl_topdown.png"}
    )


@app.get("/api/visualize/heatmap")
async def get_density_heatmap(
    width: int = Query(800, description="Image width"),
    height: int = Query(600, description="Image height")
):
    """
    Generate a density heatmap showing building concentration.
    """
    img_bytes = generate_density_heatmap(width=width, height=height)
    
    if img_bytes is None:
        raise HTTPException(status_code=500, detail="Could not generate heatmap")
    
    return StreamingResponse(
        io.BytesIO(img_bytes),
        media_type="image/png",
        headers={"Content-Disposition": "inline; filename=stl_heatmap.png"}
    )


@app.get("/api/visualize/verify-coordinates")
async def verify_coordinates():
    """
    Get coordinate mapping verification data.
    
    Returns the calculated STL coordinates for each district
    along with the STL bounds for manual verification.
    """
    processor = get_processor()
    if not processor.load_mesh():
        raise HTTPException(status_code=500, detail="Could not load mesh")
    
    bounds = processor.get_bounds()
    
    district_coords = []
    for district in SINGAPORE_DISTRICTS:
        x, y = processor.wgs84_to_local(district.lat, district.lng)
        
        # Check if within bounds
        in_bounds = (
            bounds['min_x'] <= x <= bounds['max_x'] and
            bounds['min_y'] <= y <= bounds['max_y']
        )
        
        district_coords.append({
            "id": district.id,
            "name": district.name,
            "wgs84": {"lat": district.lat, "lng": district.lng},
            "stl_coords": {"x": round(x, 1), "y": round(y, 1)},
            "in_bounds": in_bounds,
            "x_percent": round((x - bounds['min_x']) / (bounds['max_x'] - bounds['min_x']) * 100, 1),
            "y_percent": round((y - bounds['min_y']) / (bounds['max_y'] - bounds['min_y']) * 100, 1)
        })
    
    return {
        "stl_bounds": bounds,
        "singapore_geo_bounds": {
            "lat_min": 1.156,
            "lat_max": 1.472,
            "lng_min": 103.605,
            "lng_max": 104.044
        },
        "districts": district_coords
    }


# ============================================
# Streaming STL Download (for large files)
# ============================================

@app.get("/api/stl/stream")
async def stream_stl(
    district_id: Optional[str] = Query(None, description="Optional district ID")
):
    """
    Stream the STL file for download.
    
    Uses chunked transfer encoding for large files.
    """
    stl_path = get_stl_file_path()
    
    if not stl_path.exists():
        raise HTTPException(status_code=404, detail="STL file not found")
    
    async def file_iterator():
        async with aiofiles.open(stl_path, 'rb') as f:
            while chunk := await f.read(8192):  # 8KB chunks
                yield chunk
    
    if district_id:
        district = next((d for d in SINGAPORE_DISTRICTS if d.id == district_id), None)
        filename = f"{district.name.replace(' ', '_')}_SG_3D.stl" if district else "Singapore_3D.stl"
    else:
        filename = "Singapore_Building_Model.stl"
    
    return StreamingResponse(
        file_iterator(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


# ============================================
# Region Selection for Urban Agent
# ============================================

import os, tempfile

REGION_STL_ROOT = Path("/home/ubuntu/urban_agent/region_stl")

@app.get("/api/region/count")
async def count_buildings_in_region(
    lat_min: float = Query(...), lat_max: float = Query(...),
    lon_min: float = Query(...), lon_max: float = Query(...),
):
    building_index = get_building_index()
    building_index.ensure_indexed()
    buildings = building_index.find_buildings_in_bounds(lat_min, lat_max, lon_min, lon_max)
    return {"count": len(buildings)}

@app.post("/api/region/prepare")
async def prepare_region_stl(
    lat_min: float = Query(...), lat_max: float = Query(...),
    lon_min: float = Query(...), lon_max: float = Query(...),
):
    building_index = get_building_index()
    building_index.ensure_indexed()
    buildings = building_index.find_buildings_in_bounds(lat_min, lat_max, lon_min, lon_max)
    if not buildings:
        raise HTTPException(404, "No buildings found in the selected region")

    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stl_dir = REGION_STL_ROOT / ts
    stl_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for b in buildings:
        src = Path(b.get("stl_file", "")) if isinstance(b, dict) else Path(getattr(b, "stl_file", ""))
        if src.exists():
            dst = stl_dir / src.name
            if not dst.exists():
                os.symlink(src, dst)
            count += 1

    if count == 0:
        raise HTTPException(404, "No STL files found for the selected buildings")

    return {
        "stl_directory": str(stl_dir),
        "building_count": count,
        "bounds": {"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max},
    }


# ============================================
# Run Server
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )

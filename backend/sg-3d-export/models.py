"""
Data models for SG 3D Export Backend
"""
from pydantic import BaseModel
from enum import Enum
from typing import Optional


class District(BaseModel):
    """District model representing Singapore districts"""
    id: str
    name: str
    region: str
    lat: float
    lng: float


class SelectionStatus(str, Enum):
    """Status enum for selection processing"""
    IDLE = "Idle"
    PROCESSING = "Processing"
    READY = "Ready"
    ERROR = "Error"


class SelectionStats(BaseModel):
    """Statistics for a selected area"""
    buildings: int
    file_size: str
    status: SelectionStatus
    progress: int


class UrbanInsightRequest(BaseModel):
    """Request model for urban insight"""
    district_name: str


class UrbanInsightResponse(BaseModel):
    """Response model for urban insight"""
    district_name: str
    insight: str


class STLExportRequest(BaseModel):
    """Request model for STL export"""
    district_id: str
    bounds: Optional[dict] = None


class ExportJobStatus(BaseModel):
    """Export job status model"""
    job_id: str
    district_id: str
    status: SelectionStatus
    progress: int
    file_size: Optional[str] = None
    download_url: Optional[str] = None


# Predefined Singapore districts data
SINGAPORE_DISTRICTS = [
    District(id="1", name="Marina Bay", region="Central Region", lat=1.2847, lng=103.8597),
    District(id="2", name="Orchard", region="Central Region", lat=1.3048, lng=103.8318),
    District(id="3", name="Jurong West", region="West Region", lat=1.3404, lng=103.7090),
    District(id="4", name="Tampines", region="East Region", lat=1.3521, lng=103.9448),
    District(id="5", name="Woodlands", region="North Region", lat=1.4382, lng=103.7890),
    District(id="6", name="One North", region="West Region", lat=1.2995, lng=103.7872),
    District(id="7", name="NUS", region="West Region", lat=1.2966, lng=103.7764),
    District(id="8", name="NTU", region="West Region", lat=1.3483, lng=103.6831),
]

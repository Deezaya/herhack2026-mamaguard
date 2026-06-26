from fastapi import APIRouter, Query

from app.schemas.hospital import NearbyHospitalsResponse
from app.services.hospital_service import HospitalService

router = APIRouter(
    prefix="/hospitals",
    tags=["Hospitals"],
)


@router.get("/nearby", response_model=NearbyHospitalsResponse)
async def get_nearby_hospitals(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius: int = Query(
        5000,
        ge=100,
        le=50000,
        description="Search radius in meters",
    ),
):
    hospitals = await HospitalService.get_nearby_hospitals(
        latitude=lat,
        longitude=lon,
        radius=radius,
    )

    return NearbyHospitalsResponse(
        count=len(hospitals),
        hospitals=hospitals,
    )
from pydantic import BaseModel


class Hospital(BaseModel):
    name: str
    latitude: float
    longitude: float
    address: str | None = None
    distance: float

class NearbyHospitalsResponse(BaseModel):
    count: int
    hospitals: list[Hospital]
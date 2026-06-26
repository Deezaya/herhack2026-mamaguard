import json
import os

import httpx
from dotenv import load_dotenv

from app.schemas.hospital import Hospital

load_dotenv()

API_KEY = os.getenv("GEOAPIFY_API_KEY")
BASE_URL = "https://api.geoapify.com/v2/places"


class HospitalService:
    @staticmethod
    async def get_nearby_hospitals(
        latitude: float,
        longitude: float,
        radius: int = 5000,
    ) -> list[Hospital]:

        params = {
            "categories": "healthcare.hospital",
            "filter": f"circle:{longitude},{latitude},{radius}",
            "bias": f"proximity:{longitude},{latitude}",
            "limit": 20,
            "apiKey": API_KEY,
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(BASE_URL, params=params)

            print("URL:", response.request.url)
            print("STATUS:", response.status_code)
            print("BODY:", response.text)

            response.raise_for_status()

            data = response.json()
            print(json.dumps(data["features"][0], indent=2))

        hospitals = []

        for feature in data.get("features", []):
            properties = feature.get("properties", {})

            hospitals.append(
                Hospital(
                    name=properties.get("name", "Unknown Hospital"),
                    latitude=properties.get("lat"),
                    longitude=properties.get("lon"),
                    address=properties.get("formatted"),
                    distance=properties.get("distance", 0),
                )
            )

        return hospitals
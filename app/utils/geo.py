from typing import Optional


def build_near_sphere_query(
    field: str,
    lat: float,
    lng: float,
    radius_km: int = 10,
) -> dict:
    return {
        field: {
            "$nearSphere": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat],
                },
                "$maxDistance": radius_km * 1000,
            }
        }
    }


def build_geo_within_query(
    field: str,
    lat: float,
    lng: float,
    radius_km: int = 10,
) -> dict:
    return {
        field: {
            "$geoWithin": {
                "$centerSphere": [
                    [lng, lat],
                    radius_km / 6378.1,
                ],
            }
        }
    }

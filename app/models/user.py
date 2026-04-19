from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId


class GeoJSONPoint(BaseModel):
    type: str = "Point"
    coordinates: list[float] = Field(default_factory=lambda: [0.0, 0.0])


class DeviceInfo(BaseModel):
    platform: Optional[str] = None
    device_model: Optional[str] = None
    app_version: Optional[str] = None
    fcm_token: Optional[str] = None
    expo_push_token: Optional[str] = None


class UserCreate(BaseModel):
    clerk_user_id: str
    full_name: str
    email: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None
    usage_preference: Optional[str] = None
    language: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    locality: Optional[str] = None
    location: Optional[GeoJSONPoint] = None
    address_line: Optional[str] = None
    device_info: Optional[DeviceInfo] = None
    work_title: Optional[str] = None
    work_range_km: Optional[int] = None
    bio: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    clerk_user_id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None
    usage_preference: Optional[str] = "find_worker"
    is_active: bool = True
    is_blocked: bool = False
    language: Optional[str] = "hi"
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    locality: Optional[str] = None
    location: Optional[GeoJSONPoint] = None
    address_line: Optional[str] = None
    device_info: Optional[DeviceInfo] = None
    work_title: Optional[str] = None
    work_range_km: Optional[int] = None
    bio: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserPublicResponse(BaseModel):
    id: str
    full_name: str
    profile_photo_url: Optional[str] = None
    usage_preference: Optional[str] = None
    city: Optional[str] = None
    locality: Optional[str] = None
    rating_avg: float = 0.0
    rating_count: int = 0
    headline: Optional[str] = None
    experience_years: Optional[int] = None
    jobs_completed: int = 0
    skills: list[str] = []
    created_at: Optional[datetime] = None


def user_doc_to_response(doc: dict) -> UserResponse:
    doc["id"] = str(doc.pop("_id"))
    return UserResponse(**doc)


def user_doc_to_public(doc: dict) -> UserPublicResponse:
    return UserPublicResponse(
        id=str(doc["_id"]),
        full_name=doc.get("full_name", ""),
        profile_photo_url=doc.get("profile_photo_url"),
        usage_preference=doc.get("usage_preference"),
        city=doc.get("city"),
        locality=doc.get("locality"),
        created_at=doc.get("created_at"),
    )

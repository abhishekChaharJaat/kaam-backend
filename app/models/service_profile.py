from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Availability(BaseModel):
    is_available_now: bool = False
    available_from: Optional[str] = None
    available_to: Optional[str] = None
    working_days: list[str] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat"])


class ServiceProfileCreate(BaseModel):
    headline: str
    bio: Optional[str] = None
    experience_years: Optional[int] = None
    category_ids: list[str]
    subcategory_ids: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    service_radius_km: Optional[int] = 10
    service_areas: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=lambda: ["Hindi"])
    price_note: Optional[str] = None
    availability: Optional[Availability] = None


class ServiceProfileUpdate(BaseModel):
    headline: Optional[str] = None
    bio: Optional[str] = None
    experience_years: Optional[int] = None
    category_ids: Optional[list[str]] = None
    subcategory_ids: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    service_radius_km: Optional[int] = None
    service_areas: Optional[list[str]] = None
    is_available: Optional[bool] = None
    languages: Optional[list[str]] = None
    work_images: Optional[list[str]] = None
    price_note: Optional[str] = None
    availability: Optional[Availability] = None


class ServiceProfileResponse(BaseModel):
    id: str
    user_id: str
    headline: str
    bio: Optional[str] = None
    experience_years: Optional[int] = None
    category_ids: list[str] = Field(default_factory=list)
    subcategory_ids: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    service_radius_km: Optional[int] = 10
    service_areas: list[str] = Field(default_factory=list)
    is_available: bool = True
    is_verified: bool = False
    rating_avg: float = 0.0
    rating_count: int = 0
    jobs_completed: int = 0
    languages: list[str] = Field(default_factory=list)
    work_images: list[str] = Field(default_factory=list)
    price_note: Optional[str] = None
    availability: Optional[Availability] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def service_profile_doc_to_response(doc: dict) -> ServiceProfileResponse:
    doc["id"] = str(doc.pop("_id"))
    doc["user_id"] = str(doc["user_id"])
    if "category_ids" in doc:
        doc["category_ids"] = [str(c) for c in doc["category_ids"]]
    if "subcategory_ids" in doc:
        doc["subcategory_ids"] = [str(c) for c in doc["subcategory_ids"]]
    return ServiceProfileResponse(**doc)

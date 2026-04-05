from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date


class GeoJSONPoint(BaseModel):
    type: str = "Point"
    coordinates: list[float] = Field(default_factory=lambda: [0.0, 0.0])


class JobCreate(BaseModel):
    title: str
    description: str
    category_id: str
    subcategory_id: Optional[str] = None
    budget_type: str = "negotiable"
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    urgency: str = "flexible"
    required_date: Optional[str] = None
    required_time_slot: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    locality: Optional[str] = None
    address_line: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    images: list[str] = Field(default_factory=list)


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    budget_type: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    urgency: Optional[str] = None
    required_date: Optional[str] = None
    required_time_slot: Optional[str] = None
    images: Optional[list[str]] = None


class JobResponse(BaseModel):
    id: str
    posted_by_user_id: str
    posted_by_clerk_id: Optional[str] = None
    posted_by_name: Optional[str] = None
    title: str
    description: str
    category_id: str
    subcategory_id: Optional[str] = None
    budget_type: str = "negotiable"
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    currency: str = "INR"
    urgency: str = "flexible"
    status: str = "open"
    required_date: Optional[str] = None
    required_time_slot: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    locality: Optional[str] = None
    address_line: Optional[str] = None
    location: Optional[GeoJSONPoint] = None
    images: list[str] = Field(default_factory=list)
    assigned_to_user_id: Optional[str] = None
    assigned_conversation_id: Optional[str] = None
    view_count: int = 0
    conversation_count: int = 0
    poster_rating_avg: float = 0.0
    poster_rating_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def job_doc_to_response(doc: dict, poster_name: str | None = None) -> JobResponse:
    return JobResponse(
        id=str(doc["_id"]),
        posted_by_user_id=str(doc["posted_by_user_id"]),
        posted_by_clerk_id=doc.get("posted_by_clerk_id"),
        posted_by_name=poster_name or doc.get("posted_by_name"),
        title=doc["title"],
        description=doc.get("description", ""),
        category_id=str(doc.get("category_id", "")),
        subcategory_id=str(doc["subcategory_id"]) if doc.get("subcategory_id") else None,
        budget_type=doc.get("budget_type", "negotiable"),
        budget_min=doc.get("budget_min"),
        budget_max=doc.get("budget_max"),
        currency=doc.get("currency", "INR"),
        urgency=doc.get("urgency", "flexible"),
        status=doc.get("status", "open"),
        required_date=doc.get("required_date"),
        required_time_slot=doc.get("required_time_slot"),
        city=doc.get("city"),
        state=doc.get("state"),
        locality=doc.get("locality"),
        address_line=doc.get("address_line"),
        location=doc.get("location"),
        images=doc.get("images", []),
        assigned_to_user_id=str(doc["assigned_to_user_id"]) if doc.get("assigned_to_user_id") else None,
        assigned_conversation_id=str(doc["assigned_conversation_id"]) if doc.get("assigned_conversation_id") else None,
        view_count=doc.get("view_count", 0),
        conversation_count=doc.get("conversation_count", 0),
        poster_rating_avg=doc.get("poster_rating_avg", 0.0),
        poster_rating_count=doc.get("poster_rating_count", 0),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )

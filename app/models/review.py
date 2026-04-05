from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReviewCreate(BaseModel):
    job_id: str
    reviewed_user_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class ReviewResponse(BaseModel):
    id: str
    job_id: str
    reviewer_user_id: str
    reviewer_name: Optional[str] = None
    reviewed_user_id: str
    rating: int
    comment: Optional[str] = None
    is_public: bool = True
    created_at: Optional[datetime] = None


def review_doc_to_response(doc: dict) -> ReviewResponse:
    return ReviewResponse(
        id=str(doc["_id"]),
        job_id=str(doc["job_id"]),
        reviewer_user_id=str(doc["reviewer_user_id"]),
        reviewer_name=doc.get("reviewer_name"),
        reviewed_user_id=str(doc["reviewed_user_id"]),
        rating=doc.get("rating", 0),
        comment=doc.get("comment"),
        is_public=doc.get("is_public", True),
        created_at=doc.get("created_at"),
    )

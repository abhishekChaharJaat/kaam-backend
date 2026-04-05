from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ReportCreate(BaseModel):
    target_user_id: str
    job_id: Optional[str] = None
    reason: str
    description: Optional[str] = None


class ReportResponse(BaseModel):
    id: str
    reported_by_user_id: str
    target_user_id: str
    job_id: Optional[str] = None
    reason: str
    description: Optional[str] = None
    status: str = "open"
    created_at: Optional[datetime] = None


def report_doc_to_response(doc: dict) -> ReportResponse:
    return ReportResponse(
        id=str(doc["_id"]),
        reported_by_user_id=str(doc["reported_by_user_id"]),
        target_user_id=str(doc["target_user_id"]),
        job_id=str(doc["job_id"]) if doc.get("job_id") else None,
        reason=doc.get("reason", ""),
        description=doc.get("description"),
        status=doc.get("status", "open"),
        created_at=doc.get("created_at"),
    )

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    body: str
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    is_read: bool = False
    created_at: Optional[datetime] = None


def notification_doc_to_response(doc: dict) -> NotificationResponse:
    return NotificationResponse(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        type=doc.get("type", "system_alert"),
        title=doc.get("title", ""),
        body=doc.get("body", ""),
        reference_id=str(doc["reference_id"]) if doc.get("reference_id") else None,
        reference_type=doc.get("reference_type"),
        is_read=doc.get("is_read", False),
        created_at=doc.get("created_at"),
    )

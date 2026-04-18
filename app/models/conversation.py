from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ConversationCreate(BaseModel):
    job_id: str
    responder_user_id: Optional[str] = None


class ConversationResponse(BaseModel):
    id: str
    job_id: str
    job_title: Optional[str] = None
    job_status: Optional[str] = None
    poster_user_id: str
    poster_name: Optional[str] = None
    responder_user_id: str
    responder_name: Optional[str] = None
    last_message_text: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count_poster: int = 0
    unread_count_responder: int = 0
    is_assigned: bool = False
    is_disabled: bool = False
    created_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_user_id: Optional[str] = None
    message_type: str = "text"
    text: Optional[str] = None
    attachment_url: Optional[str] = None
    is_read: bool = False
    created_at: Optional[datetime] = None


def conversation_doc_to_response(doc: dict) -> ConversationResponse:
    return ConversationResponse(
        id=str(doc["_id"]),
        job_id=str(doc["job_id"]),
        job_title=doc.get("job_title"),
        job_status=doc.get("job_status"),
        poster_user_id=str(doc["poster_user_id"]),
        poster_name=doc.get("poster_name"),
        responder_user_id=str(doc["responder_user_id"]),
        responder_name=doc.get("responder_name"),
        last_message_text=doc.get("last_message_text"),
        last_message_at=doc.get("last_message_at"),
        unread_count_poster=doc.get("unread_count_poster", 0),
        unread_count_responder=doc.get("unread_count_responder", 0),
        is_assigned=doc.get("is_assigned", False),
        is_disabled=doc.get("is_disabled", False),
        created_at=doc.get("created_at"),
    )


def message_doc_to_response(doc: dict) -> MessageResponse:
    return MessageResponse(
        id=str(doc["_id"]),
        conversation_id=str(doc["conversation_id"]),
        sender_user_id=str(doc["sender_user_id"]) if doc.get("sender_user_id") else None,
        message_type=doc.get("message_type", "text"),
        text=doc.get("text"),
        attachment_url=doc.get("attachment_url"),
        is_read=doc.get("is_read", False),
        created_at=doc.get("created_at"),
    )

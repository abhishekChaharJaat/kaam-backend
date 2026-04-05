from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from bson import ObjectId
from typing import Optional

from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.routes.websocket import manager as ws_manager
from app.models.conversation import (
    ConversationCreate,
    ConversationResponse,
    MessageResponse,
    conversation_doc_to_response,
    message_doc_to_response,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    data: ConversationCreate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    job_oid = ObjectId(data.job_id)
    job = await db.jobs.find_one({"_id": job_oid})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "open":
        raise HTTPException(status_code=400, detail="Job is not open for new conversations")

    poster_id = job["posted_by_user_id"]
    responder_oid = ObjectId(data.responder_user_id) if data.responder_user_id else user["_id"]

    if user["_id"] == poster_id:
        responder_id = responder_oid
    else:
        responder_id = user["_id"]

    existing = await db.conversations.find_one({
        "job_id": job_oid,
        "poster_user_id": poster_id,
        "responder_user_id": responder_id,
    })
    if existing:
        poster_doc = await db.users.find_one({"_id": poster_id})
        responder_doc = await db.users.find_one({"_id": responder_id})
        if poster_doc and poster_doc.get("full_name"):
            existing["poster_name"] = poster_doc["full_name"]
        if responder_doc and responder_doc.get("full_name"):
            existing["responder_name"] = responder_doc["full_name"]
        return conversation_doc_to_response(existing)

    responder = await db.users.find_one({"_id": responder_id})
    poster = await db.users.find_one({"_id": poster_id})

    now = datetime.utcnow()
    doc = {
        "job_id": job_oid,
        "job_title": job.get("title", ""),
        "poster_user_id": poster_id,
        "poster_name": poster.get("full_name", "") if poster else "",
        "responder_user_id": responder_id,
        "responder_name": responder.get("full_name", "") if responder else "",
        "last_message_text": None,
        "last_message_at": None,
        "unread_count_poster": 0,
        "unread_count_responder": 0,
        "is_assigned": False,
        "is_disabled": False,
        "created_at": now,
    }
    result = await db.conversations.insert_one(doc)
    doc["_id"] = result.inserted_id

    await db.jobs.update_one({"_id": job_oid}, {"$inc": {"conversation_count": 1}})
    return conversation_doc_to_response(doc)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    role: Optional[str] = Query(None, regex="^(poster|responder)$"),
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if role == "poster":
        query = {"poster_user_id": user["_id"]}
    elif role == "responder":
        query = {"responder_user_id": user["_id"]}
    else:
        query = {
            "$or": [
                {"poster_user_id": user["_id"]},
                {"responder_user_id": user["_id"]},
            ]
        }

    cursor = db.conversations.find(query).sort("last_message_at", -1)
    convs = [doc async for doc in cursor]

    user_ids = set()
    for c in convs:
        user_ids.add(c["poster_user_id"])
        user_ids.add(c["responder_user_id"])

    users_cursor = db.users.find({"_id": {"$in": list(user_ids)}})
    user_names: dict = {}
    async for u in users_cursor:
        user_names[u["_id"]] = u.get("full_name", "")

    for c in convs:
        poster_name = user_names.get(c["poster_user_id"], "")
        responder_name = user_names.get(c["responder_user_id"], "")
        if poster_name:
            c["poster_name"] = poster_name
        if responder_name:
            c["responder_name"] = responder_name

    return [conversation_doc_to_response(c) for c in convs]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if user["_id"] not in (conv["poster_user_id"], conv["responder_user_id"]):
        raise HTTPException(status_code=403, detail="Not a participant")

    poster = await db.users.find_one({"_id": conv["poster_user_id"]})
    responder = await db.users.find_one({"_id": conv["responder_user_id"]})
    if poster and poster.get("full_name"):
        conv["poster_name"] = poster["full_name"]
    if responder and responder.get("full_name"):
        conv["responder_name"] = responder["full_name"]

    return conversation_doc_to_response(conv)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: str,
    before: Optional[str] = None,
    limit: int = Query(default=30, le=50),
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    conv_oid = ObjectId(conversation_id)
    conv = await db.conversations.find_one({"_id": conv_oid})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user["_id"] not in (conv["poster_user_id"], conv["responder_user_id"]):
        raise HTTPException(status_code=403, detail="Not a participant")

    query: dict = {"conversation_id": conv_oid}
    if before:
        query["_id"] = {"$lt": ObjectId(before)}

    cursor = db.messages.find(query).sort("_id", -1).limit(limit)
    messages = [message_doc_to_response(doc) async for doc in cursor]

    await db.messages.update_many(
        {"conversation_id": conv_oid, "sender_user_id": {"$ne": user["_id"]}, "is_read": False},
        {"$set": {"is_read": True}},
    )

    unread_field = (
        "unread_count_poster"
        if user["_id"] == conv["poster_user_id"]
        else "unread_count_responder"
    )
    await db.conversations.update_one({"_id": conv_oid}, {"$set": {unread_field: 0}})

    return list(reversed(messages))


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    conversation_id: str,
    text: str = Query(...),
    message_type: str = Query(default="text"),
    attachment_url: Optional[str] = None,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    conv_oid = ObjectId(conversation_id)
    conv = await db.conversations.find_one({"_id": conv_oid})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user["_id"] not in (conv["poster_user_id"], conv["responder_user_id"]):
        raise HTTPException(status_code=403, detail="Not a participant")
    if conv.get("is_disabled"):
        raise HTTPException(status_code=400, detail="Conversation is disabled")

    now = datetime.utcnow()
    msg_doc = {
        "conversation_id": conv_oid,
        "sender_user_id": user["_id"],
        "message_type": message_type,
        "text": text,
        "attachment_url": attachment_url,
        "is_read": False,
        "created_at": now,
    }
    result = await db.messages.insert_one(msg_doc)
    msg_doc["_id"] = result.inserted_id

    unread_field = (
        "unread_count_responder"
        if user["_id"] == conv["poster_user_id"]
        else "unread_count_poster"
    )
    await db.conversations.update_one(
        {"_id": conv_oid},
        {
            "$set": {"last_message_text": text, "last_message_at": now},
            "$inc": {unread_field: 1},
        },
    )

    broadcast_msg = {
        "id": str(result.inserted_id),
        "conversation_id": conversation_id,
        "sender_user_id": str(user["_id"]),
        "message_type": message_type,
        "text": text,
        "attachment_url": attachment_url,
        "is_read": False,
        "created_at": now.isoformat(),
    }
    await ws_manager.broadcast_all(conversation_id, broadcast_msg)

    return message_doc_to_response(msg_doc)


@router.post("/{conversation_id}/nudge", response_model=MessageResponse)
async def send_nudge(
    conversation_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    conv_oid = ObjectId(conversation_id)
    conv = await db.conversations.find_one({"_id": conv_oid})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user["_id"] not in (conv["poster_user_id"], conv["responder_user_id"]):
        raise HTTPException(status_code=403, detail="Not a participant")
    if conv.get("is_disabled"):
        raise HTTPException(status_code=400, detail="Conversation is disabled")
    if conv.get("is_assigned"):
        raise HTTPException(status_code=400, detail="Job already assigned")

    sender_name = user.get("full_name", "Worker")
    nudge_text = f"{sender_name} is interested and requesting you to close this job with them."

    now = datetime.utcnow()
    msg_doc = {
        "conversation_id": conv_oid,
        "sender_user_id": None,
        "message_type": "nudge",
        "text": nudge_text,
        "attachment_url": None,
        "is_read": False,
        "created_at": now,
    }
    result = await db.messages.insert_one(msg_doc)
    msg_doc["_id"] = result.inserted_id

    unread_field = (
        "unread_count_responder"
        if user["_id"] == conv["poster_user_id"]
        else "unread_count_poster"
    )
    await db.conversations.update_one(
        {"_id": conv_oid},
        {
            "$set": {"last_message_text": nudge_text, "last_message_at": now},
            "$inc": {unread_field: 1},
        },
    )

    broadcast_msg = {
        "id": str(result.inserted_id),
        "conversation_id": conversation_id,
        "sender_user_id": None,
        "message_type": "nudge",
        "text": nudge_text,
        "attachment_url": None,
        "is_read": False,
        "created_at": now.isoformat(),
    }
    await ws_manager.broadcast_all(conversation_id, broadcast_msg)

    return message_doc_to_response(msg_doc)

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from datetime import datetime
from bson import ObjectId
import json

from app.database import get_db
from app.middleware.auth import verify_clerk_jwt

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, conversation_id: str, ws: WebSocket):
        await ws.accept()
        if conversation_id not in self.active:
            self.active[conversation_id] = []
        self.active[conversation_id].append(ws)

    def disconnect(self, conversation_id: str, ws: WebSocket):
        if conversation_id in self.active:
            self.active[conversation_id] = [
                w for w in self.active[conversation_id] if w != ws
            ]
            if not self.active[conversation_id]:
                del self.active[conversation_id]

    async def broadcast(self, conversation_id: str, message: dict, sender_ws: WebSocket):
        for ws in self.active.get(conversation_id, []):
            if ws != sender_ws:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    async def broadcast_all(self, conversation_id: str, message: dict):
        for ws in self.active.get(conversation_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    def is_connected(self, conversation_id: str, user_id: str) -> bool:
        return conversation_id in self.active and len(self.active[conversation_id]) > 1


manager = ConnectionManager()


@router.websocket("/ws/chat/{conversation_id}")
async def websocket_chat(
    ws: WebSocket,
    conversation_id: str,
    token: str = Query(...),
):
    try:
        payload = await verify_clerk_jwt(token)
        clerk_user_id = payload.get("sub")
    except Exception:
        await ws.close(code=4001, reason="Unauthorized")
        return

    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        await ws.close(code=4001, reason="User not found")
        return

    conv_oid = ObjectId(conversation_id)
    conv = await db.conversations.find_one({"_id": conv_oid})
    if not conv:
        await ws.close(code=4004, reason="Conversation not found")
        return

    if user["_id"] not in (conv["poster_user_id"], conv["responder_user_id"]):
        await ws.close(code=4003, reason="Not a participant")
        return

    await manager.connect(conversation_id, ws)

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            if conv.get("is_disabled"):
                await ws.send_json({"error": "Conversation is disabled"})
                continue

            now = datetime.utcnow()
            msg_doc = {
                "conversation_id": conv_oid,
                "sender_user_id": user["_id"],
                "message_type": data.get("message_type", "text"),
                "text": data.get("text", ""),
                "attachment_url": data.get("attachment_url"),
                "is_read": False,
                "created_at": now,
            }
            result = await db.messages.insert_one(msg_doc)

            unread_field = (
                "unread_count_responder"
                if user["_id"] == conv["poster_user_id"]
                else "unread_count_poster"
            )
            await db.conversations.update_one(
                {"_id": conv_oid},
                {
                    "$set": {
                        "last_message_text": data.get("text", ""),
                        "last_message_at": now,
                    },
                    "$inc": {unread_field: 1},
                },
            )

            if not conv.get("last_message_at") and conv.get("job_id"):
                await db.jobs.update_one(
                    {"_id": conv["job_id"]},
                    {"$inc": {"conversation_count": 1}},
                )
            conv["last_message_at"] = now

            broadcast_msg = {
                "id": str(result.inserted_id),
                "conversation_id": conversation_id,
                "sender_user_id": str(user["_id"]),
                "message_type": data.get("message_type", "text"),
                "text": data.get("text", ""),
                "attachment_url": data.get("attachment_url"),
                "is_read": False,
                "created_at": now.isoformat(),
            }

            await ws.send_json({**broadcast_msg, "status": "sent"})
            await manager.broadcast(conversation_id, broadcast_msg, ws)

    except WebSocketDisconnect:
        manager.disconnect(conversation_id, ws)
    except Exception:
        manager.disconnect(conversation_id, ws)

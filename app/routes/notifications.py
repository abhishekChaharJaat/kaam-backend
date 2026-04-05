from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId

from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.models.notification import NotificationResponse, notification_doc_to_response

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    limit: int = Query(default=20, le=50),
    skip: int = Query(default=0, ge=0),
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cursor = (
        db.notifications.find({"user_id": user["_id"]})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return [notification_doc_to_response(doc) async for doc in cursor]


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": user["_id"]},
        {"$set": {"is_read": True}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"message": "Marked as read"}

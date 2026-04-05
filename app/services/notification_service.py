from datetime import datetime
from bson import ObjectId
from typing import Optional

from app.database import get_db


async def create_notification(
    user_id: ObjectId,
    notification_type: str,
    title: str,
    body: str,
    reference_id: Optional[ObjectId] = None,
    reference_type: Optional[str] = None,
) -> dict:
    db = get_db()
    doc = {
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "body": body,
        "reference_id": reference_id,
        "reference_type": reference_type,
        "is_read": False,
        "created_at": datetime.utcnow(),
    }
    result = await db.notifications.insert_one(doc)
    doc["_id"] = result.inserted_id

    # TODO: Send FCM push when Firebase Admin SDK is configured
    # This is a placeholder for future FCM integration
    await _send_fcm_push(user_id, title, body, reference_id, reference_type)

    return doc


async def _send_fcm_push(
    user_id: ObjectId,
    title: str,
    body: str,
    reference_id: Optional[ObjectId] = None,
    reference_type: Optional[str] = None,
):
    """Placeholder for FCM push notification delivery."""
    db = get_db()
    user = await db.users.find_one({"_id": user_id})
    if not user:
        return

    fcm_token = user.get("device_info", {}).get("fcm_token") if user.get("device_info") else None
    if not fcm_token:
        return

    # Firebase Admin SDK integration will go here
    # firebase_admin.messaging.send(Message(...))


async def notify_new_job(job_doc: dict):
    """Send new-job notifications to matching workers in the area."""
    db = get_db()
    category_id = job_doc.get("category_id")
    location = job_doc.get("location")

    query: dict = {
        "usage_preference": "find_work",
        "is_active": True,
    }

    profiles = db.service_profiles.find({"category_ids": category_id})
    async for profile in profiles:
        await create_notification(
            user_id=profile["user_id"],
            notification_type="new_job",
            title="New Job Nearby",
            body=f'{job_doc.get("title", "A new job")} has been posted in your area',
            reference_id=job_doc["_id"],
            reference_type="job",
        )


async def notify_job_assigned(job_doc: dict, assigned_user_id: ObjectId):
    await create_notification(
        user_id=assigned_user_id,
        notification_type="job_assigned",
        title="Job Assigned to You",
        body=f'You have been assigned: {job_doc.get("title", "")}',
        reference_id=job_doc["_id"],
        reference_type="job",
    )


async def notify_job_reopened(job_doc: dict):
    db = get_db()
    convs = db.conversations.find({"job_id": job_doc["_id"]})
    async for conv in convs:
        responder_id = conv["responder_user_id"]
        await create_notification(
            user_id=responder_id,
            notification_type="job_reopened",
            title="Job Reopened",
            body=f'{job_doc.get("title", "")} has been reopened',
            reference_id=job_doc["_id"],
            reference_type="job",
        )

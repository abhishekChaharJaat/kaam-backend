from datetime import datetime
from bson import ObjectId
from typing import Optional

import httpx

from app.database import get_db


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


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

    await _send_expo_push(user_id, title, body, reference_id, reference_type)

    return doc


async def _send_expo_push(
    user_id: ObjectId,
    title: str,
    body: str,
    reference_id: Optional[ObjectId] = None,
    reference_type: Optional[str] = None,
):
    """Send push notification via Expo Push API."""
    db = get_db()
    user = await db.users.find_one({"_id": user_id})
    if not user:
        return

    push_token = (
        user.get("device_info", {}).get("expo_push_token")
        if user.get("device_info")
        else None
    )
    if not push_token or not push_token.startswith("ExponentPushToken["):
        return

    message = {
        "to": push_token,
        "title": title,
        "body": body,
        "sound": "default",
        "data": {},
    }
    if reference_id:
        message["data"]["reference_id"] = str(reference_id)
    if reference_type:
        message["data"]["reference_type"] = reference_type

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                EXPO_PUSH_URL,
                json=message,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        try:
            payload = resp.json()
        except Exception:
            payload = {"_raw": resp.text}
        print(
            f"[push] expo {resp.status_code} to user={user_id} "
            f"token={push_token} resp={payload}"
        )
    except Exception as e:
        print(f"[push] expo call failed for user={user_id} token={push_token}: {e!r}")


async def notify_new_job(job_doc: dict):
    """Send new-job notifications to matching workers within their work range."""
    db = get_db()
    category_id = job_doc.get("category_id")
    job_location = job_doc.get("location")
    print(
        f"[notify_new_job] job={job_doc.get('_id')} title={job_doc.get('title')!r} "
        f"category_id={category_id} has_location={bool(job_location)}"
    )

    # Find workers with matching category via service_profiles
    matching_user_ids = []
    profiles = db.service_profiles.find({"category_ids": category_id})
    async for profile in profiles:
        matching_user_ids.append(profile["user_id"])

    print(
        f"[notify_new_job] matching service_profiles by category: "
        f"{len(matching_user_ids)} -> {[str(x) for x in matching_user_ids]}"
    )

    if not matching_user_ids:
        print("[notify_new_job] no service_profiles match this category. Exiting.")
        return

    # Fetch those users who are active workers
    workers_list = await db.users.find({
        "_id": {"$in": matching_user_ids},
        "usage_preference": "find_work",
        "is_active": True,
    }).to_list(length=None)

    print(
        f"[notify_new_job] active 'find_work' users among matches: {len(workers_list)} "
        f"-> {[str(w['_id']) for w in workers_list]}"
    )

    job_coords = (
        job_location.get("coordinates") if job_location else None
    )

    notified = 0
    for worker in workers_list:
        # Check if job is within worker's range
        if job_coords and worker.get("location"):
            worker_coords = worker["location"].get("coordinates")
            worker_range = worker.get("work_range_km")

            if worker_coords and worker_range:
                dist = _haversine_km(
                    worker_coords[1], worker_coords[0],
                    job_coords[1], job_coords[0],
                )
                if dist > worker_range:
                    print(
                        f"[notify_new_job] skip user={worker['_id']} "
                        f"dist={dist:.2f}km > range={worker_range}km"
                    )
                    continue  # Job is outside worker's range

        await create_notification(
            user_id=worker["_id"],
            notification_type="new_job",
            title="New Job Nearby",
            body=f'{job_doc.get("title", "A new job")} has been posted in your area',
            reference_id=job_doc["_id"],
            reference_type="job",
        )
        notified += 1

    print(f"[notify_new_job] notified {notified} workers")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two lat/lng points in km."""
    import math
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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

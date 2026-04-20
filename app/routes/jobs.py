from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from bson import ObjectId
from typing import Optional

from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.models.job import JobCreate, JobUpdate, JobResponse, job_doc_to_response
from app.utils.geo import build_near_sphere_query
from app.services.spam_service import check_daily_job_limit, check_duplicate_job
from app.services.notification_service import (
    notify_new_job,
    notify_job_assigned,
    notify_job_reopened,
)
from app.config import get_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    data: JobCreate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    settings = get_settings()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not await check_daily_job_limit(db, user["_id"], settings.MAX_ACTIVE_JOBS_PER_DAY):
        raise HTTPException(status_code=429, detail="Daily job posting limit reached")

    try:
        cat_id = ObjectId(data.category_id)
    except Exception:
        cat = await db.categories.find_one({"slug": data.category_id})
        if not cat:
            raise HTTPException(status_code=400, detail=f"Category '{data.category_id}' not found")
        cat_id = cat["_id"]

    if await check_duplicate_job(db, user["_id"], data.title, cat_id):
        raise HTTPException(status_code=409, detail="Duplicate job detected. Wait before posting a similar job.")

    # Always use user's stored location
    location = user.get("location")

    job_doc = {
        "posted_by_user_id": user["_id"],
        "posted_by_clerk_id": clerk_user_id,
        "posted_by_name": user.get("full_name", ""),
        "title": data.title,
        "description": data.description,
        "category_id": cat_id,
        "subcategory_id": ObjectId(data.subcategory_id) if data.subcategory_id else None,
        "budget_type": data.budget_type,
        "budget_min": data.budget_min,
        "budget_max": data.budget_max,
        "currency": "INR",
        "urgency": data.urgency,
        "status": "open",
        "required_date": data.required_date,
        "required_date_end": data.required_date_end,
        "required_time_slot": data.required_time_slot,
        "city": user.get("city"),
        "state": user.get("state"),
        "locality": user.get("locality"),
        "address_line": user.get("address_line"),
        "location": location,
        "images": data.images,
        "assigned_to_user_id": None,
        "assigned_conversation_id": None,
        "view_count": 0,
        "conversation_count": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = await db.jobs.insert_one(job_doc)
    job_doc["_id"] = result.inserted_id

    # Notify matching workers in the background
    import asyncio
    asyncio.create_task(notify_new_job(job_doc))

    return job_doc_to_response(job_doc)


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: int = Query(default=10, le=50),
    category_id: Optional[str] = None,
    budget_type: Optional[str] = None,
    urgency: Optional[str] = None,
    status: str = "open",
    q: Optional[str] = Query(default=None, max_length=100),
    exclude_mine: bool = Query(default=False),
    limit: int = Query(default=20, le=50),
    skip: int = Query(default=0, ge=0),
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    query: dict = {"status": status}

    if exclude_mine:
        user = await db.users.find_one({"clerk_user_id": clerk_user_id})
        if user:
            query["posted_by_user_id"] = {"$ne": user["_id"]}

    if q and q.strip():
        import re
        escaped = re.escape(q.strip())
        query["title"] = {"$regex": escaped, "$options": "i"}

    if category_id:
        try:
            query["category_id"] = ObjectId(category_id)
        except Exception:
            cat = await db.categories.find_one({"slug": category_id})
            if cat:
                query["category_id"] = cat["_id"]
            else:
                return []
    if budget_type:
        query["budget_type"] = budget_type
    if urgency:
        query["urgency"] = urgency

    if lat is not None and lng is not None:
        query.update(build_near_sphere_query("location", lat, lng, radius_km))

    pipeline = [
        {"$match": query},
        {"$sort": {"created_at": -1}},
        {"$skip": skip},
        {"$limit": limit},
        {"$lookup": {
            "from": "categories",
            "localField": "category_id",
            "foreignField": "_id",
            "as": "_category",
        }},
        {"$addFields": {
            "category_slug": {"$arrayElemAt": ["$_category.slug", 0]},
        }},
    ]
    cursor = db.jobs.aggregate(pipeline)
    return [job_doc_to_response(doc) async for doc in cursor]


@router.get("/mine", response_model=list[JobResponse])
async def my_jobs(
    status: Optional[str] = None,
    limit: int = Query(default=20, le=50),
    skip: int = Query(default=0, ge=0),
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query: dict = {"posted_by_user_id": user["_id"]}
    if status:
        query["status"] = status

    cursor = db.jobs.find(query).sort("created_at", -1).skip(skip).limit(limit)
    return [job_doc_to_response(doc) async for doc in cursor]


@router.get("/assigned-to-me", response_model=list[JobResponse])
async def assigned_to_me(
    limit: int = Query(default=20, le=50),
    skip: int = Query(default=0, ge=0),
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = {"assigned_to_user_id": user["_id"], "status": "assigned"}
    cursor = db.jobs.find(query).sort("updated_at", -1).skip(skip).limit(limit)

    jobs = []
    async for doc in cursor:
        poster = await db.users.find_one({"_id": doc["posted_by_user_id"]})
        poster_name = poster.get("full_name") if poster else None
        jobs.append(job_doc_to_response(doc, poster_name=poster_name))
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    try:
        oid = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = await db.jobs.find_one({"_id": oid})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    poster = await db.users.find_one({"_id": job["posted_by_user_id"]})
    poster_name = None
    if poster:
        poster_name = poster.get("full_name")
        if not job.get("posted_by_clerk_id"):
            job["posted_by_clerk_id"] = poster.get("clerk_user_id")

    poster_profile = await db.service_profiles.find_one({"user_id": job["posted_by_user_id"]})
    job["poster_rating_avg"] = poster_profile.get("rating_avg", 0.0) if poster_profile else 0.0
    job["poster_rating_count"] = poster_profile.get("rating_count", 0) if poster_profile else 0

    is_own_job = job.get("posted_by_clerk_id") == clerk_user_id
    if not is_own_job:
        already_viewed = await db.job_views.find_one(
            {"job_id": oid, "clerk_user_id": clerk_user_id}
        )
        if not already_viewed:
            await db.job_views.insert_one(
                {"job_id": oid, "clerk_user_id": clerk_user_id}
            )
            await db.jobs.update_one({"_id": oid}, {"$inc": {"view_count": 1}})
            job["view_count"] = job.get("view_count", 0) + 1

    return job_doc_to_response(job, poster_name=poster_name)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    updates: JobUpdate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["posted_by_user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if job["status"] != "open":
        raise HTTPException(status_code=400, detail="Only open jobs can be edited")

    update_data = updates.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.jobs.update_one({"_id": job["_id"]}, {"$set": update_data})

    updated = await db.jobs.find_one({"_id": job["_id"]})
    return job_doc_to_response(updated)


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["posted_by_user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.jobs.update_one(
        {"_id": job["_id"]},
        {"$set": {"status": "cancelled", "updated_at": datetime.utcnow()}},
    )
    await db.conversations.update_many(
        {"job_id": job["_id"]},
        {"$set": {"is_disabled": True}},
    )
    return {"message": "Job cancelled"}


@router.post("/{job_id}/assign")
async def assign_job(
    job_id: str,
    conversation_id: str = Query(...),
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    oid = ObjectId(job_id)
    job = await db.jobs.find_one({"_id": oid})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["posted_by_user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if job["status"] not in ("open", "assigned"):
        raise HTTPException(status_code=400, detail="Job cannot be assigned in current status")

    conv_oid = ObjectId(conversation_id)
    conv = await db.conversations.find_one({"_id": conv_oid})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    assigned_user_id = (
        conv["responder_user_id"]
        if conv["poster_user_id"] == user["_id"]
        else conv["poster_user_id"]
    )

    assigned_user = await db.users.find_one({"_id": assigned_user_id})
    worker_name = assigned_user.get("full_name", "Worker") if assigned_user else "Worker"

    now = datetime.utcnow()

    await db.jobs.update_one(
        {"_id": oid},
        {"$set": {
            "status": "assigned",
            "assigned_to_user_id": assigned_user_id,
            "assigned_conversation_id": conv_oid,
            "updated_at": now,
        }},
    )

    await db.conversations.update_many(
        {"job_id": oid, "_id": {"$ne": conv_oid}},
        {"$set": {"is_disabled": True}},
    )
    await db.conversations.update_one(
        {"_id": conv_oid},
        {"$set": {"is_assigned": True}},
    )

    system_msg = {
        "conversation_id": conv_oid,
        "sender_user_id": None,
        "message_type": "system",
        "text": f"Job assigned to {worker_name}.",
        "is_read": False,
        "created_at": now,
    }
    await db.messages.insert_one(system_msg)

    other_convs = await db.conversations.find(
        {"job_id": oid, "_id": {"$ne": conv_oid}}
    ).to_list(length=None)
    if other_convs:
        closed_msgs = [
            {
                "conversation_id": c["_id"],
                "sender_user_id": None,
                "message_type": "system",
                "text": "This job has been assigned to someone else. This conversation is now closed.",
                "is_read": False,
                "created_at": now,
            }
            for c in other_convs
        ]
        await db.messages.insert_many(closed_msgs)

    import asyncio
    asyncio.create_task(notify_job_assigned(job, assigned_user_id))

    return {"message": "Job assigned", "assigned_to_user_id": str(assigned_user_id)}


@router.post("/{job_id}/hide")
async def hide_job(
    job_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        oid = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = await db.jobs.find_one({"_id": oid})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["posted_by_user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if job["status"] != "open":
        raise HTTPException(
            status_code=400,
            detail="Only unassigned open jobs can be hidden",
        )

    now = datetime.utcnow()
    await db.jobs.update_one(
        {"_id": oid},
        {"$set": {"status": "hidden", "updated_at": now}},
    )
    await db.conversations.update_many(
        {"job_id": oid},
        {"$set": {"is_disabled": True}},
    )
    return {"message": "Job hidden"}


@router.post("/{job_id}/unhide")
async def unhide_job(
    job_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        oid = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = await db.jobs.find_one({"_id": oid})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["posted_by_user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if job["status"] != "hidden":
        raise HTTPException(status_code=400, detail="Only hidden jobs can be unhidden")

    now = datetime.utcnow()
    await db.jobs.update_one(
        {"_id": oid},
        {"$set": {"status": "open", "updated_at": now}},
    )
    await db.conversations.update_many(
        {"job_id": oid, "is_assigned": False},
        {"$set": {"is_disabled": False}},
    )
    return {"message": "Job unhidden"}


@router.post("/{job_id}/reopen")
async def reopen_job(
    job_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    oid = ObjectId(job_id)
    job = await db.jobs.find_one({"_id": oid})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["posted_by_user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if job["status"] != "assigned":
        raise HTTPException(status_code=400, detail="Only assigned jobs can be reopened")

    now = datetime.utcnow()

    await db.jobs.update_one(
        {"_id": oid},
        {"$set": {
            "status": "open",
            "assigned_to_user_id": None,
            "assigned_conversation_id": None,
            "updated_at": now,
        }},
    )

    await db.conversations.update_many(
        {"job_id": oid},
        {"$set": {"is_disabled": False, "is_assigned": False}},
    )

    import asyncio
    asyncio.create_task(notify_job_reopened(job))

    return {"message": "Job reopened"}


@router.post("/{job_id}/complete")
async def complete_job(
    job_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    oid = ObjectId(job_id)
    job = await db.jobs.find_one({"_id": oid})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["posted_by_user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if job["status"] != "assigned":
        raise HTTPException(status_code=400, detail="Only assigned jobs can be completed")

    now = datetime.utcnow()
    await db.jobs.update_one(
        {"_id": oid},
        {"$set": {"status": "completed", "updated_at": now}},
    )

    assigned_user_id = job.get("assigned_to_user_id")
    if assigned_user_id:
        completed_count = await db.jobs.count_documents(
            {"assigned_to_user_id": assigned_user_id, "status": "completed"}
        )
        await db.service_profiles.update_one(
            {"user_id": assigned_user_id},
            {
                "$set": {"jobs_completed": completed_count},
                "$setOnInsert": {"user_id": assigned_user_id, "created_at": now},
            },
            upsert=True,
        )

    return {"message": "Job completed"}

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.models.review import ReviewCreate, ReviewResponse, review_doc_to_response
from app.services.spam_service import contains_abusive_content

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=ReviewResponse, status_code=201)
async def create_review(
    data: ReviewCreate,
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
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before reviewing")

    poster_id = job["posted_by_user_id"]
    assigned_id = job.get("assigned_to_user_id")
    if user["_id"] not in (poster_id, assigned_id):
        raise HTTPException(status_code=403, detail="Only poster or assigned user can review")

    reviewed_oid = ObjectId(data.reviewed_user_id)
    if reviewed_oid == user["_id"]:
        raise HTTPException(status_code=400, detail="Cannot review yourself")

    existing = await db.reviews.find_one({
        "job_id": job_oid,
        "reviewer_user_id": user["_id"],
    })
    if existing:
        raise HTTPException(status_code=409, detail="Already reviewed for this job")

    is_public = True
    if data.comment and contains_abusive_content(data.comment):
        is_public = False

    now = datetime.utcnow()
    doc = {
        "job_id": job_oid,
        "reviewer_user_id": user["_id"],
        "reviewer_name": user.get("full_name", ""),
        "reviewed_user_id": reviewed_oid,
        "rating": data.rating,
        "comment": data.comment,
        "is_public": is_public,
        "created_at": now,
    }
    result = await db.reviews.insert_one(doc)
    doc["_id"] = result.inserted_id

    pipeline = [
        {"$match": {"reviewed_user_id": reviewed_oid, "is_public": True}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]
    agg = await db.reviews.aggregate(pipeline).to_list(1)
    if agg:
        await db.service_profiles.update_one(
            {"user_id": reviewed_oid},
            {"$set": {"rating_avg": round(agg[0]["avg"], 2), "rating_count": agg[0]["count"]}},
        )

    return review_doc_to_response(doc)


@router.get("/user/{user_id}", response_model=list[ReviewResponse])
async def get_user_reviews(
    user_id: str,
    limit: int = Query(default=20, le=50),
    skip: int = Query(default=0, ge=0),
):
    db = get_db()
    cursor = (
        db.reviews.find({"reviewed_user_id": ObjectId(user_id), "is_public": True})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return [review_doc_to_response(doc) async for doc in cursor]

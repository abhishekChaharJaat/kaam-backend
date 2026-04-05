from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from bson import ObjectId
from typing import Optional

from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.models.service_profile import (
    ServiceProfileCreate,
    ServiceProfileUpdate,
    ServiceProfileResponse,
    service_profile_doc_to_response,
)

router = APIRouter(prefix="/service-profiles", tags=["service-profiles"])


@router.post("", response_model=ServiceProfileResponse)
async def create_service_profile(
    data: ServiceProfileCreate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await db.service_profiles.find_one({"user_id": user["_id"]})
    if existing:
        raise HTTPException(status_code=409, detail="Service profile already exists")

    profile_doc = {
        "user_id": user["_id"],
        **data.model_dump(),
        "category_ids": [ObjectId(c) for c in data.category_ids],
        "subcategory_ids": [ObjectId(c) for c in data.subcategory_ids] if data.subcategory_ids else [],
        "is_available": True,
        "is_verified": False,
        "rating_avg": 0.0,
        "rating_count": 0,
        "jobs_completed": 0,
        "work_images": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = await db.service_profiles.insert_one(profile_doc)
    profile_doc["_id"] = result.inserted_id
    return service_profile_doc_to_response(profile_doc)


@router.get("/{user_id}", response_model=ServiceProfileResponse)
async def get_service_profile(user_id: str):
    db = get_db()
    try:
        profile = await db.service_profiles.find_one({"user_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    if not profile:
        raise HTTPException(status_code=404, detail="Service profile not found")

    return service_profile_doc_to_response(profile)


@router.patch("/{user_id}", response_model=ServiceProfileResponse)
async def update_service_profile(
    user_id: str,
    updates: ServiceProfileUpdate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user or str(user["_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    profile = await db.service_profiles.find_one({"user_id": user["_id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Service profile not found")

    update_data = updates.model_dump(exclude_unset=True)
    if "category_ids" in update_data and update_data["category_ids"]:
        update_data["category_ids"] = [ObjectId(c) for c in update_data["category_ids"]]
    if "subcategory_ids" in update_data and update_data["subcategory_ids"]:
        update_data["subcategory_ids"] = [ObjectId(c) for c in update_data["subcategory_ids"]]

    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.service_profiles.update_one(
            {"_id": profile["_id"]},
            {"$set": update_data},
        )

    updated = await db.service_profiles.find_one({"_id": profile["_id"]})
    return service_profile_doc_to_response(updated)


@router.get("/search", response_model=list[ServiceProfileResponse])
async def search_service_profiles(
    category_id: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: int = 10,
    available_now: Optional[bool] = None,
    min_rating: Optional[float] = None,
    limit: int = Query(default=20, le=50),
    skip: int = Query(default=0, ge=0),
):
    db = get_db()

    pipeline: list[dict] = []
    match_stage: dict = {}

    if category_id:
        match_stage["category_ids"] = ObjectId(category_id)

    if available_now:
        match_stage["availability.is_available_now"] = True

    if min_rating:
        match_stage["rating_avg"] = {"$gte": min_rating}

    if lat is not None and lng is not None:
        pipeline.append({
            "$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user",
            }
        })
        pipeline.append({"$unwind": "$user"})
        pipeline.append({
            "$match": {
                "user.location": {
                    "$nearSphere": {
                        "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                        "$maxDistance": radius_km * 1000,
                    }
                },
                "user.is_active": True,
            }
        })

    if match_stage:
        pipeline.insert(0, {"$match": match_stage})

    pipeline.extend([{"$skip": skip}, {"$limit": limit}])

    results = []
    async for doc in db.service_profiles.aggregate(pipeline):
        if "user" in doc:
            del doc["user"]
        results.append(service_profile_doc_to_response(doc))

    return results

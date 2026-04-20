from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.models.user import (
    UserUpdate,
    UserResponse,
    UserPublicResponse,
    user_doc_to_response,
    user_doc_to_public,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_own_profile(clerk_user_id: str = Depends(get_current_user_id)):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user_doc_to_response(user)


@router.patch("/me", response_model=UserResponse)
async def update_own_profile(
    updates: UserUpdate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = updates.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        if "location" in update_data and update_data["location"]:
            loc = update_data["location"]
            update_data["location"] = {
                "type": loc.get("type", "Point") if isinstance(loc, dict) else loc.type,
                "coordinates": loc.get("coordinates", [0.0, 0.0]) if isinstance(loc, dict) else loc.coordinates,
            }

        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": update_data},
        )

    updated = await db.users.find_one({"_id": user["_id"]})
    return user_doc_to_response(updated)


@router.get("/{user_id}", response_model=UserPublicResponse)
async def get_public_profile(user_id: str):
    db = get_db()
    try:
        oid = ObjectId(user_id)
        user = await db.users.find_one({"_id": oid, "is_active": True})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = await db.service_profiles.find_one({"user_id": oid})
    resp = user_doc_to_public(user)
    if profile:
        resp.headline = profile.get("headline")
        resp.experience_years = profile.get("experience_years")
        resp.skills = [str(s) for s in profile.get("skills", [])]

    # Always compute rating from the reviews collection so the number reflects
    # real data even for users who don't have a service profile yet.
    rating_pipeline = [
        {"$match": {"reviewed_user_id": oid, "is_public": True}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]
    agg = await db.reviews.aggregate(rating_pipeline).to_list(1)
    if agg:
        resp.rating_avg = round(float(agg[0]["avg"]), 2)
        resp.rating_count = int(agg[0]["count"])
    else:
        resp.rating_avg = 0.0
        resp.rating_count = 0

    # Compute jobs_completed live from the jobs collection so it always
    # reflects reality regardless of whether the cache has been kept in sync.
    resp.jobs_completed = await db.jobs.count_documents(
        {"assigned_to_user_id": oid, "status": "completed"}
    )

    return resp


@router.post("/me/push-token")
async def save_push_token(
    body: dict,
    clerk_user_id: str = Depends(get_current_user_id),
):
    token = body.get("expo_push_token")
    if not token:
        raise HTTPException(status_code=400, detail="expo_push_token is required")
    platform = body.get("platform")
    db = get_db()

    new_fields: dict = {"expo_push_token": token}
    if platform:
        new_fields["platform"] = platform

    # Use an aggregation-pipeline update so it works whether `device_info`
    # is missing, null, or already an object (a plain dotted-path $set
    # fails with "Cannot create field … in element {device_info: null}").
    result = await db.users.update_one(
        {"clerk_user_id": clerk_user_id},
        [
            {
                "$set": {
                    "device_info": {
                        "$mergeObjects": [
                            {
                                "$cond": [
                                    {"$eq": [{"$type": "$device_info"}, "object"]},
                                    "$device_info",
                                    {},
                                ]
                            },
                            new_fields,
                        ]
                    },
                    "updated_at": datetime.utcnow(),
                }
            }
        ],
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Push token saved"}


@router.delete("/me")
async def soft_delete_account(clerk_user_id: str = Depends(get_current_user_id)):
    db = get_db()
    result = await db.users.update_one(
        {"clerk_user_id": clerk_user_id},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Account deactivated"}

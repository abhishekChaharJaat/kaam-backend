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
        resp.rating_avg = profile.get("rating_avg", 0.0)
        resp.rating_count = profile.get("rating_count", 0)
        resp.headline = profile.get("headline")
        resp.experience_years = profile.get("experience_years")
        resp.jobs_completed = profile.get("jobs_completed", 0)
        resp.skills = [str(s) for s in profile.get("skills", [])]
    return resp


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

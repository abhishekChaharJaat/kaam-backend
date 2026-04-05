from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.middleware.auth import get_current_user_id

router = APIRouter(prefix="/saved-users", tags=["saved-users"])


@router.post("", status_code=201)
async def save_user(
    saved_user_id: str = Query(...),
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    saved_oid = ObjectId(saved_user_id)
    if saved_oid == user["_id"]:
        raise HTTPException(status_code=400, detail="Cannot save yourself")

    existing = await db.saved_users.find_one({
        "user_id": user["_id"],
        "saved_user_id": saved_oid,
    })
    if existing:
        return {"message": "Already saved", "id": str(existing["_id"])}

    doc = {
        "user_id": user["_id"],
        "saved_user_id": saved_oid,
        "created_at": datetime.utcnow(),
    }
    result = await db.saved_users.insert_one(doc)
    return {"message": "User saved", "id": str(result.inserted_id)}


@router.delete("/{saved_entry_id}")
async def unsave_user(
    saved_entry_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.saved_users.delete_one({
        "_id": ObjectId(saved_entry_id),
        "user_id": user["_id"],
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Saved entry not found")

    return {"message": "User unsaved"}


@router.get("")
async def list_saved_users(
    limit: int = Query(default=20, le=50),
    skip: int = Query(default=0, ge=0),
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    pipeline = [
        {"$match": {"user_id": user["_id"]}},
        {"$sort": {"created_at": -1}},
        {"$skip": skip},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "users",
                "localField": "saved_user_id",
                "foreignField": "_id",
                "as": "saved_user",
            }
        },
        {"$unwind": "$saved_user"},
        {
            "$project": {
                "id": {"$toString": "$_id"},
                "saved_user_id": {"$toString": "$saved_user_id"},
                "full_name": "$saved_user.full_name",
                "profile_photo_url": "$saved_user.profile_photo_url",
                "city": "$saved_user.city",
                "created_at": 1,
            }
        },
    ]
    results = await db.saved_users.aggregate(pipeline).to_list(limit)
    return results

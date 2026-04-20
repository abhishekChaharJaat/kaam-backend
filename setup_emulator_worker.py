"""One-shot: turn the emulator user into a worker for category 69e322bacae1dd1053a25a8f.

Looks up the user by their Expo push token, sets find_work + range,
and ensures a service_profile exists with the target category.
"""
import asyncio
from datetime import datetime
from bson import ObjectId

from app.database import connect_db, get_db, close_db


EMULATOR_PUSH_TOKEN = "ExponentPushToken[PfHsBTMiCXSN1XIpe406OJ]"
TARGET_CATEGORY_ID = ObjectId("69e322bacae1dd1053a25a8f")


async def main():
    await connect_db()
    db = get_db()

    user = await db.users.find_one(
        {"device_info.expo_push_token": EMULATOR_PUSH_TOKEN}
    )
    if not user:
        print(f"No user found with token {EMULATOR_PUSH_TOKEN}")
        await close_db()
        return

    print(f"Found user: {user.get('full_name')!r}  _id={user['_id']}")
    print(f"  current usage_preference={user.get('usage_preference')!r}")
    print(f"  current work_range_km={user.get('work_range_km')!r}")
    print(f"  current is_active={user.get('is_active')!r}")

    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "usage_preference": "find_work",
                "work_range_km": 50,
                "is_active": True,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    now = datetime.utcnow()
    res = await db.service_profiles.update_one(
        {"user_id": user["_id"]},
        {
            "$setOnInsert": {
                "user_id": user["_id"],
                "subcategory_ids": [],
                "is_available": True,
                "is_verified": False,
                "rating_avg": 0.0,
                "rating_count": 0,
                "jobs_completed": 0,
                "work_images": [],
                "created_at": now,
            },
            "$addToSet": {"category_ids": TARGET_CATEGORY_ID},
            "$set": {"updated_at": now},
        },
        upsert=True,
    )
    print(
        f"  service_profile upsert: matched={res.matched_count} "
        f"modified={res.modified_count} upserted_id={res.upserted_id}"
    )

    profile = await db.service_profiles.find_one({"user_id": user["_id"]})
    print(f"\nFinal profile category_ids: {profile.get('category_ids')}")
    print(
        f"Final user state: usage_preference="
        f"{(await db.users.find_one({'_id': user['_id']})).get('usage_preference')!r}"
    )

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())

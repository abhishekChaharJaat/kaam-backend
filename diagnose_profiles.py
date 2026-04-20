"""Quick diagnostic: print all service_profiles and their category_ids.

Run from kaam-backend dir with the .venv activated:
    python diagnose_profiles.py
"""
import asyncio
from app.database import connect_db, get_db, close_db


async def main():
    await connect_db()
    db = get_db()

    target_category = "69e322bacae1dd1053a25a8f"

    profiles = await db.service_profiles.find(
        {}, {"user_id": 1, "category_ids": 1}
    ).to_list(length=None)
    print(f"\nTotal service_profiles in DB: {len(profiles)}\n")

    for p in profiles:
        cats = p.get("category_ids") or []
        cats_repr = [f"{type(c).__name__}({c})" for c in cats]
        user = await db.users.find_one(
            {"_id": p["user_id"]},
            {"full_name": 1, "usage_preference": 1, "is_active": 1,
             "device_info.expo_push_token": 1, "work_range_km": 1},
        )
        print(f"--- profile {p['_id']}")
        print(f"  user_id     : {type(p['user_id']).__name__}({p['user_id']})")
        print(f"  category_ids: {cats_repr}")
        if user:
            print(f"  user.name        : {user.get('full_name')!r}")
            print(f"  usage_preference : {user.get('usage_preference')!r}")
            print(f"  is_active        : {user.get('is_active')!r}")
            print(f"  work_range_km    : {user.get('work_range_km')!r}")
            print(f"  expo_push_token  : "
                  f"{(user.get('device_info') or {}).get('expo_push_token')!r}")
        else:
            print("  USER MISSING for this profile")

    print(f"\nLooking up users who have a service_profile matching "
          f"category_id={target_category}")
    from bson import ObjectId
    matched = await db.service_profiles.find(
        {"category_ids": ObjectId(target_category)}
    ).to_list(length=None)
    print(f"Match count: {len(matched)}")
    for m in matched:
        print(f"  -> profile {m['_id']} user_id {m['user_id']}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())

from datetime import datetime, timedelta
from bson import ObjectId


async def check_daily_job_limit(db, user_id: ObjectId, max_per_day: int = 3) -> bool:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count = await db.jobs.count_documents({
        "posted_by_user_id": user_id,
        "created_at": {"$gte": today_start},
        "status": {"$ne": "cancelled"},
    })
    return count < max_per_day


async def check_duplicate_job(db, user_id: ObjectId, title: str, category_id: ObjectId) -> bool:
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    dup = await db.jobs.find_one({
        "posted_by_user_id": user_id,
        "title": title,
        "category_id": category_id,
        "created_at": {"$gte": one_hour_ago},
        "status": {"$ne": "cancelled"},
    })
    return dup is not None


ABUSIVE_KEYWORDS = [
    "spam", "scam", "fraud",
]


def contains_abusive_content(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in ABUSIVE_KEYWORDS)

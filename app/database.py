from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    _db = _client[settings.MONGODB_DB_NAME]
    await create_indexes()


async def close_db() -> None:
    global _client
    if _client:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db


async def create_indexes() -> None:
    db = get_db()

    await db.users.create_index("clerk_user_id", unique=True)
    await db.users.create_index([("location", "2dsphere")])

    await db.service_profiles.create_index("user_id", unique=True)
    await db.service_profiles.create_index([("category_ids", 1), ("is_available", 1)])

    await db.jobs.create_index([("location", "2dsphere")])
    await db.jobs.create_index([("category_id", 1), ("status", 1)])
    await db.jobs.create_index("posted_by_user_id")

    await db.conversations.create_index(
        [("job_id", 1), ("poster_user_id", 1), ("responder_user_id", 1)],
        unique=True,
    )
    await db.conversations.create_index("poster_user_id")
    await db.conversations.create_index("responder_user_id")

    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])

    await db.notifications.create_index(
        [("user_id", 1), ("is_read", 1), ("created_at", -1)]
    )

    await db.reviews.create_index("reviewed_user_id")

    await db.categories.create_index("slug", unique=True)
    await db.subcategories.create_index("category_id")

    await db.reports.create_index("reported_by_user_id")
    await db.reports.create_index("target_user_id")

    await db.saved_users.create_index(
        [("user_id", 1), ("saved_user_id", 1)], unique=True
    )

    await db.job_views.create_index(
        [("job_id", 1), ("clerk_user_id", 1)], unique=True
    )

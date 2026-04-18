from fastapi import APIRouter, Depends, Request
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import httpx

from app.database import get_db
from app.middleware.auth import verify_clerk_jwt, get_current_user_id
from app.middleware.rate_limit import check_rate_limit, get_client_ip
from app.models.user import UserResponse, user_doc_to_response
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class SyncBody(BaseModel):
    full_name: Optional[str] = None


async def _fetch_clerk_user_name(clerk_user_id: str) -> Optional[str]:
    settings = get_settings()
    if not settings.CLERK_SECRET_KEY:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.clerk.com/v1/users/{clerk_user_id}",
                headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                first = data.get("first_name") or ""
                last = data.get("last_name") or ""
                name = f"{first} {last}".strip()
                return name if name else None
    except Exception:
        pass
    return None


@router.post("/sync-clerk-user", response_model=UserResponse)
async def sync_clerk_user(
    request: Request,
    payload: dict = Depends(verify_clerk_jwt),
    body: SyncBody = SyncBody(),
):
    settings = get_settings()
    db = get_db()
    clerk_user_id = payload.get("sub", "")

    resolved_name = (
        body.full_name.strip() if body.full_name and body.full_name.strip() else None
    )

    existing = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if existing:
        update_fields: dict = {"last_seen_at": datetime.utcnow()}
        current_name = existing.get("full_name", "User")
        if current_name in ("User", "", None):
            best_name = resolved_name or await _fetch_clerk_user_name(clerk_user_id)
            if best_name:
                update_fields["full_name"] = best_name
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": update_fields},
        )
        existing.update(update_fields)
        return user_doc_to_response(existing)

    # Only rate-limit the expensive path: creating a brand-new user doc.
    # Existing-user heartbeats above should never burn the quota.
    client_ip = get_client_ip(request)
    check_rate_limit(
        f"auth_sync_create:{client_ip}",
        max_requests=settings.RATE_LIMIT_AUTH_PER_HOUR,
        window_seconds=3600,
    )

    email = payload.get("email", payload.get("email_address", ""))
    if not resolved_name:
        resolved_name = await _fetch_clerk_user_name(clerk_user_id)
    full_name = resolved_name or payload.get("name", payload.get("first_name", "User"))

    new_user = {
        "clerk_user_id": clerk_user_id,
        "full_name": full_name,
        "email": email,
        "phone": None,
        "profile_photo_url": None,
        "usage_preference": "find_worker",
        "is_active": True,
        "is_blocked": False,
        "language": "hi",
        "city": None,
        "state": None,
        "country": "India",
        "locality": None,
        "location": {"type": "Point", "coordinates": [0.0, 0.0]},
        "address_line": None,
        "device_info": None,
        "last_seen_at": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = await db.users.insert_one(new_user)
    new_user["_id"] = result.inserted_id
    return user_doc_to_response(new_user)


@router.get("/me", response_model=UserResponse)
async def get_me(clerk_user_id: str = Depends(get_current_user_id)):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found. Call /auth/sync-clerk-user first.")
    return user_doc_to_response(user)

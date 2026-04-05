from fastapi import Request, HTTPException
from collections import defaultdict
from datetime import datetime, timedelta

_rate_limit_store: dict[str, list[datetime]] = defaultdict(list)


def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int = 3600,
) -> None:
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)

    _rate_limit_store[key] = [
        ts for ts in _rate_limit_store[key] if ts > cutoff
    ]

    if len(_rate_limit_store[key]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {max_requests} requests per {window_seconds}s.",
        )

    _rate_limit_store[key].append(now)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

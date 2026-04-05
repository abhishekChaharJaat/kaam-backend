from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.models.report import ReportCreate, ReportResponse, report_doc_to_response

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse, status_code=201)
async def create_report(
    data: ReportCreate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    user = await db.users.find_one({"clerk_user_id": clerk_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    target_oid = ObjectId(data.target_user_id)
    if target_oid == user["_id"]:
        raise HTTPException(status_code=400, detail="Cannot report yourself")

    doc = {
        "reported_by_user_id": user["_id"],
        "target_user_id": target_oid,
        "job_id": ObjectId(data.job_id) if data.job_id else None,
        "reason": data.reason,
        "description": data.description,
        "status": "open",
        "created_at": datetime.utcnow(),
    }
    result = await db.reports.insert_one(doc)
    doc["_id"] = result.inserted_id
    return report_doc_to_response(doc)

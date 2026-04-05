from fastapi import APIRouter, HTTPException
from bson import ObjectId

from app.database import get_db
from app.models.category import (
    CategoryResponse,
    SubcategoryResponse,
    category_doc_to_response,
    subcategory_doc_to_response,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories():
    db = get_db()
    cursor = db.categories.find({"is_active": True}).sort("sort_order", 1)
    return [category_doc_to_response(doc) async for doc in cursor]


@router.get("/{category_id}/subcategories", response_model=list[SubcategoryResponse])
async def list_subcategories(category_id: str):
    db = get_db()
    try:
        oid = ObjectId(category_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid category ID")

    cursor = db.subcategories.find({"category_id": oid, "is_active": True})
    return [subcategory_doc_to_response(doc) async for doc in cursor]

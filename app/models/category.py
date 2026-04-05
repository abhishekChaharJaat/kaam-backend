from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    icon_url: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class SubcategoryResponse(BaseModel):
    id: str
    category_id: str
    name: str
    slug: str
    is_active: bool = True


def category_doc_to_response(doc: dict) -> CategoryResponse:
    return CategoryResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        slug=doc["slug"],
        icon_url=doc.get("icon_url"),
        is_active=doc.get("is_active", True),
        sort_order=doc.get("sort_order", 0),
    )


def subcategory_doc_to_response(doc: dict) -> SubcategoryResponse:
    return SubcategoryResponse(
        id=str(doc["_id"]),
        category_id=str(doc["category_id"]),
        name=doc["name"],
        slug=doc["slug"],
        is_active=doc.get("is_active", True),
    )

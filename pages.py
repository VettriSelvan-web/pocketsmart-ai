"""HTML pages + history / recommendation-details endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from .. import database, security
from ..templating import templates

router = APIRouter()
VALID_CATEGORIES = {"home", "party", "jewelry"}


@router.get("/")
async def index(request: Request, user=Depends(security.get_optional_user)):
    return templates.TemplateResponse(request, "index.html", {"user": user})


@router.get("/testimonials")
async def testimonials():
    return RedirectResponse("/#testimonials", status_code=307)


@router.get("/dashboard")
async def dashboard(request: Request, user=Depends(security.require_user_page)):
    recent = database.list_recommendations(user["id"], limit=5)
    counts = database.count_by_category(user["id"])
    return templates.TemplateResponse(
        request, "dashboard.html",
        {"user": user, "recent": recent, "counts": counts, "total": sum(counts.values())},
    )


@router.get("/home-planner")
async def home_planner(request: Request, user=Depends(security.require_user_page)):
    return templates.TemplateResponse(request, "home_planner.html", {"user": user})


@router.get("/party-planner")
async def party_planner(request: Request, user=Depends(security.require_user_page)):
    return templates.TemplateResponse(request, "party_planner.html", {"user": user})


@router.get("/jewelry-planner")
async def jewelry_planner(request: Request, user=Depends(security.require_user_page)):
    return templates.TemplateResponse(request, "jewelry_planner.html", {"user": user})


@router.get("/history")
async def history(request: Request, category: Optional[str] = None, user=Depends(security.require_user_page)):
    if category not in VALID_CATEGORIES:
        category = None
    items = database.list_recommendations(user["id"], category)
    return templates.TemplateResponse(
        request, "history.html", {"user": user, "items": items, "category": category}
    )


@router.post("/history/{rec_id}/delete")
async def delete_history(rec_id: int, user=Depends(security.require_user_page)):
    database.delete_recommendation(rec_id, user["id"])
    return RedirectResponse("/history", status_code=303)


@router.get("/recommendations/{rec_id}")
async def recommendation_page(rec_id: int, request: Request, user=Depends(security.require_user_page)):
    rec = database.get_recommendation(rec_id, user["id"])
    if not rec:
        raise HTTPException(404, "Recommendation not found")
    return templates.TemplateResponse(request, "recommendation.html", {"user": user, "rec": rec})


@router.get("/recommendations-details")
async def recommendation_details(
    id: Optional[int] = None,
    category: Optional[str] = None,
    limit: int = 20,
    user=Depends(security.require_user),
):
    """JSON access to saved recommendations (one by id, or a filtered list)."""
    if id is not None:
        rec = database.get_recommendation(id, user["id"])
        if not rec:
            raise HTTPException(404, "Recommendation not found")
        return rec
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(400, "category must be one of: home, party, jewelry")
    return database.list_recommendations(user["id"], category, limit=max(1, min(limit, 100)))


@router.get("/api/history")
async def history_json(category: Optional[str] = None, user=Depends(security.require_user)):
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(400, "category must be one of: home, party, jewelry")
    return database.list_recommendations(user["id"], category)

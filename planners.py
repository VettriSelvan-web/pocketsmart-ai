"""AI planner endpoints: /generate-home, /generate-party, /generate-jewelry."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from .. import database, security
from ..schemas import HomeRequest, JewelryRequest, PartyRequest
from ..services import gemini_utils
from ..services.images import process_upload

logger = logging.getLogger("pocketsmart.planners")
router = APIRouter()


def _response(rec_id: int, source: str, result: dict) -> dict:
    return {"id": rec_id, "redirect": f"/recommendations/{rec_id}", "source": source, "result": result}


@router.post("/generate-home")
async def generate_home(payload: HomeRequest, user=Depends(security.require_user)):
    data = payload.model_dump()
    result, source = await gemini_utils.generate("home", data)
    rooms = ", ".join(r["room_type"] for r in data["rooms"])
    title = f"Home plan: {rooms}"[:120]
    rec_id = database.save_recommendation(user["id"], "home", title, payload.budget, data, result, source)
    return _response(rec_id, source, result)


@router.post("/generate-party")
async def generate_party(payload: PartyRequest, user=Depends(security.require_user)):
    data = payload.model_dump()
    result, source = await gemini_utils.generate("party", data)
    title = f"{payload.event_type.title()} for {payload.guests} guests"[:120]
    rec_id = database.save_recommendation(user["id"], "party", title, payload.budget, data, result, source)
    return _response(rec_id, source, result)


@router.post("/generate-jewelry")
async def generate_jewelry(
    budget: float = Form(...),
    occasion: str = Form(...),
    style: str = Form(""),
    metal: str = Form("Any"),
    notes: str = Form(""),
    outfit_image: Optional[UploadFile] = File(None),
    user=Depends(security.require_user),
):
    try:
        payload = JewelryRequest(budget=budget, occasion=occasion, style=style, metal=metal, notes=notes)
    except ValidationError as exc:
        raise HTTPException(422, "; ".join(e["msg"] for e in exc.errors()))

    upload = await process_upload(outfit_image)
    image_bytes, image_url = upload if upload else (None, None)

    data = payload.model_dump()
    data["image_url"] = image_url
    result, source = await gemini_utils.generate("jewelry", data, image_bytes)
    title = f"Jewelry for {payload.occasion.lower()}"[:120]
    rec_id = database.save_recommendation(user["id"], "jewelry", title, payload.budget, data, result, source)
    return _response(rec_id, source, result)

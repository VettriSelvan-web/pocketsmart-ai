"""Gemini integration: prompt building, API call, JSON parsing and normalisation.

Everything AI-related lives here so routes stay thin.  If Gemini is not configured
or fails for any reason, `generate()` transparently returns rule-based fallback
recommendations (project Activity 5.4) so the app keeps working.
"""
import asyncio
import json
import logging
import re
from typing import Any, Optional, Tuple

from ..config import settings
from . import catalog

logger = logging.getLogger("pocketsmart.gemini")

JSON_SCHEMA_HINT = """{
  "summary": "1-2 sentence overview of the plan",
  "sections": [
    {
      "title": "section name (room / catering / necklace ...)",
      "allocated_budget": 12000,
      "items": [
        {
          "name": "specific product or service",
          "platform": "one of the allowed platforms",
          "quantity": 1,
          "estimated_price": 4500,
          "why": "short reason it fits"
        }
      ]
    }
  ],
  "tips": ["short money-saving tip", "another tip"]
}"""

COMMON_RULES = f"""
Rules:
- All money is in Indian Rupees (INR). Use plain numbers (no symbols, no commas).
- "estimated_price" is the price of ONE unit. The cost of an item = estimated_price x quantity.
- The sum of every (estimated_price x quantity) MUST NOT exceed the total budget.
- "allocated_budget" values across sections should add up to at most the total budget.
- Give 1-3 realistic items per section. Do NOT invent URLs.
- Respond with ONLY valid JSON matching this shape (no markdown, no commentary):
{JSON_SCHEMA_HINT}
"""


# ------------------------------------------------------------------ prompts
def build_prompt(category: str, payload: dict, has_image: bool = False) -> str:
    if category == "home":
        rooms = "\n".join(
            f"- {r['room_type']}: " + ", ".join(f"{i['quantity']} x {i['name']}" for i in r["items"])
            for r in payload["rooms"]
        )
        return f"""You are PocketSmart AI, an expert interior-design budget planner for Indian shoppers.
Total budget: INR {payload['budget']:.0f}
Preferred style: {payload.get('style') or 'no preference'}
Extra notes: {payload.get('notes') or 'none'}
Rooms and required items:
{rooms}

Task: split the budget sensibly across the rooms (one section per room) and recommend cost-effective
products for every requested item, balancing functionality, style and price.
Allowed platforms: {', '.join(catalog.HOME_PLATFORMS)}.
{COMMON_RULES}"""

    if category == "party":
        return f"""You are PocketSmart AI, an expert event planner for Indian users.
Total budget: INR {payload['budget']:.0f}
Event type: {payload['event_type']}
Guests: {payload['guests']}
Venue details: {payload.get('venue') or 'not specified'}
City: {payload.get('city') or 'not specified'}
Extra notes: {payload.get('notes') or 'none'}

Task: allocate the budget proportionally across sections "Catering", "Venue / Stay", "Decoration" and
"Entertainment", tailored to the event type. For catering use per-plate pricing with quantity = number of guests.
Allowed platforms: {', '.join(catalog.PARTY_PLATFORMS)}
(Swiggy/Zomato for food, OYO for venue or guest stays, Amazon/Flipkart for decor and entertainment supplies).
{COMMON_RULES}"""

    if category == "jewelry":
        image_line = (
            "An image of the user's outfit is attached: analyse its colours, fabric and style and "
            "recommend jewelry that coordinates with it. Mention the colours you noticed in the summary."
            if has_image else "No outfit image was provided."
        )
        return f"""You are PocketSmart AI, an expert jewelry stylist for Indian occasions.
Total budget: INR {payload['budget']:.0f}
Occasion: {payload['occasion']}
Style preference: {payload.get('style') or 'no preference'}
Preferred metal: {payload.get('metal') or 'Any'}
Extra notes: {payload.get('notes') or 'none'}
{image_line}

Task: recommend a coordinated set with one section per piece (e.g. Necklace, Earrings, Bangles, Ring).
Allowed platforms: {', '.join(catalog.JEWELRY_PLATFORMS)}.
{COMMON_RULES}"""

    raise ValueError(f"Unknown category: {category}")


# ------------------------------------------------------------------ API call
def _models_to_try() -> list[str]:
    seen, out = set(), []
    for m in [settings.GEMINI_MODEL, *settings.GEMINI_FALLBACK_MODELS]:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def call_gemini(prompt: str, image_bytes: Optional[bytes] = None) -> str:
    """Blocking call to Gemini. Tries the configured model, then the backups."""
    from google import genai  # imported lazily so the app still starts without the SDK
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    contents: list[Any] = [prompt]
    if image_bytes:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

    last_error: Optional[Exception] = None
    for model in _models_to_try():
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.4
                ),
            )
            text = (response.text or "").strip()
            if text:
                return text
            raise ValueError("empty response")
        except Exception as exc:  # noqa: BLE001 - try next model
            logger.warning("Gemini model %s failed: %s", model, exc)
            last_error = exc
    raise RuntimeError(f"All Gemini models failed: {last_error}")


# ------------------------------------------------------------------ parsing
def extract_json(text: str) -> dict:
    """Parse JSON even if the model wrapped it in markdown fences or extra prose."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("No JSON object found in model response")
        data = json.loads(cleaned[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("Model response is not a JSON object")
    return data


def _num(value: Any, default: float = 0.0) -> float:
    try:
        cleaned = re.sub(r"[^\d.\-]", "", str(value))
        return float(cleaned) if cleaned not in ("", "-", ".") else default
    except ValueError:
        return default


def normalize_result(raw: dict, budget: float) -> dict:
    """Clean model output into the exact structure the templates expect."""
    sections = []
    for s in (raw.get("sections") or [])[:12]:
        if not isinstance(s, dict):
            continue
        items = []
        for it in (s.get("items") or [])[:12]:
            if not isinstance(it, dict):
                continue
            name = str(it.get("name", "")).strip()[:140]
            if not name:
                continue
            platform = catalog.canonical_platform(it.get("platform"))
            qty = min(max(int(_num(it.get("quantity"), 1)) or 1, 1), 5000)
            price = max(_num(it.get("estimated_price")), 0.0)
            items.append({
                "name": name,
                "platform": platform,
                "quantity": qty,
                "estimated_price": round(price),
                "total": round(price * qty),
                "why": str(it.get("why", "")).strip()[:300],
                "url": catalog.search_url(platform, name),
            })
        if items:
            sections.append({
                "title": str(s.get("title", "Recommendations")).strip()[:60] or "Recommendations",
                "allocated_budget": round(max(_num(s.get("allocated_budget")), 0.0)),
                "items": items,
                "subtotal": sum(i["total"] for i in items),
            })

    tips = [str(t).strip()[:250] for t in (raw.get("tips") or []) if str(t).strip()][:6]
    estimated_total = sum(s["subtotal"] for s in sections)
    over = estimated_total > budget * 1.02
    if over:
        tips.append(
            f"Heads up: the estimated total (₹{estimated_total:,.0f}) is above your budget "
            f"(₹{budget:,.0f}). Consider dropping or downgrading some items."
        )
    return {
        "summary": str(raw.get("summary", "")).strip()[:600],
        "total_budget": round(budget),
        "estimated_total": estimated_total,
        "over_budget": over,
        "sections": sections,
        "tips": tips,
    }


def _finalize_fallback(result: dict, budget: float) -> dict:
    """Run the fallback through the same normaliser (adds totals + search links)."""
    return normalize_result(result, budget)


# ------------------------------------------------------------------ public API
async def generate(
    category: str, payload: dict, image_bytes: Optional[bytes] = None
) -> Tuple[dict, str]:
    """Return (result, source) where source is 'gemini' or 'fallback'."""
    budget = float(payload["budget"])

    if not settings.GEMINI_API_KEY:
        logger.info("No GEMINI_API_KEY configured - using fallback recommendations")
        result = _finalize_fallback(catalog.fallback(category, payload, bool(image_bytes)), budget)
        result["notice"] = "Gemini API key not configured - showing sample recommendations."
        return result, "fallback"

    try:
        prompt = build_prompt(category, payload, has_image=bool(image_bytes))
        text = await asyncio.to_thread(call_gemini, prompt, image_bytes)
        result = normalize_result(extract_json(text), budget)
        if not result["sections"]:
            raise ValueError("AI returned no usable recommendations")
        return result, "gemini"
    except Exception as exc:  # noqa: BLE001
        logger.error("Gemini generation failed, using fallback: %s", exc)
        result = _finalize_fallback(catalog.fallback(category, payload, bool(image_bytes)), budget)
        result["notice"] = "The AI service was unavailable, so sample recommendations are shown."
        return result, "fallback"

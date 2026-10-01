"""Platform catalogue, search-link builder and rule-based fallback recommendations.

The fallback ("simulated" product data, per project Activity 3.4 / 5.4) is used when
the Gemini key is missing, the API fails, or the AI returns an unusable answer.
Links are always *search* links built here - we never trust URLs produced by the LLM.
"""
from urllib.parse import quote_plus

PLATFORM_SEARCH = {
    "Amazon": "https://www.amazon.in/s?k={q}",
    "Flipkart": "https://www.flipkart.com/search?q={q}",
    "IKEA": "https://www.ikea.com/in/en/search/?q={q}",
    "Swiggy": "https://www.swiggy.com/search?query={q}",
    "Zomato": "https://www.zomato.com/search?q={q}",
    "OYO": "https://www.oyorooms.com/search?query={q}",
}
PLATFORMS = list(PLATFORM_SEARCH)

HOME_PLATFORMS = ["IKEA", "Amazon", "Flipkart"]
PARTY_PLATFORMS = ["Swiggy", "Zomato", "OYO", "Amazon", "Flipkart"]
JEWELRY_PLATFORMS = ["Amazon", "Flipkart"]


def canonical_platform(name) -> str:
    text = str(name or "").strip().lower()
    for p in PLATFORMS:
        if p.lower() == text or p.lower() in text:
            return p
    return "Amazon"


def search_url(platform: str, query: str) -> str:
    template = PLATFORM_SEARCH.get(canonical_platform(platform), PLATFORM_SEARCH["Amazon"])
    return template.format(q=quote_plus(query.strip()))


def _item(name, platform, unit_price, qty, why):
    return {
        "name": name,
        "platform": platform,
        "quantity": int(qty),
        "estimated_price": round(unit_price),
        "why": why,
    }


def _finish(summary, budget, sections, tips):
    for s in sections:
        s["allocated_budget"] = round(s["allocated_budget"])
    return {
        "summary": summary,
        "total_budget": round(budget),
        "sections": sections,
        "tips": tips,
    }


# ---------------------------------------------------------------- HOME
# relative price weight of each product type (only ratios matter)
_HOME_WEIGHTS = {
    "light": 1.0, "lamp": 1.2, "fan": 2.5, "dining": 7.0, "sofa": 9.0, "bed": 9.0,
    "wardrobe": 8.0, "table": 4.0, "chair": 2.0, "curtain": 1.5, "rug": 2.0,
    "shel": 3.0, "art": 1.2, "mirror": 1.8, "tv": 10.0,
}
_HOME_FURNITURE = ("dining", "sofa", "bed", "wardrobe", "table", "chair", "shel")


def _home_weight(name: str) -> float:
    n = name.lower()
    for key, w in _HOME_WEIGHTS.items():
        if key in n:
            return w
    return 2.0


def fallback_home(payload: dict) -> dict:
    budget = float(payload["budget"])
    rooms = payload["rooms"]
    style = payload.get("style") or "modern"
    room_units = [
        sum(_home_weight(i["name"]) * i["quantity"] for i in r["items"]) for r in rooms
    ]
    total_units = sum(room_units) or 1
    sections = []
    for room, units in zip(rooms, room_units):
        share = budget * units / total_units
        items = []
        for it in room["items"]:
            w = _home_weight(it["name"])
            unit_price = share * 0.92 * w / max(units, 1)  # keep ~8% headroom
            platform = "IKEA" if any(k in it["name"].lower() for k in _HOME_FURNITURE) else "Amazon"
            items.append(
                _item(
                    f"{style.title()} {it['name']}", platform, unit_price, it["quantity"],
                    f"Budget-friendly {it['name'].lower()} option that suits a {style.lower()} {room['room_type'].lower()}.",
                )
            )
        sections.append({"title": room["room_type"], "allocated_budget": share, "items": items})
    return _finish(
        f"A balanced {style.lower()} plan spread across {len(rooms)} room(s), weighted by how much each room needs.",
        budget, sections,
        ["Compare the same product on IKEA, Amazon and Flipkart before buying.",
         "Look out for festive-season sales to save 10-30% on furniture.",
         "Buy lighting and fans first - they affect daily comfort the most."],
    )


# ---------------------------------------------------------------- PARTY
_PARTY_SPLITS = {
    "birthday":  {"Catering": 0.45, "Decoration": 0.20, "Entertainment": 0.15, "Venue": 0.20},
    "wedding":   {"Catering": 0.40, "Decoration": 0.25, "Entertainment": 0.10, "Venue": 0.25},
    "corporate": {"Catering": 0.40, "Decoration": 0.10, "Entertainment": 0.10, "Venue": 0.40},
    "default":   {"Catering": 0.45, "Decoration": 0.20, "Entertainment": 0.10, "Venue": 0.25},
}


def fallback_party(payload: dict) -> dict:
    budget = float(payload["budget"])
    guests = int(payload["guests"])
    event = payload["event_type"]
    key = next((k for k in _PARTY_SPLITS if k in event.lower()), "default")
    split = _PARTY_SPLITS[key]
    venue_note = payload.get("venue") or "your chosen venue"
    sections = []

    catering = budget * split["Catering"]
    per_head = catering * 0.95 / guests
    sections.append({"title": "Catering", "allocated_budget": catering, "items": [
        _item(f"{event.title()} party meal boxes / buffet", "Swiggy", per_head, guests,
              "Per-plate price incl. desserts & drinks; Swiggy and Zomato list bulk-order party vendors."),
    ]})

    venue = budget * split["Venue"]
    sections.append({"title": "Venue / Stay", "allocated_budget": venue, "items": [
        _item(f"Banquet or party room near {venue_note}", "OYO", venue * 0.9, 1,
              "Use OYO for event spaces or to book rooms for out-of-town guests."),
    ]})

    deco = budget * split["Decoration"]
    sections.append({"title": "Decoration", "allocated_budget": deco, "items": [
        _item(f"{event.title()} theme decoration kit (balloons, banners, lights)", "Amazon", deco * 0.6, 1,
              "One kit covers most of the room."),
        _item("LED string lights & table centerpieces", "Flipkart", deco * 0.3, 1,
              "Inexpensive way to lift the ambience."),
    ]})

    fun = budget * split["Entertainment"]
    sections.append({"title": "Entertainment", "allocated_budget": fun, "items": [
        _item("Bluetooth party speaker + party games set", "Amazon", fun * 0.9, 1,
              "Music and games keep guests engaged without hiring a host."),
    ]})
    return _finish(
        f"A {event.lower()} plan for {guests} guests with the budget split across catering, venue, decoration and entertainment.",
        budget, sections,
        ["Get 2-3 quotes from caterers and confirm per-plate pricing including taxes.",
         "Keep ~5% of the budget aside for last-minute expenses.",
         "Confirm the final guest count 3 days ahead to avoid over-ordering."],
    )


# ---------------------------------------------------------------- JEWELRY
_JEWELRY_SPLIT = {"Necklace / Pendant": 0.40, "Earrings": 0.25, "Bangles / Bracelet": 0.25, "Ring": 0.10}


def fallback_jewelry(payload: dict, image_analysed: bool = False) -> dict:
    budget = float(payload["budget"])
    occasion = payload["occasion"]
    style = payload.get("style") or "elegant"
    metal = payload.get("metal") or "Any"
    metal_txt = "" if metal.lower() == "any" else f"{metal} "
    sections = []
    for i, (title, frac) in enumerate(_JEWELRY_SPLIT.items()):
        share = budget * frac
        platform = "Amazon" if i % 2 == 0 else "Flipkart"
        sections.append({"title": title, "allocated_budget": share, "items": [
            _item(f"{style.title()} {metal_txt}{title.split(' /')[0].lower()} for {occasion.lower()}",
                  platform, share * 0.9, 1,
                  f"Matches a {style.lower()} look and fits the {occasion.lower()} occasion."),
        ]})
    tips = ["Choose one statement piece and keep the rest simple.",
            "Check return policy and hallmark/certification for precious metals."]
    if image_analysed:
        tips.append("Your outfit photo was received, but AI colour matching needs a working Gemini key.")
    return _finish(
        f"A coordinated {style.lower()} jewelry set for a {occasion.lower()} within your budget.",
        budget, sections, tips,
    )


def fallback(category: str, payload: dict, image_analysed: bool = False) -> dict:
    if category == "home":
        return fallback_home(payload)
    if category == "party":
        return fallback_party(payload)
    if category == "jewelry":
        return fallback_jewelry(payload, image_analysed)
    raise ValueError(f"Unknown category: {category}")

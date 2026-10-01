"""Shared Jinja2 environment with a few helper filters."""
from fastapi.templating import Jinja2Templates

from .config import BASE_DIR

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def inr(value) -> str:
    try:
        return "₹{:,.0f}".format(float(value))
    except (TypeError, ValueError):
        return "₹0"


def nice_date(value) -> str:
    try:
        return str(value)[:16].replace("T", " ") + " UTC"
    except Exception:  # pragma: no cover
        return ""


CATEGORY_LABELS = {"home": "Home Interior", "party": "Party", "jewelry": "Jewelry"}


def category_label(value) -> str:
    return CATEGORY_LABELS.get(value, str(value).title())


templates.env.filters["inr"] = inr
templates.env.filters["nice_date"] = nice_date
templates.env.filters["category_label"] = category_label

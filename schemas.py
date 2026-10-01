"""Input schemas (Pydantic) for the three planners and auth."""
import re
from typing import List

from pydantic import BaseModel, Field, field_validator

MAX_BUDGET = 100_000_000  # 10 crore INR - sanity limit


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    quantity: int = Field(ge=1, le=50)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class RoomIn(BaseModel):
    room_type: str = Field(min_length=1, max_length=40)
    items: List[ItemIn] = Field(min_length=1, max_length=20)

    @field_validator("room_type")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class HomeRequest(BaseModel):
    budget: float = Field(gt=0, le=MAX_BUDGET)
    style: str = Field(default="", max_length=60)
    notes: str = Field(default="", max_length=500)
    rooms: List[RoomIn] = Field(min_length=1, max_length=10)


class PartyRequest(BaseModel):
    budget: float = Field(gt=0, le=MAX_BUDGET)
    guests: int = Field(ge=1, le=5000)
    event_type: str = Field(min_length=1, max_length=40)
    venue: str = Field(default="", max_length=120)
    city: str = Field(default="", max_length=60)
    notes: str = Field(default="", max_length=500)

    @field_validator("event_type", "venue", "city", "notes")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class JewelryRequest(BaseModel):
    budget: float = Field(gt=0, le=MAX_BUDGET)
    occasion: str = Field(min_length=1, max_length=60)
    style: str = Field(default="", max_length=60)
    metal: str = Field(default="Any", max_length=30)
    notes: str = Field(default="", max_length=500)

    @field_validator("occasion", "style", "metal", "notes")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_registration(username: str, email: str, password: str, confirm: str) -> str | None:
    """Return an error message, or None if the input is fine."""
    if not USERNAME_RE.match(username):
        return "Username must be 3-30 characters (letters, numbers, . _ -)."
    if not EMAIL_RE.match(email) or len(email) > 120:
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password.encode("utf-8")) > 72:
        return "Password is too long (max 72 bytes)."
    if password != confirm:
        return "Passwords do not match."
    return None

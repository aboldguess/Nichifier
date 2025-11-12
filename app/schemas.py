"""app.schemas
=================
Mini-README: Defines Pydantic models used for request validation and response
serialization throughout the API. Schemas mirror ORM models while constraining the
fields exposed to clients.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from .models import UserRole


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str


class UserRead(BaseModel):
    """Representation of a user returned to clients."""

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_premium: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """JWT token response body."""

    access_token: str
    token_type: str = "bearer"


class NicheCreate(BaseModel):
    """Payload for creating a new niche."""

    name: str
    short_description: str
    detailed_description: Optional[str] = None
    splash_image_url: Optional[str] = None
    newsletter_price: float = 0
    report_price: float = 0
    voice_instructions: Optional[str] = None
    style_guide: Optional[str] = None


class NicheRead(BaseModel):
    """Public representation of a niche."""

    id: int
    name: str
    short_description: str
    detailed_description: Optional[str]
    splash_image_url: Optional[str]
    newsletter_price: float
    report_price: float
    voice_instructions: Optional[str]
    style_guide: Optional[str]

    class Config:
        from_attributes = True


class NicheUpdate(BaseModel):
    """Payload for updating an existing niche with optional fields."""

    name: Optional[str] = None
    short_description: Optional[str] = None
    detailed_description: Optional[str] = None
    splash_image_url: Optional[str] = None
    newsletter_price: Optional[float] = None
    report_price: Optional[float] = None
    voice_instructions: Optional[str] = None
    style_guide: Optional[str] = None


class SubscriptionCreate(BaseModel):
    """Payload to create or update a subscription."""

    niche_id: int
    wants_newsletter: bool = True
    wants_report: bool = False


class SubscriptionRead(BaseModel):
    """Public representation of a subscription."""

    id: int
    niche_id: int
    wants_newsletter: bool
    wants_report: bool
    started_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True
